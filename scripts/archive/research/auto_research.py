#!/usr/bin/env python3
"""
低频交易引擎 Auto Research
============================
研究目标：
1. 分析全量历史评分分布，找到有效阈值
2. 深度分析失败案例，挖掘"人气溃散"阈值
3. 迭代优化评分体系
4. 验证最优参数组合
"""

import sqlite3
import numpy as np
from pathlib import Path
from datetime import date, timedelta
from collections import defaultdict
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)

DB_PATH = Path("var/db/stock_data.db")


def query(sql, params=None):
    db = sqlite3.connect(str(DB_PATH))
    cursor = db.cursor()
    if params:
        cursor.execute(sql, params)
    else:
        cursor.execute(sql)
    rows = cursor.fetchall()
    db.close()
    return rows


def query_one(sql, params=None):
    rows = query(sql, params)
    return rows[0] if rows else None


# ================================================================
# 第一步：分析全量历史评分分布
# ================================================================
def analyze_score_distribution():
    logger.info("=" * 60)
    logger.info("第一步：分析全量历史评分分布")
    logger.info("=" * 60)

    # 获取所有交易日
    rows = query("""
        SELECT DISTINCT trade_date FROM daily_prices
        WHERE trade_date BETWEEN '2024-11-26' AND '2026-05-22'
        ORDER BY trade_date
    """)
    trading_dates = [r[0] for r in rows]
    eval_dates = trading_dates[::5]
    logger.info(f"评估日期数: {len(eval_dates)}, 每5天一次")

    all_samples = []

    for d_str in eval_dates:
        # 获取候选板块
        sector_rows = query("""
            SELECT DISTINCT s.sector_lv1 FROM stocks s
            WHERE s.sector_lv1 IS NOT NULL
              AND (s.is_delisted IS NULL OR s.is_delisted = 0)
              AND s.total_market_cap > 200e8 AND s.total_market_cap < 400e8
            LIMIT 10
        """)
        sectors = [r[0] for r in sector_rows]

        for sector in sectors[:3]:
            stock_rows = query("""
                SELECT s.code, s.name, s.total_market_cap, dp.close, dp.pct_change, dp.amount, dp.volume
                FROM stocks s
                JOIN daily_prices dp ON s.code = dp.code
                WHERE s.sector_lv1 = ? AND dp.trade_date = ?
                  AND s.total_market_cap > 200e8 AND s.total_market_cap < 400e8
                  AND (s.is_delisted IS NULL OR s.is_delisted = 0)
                  AND dp.close > 0
                ORDER BY dp.pct_change DESC
                LIMIT 5
            """, (sector, d_str))

            for i, (code, name, mkt_cap, close, pct_chg, amount, volume) in enumerate(stock_rows[:3]):
                history_rows = query("""
                    SELECT trade_date, close, volume FROM daily_prices
                    WHERE code = ? AND trade_date <= ?
                    ORDER BY trade_date DESC LIMIT 30
                """, (code, d_str))

                if len(history_rows) < 20:
                    continue

                closes = [h[1] for h in history_rows if h[1] is not None]
                vols = [h[2] for h in history_rows if h[2] is not None]

                if len(closes) < 20:
                    continue

                score = 0
                ma5 = np.mean(closes[:5])
                ma10 = np.mean(closes[:10])
                ma20 = np.mean(closes[:20])

                # 评分体系
                if close > ma5 > ma10 > ma20: score += 20
                elif ma5 > ma10 > ma20 and close > ma5: score += 12
                elif close > ma20: score += 5

                avg_vol = np.mean(vols[1:6]) if len(vols) >= 6 else np.mean(vols[1:])
                vol_ratio = vols[0] / avg_vol if avg_vol > 0 else 1.0
                if vol_ratio > 2.5: score += 18
                elif vol_ratio > 1.8: score += 10
                elif vol_ratio > 1.3: score += 4

                ret_5d = (closes[0] - closes[4]) / closes[4] * 100 if len(closes) >= 5 and closes[4] > 0 else 0
                if 3 <= ret_5d <= 7: score += 18
                elif 7 < ret_5d <= 12: score += 8
                elif ret_5d > 0: score += 3

                consecutive_up = 0
                for j in range(len(closes) - 1):
                    if closes[j] > closes[j + 1]:
                        consecutive_up += 1
                    else:
                        break
                if consecutive_up >= 4: score += 15
                elif consecutive_up >= 2: score += 6

                x = np.arange(20)
                y = np.array(closes[:20])
                slope = np.polyfit(x, y, 1)[0]
                trend_slope = slope / closes[0] * 100
                if trend_slope > 0.5: score += 18
                elif trend_slope > 0.2: score += 8

                rank_bonus = max(0, 15 - i * 5)
                score += rank_bonus

                mkt_cap_yi = mkt_cap / 1e8
                if 200 <= mkt_cap_yi <= 350: score += 12
                elif 350 < mkt_cap_yi <= 400: score += 6

                all_samples.append({
                    "code": code, "name": name, "sector": sector,
                    "date": d_str, "score": score,
                    "close": close, "mkt_cap_yi": mkt_cap_yi,
                    "ret_5d": ret_5d, "vol_ratio": vol_ratio,
                    "consecutive_up": consecutive_up, "trend_slope": trend_slope,
                })

    logger.info(f"总样本数: {len(all_samples)}")

    # 评分分布统计
    scores = [s['score'] for s in all_samples]
    logger.info(f"\n评分统计: 最小={min(scores)}, 最大={max(scores)}, "
               f"均值={np.mean(scores):.1f}, 中位数={np.median(scores):.1f}")

    # 各区间统计
    logger.info("\n各评分区间样本数:")
    for low in range(70, 110, 5):
        high = low + 5
        count = sum(1 for s in all_samples if low <= s['score'] < high)
        if count > 0:
            logger.info(f"  {low}-{high}: {count} 个")

    # 统计90分以上的
    above_90 = [s for s in all_samples if s['score'] >= 90]
    above_85 = [s for s in all_samples if s['score'] >= 85]
    above_80 = [s for s in all_samples if s['score'] >= 80]
    logger.info(f"\n90分以上: {len(above_90)} 个")
    logger.info(f"85分以上: {len(above_85)} 个")
    logger.info(f"80分以上: {len(above_80)} 个")

    return all_samples


