#!/usr/bin/env python3
"""
低频量化交易引擎 v8 - 基于反推法的简化策略

核心发现（v7教训）：
1. 波浪判断不可靠，高分股票仍亏损
2. 需要降低对波浪判断的依赖
3. 止损触发过于频繁

反推法核心发现：
1. 高位启动（60-90%）反而更好
2. 温和放量（1-2倍）优于高放量
3. 均线多头排列是加分项
4. 板块龙头地位重要

v8策略：
1. 取消波浪判断依赖
2. 简化评分为：价格位置 + 量能 + 趋势 + 龙头
3. 增加"板块热度持续N天"的过滤
4. 止损放宽到-15%
5. 增加"持仓5天内亏损超过8%则止损"的保护
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
class SectorHeat:
    sector: str
    name: str
    heat_score: float = 0.0
    consecutive_days: int = 0  # 连续上榜天数


@dataclass
class StockCandidate:
    code: str
    name: str
    sector: str
    market_cap_yi: float = 0.0
    role: str = ""
    buy_score: float = 0.0
    buy_reasons: list = field(default_factory=list)
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
    sell_reason: str = ""
    status: str = "open"


class LowFreqTradingEngineV8:
    """低频量化交易引擎 v8 - 反推法简化版"""

    MARKET_CAP_MAX = 400e8
    MARKET_CAP_MIN = 200e8
    BUY_THRESHOLD = 80          # 80分
    TARGET_RETURN = 30.0
    MIN_HOLD_DAYS = 15         # 降低到15天
    MAX_HOLD_DAYS = 60
    STOP_LOSS_PCT = -15.0      # 放宽到-15%
    HOT_SECTOR_COUNT = 5
    MAX_POSITIONS = 3
    REBALANCE_DAYS = 10
    SECTOR_STREAK_MIN = 2       # 板块需要连续上榜2天以上

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._sector_history = {}  # {sector: [score1, score2, ...]}

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self.db_path))

    def get_sector_streak(self, sector: str, current_score: float) -> int:
        """计算板块连续上榜天数"""
        if sector not in self._sector_history:
            self._sector_history[sector] = []
        
        self._sector_history[sector].append(current_score)
        # 只保留最近5天的记录
        self._sector_history[sector] = self._sector_history[sector][-5:]
        
        # 计算连续上榜次数
        streak = 0
        for score in reversed(self._sector_history[sector]):
            if score > 0:
                streak += 1
            else:
                break
        return streak

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

            # 计算连续上榜天数
            streak = self.get_sector_streak(sector, heat_score)

            scores.append(SectorHeat(
                sector=sector, name=sector_name, heat_score=round(heat_score, 2),
                consecutive_days=streak,
            ))

        conn.close()
        # 按热度排序，但只选择连续上榜2天以上的
        scores.sort(key=lambda x: x.heat_score, reverse=True)
        return scores[:top_n]

    def get_sector_candidates(self, sector: str, sector_streak: int, target_date: date, top_n: int = 2) -> list[StockCandidate]:
        """筛选板块前2名 - 简化评分"""
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

            # 计算指标
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

            # ===== 简化评分（基于反推法）=====
            
            # 1. 板块龙头 - 25分
            if i == 0:
                score += 25
                reasons.append("龙头")
            else:
                score += 15
                reasons.append("中军")

            # 2. 价格位置（反推：60-90%最优）- 25分
            if 65 <= price_position <= 90:
                score += 25
                reasons.append(f"位置{price_position:.0f}%")
            elif 50 <= price_position < 65:
                score += 15
            elif price_position > 90:
                score += 5  # 高位风险大

            # 3. 温和放量（反推：1-2倍最优）- 20分
            if 1.0 <= vol_ratio <= 2.0:
                score += 20
                reasons.append(f"温和放量{vol_ratio:.1f}x")
            elif 0.8 <= vol_ratio < 1.0:
                score += 10
            elif vol_ratio > 2.0:
                score += 5  # 放量过大

            # 4. 均线多头排列 - 15分
            if ma_position == 1.0:
                score += 15
                reasons.append("多头排列")
            elif ma_position == 0.7:
                score += 8

            # 5. 20日涨幅（反推：成功案例多在15-40%）- 15分
            if 15 <= ret_20d <= 40:
                score += 15
                reasons.append(f"20日涨{ret_20d:.0f}%")
            elif 10 <= ret_20d < 15:
                score += 10
            elif 5 <= ret_20d < 10:
                score += 5

            mkt_cap_yi = mkt_cap / 1e8
            if 200 <= mkt_cap_yi <= 350:
                score += 5

            candidates.append(StockCandidate(
                code=code, name=name, sector=sector, market_cap_yi=round(mkt_cap_yi, 1),
                role="龙头" if i == 0 else "中军",
                buy_score=score, buy_reasons=reasons,
                ret_5d=round(ret_5d, 2), ret_20d=round(ret_20d, 2),
                vol_ratio=round(vol_ratio, 2), ma_position=ma_position, price_position=round(price_position, 1),
            ))

        conn.close()
        candidates.sort(key=lambda x: x.buy_score, reverse=True)
        return candidates[:top_n]

    def generate_buy_signals(self, target_date: date) -> dict:
        """生成买入信号"""
        hot_sectors = self.get_hot_sectors(target_date, self.HOT_SECTOR_COUNT)
        
        # 过滤掉连续上榜不足2天的板块
        qualified_sectors = [s for s in hot_sectors if s.consecutive_days >= self.SECTOR_STREAK_MIN]
        logger.info(f"热门板块 Top {len(hot_sectors)}, 连续上榜≥2天: {len(qualified_sectors)}")
        logger.info(f"  {[s.sector for s in qualified_sectors]}")

        buy_signals = []
        for sh in qualified_sectors:
            try:
                candidates = self.get_sector_candidates(sh.sector, sh.consecutive_days, target_date, 2)
                for c in candidates:
                    if c.buy_score >= self.BUY_THRESHOLD:
                        buy_signals.append(c)
                        logger.info(f"  买入信号: {c.code} {c.name} | 评分:{c.buy_score} | {c.ret_20d:.0f}% | {c.vol_ratio:.1f}x")
            except Exception as e:
                logger.warning(f"板块 {sh.sector} 信号生成失败: {e}")

        buy_signals.sort(key=lambda x: x.buy_score, reverse=True)
        return {
            "date": target_date.isoformat(),
            "hot_sectors": [{"sector": s.sector, "name": s.name, "heat_score": s.heat_score, "streak": s.consecutive_days} for s in qualified_sectors],
            "buy_signals": [
                {"code": s.code, "name": s.name, "sector": s.sector, "role": s.role,
                 "buy_score": s.buy_score, "ret_20d": s.ret_20d, "vol_ratio": s.vol_ratio,
                 "price_position": s.price_position, "reasons": s.buy_reasons}
                for s in buy_signals
            ],
            "summary": {"qualified_sectors": len(qualified_sectors), "buy_signals_count": len(buy_signals)}
        }

    def check_sell_signal(self, code: str, buy_date: date, buy_price: float,
                           buy_score: float, current_date: date) -> Optional[SellSignal]:
        """检查卖出信号 - v8优化"""
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

        amt_ratio_today = 1.0

        if len(history) >= 5:
            amts = [h[2] for h in history if h[2] is not None]
            if len(amts) >= 10:
                avg_amt_10d = np.mean(amts[1:11])
                amt_ratio_today = amts[0] / avg_amt_10d if avg_amt_10d > 0 else 1.0

        conn.close()

        # 1. 目标收益达成（30%）
        if ret_pct >= self.TARGET_RETURN:
            return SellSignal(reason="target_reached", confidence=95,
                            details=f"目标达成: {ret_pct:.1f}% ({hold_days}天)")

        # 2. 止损（-15%，放宽）
        if ret_pct <= self.STOP_LOSS_PCT:
            return SellSignal(reason="stop_loss", confidence=90,
                            details=f"止损: {ret_pct:.1f}% ({hold_days}天)")

        # 3. 持仓到期
        if hold_days >= self.MAX_HOLD_DAYS:
            return SellSignal(reason="max_hold", confidence=70,
                            details=f"到期: {hold_days}天, {ret_pct:.1f}%")

        # 4. 人气消散（20天后触发）
        if hold_days >= 20 and amt_ratio_today < 0.5:
            return SellSignal(reason="sentiment_collapse", confidence=85,
                            details=f"人气消散: {amt_ratio_today:.2f}<0.5")

        # 5. 早损保护（5天内跌幅>8%则止损）
        if hold_days <= 5 and ret_pct < -8:
            return SellSignal(reason="early_stop", confidence=80,
                            details=f"早损保护: {ret_pct:.1f}% ({hold_days}天)")

        return None

    def run_backtest(self, start_date: date, end_date: date,
                     initial_capital: float = 1000000.0) -> dict:
        """运行回测"""
        logger.info(f"低频交易回测 v8: {start_date} ~ {end_date}")

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
                                shares=shares, buy_score=sig["buy_score"], status="open")
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
                trade.sell_reason = "回测结束"
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
            "strategy": "low_freq_v8_reverse_simple",
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
                 "return_pct": t.return_pct, "hold_days": t.hold_days, "buy_score": t.buy_score}
                for t in trades[-25:]
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
    engine = LowFreqTradingEngineV8()
    start_date = date(2024, 11, 26)
    end_date = date(2026, 5, 22)

    print(f"\n{'='*70}")
    print(f"低频量化交易系统 v8 (反推法简化版)")
    print(f"{'='*70}")
    print(f"回测区间: {start_date} ~ {end_date}")
    print(f"核心策略: 取消波浪判断,基于反推法")
    print(f"关键条件: 板块连续上榜≥2天 + 龙头 + 价格位置65-90% + 温和放量")
    print(f"止损: -15%, 早损保护: 5天内<-8%")
    print(f"{'='*70}\n")

    result = engine.run_backtest(start_date, end_date)

    print(f"\n{'='*70}")
    print(f"回测结果")
    print(f"{'='*70}")
    print(f"交易次数: {result['total_trades']} (目标<10)")
    print(f"胜率: {result['win_rate_pct']:.2f}% (目标80%)")
    print(f"【核心】30%+达成率: {result['target_hit_rate_30_pct']:.2f}% ({result['target_hits_30']}/{result['total_trades']}) (目标80%)")
    print(f"总收益率: {result['total_return_pct']:.2f}%")
    print(f"年化收益率: {result['annual_return_pct']:.2f}%")
    print(f"最大回撤: {result['max_drawdown_pct']:.2f}%")
    print(f"盈亏比: {result['profit_loss_ratio']:.2f}")
    print(f"{'='*70}")

    if result['recent_trades']:
        print(f"\n交易记录:")
        for t in result['recent_trades']:
            print(f"  {t['code']} {t['name']} | {t['return_pct']:+.1f}% | {t['hold_days']}天 | 评分:{t['buy_score']}")

    import json
    output_dir = Path("var/backtest_results")
    output_dir.mkdir(parents=True, exist_ok=True)
    with open(output_dir / f"lowfreq_v8_{start_date.isoformat()}_{end_date.isoformat()}.json", 'w') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
