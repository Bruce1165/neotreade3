#!/usr/bin/env python3
"""
低频量化交易引擎 v7 - Auto Research Round 5 平衡版

v6教训：
- 筛选过于严格，0笔交易
- 需要在"严格筛选"和"有交易机会"之间找到平衡

Round 5 优化：
1. 波浪判断分数从80降到75
2. 降低均线多头排列要求
3. rebalance周期改回10天
4. 连续放量从>=2天改为>=1天
5. 只选板块前2名
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


class WavePhase(Enum):
    WAVE_1 = "1浪"
    WAVE_2 = "2浪"
    WAVE_3 = "3浪"
    WAVE_4 = "4浪"
    WAVE_5 = "5浪"
    WAVE_A = "A浪"
    WAVE_B = "B浪"
    WAVE_C = "C浪"
    UNKNOWN = "未知"


@dataclass
class SectorHeat:
    sector: str
    name: str
    heat_score: float = 0.0
    momentum_5d: float = 0.0
    momentum_20d: float = 0.0
    advance_ratio: float = 0.0
    stock_count: int = 0


@dataclass
class StockCandidate:
    code: str
    name: str
    sector: str
    market_cap_yi: float = 0.0
    role: str = ""
    buy_score: float = 0.0
    buy_reasons: list = field(default_factory=list)
    wave_phase: str = ""
    consecutive_volume_days: int = 0
    cup_handle_score: float = 0.0
    ret_5d: float = 0.0
    ret_20d: float = 0.0
    vol_ratio: float = 0.0
    ma_position: float = 0.5
    price_position: float = 0.0


@dataclass
class SellSignal:
    reason: str
    confidence: float = 0.0
    details: str = ""


@dataclass
class TradeRecord:
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


class LowFreqTradingEngineV7:
    """低频量化交易引擎 v7 - Round 5 平衡版"""

    MARKET_CAP_MAX = 400e8
    MARKET_CAP_MIN = 200e8
    BUY_THRESHOLD = 85          # 稍微降低到85分
    TARGET_RETURN = 30.0
    MIN_HOLD_DAYS = 20
    MAX_HOLD_DAYS = 60
    STOP_LOSS_PCT = -10.0
    HOT_SECTOR_COUNT = 5
    MAX_POSITIONS = 3
    REBALANCE_DAYS = 10        # 改回10天

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self.db_path))

    def detect_consecutive_volume(self, code: str, target_date: date) -> int:
        """检测连续放量天数"""
        conn = self._conn()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT volume FROM daily_prices
            WHERE code = ? AND trade_date <= ?
            ORDER BY trade_date DESC LIMIT 15
        """, (code, target_date.isoformat()))
        rows = cursor.fetchall()
        conn.close()
        
        if len(rows) < 5:
            return 0
        
        vols = [r[0] for r in rows if r[0] is not None and r[0] > 0]
        if len(vols) < 5:
            return 0
        
        avg_vol = np.mean(vols[1:11]) if len(vols) >= 11 else np.mean(vols[1:])
        
        consecutive = 0
        for v in vols:
            if v > avg_vol * 1.2:
                consecutive += 1
            else:
                break
        
        return consecutive

    def detect_cup_handle(self, code: str, target_date: date) -> float:
        """检测杯柄形态"""
        conn = self._conn()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT close, volume FROM daily_prices
            WHERE code = ? AND trade_date <= ?
            ORDER BY trade_date DESC LIMIT 40
        """, (code, target_date.isoformat()))
        rows = cursor.fetchall()
        conn.close()
        
        if len(rows) < 25:
            return 0.0
        
        closes = [r[0] for r in reversed(rows) if r[0] is not None]
        vols = [r[1] for r in reversed(rows) if r[1] is not None]
        
        if len(closes) < 25 or len(vols) < 25:
            return 0.0
        
        score = 0.0
        
        # 杯型结构
        recent_20 = closes[-20:]
        min_idx = recent_20.index(min(recent_20))
        min_price = min(recent_20)
        
        if 5 <= min_idx <= 15:
            rebound = (recent_20[-1] - min_price) / min_price * 100
            if rebound > 8:
                score += 0.3
        
        # 柄部缩量
        if len(vols) >= 12:
            recent_vol = np.mean(vols[-5:])
            pre_vol = np.mean(vols[-12:-5])
            if pre_vol > 0 and recent_vol / pre_vol < 0.9:
                score += 0.3
        
        # 接近高点
        recent_high = max(closes[-20:])
        if recent_high > 0 and closes[-1] / recent_high > 0.95:
            score += 0.4
        
        return min(score, 1.0)

    def detect_wave_phase_v7(self, code: str, target_date: date) -> tuple[str, float]:
        """
        Round 7 波浪判断：降低门槛，增加识别度
        """
        conn = self._conn()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT close, volume FROM daily_prices
            WHERE code = ? AND trade_date <= ?
            ORDER BY trade_date DESC LIMIT 50
        """, (code, target_date.isoformat()))
        rows = cursor.fetchall()
        conn.close()

        if len(rows) < 35:
            return WavePhase.UNKNOWN.value, 0.0

        closes = [r[0] for r in reversed(rows) if r[0] is not None]
        vols = [r[1] for r in reversed(rows) if r[1] is not None]

        if len(closes) < 35:
            return WavePhase.UNKNOWN.value, 0.0

        current_price = closes[-1]
        recent_high = max(closes[:-5]) if len(closes) > 5 else max(closes)

        ma5 = np.mean(closes[-5:])
        ma10 = np.mean(closes[-10:])
        ma20 = np.mean(closes[-20:])

        ret_20d = (current_price - closes[-20]) / closes[-20] * 100 if len(closes) >= 20 and closes[-20] > 0 else 0

        avg_vol_10d = np.mean(vols[-11:-1]) if len(vols) >= 11 else np.mean(vols[:-1])
        vol_ratio = vols[-1] / avg_vol_10d if avg_vol_10d > 0 else 1.0

        # ===== 3浪判断（降低到75分）=====
        wave3_score = 0
        
        # 均线多头排列
        if current_price > ma5 > ma10 > ma20:
            wave3_score += 35
        elif ma5 > ma10 and current_price > ma20:
            wave3_score += 20
        
        # 接近高点
        if current_price / recent_high >= 0.97:
            wave3_score += 25
        
        # 20日涨幅
        if 10 <= ret_20d <= 50:
            wave3_score += 20
        
        # 温和放量
        if 1.2 <= vol_ratio <= 2.5:
            wave3_score += 15
        elif vol_ratio > 2.5:
            wave3_score += 5

        if wave3_score >= 75:
            return WavePhase.WAVE_3.value, wave3_score / 100

        # ===== 1浪判断 =====
        wave1_score = 0
        if ret_20d < 20:
            wave1_score += 25
        if ma5 > ma10:
            wave1_score += 25
        if 1.0 < vol_ratio < 2.5:
            wave1_score += 25
        if current_price > ma20:
            wave1_score += 25

        if wave1_score >= 75:
            return WavePhase.WAVE_1.value, wave1_score / 100

        return WavePhase.UNKNOWN.value, 0.3

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

            momentum_5d = momentum_5d or 0
            momentum_20d = momentum_20d or 0
            advance_ratio = advance_ratio or 0
            heat_score = momentum_5d * 2.0 + momentum_20d * 1.5 + advance_ratio * 0.8

            scores.append(SectorHeat(
                sector=sector, name=sector_name, heat_score=round(heat_score, 2),
                momentum_5d=round(momentum_5d, 2), momentum_20d=round(momentum_20d, 2),
                advance_ratio=round(advance_ratio, 2), stock_count=len(rows),
            ))

        conn.close()
        scores.sort(key=lambda x: x.heat_score, reverse=True)
        return scores[:top_n]

    def get_sector_candidates(self, sector: str, target_date: date, top_n: int = 2) -> list[StockCandidate]:
        """筛选板块前2名"""
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
        for i in range(min(top_n, len(rows))):
            code, name, mkt_cap, close, pct_chg, amount, volume = rows[i]
            reasons = []
            score = 0

            cursor.execute("""
                SELECT close, volume FROM daily_prices
                WHERE code = ? AND trade_date <= ?
                ORDER BY trade_date DESC LIMIT 30
            """, (code, target_date.isoformat()))
            history = cursor.fetchall()

            if len(history) < 20:
                continue

            closes = [h[0] for h in history if h[0] is not None]
            vols = [h[1] for h in history if h[1] is not None]

            wave_phase, wave_confidence = self.detect_wave_phase_v7(code, target_date)
            consecutive_volume_days = self.detect_consecutive_volume(code, target_date)
            cup_handle_score = self.detect_cup_handle(code, target_date)

            price_position = 50
            if len(closes) >= 20:
                high_20 = max(closes[:20])
                low_20 = min(closes[:20])
                price_position = (close - low_20) / (high_20 - low_20) * 100 if high_20 > low_20 else 50

            ret_5d = (closes[0] - closes[4]) / closes[4] * 100 if len(closes) >= 5 and closes[4] > 0 else 0
            ret_20d = (closes[0] - closes[19]) / closes[19] * 100 if len(closes) >= 20 and closes[19] > 0 else 0

            avg_vol_5d = np.mean(vols[1:6]) if len(vols) >= 6 else np.mean(vols[1:])
            vol_ratio = vols[0] / avg_vol_5d if avg_vol_5d > 0 else 1.0

            ma_position = 0.5
            if len(closes) >= 20:
                ma5 = np.mean(closes[:5])
                ma10 = np.mean(closes[:10])
                ma20 = np.mean(closes[:20])
                if close > ma5 > ma10 > ma20:
                    ma_position = 1.0
                elif ma5 > ma10 and close > ma5:
                    ma_position = 0.7
                elif close > ma20:
                    ma_position = 0.4

            # 评分
            if wave_phase == WavePhase.WAVE_3.value:
                score += 25
                reasons.append(f"3浪(置信{wave_confidence:.0%})")
            elif wave_phase == WavePhase.WAVE_1.value:
                score += 20
                reasons.append("1浪")

            if ma_position == 1.0:
                score += 20
                reasons.append("均线多头")
            elif ma_position == 0.7:
                score += 12

            if consecutive_volume_days >= 2:
                score += 15
                reasons.append(f"放量{consecutive_volume_days}天")
            elif consecutive_volume_days >= 1:
                score += 8

            if 60 <= price_position <= 95:
                score += 12
                reasons.append(f"位置{price_position:.0f}%")

            if 1.2 <= vol_ratio <= 2.0:
                score += 10

            if cup_handle_score >= 0.6:
                score += 10
                reasons.append("杯柄")

            if i == 0:
                score += 15
                reasons.append("龙头")
            else:
                score += 10

            mkt_cap_yi = mkt_cap / 1e8
            if 200 <= mkt_cap_yi <= 350:
                score += 8

            candidates.append(StockCandidate(
                code=code, name=name, sector=sector, market_cap_yi=round(mkt_cap_yi, 1),
                role="龙头" if i == 0 else "中军",
                buy_score=score, buy_reasons=reasons, wave_phase=wave_phase,
                consecutive_volume_days=consecutive_volume_days, cup_handle_score=cup_handle_score,
                ret_5d=round(ret_5d, 2), ret_20d=round(ret_20d, 2),
                vol_ratio=round(vol_ratio, 2), ma_position=ma_position, price_position=round(price_position, 1),
            ))

        conn.close()
        candidates.sort(key=lambda x: x.buy_score, reverse=True)
        return candidates[:top_n]

    def generate_buy_signals(self, target_date: date) -> dict:
        """生成买入信号"""
        hot_sectors = self.get_hot_sectors(target_date, self.HOT_SECTOR_COUNT)
        logger.info(f"热门板块 Top {len(hot_sectors)}: {[s.sector for s in hot_sectors]}")

        buy_signals = []
        for sh in hot_sectors:
            try:
                candidates = self.get_sector_candidates(sh.sector, target_date, 2)
                for c in candidates:
                    wave_ok = c.wave_phase in [WavePhase.WAVE_3.value, WavePhase.WAVE_1.value]
                    if c.buy_score >= self.BUY_THRESHOLD and wave_ok:
                        buy_signals.append(c)
                        logger.info(f"  买入信号: {c.code} {c.name} | 评分:{c.buy_score} | {c.wave_phase} | 放量:{c.consecutive_volume_days}天")
            except Exception as e:
                logger.warning(f"板块 {sh.sector} 信号生成失败: {e}")

        buy_signals.sort(key=lambda x: x.buy_score, reverse=True)
        return {
            "date": target_date.isoformat(),
            "hot_sectors": [{"sector": s.sector, "name": s.name, "heat_score": s.heat_score} for s in hot_sectors],
            "buy_signals": [
                {"code": s.code, "name": s.name, "sector": s.sector, "role": s.role,
                 "buy_score": s.buy_score, "wave_phase": s.wave_phase, 
                 "consecutive_volume_days": s.consecutive_volume_days,
                 "ret_20d": s.ret_20d, "reasons": s.buy_reasons}
                for s in buy_signals
            ],
            "summary": {"hot_sectors_count": len(hot_sectors), "buy_signals_count": len(buy_signals)}
        }

    def check_sell_signal(self, code: str, buy_date: date, buy_price: float,
                           buy_score: float, current_date: date) -> Optional[SellSignal]:
        """检查卖出信号"""
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
            amts = [h[2] for h in history if h[2] is not None]
            ma5 = np.mean(closes[:5])
            ma5_pos = closes[0] / ma5 if ma5 > 0 else 1.0

            if len(amts) >= 10:
                avg_amt_10d = np.mean(amts[1:11])
                amt_ratio_today = amts[0] / avg_amt_10d if avg_amt_10d > 0 else 1.0

        conn.close()

        if ret_pct >= self.TARGET_RETURN:
            return SellSignal(reason="target_reached", confidence=95,
                            details=f"目标达成: {ret_pct:.1f}% ({hold_days}天)")

        if ret_pct <= self.STOP_LOSS_PCT:
            return SellSignal(reason="stop_loss", confidence=90,
                            details=f"止损: {ret_pct:.1f}% ({hold_days}天)")

        if hold_days >= self.MAX_HOLD_DAYS:
            return SellSignal(reason="max_hold", confidence=70,
                            details=f"到期: {hold_days}天, {ret_pct:.1f}%")

        if hold_days >= 15 and amt_ratio_today < 0.5:
            return SellSignal(reason="sentiment_collapse", confidence=85,
                            details=f"人气消散: {amt_ratio_today:.2f}<0.5")

        if hold_days >= self.MIN_HOLD_DAYS and ma5_pos < 0.93:
            return SellSignal(reason="trend_collapse", confidence=80,
                            details=f"破位: MA5={ma5_pos:.3f}")

        return None

    def run_backtest(self, start_date: date, end_date: date,
                     initial_capital: float = 1000000.0) -> dict:
        """运行回测"""
        logger.info(f"低频交易回测 v7: {start_date} ~ {end_date}")

        trading_dates = self._get_trading_dates(start_date, end_date)
        logger.info(f"交易日: {len(trading_dates)}, rebalance: {self.REBALANCE_DAYS}天")

        capital = initial_capital
        positions = {}
        all_trades = []
        daily_values = []

        for i, current_date in enumerate(trading_dates):
            closed_codes = []
            for code, trade in list(positions.items()):
                sell = self.check_sell_signal(code, date.fromisoformat(trade.buy_date),
                                              trade.buy_price, trade.buy_score, current_date)
                if sell:
                    sell_price = self._get_price(code, current_date)
                    if sell_price:
                        ret = (sell_price - trade.buy_price) / trade.buy_price * 100
                        capital += sell_price * trade.shares
                        trade.sell_date = current_date.isoformat()
                        trade.sell_price = sell_price
                        trade.return_pct = round(ret, 2)
                        trade.hold_days = self._count_trading_days(date.fromisoformat(trade.buy_date), current_date)
                        trade.sell_reason = sell.details
                        trade.status = "closed"
                        all_trades.append(trade)
                        closed_codes.append(code)
                        logger.info(f"  卖出: {code} | {sell.reason} | {ret:+.1f}% | {trade.hold_days}天")

            for code in closed_codes:
                del positions[code]

            if i % self.REBALANCE_DAYS == 0 and len(positions) < self.MAX_POSITIONS:
                try:
                    signals = self.generate_buy_signals(current_date)

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
                                code=sig["code"], name=sig["name"], sector=sig["sector"],
                                buy_date=current_date.isoformat(), buy_price=price,
                                shares=shares, buy_score=sig["buy_score"],
                                wave_phase=sig["wave_phase"], status="open")
                            logger.info(f"  买入: {sig['code']} {sig['name']} | 评分:{sig['buy_score']}")
                except Exception as e:
                    logger.warning(f"信号生成失败 {current_date}: {e}")

            pos_value = sum((self._get_price(code, current_date) or pos.buy_price) * pos.shares
                          for code, pos in positions.items())
            total = capital + pos_value
            daily_values.append({"date": current_date.isoformat(), "total_value": round(total, 2), "positions": len(positions)})

            if (i + 1) % 50 == 0:
                logger.info(f"  {current_date}: 总资产={total:,.0f}, 持仓={len(positions)}")

        for code, trade in positions.items():
            final_price = self._get_price(code, trading_dates[-1])
            if final_price:
                ret = (final_price - trade.buy_price) / trade.buy_price * 100
                capital += final_price * trade.shares
                trade.sell_date = trading_dates[-1].isoformat()
                trade.sell_price = final_price
                trade.return_pct = round(ret, 2)
                trade.hold_days = self._count_trading_days(date.fromisoformat(trade.buy_date), trading_dates[-1])
                trade.sell_reason = "回测结束平仓"
                trade.status = "closed"
                all_trades.append(trade)

        return self._calc_metrics(daily_values, all_trades, initial_capital)

    def _calc_metrics(self, daily_values, trades, initial_capital):
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

        target_hits_30 = [t for t in trades if t.return_pct >= 30]
        target_hit_rate_30 = len(target_hits_30) / len(trades) * 100 if trades else 0

        sell_reasons = {}
        for t in trades:
            reason_key = t.sell_reason.split(":")[0].strip() if t.sell_reason else "unknown"
            sell_reasons[reason_key] = sell_reasons.get(reason_key, 0) + 1

        return {
            "strategy": "low_freq_v7_round5",
            "total_trades": len(trades),
            "win_rate_pct": round(win_rate, 2),
            "target_hit_rate_30_pct": round(target_hit_rate_30, 2),
            "target_hits_30": len(target_hits_30),
            "total_return_pct": round(total_return, 2),
            "annual_return_pct": round(annual_return * 100, 2),
            "max_drawdown_pct": round(max_dd, 2),
            "avg_return_pct": round(avg_return, 2),
            "profit_loss_ratio": round(pl_ratio, 2),
            "sell_reasons": sell_reasons,
            "recent_trades": [
                {"code": t.code, "name": t.name, "buy_date": t.buy_date, "sell_date": t.sell_date,
                 "return_pct": t.return_pct, "hold_days": t.hold_days, "wave_phase": t.wave_phase, "buy_score": t.buy_score}
                for t in trades[-20:]
            ],
        }

    def _get_trading_dates(self, start: date, end: date) -> list[date]:
        conn = self._conn()
        cursor = conn.execute("SELECT DISTINCT trade_date FROM daily_prices WHERE trade_date BETWEEN ? AND ? ORDER BY trade_date",
                            (start.isoformat(), end.isoformat()))
        dates = [date.fromisoformat(r[0]) for r in cursor.fetchall()]
        conn.close()
        return dates

    def _get_price(self, code: str, d: date) -> float | None:
        conn = self._conn()
        cursor = conn.execute("SELECT close FROM daily_prices WHERE code = ? AND trade_date = ?", (code, d.isoformat()))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row and row[0] > 0 else None

    def _count_trading_days(self, start: date, end: date) -> int:
        return len(self._get_trading_dates(start, end))


