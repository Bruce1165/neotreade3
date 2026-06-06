#!/usr/bin/env python3
"""
人气聚集/消散因子 Auto Research (咖啡杯柄形态启发)
==========================================================
核心逻辑：
1. 杯部形成 = 人气聚集（成交量/换手率放大）
2. 柄部形成 = 人气消散（成交量/换手率萎缩）
3. 突破确认 = 人气重新聚集（成交量再次放大）

研究目标：
- 找到最佳人气聚集周期（5/10/15/20天）
- 找到人气消散阈值（量比/换手率跌破多少）
- 找到人气与价格的最佳配合关系
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
# 人气因子计算
# ================================================================
def calculate_sentiment_factors(code, target_date, lookback_days=20):
    """
    计算股票的人气聚集/消散指标

    返回：
    - sentiment_score: 人气评分 (0-100)
    - accumulation_period: 聚集周期天数
    - distribution_period: 消散周期天数
    - turnover_trend: 换手率趋势
    - amount_trend: 成交额趋势
    - price_volume_divergence: 价量背离度
    """
    history = query("""
        SELECT trade_date, close, volume, amount, pct_change,
               (volume * close / (total_market_cap / close)) as turnover_rate
        FROM daily_prices dp
        JOIN stocks s ON dp.code = s.code
        WHERE dp.code = ? AND dp.trade_date <= ?
        ORDER BY trade_date DESC LIMIT ?
    """, (code, target_date, lookback_days + 10))

    if len(history) < lookback_days:
        return None

    # 提取数据（倒序，最近在前）
    dates = [h[0] for h in history]
    closes = [h[1] for h in history]
    volumes = [h[2] for h in history]
    amounts = [h[3] for h in history]
    pct_changes = [h[4] for h in history]
    turnover_rates = [h[5] if h[5] else 0 for h in history]

    # 1. 计算N日平均换手率、成交额
    avg_turnover_5d = np.mean(turnover_rates[1:6]) if len(turnover_rates) >= 6 else np.mean(turnover_rates[1:])
    avg_turnover_10d = np.mean(turnover_rates[1:11]) if len(turnover_rates) >= 11 else avg_turnover_5d
    avg_turnover_20d = np.mean(turnover_rates[1:21]) if len(turnover_rates) >= 21 else avg_turnover_10d

    avg_amount_5d = np.mean(amounts[1:6]) if len(amounts) >= 6 else np.mean(amounts[1:])
    avg_amount_10d = np.mean(amounts[1:11]) if len(amounts) >= 11 else avg_amount_5d
    avg_amount_20d = np.mean(amounts[1:21]) if len(amounts) >= 21 else avg_amount_10d

    # 2. 今日相对N日平均的倍数（人气强度）
    turnover_ratio_5d = turnover_rates[0] / avg_turnover_5d if avg_turnover_5d > 0 else 1.0
    turnover_ratio_10d = turnover_rates[0] / avg_turnover_10d if avg_turnover_10d > 0 else 1.0
    turnover_ratio_20d = turnover_rates[0] / avg_turnover_20d if avg_turnover_20d > 0 else 1.0

    amount_ratio_5d = amounts[0] / avg_amount_5d if avg_amount_5d > 0 else 1.0
    amount_ratio_10d = amounts[0] / avg_amount_10d if avg_amount_10d > 0 else 1.0
    amount_ratio_20d = amounts[0] / avg_amount_20d if avg_amount_20d > 0 else 1.0

    # 3. 寻找"杯柄"结构：先放量（杯）→ 缩量（柄）→ 再放量（突破）
    # 检测最近N天内是否存在明显的"放量-缩量-放量"结构

    # 3.1 找杯部：连续3天以上放量（量比>1.5）
    cup_period = 0
    cup_max_ratio = 1.0
    for i in range(min(15, len(volumes) - 3)):
        window_vols = volumes[i:i+3]
        window_avg = np.mean(volumes[i+3:i+8]) if len(volumes) > i+8 else np.mean(volumes[i+3:])
        if window_avg > 0:
            ratios = [v / window_avg for v in window_vols]
            if all(r > 1.5 for r in ratios):
                cup_period = i
                cup_max_ratio = max(ratios)
                break

    # 3.2 找柄部：杯部之后连续2-5天缩量（量比<0.8）
    handle_period = 0
    handle_min_ratio = 1.0
    if cup_period > 0:
        for i in range(cup_period + 3, min(cup_period + 10, len(volumes) - 2)):
            window_vols = volumes[i:i+3]
            window_avg = np.mean(volumes[i-3:i]) if i >= 3 else np.mean(volumes[:i])
            if window_avg > 0:
                ratios = [v / window_avg for v in window_vols]
                if all(r < 0.8 for r in ratios):
                    handle_period = i - cup_period
                    handle_min_ratio = min(ratios)
                    break

    # 3.3 找突破：柄部之后再次放量（量比>1.3）
    breakout = False
    breakout_ratio = 1.0
    if handle_period > 0:
        breakout_idx = cup_period + 3 + handle_period
        if breakout_idx < len(volumes):
            handle_avg = np.mean(volumes[cup_period+3:breakout_idx]) if breakout_idx > cup_period+3 else np.mean(volumes[cup_period+3:cup_period+6])
            if handle_avg > 0:
                breakout_ratio = volumes[breakout_idx] / handle_avg
                breakout = breakout_ratio > 1.3

    # 4. 计算价量背离度
    # 价格上涨但成交量下降 = 背离（负值）
    # 价格上涨且成交量上升 = 确认（正值）
    price_change_5d = (closes[0] - closes[4]) / closes[4] * 100 if len(closes) >= 5 and closes[4] > 0 else 0
    vol_change_5d = (volumes[0] - np.mean(volumes[1:6])) / np.mean(volumes[1:6]) * 100 if len(volumes) >= 6 else 0
    divergence = price_change_5d - vol_change_5d * 0.5  # 价格变化减去成交量变化的加权

    # 5. 综合人气评分
    sentiment_score = 0

    # 基础分：换手率倍数
    if turnover_ratio_5d > 2.0: sentiment_score += 20
    elif turnover_ratio_5d > 1.5: sentiment_score += 15
    elif turnover_ratio_5d > 1.2: sentiment_score += 10
    elif turnover_ratio_5d > 1.0: sentiment_score += 5

    # 成交额倍数
    if amount_ratio_5d > 2.0: sentiment_score += 20
    elif amount_ratio_5d > 1.5: sentiment_score += 15
    elif amount_ratio_5d > 1.2: sentiment_score += 10
    elif amount_ratio_5d > 1.0: sentiment_score += 5

    # 杯柄结构加分
    if cup_period > 0 and handle_period > 0 and breakout:
        sentiment_score += 25
    elif cup_period > 0 and handle_period > 0:
        sentiment_score += 15
    elif cup_period > 0:
        sentiment_score += 10

    # 趋势一致性加分
    if price_change_5d > 0 and vol_change_5d > 0:
        sentiment_score += 15  # 量价齐升
    elif price_change_5d > 0 and vol_change_5d < 0:
        sentiment_score -= 10  # 量价背离（减分）

    return {
        'sentiment_score': min(100, max(0, sentiment_score)),
        'turnover_ratio_5d': turnover_ratio_5d,
        'turnover_ratio_10d': turnover_ratio_10d,
        'turnover_ratio_20d': turnover_ratio_20d,
        'amount_ratio_5d': amount_ratio_5d,
        'amount_ratio_10d': amount_ratio_10d,
        'amount_ratio_20d': amount_ratio_20d,
        'cup_period': cup_period,
        'handle_period': handle_period,
        'breakout': breakout,
        'breakout_ratio': breakout_ratio,
        'price_change_5d': price_change_5d,
        'vol_change_5d': vol_change_5d,
        'divergence': divergence,
    }


# ================================================================
# 第一轮：测试不同人气聚集周期
# ================================================================
def round1_accumulation_period():
    """第一轮：测试不同人气聚集周期对收益的影响"""
    logger.info("=" * 70)
    logger.info("第一轮：测试人气聚集周期 (5/10/15/20天)")
    logger.info("=" * 70)

    # 获取评估日期
    rows = query("""
        SELECT DISTINCT trade_date FROM daily_prices
        WHERE trade_date BETWEEN '2024-11-26' AND '2026-05-22'
        ORDER BY trade_date
    """)
    eval_dates = [r[0] for r in rows][::5]

    results_by_period = defaultdict(lambda: {'trades': [], 'returns': []})

    for period in [5, 10, 15, 20]:
        logger.info(f"\n--- 测试周期: {period}天 ---")

        for d_str in eval_dates[:20]:  # 取前20个评估点加速
            # 获取候选股票
            stock_rows = query("""
                SELECT s.code, s.name, s.total_market_cap, dp.close
                FROM stocks s
                JOIN daily_prices dp ON s.code = dp.code
                WHERE dp.trade_date = ?
                  AND s.total_market_cap > 200e8 AND s.total_market_cap < 400e8
                  AND (s.is_delisted IS NULL OR s.is_delisted = 0)
                  AND dp.close > 0
                ORDER BY dp.pct_change DESC
                LIMIT 10
            """, (d_str,))

            for code, name, mkt_cap, close in stock_rows:
                sentiment = calculate_sentiment_factors(code, d_str, period)
                if not sentiment:
                    continue

                # 模拟买入后30天收益
                future_rows = query("""
                    SELECT close FROM daily_prices
                    WHERE code = ? AND trade_date > ?
                    ORDER BY trade_date LIMIT 30
                """, (code, d_str))

                if len(future_rows) >= 20:
                    future_close = future_rows[19][0]  # 20天后价格
                    ret_20d = (future_close - close) / close * 100

                    results_by_period[period]['trades'].append({
                        'code': code,
                        'date': d_str,
                        'sentiment_score': sentiment['sentiment_score'],
                        'turnover_ratio': sentiment['turnover_ratio_5d'],
                        'cup_handle': sentiment['cup_period'] > 0 and sentiment['handle_period'] > 0,
                        'ret_20d': ret_20d,
                    })
                    results_by_period[period]['returns'].append(ret_20d)

        # 统计结果
        trades = results_by_period[period]['trades']
        returns = results_by_period[period]['returns']
        if trades:
            high_sentiment = [t for t in trades if t['sentiment_score'] >= 60]
            cup_handle_trades = [t for t in trades if t['cup_handle']]

            logger.info(f"  总样本: {len(trades)}")
            logger.info(f"  平均20天收益: {np.mean(returns):+.2f}%")
            logger.info(f"  高人气(≥60分)样本: {len(high_sentiment)}, 平均收益: {np.mean([t['ret_20d'] for t in high_sentiment]):+.2f}%" if high_sentiment else "  高人气样本: 0")
            logger.info(f"  杯柄结构样本: {len(cup_handle_trades)}, 平均收益: {np.mean([t['ret_20d'] for t in cup_handle_trades]):+.2f}%" if cup_handle_trades else "  杯柄结构样本: 0")

    return results_by_period


# ================================================================
# 第二轮：测试人气消散阈值
# ================================================================
def round2_distribution_threshold():
    """第二轮：测试人气消散的最佳卖出阈值"""
    logger.info("\n" + "=" * 70)
    logger.info("第二轮：测试人气消散阈值")
    logger.info("=" * 70)

    # 获取所有历史交易（模拟买入后跟踪）
    rows = query("""
        SELECT DISTINCT trade_date FROM daily_prices
        WHERE trade_date BETWEEN '2024-11-26' AND '2026-05-22'
        ORDER BY trade_date
    """)
    eval_dates = [r[0] for r in rows][::10]

    # 测试不同阈值
    thresholds = {
        '量比<0.5': 0.5,
        '量比<0.6': 0.6,
        '量比<0.7': 0.7,
        '量比<0.8': 0.8,
        '换手率<0.5倍': 0.5,
        '换手率<0.6倍': 0.6,
        '成交额<0.5倍': 0.5,
        '成交额<0.6倍': 0.6,
    }

    results = defaultdict(list)

    for d_str in eval_dates[:15]:
        # 获取高人气股票
        stock_rows = query("""
            SELECT s.code, s.name, s.total_market_cap, dp.close, dp.volume, dp.amount
            FROM stocks s
            JOIN daily_prices dp ON s.code = dp.code
            WHERE dp.trade_date = ?
              AND s.total_market_cap > 200e8 AND s.total_market_cap < 400e8
              AND dp.close > 0
            ORDER BY dp.amount DESC
            LIMIT 5
        """, (d_str,))

        for code, name, mkt_cap, buy_price, buy_vol, buy_amt in stock_rows:
            # 获取后续10天数据
            future_rows = query("""
                SELECT trade_date, close, volume, amount
                FROM daily_prices
                WHERE code = ? AND trade_date > ?
                ORDER BY trade_date LIMIT 10
            """, (code, d_str))

            if len(future_rows) < 5:
                continue

            # 计算每日指标
            for i, (f_date, f_close, f_vol, f_amt) in enumerate(future_rows):
                day = i + 1
                ret = (f_close - buy_price) / buy_price * 100

                # 计算量比、换手率比、成交额比
                vol_ratio = f_vol / buy_vol if buy_vol > 0 else 1.0
                amt_ratio = f_amt / buy_amt if buy_amt > 0 else 1.0

                # 测试各阈值
                for name_thresh, thresh_val in thresholds.items():
                    if '量比' in name_thresh and vol_ratio < thresh_val:
                        results[name_thresh].append({
                            'day': day, 'ret': ret, 'ratio': vol_ratio,
                            'triggered': True
                        })
                    elif '成交额' in name_thresh and amt_ratio < thresh_val:
                        results[name_thresh].append({
                            'day': day, 'ret': ret, 'ratio': amt_ratio,
                            'triggered': True
                        })

    # 分析结果
    logger.info("\n各阈值触发后的平均收益:")
    for name_thresh, data in results.items():
        if data:
            avg_ret = np.mean([d['ret'] for d in data])
            avg_day = np.mean([d['day'] for d in data])
            logger.info(f"  {name_thresh}: 触发后平均收益 {avg_ret:+.2f}%, 平均天数 {avg_day:.1f}天, 样本 {len(data)}")

    return results


# ================================================================
# 第三轮：测试人气与价格的背离/确认
# ================================================================
def round3_price_volume_divergence():
    """第三轮：测试价量关系对收益的影响"""
    logger.info("\n" + "=" * 70)
    logger.info("第三轮：测试价量背离/确认")
    logger.info("=" * 70)

    rows = query("""
        SELECT DISTINCT trade_date FROM daily_prices
        WHERE trade_date BETWEEN '2024-11-26' AND '2026-05-22'
        ORDER BY trade_date
    """)
    eval_dates = [r[0] for r in rows][::5]

    patterns = {
        '量价齐升': [],
        '量价背离(价涨量跌)': [],
        '量价齐跌': [],
        '价跌量升': [],
    }

    for d_str in eval_dates[:20]:
        stock_rows = query("""
            SELECT s.code, dp.close
            FROM stocks s
            JOIN daily_prices dp ON s.code = dp.code
            WHERE dp.trade_date = ?
              AND s.total_market_cap > 200e8 AND s.total_market_cap < 400e8
              AND dp.close > 0
            ORDER BY dp.pct_change DESC
            LIMIT 10
        """, (d_str,))

        for code, close in stock_rows:
            # 获取5日历史
            hist = query("""
                SELECT close, volume, amount FROM daily_prices
                WHERE code = ? AND trade_date <= ?
                ORDER BY trade_date DESC LIMIT 6
            """, (code, d_str))

            if len(hist) < 6:
                continue

            closes = [h[0] for h in hist]
            vols = [h[1] for h in hist]
            amts = [h[2] for h in hist]

            price_change = (closes[0] - closes[5]) / closes[5] * 100 if closes[5] > 0 else 0
            vol_change = (vols[0] - np.mean(vols[1:])) / np.mean(vols[1:]) * 100 if np.mean(vols[1:]) > 0 else 0

            # 分类
            if price_change > 2 and vol_change > 20:
                pattern = '量价齐升'
            elif price_change > 2 and vol_change < -10:
                pattern = '量价背离(价涨量跌)'
            elif price_change < -2 and vol_change < -10:
                pattern = '量价齐跌'
            elif price_change < -2 and vol_change > 20:
                pattern = '价跌量升'
            else:
                continue

            # 获取未来20天收益
            future = query("""
                SELECT close FROM daily_prices
                WHERE code = ? AND trade_date > ?
                ORDER BY trade_date LIMIT 20
            """, (code, d_str))

            if len(future) >= 20:
                ret_20d = (future[19][0] - close) / close * 100
                patterns[pattern].append(ret_20d)

    logger.info("\n各价量模式20天后的平均收益:")
    for pattern, returns in patterns.items():
        if returns:
            logger.info(f"  {pattern}: {np.mean(returns):+.2f}% (样本{len(returns)})")

    return patterns


# ================================================================
# 主函数
# ================================================================
if __name__ == "__main__":
    print("=" * 70)
    print("人气聚集/消散因子 Auto Research")
    print("咖啡杯柄形态启发：放量(杯)→缩量(柄)→再放量(突破)")
    print("=" * 70)

    # 第一轮
    r1 = round1_accumulation_period()

    # 第二轮
    r2 = round2_distribution_threshold()

    # 第三轮
    r3 = round3_price_volume_divergence()

    print("\n" + "=" * 70)
    print("三轮研究完成，准备整合最优参数")
    print("=" * 70)
