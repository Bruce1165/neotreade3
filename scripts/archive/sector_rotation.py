#!/usr/bin/env python3
"""
板块轮动 + 低频交易策略引擎

核心逻辑：
1. 每周计算板块强度排名（动量+资金流+领涨比例）
2. 选出 Top 3 强势板块
3. 在强势板块内选出领涨股（趋势最强+放量确认）
4. 生成买入/卖出信号

适合低频交易者：每周操作一次，持仓1-2周
"""

import sqlite3
import logging
import numpy as np
from pathlib import Path
from datetime import date, timedelta
from dataclasses import dataclass, field
from typing import Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)

DB_PATH = Path("var/db/stock_data.db")


@dataclass
class SectorScore:
    """板块评分"""
    sector: str
    name: str
    momentum_5d: float = 0.0    # 5日动量
    momentum_20d: float = 0.0   # 20日动量
    volume_ratio: float = 0.0   # 量比（近期vs远期）
    advance_ratio: float = 0.0  # 上涨比例
    leader_strength: float = 0.0  # 领涨股强度
    composite_score: float = 0.0  # 综合评分
    stock_count: int = 0


@dataclass
class StockSignal:
    """个股信号"""
    code: str
    name: str
    sector: str
    signal: str = "hold"  # buy / sell / hold
    confidence: float = 0.0
    reasons: list = field(default_factory=list)
    # 增长确定性指标
    consecutive_up_days: int = 0  # 连续上涨天数
    volume_breakout: bool = False  # 放量突破
    ma_cross: str = ""  # 均线交叉信号
    trend_strength: float = 0.0  # 趋势强度


