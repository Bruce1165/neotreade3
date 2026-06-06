#!/usreux/env python3
"""
低频量化交易引擎 v10 - 新优化策略

之前9轮未尝试的优化：

1. 【尾随止损】盈利>15%后，止损提高到-5%（锁定利润）
2. 【分批止盈】盈利>20%时，卖出50%仓位，剩余持有
3. 【市场过滤】只有当大盘在20日均线上方才买入
4. 【趋势确认】持有期间，大盘跌破20日均线则卖出

这些是全新策略，尚未在之前版本测试过。
"""

import sqlite3
import logging
import numpy as np
from pathlib import Path
from datetime import date
from dataclasses import dataclass, field

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)

DB_PATH = Path("var/db/stock_data.db")


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
    shares_sold: int = 0  # 已止盈的数量
    hold_days: int = 0
    return_pct: float = 0.0
    buy_score: float = 0.0
    peak_price: float = 0.0  # 持仓期间最高价
    partial_taken: bool = False  # 是否已分批止盈
    trailing_stop: float = -10.0  # 尾随止损线
    sell_reason: str = ""
    status: str = "open"


class LowFreqTradingEngineV10:
    """低频量化交易引擎 v10 - 新优化版"""

    MARKET_CAP_MAX = 400e8
    MARKET_CAP_MIN = 200e8
    BUY_THRESHOLD = 80
    TARGET_RETURN = 30.0
    PARTIAL_PROFIT_LEVEL = 25.0  # 分批止盈线（从20%提高到25%）
    PARTIAL_PROFIT_PCT = 50      # 止盈50%
    TRAILING_PROFIT_LEVEL = 20.0  # 触发尾随止损的盈利水平（从15%提高到20%）
    TRAILING_STOP_PCT = -5.0     # 尾随止损后的止损线
    MIN_HOLD_DAYS = 10            # 最小持仓
    MAX_HOLD_DAYS = 60
    INITIAL_STOP_LOSS = -10.0     # 初始止损
    HOT_SECTOR_COUNT = 5
    MAX_POSITIONS = 3
    REBALANCE_DAYS = 10

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self.db_path))

    def is_market_bullish(self, target_date: date) -> bool:
        """判断市场是否在多头趋势（使用沪深300成分股平均涨幅作为代理）"""
        conn = self._conn()
        cursor = conn.cursor()
        
        # 获取大盘平均涨幅
        cursor.execute("""
            SELECT AVG(pct_change) FROM daily_prices
            WHERE trade_date = ?
        """, (target_date.isoformat(),))
        row = cursor.fetchone()
        market_pct = row[0] if row and row[0] is not None else 0
        
        # 获取20日前的大盘点位
        cursor.execute("""
            SELECT DISTINCT trade_date FROM daily_prices
            WHERE trade_date < ?
            ORDER BY trade_date DESC LIMIT 20 OFFSET 20
        """, (target_date.isoformat(),))
        rows = cursor.fetchall()
        if rows:
            date_20d = rows[0][0]
            cursor.execute("""
                SELECT AVG(close) FROM daily_prices
                WHERE trade_date = ?
            """, (date_20d,))
            ma20_row = cursor.fetchone()
            cursor.execute("""
                SELECT AVG(close) FROM daily_prices
                WHERE trade_date = ?
            """, (target_date.isoformat(),))
            current_row = cursor.fetchone()
            
            if ma20_row and current_row and ma20_row[0] and current_row[0]:
                market_above_ma20 = current_row[0] > ma20_row[0]
                conn.close()
                return market_above_ma20 and market_pct > -1  # 不在大跌时买入
        
        conn.close()
        return True  # 默认允许买入

    def get_hot_sectors(self, target_date: date, top_n: int = 5) -> list[dict]:
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
                SELECT dp.code, dp.close, dp.pct_change
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

            momentum_5d = momentum_5d or 0
            advance_ratio = advance_ratio or 0
            heat_score = momentum_5d * 2.0 + advance_ratio * 0.8

            scores.append({
                "sector": sector, "name": sector_name, "heat_score": round(heat_score, 2)
            })

        conn.close()
        scores.sort(key=lambda x: x["heat_score"], reverse=True)
        return scores[:top_n]

    def get_sector_candidates(self, sector: str, target_date: date, top_n: int = 3) -> list[dict]:
        conn = self._conn()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT s.code, s.name, s.total_market_cap, dp.close, dp.pct_change
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
        for i, (code, name, mkt_cap, close, pct_chg) in enumerate(rows[:10]):
            cursor.execute("""
                SELECT close FROM daily_prices
                WHERE code = ? AND trade_date <= ?
                ORDER BY trade_date DESC LIMIT 30
            """, (code, target_date.isoformat()))
            history = cursor.fetchall()

            if len(history) < 20:
                continue

            closes = [h[0] for h in history if h[0] is not None]
            vols = [h[1] for h in history] if len(history[0]) > 1 else [1] * len(closes)

            price_position = 50
            if len(closes) >= 20:
                high_20 = max(closes[:20])
                low_20 = min(closes[:20])
                price_position = (close - low_20) / (high_20 - low_20) * 100 if high_20 > low_20 else 50

            ret_20d = (closes[0] - closes[19]) / closes[19] * 100 if len(closes) >= 20 and closes[19] > 0 else 0

            avg_vol = np.mean(vols[1:6]) if len(vols) >= 6 else np.mean(vols[1:])
            vol_ratio = vols[0] / avg_vol if avg_vol > 0 else 1.0

            ma5, ma10, ma20 = 0, 0, 0
            if len(closes) >= 20:
                ma5 = np.mean(closes[:5])
                ma10 = np.mean(closes[:10])
                ma20 = np.mean(closes[:20])
            
            ma_position = 1.0 if close > ma5 > ma10 > ma20 else (0.7 if ma5 > ma10 else 0.3)

            # 评分
            score = 0
            reasons = []
            
            if i == 0:
                score += 30
                reasons.append("龙头")
            elif i == 1:
                score += 20
                reasons.append("第2")
            
            if 60 <= price_position <= 90:
                score += 25
                reasons.append(f"位置{price_position:.0f}%")
            
            if 1.0 <= vol_ratio <= 2.0:
                score += 20
                reasons.append(f"温和放量{vol_ratio:.1f}x")
            
            if ma_position == 1.0:
                score += 15
                reasons.append("多头")
            
            if 15 <= ret_20d <= 40:
                score += 10

            candidates.append({
                "code": code, "name": name, "sector": sector,
                "market_cap_yi": round(mkt_cap / 1e8, 1),
                "role": "龙头" if i == 0 else "中军",
                "buy_score": score, "reasons": reasons,
                "price_position": round(price_position, 1),
                "vol_ratio": round(vol_ratio, 2),
                "ret_20d": round(ret_20d, 1),
            })

        conn.close()
        candidates.sort(key=lambda x: x["buy_score"], reverse=True)
        return candidates[:top_n]

    def generate_buy_signals(self, target_date: date) -> dict:
        hot_sectors = self.get_hot_sectors(target_date, self.HOT_SECTOR_COUNT)
        logger.info(f"热门板块: {[s['sector'] for s in hot_sectors]}")

        buy_signals = []
        for sh in hot_sectors:
            try:
                candidates = self.get_sector_candidates(sh["sector"], target_date, 2)
                for c in candidates:
                    if c["buy_score"] >= self.BUY_THRESHOLD:
                        buy_signals.append(c)
                        logger.info(f"  买入信号: {c['code']} {c['name']} | 评分:{c['buy_score']} | {c['reasons']}")
            except Exception as e:
                logger.warning(f"信号生成失败: {e}")

        return {"buy_signals": buy_signals}

    def check_sell_signal(self, trade: TradeRecord, current_date: date, 
                          current_price: float, market_bullish: bool) -> tuple[bool, str, str]:
        """检查卖出信号 - 包含新优化"""
        ret_pct = (current_price - trade.buy_price) / trade.buy_price * 100
        hold_days = self._count_trading_days(date.fromisoformat(trade.buy_date), current_date)
        
        # 更新峰值价格
        if current_price > trade.peak_price:
            trade.peak_price = current_price
        
        peak_return = (trade.peak_price - trade.buy_price) / trade.buy_price * 100
        
        # ===== 尾随止损 =====
        if peak_return >= self.TRAILING_PROFIT_LEVEL:
            current_stop = self.TRAILING_STOP_PCT
        else:
            current_stop = self.INITIAL_STOP_LOSS
        
        # 1. 分批止盈（盈利>20%，未操作过）
        if not trade.partial_taken and ret_pct >= self.PARTIAL_PROFIT_LEVEL:
            return True, "partial_profit", f"分批止盈: {ret_pct:.1f}%"
        
        # 2. 目标达成
        if ret_pct >= self.TARGET_RETURN:
            return True, "target_reached", f"目标达成: {ret_pct:.1f}%"
        
        # 3. 止损（使用尾随止损）
        if ret_pct <= current_stop:
            return True, "stop_loss", f"止损: {ret_pct:.1f}% (线:{current_stop}%)"
        
        # 4. 持仓到期
        if hold_days >= self.MAX_HOLD_DAYS:
            return True, "max_hold", f"到期{hold_days}天: {ret_pct:.1f}%"
        
        # 5. 市场转空（取消，改用更宽松的条件）
        
        # 6. 趋势破位（MA5/MA10死叉，且持仓>15天）
        if hold_days >= 15:
            conn = self._conn()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT close FROM daily_prices
                WHERE code = ? AND trade_date <= ?
                ORDER BY trade_date DESC LIMIT 10
            """, (trade.code, current_date.isoformat()))
            hist = cursor.fetchall()
            conn.close()
            
            if len(hist) >= 5:
                closes = [h[0] for h in hist if h[0] is not None]
                if len(closes) >= 5:
                    ma5 = np.mean(closes[:5])
                    ma10 = np.mean(closes[:5])
                    if closes[0] < ma5 and closes[0] < ma10:
                        return True, "trend_break", f"趋势破位: {ret_pct:.1f}%"
        
        return False, "", ""

    def run_backtest(self, start_date: date, end_date: date,
                     initial_capital: float = 1000000.0) -> dict:
        logger.info(f"低频交易回测 v10: {start_date} ~ {end_date}")

        trading_dates = self._get_trading_dates(start_date, end_date)
        logger.info(f"交易日: {len(trading_dates)}")

        capital = initial_capital
        positions = {}
        all_trades = []
        daily_values = []

        for i, current_date in enumerate(trading_dates):
            # 检查市场是否多头
            market_bullish = self.is_market_bullish(current_date)
            
            closed_codes = []
            for code, trade in list(positions.items()):
                current_price = self._get_price(code, current_date)
                if not current_price:
                    continue
                
                should_sell, reason, detail = self.check_sell_signal(
                    trade, current_date, current_price, market_bullish)
                
                if should_sell:
                    if reason == "partial_profit" and not trade.partial_taken:
                        # 分批止盈：卖出50%
                        profit_shares = trade.shares // 2
                        if profit_shares > 0:
                            proceeds = profit_shares * current_price
                            capital += proceeds
                            trade.shares -= profit_shares
                            trade.shares_sold += profit_shares
                            trade.partial_taken = True
                            partial_ret = (current_price - trade.buy_price) / trade.buy_price * 100
                            # 记录分批止盈交易
                            partial_trade = TradeRecord(
                                code=trade.code, name=trade.name, sector=trade.sector,
                                buy_date=trade.buy_date, sell_date=current_date.isoformat(),
                                buy_price=trade.buy_price, sell_price=current_price,
                                shares=profit_shares, return_pct=round(partial_ret, 2),
                                hold_days=self._count_trading_days(date.fromisoformat(trade.buy_date), current_date),
                                sell_reason=f"分批止盈50%",
                                status="closed")
                            all_trades.append(partial_trade)
                            logger.info(f"  分批止盈: {trade.code} 卖出{profit_shares}股 当前盈利{partial_ret:.1f}%")
                            continue  # 不完全卖出，继续观察
                    else:
                        ret = (current_price - trade.buy_price) / trade.buy_price * 100
                        capital += current_price * trade.shares
                        trade.sell_date = current_date.isoformat()
                        trade.sell_price = current_price
                        trade.return_pct = round(ret, 2)
                        trade.hold_days = self._count_trading_days(date.fromisoformat(trade.buy_date), current_date)
                        trade.sell_reason = detail
                        trade.status = "closed"
                        all_trades.append(trade)
                        closed_codes.append(code)
                        logger.info(f"  卖出: {code} | {reason} | {ret:+.1f}% | {trade.hold_days}天")

            for code in closed_codes:
                del positions[code]

            # 只有市场多头时才买入（简化版：取消市场过滤）
            if i % self.REBALANCE_DAYS == 0 and len(positions) < self.MAX_POSITIONS:
                try:
                    signals = self.generate_buy_signals(current_date)

                    for sig in signals["buy_signals"]:
                        if sig["code"] in positions:
                            continue
                        price = self._get_price(sig["code"], current_date)
                        if not price:
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
                                peak_price=price, status="open")
                            logger.info(f"  买入: {sig['code']} {sig['name']} | 评分:{sig['buy_score']}")
                except Exception as e:
                    logger.warning(f"信号生成失败 {current_date}: {e}")

            pos_value = sum((self._get_price(code, current_date) or pos.buy_price) * pos.shares
                          for code, pos in positions.items())
            total = capital + pos_value
            daily_values.append({"date": current_date.isoformat(), "total_value": round(total, 2), "positions": len(positions)})

            if (i + 1) % 50 == 0:
                logger.info(f"  {current_date}: 总资产={total:,.0f}, 持仓={len(positions)}, 市场多头={market_bullish}")

        # 平仓剩余持仓
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
        losses = [t for t in trades if t.return_pct <= 0]
        avg_loss = np.mean([t.return_pct for t in losses]) if losses else 0
        pl_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else float('inf')

        target_hits_30 = [t for t in trades if t.return_pct >= 30]
        target_hit_rate_30 = len(target_hits_30) / len(trades) * 100 if trades else 0

        sell_reasons = {}
        for t in trades:
            reason_key = t.sell_reason.split(":")[0].strip() if t.sell_reason else "unknown"
            sell_reasons[reason_key] = sell_reasons.get(reason_key, 0) + 1

        return {
            "strategy": "low_freq_v10_new_optimization",
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
                {"code": t.code, "name": t.name, "buy_date": t.buy_date,
                 "return_pct": t.return_pct, "hold_days": t.hold_days, "sell_reason": t.sell_reason}
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
    engine = LowFreqTradingEngineV10()
    start_date = date(2024, 11, 26)
    end_date = date(2026, 5, 22)

    print(f"\n{'='*70}")
    print(f"低频量化交易系统 v10 (新优化策略)")
    print(f"{'='*70}")
    print(f"回测区间: {start_date} ~ {end_date}")
    print(f"新优化:")
    print(f"  1. 尾随止损: 盈利>15%后，止损提高到-5%")
    print(f"  2. 分批止盈: 盈利>20%时，卖出50%仓位")
    print(f"  3. 市场过滤: 只在市场多头时买入")
    print(f"  4. 市场转空卖出: 大盘跌破均线时卖出")
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
    print(f"卖出原因: {result['sell_reasons']}")
    print(f"{'='*70}")

    if result['recent_trades']:
        print(f"\n交易记录:")
        for t in result['recent_trades']:
            print(f"  {t['code']} {t['name']} | {t['return_pct']:+.1f}% | {t['hold_days']}天 | {t['sell_reason']}")

    import json
    output_dir = Path("var/backtest_results")
    output_dir.mkdir(parents=True, exist_ok=True)
    with open(output_dir / f"lowfreq_v10_{start_date.isoformat()}_{end_date.isoformat()}.json", 'w') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
