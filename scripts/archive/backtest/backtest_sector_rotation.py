#!/usr/bin/env python3
"""
板块轮动策略回测

策略：
1. 每周一计算板块强度排名
2. 买入 Top 3 强势板块的领涨股（每板块 1 只）
3. 持有 5 个交易日
4. 下周一重新评估，调仓

对比基准：
- 等权持有 Top 100 成交额股票
- 纯 ML 预测策略
"""

import sys
import json
import sqlite3
import logging
import numpy as np
from pathlib import Path
from datetime import date, timedelta
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent))

from sector_rotation import SectorRotationEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)

DB_PATH = Path("var/db/stock_data.db")
OUTPUT_DIR = Path("var/backtest_results")


class SectorRotationBacktest:
    """板块轮动策略回测"""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.engine = SectorRotationEngine(db_path)

    def _get_conn(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self.db_path))

    def _get_trading_dates(self, start: date, end: date) -> list[date]:
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT DISTINCT trade_date FROM daily_prices WHERE trade_date BETWEEN ? AND ? ORDER BY trade_date",
            (start.isoformat(), end.isoformat()),
        )
        dates = [date.fromisoformat(r[0]) for r in cursor.fetchall()]
        conn.close()
        return dates

    def _get_price(self, code: str, d: date) -> float | None:
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT close FROM daily_prices WHERE code = ? AND trade_date = ?",
            (code, d.isoformat()),
        )
        row = cursor.fetchone()
        conn.close()
        return row[0] if row and row[0] > 0 else None

    def run_backtest(
        self,
        start_date: date,
        end_date: date,
        initial_capital: float = 1000000.0,
        hold_days: int = 5,
        top_sectors: int = 3,
        stocks_per_sector: int = 1,
    ) -> dict:
        """
        运行板块轮动回测

        Args:
            start_date: 回测开始日期
            end_date: 回测结束日期
            initial_capital: 初始资金
            hold_days: 持有天数
            top_sectors: 买入的强势板块数量
            stocks_per_sector: 每个板块买入的股票数量
        """
        logger.info(f"板块轮动回测: {start_date} ~ {end_date}")
        logger.info(f"参数: hold={hold_days}d, top_sectors={top_sectors}, stocks_per_sector={stocks_per_sector}")

        trading_dates = self._get_trading_dates(start_date, end_date)
        logger.info(f"交易日数量: {len(trading_dates)}")

        # 每周一次调仓（取每周一）
        rebalance_dates = []
        for i, d in enumerate(trading_dates):
            if i == 0 or (d - trading_dates[i-1]).days >= 3:  # 简化：间隔>=3天视为新一周
                rebalance_dates.append(d)
        logger.info(f"调仓次数: {len(rebalance_dates)}")

        capital = initial_capital
        positions = {}  # {code: {buy_date, buy_price, shares}}
        daily_values = []
        trades = []

        for i, current_date in enumerate(trading_dates):
            # 检查是否调仓日
            is_rebalance = current_date in rebalance_dates

            # 先检查持仓是否到期
            closed = []
            for code, pos in list(positions.items()):
                days_held = 0
                for d in trading_dates:
                    if d >= pos['buy_date'] and d <= current_date:
                        days_held += 1
                if days_held > hold_days:
                    sell_price = self._get_price(code, current_date)
                    if sell_price:
                        ret = (sell_price - pos['buy_price']) / pos['buy_price'] * 100
                        capital += sell_price * pos['shares']
                        trades.append({
                            'code': code,
                            'buy_date': pos['buy_date'].isoformat(),
                            'sell_date': current_date.isoformat(),
                            'return_pct': round(ret, 2),
                            'profit': round((sell_price - pos['buy_price']) * pos['shares'], 2),
                        })
                        closed.append(code)
            for code in closed:
                del positions[code]

            # 调仓日：买入新信号
            if is_rebalance and len(positions) < top_sectors * stocks_per_sector:
                try:
                    signals = self.engine.generate_weekly_signals(current_date)
                    buy_signals = signals.get('buy_signals', [])
                    
                    # 按置信度排序，取前 N 个
                    buy_signals = sorted(buy_signals, key=lambda x: x['confidence'], reverse=True)
                    buy_signals = buy_signals[:top_sectors * stocks_per_sector]
                    
                    for sig in buy_signals:
                        code = sig['code']
                        if code in positions:
                            continue
                        price = self._get_price(code, current_date)
                        if not price or price <= 0:
                            continue
                        
                        # 等权分配
                        per_position = capital / max(top_sectors * stocks_per_sector - len(positions), 1)
                        shares = int(per_position / price / 100) * 100
                        if shares >= 100 and shares * price <= capital:
                            capital -= shares * price
                            positions[code] = {
                                'buy_date': current_date,
                                'buy_price': price,
                                'shares': shares,
                                'sector': sig.get('sector', ''),
                            }
                except Exception as e:
                    logger.warning(f"调仓失败 {current_date}: {e}")

            # 计算当日总资产
            position_value = sum(
                (self._get_price(code, current_date) or pos['buy_price']) * pos['shares']
                for code, pos in positions.items()
            )
            total_value = capital + position_value
            daily_values.append({
                'date': current_date.isoformat(),
                'total_value': round(total_value, 2),
                'num_positions': len(positions),
            })

            if (i + 1) % 20 == 0:
                logger.info(f"  {current_date}: 总资产={total_value:,.0f}")

        # 平仓剩余持仓
        for code, pos in positions.items():
            final_price = self._get_price(code, trading_dates[-1])
            if final_price:
                ret = (final_price - pos['buy_price']) / pos['buy_price'] * 100
                capital += final_price * pos['shares']
                trades.append({
                    'code': code,
                    'buy_date': pos['buy_date'].isoformat(),
                    'sell_date': trading_dates[-1].isoformat(),
                    'return_pct': round(ret, 2),
                })

        # 计算指标
        final_value = capital
        total_return = (final_value - initial_capital) / initial_capital * 100
        annual_return = (1 + total_return / 100) ** (252 / len(trading_dates)) - 1

        # 最大回撤
        values = [d['total_value'] for d in daily_values]
        peak = values[0]
        max_dd = 0
        for v in values:
            if v > peak:
                peak = v
            dd = (peak - v) / peak * 100
            if dd > max_dd:
                max_dd = dd

        # 胜率
        wins = [t for t in trades if t.get('return_pct', 0) > 0]
        win_rate = len(wins) / len(trades) * 100 if trades else 0
        avg_return = np.mean([t['return_pct'] for t in trades]) if trades else 0

        return {
            'strategy': 'sector_rotation',
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'initial_capital': initial_capital,
            'final_value': round(final_value, 2),
            'total_return_pct': round(total_return, 2),
            'annual_return_pct': round(annual_return * 100, 2),
            'max_drawdown_pct': round(max_dd, 2),
            'total_trades': len(trades),
            'win_rate_pct': round(win_rate, 2),
            'avg_return_pct': round(avg_return, 2),
            'trading_days': len(trading_dates),
            'trades': trades[-20:],  # 最近20笔
        }