def main():
    engine = LowFreqTradingEngineV7()
    start_date = date(2024, 11, 26)
    end_date = date(2026, 5, 22)

    print(f"\n{'='*70}")
    print(f"低频量化交易系统 v7 (Round 5: 平衡版)")
    print(f"{'='*70}")
    print(f"回测区间: {start_date} ~ {end_date}")
    print(f"买入条件: 评分≥85 + 板块前2名 + 3浪/1浪")
    print(f"Rebalance周期: {engine.REBALANCE_DAYS}天")
    print(f"{'='*70}\n")

    result = engine.run_backtest(start_date, end_date)

    print(f"\n{'='*70}")
    print(f"回测结果")
    print(f"{'='*70}")
    print(f"交易次数: {result['total_trades']}")
    print(f"胜率: {result['win_rate_pct']:.2f}%")
    print(f"【核心】30%+达成率: {result['target_hit_rate_30_pct']:.2f}% ({result['target_hits_30']}/{result['total_trades']})")
    print(f"总收益率: {result['total_return_pct']:.2f}%")
    print(f"年化收益率: {result['annual_return_pct']:.2f}%")
    print(f"最大回撤: {result['max_drawdown_pct']:.2f}%")
    print(f"盈亏比: {result['profit_loss_ratio']:.2f}")
    print(f"{'='*70}")

    if result['recent_trades']:
        print(f"\n交易记录:")
        for t in result['recent_trades']:
            print(f"  {t['code']} {t['name']} | {t['return_pct']:+.1f}% | {t['wave_phase']} | {t['hold_days']}天 | 评分:{t['buy_score']}")

    import json
    output_dir = Path("var/backtest_results")
    output_dir.mkdir(parents=True, exist_ok=True)
    with open(output_dir / f"lowfreq_v7_{start_date.isoformat()}_{end_date.isoformat()}.json", 'w') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
