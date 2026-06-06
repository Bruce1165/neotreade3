#!/usr/bin/env python3
"""
train.py - ML 模型训练脚本 (Agent 可修改)

这是 autoresearch 框架中的核心实验文件。
Agent 可以修改模型参数、特征选择、训练配置等。
评估指标: out_of_sample_accuracy (样本外准确率)
"""

from __future__ import annotations

import logging
import pickle
import sqlite3
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import numpy as np

# ============================================================
# Agent 可调整的配置 (默认值，可被修改)
# ============================================================

# 模型参数
N_ESTIMATORS = 300
MAX_DEPTH = 20
MIN_SAMPLES_SPLIT = 10
MIN_SAMPLES_LEAF = 8

# 训练参数
LOOKBACK_DAYS = 120
FORWARD_DAYS = 5
THRESHOLD_UP = 1.5
THRESHOLD_DOWN = -1.5
TEST_SIZE = 0.2
UNIVERSE_SIZE = 100  # 每个采样日选取的股票数量

# 市值筛选（单位：亿元）
USE_MARKET_CAP_FILTER = False
MARKET_CAP_MIN = 100   # 最小市值 100 亿
MARKET_CAP_MAX = 500   # 最大市值 500 亿
# 注意：数据库中 total_market_cap 单位为元，查询时需转换

# 技术面特征开关
USE_RSI = False
USE_MACD = False
USE_BOLLINGER = True
USE_VOLATILITY_REGIME = True
USE_MARKET_BREADTH = True

# 基本面特征开关
USE_FUNDAMENTAL = False  # 是否使用基本面特征
USE_PE = True           # 市盈率
USE_PB = True           # 市净率
USE_ROE = True          # 净资产收益率
USE_REVENUE_GROWTH = True  # 营收增长率
USE_PROFIT_GROWTH = True   # 利润增长率
USE_EPS = True          # 每股收益

# Universe 采样策略
USE_SECTOR_WEIGHTING = False  # 是否使用板块加权采样
SECTOR_BOOST_FACTOR = 2.0     # 热门板块权重倍数
HOT_SECTOR_COUNT = 10         # 热门板块数量

# 固定路径
DB_PATH = Path("var/db/stock_data.db")
MODEL_DIR = Path("var/models")
OUTPUT_FILE = Path("neotrade3/ml/autore/last_result.txt")

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


@dataclass
class TrainingConfig:
    lookback_days: int = 180
    forward_days: int = 5
    threshold_up: float = 2.0
    threshold_down: float = -2.0
    test_size: float = 0.2
    random_state: int = 42