def main():
    # 获取数据范围
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.execute("SELECT MAX(trade_date) FROM daily_prices")
    max_date = date.fromisoformat(cursor.fetchone()[0])
    cursor = conn.execute("SELECT MIN(trade_date) FROM daily_prices WHERE trade_date >= '2025-01-01'")
    min_date = date.fromisoformat(cursor.fetchone()[0] or '2025-01-01')
    conn.close()

    # 回测最近 3 个月
    end_date = max_date
    start_date = end_date - timedelta(days=90)

    backtest = SectorRotationBacktest()
    result = backtest.run_backtest(start_date, end_date)

    print("\n" + "=" * 60)
    print("板块轮动策略回测结果")
    print("=" * 60)
    print(f"回测区间: {result['start_date']} ~ {result['end_date']}")
    print(f"初始资金: ¥{result['initial_capital']:,.0f}")
    print(f"最终资产: ¥{result['final_value']:,.0f}")
    print(f"总收益率: {result['total_return_pct']:.2f}%")
    print(f"年化收益率: {result['annual_return_pct']:.2f}%")
    print(f"最大回撤: {result['max_drawdown_pct']:.2f}%")
    print(f"交易次数: {result['total_trades']}")
    print(f"胜率: {result['win_rate_pct']:.2f}%")
    print(f"平均收益: {result['avg_return_pct']:.2f}%")
    print("=" * 60)

    # 保存
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_file = OUTPUT_DIR / f"sector_rotation_{start_date.isoformat()}_{end_date.isoformat()}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n结果已保存: {output_file}")


if __name__ == "__main__":
    main()