class SectorRotationEngine:
    """板块轮动引擎"""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path

    def _get_conn(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self.db_path))

    def get_sector_strength(self, target_date: date) -> list[SectorScore]:
        """
        计算所有板块的强度评分

        评分维度：
        1. 动量（5日/20日涨幅）
        2. 资金流（量比变化）
        3. 领涨比例（板块内上涨股票占比）
        4. 领涨股强度（板块内最强股的涨幅）
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        # 获取所有板块
        cursor.execute("""
            SELECT DISTINCT sector_lv1 FROM stocks
            WHERE sector_lv1 IS NOT NULL AND (is_delisted IS NULL OR is_delisted = 0)
        """)
        sectors = [r[0] for r in cursor.fetchall()]
        conn.close()

        scores = []
        for sector in sectors:
            score = self._calc_sector_score(sector, target_date)
            if score and score.stock_count >= 5:  # 至少5只股票才有统计意义
                scores.append(score)

        # 按综合评分排序
        scores.sort(key=lambda x: x.composite_score, reverse=True)
        return scores

    def _calc_sector_score(self, sector: str, target_date: date) -> Optional[SectorScore]:
        """计算单个板块的评分"""
        conn = self._get_conn()
        cursor = conn.cursor()

        # 获取板块内所有股票在目标日期的行情
        cursor.execute("""
            SELECT dp.code, dp.close, dp.amount, dp.volume, dp.pct_change
            FROM daily_prices dp
            JOIN stocks s ON dp.code = s.code
            WHERE s.sector_lv1 = ? AND dp.trade_date = ?
              AND (s.is_delisted IS NULL OR s.is_delisted = 0)
              AND dp.close > 0
        """, (sector, target_date.isoformat()))
        rows = cursor.fetchall()

        if len(rows) < 5:
            conn.close()
            return None

        # 获取板块名称（取第一只股票的板块名）
        cursor.execute("""
            SELECT name FROM stocks WHERE sector_lv1 = ? AND name IS NOT NULL LIMIT 1
        """, (sector,))
        name_row = cursor.fetchone()
        sector_name = name_row[0] if name_row else sector

        # 1. 计算板块5日/20日动量
        # 获取板块内股票的5日和20日前价格
        codes = [r[0] for r in rows]
        placeholders = ','.join(['?'] * len(codes))

        # 5日前
        cursor.execute(f"""
            SELECT AVG((b.close - a.close) / a.close * 100)
            FROM daily_prices a
            JOIN daily_prices b ON a.code = b.code
            WHERE a.code IN ({placeholders})
              AND a.trade_date = (SELECT MAX(trade_date) FROM daily_prices WHERE trade_date < ?)
              AND b.trade_date = ?
              AND a.close > 0
        """, codes + [target_date.isoformat(), target_date.isoformat()])
        mom_5d_row = cursor.fetchone()
        momentum_5d = mom_5d_row[0] if mom_5d_row and mom_5d_row[0] else 0

        # 20日前（简化：用最近的第20个交易日）
        cursor.execute(f"""
            SELECT DISTINCT trade_date FROM daily_prices
            WHERE trade_date <= ? ORDER BY trade_date DESC LIMIT 1 OFFSET 20
        """, (target_date.isoformat(),))
        date_20d_ago_row = cursor.fetchone()
        momentum_20d = 0
        if date_20d_ago_row:
            cursor.execute(f"""
                SELECT AVG((b.close - a.close) / a.close * 100)
                FROM daily_prices a
                JOIN daily_prices b ON a.code = b.code
                WHERE a.code IN ({placeholders})
                  AND a.trade_date = ?
                  AND b.trade_date = ?
                  AND a.close > 0
            """, codes + [date_20d_ago_row[0], target_date.isoformat()])
            mom_20d_row = cursor.fetchone()
            momentum_20d = mom_20d_row[0] if mom_20d_row and mom_20d_row[0] else 0

        # 2. 上涨比例
        up_count = sum(1 for r in rows if r[4] and r[4] > 0)
        advance_ratio = up_count / len(rows) * 100

        # 3. 量比（板块总成交额 vs 20日前）
        total_amount_today = sum(r[2] or 0 for r in rows)
        volume_ratio = 1.0
        if date_20d_ago_row:
            cursor.execute(f"""
                SELECT SUM(dp.amount) FROM daily_prices dp
                JOIN stocks s ON dp.code = s.code
                WHERE s.sector_lv1 = ? AND dp.trade_date = ?
            """, (sector, date_20d_ago_row[0]))
            amt_20d = cursor.fetchone()[0]
            if amt_20d and amt_20d > 0:
                volume_ratio = total_amount_today / amt_20d

        # 4. 领涨股强度（板块内涨幅前5的平均涨幅）
        changes = sorted([r[4] or 0 for r in rows], reverse=True)
        leader_strength = np.mean(changes[:5]) if changes else 0

        conn.close()

        # 综合评分（加权）
        composite = (
            momentum_5d * 0.30 +
            momentum_20d * 0.20 +
            advance_ratio * 0.15 +
            (volume_ratio - 1) * 100 * 0.15 +
            leader_strength * 0.20
        )

        return SectorScore(
            sector=sector,
            name=sector_name,
            momentum_5d=round(momentum_5d, 2),
            momentum_20d=round(momentum_20d, 2),
            volume_ratio=round(volume_ratio, 2),
            advance_ratio=round(advance_ratio, 2),
            leader_strength=round(leader_strength, 2),
            composite_score=round(composite, 2),
            stock_count=len(rows),
        )

    def get_sector_leaders(self, sector: str, target_date: date, top_n: int = 3) -> list[StockSignal]:
        """
        在指定板块内选出领涨股

        筛选条件：
        1. 5日涨幅排名前5
        2. 成交量放大（量比 > 1.2）
        3. 价格在20日均线上方
        4. 连续上涨或放量突破
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        # 获取板块内所有股票的近期行情
        cursor.execute("""
            SELECT dp.code, s.name, dp.close, dp.pct_change, dp.amount, dp.volume
            FROM daily_prices dp
            JOIN stocks s ON dp.code = s.code
            WHERE s.sector_lv1 = ? AND dp.trade_date = ?
              AND (s.is_delisted IS NULL OR s.is_delisted = 0)
              AND dp.close > 0
            ORDER BY dp.pct_change DESC
        """, (sector, target_date.isoformat()))
        rows = cursor.fetchall()

        if not rows:
            conn.close()
            return []

        signals = []
        for code, name, close, change_pct, amount, volume in rows[:10]:  # 取涨幅前10
            reasons = []
            confidence = 0.0

            # 获取近期数据
            cursor.execute("""
                SELECT trade_date, close, volume, amount
                FROM daily_prices
                WHERE code = ? AND trade_date <= ?
                ORDER BY trade_date DESC LIMIT 25
            """, (code, target_date.isoformat()))
            history = cursor.fetchall()

            if len(history) < 10:
                continue

            closes = [h[1] for h in history]
            volumes = [h[2] for h in history]
            dates = [h[0] for h in history]

            # 连续上涨天数
            consecutive_up = 0
            for i in range(len(closes) - 1):
                if closes[i] > closes[i + 1]:
                    consecutive_up += 1
                else:
                    break

            # 5日涨幅
            ret_5d = (closes[0] - closes[4]) / closes[4] * 100 if closes[4] > 0 else 0

            # 20日均线
            ma20 = np.mean(closes[:20]) if len(closes) >= 20 else np.mean(closes)
            above_ma20 = closes[0] > ma20

            # 量比（今日vs过去5日均量）
            avg_vol_5d = np.mean(volumes[1:6]) if len(volumes) >= 6 else np.mean(volumes[1:])
            vol_ratio = volumes[0] / avg_vol_5d if avg_vol_5d > 0 else 1.0

            # 放量突破判断
            volume_breakout = vol_ratio > 1.5 and closes[0] > closes[1]

            # 均线交叉
            if len(closes) >= 10:
                ma5 = np.mean(closes[:5])
                ma10 = np.mean(closes[:10])
                if ma5 > ma10 and closes[0] > ma5:
                    ma_cross = "golden_cross"  # 金叉
                elif ma5 < ma10 and closes[0] < ma5:
                    ma_cross = "death_cross"  # 死叉
                else:
                    ma_cross = "neutral"
            else:
                ma_cross = "neutral"

            # 趋势强度（20日线性回归斜率）
            if len(closes) >= 20:
                x = np.arange(len(closes[:20]))
                y = np.array(closes[:20])
                slope = np.polyfit(x, y, 1)[0]
                trend_strength = slope / closes[0] * 100  # 标准化
            else:
                trend_strength = 0

            # 综合评分
            score = 0
            if ret_5d > 3:
                score += 25
                reasons.append(f"5日涨{ret_5d:.1f}%")
            elif ret_5d > 1:
                score += 15
                reasons.append(f"5日涨{ret_5d:.1f}%")

            if above_ma20:
                score += 20
                reasons.append("站上20日线")

            if vol_ratio > 1.5:
                score += 20
                reasons.append(f"放量{vol_ratio:.1f}倍")
            elif vol_ratio > 1.2:
                score += 10
                reasons.append(f"温和放量{vol_ratio:.1f}倍")

            if consecutive_up >= 3:
                score += 15
                reasons.append(f"连涨{consecutive_up}天")
            elif consecutive_up >= 2:
                score += 10
                reasons.append(f"连涨{consecutive_up}天")

            if ma_cross == "golden_cross":
                score += 10
                reasons.append("均线金叉")

            if trend_strength > 0.5:
                score += 10
                reasons.append("趋势向上")

            # 判定信号
            signal = "hold"
            if score >= 50:
                signal = "buy"
            elif score <= -20:
                signal = "sell"

            confidence = min(score / 100, 1.0)

            signals.append(StockSignal(
                code=code,
                name=name,
                sector=sector,
                signal=signal,
                confidence=round(confidence, 2),
                reasons=reasons,
                consecutive_up_days=consecutive_up,
                volume_breakout=volume_breakout,
                ma_cross=ma_cross,
                trend_strength=round(trend_strength, 2),
            ))

        conn.close()

        # 按置信度排序
        signals.sort(key=lambda x: x.confidence, reverse=True)
        return signals[:top_n]

    def generate_weekly_signals(self, target_date: Optional[date] = None) -> dict:
        """
        生成周级别交易信号

        策略：
        1. 计算板块强度排名
        2. 选出 Top 3 强势板块
        3. 在每个强势板块内选出 Top 3 领涨股
        4. 同时选出 Bottom 3 弱势板块的卖出信号

        Returns:
            {
                'date': 'YYYY-MM-DD',
                'strong_sectors': [...],
                'weak_sectors': [...],
                'buy_signals': [...],
                'sell_signals': [...],
            }
        """
        if target_date is None:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(trade_date) FROM daily_prices")
            target_date = date.fromisoformat(cursor.fetchone()[0])
            conn.close()

        logger.info(f"生成信号: {target_date}")

        # 1. 板块强度排名
        sector_scores = self.get_sector_strength(target_date)
        logger.info(f"共 {len(sector_scores)} 个板块参与排名")

        # 2. 选出 Top 3 强势板块
        strong_sectors = sector_scores[:3]
        weak_sectors = sector_scores[-3:]

        # 3. 在强势板块内选领涨股
        buy_signals = []
        for ss in strong_sectors:
            leaders = self.get_sector_leaders(ss.sector, target_date, top_n=3)
            for sig in leaders:
                if sig.signal == "buy":
                    sig.reasons.insert(0, f"强势板块[{ss.sector}]评分{ss.composite_score}")
                    buy_signals.append(sig)

        # 4. 弱势板块内的卖出信号
        sell_signals = []
        for ws in weak_sectors:
            leaders = self.get_sector_leaders(ws.sector, target_date, top_n=3)
            for sig in leaders:
                if sig.signal == "sell":
                    sig.reasons.insert(0, f"弱势板块[{ws.sector}]评分{ws.composite_score}")
                    sell_signals.append(sig)

        # 按置信度排序
        buy_signals.sort(key=lambda x: x.confidence, reverse=True)
        sell_signals.sort(key=lambda x: x.confidence, reverse=True)

        return {
            'date': target_date.isoformat(),
            'strong_sectors': [
                {
                    'sector': ss.sector,
                    'name': ss.name,
                    'score': ss.composite_score,
                    'momentum_5d': ss.momentum_5d,
                    'momentum_20d': ss.momentum_20d,
                    'advance_ratio': ss.advance_ratio,
                    'volume_ratio': ss.volume_ratio,
                    'stock_count': ss.stock_count,
                }
                for ss in strong_sectors
            ],
            'weak_sectors': [
                {
                    'sector': ws.sector,
                    'name': ws.name,
                    'score': ws.composite_score,
                    'momentum_5d': ws.momentum_5d,
                }
                for ws in weak_sectors
            ],
            'buy_signals': [
                {
                    'code': s.code,
                    'name': s.name,
                    'sector': s.sector,
                    'confidence': s.confidence,
                    'reasons': s.reasons,
                    'consecutive_up': int(s.consecutive_up_days),
                    'volume_breakout': bool(s.volume_breakout),
                    'trend_strength': s.trend_strength,
                }
                for s in buy_signals
            ],
            'sell_signals': [
                {
                    'code': s.code,
                    'name': s.name,
                    'sector': s.sector,
                    'confidence': s.confidence,
                    'reasons': s.reasons,
                }
                for s in sell_signals
            ],
        }


