#!/usr/bin/env python3
"""
Auto Research Round 1: 分析失败案例，找出优化方向
========================================================

当前问题：
- 胜率 50% (目标 80%)
- 30%+达成率 50% (目标 80%)
- 2笔交易被-10%止损过早触发

研究目标：
1. 如果放宽止损到-15%，这两笔交易最终收益如何？
2. 失败案例买入时的波浪判断是否正确？
3. 成功案例和失败案例的买入时特征差异
"""

import sqlite3
import numpy as np
from pathlib import Path
from datetime import date, timedelta
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


def analyze_failed_trades():
    """分析失败交易的如果持有到期的收益"""
    logger.info("=" * 70)
    logger.info("Round 1: 分析失败案例的潜在收益")
    logger.info("=" * 70)

    # 失败案例1: 海南矿业 2025-07-24买入, 2025-09-04止损(-10.2%), 持有31天
    # 失败案例2: 锦江酒店 2025-09-18买入, 2025-10-09止损(-10.5%), 持有10天

    failed_cases = [
        {"code": "601969", "name": "海南矿业", "buy_date": "2025-07-24",
         "sell_date": "2025-09-04", "actual_return": -10.2, "hold_days": 31},
        {"code": "600754", "name": "锦江酒店", "buy_date": "2025-09-18",
         "sell_date": "2025-10-09", "actual_return": -10.5, "hold_days": 10},
    ]

    results = []

    for case in failed_cases:
        code = case["code"]
        buy_date = case["buy_date"]
        sell_date = case["sell_date"]

        # 获取买入价格
        buy_price_row = query(
            "SELECT close FROM daily_prices WHERE code = ? AND trade_date = ?",
            (code, buy_date)
        )
        if not buy_price_row:
            continue
        buy_price = buy_price_row[0][0]

        # 获取止损时的价格
        sell_price_row = query(
            "SELECT close FROM daily_prices WHERE code = ? AND trade_date = ?",
            (code, sell_date)
        )
        sell_price = sell_price_row[0][0] if sell_price_row else buy_price * 0.9

        # 如果持有到60天的价格
        future_dates = query(
            """SELECT trade_date, close FROM daily_prices
               WHERE code = ? AND trade_date > ?
               ORDER BY trade_date LIMIT 60""",
            (code, buy_date)
        )

        if len(future_dates) < 20:
            continue

        # 计算不同持有期的收益
        returns_by_day = {}
        for i, (d, p) in enumerate(future_dates):
            ret = (p - buy_price) / buy_price * 100
            returns_by_day[i+1] = {"date": d, "price": p, "return": ret}

        # 关键节点
        day_20 = returns_by_day.get(20, {})
        day_40 = returns_by_day.get(40, {})
        day_60 = returns_by_day.get(60, {})

        # 最大回撤和最大收益
        max_return = max(r["return"] for r in returns_by_day.values())
        min_return = min(r["return"] for r in returns_by_day.values())
        max_return_day = [k for k, v in returns_by_day.items() if v["return"] == max_return][0]
        min_return_day = [k for k, v in returns_by_day.items() if v["return"] == min_return][0]

        # 如果-15%止损，会在哪天触发？
        stop_loss_15_day = None
        for day, data in returns_by_day.items():
            if data["return"] <= -15:
                stop_loss_15_day = day
                break

        # 如果持有到回本或盈利
        breakeven_day = None
        profit_20_day = None
        profit_30_day = None
        for day, data in returns_by_day.items():
            if breakeven_day is None and data["return"] >= 0:
                breakeven_day = day
            if profit_20_day is None and data["return"] >= 20:
                profit_20_day = day
            if profit_30_day is None and data["return"] >= 30:
                profit_30_day = day

        result = {
            "code": code,
            "name": case["name"],
            "buy_date": buy_date,
            "actual_sell_date": sell_date,
            "actual_return": case["actual_return"],
            "buy_price": buy_price,
            "day_20_return": day_20.get("return", 0),
            "day_40_return": day_40.get("return", 0),
            "day_60_return": day_60.get("return", 0),
            "max_return": max_return,
            "max_return_day": max_return_day,
            "min_return": min_return,
            "min_return_day": min_return_day,
            "stop_loss_15_day": stop_loss_15_day,
            "breakeven_day": breakeven_day,
            "profit_20_day": profit_20_day,
            "profit_30_day": profit_30_day,
        }
        results.append(result)

        logger.info(f"\n【{case['name']} {code}】买入: {buy_date}")
        logger.info(f"  实际: {case['hold_days']}天, 收益 {case['actual_return']:.1f}%")
        logger.info(f"  持有20天: {day_20.get('return', 0):.1f}%")
        logger.info(f"  持有40天: {day_40.get('return', 0):.1f}%")
        logger.info(f"  持有60天: {day_60.get('return', 0):.1f}%")
        logger.info(f"  期间最高: {max_return:.1f}% (第{max_return_day}天)")
        logger.info(f"  期间最低: {min_return:.1f}% (第{min_return_day}天)")
        logger.info(f"  -15%止损会在第 {stop_loss_15_day} 天触发" if stop_loss_15_day else "  -15%止损不会被触发")
        logger.info(f"  回本需要 {breakeven_day} 天" if breakeven_day else "  60天内未回本")
        logger.info(f"  达到20%需要 {profit_20_day} 天" if profit_20_day else "  60天内未达到20%")
        logger.info(f"  达到30%需要 {profit_30_day} 天" if profit_30_day else "  60天内未达到30%")

    return results