# ================================================================
# 第二步：深度分析失败案例
# ================================================================
def analyze_failure_cases():
    logger.info("\n" + "=" * 60)
    logger.info("第二步：深度分析失败案例 → 人气溃散阈值")
    logger.info("=" * 60)

    failure_trades = [
        ("603899", "晨光股份", "2024-11-26", -9.7),
        ("600612", "老凤祥", "2024-12-10", -7.2),
        ("601139", "深圳燃气", "2025-08-14", -4.5),
        ("600637", "东方明珠", "2025-08-21", +0.1),
        ("688297", "中无人机", "2025-12-12", +3.5),
    ]

    all_metrics = []

    for code, name, buy_date, final_ret in failure_trades:
        logger.info(f"\n{'='*50}")
        logger.info(f"失败案例: {code} {name} (买入:{buy_date}, 终收益:{final_ret}%)")
        logger.info(f"{'='*50}")

        days = query("""
            SELECT trade_date, close, volume, amount, pct_change
            FROM daily_prices
            WHERE code = ? AND trade_date >= ? AND trade_date <= ?
            ORDER BY trade_date
        """, (code, buy_date, str(date.fromisoformat(buy_date) + timedelta(days=60))))

        if not days:
            continue

        buy_row = query_one("""
            SELECT close FROM daily_prices WHERE code = ? AND trade_date = ?
        """, (code, buy_date))
        if not buy_row:
            continue
        buy_price = buy_row[0]

        peak_price = buy_price
        peak_return = 0.0

        for j, (d_str, close, volume, amount, pct_chg) in enumerate(days):
            ret_from_buy = (close - buy_price) / buy_price * 100
            if close > peak_price:
                peak_price = close
                peak_return = ret_from_buy

            # 市场情绪代理
            market_row = query_one("""
                SELECT AVG(dp.pct_change) FROM daily_prices dp
                JOIN stocks s ON dp.code = s.code
                WHERE dp.trade_date = ?
                  AND s.total_market_cap > 200e8 AND s.total_market_cap < 400e8
                  AND dp.close > 0 AND dp.code != ?
            """, (d_str, code))
            market_ret = market_row[0] if market_row else 0

            up_row = query_one("""
                SELECT COUNT(*) FROM daily_prices dp JOIN stocks s ON dp.code = s.code
                WHERE dp.trade_date = ?
                  AND s.total_market_cap > 200e8 AND s.total_market_cap < 400e8
                  AND dp.close > 0 AND dp.pct_change > 0
            """, (d_str,))
            total_row = query_one("""
                SELECT COUNT(*) FROM daily_prices dp JOIN stocks s ON dp.code = s.code
                WHERE dp.trade_date = ?
                  AND s.total_market_cap > 200e8 AND s.total_market_cap < 400e8
                  AND dp.close > 0
            """, (d_str,))
            up_count = up_row[0] if up_row else 0
            total_count = total_row[0] if total_row else 1
            advance_ratio = up_count / total_count * 100

            # MA5位置
            recent = query("""
                SELECT close FROM daily_prices
                WHERE code = ? AND trade_date <= ?
                ORDER BY trade_date DESC LIMIT 5
            """, (code, d_str))
            ma5 = np.mean([r[0] for r in recent]) if recent else close
            ma5_pos = close / ma5 if ma5 > 0 else 1.0

            # MA10位置（用于死叉判断）
            recent10 = query("""
                SELECT close FROM daily_prices
                WHERE code = ? AND trade_date <= ?
                ORDER BY trade_date DESC LIMIT 10
            """, (code, d_str))
            ma10 = np.mean([r[0] for r in recent10]) if len(recent10) >= 10 else ma5
            ma_cross = 1 if ma5 > ma10 else 0

            # 量比
            vol_rows = query("""
                SELECT AVG(volume) FROM daily_prices
                WHERE code = ? AND trade_date < ?
                ORDER BY trade_date DESC LIMIT 5
            """, (code, d_str))
            avg_vol = vol_rows[0][0] if vol_rows and vol_rows[0][0] else volume
            vol_ratio_day = volume / avg_vol if avg_vol > 0 else 1.0

            # 回撤率
            drawdown = (peak_return - ret_from_buy) if peak_return > ret_from_buy else 0

            m = {
                "code": code, "name": name,
                "day": j + 1, "date": d_str,
                "close": close,
                "ret_from_buy": ret_from_buy,
                "peak_return": peak_return,
                "drawdown": drawdown,
                "market_ret": market_ret or 0,
                "advance_ratio": advance_ratio,
                "ma5_pos": ma5_pos,
                "ma_cross": ma_cross,
                "vol_ratio": vol_ratio_day,
                "final_ret": final_ret,
            }
            all_metrics.append(m)

        # 打印每日指标
        logger.info(f"买入日: {buy_date} | 买入价: {buy_price:.2f}")
        logger.info(f"{'日':>3} {'价格':>8} {'收益%':>7} {'最高%':>7} {'回撤%':>6} {'MA5位':>6} {'量比':>5} {'市场%':>7} {'上涨%':>6}")
        for m in days[:10]:
            idx = next((i for i, x in enumerate(all_metrics)
                       if x['code'] == code and x['day'] == m[0]), -1)
            if idx >= 0:
                data = all_metrics[idx]
                flag = ""
                if data['ma5_pos'] < 0.98: flag += "MA5↓"
                if data['advance_ratio'] < 40: flag += "情绪↓"
                if data['vol_ratio'] < 0.7: flag += "量减"
                logger.info(f"{data['day']:>3} {data['close']:>8.2f} {data['ret_from_buy']:>+7.1f} "
                           f"{data['peak_return']:>+7.1f} {data['drawdown']:>+6.1f} "
                           f"{data['ma5_pos']:>6.3f} {data['vol_ratio']:>5.2f} "
                           f"{data['market_ret']:>+7.1f} {data['advance_ratio']:>6.0f}% {flag}")

    # ================================================================
    # 全局分析
    # ================================================================
    if not all_metrics:
        return

    logger.info("\n" + "=" * 60)
    logger.info("全局人气溃散阈值分析")
    logger.info("=" * 60)

    df_data = {k: [m[k] for m in all_metrics] for k in all_metrics[0].keys()}
    n = len(df_data['day'])

    logger.info(f"总数据点: {n}")

    # 1. MA5位置分析
    logger.info("\n1. MA5位置（价格/MA5）与收益的关系:")
    for t in [0.95, 0.97, 0.99, 1.00, 1.01, 1.02]:
        below = [m['ret_from_buy'] for m in all_metrics if m['ma5_pos'] < t]
        above = [m['ret_from_buy'] for m in all_metrics if m['ma5_pos'] >= t]
        if below and above:
            logger.info(f"  MA5位置 < {t:.2f}: 均值={np.mean(below):+.2f}% ({len(below)}点) "
                       f"| >= {t:.2f}: 均值={np.mean(above):+.2f}% ({len(above)}点)")

    # 2. 上涨占比分析
    logger.info("\n2. 上涨占比（板块情绪）与收益的关系:")
    for t in [30, 40, 50, 60, 70]:
        below = [m['ret_from_buy'] for m in all_metrics if m['advance_ratio'] < t]
        above = [m['ret_from_buy'] for m in all_metrics if m['advance_ratio'] >= t]
        if below and above:
            logger.info(f"  上涨占比 < {t}%: 均值={np.mean(below):+.2f}% ({len(below)}点) "
                       f"| >= {t}%: 均值={np.mean(above):+.2f}% ({len(above)}点)")

    # 3. 量比分析
    logger.info("\n3. 量比（资金活跃度）与收益的关系:")
    for t in [0.5, 0.6, 0.7, 0.8, 0.9, 1.0]:
        below = [m['ret_from_buy'] for m in all_metrics if m['vol_ratio'] < t]
        above = [m['ret_from_buy'] for m in all_metrics if m['vol_ratio'] >= t]
        if below and above:
            logger.info(f"  量比 < {t:.1f}: 均值={np.mean(below):+.2f}% ({len(below)}点) "
                       f"| >= {t:.1f}: 均值={np.mean(above):+.2f}% ({len(above)}点)")

    # 4. 均线死叉分析
    logger.info("\n4. 均线死叉与收益的关系:")
    for val, label in [(0, "MA5<MA10(死叉)"), (1, "MA5>=MA10(多头)")]:
        subset = [m['ret_from_buy'] for m in all_metrics if m['ma_cross'] == val]
        if subset:
            logger.info(f"  {label}: 均值={np.mean(subset):+.2f}%, 样本={len(subset)}")

    # 5. 市场情绪分析
    logger.info("\n5. 市场整体涨幅（大盘情绪）与持仓收益的关系:")
    for t in [-2, -1, 0, 1, 2]:
        below = [m['ret_from_buy'] for m in all_metrics if m['market_ret'] < t]
        above = [m['ret_from_buy'] for m in all_metrics if m['market_ret'] >= t]
        if below and above:
            logger.info(f"  大盘涨幅 < {t}%: 均值={np.mean(below):+.2f}% ({len(below)}点) "
                       f"| >= {t}%: 均值={np.mean(above):+.2f}% ({len(above)}点)")

    # 6. 最高收益回撤
    logger.info("\n6. 最高收益回撤分析:")
    for t in [20, 30, 40, 50, 60]:
        subset = [m['ret_from_buy'] for m in all_metrics if m['drawdown'] > t]
        if subset:
            logger.info(f"  回撤 > {t}%: 均值={np.mean(subset):+.2f}%, 样本={len(subset)}")

    # 关键发现
    logger.info("\n" + "=" * 60)
    logger.info("【关键发现】人气溃散阈值:")
    logger.info("=" * 60)

    # 最有效的单一指标
    best_indicators = []

    # MA5位置
    ma5_groups = [(0.95, 0.99), (0.97, 1.00), (0.99, 1.00), (1.00, 1.01)]
    for lo, hi in ma5_groups:
        below = [m['ret_from_buy'] for m in all_metrics if lo <= m['ma5_pos'] < hi]
        if below and len(below) >= 3:
            best_indicators.append(("MA5位置" + str((lo, hi)), np.mean(below), len(below)))

    # 上涨占比
    for t in [30, 40, 50]:
        below = [m['ret_from_buy'] for m in all_metrics if m['advance_ratio'] < t]
        if below and len(below) >= 3:
            best_indicators.append((f"上涨占比<{t}%", np.mean(below), len(below)))

    # 量比
    for t in [0.5, 0.6, 0.7]:
        below = [m['ret_from_buy'] for m in all_metrics if m['vol_ratio'] < t]
        if below and len(below) >= 3:
            best_indicators.append((f"量比<{t}", np.mean(below), len(below)))

    # 排序输出
    best_indicators.sort(key=lambda x: x[1])
    logger.info("\n最有效的离场预警信号（按收益从低到高）:")
    for name, avg_ret, count in best_indicators:
        logger.info(f"  [{count}个样本] {name}: 平均收益 {avg_ret:+.2f}%")

    return all_metrics