def main():
    """测试板块轮动引擎"""
    engine = SectorRotationEngine()

    # 获取最新交易日
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute("SELECT MAX(trade_date) FROM daily_prices")
    latest_date = date.fromisoformat(cursor.fetchone()[0])
    conn.close()

    print(f"\n{'='*70}")
    print(f"板块轮动信号 - {latest_date}")
    print(f"{'='*70}")

    result = engine.generate_weekly_signals(latest_date)

    # 输出强势板块
    print(f"\n🔥 Top 3 强势板块:")
    for i, s in enumerate(result['strong_sectors'], 1):
        print(f"  {i}. {s['sector']} | 评分:{s['score']:.1f} | "
              f"5日动量:{s['momentum_5d']:+.2f}% | "
              f"上涨比:{s['advance_ratio']:.0f}% | "
              f"量比:{s['volume_ratio']:.2f} | "
              f"{s['stock_count']}只")

    # 输出买入信号
    print(f"\n📈 买入信号 ({len(result['buy_signals'])}个):")
    for s in result['buy_signals']:
        print(f"  {s['code']} {s['name']} | 置信度:{s['confidence']:.2f} | "
              f"连涨{s['consecutive_up']}天 | 趋势:{s['trend_strength']}")
        print(f"    原因: {', '.join(s['reasons'])}")

    # 输出弱势板块
    print(f"\n❄️ Bottom 3 弱势板块:")
    for i, s in enumerate(result['weak_sectors'], 1):
        print(f"  {i}. {s['sector']} | 评分:{s['score']:.1f} | 5日动量:{s['momentum_5d']:+.2f}%")

    # 输出卖出信号
    if result['sell_signals']:
        print(f"\n📉 卖出信号 ({len(result['sell_signals'])}个):")
        for s in result['sell_signals']:
            print(f"  {s['code']} {s['name']} | {', '.join(s['reasons'])}")

    # 保存结果
    import json
    output_dir = Path("var/sector_rotation")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"signals_{latest_date.isoformat()}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n结果已保存: {output_file}")


if __name__ == "__main__":
    main()
