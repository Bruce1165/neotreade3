#!/usr/bin/env python3
"""
反推法研究：找出50个交易日内涨幅最大的股票，分析共性
==========================================================
步骤：
1. 遍历所有股票，计算任意起点后50个交易日的最大涨幅
2. 找出涨幅TOP50的股票-起点组合
3. 分析这些牛股的共同特征：
   - 买入时的人气状态（成交额/换手率）
   - 技术形态（杯柄结构？均线排列？）
   - 板块地位（龙头/中军？）
   - 市值范围
   - 价格位置（相对前期高低点）
4. 归纳成功因子，优化评分体系
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
# 第一步：找出50个交易日内涨幅最大的股票
# ================================================================
def find_top_performers():
    """找出50个交易日内涨幅最大的股票"""
    logger.info("=" * 70)
    logger.info("第一步：扫描50个交易日最大涨幅")
    logger.info("=" * 70)

    # 获取所有交易日
    rows = query("""
        SELECT DISTINCT trade_date FROM daily_prices
        WHERE trade_date BETWEEN '2024-11-26' AND '2025-12-31'
        ORDER BY trade_date
    """)
    all_dates = [r[0] for r in rows]
    logger.info(f"总交易日数: {len(all_dates)}")

    # 获取所有符合条件的股票（市值200-400亿）
    stock_rows = query("""
        SELECT DISTINCT code FROM stocks
        WHERE total_market_cap > 200e8 AND total_market_cap < 400e8
          AND (is_delisted IS NULL OR is_delisted = 0)
    """)
    all_stocks = [r[0] for r in stock_rows]
    logger.info(f"符合条件的股票数: {len(all_stocks)}")

    # 存储所有50日涨幅数据
    all_performers = []

    # 每只股票计算
    for idx, code in enumerate(all_stocks[:500]):  # 先取前500只加速
        if idx % 100 == 0:
            logger.info(f"处理第 {idx+1}/{min(500, len(all_stocks))} 只股票...")

        # 获取该股票所有交易日数据
        price_rows = query("""
            SELECT trade_date, close, volume, amount, pct_change
            FROM daily_prices
            WHERE code = ? AND trade_date BETWEEN '2024-11-26' AND '2026-05-22'
            ORDER BY trade_date
        """, (code,))

        if len(price_rows) < 60:  # 需要至少60天数据
            continue

        # 计算每个起点后50天的涨幅
        for i in range(len(price_rows) - 50):
            start_date = price_rows[i][0]
            start_price = price_rows[i][1]
            start_vol = price_rows[i][2]
            start_amt = price_rows[i][3]

            # 50天后的价格
            end_price = price_rows[i + 50][1]
            if end_price is None or start_price is None or start_price == 0:
                continue
            prices_50d = [r[1] for r in price_rows[i:i+51] if r[1] is not None]
            if not prices_50d:
                continue
            max_price = max(prices_50d)

            # 计算涨幅
            ret_50d = (end_price - start_price) / start_price * 100
            max_ret_50d = (max_price - start_price) / start_price * 100

            # 只记录涨幅>30%的
            if ret_50d > 30:
                all_performers.append({
                    'code': code,
                    'start_date': start_date,
                    'start_price': start_price,
                    'end_price': end_price,
                    'max_price': max_price,
                    'ret_50d': ret_50d,
                    'max_ret_50d': max_ret_50d,
                    'start_vol': start_vol,
                    'start_amt': start_amt,
                })

    # 按50日涨幅排序，取TOP50
    all_performers.sort(key=lambda x: x['ret_50d'], reverse=True)
    top50 = all_performers[:50]

    logger.info(f"\n找到 {len(all_performers)} 个涨幅>30%的案例")
    logger.info(f"TOP50 最小涨幅: {top50[-1]['ret_50d']:.1f}%")
    logger.info(f"TOP50 最大涨幅: {top50[0]['ret_50d']:.1f}%")

    return top50


# ================================================================
# 第二步：分析TOP50牛股的共同特征
# ================================================================
def analyze_winner_characteristics(top50):
    """分析牛股的共同特征"""
    logger.info("\n" + "=" * 70)
    logger.info("第二步：分析TOP50牛股的共同特征")
    logger.info("=" * 70)

    characteristics = {
        'price_position': [],  # 价格位置（相对20日高低点）
        'volume_ratio': [],    # 成交量比（相对5日平均）
        'amount_ratio': [],    # 成交额比（相对10日平均）
        'turnover_rate': [],   # 换手率
        'ma_alignment': [],    # 均线多头排列
        'consecutive_up': [],  # 连涨天数
        'market_cap': [],      # 市值
        'sector_rank': [],     # 板块内排名
        'cup_handle': [],      # 杯柄结构
        'volatility': [],      # 波动率
    }

    for winner in top50:
        code = winner['code']
        start_date = winner['start_date']
        start_price = winner['start_price']

        # 获取买入前30天数据
        hist = query("""
            SELECT trade_date, close, volume, amount
            FROM daily_prices
            WHERE code = ? AND trade_date <= ?
            ORDER BY trade_date DESC LIMIT 30
        """, (code, start_date))

        if len(hist) < 20:
            continue

        closes = [h[1] for h in reversed(hist) if h[1] is not None]  # 正序
        vols = [h[2] for h in reversed(hist) if h[2] is not None]
        amts = [h[3] for h in reversed(hist) if h[3] is not None]

        if len(closes) < 20 or len(vols) < 6 or len(amts) < 11:
            continue

        # 1. 价格位置（相对20日区间）
        high_20 = max(closes[-20:])
        low_20 = min(closes[-20:])
        price_position = (start_price - low_20) / (high_20 - low_20) * 100 if high_20 > low_20 else 50
        characteristics['price_position'].append(price_position)

        # 2. 成交量比
        avg_vol_5d = np.mean(vols[-6:-1])
        vol_ratio = vols[-1] / avg_vol_5d if avg_vol_5d > 0 else 1.0
        characteristics['volume_ratio'].append(vol_ratio)

        # 3. 成交额比
        avg_amt_10d = np.mean(amts[-11:-1])
        amt_ratio = amts[-1] / avg_amt_10d if avg_amt_10d > 0 else 1.0
        characteristics['amount_ratio'].append(amt_ratio)

        # 4. 换手率（近似）
        mkt_cap_row = query_one("SELECT total_market_cap FROM stocks WHERE code = ?", (code,))
        if mkt_cap_row:
            mkt_cap = mkt_cap_row[0]
            turnover = (vols[-1] * start_price) / mkt_cap * 100
            characteristics['turnover_rate'].append(turnover)

        # 5. 均线多头排列
        ma5 = np.mean(closes[-5:])
        ma10 = np.mean(closes[-10:])
        ma20 = np.mean(closes[-20:])
        alignment = 1 if start_price > ma5 > ma10 > ma20 else 0
        characteristics['ma_alignment'].append(alignment)

        # 6. 连涨天数
        consecutive = 0
        for i in range(len(closes)-1, 0, -1):
            if closes[i] > closes[i-1]:
                consecutive += 1
            else:
                break
        characteristics['consecutive_up'].append(consecutive)

        # 7. 市值
        if mkt_cap_row:
            characteristics['market_cap'].append(mkt_cap / 1e8)

        # 8. 板块内排名
        sector_row = query_one("SELECT sector_lv1 FROM stocks WHERE code = ?", (code,))
        if sector_row:
            sector = sector_row[0]
            sector_stocks = query("""
                SELECT s.code, dp.pct_change
                FROM stocks s JOIN daily_prices dp ON s.code = dp.code
                WHERE s.sector_lv1 = ? AND dp.trade_date = ?
                  AND s.total_market_cap > 200e8 AND s.total_market_cap < 400e8
                ORDER BY dp.pct_change DESC
            """, (sector, start_date))
            rank = next((i for i, (c, _) in enumerate(sector_stocks) if c == code), 99)
            characteristics['sector_rank'].append(rank)

        # 9. 杯柄结构检测
        # 简化版：先放量(>1.5倍3天) -> 后缩量(<0.8倍3天) -> 再放量(>1.3倍)
        cup = 0
        handle = 0
        breakout = 0

        # 找杯部（最近10天内连续3天放量）
        for i in range(len(vols)-10, len(vols)-5):
            if i >= 3:
                avg_before = np.mean(vols[i-3:i])
                if avg_before > 0 and all(vols[j] / avg_before > 1.5 for j in range(i, min(i+3, len(vols)))):
                    cup = i
                    break

        # 找柄部（杯部后缩量）
        if cup > 0:
            for i in range(cup+3, min(cup+8, len(vols)-2)):
                avg_cup = np.mean(vols[cup:cup+3])
                if avg_cup > 0 and all(vols[j] / avg_cup < 0.8 for j in range(i, min(i+3, len(vols)))):
                    handle = i
                    break

        # 找突破（柄部后再放量）
        if handle > 0 and len(vols) > handle + 1:
            avg_handle = np.mean(vols[handle:handle+3]) if handle+3 <= len(vols) else np.mean(vols[handle:])
            if avg_handle > 0 and vols[-1] / avg_handle > 1.3:
                breakout = 1

        characteristics['cup_handle'].append(1 if cup > 0 and handle > 0 and breakout else 0)

        # 10. 波动率（20日标准差）
        volatility = np.std(closes[-20:]) / np.mean(closes[-20:]) * 100 if len(closes) >= 20 else 0
        characteristics['volatility'].append(volatility)

    # 输出统计结果
    logger.info("\n【TOP50牛股特征统计】")
    logger.info("-" * 50)

    for key, values in characteristics.items():
        if values:
            logger.info(f"{key}:")
            logger.info(f"  均值={np.mean(values):.2f}, 中位数={np.median(values):.2f}")
            logger.info(f"  25分位={np.percentile(values, 25):.2f}, 75分位={np.percentile(values, 75):.2f}")

    # 关键发现
    logger.info("\n【关键发现】")
    logger.info("-" * 50)

    # 价格位置分布
    pp_low = sum(1 for p in characteristics['price_position'] if p < 50)
    pp_high = sum(1 for p in characteristics['price_position'] if p > 80)
    logger.info(f"价格位置: {pp_low}只在50%以下(低位启动), {pp_high}只在80%以上(高位追涨)")

    # 成交量分布
    vr_high = sum(1 for v in characteristics['volume_ratio'] if v > 2.0)
    vr_med = sum(1 for v in characteristics['volume_ratio'] if 1.0 < v <= 2.0)
    logger.info(f"成交量比: {vr_high}只>2倍(高人气), {vr_med}只1-2倍(温和放量)")

    # 成交额分布
    ar_high = sum(1 for a in characteristics['amount_ratio'] if a > 2.0)
    logger.info(f"成交额比: {ar_high}只>2倍(10日均)")

    # 均线多头排列
    ma_pct = sum(characteristics['ma_alignment']) / len(characteristics['ma_alignment']) * 100
    logger.info(f"均线多头排列: {ma_pct:.0f}%")

    # 杯柄结构
    cup_pct = sum(characteristics['cup_handle']) / len(characteristics['cup_handle']) * 100
    logger.info(f"杯柄结构: {cup_pct:.0f}%")

    # 板块排名
    rank_top3 = sum(1 for r in characteristics['sector_rank'] if r < 3)
    logger.info(f"板块排名前3: {rank_top3}只 ({rank_top3/len(characteristics['sector_rank'])*100:.0f}%)")

    return characteristics


# ================================================================
# 第三步：输出优化建议
# ================================================================
def generate_optimization_suggestions(characteristics):
    """基于反推结果生成优化建议"""
    logger.info("\n" + "=" * 70)
    logger.info("第三步：基于反推结果的优化建议")
    logger.info("=" * 70)

    suggestions = []

    # 1. 价格位置
    pp_median = np.median(characteristics['price_position'])
    if pp_median < 60:
        suggestions.append(f"1. 价格位置: 牛股多在相对低位启动(中位数{pp_median:.0f}%), 建议增加'价格位置<60%'的加分项")

    # 2. 成交量
    vr_median = np.median(characteristics['volume_ratio'])
    suggestions.append(f"2. 成交量: 牛股启动时量比中位数{vr_median:.1f}, 建议将'量比>2'的权重提高到15分")

    # 3. 成交额
    ar_median = np.median(characteristics['amount_ratio'])
    suggestions.append(f"3. 成交额: 牛股启动时成交额比中位数{ar_median:.1f}, 建议'成交额比>2'权重15分")

    # 4. 均线
    ma_pct = sum(characteristics['ma_alignment']) / len(characteristics['ma_alignment']) * 100
    suggestions.append(f"4. 均线: {ma_pct:.0f}%牛股有多头排列, 建议维持'均线多头排列'20分权重")

    # 5. 杯柄结构
    cup_pct = sum(characteristics['cup_handle']) / len(characteristics['cup_handle']) * 100
    if cup_pct > 30:
        suggestions.append(f"5. 杯柄结构: {cup_pct:.0f}%牛股有杯柄形态, 建议增加'杯柄结构'15分专项评分")

    # 6. 板块排名
    rank_top3_pct = sum(1 for r in characteristics['sector_rank'] if r < 3) / len(characteristics['sector_rank']) * 100
    suggestions.append(f"6. 板块地位: {rank_top3_pct:.0f}%是板块前3, 建议'板块排名前3'权重12分")

    # 7. 市值
    mc_median = np.median(characteristics['market_cap'])
    suggestions.append(f"7. 市值: 牛股中位数{mc_median:.0f}亿, 建议维持200-350亿最优区间")

    for s in suggestions:
        logger.info(s)

    return suggestions


# ================================================================
# 主函数
# ================================================================
if __name__ == "__main__":
    print("=" * 70)
    print("反推法研究：找出50日涨幅最大的股票，分析共性")
    print("=" * 70)

    # 第一步：找出TOP50
    top50 = find_top_performers()

    # 第二步：分析特征
    if top50:
        characteristics = analyze_winner_characteristics(top50)

        # 第三步：生成建议
        suggestions = generate_optimization_suggestions(characteristics)

    print("\n" + "=" * 70)
    print("反推法研究完成")
    print("=" * 70)
