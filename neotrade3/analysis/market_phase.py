"""
市场阶段检测模块

提供市场阶段识别功能，包括牛市、熊市、震荡市和过渡期判断。
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional, List, Tuple
from datetime import datetime, timedelta
import sqlite3


class MarketPhase(Enum):
    """市场阶段枚举"""
    BULL = "bull"           # 牛市
    BEAR = "bear"           # 熊市
    RANGE = "range"         # 震荡市
    TRANSITION = "transition"  # 过渡期


@dataclass
class MarketPhaseResult:
    """市场阶段检测结果"""
    phase: MarketPhase
    confidence: float
    market_return_20d: float
    market_return_60d: float
    market_breadth: float
    ma20_slope: float
    ma60_slope: float
    total_amount: float
    amount_trend: str


def _simple_ma(prices: List[float], period: int) -> List[float]:
    """
    计算简单移动平均线
    
    Args:
        prices: 价格列表
        period: 周期
        
    Returns:
        移动平均线列表
    """
    if len(prices) < period:
        return []
    
    ma = []
    for i in range(period - 1, len(prices)):
        avg = sum(prices[i - period + 1:i + 1]) / period
        ma.append(avg)
    return ma


def _calc_market_return(prices: List[float], days: int) -> float:
    """
    计算市场收益率
    
    Args:
        prices: 价格列表
        days: 计算周期
        
    Returns:
        收益率（小数形式）
    """
    if len(prices) < days + 1:
        return 0.0
    
    current_price = prices[-1]
    past_price = prices[-(days + 1)]
    
    if past_price == 0:
        return 0.0
    
    return (current_price - past_price) / past_price


def _calc_market_breadth(
    db_path: str,
    target_date: str,
    lookback_days: int = 20
) -> float:
    """
    计算市场广度（上涨股票占比）
    
    Args:
        db_path: 数据库路径
        target_date: 目标日期
        lookback_days: 回看天数
        
    Returns:
        市场广度（0-1之间）
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        row = cursor.execute(
            "SELECT trade_date FROM trading_calendar_cache WHERE trade_date <= ? ORDER BY trade_date DESC LIMIT 1 OFFSET ?",
            (target_date, int(lookback_days)),
        ).fetchone()
        if not row or not row[0]:
            row = cursor.execute(
                "SELECT trade_date FROM (SELECT DISTINCT trade_date FROM daily_prices WHERE trade_date <= ?) ORDER BY trade_date DESC LIMIT 1 OFFSET ?",
                (target_date, int(lookback_days)),
            ).fetchone()
        past_date = str(row[0]) if row and row[0] else None
        if not past_date:
            conn.close()
            return 0.5
        
        # 查询所有股票在目标日期和回看日期的收盘价
        cursor.execute("""
            SELECT code, trade_date, close
            FROM daily_prices
            WHERE trade_date IN (?, ?)
            ORDER BY code, trade_date
        """, (past_date, target_date))
        
        rows = cursor.fetchall()
        conn.close()
        
        # 按股票分组计算涨跌
        stock_prices = {}
        for code, trade_date, close in rows:
            if code not in stock_prices:
                stock_prices[code] = {}
            stock_prices[code][trade_date] = close
        
        up_count = 0
        total_count = 0
        
        for code, prices in stock_prices.items():
            if past_date in prices and target_date in prices:
                total_count += 1
                if prices[target_date] > prices[past_date]:
                    up_count += 1
        
        if total_count == 0:
            return 0.5
        
        return up_count / total_count
        
    except Exception as e:
        print(f"计算市场广度时出错: {e}")
        return 0.5