class MLTrainer:
    """可配置的 ML 训练器"""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self._model: Any | None = None
        self._feature_names: list[str] = []
        self._init_features()

    def _init_features(self) -> None:
        """根据配置初始化特征列表"""
        self._feature_names = [
            "return_5d", "return_20d", "return_60d",
            "volatility_20d",
            "volume_ratio", "volume_trend_5d",
        ]
        if USE_RSI:
            self._feature_names.append("rsi_14")
        if USE_MACD:
            self._feature_names.append("macd_histogram")
        if USE_BOLLINGER:
            self._feature_names.append("bollinger_position")
        if USE_VOLATILITY_REGIME:
            self._feature_names.append("volatility_regime")
        
        # 基本面特征
        if USE_FUNDAMENTAL:
            if USE_PE:
                self._feature_names.append("pe_ratio")
            if USE_PB:
                self._feature_names.append("pb_ratio")
            if USE_ROE:
                self._feature_names.append("roe")
            if USE_REVENUE_GROWTH:
                self._feature_names.append("revenue_growth")
            if USE_PROFIT_GROWTH:
                self._feature_names.append("profit_growth")
            if USE_EPS:
                self._feature_names.append("eps")
        
        self._feature_names.extend([
            "market_return_5d", "market_return_20d",
            "market_volatility", "sector_return_5d",
        ])
        if USE_MARKET_BREADTH:
            self._feature_names.append("market_breadth")

    @staticmethod
    def _calc_rsi(closes: list[float], period: int = 14) -> float:
        if len(closes) < period + 1:
            return 50.0
        deltas = [closes[i] - closes[i + 1] for i in range(period)]
        gains = [d for d in deltas if d > 0]
        losses = [-d for d in deltas if d < 0]
        avg_gain = np.mean(gains) if gains else 0
        avg_loss = np.mean(losses) if losses else 0.001
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    @staticmethod
    def _calc_macd_histogram(closes: list[float]) -> float:
        if len(closes) < 26:
            return 0.0
        def ema(data, period):
            result = [data[0]]
            k = 2 / (period + 1)
            for i in range(1, len(data)):
                result.append(data[i] * k + result[-1] * (1 - k))
            return result[-1]
        ema12 = ema(closes[:30], 12)
        ema26 = ema(closes[:30], 26)
        return (ema12 - ema26) / closes[0] * 100 if closes[0] > 0 else 0

    @staticmethod
    def _calc_bollinger_position(closes: list[float], period: int = 20) -> float:
        if len(closes) < period:
            return 0.5
        recent = closes[:period]
        mean = np.mean(recent)
        std = np.std(recent)
        if std == 0:
            return 0.5
        upper = mean + 2 * std
        lower = mean - 2 * std
        return max(0.0, min(1.0, (closes[0] - lower) / (upper - lower)))

    def _extract_features_for_date(
        self, code: str, target_date: date
    ) -> dict[str, float] | None:
        """提取单只股票在指定日期的特征"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                SELECT close, volume, amount
                FROM daily_prices
                WHERE code = ? AND trade_date <= ?
                ORDER BY trade_date DESC
                LIMIT 70
            """,
                (code, target_date.isoformat()),
            )
            rows = cursor.fetchall()
            if len(rows) < 60:
                return None

            closes = [r[0] for r in rows if r[0] is not None]
            volumes = [r[1] or 0 for r in rows]

            if len(closes) < 60:
                return None

            # 动量特征
            return_5d = (closes[0] - closes[4]) / closes[4] * 100 if closes[4] > 0 else 0
            return_20d = (closes[0] - closes[19]) / closes[19] * 100 if closes[19] > 0 else 0
            return_60d = (closes[0] - closes[59]) / closes[59] * 100 if closes[59] > 0 else 0

            # 波动率
            daily_returns = []
            for i in range(min(19, len(closes) - 1)):
                if closes[i + 1] > 0:
                    daily_returns.append((closes[i] - closes[i + 1]) / closes[i + 1])
            volatility_20d = np.std(daily_returns) * np.sqrt(252) * 100 if daily_returns else 0

            # 波动率状态
            volatility_regime = 1.0
            if USE_VOLATILITY_REGIME:
                vol_list = []
                for start in range(0, min(40, len(closes) - 20)):
                    window = closes[start:start+20]
                    if len(window) >= 2:
                        rets = [(window[i] - window[i+1]) / window[i+1] for i in range(len(window)-1) if window[i+1] > 0]
                        if rets:
                            vol_list.append(np.std(rets) * np.sqrt(252) * 100)
                vol_avg = np.mean(vol_list) if vol_list else volatility_20d
                volatility_regime = volatility_20d / vol_avg if vol_avg > 0 else 1.0

            # 成交量
            valid_vols = [v for v in volumes[1:20] if v > 0]
            volume_ratio = volumes[0] / np.mean(valid_vols) if valid_vols else 1.0
            recent_vol = np.mean(volumes[:5]) if volumes[:5] else 0
            older_vol = np.mean(volumes[5:20]) if volumes[5:20] else 0
            volume_trend_5d = recent_vol / older_vol if older_vol > 0 else 1.0

            # 技术指标
            rsi_14 = self._calc_rsi(closes) if USE_RSI else 50.0
            macd_histogram = self._calc_macd_histogram(closes) if USE_MACD else 0.0
            bollinger_position = self._calc_bollinger_position(closes) if USE_BOLLINGER else 0.5

            # 基本面
            if USE_FUNDAMENTAL:
                cursor.execute(
                    "SELECT pe_ratio, pb_ratio, roe, revenue_growth, profit_growth, eps FROM stocks WHERE code = ?", (code,)
                )
                fund = cursor.fetchone()
                pe_ratio = fund[0] if fund and fund[0] else 0
                pb_ratio = fund[1] if fund and fund[1] else 0
                roe = fund[2] if fund and fund[2] else 0
                revenue_growth = fund[3] if fund and fund[3] else 0
                profit_growth = fund[4] if fund and fund[4] else 0
                eps = fund[5] if fund and fund[5] else 0
            else:
                pe_ratio = pb_ratio = roe = revenue_growth = profit_growth = eps = 0

            # 市场环境
            cursor.execute(
                """
                SELECT close FROM daily_prices
                WHERE code = '000001' AND trade_date <= ?
                ORDER BY trade_date DESC LIMIT 21
            """,
                (target_date.isoformat(),),
            )
            market_rows = cursor.fetchall()
            market_return_5d, market_return_20d, market_volatility = 0, 0, 0
            if len(market_rows) >= 21:
                m_closes = [r[0] for r in market_rows]
                market_return_5d = (m_closes[0] - m_closes[5]) / m_closes[5] * 100
                market_return_20d = (m_closes[0] - m_closes[20]) / m_closes[20] * 100
                m_rets = [(m_closes[i] - m_closes[i+1]) / m_closes[i+1] for i in range(min(20, len(m_closes)-1)) if m_closes[i+1] != 0]
                market_volatility = np.std(m_rets) * np.sqrt(252) * 100 if m_rets else 0

            # 板块
            cursor.execute("SELECT sector_lv1 FROM stocks WHERE code = ?", (code,))
            sector_row = cursor.fetchone()
            sector_return_5d = 0
            if sector_row and sector_row[0]:
                cursor.execute(
                    """
                    SELECT AVG(dp.close) FROM daily_prices dp
                    JOIN stocks s ON dp.code = s.code
                    WHERE s.sector_lv1 = ? AND dp.trade_date IN (?, ?)
                    GROUP BY dp.trade_date ORDER BY dp.trade_date DESC LIMIT 2
                """,
                    (sector_row[0], target_date.isoformat(), (target_date - timedelta(days=5)).isoformat()),
                )
                sector_closes = cursor.fetchall()
                if len(sector_closes) >= 2:
                    sector_return_5d = (sector_closes[0][0] - sector_closes[1][0]) / sector_closes[1][0] * 100

            # 市场广度
            market_breadth = 50.0
            if USE_MARKET_BREADTH:
                cursor.execute(
                    "SELECT COUNT(DISTINCT code) FROM daily_prices WHERE trade_date = ?",
                    (target_date.isoformat(),),
                )
                total_stocks = cursor.fetchone()[0] or 1
                market_breadth = 50.0  # 简化版本

            features = {
                "return_5d": return_5d,
                "return_20d": return_20d,
                "return_60d": return_60d,
                "volatility_20d": volatility_20d,
                "volume_ratio": volume_ratio,
                "volume_trend_5d": volume_trend_5d,
                "market_return_5d": market_return_5d,
                "market_return_20d": market_return_20d,
                "market_volatility": market_volatility,
                "sector_return_5d": sector_return_5d,
            }
            
            # 技术面特征
            if USE_RSI:
                features["rsi_14"] = rsi_14
            if USE_MACD:
                features["macd_histogram"] = macd_histogram
            if USE_BOLLINGER:
                features["bollinger_position"] = bollinger_position
            if USE_VOLATILITY_REGIME:
                features["volatility_regime"] = volatility_regime
            if USE_MARKET_BREADTH:
                features["market_breadth"] = market_breadth
            
            # 基本面特征
            if USE_FUNDAMENTAL:
                if USE_PE:
                    features["pe_ratio"] = pe_ratio
                if USE_PB:
                    features["pb_ratio"] = pb_ratio
                if USE_ROE:
                    features["roe"] = roe
                if USE_REVENUE_GROWTH:
                    features["revenue_growth"] = revenue_growth
                if USE_PROFIT_GROWTH:
                    features["profit_growth"] = profit_growth
                if USE_EPS:
                    features["eps"] = eps

            return features

        finally:
            conn.close()

    def _get_forward_return(self, code: str, from_date: date, days: int = 5) -> float | None:
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT close FROM daily_prices
                WHERE code = ? AND trade_date >= ?
                ORDER BY trade_date ASC LIMIT ?
            """,
                (code, from_date.isoformat(), days + 1),
            )
            rows = cursor.fetchall()
            if len(rows) < days + 1:
                return None
            start_price, end_price = rows[0][0], rows[days][0]
            if not start_price or not end_price or start_price == 0:
                return None
            return (end_price - start_price) / start_price * 100
        finally:
            conn.close()

    def build_dataset(
        self, config: TrainingConfig | None = None
    ) -> tuple[np.ndarray, np.ndarray]:
        """构建训练数据集"""
        if config is None:
            config = TrainingConfig()

        end_date = date.today()
        start_date = end_date - timedelta(days=config.lookback_days)

        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        cursor.execute(
            "SELECT DISTINCT trade_date FROM daily_prices WHERE trade_date BETWEEN ? AND ? ORDER BY trade_date",
            (start_date.isoformat(), end_date.isoformat()),
        )
        trading_dates = [date.fromisoformat(r[0]) for r in cursor.fetchall()]
        conn.close()

        sample_dates = trading_dates[::5]
        X_list, y_list = [], []

        for sample_date in sample_dates:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            if USE_MARKET_CAP_FILTER:
                # 市值筛选：聚焦指定市值区间，按成交额排序
                cap_min_yuan = MARKET_CAP_MIN * 1e8   # 亿元 → 元
                cap_max_yuan = MARKET_CAP_MAX * 1e8
                cursor.execute(
                    """
                    SELECT s.code FROM stocks s
                    JOIN daily_prices dp ON s.code = dp.code
                    WHERE dp.trade_date = ? 
                      AND (s.is_delisted IS NULL OR s.is_delisted = 0)
                      AND s.total_market_cap BETWEEN ? AND ?
                    ORDER BY dp.amount DESC LIMIT ?
                """,
                    (sample_date.isoformat(), cap_min_yuan, cap_max_yuan, UNIVERSE_SIZE),
                )
            else:
                cursor.execute(
                    """
                    SELECT s.code FROM stocks s
                    JOIN daily_prices dp ON s.code = dp.code
                    WHERE dp.trade_date = ? AND (s.is_delisted IS NULL OR s.is_delisted = 0)
                    ORDER BY dp.amount DESC LIMIT ?
                """,
                    (sample_date.isoformat(), UNIVERSE_SIZE),
                )
            codes = [r[0] for r in cursor.fetchall()]
            conn.close()

            for code in codes:
                features = self._extract_features_for_date(code, sample_date)
                if features is None:
                    continue
                forward_return = self._get_forward_return(code, sample_date, config.forward_days)
                if forward_return is None:
                    continue

                if forward_return > config.threshold_up:
                    label = 1
                elif forward_return < config.threshold_down:
                    label = 0
                else:
                    continue

                X_list.append([features[f] for f in self._feature_names])
                y_list.append(label)

        X = np.array(X_list)
        y = np.array(y_list)

        # 样本平衡
        pos_idx = np.where(y == 1)[0]
        neg_idx = np.where(y == 0)[0]
        min_samples = min(len(pos_idx), len(neg_idx))
        if min_samples > 0:
            np.random.seed(42)
            pos_sample = np.random.choice(pos_idx, min_samples, replace=False)
            neg_sample = np.random.choice(neg_idx, min_samples, replace=False)
            balanced_idx = np.concatenate([pos_sample, neg_sample])
            np.random.shuffle(balanced_idx)
            X = X[balanced_idx]
            y = y[balanced_idx]

        logger.info(f"Dataset: {len(y)} samples (up: {sum(y)}, down: {len(y) - sum(y)})")
        return X, y

    def train(self, config: TrainingConfig | None = None) -> dict[str, Any]:
        """训练模型"""
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

        X, y = self.build_dataset(config)
        if len(X) < 100:
            raise ValueError(f"Insufficient data: {len(X)} samples")

        if config is None:
            config = TrainingConfig()

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=config.test_size, random_state=config.random_state, stratify=y
        )

        self._model = RandomForestClassifier(
            n_estimators=N_ESTIMATORS,
            max_depth=MAX_DEPTH,
            min_samples_split=MIN_SAMPLES_SPLIT,
            min_samples_leaf=MIN_SAMPLES_LEAF,
            random_state=config.random_state,
            n_jobs=-1,
        )
        self._model.fit(X_train, y_train)

        y_pred = self._model.predict(X_test)
        metrics = {
            "accuracy": accuracy_score(y_test, y_pred),
            "precision": precision_score(y_test, y_pred, zero_division=0),
            "recall": recall_score(y_test, y_pred, zero_division=0),
            "f1": f1_score(y_test, y_pred, zero_division=0),
            "train_samples": len(X_train),
            "test_samples": len(X_test),
        }
        return metrics

    def save_model(self, path: str) -> None:
        """保存模型到文件"""
        import joblib
        if self._model is None:
            raise RuntimeError("Model not trained")
        joblib.dump({
            'model': self._model,
            'feature_names': self._feature_names,
            'config': {
                'n_estimators': N_ESTIMATORS,
                'max_depth': MAX_DEPTH,
                'min_samples_split': MIN_SAMPLES_SPLIT,
                'min_samples_leaf': MIN_SAMPLES_LEAF,
                'lookback_days': LOOKBACK_DAYS,
                'forward_days': FORWARD_DAYS,
                'threshold_up': THRESHOLD_UP,
                'threshold_down': THRESHOLD_DOWN,
            }
        }, path)

    def load_model(self, path: str) -> None:
        """从文件加载模型"""
        import joblib
        data = joblib.load(path)
        self._model = data['model']
        self._feature_names = data['feature_names']

    def get_feature_importance(self) -> list[tuple[str, float]]:
        """获取特征重要性排序"""
        if self._model is None:
            raise RuntimeError("Model not trained")
        importance = self._model.feature_importances_
        return sorted(zip(self._feature_names, importance), key=lambda x: x[1], reverse=True)

    def out_of_sample_test(self) -> float:
        """样本外测试 (April 2025)"""
        test_start = date(2025, 4, 1)
        test_end = date(2025, 4, 30)

        if self._model is None:
            raise RuntimeError("Model not trained")

        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        cursor.execute(
            "SELECT DISTINCT trade_date FROM daily_prices WHERE trade_date BETWEEN ? AND ? ORDER BY trade_date",
            (test_start.isoformat(), test_end.isoformat()),
        )
        test_dates = [date.fromisoformat(r[0]) for r in cursor.fetchall()]
        conn.close()

        sample_dates = test_dates[::5]
        predictions, actuals = [], []

        for sample_date in sample_dates:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            if USE_MARKET_CAP_FILTER:
                cap_min_yuan = MARKET_CAP_MIN * 1e8
                cap_max_yuan = MARKET_CAP_MAX * 1e8
                cursor.execute(
                    """
                    SELECT s.code FROM stocks s
                    JOIN daily_prices dp ON s.code = dp.code
                    WHERE dp.trade_date = ? 
                      AND (s.is_delisted IS NULL OR s.is_delisted = 0)
                      AND s.total_market_cap BETWEEN ? AND ?
                    ORDER BY dp.amount DESC LIMIT ?
                """,
                    (sample_date.isoformat(), cap_min_yuan, cap_max_yuan, min(UNIVERSE_SIZE, 200)),
                )
            else:
                cursor.execute(
                    """
                    SELECT s.code FROM stocks s
                    JOIN daily_prices dp ON s.code = dp.code
                    WHERE dp.trade_date = ? AND (s.is_delisted IS NULL OR s.is_delisted = 0)
                    ORDER BY dp.amount DESC LIMIT ?
                """,
                    (sample_date.isoformat(), min(UNIVERSE_SIZE, 200)),
                )
            codes = [r[0] for r in cursor.fetchall()]
            conn.close()

            for code in codes:
                features = self._extract_features_for_date(code, sample_date)
                if features is None:
                    continue
                forward_return = self._get_forward_return(code, sample_date, 5)
                if forward_return is None:
                    continue

                X = np.array([[features[f] for f in self._feature_names]])
                proba = self._model.predict_proba(X)[0]

                if proba[1] >= 0.6:
                    pred = 1
                elif proba[1] <= 0.4:
                    pred = 0
                else:
                    continue

                actual = 1 if forward_return > 2.0 else (0 if forward_return < -2.0 else None)
                if actual is not None:
                    predictions.append(pred)
                    actuals.append(actual)

        if len(predictions) < 10:
            return 0.5
        correct = sum(1 for p, a in zip(predictions, actuals) if p == a)
        return correct / len(predictions)


def main():
    """主函数 - 运行单次实验"""
    logger.info("=" * 50)
    logger.info("ML Autore Experiment")
    logger.info("=" * 50)
    logger.info(f"N_ESTIMATORS = {N_ESTIMATORS}")
    logger.info(f"MAX_DEPTH = {MAX_DEPTH}")
    logger.info(f"LOOKBACK_DAYS = {LOOKBACK_DAYS}")
    logger.info(f"THRESHOLD_UP = {THRESHOLD_UP}")
    logger.info(f"THRESHOLD_DOWN = {THRESHOLD_DOWN}")
    logger.info(f"USE_RSI = {USE_RSI}, USE_MACD = {USE_MACD}")
    logger.info(f"USE_BOLLINGER = {USE_BOLLINGER}, USE_VOLATILITY_REGIME = {USE_VOLATILITY_REGIME}")
    logger.info(f"USE_MARKET_BREADTH = {USE_MARKET_BREADTH}")
    logger.info(f"USE_FUNDAMENTAL = {USE_FUNDAMENTAL}")
    if USE_FUNDAMENTAL:
        logger.info(f"  USE_PE={USE_PE}, USE_PB={USE_PB}, USE_ROE={USE_ROE}")
        logger.info(f"  USE_REVENUE_GROWTH={USE_REVENUE_GROWTH}, USE_PROFIT_GROWTH={USE_PROFIT_GROWTH}, USE_EPS={USE_EPS}")
    logger.info(f"USE_MARKET_CAP_FILTER = {USE_MARKET_CAP_FILTER}")
    if USE_MARKET_CAP_FILTER:
        logger.info(f"MARKET_CAP_RANGE = {MARKET_CAP_MIN}-{MARKET_CAP_MAX} 亿")
    logger.info(f"UNIVERSE_SIZE = {UNIVERSE_SIZE}")

    config = TrainingConfig(
        lookback_days=LOOKBACK_DAYS,
        forward_days=FORWARD_DAYS,
        threshold_up=THRESHOLD_UP,
        threshold_down=THRESHOLD_DOWN,
        test_size=TEST_SIZE,
    )

    trainer = MLTrainer(DB_PATH)

    # 样本内训练
    metrics = trainer.train(config)
    logger.info(f"\nIn-sample: accuracy={metrics['accuracy']:.3f}, precision={metrics['precision']:.3f}")

    # 样本外测试
    oos_accuracy = trainer.out_of_sample_test()
    logger.info(f"Out-of-sample accuracy: {oos_accuracy:.3f}")

    # 保存模型
    model_path = MODEL_DIR / "autore_v2_best.pkl"
    model_path.parent.mkdir(parents=True, exist_ok=True)
    trainer.save_model(str(model_path))
    logger.info(f"\nModel saved to: {model_path}")
    
    # 输出特征重要性
    importance = trainer.get_feature_importance()
    logger.info("\nTop 10 Feature Importance:")
    for feat, imp in importance[:10]:
        logger.info(f"  {feat}: {imp:.4f}")

    # 输出结果
    result = oos_accuracy
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(f"accuracy = {result:.4f}")

    print(f"\n=== RESULT ===")
    print(f"out_of_sample_accuracy = {result:.4f}")
    print(f"==============")

    return result


if __name__ == "__main__":
    main()
