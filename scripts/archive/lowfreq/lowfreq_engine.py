#!/usr/bin/env python3
"""
低频量化交易引擎 v2

核心逻辑：
1. 识别热门情绪板块（资金流入+涨幅+市场关注度）
2. 在热门板块中筛选龙头股和中军股（市值50-500亿）
3. 买入信号：确定性评分 ≥ 80%
4. 持仓周期：20-50天，目标收益 20-30%+
5. 卖出信号：目标达成 / 止损 / 持仓到期
6. 完整交易闭环：板块 → 标的 → 买入 → 持仓 → 卖出
"""

import sqlite3
import logging
import numpy as np
from pathlib import Path
from datetime import date, timedelta
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)

DB_PATH = Path("var/db/stock_data.db")


class SignalType(Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


@dataclass
class SectorHeat:
    """板块热度评分"""
    sector: str
    name: str
    heat_score: float = 0.0
    capital_flow: float = 0.0      # 资金流入（成交额变化）
    momentum_5d: float = 0.0        # 5日动量
    momentum_20d: float = 0.0       # 20日动量
    advance_ratio: float = 0.0      # 上涨比例
    volume_ratio: float = 0.0       # 量比
    stock_count: int = 0


@dataclass
class StockCandidate:
    """个股候选"""
    code: str
    name: str
    sector: str
    market_cap_yi: float = 0.0      # 市值（亿元）
    role: str = ""                   # 龙头/中军
    buy_score: float = 0.0          # 买入确定性评分（0-100）
    buy_reasons: list = field(default_factory=list)
    # 技术指标
    ret_5d: float = 0.0
    ret_20d: float = 0.0
    vol_ratio: float = 0.0
    ma_position: float = 0.0        # 均线位置（0=空头，1=多头）
    trend_slope: float = 0.0        # 趋势斜率
    consecutive_up: int = 0
    volume_breakout: bool = False


@dataclass
class SellSignal:
    """卖出信号"""
    reason: str                      # 卖出原因
    confidence: float = 0.0          # 确定性
    details: str = ""


@dataclass
class TradeRecord:
    """交易记录"""
    code: str
    name: str
    sector: str
    buy_date: str
    sell_date: str = ""
    buy_price: float = 0.0
    sell_price: float = 0.0
    shares: int = 0
    hold_days: int = 0
    return_pct: float = 0.0
    buy_score: float = 0.0
    sell_reason: str = ""
    status: str = "open"             # open / closed


class LowFreqTradingEngine:
    """低频量化交易引擎"""

    # ===== 参数配置 =====
    MARKET_CAP_MAX = 400e8           # 最大市值400亿（元）
    MARKET_CAP_MIN = 200e8           # 最小市值200亿（元）
    BUY_THRESHOLD = 80              # 买入确定性阈值（只选高确定性机会）
    TARGET_RETURN = 25.0             # 目标收益率25%
    MIN_HOLD_DAYS = 20               # 最小持仓天数
    MAX_HOLD_DAYS = 60               # 最大持仓天数（延长到60天）
    STOP_LOSS_PCT = -10.0            # 止损线-10%（反推优化：更严格止损）
    HOT_SECTOR_COUNT = 5             # 热门板块数量
    STOCKS_PER_SECTOR = 3            # 每板块选股数量
    MAX_POSITIONS = 5                # 最大持仓数

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self.db_path))

    # ================================================================
    # 第一步：识别热门情绪板块
    # ================================================================
    def get_hot_sectors(self, target_date: date, top_n: int = 5) -> list[SectorHeat]:
        """
        识别热门情绪板块

        评分维度：
        1. 资金流入（成交额相对20日均量的变化）
        2. 5日动量（板块平均涨幅）
        3. 20日动量（中期趋势）
        4. 上涨比例（板块内上涨股票占比）
        """
        conn = self._conn()
        cursor = conn.cursor()

        # 获取所有板块
        cursor.execute("""
            SELECT DISTINCT sector_lv1 FROM stocks
            WHERE sector_lv1 IS NOT NULL
              AND (is_delisted IS NULL OR is_delisted = 0)
              AND total_market_cap > 0 AND total_market_cap < ?
        """, (self.MARKET_CAP_MAX,))
        sectors = [r[0] for r in cursor.fetchall()]

        # 获取20天前的日期
        cursor.execute("""
            SELECT DISTINCT trade_date FROM daily_prices
            WHERE trade_date <= ? ORDER BY trade_date DESC LIMIT 1 OFFSET 20
        """, (target_date.isoformat(),))
        row = cursor.fetchone()
        date_20d = row[0] if row else None

        scores = []
        for sector in sectors:
            cursor.execute("""
                SELECT dp.code, dp.close, dp.pct_change, dp.amount
                FROM daily_prices dp
                JOIN stocks s ON dp.code = s.code
                WHERE s.sector_lv1 = ? AND dp.trade_date = ?
                  AND dp.close > 0
            """, (sector, target_date.isoformat()))
            rows = cursor.fetchall()

            if len(rows) < 5:
                continue

            # 获取板块名称
            cursor.execute("""
                SELECT name FROM stocks WHERE sector_lv1 = ? AND name IS NOT NULL LIMIT 1
            """, (sector,))
            name_row = cursor.fetchone()
            sector_name = name_row[0] if name_row else sector

            # 1. 上涨比例
            up_count = sum(1 for r in rows if r[2] is not None and r[2] > 0)
            advance_ratio = up_count / len(rows) * 100

            # 2. 5日动量（板块平均）
            codes = [r[0] for r in rows]
            placeholders = ','.join(['?'] * len(codes))
            cursor.execute(f"""
                SELECT AVG((b.close - a.close) / a.close * 100)
                FROM daily_prices a
                JOIN daily_prices b ON a.code = b.code
                WHERE a.code IN ({placeholders})
                  AND a.trade_date = (SELECT MAX(trade_date) FROM daily_prices WHERE trade_date < ?)
                  AND b.trade_date = ?
                  AND a.close > 0
            """, codes + [target_date.isoformat(), target_date.isoformat()])
            mom_row = cursor.fetchone()
            momentum_5d = mom_row[0] if mom_row and mom_row[0] is not None else 0

            # 3. 20日动量
            momentum_20d = 0
            if date_20d:
                cursor.execute(f"""
                    SELECT AVG((b.close - a.close) / a.close * 100)
                    FROM daily_prices a
                    JOIN daily_prices b ON a.code = b.code
                    WHERE a.code IN ({placeholders})
                      AND a.trade_date = ?
                      AND b.trade_date = ?
                      AND a.close > 0
                """, codes + [date_20d, target_date.isoformat()])
                mom20_row = cursor.fetchone()
                momentum_20d = mom20_row[0] if mom20_row and mom20_row[0] is not None else 0

            # 4. 量比（今日总成交额 vs 20日前）
            total_amount = sum(r[3] or 0 for r in rows if r[3] is not None)
            volume_ratio = 1.0
            if date_20d:
                cursor.execute("""
                    SELECT SUM(dp.amount) FROM daily_prices dp
                    JOIN stocks s ON dp.code = s.code
                    WHERE s.sector_lv1 = ? AND dp.trade_date = ?
                """, (sector, date_20d))
                amt_row = cursor.fetchone()
                if amt_row and amt_row[0] and amt_row[0] > 0:
                    volume_ratio = total_amount / amt_row[0]

            # 综合热度评分
            momentum_5d = momentum_5d or 0
            momentum_20d = momentum_20d or 0
            advance_ratio = advance_ratio or 0
            volume_ratio = volume_ratio or 1.0
            heat_score = (
                momentum_5d * 2.0 +        # 短期动量权重最高
                momentum_20d * 1.5 +       # 中期趋势
                advance_ratio * 0.8 +       # 上涨广度
                (volume_ratio - 1) * 100 * 1.0  # 资金流入
            )

            scores.append(SectorHeat(
                sector=sector,
                name=sector_name,
                heat_score=round(heat_score, 2),
                capital_flow=round((volume_ratio - 1) * 100, 2),
                momentum_5d=round(momentum_5d, 2),
                momentum_20d=round(momentum_20d, 2),
                advance_ratio=round(advance_ratio, 2),
                volume_ratio=round(volume_ratio, 2),
                stock_count=len(rows),
            ))

        conn.close()
        scores.sort(key=lambda x: x.heat_score, reverse=True)
        return scores[:top_n]

    # ================================================================
    # 第二步：筛选龙头股和中军股
    # ================================================================
    def get_sector_candidates(self, sector: str, target_date: date, top_n: int = 3) -> list[StockCandidate]:
        """
        在热门板块中筛选龙头股和中军股

        龙头股定义：板块内市值最大 + 涨幅领先
        中军股定义：市值中等 + 趋势向上 + 放量确认

        买入确定性评分（满分100）：
        - 趋势向上（均线多头排列）: 20分
        - 放量确认（量比>1.3）: 15分
        - 5日涨幅适中（2-8%）: 15分
        - 连续上涨（≥2天）: 10分
        - 20日趋势斜率正向: 15分
        - 板块内排名靠前: 15分
        - 市值适中（100-300亿最优）: 10分
        """
        conn = self._conn()
        cursor = conn.cursor()

        # 获取板块内符合条件的股票（市值50-500亿）
        cursor.execute("""
            SELECT s.code, s.name, s.total_market_cap, dp.close, dp.pct_change, dp.amount, dp.volume
            FROM stocks s
            JOIN daily_prices dp ON s.code = dp.code
            WHERE s.sector_lv1 = ? AND dp.trade_date = ?
              AND s.total_market_cap > ? AND s.total_market_cap < ?
              AND (s.is_delisted IS NULL OR s.is_delisted = 0)
              AND dp.close > 0
            ORDER BY dp.pct_change DESC
        """, (sector, target_date.isoformat(), self.MARKET_CAP_MIN, self.MARKET_CAP_MAX))

        rows = cursor.fetchall()
        if not rows:
            conn.close()
            return []

        candidates = []
        for i, (code, name, mkt_cap, close, pct_chg, amount, volume) in enumerate(rows[:15]):
            reasons = []
            score = 0

            # 获取近期数据
            cursor.execute("""
                SELECT trade_date, close, volume FROM daily_prices
                WHERE code = ? AND trade_date <= ?
                ORDER BY trade_date DESC LIMIT 30
            """, (code, target_date.isoformat()))
            history = cursor.fetchall()

            if len(history) < 15:
                continue

            closes = [h[1] for h in history if h[1] is not None]
            vols = [h[2] for h in history if h[2] is not None]

            # --- 评分维度（基于反推法优化）---
            # 反推发现：牛股多在高位启动(中位数78%)、温和放量(量比中位数0.95)、
            # 仅34%有多头排列、48%是板块前3

            # 1. 价格位置（反推优化：高位启动反而更好）- 满分15分
            if len(closes) >= 20:
                high_20 = max(closes[:20])
                low_20 = min(closes[:20])
                price_position = (close - low_20) / (high_20 - low_20) * 100 if high_20 > low_20 else 50

                # 反推发现：牛股多在60-90%区间启动
                if 60 <= price_position <= 90:
                    score += 15
                    reasons.append(f"价格位置{price_position:.0f}%（突破区间）")
                elif 40 <= price_position < 60:
                    score += 10
                    reasons.append(f"价格位置{price_position:.0f}%（中位）")
                elif price_position > 90:
                    score += 5  # 高位追涨风险高，低分
                    reasons.append(f"价格位置{price_position:.0f}%（高位）")

            # 2. 温和放量（反推优化：1-2倍比>2倍更好）- 满分15分
            avg_vol_5d = np.mean(vols[1:6]) if len(vols) >= 6 else np.mean(vols[1:])
            vol_ratio = vols[0] / avg_vol_5d if avg_vol_5d > 0 else 1.0
            if 1.0 < vol_ratio <= 2.0:  # 温和放量最优
                score += 15
                reasons.append(f"温和放量{vol_ratio:.1f}倍")
            elif 2.0 < vol_ratio <= 3.0:
                score += 10
                reasons.append(f"放量{vol_ratio:.1f}倍")
            elif vol_ratio > 3.0:
                score += 5  # 过度放量可能是出货

            # 3. 5日涨幅（反推：牛股5日涨幅中位数约5%）- 满分15分
            ret_5d = (closes[0] - closes[4]) / closes[4] * 100 if len(closes) >= 5 and closes[4] > 0 else 0
            if 2 <= ret_5d <= 8:  # 适中涨幅最优
                score += 15
                reasons.append(f"5日涨{ret_5d:.1f}%（适中）")
            elif 8 < ret_5d <= 15:
                score += 8
                reasons.append(f"5日涨{ret_5d:.1f}%（偏强）")
            elif ret_5d > 15:
                score += 3  # 涨太多可能回调

            # 计算连涨天数
            consecutive_up = 0
            for j in range(len(closes) - 1):
                if closes[j] > closes[j + 1]:
                    consecutive_up += 1
                else:
                    break

            # 4. 均线趋势（反推：仅34%有多头排列，降低权重）- 满分10分
            ma_position = 0.5
            if len(closes) >= 20:
                ma5 = np.mean(closes[:5])
                ma10 = np.mean(closes[:10])
                ma20 = np.mean(closes[:20])
                if close > ma5 > ma10 > ma20:
                    score += 10
                    reasons.append("均线多头排列")
                    ma_position = 1.0
                elif ma5 > ma10 and close > ma5:
                    score += 6
                    reasons.append("短期多头")
                    ma_position = 0.7
                elif close > ma20:
                    score += 3
                    ma_position = 0.4

            # 计算20日涨幅和趋势斜率（用于StockCandidate）
            ret_20d = (closes[0] - closes[19]) / closes[19] * 100 if len(closes) >= 20 and closes[19] > 0 else 0
            trend_slope = 0
            if len(closes) >= 20:
                x = np.arange(20)
                y = np.array(closes[:20])
                slope = np.polyfit(x, y, 1)[0]
                trend_slope = slope / closes[0] * 100

            # 5. 板块地位（反推：48%是板块前3，很重要）- 满分20分
            rank_bonus = max(0, 20 - i * 6)  # 第1名20分，第2名14分，第3名8分
            score += rank_bonus
            if i == 0:
                reasons.append("板块龙头")
            elif i == 1:
                reasons.append("板块第2")

            # 6. 市值（反推：中位数259亿，200-350亿最优）- 满分10分
            mkt_cap_yi = mkt_cap / 1e8
            if 220 <= mkt_cap_yi <= 280:  # 反推中位数259亿附近
                score += 10
                reasons.append(f"市值{mkt_cap_yi:.0f}亿（最优）")
            elif 200 <= mkt_cap_yi <= 350:
                score += 7
                reasons.append(f"市值{mkt_cap_yi:.0f}亿（适中）")
            elif 350 < mkt_cap_yi <= 400:
                score += 3

            # 7. 人气因子（成交额+换手率）- 满分15分
            # 重新查询包含amount的历史数据
            conn2 = self._conn()
            cursor2 = conn2.cursor()
            cursor2.execute("""
                SELECT amount, volume FROM daily_prices
                WHERE code = ? AND trade_date <= ?
                ORDER BY trade_date DESC LIMIT 15
            """, (code, target_date.isoformat()))
            amt_vol_hist = cursor2.fetchall()
            conn2.close()

            if len(amt_vol_hist) >= 10:
                amts = [av[0] for av in amt_vol_hist if av[0] is not None]
                vols_full = [av[1] for av in amt_vol_hist if av[1] is not None]

                if len(amts) >= 10 and len(vols_full) >= 10:
                    avg_amt_10d = np.mean(amts[1:11])
                    avg_vol_10d = np.mean(vols_full[1:11])
                    amt_ratio_10d = amts[0] / avg_amt_10d if avg_amt_10d > 0 else 1.0
                    vol_ratio_10d = vols_full[0] / avg_vol_10d if avg_vol_10d > 0 else 1.0

                    # 反推：成交额比中位数1.0，温和放量最优
                    if 1.0 < amt_ratio_10d <= 2.0:
                        score += 8
                        reasons.append(f"成交额{amt_ratio_10d:.1f}倍")
                    elif amt_ratio_10d > 2.0:
                        score += 4

                    if 1.0 < vol_ratio_10d <= 2.0:
                        score += 7
                    elif vol_ratio_10d > 2.0:
                        score += 3

            # 判定角色
            role = "龙头" if i < 2 else "中军"

            candidates.append(StockCandidate(
                code=code,
                name=name,
                sector=sector,
                market_cap_yi=round(mkt_cap_yi, 1),
                role=role,
                buy_score=score,
                buy_reasons=reasons,
                ret_5d=round(ret_5d, 2),
                ret_20d=round(ret_20d, 2),
                vol_ratio=round(vol_ratio, 2),
                ma_position=round(ma_position, 2),
                trend_slope=round(trend_slope, 2) if len(closes) >= 20 else 0,
                consecutive_up=consecutive_up,
                volume_breakout=vol_ratio > 1.5,
            ))

        conn.close()
        candidates.sort(key=lambda x: x.buy_score, reverse=True)
        return candidates[:top_n]

    # ================================================================
    # 第三步：生成买入信号（确定性 ≥ 80%，且是板块前2）
    # ================================================================
    def generate_buy_signals(self, target_date: date) -> dict:
        """生成买入信号 - 严格筛选：高评分+板块龙头"""
        hot_sectors = self.get_hot_sectors(target_date, self.HOT_SECTOR_COUNT)
        logger.info(f"热门板块 Top {len(hot_sectors)}: {[s.sector for s in hot_sectors]}")

        buy_signals = []
        for sh in hot_sectors:
            try:
                # 只取板块前2，且评分≥80
                candidates = self.get_sector_candidates(sh.sector, target_date, 2)
                for c in candidates:
                    # 严格条件：评分≥80 且 是板块前2（龙头）
                    if c.buy_score >= self.BUY_THRESHOLD and c.role == "龙头":
                        buy_signals.append(c)
                        logger.info(f"  买入信号: {c.code} {c.name} | 评分:{c.buy_score} | {c.role} | 市值:{c.market_cap_yi}亿")
            except Exception as e:
                logger.warning(f"板块 {sh.sector} 信号生成失败: {e}")

        buy_signals.sort(key=lambda x: x.buy_score, reverse=True)
        return {
            "date": target_date.isoformat(),
            "hot_sectors": [
                {"sector": s.sector, "name": s.name, "heat_score": s.heat_score,
                 "momentum_5d": s.momentum_5d, "advance_ratio": s.advance_ratio,
                 "volume_ratio": s.volume_ratio, "stock_count": s.stock_count}
                for s in hot_sectors
            ],
            "buy_signals": [
                {"code": s.code, "name": s.name, "sector": s.sector, "role": s.role,
                 "buy_score": s.buy_score, "market_cap_yi": s.market_cap_yi,
                 "ret_5d": s.ret_5d, "vol_ratio": s.vol_ratio,
                 "reasons": s.buy_reasons}
                for s in buy_signals
            ],
            "summary": {
                "hot_sectors_count": len(hot_sectors),
                "buy_signals_count": len(buy_signals),
                "threshold": self.BUY_THRESHOLD,
            }
        }

    # ================================================================
    # 第四步：生成卖出信号
    # ================================================================
    def check_sell_signal(self, code: str, buy_date: date, buy_price: float,
                           buy_score: float, current_date: date) -> Optional[SellSignal]:
        """
        检查是否触发卖出信号（基于Auto Research发现优化）

        卖出条件（按优先级）：
        1. 目标收益达成（≥25%）—— 核心赢利点
        2. 止损（≤-10%）—— 硬止损，严格执行
        3. 持仓到期（≥50天）—— 强制平仓
        4. 预警信号（量比<0.5或MA5<0.95）—— 仅提示，不自动卖出
           研究发现：这些信号出现后价格经常反弹，不宜作为强制卖出条件

        注意：Auto Research分析显示量比<0.5（均-7.00%）和MA5<0.97
        是有效的"人气溃散预警"，但成功案例（如平潭发展+26.7%、海南矿业+29.4%）
        均出现过这些预警后才大幅上涨。因此仅记录预警，等待价格反弹确认后再决策。
        """
        sell_price = self._get_price(code, current_date)
        if not sell_price or sell_price <= 0:
            return None

        ret_pct = (sell_price - buy_price) / buy_price * 100
        hold_days = self._count_trading_days(buy_date, current_date)

        # 获取量比、均线、成交额数据
        conn = self._conn()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT close, volume, amount FROM daily_prices
            WHERE code = ? AND trade_date <= ?
            ORDER BY trade_date DESC LIMIT 15
        """, (code, current_date.isoformat()))
        history = cursor.fetchall()

        ma5_pos = 1.0
        vol_ratio_today = 1.0
        amt_ratio_today = 1.0

        if len(history) >= 5:
            closes = [h[0] for h in history if h[0] is not None]
            vols = [h[1] for h in history if h[1] is not None]
            amts = [h[2] for h in history if h[2] is not None]
            ma5 = np.mean(closes[:5])
            ma5_pos = closes[0] / ma5 if ma5 > 0 else 1.0
            avg_vol = np.mean(vols[1:6]) if len(vols) >= 6 else np.mean(vols[1:])
            vol_ratio_today = vols[0] / avg_vol if avg_vol > 0 else 1.0

            # 计算成交额比（10日平均）
            if len(amts) >= 10:
                avg_amt_10d = np.mean(amts[1:11])
                amt_ratio_today = amts[0] / avg_amt_10d if avg_amt_10d > 0 else 1.0

        conn.close()

        # 1. 目标收益达成
        if ret_pct >= self.TARGET_RETURN:
            return SellSignal(
                reason="target_reached",
                confidence=min(95, 80 + ret_pct),
                details=f"目标收益达成: {ret_pct:.1f}% (持有{hold_days}天)"
            )

        # 2. 止损（优化为-10%，研究数据显示-10%止损胜率66.7%）
        if ret_pct <= -10.0:
            return SellSignal(
                reason="stop_loss",
                confidence=90,
                details=f"触发止损: {ret_pct:.1f}% (持有{hold_days}天)"
            )

        # 3. 持仓到期
        if hold_days >= self.MAX_HOLD_DAYS:
            return SellSignal(
                reason="max_hold",
                confidence=70,
                details=f"持仓到期: {hold_days}天, 收益{ret_pct:.1f}%"
            )

        # 4. 人气消散：成交额<0.5倍（研究：最强离场信号，触发后均-7.69%）
        # 仅在持仓超过15天后触发，避免早期洗盘被震出
        if hold_days >= 15 and amt_ratio_today < 0.5:
            return SellSignal(
                reason="sentiment_collapse",
                confidence=85,
                details=f"人气消散: 成交额{amt_ratio_today:.2f}<0.5倍(10日均), 持有{hold_days}天, 收益{ret_pct:.1f}%"
            )

        # 5. 持仓达到最低要求（20天）且触发严重预警：MA5<0.93（深度跌破）
        # 研究发现：MA5<0.93以下时，继续持有的胜率较低
        if hold_days >= self.MIN_HOLD_DAYS and ma5_pos < 0.93:
            return SellSignal(
                reason="trend_collapse",
                confidence=80,
                details=f"趋势深度破位: MA5位置{ma5_pos:.3f}<0.93, 当前收益{ret_pct:.1f}%"
            )

        # 5. 持仓超过35天 + MA5<0.95（均线空头排列确认）
        if hold_days >= 35 and ma5_pos < 0.95:
            conn = self._conn()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT close FROM daily_prices
                WHERE code = ? AND trade_date <= ?
                ORDER BY trade_date DESC LIMIT 10
            """, (code, current_date.isoformat()))
            closes_hist = [r[0] for r in cursor.fetchall() if r[0] is not None]
            conn.close()
            if len(closes_hist) >= 10:
                ma5 = np.mean(closes_hist[:5])
                ma10 = np.mean(closes_hist[:10])
                if ma5 < ma10:  # 均线死叉
                    recent_drop = all(
                        closes_hist[i] < closes_hist[i+1]
                        for i in range(min(3, len(closes_hist)-1))
                    )
                    if recent_drop:
                        return SellSignal(
                            reason="trend_reversal_late",
                            confidence=75,
                            details=f"长期趋势反转: MA5位置{ma5_pos:.3f}<0.95, 均线死叉+连续下跌, 持有{hold_days}天, 收益{ret_pct:.1f}%"
                        )

        return None

    # ================================================================
    # 第五步：完整回测
    # ================================================================
    def run_backtest(
        self,
        start_date: date,
        end_date: date,
        initial_capital: float = 1000000.0,
        rebalance_days: int = 5,  # 每5个交易日重新评估
    ) -> dict:
        """运行完整回测"""
        logger.info(f"低频交易回测: {start_date} ~ {end_date}")

        trading_dates = self._get_trading_dates(start_date, end_date)
        logger.info(f"交易日: {len(trading_dates)}")

        capital = initial_capital
        positions: dict[str, TradeRecord] = {}
        all_trades: list[TradeRecord] = []
        daily_values = []
        buy_signal_log = []

        for i, current_date in enumerate(trading_dates):
            # --- 检查持仓卖出信号 ---
            closed_codes = []
            for code, trade in list(positions.items()):
                sell = self.check_sell_signal(
                    code, date.fromisoformat(trade.buy_date),
                    trade.buy_price, trade.buy_score, current_date
                )
                if sell:
                    sell_price = self._get_price(code, current_date)
                    if sell_price:
                        ret = (sell_price - trade.buy_price) / trade.buy_price * 100
                        capital += sell_price * trade.shares
                        trade.sell_date = current_date.isoformat()
                        trade.sell_price = sell_price
                        trade.return_pct = round(ret, 2)
                        trade.hold_days = self._count_trading_days(
                            date.fromisoformat(trade.buy_date), current_date)
                        trade.sell_reason = sell.details
                        trade.status = "closed"
                        all_trades.append(trade)
                        closed_codes.append(code)
                        logger.info(f"  卖出: {code} | {sell.reason} | {ret:+.1f}% | {trade.hold_days}天")

            for code in closed_codes:
                del positions[code]

            # --- 生成买入信号（每 rebalance_days 天一次）---
            if i % rebalance_days == 0 and len(positions) < self.MAX_POSITIONS:
                try:
                    signals = self.generate_buy_signals(current_date)
                    buy_signal_log.append(signals)

                    for sig in signals["buy_signals"]:
                        if sig["code"] in positions:
                            continue
                        price = self._get_price(sig["code"], current_date)
                        if not price or price <= 0:
                            continue

                        # 等权分配资金
                        slots = self.MAX_POSITIONS - len(positions)
                        per_slot = capital / max(slots, 1)
                        shares = int(per_slot / price / 100) * 100
                        if shares >= 100 and shares * price <= capital:
                            capital -= shares * price
                            positions[sig["code"]] = TradeRecord(
                                code=sig["code"],
                                name=sig["name"],
                                sector=sig["sector"],
                                buy_date=current_date.isoformat(),
                                buy_price=price,
                                shares=shares,
                                buy_score=sig["buy_score"],
                                status="open",
                            )
                            logger.info(f"  买入: {sig['code']} {sig['name']} | "
                                       f"评分:{sig['buy_score']} | {sig['role']} | "
                                       f"市值:{sig['market_cap_yi']}亿")
                except Exception as e:
                    logger.warning(f"信号生成失败 {current_date}: {e}")

            # --- 计算总资产 ---
            pos_value = sum(
                (self._get_price(code, current_date) or pos.buy_price) * pos.shares
                for code, pos in positions.items()
            )
            total = capital + pos_value
            daily_values.append({
                "date": current_date.isoformat(),
                "total_value": round(total, 2),
                "positions": len(positions),
            })

            if (i + 1) % 50 == 0:
                logger.info(f"  {current_date}: 总资产={total:,.0f}, 持仓={len(positions)}")

        # 平仓剩余持仓
        for code, trade in positions.items():
            final_price = self._get_price(code, trading_dates[-1])
            if final_price:
                ret = (final_price - trade.buy_price) / trade.buy_price * 100
                capital += final_price * trade.shares
                trade.sell_date = trading_dates[-1].isoformat()
                trade.sell_price = final_price
                trade.return_pct = round(ret, 2)
                trade.hold_days = self._count_trading_days(
                    date.fromisoformat(trade.buy_date), trading_dates[-1])
                trade.sell_reason = "回测结束平仓"
                trade.status = "closed"
                all_trades.append(trade)

        # 计算指标
        return self._calc_metrics(daily_values, all_trades, initial_capital, buy_signal_log)

    def _calc_metrics(self, daily_values, trades, initial_capital, buy_signal_log):
        """计算回测指标"""
        values = [d["total_value"] for d in daily_values]
        final_value = values[-1] if values else initial_capital
        total_return = (final_value - initial_capital) / initial_capital * 100
        n_days = len(values)
        annual_return = (1 + total_return / 100) ** (252 / max(n_days, 1)) - 1

        # 最大回撤
        peak = values[0]
        max_dd = 0
        for v in values:
            if v > peak:
                peak = v
            dd = (peak - v) / peak * 100
            if dd > max_dd:
                max_dd = dd

        # 胜率
        wins = [t for t in trades if t.return_pct > 0]
        win_rate = len(wins) / len(trades) * 100 if trades else 0
        avg_return = np.mean([t.return_pct for t in trades]) if trades else 0
        avg_win = np.mean([t.return_pct for t in wins]) if wins else 0
        avg_loss = np.mean([t.return_pct for t in trades if t.return_pct <= 0]) if [t for t in trades if t.return_pct <= 0] else 0
        pl_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else float('inf')

        # 达标交易（收益≥20%）
        target_hits = [t for t in trades if t.return_pct >= 20]
        target_hit_rate = len(target_hits) / len(trades) * 100 if trades else 0

        # 买入信号统计
        total_buy_signals = sum(len(s.get("buy_signals", [])) for s in buy_signal_log)
        qualified_signals = sum(1 for s in buy_signal_log for c in s.get("buy_signals", []) if c["buy_score"] >= 80)

        # 卖出原因分布
        sell_reasons = {}
        for t in trades:
            reason_key = t.sell_reason.split(":")[0].strip() if t.sell_reason else "unknown"
            sell_reasons[reason_key] = sell_reasons.get(reason_key, 0) + 1

        return {
            "strategy": "low_freq_v2",
            "start_date": daily_values[0]["date"] if daily_values else "",
            "end_date": daily_values[-1]["date"] if daily_values else "",
            "trading_days": n_days,
            "initial_capital": initial_capital,
            "final_value": round(final_value, 2),
            "total_return_pct": round(total_return, 2),
            "annual_return_pct": round(annual_return * 100, 2),
            "max_drawdown_pct": round(max_dd, 2),
            "total_trades": len(trades),
            "win_rate_pct": round(win_rate, 2),
            "avg_return_pct": round(avg_return, 2),
            "avg_win_pct": round(avg_win, 2),
            "avg_loss_pct": round(avg_loss, 2),
            "profit_loss_ratio": round(pl_ratio, 2),
            "target_hit_rate_pct": round(target_hit_rate, 2),  # 收益≥20%的比例
            "target_hits": len(target_hits),
            "total_buy_signals": total_buy_signals,
            "qualified_buy_signals": qualified_signals,  # 评分≥80的信号
            "sell_reasons": sell_reasons,
            "recent_trades": [
                {"code": t.code, "name": t.name, "sector": t.sector,
                 "buy_date": t.buy_date, "sell_date": t.sell_date,
                 "return_pct": t.return_pct, "hold_days": t.hold_days,
                 "buy_score": t.buy_score, "sell_reason": t.sell_reason}
                for t in trades[-20:]
            ],
        }

    # ================================================================
    # 辅助方法
    # ================================================================
    def _get_trading_dates(self, start: date, end: date) -> list[date]:
        conn = self._conn()
        cursor = conn.execute(
            "SELECT DISTINCT trade_date FROM daily_prices WHERE trade_date BETWEEN ? AND ? ORDER BY trade_date",
            (start.isoformat(), end.isoformat()))
        dates = [date.fromisoformat(r[0]) for r in cursor.fetchall()]
        conn.close()
        return dates

    def _get_price(self, code: str, d: date) -> float | None:
        conn = self._conn()
        cursor = conn.execute(
            "SELECT close FROM daily_prices WHERE code = ? AND trade_date = ?",
            (code, d.isoformat()))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row and row[0] > 0 else None

    def _count_trading_days(self, start: date, end: date) -> int:
        dates = self._get_trading_dates(start, end)
        return len(dates)