def _calc_total_amount(
    db_path: str,
    target_date: str,
    lookback_days: int = 20
) -> Tuple[float, str]:
    """
    计算市场总成交额及趋势
    
    Args:
        db_path: 数据库路径
        target_date: 目标日期
        lookback_days: 回看天数
        
    Returns:
        (总成交额, 趋势)
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        row = cursor.execute(
            "SELECT trade_date FROM trading_calendar_cache WHERE trade_date <= ? ORDER BY trade_date DESC LIMIT 1 OFFSET ?",
            (target_date, int(lookback_days) + 10),
        ).fetchone()
        if not row or not row[0]:
            row = cursor.execute(
                "SELECT trade_date FROM (SELECT DISTINCT trade_date FROM daily_prices WHERE trade_date <= ?) ORDER BY trade_date DESC LIMIT 1 OFFSET ?",
                (target_date, int(lookback_days) + 10),
            ).fetchone()
        start_date = str(row[0]) if row and row[0] else None
        if not start_date:
            conn.close()
            return 0.0, "unknown"
        
        # 查询每日成交额
        cursor.execute("""
            SELECT trade_date, SUM(amount) as total_amount
            FROM daily_prices
            WHERE trade_date BETWEEN ? AND ?
            GROUP BY trade_date
            ORDER BY trade_date
        """, (start_date, target_date))
        
        rows = cursor.fetchall()
        conn.close()
        
        if len(rows) < 10:
            return 0.0, "unknown"
        
        amounts = [row[1] for row in rows]
        current_amount = amounts[-1]
        
        # 计算成交额趋势
        recent_avg = sum(amounts[-5:]) / 5
        past_avg = sum(amounts[-10:-5]) / 5
        
        if recent_avg > past_avg * 1.1:
            trend = "increasing"
        elif recent_avg < past_avg * 0.9:
            trend = "decreasing"
        else:
            trend = "stable"
        
        return current_amount, trend
        
    except Exception as e:
        print(f"计算成交额时出错: {e}")
        return 0.0, "unknown"


def _classify_phase(
    return_20d: float,
    return_60d: float,
    breadth: float,
    ma20_slope: float,
    ma60_slope: float
) -> Tuple[MarketPhase, float]:
    """
    根据指标分类市场阶段
    
    Args:
        return_20d: 20日收益率
        return_60d: 60日收益率
        breadth: 市场广度
        ma20_slope: 20日均线斜率
        ma60_slope: 60日均线斜率
        
    Returns:
        (市场阶段, 置信度)
    """
    # 牛市判断条件
    bull_signals = 0
    if return_20d > 0.05:
        bull_signals += 1
    if return_60d > 0.10:
        bull_signals += 1
    if breadth > 0.6:
        bull_signals += 1
    if ma20_slope > 0 and ma60_slope > 0:
        bull_signals += 1
    
    # 熊市判断条件
    bear_signals = 0
    if return_20d < -0.05:
        bear_signals += 1
    if return_60d < -0.10:
        bear_signals += 1
    if breadth < 0.4:
        bear_signals += 1
    if ma20_slope < 0 and ma60_slope < 0:
        bear_signals += 1
    
    # 震荡市判断条件
    range_signals = 0
    if abs(return_20d) < 0.05:
        range_signals += 1
    if abs(return_60d) < 0.10:
        range_signals += 1
    if 0.4 <= breadth <= 0.6:
        range_signals += 1
    if abs(ma20_slope) < 0.001:
        range_signals += 1
    
    # 确定阶段和置信度
    if bull_signals >= 3:
        confidence = min(bull_signals / 4, 1.0)
        return MarketPhase.BULL, confidence
    elif bear_signals >= 3:
        confidence = min(bear_signals / 4, 1.0)
        return MarketPhase.BEAR, confidence
    elif range_signals >= 3:
        confidence = min(range_signals / 4, 1.0)
        return MarketPhase.RANGE, confidence
    else:
        return MarketPhase.TRANSITION, 0.5


def detect_market_phase(
    db_path: str,
    target_date: str,
    lookback_days: int = 60
) -> MarketPhaseResult:
    """
    检测市场阶段
    
    Args:
        db_path: 数据库路径
        target_date: 目标日期（格式：YYYY-MM-DD）
        lookback_days: 回看天数，默认60天
        
    Returns:
        MarketPhaseResult对象
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        row = cursor.execute(
            "SELECT trade_date FROM trading_calendar_cache WHERE trade_date <= ? ORDER BY trade_date DESC LIMIT 1 OFFSET ?",
            (target_date, int(lookback_days) + 10),
        ).fetchone()
        if not row or not row[0]:
            row = cursor.execute(
                "SELECT trade_date FROM (SELECT DISTINCT trade_date FROM daily_prices WHERE trade_date <= ?) ORDER BY trade_date DESC LIMIT 1 OFFSET ?",
                (target_date, int(lookback_days) + 10),
            ).fetchone()
        start_date = str(row[0]) if row and row[0] else None
        if not start_date:
            conn.close()
            return MarketPhaseResult(
                phase=MarketPhase.TRANSITION,
                confidence=0.0,
                market_return_20d=0.0,
                market_return_60d=0.0,
                market_breadth=0.5,
                ma20_slope=0.0,
                ma60_slope=0.0,
                total_amount=0.0,
                amount_trend="unknown"
            )
        
        # 查询市场数据（使用全市场平均收盘价作为市场代表）
        cursor.execute("""
            SELECT trade_date, AVG(close) as avg_close
            FROM daily_prices
            WHERE trade_date BETWEEN ? AND ?
            GROUP BY trade_date
            ORDER BY trade_date
        """, (start_date, target_date))
        
        rows = cursor.fetchall()
        conn.close()
        
        if len(rows) < lookback_days:
            # 数据不足，返回默认值
            return MarketPhaseResult(
                phase=MarketPhase.TRANSITION,
                confidence=0.0,
                market_return_20d=0.0,
                market_return_60d=0.0,
                market_breadth=0.5,
                ma20_slope=0.0,
                ma60_slope=0.0,
                total_amount=0.0,
                amount_trend="unknown"
            )
        
        # 提取平均收盘价数据（avg_close）
        prices = [row[1] for row in rows]
        
        # 计算收益率
        return_20d = _calc_market_return(prices, 20)
        return_60d = _calc_market_return(prices, 60)
        
        # 计算市场广度
        breadth = _calc_market_breadth(db_path, target_date, 20)
        
        # 计算移动平均线
        ma20 = _simple_ma(prices, 20)
        ma60 = _simple_ma(prices, 60)
        
        # 计算均线斜率
        ma20_slope = 0.0
        if len(ma20) >= 5:
            ma20_slope = (ma20[-1] - ma20[-5]) / ma20[-5] if ma20[-5] != 0 else 0.0
        
        ma60_slope = 0.0
        if len(ma60) >= 5:
            ma60_slope = (ma60[-1] - ma60[-5]) / ma60[-5] if ma60[-5] != 0 else 0.0
        
        # 计算成交额
        total_amount, amount_trend = _calc_total_amount(db_path, target_date, 20)
        
        # 分类市场阶段
        phase, confidence = _classify_phase(
            return_20d, return_60d, breadth, ma20_slope, ma60_slope
        )
        
        return MarketPhaseResult(
            phase=phase,
            confidence=confidence,
            market_return_20d=return_20d,
            market_return_60d=return_60d,
            market_breadth=breadth,
            ma20_slope=ma20_slope,
            ma60_slope=ma60_slope,
            total_amount=total_amount,
            amount_trend=amount_trend
        )
        
    except Exception as e:
        print(f"检测市场阶段时出错: {e}")
        return MarketPhaseResult(
            phase=MarketPhase.TRANSITION,
            confidence=0.0,
            market_return_20d=0.0,
            market_return_60d=0.0,
            market_breadth=0.5,
            ma20_slope=0.0,
            ma60_slope=0.0,
            total_amount=0.0,
            amount_trend="unknown"
        )
