#!/usr/bin/env python3
"""
回测框架 - 用训练好的模型对历史数据做模拟交易

策略：
1. 每个交易日对 Top 100 股票做预测
2. 模型给出"买入"信号（prob >= 0.6）的股票纳入持仓
3. 持有 5 天后卖出
4. 计算收益率、胜率、最大回撤等指标
"""

import sys
import json
import sqlite3
import logging
import numpy as np
from pathlib import Path
from datetime import date, timedelta
from collections import defaultdict

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from neotrade3.ml.autore.train import MLTrainer, N_ESTIMATORS, MAX_DEPTH, MIN_SAMPLES_SPLIT, MIN_SAMPLES_LEAF

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)

DB_PATH = Path("var/db/stock_data.db")
MODEL_PATH = Path("var/models/autore_v2_best.pkl")
OUTPUT_DIR = Path("var/backtest_results")


class BacktestEngine:
    """回测引擎"""

    def __init__(self, db_path: Path, model_path: Path):
        self.db_path = db_path
        self.trainer = MLTrainer(db_path)
        self.trainer.load_model(str(model_path))
        logger.info(f"模型加载成功: {model_path}")

    def run_backtest(
        self,
        start_date: date,
        end_date: date,
        hold_days: int = 5,
        buy_threshold: float = 0.6,
        sell_threshold: float = 0.4,
        max_positions: int = 10,
        initial_capital: float = 1000000.0,
    ) -> dict:
        """
        运行回测

        Args:
            start_date: 回测开始日期
            end_date: 回测结束日期
            hold_days: 持有天数
            buy_threshold: 买入概率阈值
            sell_threshold: 卖出概率阈值
            max_positions: 最大持仓数
            initial_capital: 初始资金

        Returns:
            回测结果字典
        """
        logger.info(f"回测区间: {start_date} ~ {end_date}")
        logger.info(f"参数: hold={hold_days}d, buy>={buy_threshold}, max_pos={max_positions}")

        # 获取交易日历
        trading_dates = self._get_trading_dates(start_date, end_date)
        logger.info(f"交易日数量: {len(trading_dates)}")

        # 回测状态
        capital = initial_capital
        positions = {}  # {code: {buy_date, buy_price, shares}}
        daily_values = []
        trades = []
        all_signals = []

        for i, current_date in enumerate(trading_dates):
            # 1. 检查持仓是否到期
            closed = []
            for code, pos in positions.items():
                days_held = (current_date - pos['buy_date']).days
                # 计算交易日持有天数
                held_dates = self._count_trading_days(pos['buy_date'], current_date)
                if held_dates >= hold_days:
                    # 卖出
                    sell_price = self._get_close_price(code, current_date)
                    if sell_price and sell_price > 0:
                        sell_return = (sell_price - pos['buy_price']) / pos['buy_price'] * 100
                        sell_amount = sell_price * pos['shares']
                        capital += sell_amount
                        trades.append({
                            'code': code,
                            'buy_date': pos['buy_date'].isoformat(),
                            'sell_date': current_date.isoformat(),
                            'buy_price': round(pos['buy_price'], 2),
                            'sell_price': round(sell_price, 2),
                            'return_pct': round(sell_return, 2),
                            'shares': pos['shares'],
                            'profit': round(sell_amount - pos['buy_price'] * pos['shares'], 2),
                        })
                        closed.append(code)
            for code in closed:
                del positions[code]

            # 2. 生成信号（每 5 个交易日一次，避免过于频繁）
            if i % 5 == 0 and len(positions) < max_positions:
                signals = self._generate_signals(current_date, buy_threshold)
                all_signals.extend(signals)

                # 3. 买入信号最强的股票
                buy_signals = [s for s in signals if s['signal'] == 'buy']
                buy_signals.sort(key=lambda x: x['probability'], reverse=True)

                for sig in buy_signals[:max_positions - len(positions)]:
                    price = self._get_close_price(sig['code'], current_date)
                    if price and price > 0:
                        # 等权分配资金
                        per_position = capital / (max_positions - len(positions) + len(buy_signals))
                        shares = int(per_position / price / 100) * 100  # A股100股整数倍
                        if shares >= 100:
                            cost = price * shares
                            if cost <= capital:
                                capital -= cost
                                positions[sig['code']] = {
                                    'buy_date': current_date,
                                    'buy_price': price,
                                    'shares': shares,
                                }
                                trades.append({
                                    'code': sig['code'],
                                    'buy_date': current_date.isoformat(),
                                    'sell_date': None,
                                    'buy_price': round(price, 2),
                                    'return_pct': None,
                                    'shares': shares,
                                    'profit': None,
                                })

            # 4. 计算当日总资产
            position_value = sum(
                self._get_close_price(code, current_date) * pos['shares']
                for code, pos in positions.items()
                if self._get_close_price(code, current_date)
            )
            total_value = capital + position_value
            daily_values.append({
                'date': current_date.isoformat(),
                'capital': round(capital, 2),
                'position_value': round(position_value, 2),
                'total_value': round(total_value, 2),
                'num_positions': len(positions),
            })

            if (i + 1) % 20 == 0:
                logger.info(f"  {current_date}: 总资产={total_value:,.0f}, 持仓={len(positions)}")

        # 计算回测指标
        metrics = self._calculate_metrics(daily_values, trades, initial_capital)
        metrics['signals'] = all_signals
        metrics['daily_values'] = daily_values
        metrics['trades'] = [t for t in trades if t.get('sell_date')]

        return metrics

    def _get_trading_dates(self, start: date, end: date) -> list[date]:
        """获取交易日历"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        cursor.execute(
            "SELECT DISTINCT trade_date FROM daily_prices WHERE trade_date BETWEEN ? AND ? ORDER BY trade_date",
            (start.isoformat(), end.isoformat()),
        )
        dates = [date.fromisoformat(r[0]) for r in cursor.fetchall()]
        conn.close()
        return dates

    def _count_trading_days(self, start: date, end: date) -> int:
        """计算两个日期之间的交易日数"""
        dates = self._get_trading_dates(start, end)
        return len(dates)

    def _get_close_price(self, code: str, d: date) -> float | None:
        """获取收盘价"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        cursor.execute(
            "SELECT close FROM daily_prices WHERE code = ? AND trade_date = ?",
            (code, d.isoformat()),
        )
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else None

    def _generate_signals(self, target_date: date, threshold: float) -> list[dict]:
        """生成交易信号"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT s.code FROM stocks s
            JOIN daily_prices dp ON s.code = dp.code
            WHERE dp.trade_date = ? AND (s.is_delisted IS NULL OR s.is_delisted = 0)
            ORDER BY dp.amount DESC LIMIT 100
        """,
            (target_date.isoformat(),),
        )
        codes = [r[0] for r in cursor.fetchall()]
        conn.close()

        signals = []
        for code in codes:
            features = self.trainer._extract_features_for_date(code, target_date)
            if features is None:
                continue

            X = np.array([[features[f] for f in self.trainer._feature_names]])
            proba = self.trainer._model.predict_proba(X)[0]

            signal = 'hold'
            if proba[1] >= threshold:
                signal = 'buy'
            elif proba[1] <= (1 - threshold):
                signal = 'sell'

            if signal != 'hold':
                signals.append({
                    'date': target_date.isoformat(),
                    'code': code,
                    'signal': signal,
                    'probability': round(float(proba[1]), 4),
                })

        return signals

    def _calculate_metrics(self, daily_values: list, trades: list, initial_capital: float) -> dict:
        """计算回测指标"""
        if not daily_values:
            return {}

        values = [d['total_value'] for d in daily_values]
        final_value = values[-1]

        # 总收益率
        total_return = (final_value - initial_capital) / initial_capital * 100

        # 年化收益率（假设252个交易日）
        n_days = len(values)
        annual_return = (1 + total_return / 100) ** (252 / max(n_days, 1)) - 1

        # 最大回撤
        peak = values[0]
        max_drawdown = 0
        for v in values:
            if v > peak:
                peak = v
            dd = (peak - v) / peak * 100
            if dd > max_drawdown:
                max_drawdown = dd

        # 胜率（已完成交易）
        completed = [t for t in trades if t.get('sell_date') and t.get('return_pct') is not None]
        wins = [t for t in completed if t['return_pct'] > 0]
        win_rate = len(wins) / len(completed) * 100 if completed else 0

        # 平均收益
        avg_return = np.mean([t['return_pct'] for t in completed]) if completed else 0
        avg_win = np.mean([t['return_pct'] for t in wins]) if wins else 0
        avg_loss = np.mean([t['return_pct'] for t in completed if t['return_pct'] <= 0]) if [t for t in completed if t['return_pct'] <= 0] else 0

        # 盈亏比
        profit_loss_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else float('inf')

        return {
            'initial_capital': initial_capital,
            'final_value': round(final_value, 2),
            'total_return_pct': round(total_return, 2),
            'annual_return_pct': round(annual_return * 100, 2),
            'max_drawdown_pct': round(max_drawdown, 2),
            'total_trades': len(completed),
            'win_rate_pct': round(win_rate, 2),
            'avg_return_pct': round(avg_return, 2),
            'avg_win_pct': round(avg_win, 2),
            'avg_loss_pct': round(avg_loss, 2),
            'profit_loss_ratio': round(profit_loss_ratio, 2),
            'trading_days': n_days,
        }