# ================================================================
# 第三步：分析成功案例
# ================================================================
def analyze_success_cases():
    logger.info("\n" + "=" * 60)
    logger.info("第三步：分析成功案例 → 成功因子")
    logger.info("=" * 60)

    success_trades = [
        ("000592", "平潭发展", "2025-08-21", +26.7),
        ("601969", "海南矿业", "2025-10-17", +29.4),
    ]

    for code, name, buy_date, final_ret in success_trades:
        logger.info(f"\n{'='*50}")
        logger.info(f"成功案例: {code} {name} (买入:{buy_date}, 终收益:{final_ret}%)")
        logger.info(f"{'='*50}")

        days = query("""
            SELECT trade_date, close, volume, amount, pct_change
            FROM daily_prices
            WHERE code = ? AND trade_date >= ? AND trade_date <= ?
            ORDER BY trade_date
        """, (code, buy_date, str(date.fromisoformat(buy_date) + timedelta(days=60))))

        if not days:
            continue

        buy_row = query_one("""
            SELECT close FROM daily_prices WHERE code = ? AND trade_date = ?
        """, (code, buy_date))
        if not buy_row:
            continue
        buy_price = buy_row[0]

        logger.info(f"持仓期: {len(days)}天 | 买入价: {buy_price:.2f}")
        logger.info(f"{'日':>3} {'价格':>8} {'收益%':>7} {'MA5位':>6} {'量比':>5} {'市场%':>7} {'上涨%':>6}")

        for j, (d_str, close, volume, amount, pct_chg) in enumerate(days):
            ret_from_buy = (close - buy_price) / buy_price * 100

            market_row = query_one("""
                SELECT AVG(dp.pct_change) FROM daily_prices dp
                JOIN stocks s ON dp.code = s.code
                WHERE dp.trade_date = ?
                  AND s.total_market_cap > 200e8 AND s.total_market_cap < 400e8
                  AND dp.close > 0
            """, (d_str,))
            market_ret = market_row[0] if market_row else 0

            up_row = query_one("""
                SELECT COUNT(*) FROM daily_prices dp JOIN stocks s ON dp.code = s.code
                WHERE dp.trade_date = ?
                  AND s.total_market_cap > 200e8 AND s.total_market_cap < 400e8
                  AND dp.close > 0 AND dp.pct_change > 0
            """, (d_str,))
            total_row = query_one("""
                SELECT COUNT(*) FROM daily_prices dp JOIN stocks s ON dp.code = s.code
                WHERE dp.trade_date = ?
                  AND s.total_market_cap > 200e8 AND s.total_market_cap < 400e8
                  AND dp.close > 0
            """, (d_str,))
            up_count = up_row[0] if up_row else 0
            total_count = total_row[0] if total_row else 1
            advance_ratio = up_count / total_count * 100

            recent = query("""
                SELECT close FROM daily_prices WHERE code = ? AND trade_date <= ?
                ORDER BY trade_date DESC LIMIT 5
            """, (code, d_str))
            ma5 = np.mean([r[0] for r in recent]) if recent else close
            ma5_pos = close / ma5 if ma5 > 0 else 1.0

            vol_rows = query("""
                SELECT AVG(volume) FROM daily_prices
                WHERE code = ? AND trade_date < ?
                ORDER BY trade_date DESC LIMIT 5
            """, (code, d_str))
            avg_vol = vol_rows[0][0] if vol_rows and vol_rows[0][0] else volume
            vol_ratio = volume / avg_vol if avg_vol > 0 else 1.0

            flag = ""
            if j > 0 and ma5_pos < 0.98: flag += "MA5↓"
            if advance_ratio < 40: flag += "情绪↓"
            if vol_ratio < 0.7: flag += "量减"

            logger.info(f"{j+1:>3} {close:>8.2f} {ret_from_buy:>+7.1f} "
                        f"{ma5_pos:>6.3f} {vol_ratio:>5.2f} "
                        f"{market_ret:>+7.1f} {advance_ratio:>6.0f}% {flag}")


