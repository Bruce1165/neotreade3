#!/usr/bin/env python3
"""
低频量化交易引擎 v3

核心目标：预判未来20-60个交易日有80%+机会涨幅达到30-50%的股票

反推法优化要点：
1. 高位启动反而更好（60-90%区间）
2. 温和放量（1-2倍）优于高放量
3. 均线多头排列非必要条件（仅34%符合）
4. 板块地位重要（48%是板块前3）
5. 市值200-350亿最优

新增：波浪阶段判断（3浪/5浪/B浪识别）
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


class WavePhase(Enum):
    """波浪阶段"""
    WAVE_1 = "1浪"      # 启动浪
    WAVE_2 = "2浪"      # 回调浪
    WAVE_3 = "3浪"      # 主升浪（最优）
    WAVE_4 = "4浪"      # 调整浪
    WAVE_5 = "5浪"      # 末升浪（次优）
    WAVE_A = "A浪"      # 下跌A浪
    WAVE_B = "B浪"      # 反弹B浪（可做）
    WAVE_C = "C浪"      # 下跌C浪
    UNKNOWN = "未知"


@dataclass
class SectorHeat:
    """板块热度评分"""
    sector: str
    name: str
    heat_score: float = 0.0
    capital_flow: float = 0.0
    momentum_5d: float = 0.0
    momentum_20d: float = 0.0
    advance_ratio: float = 0.0
    volume_ratio: float = 0.0
    stock_count: int = 0


@dataclass
class StockCandidate:
    """个股候选"""
    code: str
    name: str
    sector: str
    market_cap_yi: float = 0.0
    role: str = ""
    buy_score: float = 0.0
    buy_reasons: list = field(default_factory=list)
    wave_phase: str = ""
    # 技术指标
    ret_5d: float = 0.0
    ret_20d: float = 0.0
    vol_ratio: float = 0.0
    ma_position: float = 0.5
    trend_slope: float = 0.0
    consecutive_up: int = 0
    volume_breakout: bool = False
    price_position: float = 0.0  # 价格位置（0-100）


@dataclass
class SellSignal:
    """卖出信号"""
    reason: str
    confidence: float = 0.0
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
    wave_phase: str = ""
    sell_reason: str = ""
    status: str = "open"


class LowFreqTradingEngineV3:
    """低频量化交易引擎 v3 - 反推法优化版"""

    # ===== 参数配置（基于反推法优化） =====
    MARKET_CAP_MAX = 500e8           # 最大市值500亿
    MARKET_CAP_MIN = 200e8           # 最小市值200亿
    BUY_THRESHOLD = 80               # 买入确定性阈值
    TARGET_RETURN = 30.0             # 目标收益率30%（提高）
    MIN_HOLD_DAYS = 20               # 最小持仓天数
    MAX_HOLD_DAYS = 60               # 最大持仓天数
    STOP_LOSS_PCT = -10.0            # 止损线-10%
    HOT_SECTOR_COUNT = 5             # 热门板块数量
    MAX_POSITIONS = 3                # 最大持仓数（降低，更精选）

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self.db_path))

    # ================================================================
    # 波浪阶段判断（新增）
    # ================================================================
    def detect_wave_phase(self, code: str, target_date: date) -> tuple[str, float]:
        """
        判断当前处于哪个波浪阶段

        返回: (波浪阶段, 置信度0-1)

        判断逻辑：
        - 3浪：突破前期高点 + 放量 + 均线多头排列初期
        - 5浪：涨幅已大 + 量价背离 + 接近前高
        - B浪：深度回调后 + 缩量反弹
        """
        conn = self._conn()
        cursor = conn.cursor()

        # 获取60天数据
        cursor.execute("""
            SELECT trade_date, close, volume, amount, pct_change
            FROM daily_prices
            WHERE code = ? AND trade_date <= ?
            ORDER BY trade_date DESC LIMIT 60
        """, (code, target_date.isoformat()))
        rows = cursor.fetchall()
        conn.close()

        if len(rows) < 40:
            return WavePhase.UNKNOWN.value, 0.0

        closes = [r[1] for r in reversed(rows) if r[1] is not None]
        vols = [r[2] for r in reversed(rows) if r[2] is not None]
        amts = [r[3] for r in reversed(rows) if r[3] is not None]

        if len(closes) < 40:
            return WavePhase.UNKNOWN.value, 0.0

        current_price = closes[-1]

        # 找前期高点（最近40天）
        recent_high = max(closes[:-5]) if len(closes) > 5 else max(closes)
        recent_low = min(closes[:-5]) if len(closes) > 5 else min(closes)

        # 计算关键指标
        ma5 = np.mean(closes[-5:])
        ma10 = np.mean(closes[-10:])
        ma20 = np.mean(closes[-20:])

        # 20日涨幅
        ret_20d = (current_price - closes[-20]) / closes[-20] * 100 if len(closes) >= 20 and closes[-20] > 0 else 0

        # 40日涨幅
        ret_40d = (current_price - closes[-40]) / closes[-40] * 100 if len(closes) >= 40 and closes[-40] > 0 else 0

        # 量比
        avg_vol_10d = np.mean(vols[-11:-1]) if len(vols) >= 11 else np.mean(vols[:-1])
        vol_ratio = vols[-1] / avg_vol_10d if avg_vol_10d > 0 else 1.0

        # 成交额比
        avg_amt_10d = np.mean(amts[-11:-1]) if len(amts) >= 11 else np.mean(amts[:-1])
        amt_ratio = amts[-1] / avg_amt_10d if avg_amt_10d > 0 else 1.0

        # ===== 3浪判断 =====
        # 特征：突破前高 + 20日涨幅15-40% + 放量 + 均线多头排列
        wave3_score = 0
        if current_price > recent_high * 0.98:  # 接近或突破前高
            wave3_score += 30
        if 15 <= ret_20d <= 40:  # 20日涨幅适中
            wave3_score += 25
        if vol_ratio > 1.3:  # 放量
            wave3_score += 20
        if current_price > ma5 > ma10 > ma20:  # 多头排列
            wave3_score += 25

        if wave3_score >= 70:
            return WavePhase.WAVE_3.value, wave3_score / 100

        # ===== 5浪判断 =====
        # 特征：涨幅已大(40日>50%) + 可能量价背离 + 接近历史高点
        wave5_score = 0
        if ret_40d > 50:  # 涨幅已大
            wave5_score += 35
        if current_price > recent_high * 0.95:  # 接近前高
            wave5_score += 25
        if vol_ratio < 1.0 and ret_20d > 20:  # 量价背离
            wave5_score += 20
        if ret_20d > 30:  # 近期涨幅大
            wave5_score += 20

        if wave5_score >= 60:
            return WavePhase.WAVE_5.value, wave5_score / 100

        # ===== B浪判断 =====
        # 特征：深度回调(从高点跌20%+) + 缩量 + 开始反弹
        waveB_score = 0
        high_to_now = (current_price - recent_high) / recent_high * 100 if recent_high > 0 else 0
        if -40 < high_to_now < -15:  # 从高点回调15-40%
            waveB_score += 35
        if vol_ratio < 0.8:  # 缩量
            waveB_score += 25
        if ret_5d > 0:  # 开始反弹
            waveB_score += 20
        if ma5 > ma10:  # 短期均线金叉
            waveB_score += 20

        if waveB_score >= 60:
            return WavePhase.WAVE_B.value, waveB_score / 100

        # ===== 1浪判断 =====
        # 特征：底部启动 + 温和放量 + 均线开始多头排列
        wave1_score = 0
        price_position = (current_price - recent_low) / (recent_high - recent_low) * 100 if recent_high > recent_low else 50
        if price_position < 40:  # 相对低位
            wave1_score += 30
        if 1.2 < vol_ratio < 2.0:  # 温和放量
            wave1_score += 25
        if 5 < ret_20d < 20:  # 初步上涨
            wave1_score += 25
        if ma5 > ma10 and current_price > ma20:  # 均线转多
            wave1_score += 20

        if wave1_score >= 60:
            return WavePhase.WAVE_1.value, wave1_score / 100

        return WavePhase.UNKNOWN.value, 0.3

    # ================================================================
    # 第一步：识别热门情绪板块
    # ================================================================
    def get_hot_sectors(self, target_date: date, top_n: int = 5) -> list[SectorHeat]:
        """识别热门情绪板块"""
        conn = self._conn()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT DISTINCT sector_lv1 FROM stocks
            WHERE sector_lv1 IS NOT NULL
              AND (is_delisted IS NULL OR is_delisted = 0)
              AND total_market_cap > 0 AND total_market_cap < ?
        """, (self.MARKET_CAP_MAX,))
        sectors = [r[0] for r in cursor.fetchall()]

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

            cursor.execute("""
                SELECT name FROM stocks WHERE sector_lv1 = ? AND name IS NOT NULL LIMIT 1
            """, (sector,))
            name_row = cursor.fetchone()
            sector_name = name_row[0] if name_row else sector

            up_count = sum(1 for r in rows if r[2] is not None and r[2] > 0)
            advance_ratio = up_count / len(rows) * 100

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

            momentum_5d = momentum_5d or 0
            momentum_20d = momentum_20d or 0
            advance_ratio = advance_ratio or 0
            volume_ratio = volume_ratio or 1.0
            heat_score = (
                momentum_5d * 2.0 +
                momentum_20d * 1.5 +
                advance_ratio * 0.8 +
                (volume_ratio - 1) * 100 * 1.0
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
    # 第二步：筛选龙头股（反推法优化版）
    # ================================================================
    def get_sector_candidates(self, sector: str, target_date: date, top_n: int = 3) -> list[StockCandidate]:
        """
        在热门板块中筛选龙头股

        评分维度（满分100，基于反推法优化）：
        - 价格位置（60-90%最优）: 20分
        - 波浪阶段（3浪最优）: 20分
        - 板块地位（前3名）: 15分
        - 温和放量（1-2倍）: 15分
        - 5日涨幅适中（2-10%）: 10分
        - 均线趋势: 10分
        - 市值（200-350亿）: 10分
        """
        conn = self._conn()
        cursor = conn.cursor()

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

            cursor.execute("""
                SELECT trade_date, close, volume, amount FROM daily_prices
                WHERE code = ? AND trade_date <= ?
                ORDER BY trade_date DESC LIMIT 30
            """, (code, target_date.isoformat()))
            history = cursor.fetchall()

            if len(history) < 20:
                continue

            closes = [h[1] for h in history if h[1] is not None]
            vols = [h[2] for h in history if h[2] is not None]
            amts = [h[3] for h in history if h[3] is not None]

            # ===== 1. 价格位置（反推优化：60-90%最优）- 满分20分 =====
            price_position = 50
            if len(closes) >= 20:
                high_20 = max(closes[:20])
                low_20 = min(closes[:20])
                price_position = (close - low_20) / (high_20 - low_20) * 100 if high_20 > low_20 else 50

                if 60 <= price_position <= 90:  # 反推发现的最优区间
                    score += 20
                    reasons.append(f"价格位置{price_position:.0f}%（突破区间）")
                elif 40 <= price_position < 60:
                    score += 12
                    reasons.append(f"价格位置{price_position:.0f}%（中位）")
                elif price_position > 90:
                    score += 5
                    reasons.append(f"价格位置{price_position:.0f}%（高位）")

            # ===== 2. 波浪阶段（新增）- 满分20分 =====
            wave_phase, wave_confidence = self.detect_wave_phase(code, target_date)
            if wave_phase == WavePhase.WAVE_3.value:  # 3浪最优
                score += 20
                reasons.append(f"3浪主升浪(置信{wave_confidence:.0%})")
            elif wave_phase == WavePhase.WAVE_1.value:
                score += 15
                reasons.append(f"1浪启动(置信{wave_confidence:.0%})")
            elif wave_phase == WavePhase.WAVE_5.value:
                score += 10
                reasons.append(f"5浪末升(谨慎)")
            elif wave_phase == WavePhase.WAVE_B.value:
                score += 8
                reasons.append(f"B浪反弹")

            # ===== 3. 板块地位（反推：48%是板块前3）- 满分15分 =====
            if i == 0:
                score += 15
                reasons.append("板块龙头")
            elif i == 1:
                score += 12
                reasons.append("板块第2")
            elif i == 2:
                score += 8
                reasons.append("板块第3")

            # ===== 4. 温和放量（反推：1-2倍最优）- 满分15分 =====
            avg_vol_5d = np.mean(vols[1:6]) if len(vols) >= 6 else np.mean(vols[1:])
            vol_ratio = vols[0] / avg_vol_5d if avg_vol_5d > 0 else 1.0
            if 1.0 < vol_ratio <= 2.0:
                score += 15
                reasons.append(f"温和放量{vol_ratio:.1f}倍")
            elif 2.0 < vol_ratio <= 3.0:
                score += 8
                reasons.append(f"放量{vol_ratio:.1f}倍")

            # ===== 5. 5日涨幅（反推：牛股5日涨幅中位数约5%）- 满分10分 =====
            ret_5d = (closes[0] - closes[4]) / closes[4] * 100 if len(closes) >= 5 and closes[4] > 0 else 0
            if 2 <= ret_5d <= 10:
                score += 10
                reasons.append(f"5日涨{ret_5d:.1f}%（适中）")
            elif 10 < ret_5d <= 20:
                score += 5
                reasons.append(f"5日涨{ret_5d:.1f}%（偏强）")

            # 计算连涨天数
            consecutive_up = 0
            for j in range(len(closes) - 1):
                if closes[j] > closes[j + 1]:
                    consecutive_up += 1
                else:
                    break

            # ===== 6. 均线趋势（反推：仅34%有多头排列，降低权重）- 满分10分 =====
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

            # 计算20日涨幅和趋势斜率
            ret_20d = (closes[0] - closes[19]) / closes[19] * 100 if len(closes) >= 20 and closes[19] > 0 else 0
            trend_slope = 0
            if len(closes) >= 20:
                x = np.arange(20)
                y = np.array(closes[:20])
                slope = np.polyfit(x, y, 1)[0]
                trend_slope = slope / closes[0] * 100

            # ===== 7. 市值（反推：中位数259亿）- 满分10分 =====
            mkt_cap_yi = mkt_cap / 1e8
            if 200 <= mkt_cap_yi <= 300:
                score += 10
                reasons.append(f"市值{mkt_cap_yi:.0f}亿（最优）")
            elif 300 < mkt_cap_yi <= 350:
                score += 7
                reasons.append(f"市值{mkt_cap_yi:.0f}亿（适中）")
            elif 350 < mkt_cap_yi <= 400:
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
                wave_phase=wave_phase,
                ret_5d=round(ret_5d, 2),
                ret_20d=round(ret_20d, 2),
                vol_ratio=round(vol_ratio, 2),
                ma_position=round(ma_position, 2),
                trend_slope=round(trend_slope, 2) if len(closes) >= 20 else 0,
                consecutive_up=consecutive_up,
                volume_breakout=vol_ratio > 1.5,
                price_position=round(price_position, 1),
            ))

        conn.close()
        candidates.sort(key=lambda x: x.buy_score, reverse=True)
        return candidates[:top_n]

    # ================================================================
    # 第三步：生成买入信号
    # ================================================================
    def generate_buy_signals(self, target_date: date) -> dict:
        """生成买入信号 - 严格筛选"""
        hot_sectors = self.get_hot_sectors(target_date, self.HOT_SECTOR_COUNT)
        logger.info(f"热门板块 Top {len(hot_sectors)}: {[s.sector for s in hot_sectors]}")

        buy_signals = []
        for sh in hot_sectors:
            try:
                candidates = self.get_sector_candidates(sh.sector, target_date, 3)
                for c in candidates:
                    # 严格条件：评分≥80 且 是板块龙头 且 波浪阶段为3浪或1浪
                    wave_ok = c.wave_phase in [WavePhase.WAVE_3.value, WavePhase.WAVE_1.value]
                    if c.buy_score >= self.BUY_THRESHOLD and c.role == "龙头" and wave_ok:
                        buy_signals.append(c)
                        logger.info(f"  买入信号: {c.code} {c.name} | 评分:{c.buy_score} | {c.wave_phase} | 市值:{c.market_cap_yi}亿")
            except Exception as e:
                logger.warning(f"板块 {sh.sector} 信号生成失败: {e}")

        buy_signals.sort(key=lambda x: x.buy_score, reverse=True)
        return {
            "date": target_date.isoformat(),
            "hot_sectors": [
                {"sector": s.sector, "name": s.name, "heat_score": s.heat_score}
                for s in hot_sectors
            ],
            "buy_signals": [
                {"code": s.code, "name": s.name, "sector": s.sector, "role": s.role,
                 "buy_score": s.buy_score, "wave_phase": s.wave_phase,
                 "market_cap_yi": s.market_cap_yi, "price_position": s.price_position,
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
        """检查是否触发卖出信号"""
        sell_price = self._get_price(code, current_date)
        if not sell_price or sell_price <= 0:
            return None

        ret_pct = (sell_price - buy_price) / buy_price * 100
        hold_days = self._count_trading_days(buy_date, current_date)

        conn = self._conn()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT close, volume, amount FROM daily_prices
            WHERE code = ? AND trade_date <= ?
            ORDER BY trade_date DESC LIMIT 15
        """, (code, current_date.isoformat()))
        history = cursor.fetchall()

        ma5_pos = 1.0
        amt_ratio_today = 1.0

        if len(history) >= 5:
            closes = [h[0] for h in history if h[0] is not None]
            vols = [h[1] for h in history if h[1] is not None]
            amts = [h[2] for h in history if h[2] is not None]
            ma5 = np.mean(closes[:5])
            ma5_pos = closes[0] / ma5 if ma5 > 0 else 1.0

            if len(amts) >= 10:
                avg_amt_10d = np.mean(amts[1:11])
                amt_ratio_today = amts[0] / avg_amt_10d if avg_amt_10d > 0 else 1.0

        conn.close()

        # 1. 目标收益达成（30%）
        if ret_pct >= self.TARGET_RETURN:
            return SellSignal(
                reason="target_reached",
                confidence=min(95, 80 + ret_pct),
                details=f"目标收益达成: {ret_pct:.1f}% (持有{hold_days}天)"
            )

        # 2. 止损（-10%）
        if ret_pct <= self.STOP_LOSS_PCT:
            return SellSignal(
                reason="stop_loss",
                confidence=90,
                details=f"触发止损: {ret_pct:.1f}% (持有{hold_days}天)"
            )

        # 3. 持仓到期（60天）
        if hold_days >= self.MAX_HOLD_DAYS:
            return SellSignal(
                reason="max_hold",
                confidence=70,
                details=f"持仓到期: {hold_days}天, 收益{ret_pct:.1f}%"
            )

        # 4. 人气消散：成交额<0.5倍（15天后触发）
        if hold_days >= 15 and amt_ratio_today < 0.5:
            return SellSignal(
                reason="sentiment_collapse",
                confidence=85,
                details=f"人气消散: 成交额{amt_ratio_today:.2f}<0.5倍, 持有{hold_days}天, 收益{ret_pct:.1f}%"
            )

        # 5. 趋势深度破位（20天后触发）
        if hold_days >= self.MIN_HOLD_DAYS and ma5_pos < 0.93:
            return SellSignal(
                reason="trend_collapse",
                confidence=80,
                details=f"趋势深度破位: MA5位置{ma5_pos:.3f}<0.93, 当前收益{ret_pct:.1f}%"
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
        rebalance_days: int = 10,  # 每10个交易日评估一次（低频）
    ) -> dict:
        """运行完整回测"""
        logger.info(f"低频交易回测 v3: {start_date} ~ {end_date}")

        trading_dates = self._get_trading_dates(start_date, end_date)
        logger.info(f"交易日: {len(trading_dates)}")

        capital = initial_capital
        positions: dict[str, TradeRecord] = {}
        all_trades: list[TradeRecord] = []
        daily_values = []
        buy_signal_log = []

        for i, current_date in enumerate(trading_dates):
            # 检查持仓卖出信号
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

            # 生成买入信号（每 rebalance_days 天一次）
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
                                wave_phase=sig["wave_phase"],
                                status="open",
                            )
                            logger.info(f"  买入: {sig['code']} {sig['name']} | "
                                       f"评分:{sig['buy_score']} | {sig['wave_phase']} | "
                                       f"市值:{sig['market_cap_yi']}亿")
                except Exception as e:
                    logger.warning(f"信号生成失败 {current_date}: {e}")

            # 计算总资产
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

        return self._calc_metrics(daily_values, all_trades, initial_capital, buy_signal_log)

    def _calc_metrics(self, daily_values, trades, initial_capital, buy_signal_log):
        """计算回测指标"""
        values = [d["total_value"] for d in daily_values]
        final_value = values[-1] if values else initial_capital
        total_return = (final_value - initial_capital) / initial_capital * 100
        n_days = len(values)
        annual_return = (1 + total_return / 100) ** (252 / max(n_days, 1)) - 1

        peak = values[0]
        max_dd = 0
        for v in values:
            if v > peak:
                peak = v
            dd = (peak - v) / peak * 100
            if dd > max_dd:
                max_dd = dd

        wins = [t for t in trades if t.return_pct > 0]
        win_rate = len(wins) / len(trades) * 100 if trades else 0
        avg_return = np.mean([t.return_pct for t in trades]) if trades else 0
        avg_win = np.mean([t.return_pct for t in wins]) if wins else 0
        avg_loss = np.mean([t.return_pct for t in trades if t.return_pct <= 0]) if [t for t in trades if t.return_pct <= 0] else 0
        pl_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else float('inf')

        # 30%+收益占比（核心目标）
        target_hits_30 = [t for t in trades if t.return_pct >= 30]
        target_hit_rate_30 = len(target_hits_30) / len(trades) * 100 if trades else 0

        # 20%+收益占比
        target_hits_20 = [t for t in trades if t.return_pct >= 20]
        target_hit_rate_20 = len(target_hits_20) / len(trades) * 100 if trades else 0

        total_buy_signals = sum(len(s.get("buy_signals", [])) for s in buy_signal_log)
        qualified_signals = sum(1 for s in buy_signal_log for c in s.get("buy_signals", []) if c["buy_score"] >= 80)

        sell_reasons = {}
        for t in trades:
            reason_key = t.sell_reason.split(":")[0].strip() if t.sell_reason else "unknown"
            sell_reasons[reason_key] = sell_reasons.get(reason_key, 0) + 1

        return {
            "strategy": "low_freq_v3_reverse_engineering",
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
            "target_hit_rate_30_pct": round(target_hit_rate_30, 2),  # 核心指标：30%+占比
            "target_hits_30": len(target_hits_30),
            "target_hit_rate_20_pct": round(target_hit_rate_20, 2),  # 20%+占比
            "target_hits_20": len(target_hits_20),
            "total_buy_signals": total_buy_signals,
            "qualified_buy_signals": qualified_signals,
            "sell_reasons": sell_reasons,
            "recent_trades": [
                {"code": t.code, "name": t.name, "sector": t.sector,
                 "buy_date": t.buy_date, "sell_date": t.sell_date,
                 "return_pct": t.return_pct, "hold_days": t.hold_days,
                 "buy_score": t.buy_score, "wave_phase": t.wave_phase,
                 "sell_reason": t.sell_reason}
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
    """运行低频交易回测 v3"""
    engine = LowFreqTradingEngineV3()

    # 18个月回测
    start_date = date(2024, 11, 26)
    end_date = date(2026, 5, 22)

    print(f"\n{'='*70}")
    print(f"低频量化交易系统 v3 (反推法优化版)")
    print(f"{'='*70}")
    print(f"回测区间: {start_date} ~ {end_date}")
    print(f"选股范围: 市值 200-400 亿")
    print(f"买入阈值: 确定性评分 ≥ {engine.BUY_THRESHOLD}")
    print(f"目标收益: ≥ {engine.TARGET_RETURN}%")
    print(f"持仓周期: {engine.MIN_HOLD_DAYS}-{engine.MAX_HOLD_DAYS} 天")
    print(f"止损线: {engine.STOP_LOSS_PCT}%")
    print(f"新增功能: 波浪阶段判断(3浪/5浪/B浪)")
    print(f"评分优化: 基于反推法结果(高位启动、温和放量)")
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
    print(f"【核心目标】30%+收益达成率: {result['target_hit_rate_30_pct']:.2f}% ({result['target_hits_30']}/{result['total_trades']})")
    print(f"20%+收益达成率: {result['target_hit_rate_20_pct']:.2f}% ({result['target_hits_20']}/{result['total_trades']})")
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
                  f"{t['hold_days']}天 | {t['return_pct']:+.1f}% | {t['wave_phase']} | 评分:{t['buy_score']}")

    # 保存结果
    import json
    output_dir = Path("var/backtest_results")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"lowfreq_v3_{start_date.isoformat()}_{end_date.isoformat()}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n结果已保存: {output_file}")


if __name__ == "__main__":
    main()