def main():
    """运行回测"""
    if not MODEL_PATH.exists():
        logger.error(f"模型文件不存在: {MODEL_PATH}")
        logger.info("请先运行: python neotrade3/ml/autore/train.py")
        return

    engine = BacktestEngine(DB_PATH, MODEL_PATH)

    # 回测最近3个月的数据
    # 先检查数据库中最新的交易日期
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute("SELECT MAX(trade_date) FROM daily_prices")
    max_date = cursor.fetchone()[0]
    cursor.execute("SELECT MIN(trade_date) FROM daily_prices")
    min_date = cursor.fetchone()[0]
    conn.close()

    logger.info(f"数据范围: {min_date} ~ {max_date}")

    # 回测最近可用的3个月
    end = date.fromisoformat(max_date)
    start = end - timedelta(days=90)

    results = engine.run_backtest(
        start_date=start,
        end_date=end,
        hold_days=5,
        buy_threshold=0.6,
        max_positions=10,
        initial_capital=1000000.0,
    )

    # 输出结果
    print("\n" + "=" * 60)
    print("回测结果")
    print("=" * 60)
    print(f"回测区间: {start} ~ {end}")
    print(f"初始资金: ¥{results['initial_capital']:,.0f}")
    print(f"最终资产: ¥{results['final_value']:,.0f}")
    print(f"总收益率: {results['total_return_pct']:.2f}%")
    print(f"年化收益率: {results['annual_return_pct']:.2f}%")
    print(f"最大回撤: {results['max_drawdown_pct']:.2f}%")
    print(f"交易次数: {results['total_trades']}")
    print(f"胜率: {results['win_rate_pct']:.2f}%")
    print(f"平均收益: {results['avg_return_pct']:.2f}%")
    print(f"平均盈利: {results['avg_win_pct']:.2f}%")
    print(f"平均亏损: {results['avg_loss_pct']:.2f}%")
    print(f"盈亏比: {results['profit_loss_ratio']:.2f}")
    print("=" * 60)

    # 输出最近交易
    print("\n最近交易记录:")
    for t in results['trades'][-10:]:
        print(f"  {t['code']} | {t['buy_date']}→{t['sell_date']} | "
              f"¥{t['buy_price']}→¥{t['sell_price']} | {t['return_pct']:+.2f}%")

    # 保存结果
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / f"backtest_{start.isoformat()}_{end.isoformat()}.json"

    # 只保存摘要，不保存大量明细
    summary = {k: v for k, v in results.items() if k not in ('signals', 'daily_values')}
    summary['recent_trades'] = results['trades'][-20:]
    summary['signal_stats'] = {
        'total_signals': len(results['signals']),
        'buy_signals': len([s for s in results['signals'] if s['signal'] == 'buy']),
        'sell_signals': len([s for s in results['signals'] if s['signal'] == 'sell']),
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    logger.info(f"\n结果已保存: {output_path}")


if __name__ == "__main__":
    main()