# ================================================================
# 第四步：测试不同离场信号组合
# ================================================================
def test_exit_signals():
    logger.info("\n" + "=" * 60)
    logger.info("第四步：测试离场信号组合")
    logger.info("=" * 60)

    # 获取评估日期
    rows = query("""
        SELECT DISTINCT trade_date FROM daily_prices
        WHERE trade_date BETWEEN '2024-11-26' AND '2026-05-22'
        ORDER BY trade_date
    """)
    eval_dates = [r[0] for r in rows][::5]

    # 收集85+分的买入信号
    all_signals = []
    for d_str in eval_dates:
        sector_rows = query("""
            SELECT DISTINCT s.sector_lv1 FROM stocks s
            WHERE s.sector_lv1 IS NOT NULL
              AND (s.is_delisted IS NULL OR s.is_delisted = 0)
              AND s.total_market_cap > 200e8 AND s.total_market_cap < 400e8
            LIMIT 10
        """)
        sectors = [r[0] for r in sector_rows]

        for sector in sectors[:3]:
            stock_rows = query("""
                SELECT s.code, s.name, s.total_market_cap, dp.close
                FROM stocks s
                JOIN daily_prices dp ON s.code = dp.code
                WHERE s.sector_lv1 = ? AND dp.trade_date = ?
                  AND s.total_market_cap > 200e8 AND s.total_market_cap < 400e8
                  AND (s.is_delisted IS NULL OR s.is_delisted = 0)
                  AND dp.close > 0
                ORDER BY dp.pct_change DESC
                LIMIT 3
            """, (sector, d_str))

            for i, (code, name, mkt_cap, close) in enumerate(stock_rows[:3]):
                history_rows = query("""
                    SELECT trade_date, close, volume FROM daily_prices
                    WHERE code = ? AND trade_date <= ?
                    ORDER BY trade_date DESC LIMIT 30
                """, (code, d_str))

                if len(history_rows) < 20:
                    continue

                closes = [h[1] for h in history_rows if h[1] is not None]
                vols = [h[2] for h in history_rows if h[2] is not None]

                if len(closes) < 20:
                    continue

                score = 0
                ma5 = np.mean(closes[:5])
                ma10 = np.mean(closes[:10])
                ma20 = np.mean(closes[:20])

                if close > ma5 > ma10 > ma20: score += 20
                elif ma5 > ma10 > ma20 and close > ma5: score += 12
                elif close > ma20: score += 5

                avg_vol = np.mean(vols[1:6]) if len(vols) >= 6 else np.mean(vols[1:])
                vol_ratio = vols[0] / avg_vol if avg_vol > 0 else 1.0
                if vol_ratio > 2.5: score += 18
                elif vol_ratio > 1.8: score += 10
                elif vol_ratio > 1.3: score += 4

                ret_5d = (closes[0] - closes[4]) / closes[4] * 100 if len(closes) >= 5 and closes[4] > 0 else 0
                if 3 <= ret_5d <= 7: score += 18
                elif 7 < ret_5d <= 12: score += 8
                elif ret_5d > 0: score += 3

                consecutive_up = 0
                for j in range(len(closes) - 1):
                    if closes[j] > closes[j + 1]:
                        consecutive_up += 1
                    else:
                        break
                if consecutive_up >= 4: score += 15
                elif consecutive_up >= 2: score += 6

                x = np.arange(20)
                y = np.array(closes[:20])
                slope = np.polyfit(x, y, 1)[0]
                trend_slope = slope / closes[0] * 100
                if trend_slope > 0.5: score += 18
                elif trend_slope > 0.2: score += 8

                score += max(0, 15 - i * 5)

                mkt_cap_yi = mkt_cap / 1e8
                if 200 <= mkt_cap_yi <= 350: score += 12
                elif 350 < mkt_cap_yi <= 400: score += 6

                if score >= 85:
                    all_signals.append({
                        "code": code, "name": name,
                        "buy_date": d_str, "buy_price": close,
                        "score": score
                    })

    logger.info(f"收集到 {len(all_signals)} 个买入信号")

    # 定义离场策略
    def make_exit_fn(ma5_thresh=None, adv_thresh=None, vol_thresh=None,
                     use_ma_cross=False, use_profit_take=None, use_stop_loss=None):
        def exit_fn(m):
            if use_profit_take and m['ret_from_buy'] >= use_profit_take:
                return True
            if use_stop_loss and m['ret_from_buy'] <= use_stop_loss:
                return True
            if ma5_thresh and m['ma5_pos'] < ma5_thresh:
                return True
            if adv_thresh and m['advance_ratio'] < adv_thresh:
                return True
            if vol_thresh and m['vol_ratio'] < vol_thresh:
                return True
            if use_ma_cross and m['ma_cross'] == 0:
                return True
            return False
        return exit_fn

    strategies = [
        ("原始死叉", make_exit_fn(use_ma_cross=True)),
        ("MA5<0.98", make_exit_fn(ma5_thresh=0.98)),
        ("MA5<0.99", make_exit_fn(ma5_thresh=0.99)),
        ("MA5<1.00", make_exit_fn(ma5_thresh=1.00)),
        ("MA5<1.01", make_exit_fn(ma5_thresh=1.01)),
        ("上涨<30%", make_exit_fn(adv_thresh=30)),
        ("上涨<40%", make_exit_fn(adv_thresh=40)),
        ("上涨<50%", make_exit_fn(adv_thresh=50)),
        ("量比<0.5", make_exit_fn(vol_thresh=0.5)),
        ("量比<0.7", make_exit_fn(vol_thresh=0.7)),
        ("量比<0.8", make_exit_fn(vol_thresh=0.8)),
        ("MA5<0.98+上涨<40%", make_exit_fn(ma5_thresh=0.98, adv_thresh=40)),
        ("MA5<0.98+量比<0.7", make_exit_fn(ma5_thresh=0.98, vol_thresh=0.7)),
        ("MA5<0.99+上涨<40%", make_exit_fn(ma5_thresh=0.99, adv_thresh=40)),
        ("MA5<1.00+上涨<40%", make_exit_fn(ma5_thresh=1.00, adv_thresh=40)),
        ("MA5<0.98+量比<0.8", make_exit_fn(ma5_thresh=0.98, vol_thresh=0.8)),
        ("MA5<1.00+量比<0.7", make_exit_fn(ma5_thresh=1.00, vol_thresh=0.7)),
        ("任意一人气溃散", make_exit_fn(ma5_thresh=0.98, adv_thresh=40, vol_thresh=0.7)),
        ("MA5<0.97", make_exit_fn(ma5_thresh=0.97)),
        ("MA5<0.96", make_exit_fn(ma5_thresh=0.96)),
        ("MA5<0.98+上涨<50%", make_exit_fn(ma5_thresh=0.98, adv_thresh=50)),
        ("MA5<1.00+量比<0.8", make_exit_fn(ma5_thresh=1.00, vol_thresh=0.8)),
        ("止损-10%", make_exit_fn(use_stop_loss=-10.0)),
        ("止损-8%", make_exit_fn(use_stop_loss=-8.0)),
        ("止损-5%", make_exit_fn(use_stop_loss=-5.0)),
        ("止盈15%+MA5<0.98", make_exit_fn(use_profit_take=15.0, ma5_thresh=0.98)),
        ("止盈20%+MA5<0.98", make_exit_fn(use_profit_take=20.0, ma5_thresh=0.98)),
        ("止盈20%+止损-8%", make_exit_fn(use_profit_take=20.0, use_stop_loss=-8.0)),
        ("止盈15%+止损-8%+MA5<0.98", make_exit_fn(
            use_profit_take=15.0, use_stop_loss=-8.0, ma5_thresh=0.98)),
    ]

    logger.info(f"\n测试 {len(all_signals)} 个信号 × {len(strategies)} 种离场策略")
    logger.info(f"{'策略':<35} {'交易':>5} {'胜率':>6} {'均收益':>7} {'最大亏':>7} {'总收益':>8}")
    logger.info("-" * 80)

    best = None
    best_score = -999

    for strategy_name, exit_fn in strategies:
        wins = losses = 0
        total_ret = 0.0
        max_loss = 0.0
        trade_count = 0

        for sig in all_signals:
            code = sig['code']
            buy_price = sig['buy_price']
            buy_date = sig['buy_date']

            # 获取持仓期每日数据
            days = query("""
                SELECT trade_date, close, volume, amount, pct_change
                FROM daily_prices
                WHERE code = ? AND trade_date >= ?
                ORDER BY trade_date
            """, (code, buy_date))

            exited = False
            for j, (d_str, close, volume, amount, pct_chg) in enumerate(days):
                ret = (close - buy_price) / buy_price * 100

                # 计算当日指标
                recent = query("""
                    SELECT close FROM daily_prices
                    WHERE code = ? AND trade_date <= ?
                    ORDER BY trade_date DESC LIMIT 5
                """, (code, d_str))
                ma5 = np.mean([r[0] for r in recent]) if recent else close
                ma5_pos = close / ma5 if ma5 > 0 else 1.0

                recent10 = query("""
                    SELECT close FROM daily_prices
                    WHERE code = ? AND trade_date <= ?
                    ORDER BY trade_date DESC LIMIT 10
                """, (code, d_str))
                ma10 = np.mean([r[0] for r in recent10]) if len(recent10) >= 10 else ma5
                ma_cross = 1 if ma5 > ma10 else 0

                up_row = query_one("""
                    SELECT COUNT(*) FROM daily_prices dp JOIN stocks s ON dp.code = s.code
                    WHERE dp.trade_date = ?
                      AND s.total_market_cap > 200e8 AND s.total_market_cap < 400e8
                      AND dp.close > 0 AND dp.pct_change > 0
                """, (d_str,))
                total_row = query_one("""
                    SELECT COUNT(*) FROM daily_prices dp JOIN stocks s ON dp.code = s.code
                    WHERE dp.trade_date = ?
                      AND s.total_market_cap > 200e8 AND s.total_market_cap < 400e8
                      AND dp.close > 0
                """, (d_str,))
                up_count = up_row[0] if up_row else 0
                total_count = total_row[0] if total_row else 1
                advance_ratio = up_count / total_count * 100

                vol_rows = query("""
                    SELECT AVG(volume) FROM daily_prices
                    WHERE code = ? AND trade_date < ?
                    ORDER BY trade_date DESC LIMIT 5
                """, (code, d_str))
                avg_vol = vol_rows[0][0] if vol_rows and vol_rows[0][0] else volume
                vol_ratio_today = volume / avg_vol if avg_vol > 0 else 1.0

                m = {
                    'day': j + 1,
                    'ret_from_buy': ret,
                    'ma5_pos': ma5_pos,
                    'ma_cross': ma_cross,
                    'advance_ratio': advance_ratio,
                    'vol_ratio': vol_ratio_today,
                }

                should_exit = exit_fn(m)
                if should_exit or j >= 49:
                    final_ret = ret
                    trade_count += 1
                    total_ret += final_ret
                    if final_ret > 0:
                        wins += 1
                    else:
                        losses += 1
                        if final_ret < max_loss:
                            max_loss = final_ret
                    exited = True
                    break

        if trade_count > 0:
            win_rate = wins / trade_count * 100
            avg_ret = total_ret / trade_count
            logger.info(f"{strategy_name:<35} {trade_count:>5} {win_rate:>6.1f}% "
                       f"{avg_ret:>+7.2f}% {max_loss:>+8.2f}% {total_ret:>+8.2f}%")

            # 综合评分 = 总收益 * 胜率（兼顾收益和稳定性）
            score_metric = total_ret * (win_rate / 100) if trade_count >= 5 else -999
            if score_metric > best_score:
                best_score = score_metric
                best = (strategy_name, trade_count, win_rate, avg_ret, max_loss, total_ret)

    logger.info("-" * 80)
    if best:
        logger.info(f"\n★ 最优策略: {best[0]}")
        logger.info(f"  交易{best[1]}笔, 胜率{best[2]:.1f}%, "
                   f"均收益{best[3]:+.2f}%, 最大亏{best[4]:+.2f}%, 总收益{best[5]:+.2f}%")

    return best


if __name__ == "__main__":
    print("=" * 60)
    print("低频交易引擎 Auto Research")
    print("目标: 找到成功因子 + 人气溃散阈值")
    print("=" * 60)

    # 第一步
    samples = analyze_score_distribution()

    # 第二步
    metrics = analyze_failure_cases()

    # 第三步
    analyze_success_cases()

    # 第四步
    best = test_exit_signals()

    print("\n" + "=" * 60)
    print("Auto Research 完成")
    print("=" * 60)