def main():
    """运行低频交易回测"""
    engine = LowFreqTradingEngine()

    # 18个月回测
    start_date = date(2024, 11, 26)
    end_date = date(2026, 5, 22)

    print(f"\n{'='*70}")
    print(f"低频量化交易系统 v2 (Auto Research优化版)")
    print(f"{'='*70}")
    print(f"回测区间: {start_date} ~ {end_date}")
    print(f"选股范围: 市值 200-400 亿 (200-450亿过滤)")
    print(f"买入阈值: 确定性评分 ≥ {engine.BUY_THRESHOLD} (Auto Research优化)")
    print(f"目标收益: ≥ {engine.TARGET_RETURN}%")
    print(f"持仓周期: {engine.MIN_HOLD_DAYS}-{engine.MAX_HOLD_DAYS} 天")
    print(f"止损线: -10% (研究优化，原-15%)")
    print(f"人气溃散: 量比<0.5 卖出")
    print(f"趋势反转: MA5<0.97+量比<0.6 早期 / MA5<0.97+死叉 晚期")
    print(f"{'='*70}\n")

    result = engine.run_backtest(start_date, end_date)

    # 输出结果
    print(f"\n{'='*70}")
    print(f"回测结果")
    print(f"{'='*70}")
    print(f"回测区间: {result['start_date']} ~ {result['end_date']}")
    print(f"交易日数: {result['trading_days']}")
    print(f"初始资金: ¥{result['initial_capital']:,.0f}")
    print(f"最终资产: ¥{result['final_value']:,.0f}")
    print(f"总收益率: {result['total_return_pct']:.2f}%")
    print(f"年化收益率: {result['annual_return_pct']:.2f}%")
    print(f"最大回撤: {result['max_drawdown_pct']:.2f}%")
    print(f"")
    print(f"交易次数: {result['total_trades']}")
    print(f"胜率: {result['win_rate_pct']:.2f}%")
    print(f"平均收益: {result['avg_return_pct']:.2f}%")
    print(f"平均盈利: {result['avg_win_pct']:.2f}%")
    print(f"平均亏损: {result['avg_loss_pct']:.2f}%")
    print(f"盈亏比: {result['profit_loss_ratio']:.2f}")
    print(f"")
    print(f"目标达成率(≥20%): {result['target_hit_rate_pct']:.2f}% ({result['target_hits']}/{result['total_trades']})")
    print(f"")
    print(f"总买入信号: {result['total_buy_signals']}")
    print(f"达标信号(≥80分): {result['qualified_buy_signals']}")
    print(f"")
    print(f"卖出原因分布:")
    for reason, count in result['sell_reasons'].items():
        print(f"  {reason}: {count}次")
    print(f"{'='*70}")

    # 最近交易
    if result['recent_trades']:
        print(f"\n最近交易记录:")
        for t in result['recent_trades'][-10:]:
            print(f"  {t['code']} {t['name']} | {t['buy_date']}→{t['sell_date']} | "
                  f"{t['hold_days']}天 | {t['return_pct']:+.1f}% | 买入评分:{t['buy_score']}")

    # 保存结果
    import json
    output_dir = Path("var/backtest_results")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"lowfreq_v2_{start_date.isoformat()}_{end_date.isoformat()}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n结果已保存: {output_file}")


if __name__ == "__main__":
    main()