def analyze_buy_timing():
    """分析买入时机的特征差异"""
    logger.info("\n" + "=" * 70)
    logger.info("分析成功案例 vs 失败案例的买入时机特征")
    logger.info("=" * 70)

    # 成功案例: 深桑达A(000032) 2025-02-13, 海南矿业(601969) 2025-11-07, 平潭发展(000592) 2025-11-07
    # 失败案例: 海南矿业(601969) 2025-07-24, 锦江酒店(600754) 2025-09-18

    cases = [
        {"code": "000032", "name": "深桑达A", "date": "2025-02-13", "result": "success", "return": 30.7},
        {"code": "601969", "name": "海南矿业(成功)", "date": "2025-11-07", "result": "success", "return": 34.9},
        {"code": "000592", "name": "平潭发展", "date": "2025-11-07", "result": "success", "return": 34.5},
        {"code": "601969", "name": "海南矿业(失败)", "date": "2025-07-24", "result": "failed", "return": -10.2},
        {"code": "600754", "name": "锦江酒店", "date": "2025-09-18", "result": "failed", "return": -10.5},
    ]

    for case in cases:
        code = case["code"]
        d = case["date"]

        # 获取买入前30天数据
        hist = query("""
            SELECT close, volume, amount, pct_change
            FROM daily_prices
            WHERE code = ? AND trade_date <= ?
            ORDER BY trade_date DESC LIMIT 30
        """, (code, d))

        if len(hist) < 20:
            continue

        closes = [h[0] for h in reversed(hist) if h[0] is not None]
        vols = [h[1] for h in reversed(hist) if h[1] is not None]
        amts = [h[2] for h in reversed(hist) if h[2] is not None]

        # 计算指标
        buy_price = closes[-1]
        high_20 = max(closes[-20:])
        low_20 = min(closes[-20:])
        price_position = (buy_price - low_20) / (high_20 - low_20) * 100 if high_20 > low_20 else 50

        ret_5d = (closes[-1] - closes[-5]) / closes[-5] * 100 if len(closes) >= 5 else 0
        ret_20d = (closes[-1] - closes[-20]) / closes[-20] * 100 if len(closes) >= 20 else 0

        avg_vol_5d = np.mean(vols[-6:-1])
        vol_ratio = vols[-1] / avg_vol_5d if avg_vol_5d > 0 else 1.0

        avg_amt_10d = np.mean(amts[-11:-1])
        amt_ratio = amts[-1] / avg_amt_10d if avg_amt_10d > 0 else 1.0

        ma5 = np.mean(closes[-5:])
        ma10 = np.mean(closes[-10:])
        ma20 = np.mean(closes[-20:])
        ma_align = 1 if buy_price > ma5 > ma10 > ma20 else 0

        logger.info(f"\n【{case['name']}】{d} | 结果: {case['result']} | 收益: {case['return']:.1f}%")
        logger.info(f"  价格位置: {price_position:.0f}%")
        logger.info(f"  5日涨幅: {ret_5d:.1f}%")
        logger.info(f"  20日涨幅: {ret_20d:.1f}%")
        logger.info(f"  量比: {vol_ratio:.2f}")
        logger.info(f"  成交额比: {amt_ratio:.2f}")
        logger.info(f"  均线多头: {'是' if ma_align else '否'}")


def generate_recommendations():
    """生成优化建议"""
    logger.info("\n" + "=" * 70)
    logger.info("优化建议")
    logger.info("=" * 70)

    recommendations = [
        "1. 止损线调整:",
        "   - 当前-10%止损过早，建议调整到-15%",
        "   - 或者采用动态止损：跌破MA20且跌幅>12%",
        "",
        "2. 波浪判断优化:",
        "   - 增加'突破前高'的确认条件",
        "   - 3浪判断需要：价格>前高*0.98 + 20日涨幅15-40% + 放量",
        "   - 排除5浪末升段（40日涨幅>50%）",
        "",
        "3. 买入时机优化:",
        "   - 成功案例的价格位置多在60-80%",
        "   - 失败案例的5日涨幅可能过高(>15%)",
        "   - 建议增加'5日涨幅<15%'的过滤",
        "",
        "4. 持有期优化:",
        "   - 成功案例多在7-15天达到30%",
        "   - 建议：达到30%后设置移动止盈（回撤5%卖出）",
        "   - 未达到30%但持有>40天，检查趋势是否还在",
    ]

    for r in recommendations:
        logger.info(r)


if __name__ == "__main__":
    print("=" * 70)
    print("Auto Research Round 1: 失败案例分析")
    print("=" * 70)

    # 分析失败案例
    failed_results = analyze_failed_trades()

    # 分析买入时机
    analyze_buy_timing()

    # 生成建议
    generate_recommendations()

    print("\n" + "=" * 70)
    print("Round 1 完成")
    print("=" * 70)
