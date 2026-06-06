#!/usr/bin/env python3
"""
低频量化交易引擎 v16 - 高级优化版

核心目标：预判未来20-60个交易日有80%+机会涨幅达到30-50%的股票

v16 新增优化：
1. 板块人气消散检测（跟随股先回调 → 中军稳 → 龙头其次）
2. 同频共振买入条件（大势+个股同步向上）
3. 基本面筛选（业绩增速、PE估值）
4. 止盈阈值100%（追求大波段）
5. 市场情绪过滤器
"""

import sqlite3
import logging
import numpy as np
from pathlib import Path
from datetime import date, timedelta
from dataclasses import dataclass, field
from typing import Optional, Any
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


class MarketSentiment(Enum):
    """市场情绪"""
    STRONG_BULL = "强牛"      # 强势上涨
    BULL = "牛市"              # 上涨
    NEUTRAL = "震荡"           # 震荡
    BEAR = "熊市"              # 下跌
    STRONG_BEAR = "强熊"       # 强势下跌


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
    # v16: 板块趋势状态
    trend_state: str = "unknown"  # rising, falling, consolidating
    leader_strength: float = 0.0   # 龙头强度
    follower_weakness: float = 0.0  # 跟随股弱势程度


@dataclass
class StockCandidate:
    """个股候选"""
    code: str
    name: str
    sector: str
    market_cap_yi: float = 0.0
    role: str = ""  # 龙头/中军/跟随
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
    price_position: float = 0.0
    # v16: 基本面指标
    pe_ttm: float = 0.0
    profit_growth: float = 0.0  # 净利润增速
    revenue_growth: float = 0.0  # 营收增速
    roe: float = 0.0
    # v16: 与板块共振度
    sector_resonance: float = 0.0  # 0-1，越高越共振
    cup_handle_ok: bool = False


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
    shares_sold: int = 0
    hold_days: int = 0
    return_pct: float = 0.0
    buy_score: float = 0.0
    wave_phase: str = ""
    peak_price: float = 0.0
    partial_taken: bool = False
    sell_reason: str = ""
    status: str = "open"
    role: str = ""  # v16: 记录买入时的角色


class LowFreqTradingEngineV16:
    """低频量化交易引擎 v16 - 高级优化版"""

    # ===== 参数配置 =====
    MARKET_CAP_MAX = 400e8
    MARKET_CAP_MIN = 200e8
    BUY_THRESHOLD = 85               # v16opt: 提高到85，更严格
    MIN_RESONANCE = 0.7              # v16opt: 新增共振度最低要求
    TARGET_RETURN = 30.0
    PARTIAL_PROFIT_LEVEL = 25.0
    PARTIAL_PROFIT_PCT = 50
    TRAILING_PROFIT_LEVEL = 20.0
    TRAILING_STOP_PCT = -5.0
    MIN_HOLD_DAYS = 15
    MAX_HOLD_DAYS = 75               # v17opt: 延长到75天，让趋势股跑完
    STOP_LOSS_PCT = -10.0
    HOT_SECTOR_COUNT = 5
    MAX_POSITIONS = 3
    REBALANCE_DAYS = 15              # v16opt: 调仓周期延长到15天
    STOP_LOSS_CONFIRM_DAYS = 2
    SECTOR_COOLDOWN_CONFIRM_WINDOW = 3
    SECTOR_COOLDOWN_CONFIRM_HITS = 2
    ROTATION_SCORE_DELTA = 8.0
    ROTATION_MIN_RETURN_PCT = -100.0

    CROSS_SECTOR_SCAN_ENABLED = True
    CROSS_SECTOR_MAX_SIGNALS = 1
    CROSS_SECTOR_SCORE_MARGIN = 8.0
    CROSS_SECTOR_SCAN_LIMIT = 120
    CROSS_SECTOR_WAVE3_ONLY = True

    WEEKLY_DUCK_HEAD_ENABLED = True
    WEEKLY_DUCK_HEAD_MA_SHORT = 5
    WEEKLY_DUCK_HEAD_MA_MID = 10
    WEEKLY_DUCK_HEAD_MA_LONG = 15
    WEEKLY_DUCK_HEAD_MIN_WEEKS = 20
    WEEKLY_DUCK_HEAD_PULLBACK_WEEKS = 3
    WEEKLY_DUCK_HEAD_BREAKOUT_LOOKBACK_WEEKS = 2
    WEEKLY_DUCK_HEAD_OVEREXTEND_PCT = 25.0
    WEEKLY_DUCK_HEAD_LOOKBACK_DAYS = 520

    NO_LOOKAHEAD_ENFORCED = True

    SECTOR_ACCEL_LOOKBACK_TRADING_DAYS = 5
    SECTOR_ACCEL_BONUS_ENABLED = False
    SECTOR_ACCEL_BONUS_HIGH = 8.0
    SECTOR_ACCEL_BONUS_LOW = 4.0
    RELATIVE_STRENGTH_BONUS_CAP = 0.0

    CUP_HANDLE_ENABLED = True
    CUP_HANDLE_SCREENER_ID = "cup_handle_v4"
    CUP_HANDLE_TOP_N = 50
    STRUCTURE_CONFIRM_MODE = "duck_only"
    CUP_HANDLE_SCORE_BONUS = 6.0
    CUP_HANDLE_NONCONFIRM_THRESHOLD_BONUS = 0.0
    
    # v16: 基本面筛选参数（表不存在时自动跳过）
    MAX_PE = 50
    MIN_PROFIT_GROWTH = 10
    MIN_ROE = 8
    
    # v16: 市场情绪参数
    MARKET_FILTER_ENABLED = False

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        # v16: 缓存板块历史数据用于趋势判断
        self._sector_history_cache = {}
        self._weekly_duck_head_cache: dict[tuple[str, str], dict] = {}
        self._cup_handle_cache: dict[str, set[str]] = {}
        self._has_financial_reports: Optional[bool] = None
        self._sector_cooldown_cache: dict[tuple[str, str], dict] = {}
        self._indexes_ready = False
        self._sector_members_cache: dict[str, dict[str, Any]] = {}

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        if not bool(getattr(self, "_indexes_ready", False)):
            try:
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_daily_prices_code_trade_date ON daily_prices(code, trade_date)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_daily_prices_trade_date_code ON daily_prices(trade_date, code)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_stocks_sector_lv1 ON stocks(sector_lv1)"
                )
                conn.commit()
                self._indexes_ready = True
            except Exception:
                pass
        return conn

    def _ensure_no_lookahead_trade_dates(
        self, rows: list[tuple], *, target_date: date, trade_date_index: int = 0, context: str
    ) -> None:
        if not bool(self.NO_LOOKAHEAD_ENFORCED):
            return
        future = []
        for r in rows:
            if not r:
                continue
            try:
                d = date.fromisoformat(str(r[int(trade_date_index)]))
            except Exception:
                continue
            if d > target_date:
                future.append(d)
        if future:
            latest = max(future)
            raise ValueError(f"回测禁止引用未来数据：{context} 存在 {latest.isoformat()} > {target_date.isoformat()}")

    def _cup_handle_picks(self, target_date: date) -> set[str]:
        if not bool(self.CUP_HANDLE_ENABLED):
            return set()
        key = target_date.isoformat()
        cached = self._cup_handle_cache.get(key)
        if cached is not None:
            return cached
        try:
            from neotrade3.screeners.runtime import run_cup_handle_v4
        except Exception:
            self._cup_handle_cache[key] = set()
            return set()
        try:
            payload = run_cup_handle_v4(
                screener_id=str(self.CUP_HANDLE_SCREENER_ID),
                target_date=target_date,
                parameters={"top_n": int(self.CUP_HANDLE_TOP_N)},
            )
        except Exception:
            payload = {}
        picks = payload.get("picks") if isinstance(payload, dict) else None
        if isinstance(picks, list):
            out = {str(x).split(".", 1)[0].strip() for x in picks if str(x).strip()}
        else:
            out = set()
        out = {x for x in out if len(x) == 6 and x.isdigit()}
        self._cup_handle_cache[key] = out
        return out

    def _structure_confirm(self, *, code: str, target_date: date) -> dict:
        mode = str(getattr(self, "STRUCTURE_CONFIRM_MODE", "duck_only") or "duck_only")
        weekly = self.check_weekly_duck_head(str(code), target_date)
        duck_ok = bool(weekly.get("passed"))

        cup_ok = False
        if mode != "duck_only" and bool(self.CUP_HANDLE_ENABLED):
            cup_picks = self._cup_handle_picks(target_date)
            cup_ok = str(code) in cup_picks

        if mode == "duck_only":
            passed = duck_ok
        elif mode == "cup_only":
            passed = cup_ok
        elif mode == "duck_or_cup":
            passed = duck_ok or cup_ok
        elif mode == "duck_and_cup":
            passed = duck_ok and cup_ok
        else:
            passed = duck_ok

        reasons: list[str] = []
        if duck_ok:
            reasons.append("周线老鸭头确认（MA5/MA10/MA15）")
        if cup_ok:
            reasons.append("杯柄确认（cup_handle_v4）")

        return {
            "passed": bool(passed),
            "mode": mode,
            "duck_ok": bool(duck_ok),
            "cup_ok": bool(cup_ok),
            "weekly_reason": weekly.get("reason"),
            "reasons": reasons,
        }

    def _recent_trading_dates(self, target_date: date, *, limit: int) -> list[date]:
        if int(limit) <= 0:
            return []
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT DISTINCT trade_date FROM daily_prices WHERE trade_date <= ? ORDER BY trade_date DESC LIMIT ?",
                (target_date.isoformat(), int(limit)),
            ).fetchall()
        finally:
            conn.close()
        out = [date.fromisoformat(str(r[0])) for r in rows if r and r[0]]
        out.sort()
        return out

    def _weekly_series_view(self, code: str, target_date: date) -> dict:
        cache_key = (str(code), target_date.isoformat())
        cached = self._weekly_duck_head_cache.get(cache_key)
        if cached is not None:
            return cached

        start_date = target_date - timedelta(days=int(self.WEEKLY_DUCK_HEAD_LOOKBACK_DAYS))
        conn = self._conn()
        try:
            cursor = conn.execute(
                """
                SELECT trade_date, close
                FROM daily_prices
                WHERE code = ?
                  AND trade_date BETWEEN ? AND ?
                  AND close IS NOT NULL
                ORDER BY trade_date ASC
                """,
                (str(code), start_date.isoformat(), target_date.isoformat()),
            )
            rows = cursor.fetchall()
        finally:
            conn.close()

        self._ensure_no_lookahead_trade_dates(rows, target_date=target_date, context=f"_weekly_series_view({code})")

        buckets: dict[tuple[int, int], dict] = {}
        for trade_date, close in rows:
            d = date.fromisoformat(str(trade_date))
            iso = d.isocalendar()
            key = (int(iso.year), int(iso.week))
            b = buckets.get(key)
            if b is None:
                b = {"last_date": d, "close": float(close), "min_close": float(close)}
                buckets[key] = b
            else:
                b["last_date"] = d
                b["close"] = float(close)
                b["min_close"] = min(float(b["min_close"]), float(close))

        weeks = sorted(buckets.keys())
        series = []
        for y, w in weeks:
            b = buckets[(y, w)]
            series.append(
                {
                    "iso_year": int(y),
                    "iso_week": int(w),
                    "last_date": b["last_date"].isoformat(),
                    "close": float(b["close"]),
                    "min_close": float(b["min_close"]),
                }
            )

        out = {"status": "ok", "series": series}
        self._weekly_duck_head_cache[cache_key] = out
        return out

    def _sma_at(self, closes: list[float], window: int, idx: int) -> Optional[float]:
        w = int(window)
        if w <= 0:
            return None
        if idx < w - 1:
            return None
        segment = closes[idx - w + 1 : idx + 1]
        if len(segment) != w:
            return None
        return float(np.mean(segment))

    def check_weekly_duck_head(self, code: str, target_date: date) -> dict:
        if not bool(self.WEEKLY_DUCK_HEAD_ENABLED):
            return {"passed": True, "reason": "disabled"}

        view = self._weekly_series_view(str(code), target_date)
        series = view.get("series") or []
        closes = [float(x["close"]) for x in series if isinstance(x, dict) and x.get("close") is not None]
        if len(closes) < int(self.WEEKLY_DUCK_HEAD_MIN_WEEKS):
            return {"passed": False, "reason": "weekly_insufficient", "weeks": len(closes)}

        t = len(closes) - 1
        ma_s = self._sma_at(closes, int(self.WEEKLY_DUCK_HEAD_MA_SHORT), t)
        ma_m = self._sma_at(closes, int(self.WEEKLY_DUCK_HEAD_MA_MID), t)
        ma_l = self._sma_at(closes, int(self.WEEKLY_DUCK_HEAD_MA_LONG), t)
        ma_s_prev = self._sma_at(closes, int(self.WEEKLY_DUCK_HEAD_MA_SHORT), t - 1)
        ma_m_prev = self._sma_at(closes, int(self.WEEKLY_DUCK_HEAD_MA_MID), t - 1)
        if ma_s is None or ma_m is None or ma_l is None or ma_s_prev is None or ma_m_prev is None:
            return {"passed": False, "reason": "weekly_ma_unavailable"}

        c_t = float(closes[t])

        cond1 = ma_s > ma_m > ma_l
        if not cond1:
            return {"passed": False, "reason": "weekly_ma_not_bull", "ma5": ma_s, "ma10": ma_m, "ma15": ma_l}

        cond2 = ma_s > ma_s_prev and ma_m >= ma_m_prev
        if not cond2:
            return {"passed": False, "reason": "weekly_turn_not_confirmed", "ma5_slope": ma_s - ma_s_prev, "ma10_slope": ma_m - ma_m_prev}

        pullback_weeks = int(self.WEEKLY_DUCK_HEAD_PULLBACK_WEEKS)
        start_idx = max(0, t - pullback_weeks + 1)
        touched = False
        for i in range(start_idx, t + 1):
            ma10_i = self._sma_at(closes, int(self.WEEKLY_DUCK_HEAD_MA_MID), i)
            if ma10_i is None:
                continue
            min_close = float(series[i]["min_close"]) if i < len(series) else float(closes[i])
            if min_close <= float(ma10_i):
                touched = True
                break
        if not touched:
            return {"passed": False, "reason": "weekly_pullback_missing"}
        if c_t <= float(ma_m):
            return {"passed": False, "reason": "weekly_close_below_ma10", "close": c_t, "ma10": ma_m}

        lb = int(self.WEEKLY_DUCK_HEAD_BREAKOUT_LOOKBACK_WEEKS)
        if lb >= 1 and t - lb >= 0:
            recent = closes[max(0, t - lb) : t]
            if recent and c_t < float(max(recent)):
                return {"passed": False, "reason": "weekly_breakout_not_confirmed"}

        if float(ma_l) > 0:
            over = (c_t / float(ma_l) - 1.0) * 100.0
            if over > float(self.WEEKLY_DUCK_HEAD_OVEREXTEND_PCT):
                return {"passed": False, "reason": "weekly_overextended", "over_ma15_pct": over}

        return {
            "passed": True,
            "reason": "weekly_duck_head_confirmed",
            "ma5": ma_s,
            "ma10": ma_m,
            "ma15": ma_l,
        }

    def _weekly_returns_view(self, code: str, target_date: date) -> dict:
        view = self._weekly_series_view(str(code), target_date)
        series = view.get("series") or []
        closes = [float(x["close"]) for x in series if isinstance(x, dict) and x.get("close") is not None]
        if len(closes) < 16:
            return {"status": "insufficient", "weeks": len(closes)}
        t = len(closes) - 1
        def _ret(k: int) -> float:
            if t - k < 0:
                return 0.0
            base = float(closes[t - k])
            if base <= 0:
                return 0.0
            return (float(closes[t]) / base - 1.0) * 100.0
        return {
            "status": "ok",
            "ret_1w": _ret(1),
            "ret_4w": _ret(4),
            "ret_12w": _ret(12),
        }

    def _is_return_below_threshold_consecutive(
        self, *, code: str, current_date: date, buy_price: float, threshold_pct: float, days: int
    ) -> bool:
        if days <= 1:
            return True
        if not buy_price or buy_price <= 0:
            return False
        conn = self._conn()
        try:
            cursor = conn.execute(
                "SELECT close FROM daily_prices WHERE code = ? AND trade_date <= ? "
                "ORDER BY trade_date DESC LIMIT ?",
                (code, current_date.isoformat(), int(days)),
            )
            closes = [r[0] for r in cursor.fetchall() if r and r[0] is not None]
        finally:
            conn.close()
        if len(closes) < int(days):
            return False
        for close in closes:
            ret = (float(close) - float(buy_price)) / float(buy_price) * 100.0
            if ret > float(threshold_pct):
                return False
        return True

    def _sector_cooldown_confirmed(self, sector: str, current_date: date) -> dict:
        window = int(self.SECTOR_COOLDOWN_CONFIRM_WINDOW)
        required = int(self.SECTOR_COOLDOWN_CONFIRM_HITS)
        start = current_date - timedelta(days=40)
        dates = self._get_trading_dates(start, current_date)
        tail = dates[-window:] if window > 0 else dates[-3:]
        hits = 0
        checked = 0
        latest: dict | None = None
        for d in tail:
            info = self.detect_sector_cooldown(sector, d)
            latest = info
            checked += 1
            if (
                info.get("cooldown_detected")
                and float(info.get("follower_weakness") or 0) > 0.6
                and str(info.get("trend_state") or "") in {"diverging", "falling"}
            ):
                hits += 1
        return {
            "confirmed": bool(checked > 0 and hits >= required),
            "hits": hits,
            "checked": checked,
            "latest": latest or {},
        }

    # ================================================================
    # v16: 市场情绪判断
    # ================================================================
    def get_market_sentiment(self, target_date: date) -> tuple[MarketSentiment, float]:
        """
        判断整体市场情绪
        返回: (情绪状态, 分数0-100)
        """
        conn = self._conn()
        cursor = conn.cursor()
        
        # 获取沪深300或全市场指数数据
        cursor.execute("""
            SELECT AVG(pct_change), AVG(volume), COUNT(*) 
            FROM daily_prices 
            WHERE trade_date = ? AND code LIKE '000___'
        """, (target_date.isoformat(),))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row or row[0] is None:
            return MarketSentiment.NEUTRAL, 50.0
        
        avg_change, avg_volume, count = row
        
        # 计算市场得分
        score = 50.0
        
        # 涨跌影响
        if avg_change > 2:
            score += 30
        elif avg_change > 1:
            score += 20
        elif avg_change > 0:
            score += 10
        elif avg_change > -1:
            score -= 10
        elif avg_change > -2:
            score -= 20
        else:
            score -= 30
        
        # 限制范围
        score = max(0, min(100, score))
        
        # 判断情绪状态
        if score >= 70:
            sentiment = MarketSentiment.STRONG_BULL
        elif score >= 55:
            sentiment = MarketSentiment.BULL
        elif score >= 45:
            sentiment = MarketSentiment.NEUTRAL
        elif score >= 30:
            sentiment = MarketSentiment.BEAR
        else:
            sentiment = MarketSentiment.STRONG_BEAR
        
        return sentiment, score

    # ================================================================
    # v17: 跟随股溃散预警（针对持仓）
    # ================================================================
    def check_follower_collapse_warning(self, trade: TradeRecord, target_date: date) -> Optional[SellSignal]:
        """
        v17新增：监控持仓板块中的跟随股表现
        当跟随股开始溃散（相对龙头大幅下跌），提前卖出龙头/中军锁定利润
        
        逻辑：
        1. 获取持仓股近5日表现（龙头/中军）
        2. 获取板块中跟随股近5日表现
        3. 如果跟随股跌幅 > 龙头跌幅 +5%，触发预警卖出
        """
        # 获取持仓股的5日涨幅
        conn = self._conn()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT close FROM daily_prices
            WHERE code = ? AND trade_date <= ?
            ORDER BY trade_date DESC LIMIT 5
        """, (trade.code, target_date.isoformat()))
        
        trade_closes = [r[0] for r in cursor.fetchall() if r[0]]
        if len(trade_closes) < 5:
            conn.close()
            return None
        
        trade_5d_ret = (trade_closes[0] - trade_closes[4]) / trade_closes[4] * 100
        
        # 获取板块中跟随股的5日涨幅
        cursor.execute("""
            SELECT s.code, s.name,
                   (SELECT close FROM daily_prices WHERE code = s.code AND trade_date <= ? ORDER BY trade_date DESC LIMIT 1 OFFSET 0) as close_0,
                   (SELECT close FROM daily_prices WHERE code = s.code AND trade_date <= ? ORDER BY trade_date DESC LIMIT 1 OFFSET 4) as close_5
            FROM stocks s
            WHERE s.sector_lv1 = ? 
              AND s.total_market_cap > ? AND s.total_market_cap < ?
              AND s.code != ?
              AND (s.is_delisted IS NULL OR s.is_delisted = 0)
        """, (target_date.isoformat(), target_date.isoformat(),
              trade.sector, self.MARKET_CAP_MIN, self.MARKET_CAP_MAX, trade.code))
        
        rows = cursor.fetchall()
        conn.close()
        
        if len(rows) < 5:
            return None
        
        # 计算跟随股平均5日涨幅
        follower_rets = []
        for code, name, close_0, close_5 in rows:
            if close_0 and close_5 and close_5 > 0:
                ret = (close_0 - close_5) / close_5 * 100
                follower_rets.append(ret)
        
        if not follower_rets:
            return None
        
        avg_follower_ret = np.mean(follower_rets)
        
        # 关键指标：跟随股相对龙头的差距
        gap = avg_follower_ret - trade_5d_ret  # 正数=跟随股比龙头弱
        
        # 计算当前持仓盈亏
        current_return = (trade_closes[0] - trade.buy_price) / trade.buy_price * 100
        
        # v19: 触发条件优化 - 平衡收益与风险
        # 1. 跟随股相对龙头跌幅超过12%
        # 2. 持仓盈利超过20%
        # 3. 持仓至少持有12天
        if gap < -12 and current_return >= 20:
            hold_days = self._count_trading_days(date.fromisoformat(trade.buy_date), target_date)
            if hold_days >= 12:
                confidence = min(0.9, abs(gap) / 18)
                return SellSignal(
                    "follower_collapse",
                    confidence,
                    f"跟随股溃散预警！龙头{trade_5d_ret:.1f}% vs 跟随股{avg_follower_ret:.1f}%(差{gap:.1f}%), 持仓盈利{current_return:.1f}%"
                )
        
        return None

    # ================================================================
    # v16: 板块人气消散检测
    # ================================================================
    def detect_sector_cooldown(self, sector: str, target_date: date, cursor: Optional[Any] = None) -> dict:
        """
        检测板块是否开始人气消散
        
        逻辑：
        1. 获取板块内所有股票近5日表现
        2. 计算跟随股（涨幅后50%）的平均回调幅度
        3. 计算中军（涨幅中间30%）的稳定性
        4. 计算龙头（涨幅前20%）的相对强度
        
        返回: {
            'cooldown_detected': bool,
            'follower_weakness': float,  # 跟随股弱势程度 0-1
            'leader_strength': float,    # 龙头强度 0-1
            'trend_state': str           # rising/falling/consolidating
        }
        """
        cache_key = (str(sector or ""), target_date.isoformat())
        cached = self._sector_cooldown_cache.get(cache_key)
        if isinstance(cached, dict):
            return cached

        managed = cursor is None
        conn = self._conn() if managed else None
        cursor = (conn.cursor() if conn is not None else cursor)

        sector_key = str(sector or "").strip()
        cached_members = self._sector_members_cache.get(sector_key) if sector_key else None
        if isinstance(cached_members, dict):
            codes = list(cached_members.get("codes") or [])
            name_by_code = dict(cached_members.get("name_by_code") or {})
        else:
            cursor.execute(
                """
                SELECT s.code, s.name
                FROM stocks s
                WHERE s.sector_lv1 = ?
                  AND s.total_market_cap > ? AND s.total_market_cap < ?
                  AND (s.is_delisted IS NULL OR s.is_delisted = 0)
                """,
                (sector, self.MARKET_CAP_MIN, self.MARKET_CAP_MAX),
            )
            stock_rows = cursor.fetchall()
            if len(stock_rows) < 10:
                if conn is not None:
                    conn.close()
                result = {
                    "cooldown_detected": False,
                    "follower_weakness": 0,
                    "leader_strength": 0.5,
                    "trend_state": "unknown",
                }
                self._sector_cooldown_cache[cache_key] = result
                return result

            codes = []
            name_by_code = {}
            for code, name in stock_rows:
                code_s = str(code or "").strip()
                if not code_s:
                    continue
                codes.append(code_s)
                name_by_code[code_s] = str(name or "")

            self._sector_members_cache[sector_key] = {"codes": codes, "name_by_code": name_by_code}

        if len(codes) < 10:
            if conn is not None:
                conn.close()
            result = {
                "cooldown_detected": False,
                "follower_weakness": 0,
                "leader_strength": 0.5,
                "trend_state": "unknown",
            }
            self._sector_cooldown_cache[cache_key] = result
            return result

        if not codes:
            if conn is not None:
                conn.close()
            result = {
                "cooldown_detected": False,
                "follower_weakness": 0,
                "leader_strength": 0.5,
                "trend_state": "unknown",
            }
            self._sector_cooldown_cache[cache_key] = result
            return result

        placeholders = ",".join(["?"] * len(codes))
        cursor.execute(
            f"""
            SELECT code, close, rn FROM (
                SELECT code, close,
                       row_number() OVER (PARTITION BY code ORDER BY trade_date DESC) as rn
                FROM daily_prices
                WHERE trade_date <= ?
                  AND code IN ({placeholders})
            )
            WHERE rn <= 5
            ORDER BY code, rn
            """,
            (target_date.isoformat(), *codes),
        )
        price_rows = cursor.fetchall()
        if conn is not None:
            conn.close()

        closes_by_code: dict[str, list[float]] = {}
        for code, close, _rn in price_rows:
            code_s = str(code or "").strip()
            if not code_s:
                continue
            if close is None:
                continue
            lst = closes_by_code.get(code_s)
            if lst is None:
                lst = []
                closes_by_code[code_s] = lst
            if len(lst) >= 5:
                continue
            lst.append(float(close))

        returns: list[tuple[str, str, float]] = []
        for code_s in codes:
            closes = closes_by_code.get(code_s) or []
            if len(closes) < 5:
                continue
            close_0 = float(closes[0])
            close_5 = float(closes[4])
            if close_5 <= 0:
                continue
            ret = (close_0 - close_5) / close_5 * 100
            returns.append((code_s, name_by_code.get(code_s, ""), float(ret)))
        
        if len(returns) < 10:
            result = {
                "cooldown_detected": False,
                "follower_weakness": 0,
                "leader_strength": 0.5,
                "trend_state": "unknown",
            }
            self._sector_cooldown_cache[cache_key] = result
            return result
        
        # 按涨幅排序
        returns.sort(key=lambda x: x[2], reverse=True)
        n = len(returns)
        
        # 分组：龙头(前20%)、中军(中间30%)、跟随股(后50%)
        leaders = returns[:max(1, n//5)]
        middle = returns[max(1, n//5):max(1, n//5)+max(1, n*3//10)]
        followers = returns[max(1, n//2):]
        
        # 计算各组平均涨幅
        leader_avg = np.mean([r[2] for r in leaders]) if leaders else 0
        middle_avg = np.mean([r[2] for r in middle]) if middle else 0
        follower_avg = np.mean([r[2] for r in followers]) if followers else 0
        
        # 计算指标
        leader_strength = min(1.0, max(0, (leader_avg + 10) / 30))  # 归一化到0-1
        follower_weakness = min(1.0, max(0, (5 - follower_avg) / 15))  # 跟随股越弱值越高
        
        # 判断趋势状态
        if leader_avg > 15 and follower_avg > 5:
            trend_state = 'rising'
        elif leader_avg < 5 and follower_avg < -5:
            trend_state = 'falling'
        elif follower_avg < -3 and leader_avg > 10:
            trend_state = 'diverging'  # 分化，危险信号
        else:
            trend_state = 'consolidating'
        
        # 人气消散判断：跟随股大幅回调 + 龙头仍强 = 早期消散信号
        cooldown_detected = (follower_weakness > 0.6 and leader_strength > 0.5)
        
        result = {
            "cooldown_detected": cooldown_detected,
            "follower_weakness": follower_weakness,
            "leader_strength": leader_strength,
            "trend_state": trend_state,
            "leader_avg": leader_avg,
            "follower_avg": follower_avg,
        }
        self._sector_cooldown_cache[cache_key] = result
        return result

    # ================================================================
    # v16: 同频共振检测
    # ================================================================
    def check_resonance(self, code: str, sector: str, target_date: date) -> float:
        """
        检测个股与板块是否同频共振
        返回: 共振度 0-1
        """
        conn = self._conn()
        cursor = conn.cursor()
        
        # 获取个股近10日涨幅
        cursor.execute("""
            SELECT close FROM daily_prices
            WHERE code = ? AND trade_date <= ?
            ORDER BY trade_date DESC LIMIT 10
        """, (code, target_date.isoformat()))
        
        stock_closes = [r[0] for r in cursor.fetchall() if r[0] is not None]
        
        # 获取板块平均近10日涨幅
        cursor.execute("""
            SELECT AVG(close) FROM (
                SELECT code, close FROM daily_prices
                WHERE code IN (
                    SELECT code FROM stocks WHERE sector_lv1 = ?
                ) AND trade_date = ?
            )
        """, (sector, target_date.isoformat()))
        
        conn.close()
        
        if len(stock_closes) < 10:
            return 0.5
        
        # 计算个股5日、10日涨幅
        stock_ret_5d = (stock_closes[0] - stock_closes[4]) / stock_closes[4] * 100 if stock_closes[4] > 0 else 0
        stock_ret_10d = (stock_closes[0] - stock_closes[9]) / stock_closes[9] * 100 if stock_closes[9] > 0 else 0
        
        # 简单共振度计算：个股涨幅与板块趋势的一致性
        # 理想状态：个股和板块都在温和上涨（2-10%）
        resonance = 0.5
        
        if 2 <= stock_ret_5d <= 15:  # 个股温和上涨
            resonance += 0.3
        if 2 <= stock_ret_10d <= 20:  # 个股中期趋势向上
            resonance += 0.2
        
        return min(1.0, resonance)

    # ================================================================
    # v16: 基本面筛选
    # ================================================================
    def _get_fundamentals_batch(self, cursor, codes: list[str], target_date: date) -> dict[str, dict]:
        codes = [str(c or "").strip() for c in (codes or []) if str(c or "").strip()]
        if not codes:
            return {}

        if self._has_financial_reports is None:
            cursor.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='financial_reports' LIMIT 1"
            )
            self._has_financial_reports = bool(cursor.fetchone())

        if not bool(self._has_financial_reports):
            return {
                code: {
                    "pe_ttm": 0,
                    "profit_growth": 0,
                    "revenue_growth": 0,
                    "roe": 0,
                    "table_exists": False,
                }
                for code in codes
            }

        placeholders = ",".join(["?"] * len(codes))
        cursor.execute(
            f"""
            SELECT code, report_date, pe_ttm, profit_growth_yoy, revenue_growth_yoy, roe
            FROM financial_reports
            WHERE code IN ({placeholders}) AND report_date <= ?
            ORDER BY code, report_date DESC
            """,
            (*codes, target_date.isoformat()),
        )
        rows = cursor.fetchall()

        latest_by_code: dict[str, dict] = {}
        for code, _report_date, pe_ttm, profit_growth_yoy, revenue_growth_yoy, roe in rows:
            code_s = str(code or "").strip()
            if not code_s or code_s in latest_by_code:
                continue
            latest_by_code[code_s] = {
                "pe_ttm": pe_ttm or 0,
                "profit_growth": profit_growth_yoy or 0,
                "revenue_growth": revenue_growth_yoy or 0,
                "roe": roe or 0,
                "table_exists": True,
            }

        out: dict[str, dict] = {}
        for code in codes:
            out[code] = latest_by_code.get(code) or {
                "pe_ttm": 0,
                "profit_growth": 0,
                "revenue_growth": 0,
                "roe": 0,
                "table_exists": False,
            }
        return out

    def get_fundamentals(self, code: str, target_date: date) -> dict:
        """
        获取股票基本面数据
        如果financial_reports表不存在，返回空数据（跳过基本面筛选）
        """
        code = str(code or "").strip()
        if not code:
            return {"pe_ttm": 0, "profit_growth": 0, "revenue_growth": 0, "roe": 0, "table_exists": False}

        if self._has_financial_reports is False:
            return {"pe_ttm": 0, "profit_growth": 0, "revenue_growth": 0, "roe": 0, "table_exists": False}

        conn = self._conn()
        cursor = conn.cursor()

        if self._has_financial_reports is None:
            cursor.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='financial_reports' LIMIT 1"
            )
            self._has_financial_reports = bool(cursor.fetchone())

        if not bool(self._has_financial_reports):
            conn.close()
            return {"pe_ttm": 0, "profit_growth": 0, "revenue_growth": 0, "roe": 0, "table_exists": False}
        
        # 从financial_reports表获取数据
        try:
            cursor.execute("""
                SELECT pe_ttm, profit_growth_yoy, revenue_growth_yoy, roe
                FROM financial_reports
                WHERE code = ? AND report_date <= ?
                ORDER BY report_date DESC LIMIT 1
            """, (code, target_date.isoformat()))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return {
                    'pe_ttm': row[0] or 0,
                    'profit_growth': row[1] or 0,
                    'revenue_growth': row[2] or 0,
                    'roe': row[3] or 0,
                    'table_exists': True
                }
        except Exception:
            pass
        
        conn.close()
        return {'pe_ttm': 0, 'profit_growth': 0, 'revenue_growth': 0, 'roe': 0, 'table_exists': False}

    def check_fundamentals(self, fundamentals: dict) -> tuple[bool, float, list]:
        """
        检查基本面是否达标
        如果表不存在，自动通过检查
        返回: (是否达标, 基本面得分, 原因列表)
        """
        # v16: 如果financial_reports表不存在，跳过基本面检查
        if not fundamentals.get('table_exists', False):
            return True, 50, ["基本面数据不可用，跳过筛选"]
        
        score = 0
        reasons = []
        passed = True
        
        pe = fundamentals.get('pe_ttm', 0)
        profit_growth = fundamentals.get('profit_growth', 0)
        revenue_growth = fundamentals.get('revenue_growth', 0)
        roe = fundamentals.get('roe', 0)
        
        # PE检查
        if 0 < pe < self.MAX_PE:
            score += 20
            reasons.append(f"PE{pe:.1f}合理")
        elif pe <= 0:
            # 亏损但高增长也可接受
            if profit_growth > 30:
                score += 10
                reasons.append("亏损但高增长")
            else:
                passed = False
                reasons.append(f"PE无效且无高增长")
        else:
            score += 5
            reasons.append(f"PE{pe:.1f}偏高")
        
        # 净利润增速
        if profit_growth >= self.MIN_PROFIT_GROWTH:
            score += 30
            reasons.append(f"净利增{profit_growth:.1f}%")
        elif profit_growth > 0:
            score += 15
            reasons.append(f"净利增{profit_growth:.1f}%（偏低）")
        else:
            score += 5
            reasons.append(f"净利下滑{profit_growth:.1f}%")
        
        # 营收增速
        if revenue_growth >= 10:
            score += 20
            reasons.append(f"营收增{revenue_growth:.1f}%")
        elif revenue_growth > 0:
            score += 10
        
        # ROE
        if roe >= self.MIN_ROE:
            score += 30
            reasons.append(f"ROE{roe:.1f}%")
        elif roe > 0:
            score += 15
        
        return passed, score, reasons

    # ================================================================
    # 原有方法（波浪判断、热门板块等）
    # ================================================================
    def detect_wave_phase(self, code: str, target_date: date) -> tuple[str, float]:
        """判断当前处于哪个波浪阶段"""
        conn = self._conn()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT close, volume, high, low FROM daily_prices
            WHERE code = ? AND trade_date <= ?
            ORDER BY trade_date DESC LIMIT 60
        """, (code, target_date.isoformat()))

        rows = cursor.fetchall()
        conn.close()

        if len(rows) < 30:
            return WavePhase.UNKNOWN.value, 0.0

        closes = [r[0] for r in rows if r[0] is not None]
        highs = [r[2] for r in rows if r[2] is not None]
        lows = [r[3] for r in rows if r[3] is not None]

        if len(closes) < 30:
            return WavePhase.UNKNOWN.value, 0.0

        # 找前期高点
        recent_high = max(highs[:20])
        recent_low = min(lows[:20])
        prev_high = max(highs[20:40]) if len(highs) >= 40 else recent_high * 0.9

        current_price = closes[0]
        price_change_20d = (current_price - closes[19]) / closes[19] * 100 if closes[19] > 0 else 0

        # 判断逻辑
        if current_price > prev_high * 1.02 and price_change_20d > 10:
            return WavePhase.WAVE_3.value, 0.8
        elif current_price > prev_high * 1.05 and price_change_20d > 20:
            return WavePhase.WAVE_5.value, 0.7
        elif current_price < recent_low * 1.05 and price_change_20d < -10:
            return WavePhase.WAVE_B.value, 0.6
        elif price_change_20d > 5:
            return WavePhase.WAVE_1.value, 0.5
        else:
            return WavePhase.UNKNOWN.value, 0.3

    def get_hot_sectors(self, target_date: date, top_n: int = 5, cursor: Optional[Any] = None) -> list[SectorHeat]:
        """获取热门板块 - v16增加人气消散过滤"""
        managed = cursor is None
        conn = self._conn() if managed else None
        cursor = (conn.cursor() if conn is not None else cursor)

        cursor.execute("""
            SELECT sector_lv1, MAX(sector_lv2) AS sector_name
            FROM stocks
            WHERE sector_lv1 IS NOT NULL AND sector_lv2 IS NOT NULL
            GROUP BY sector_lv1
        """)
        sector_name_by_code: dict[str, str] = {}
        for sec_code, sec_name in cursor.fetchall():
            sec_code = str(sec_code or "").strip()
            sec_name = str(sec_name or "").strip()
            if sec_code and sec_name:
                sector_name_by_code[sec_code] = sec_name

        recent_avg_by_sector: dict[str, float] = {}
        if bool(self.SECTOR_ACCEL_BONUS_ENABLED):
            recent_dates = self._recent_trading_dates(
                target_date, limit=max(1, int(self.SECTOR_ACCEL_LOOKBACK_TRADING_DAYS))
            )
            if recent_dates:
                placeholders = ",".join(["?"] * len(recent_dates))
                args: list[object] = [d.isoformat() for d in recent_dates]
                args.extend([float(self.MARKET_CAP_MIN), float(self.MARKET_CAP_MAX)])
                cursor.execute(
                    f"""
                    SELECT s.sector_lv1, AVG(dp.pct_change) as avg_change_recent
                    FROM stocks s
                    JOIN daily_prices dp ON s.code = dp.code
                    WHERE dp.trade_date IN ({placeholders})
                      AND s.total_market_cap > ? AND s.total_market_cap < ?
                      AND (s.is_delisted IS NULL OR s.is_delisted = 0)
                    GROUP BY s.sector_lv1
                    """,
                    tuple(args),
                )
                for sec, avg_recent in cursor.fetchall():
                    if sec:
                        recent_avg_by_sector[str(sec)] = float(avg_recent or 0.0)

        cursor.execute("""
            SELECT s.sector_lv1, COUNT(*) as stock_count,
                   AVG(dp.pct_change) as avg_change,
                   AVG(dp.volume) as avg_volume,
                   SUM(dp.amount) as total_amount
            FROM stocks s
            JOIN daily_prices dp ON s.code = dp.code
            WHERE dp.trade_date = ? 
              AND s.total_market_cap > ? AND s.total_market_cap < ?
              AND (s.is_delisted IS NULL OR s.is_delisted = 0)
            GROUP BY s.sector_lv1
            HAVING COUNT(*) >= 3
            ORDER BY avg_change DESC
            LIMIT ?
        """, (target_date.isoformat(), self.MARKET_CAP_MIN, 
              self.MARKET_CAP_MAX, top_n * 2))

        sectors = []
        for row in cursor.fetchall():
            sector, count, avg_change, avg_vol, total_amt = row
            sector_code = str(sector or "").strip()
            sector_display = sector_name_by_code.get(sector_code) or sector_code or str(sector)
            
            # v16: 检测板块人气消散
            cooldown_info = self.detect_sector_cooldown(sector, target_date, cursor=cursor)
            
            # 如果板块正在人气消散，降低评分或跳过
            if cooldown_info['cooldown_detected'] and cooldown_info['follower_weakness'] > 0.7:
                logger.info(f"板块 {sector} 人气消散，跟随股弱势{cooldown_info['follower_weakness']:.0%}")
                continue
            
            # 计算热度分
            heat_score = 50
            if avg_change > 2:
                heat_score += 30
            elif avg_change > 1:
                heat_score += 20
            elif avg_change > 0:
                heat_score += 10
            if bool(self.SECTOR_ACCEL_BONUS_ENABLED):
                avg_change_recent = float(recent_avg_by_sector.get(str(sector)) or 0.0)
                accel = float(avg_change or 0.0) - float(avg_change_recent)
                if accel >= 0.8:
                    heat_score += float(self.SECTOR_ACCEL_BONUS_HIGH)
                elif accel >= 0.3:
                    heat_score += float(self.SECTOR_ACCEL_BONUS_LOW)
            
            # 共振加分
            if cooldown_info['trend_state'] == 'rising':
                heat_score += 15
            
            sectors.append(SectorHeat(
                sector=sector,
                name=sector_display,
                heat_score=heat_score,
                momentum_5d=avg_change or 0,
                stock_count=count,
                trend_state=cooldown_info['trend_state'],
                leader_strength=cooldown_info['leader_strength'],
                follower_weakness=cooldown_info['follower_weakness']
            ))

        if conn is not None:
            conn.close()
        sectors.sort(key=lambda x: x.heat_score, reverse=True)
        return sectors[:top_n]

    def get_sector_candidates(self, sector: str, target_date: date, top_n: int = 3, cursor: Optional[Any] = None) -> list[StockCandidate]:
        """在热门板块中筛选龙头股 - v16增加基本面和共振检测"""
        managed = cursor is None
        conn = self._conn() if managed else None
        cursor = (conn.cursor() if conn is not None else cursor)
        cup_picks = self._cup_handle_picks(target_date) if bool(self.CUP_HANDLE_ENABLED) else set()

        cursor.execute("""
            SELECT s.code, s.name, s.total_market_cap, dp.close, dp.pct_change, dp.amount, dp.volume
            FROM stocks s
            JOIN daily_prices dp ON s.code = dp.code
            WHERE s.sector_lv1 = ? AND dp.trade_date = ?
              AND s.total_market_cap > ? AND s.total_market_cap < ?
              AND (s.is_delisted IS NULL OR s.is_delisted = 0)
              AND dp.close > 0
            ORDER BY dp.pct_change DESC
            LIMIT 20
        """, (sector, target_date.isoformat(), self.MARKET_CAP_MIN, self.MARKET_CAP_MAX))

        rows = cursor.fetchall()
        if not rows:
            if conn is not None:
                conn.close()
            return []

        staged = []
        top_rows = rows[:20]
        top_codes: list[str] = []
        for code, _name, _mkt_cap, _close, _pct_chg, _amount, _volume in top_rows:
            code_s = str(code or "").strip()
            if code_s:
                top_codes.append(code_s)

        fundamentals_by_code = self._get_fundamentals_batch(cursor, top_codes, target_date)

        history_by_code: dict[str, list[tuple[Any, Any, Any, Any]]] = {}
        wave_phase_by_code: dict[str, tuple[str, float]] = {}
        rows_by_code: dict[str, list[tuple[Any, Any, Any, Any]]] = {}
        if top_codes:
            placeholders = ",".join(["?"] * len(top_codes))
            cursor.execute(
                f"""
                SELECT code, trade_date, close, volume, amount, high, low, rn FROM (
                    SELECT code, trade_date, close, volume, amount, high, low,
                           row_number() OVER (PARTITION BY code ORDER BY trade_date DESC) as rn
                    FROM daily_prices
                    WHERE trade_date <= ?
                      AND code IN ({placeholders})
                )
                WHERE rn <= 60
                ORDER BY code, rn
                """,
                (target_date.isoformat(), *top_codes),
            )
            for code, trade_date, close, volume, amount, high, low, rn in cursor.fetchall():
                code_s = str(code or "").strip()
                if not code_s:
                    continue
                rows60 = rows_by_code.get(code_s)
                if rows60 is None:
                    rows60 = []
                    rows_by_code[code_s] = rows60
                if len(rows60) < 60:
                    rows60.append((close, volume, high, low))

                if int(rn or 0) <= 30:
                    hist = history_by_code.get(code_s)
                    if hist is None:
                        hist = []
                        history_by_code[code_s] = hist
                    if len(hist) < 30:
                        hist.append((trade_date, close, volume, amount))

            for code_s, rows60 in rows_by_code.items():
                if len(rows60) < 30:
                    wave_phase_by_code[code_s] = (WavePhase.UNKNOWN.value, 0.0)
                    continue
                closes60 = [r[0] for r in rows60 if r[0] is not None]
                highs60 = [r[2] for r in rows60 if r[2] is not None]
                lows60 = [r[3] for r in rows60 if r[3] is not None]
                if len(closes60) < 30 or len(highs60) < 20 or len(lows60) < 20:
                    wave_phase_by_code[code_s] = (WavePhase.UNKNOWN.value, 0.0)
                    continue
                recent_high = max(highs60[:20])
                recent_low = min(lows60[:20])
                prev_high = max(highs60[20:40]) if len(highs60) >= 40 else recent_high * 0.9
                current_price = closes60[0]
                base_20 = closes60[19]
                price_change_20d = (current_price - base_20) / base_20 * 100 if base_20 and base_20 > 0 else 0
                if current_price > prev_high * 1.02 and price_change_20d > 10:
                    wave_phase_by_code[code_s] = (WavePhase.WAVE_3.value, 0.8)
                elif current_price > prev_high * 1.05 and price_change_20d > 20:
                    wave_phase_by_code[code_s] = (WavePhase.WAVE_5.value, 0.7)
                elif current_price < recent_low * 1.05 and price_change_20d < -10:
                    wave_phase_by_code[code_s] = (WavePhase.WAVE_B.value, 0.6)
                elif price_change_20d > 5:
                    wave_phase_by_code[code_s] = (WavePhase.WAVE_1.value, 0.5)
                else:
                    wave_phase_by_code[code_s] = (WavePhase.UNKNOWN.value, 0.3)

        weekly_ret_by_code: dict[str, dict] = {}
        if top_codes:
            start_date = target_date - timedelta(days=int(self.WEEKLY_DUCK_HEAD_LOOKBACK_DAYS))
            placeholders = ",".join(["?"] * len(top_codes))
            cursor.execute(
                f"""
                SELECT code, trade_date, close
                FROM daily_prices
                WHERE code IN ({placeholders})
                  AND trade_date BETWEEN ? AND ?
                  AND close IS NOT NULL
                ORDER BY code, trade_date ASC
                """,
                (*top_codes, start_date.isoformat(), target_date.isoformat()),
            )
            rows_by_code_asc: dict[str, list[tuple[Any, Any]]] = {}
            for code, trade_date, close in cursor.fetchall():
                code_s = str(code or "").strip()
                if not code_s:
                    continue
                lst = rows_by_code_asc.get(code_s)
                if lst is None:
                    lst = []
                    rows_by_code_asc[code_s] = lst
                lst.append((trade_date, close))

            for code_s in top_codes:
                raw_rows = rows_by_code_asc.get(code_s) or []
                if raw_rows:
                    self._ensure_no_lookahead_trade_dates(
                        raw_rows, target_date=target_date, context=f"_weekly_series_view({code_s})"
                    )

                buckets: dict[tuple[int, int], dict] = {}
                for trade_date, close in raw_rows:
                    d = date.fromisoformat(str(trade_date))
                    iso = d.isocalendar()
                    key = (int(iso.year), int(iso.week))
                    b = buckets.get(key)
                    if b is None:
                        b = {"last_date": d, "close": float(close), "min_close": float(close)}
                        buckets[key] = b
                    else:
                        b["last_date"] = d
                        b["close"] = float(close)
                        b["min_close"] = min(float(b["min_close"]), float(close))

                weeks = sorted(buckets.keys())
                series = []
                for y, w in weeks:
                    b = buckets[(y, w)]
                    series.append(
                        {
                            "iso_year": int(y),
                            "iso_week": int(w),
                            "last_date": b["last_date"].isoformat(),
                            "close": float(b["close"]),
                            "min_close": float(b["min_close"]),
                        }
                    )

                if series:
                    self._weekly_duck_head_cache[(str(code_s), target_date.isoformat())] = {
                        "status": "ok",
                        "series": series,
                    }

                closes_w = [
                    float(x["close"])
                    for x in series
                    if isinstance(x, dict) and x.get("close") is not None
                ]
                if len(closes_w) < 16:
                    weekly_ret_by_code[code_s] = {"status": "insufficient", "weeks": len(closes_w)}
                    continue
                t = len(closes_w) - 1
                def _ret(k: int) -> float:
                    if t - k < 0:
                        return 0.0
                    base = float(closes_w[t - k])
                    if base <= 0:
                        return 0.0
                    return (float(closes_w[t]) / base - 1.0) * 100.0
                weekly_ret_by_code[code_s] = {
                    "status": "ok",
                    "ret_1w": _ret(1),
                    "ret_4w": _ret(4),
                    "ret_12w": _ret(12),
                }

        for _i, (code, name, mkt_cap, close, pct_chg, amount, volume) in enumerate(top_rows):
            reasons = []
            base_score = 0.0
            code = str(code or "").strip()
            cup_ok = code in cup_picks

            # v16: 基本面检查
            fundamentals = fundamentals_by_code.get(code) or {
                "pe_ttm": 0,
                "profit_growth": 0,
                "revenue_growth": 0,
                "roe": 0,
                "table_exists": False,
            }
            fund_passed, fund_score, fund_reasons = self.check_fundamentals(fundamentals)
            
            if not fund_passed:
                continue  # 基本面不达标直接跳过
            
            base_score += float(fund_score) * 0.3  # 基本面占30%
            reasons.extend(fund_reasons)

            structure = self._structure_confirm(code=str(code), target_date=target_date)
            if not structure.get("passed"):
                continue
            reasons.extend(list(structure.get("reasons") or []))

            if cup_ok:
                base_score += float(self.CUP_HANDLE_SCORE_BONUS)
                if "杯柄确认（cup_handle_v4）" not in reasons:
                    reasons.append("杯柄确认（cup_handle_v4）")

            history = history_by_code.get(code) or []

            self._ensure_no_lookahead_trade_dates(history, target_date=target_date, context=f"get_sector_candidates.history({code})")

            if len(history) < 20:
                continue

            closes = [h[1] for h in history if h[1] is not None]
            vols = [h[2] for h in history if h[2] is not None]

            # 价格位置
            price_position = 50
            if len(closes) >= 20:
                high_20 = max(closes[:20])
                low_20 = min(closes[:20])
                price_position = (close - low_20) / (high_20 - low_20) * 100 if high_20 > low_20 else 50

                if 60 <= price_position <= 90:
                    base_score += 20
                    reasons.append(f"价格位置{price_position:.0f}%（突破区间）")
                elif 40 <= price_position < 60:
                    base_score += 12

            # 波浪阶段
            wave_phase, wave_confidence = wave_phase_by_code.get(code) or (WavePhase.UNKNOWN.value, 0.0)
            if wave_phase == WavePhase.WAVE_3.value:
                base_score += 20
                reasons.append(f"3浪主升浪")
            elif wave_phase == WavePhase.WAVE_1.value:
                base_score += 15
                reasons.append(f"1浪启动")

            # v16: 同频共振检测
            resonance = 0.5
            if len(closes) >= 10 and closes[4] and closes[9] and closes[4] > 0 and closes[9] > 0:
                stock_ret_5d = (closes[0] - closes[4]) / closes[4] * 100
                stock_ret_10d = (closes[0] - closes[9]) / closes[9] * 100
                if 2 <= stock_ret_5d <= 15:
                    resonance += 0.3
                if 2 <= stock_ret_10d <= 20:
                    resonance += 0.2
            resonance = min(1.0, float(resonance))
            if resonance >= 0.7:
                base_score += 15
                reasons.append(f"同频共振{resonance:.0%}")
            elif resonance >= 0.5:
                base_score += 8
                reasons.append(f"共振{resonance:.0%}")

            # 温和放量
            avg_vol_5d = np.mean(vols[1:6]) if len(vols) >= 6 else np.mean(vols[1:])
            vol_ratio = vols[0] / avg_vol_5d if avg_vol_5d > 0 else 1.0
            if 1.0 < vol_ratio <= 2.0:
                base_score += 15
                reasons.append(f"温和放量{vol_ratio:.1f}倍")

            # 5日涨幅
            ret_5d = (closes[0] - closes[4]) / closes[4] * 100 if len(closes) >= 5 and closes[4] > 0 else 0
            if 2 <= ret_5d <= 10:
                base_score += 10
                reasons.append(f"5日涨{ret_5d:.1f}%（适中）")

            # 均线趋势
            if len(closes) >= 20:
                ma5 = np.mean(closes[:5])
                ma10 = np.mean(closes[:10])
                ma20 = np.mean(closes[:20])
                if close > ma5 > ma10 > ma20:
                    base_score += 10
                    reasons.append("均线多头排列")
                elif ma5 > ma10 and close > ma5:
                    base_score += 6

            # 市值
            mkt_cap_yi = mkt_cap / 1e8
            if 200 <= mkt_cap_yi <= 300:
                base_score += 10
            elif 300 < mkt_cap_yi <= 350:
                base_score += 7

            weekly_ret = weekly_ret_by_code.get(str(code)) or self._weekly_returns_view(str(code), target_date)
            if weekly_ret.get("status") == "ok":
                strength_score = (
                    float(weekly_ret.get("ret_1w") or 0.0) * 0.45
                    + float(weekly_ret.get("ret_4w") or 0.0) * 0.35
                    + float(weekly_ret.get("ret_12w") or 0.0) * 0.2
                )
            else:
                ret_20d = (closes[0] - closes[19]) / closes[19] * 100 if len(closes) >= 20 and closes[19] > 0 else 0
                strength_score = (
                    float(pct_chg or 0.0) * 0.45
                    + float(ret_5d or 0.0) * 0.35
                    + float(ret_20d or 0.0) * 0.2
                )

            staged.append(
                {
                    "code": str(code),
                    "name": str(name),
                    "mkt_cap": float(mkt_cap or 0.0),
                    "close": float(close or 0.0),
                    "pct_chg": float(pct_chg or 0.0),
                    "fundamentals": fundamentals,
                    "base_score": float(base_score),
                    "reasons": reasons,
                    "wave_phase": wave_phase,
                    "ret_5d": float(ret_5d),
                    "vol_ratio": float(vol_ratio),
                    "price_position": float(price_position),
                    "resonance": float(resonance),
                    "strength_score": float(strength_score),
                    "cup_ok": bool(cup_ok),
                }
            )

        if conn is not None:
            conn.close()
        if not staged:
            return []

        staged.sort(key=lambda x: float(x.get("strength_score") or 0.0), reverse=True)
        sector_avg_strength = float(np.mean([float(x.get("strength_score") or 0.0) for x in staged])) if staged else 0.0
        role_by_code: dict[str, str] = {}
        for idx, item in enumerate(staged):
            if idx <= 1:
                role_by_code[str(item["code"])] = "龙头"
            elif idx <= 3:
                role_by_code[str(item["code"])] = "中军"
            else:
                role_by_code[str(item["code"])] = "跟随"

        candidates: list[StockCandidate] = []
        for item in staged:
            code = str(item["code"])
            role = role_by_code.get(code) or "跟随"
            score = float(item["base_score"] or 0.0)
            reasons = list(item.get("reasons") or [])
            rel_delta = float(item.get("strength_score") or 0.0) - float(sector_avg_strength)
            bonus_cap = float(self.RELATIVE_STRENGTH_BONUS_CAP)
            if bonus_cap > 0 and rel_delta > 0:
                score += min(bonus_cap, float(rel_delta))
                reasons.append(f"相对板块强度+{rel_delta:.1f}")
            if role == "龙头":
                score += 15
                reasons.append("板块龙头（多因子）")
            elif role == "中军":
                score += 8
                reasons.append("板块中军（多因子）")

            mkt_cap_yi = float(item.get("mkt_cap") or 0.0) / 1e8
            fundamentals = item.get("fundamentals") or {}
            candidates.append(
                StockCandidate(
                    code=code,
                    name=str(item.get("name") or ""),
                    sector=sector,
                    market_cap_yi=round(mkt_cap_yi, 1),
                    role=role,
                    buy_score=float(score),
                    buy_reasons=reasons,
                    wave_phase=str(item.get("wave_phase") or ""),
                    ret_5d=round(float(item.get("ret_5d") or 0.0), 2),
                    vol_ratio=round(float(item.get("vol_ratio") or 0.0), 2),
                    price_position=round(float(item.get("price_position") or 0.0), 1),
                    pe_ttm=fundamentals.get('pe_ttm', 0),
                    profit_growth=fundamentals.get('profit_growth', 0),
                    revenue_growth=fundamentals.get('revenue_growth', 0),
                    roe=fundamentals.get('roe', 0),
                    sector_resonance=round(float(item.get("resonance") or 0.0), 2),
                    cup_handle_ok=bool(item.get("cup_ok") or False),
                )
            )

        candidates.sort(key=lambda x: x.buy_score, reverse=True)
        return candidates[:top_n]

    def get_global_candidates(
        self,
        target_date: date,
        top_n: int = 10,
        *,
        exclude_sectors: Optional[set[str]] = None,
        exclude_codes: Optional[set[str]] = None,
    ) -> list[StockCandidate]:
        """跨板块机会扫描：从全市场（同一市值范围）筛选高分候选，不依赖热门板块列表。"""
        exclude_sectors = exclude_sectors or set()
        exclude_codes = exclude_codes or set()

        conn = self._conn()
        cursor = conn.cursor()
        cup_picks = self._cup_handle_picks(target_date) if bool(self.CUP_HANDLE_ENABLED) else set()

        cursor.execute(
            """
            SELECT s.code, s.name, s.sector_lv1, s.total_market_cap,
                   dp.close, dp.pct_change, dp.amount, dp.volume
            FROM stocks s
            JOIN daily_prices dp ON s.code = dp.code
            WHERE dp.trade_date = ?
              AND s.total_market_cap > ? AND s.total_market_cap < ?
              AND (s.is_delisted IS NULL OR s.is_delisted = 0)
              AND dp.close > 0
            ORDER BY dp.pct_change DESC
            LIMIT ?
            """,
            (
                target_date.isoformat(),
                self.MARKET_CAP_MIN,
                self.MARKET_CAP_MAX,
                int(self.CROSS_SECTOR_SCAN_LIMIT),
            ),
        )
        rows = cursor.fetchall()
        if not rows:
            conn.close()
            return []

        staged: list[dict] = []
        for code, name, sector, mkt_cap, close, pct_chg, amount, volume in rows:
            code = str(code)
            sector = str(sector or "").strip()
            if not sector:
                continue
            if code in exclude_codes:
                continue
            if sector in exclude_sectors:
                continue

            reasons: list[str] = []
            base_score = 0.0
            cup_ok = str(code) in cup_picks

            fundamentals = self.get_fundamentals(code, target_date)
            fund_passed, fund_score, fund_reasons = self.check_fundamentals(fundamentals)
            if not fund_passed:
                continue
            base_score += float(fund_score) * 0.3
            reasons.extend(fund_reasons)

            structure = self._structure_confirm(code=str(code), target_date=target_date)
            if not structure.get("passed"):
                continue
            reasons.extend(list(structure.get("reasons") or []))

            if cup_ok:
                base_score += float(self.CUP_HANDLE_SCORE_BONUS)
                if "杯柄确认（cup_handle_v4）" not in reasons:
                    reasons.append("杯柄确认（cup_handle_v4）")

            cursor.execute(
                """
                SELECT trade_date, close, volume, amount FROM daily_prices
                WHERE code = ? AND trade_date <= ?
                ORDER BY trade_date DESC LIMIT 30
                """,
                (code, target_date.isoformat()),
            )
            history = cursor.fetchall()
            self._ensure_no_lookahead_trade_dates(history, target_date=target_date, context=f"get_global_candidates.history({code})")
            if len(history) < 20:
                continue

            closes = [h[1] for h in history if h[1] is not None]
            vols = [h[2] for h in history if h[2] is not None]
            if len(closes) < 20 or len(vols) < 6:
                continue

            price_position = 50.0
            high_20 = max(closes[:20])
            low_20 = min(closes[:20])
            if high_20 > low_20:
                price_position = (float(close) - low_20) / (high_20 - low_20) * 100.0
            if 60 <= price_position <= 90:
                base_score += 20
                reasons.append(f"价格位置{price_position:.0f}%（突破区间）")
            elif 40 <= price_position < 60:
                base_score += 12

            wave_phase, wave_confidence = self.detect_wave_phase(code, target_date)
            if wave_phase == WavePhase.WAVE_3.value:
                base_score += 20
                reasons.append("3浪主升浪")
            elif wave_phase == WavePhase.WAVE_1.value:
                base_score += 15
                reasons.append("1浪启动")

            resonance = self.check_resonance(code, sector, target_date)
            if resonance >= 0.7:
                base_score += 15
                reasons.append(f"同频共振{resonance:.0%}")
            elif resonance >= 0.5:
                base_score += 8
                reasons.append(f"共振{resonance:.0%}")

            avg_vol_5d = np.mean(vols[1:6])
            vol_ratio = float(vols[0]) / float(avg_vol_5d) if avg_vol_5d > 0 else 1.0
            if 1.0 < vol_ratio <= 2.0:
                base_score += 15
                reasons.append(f"温和放量{vol_ratio:.1f}倍")

            ret_5d = (
                (float(closes[0]) - float(closes[4])) / float(closes[4]) * 100.0
                if float(closes[4]) > 0
                else 0.0
            )
            if 2 <= ret_5d <= 10:
                base_score += 10
                reasons.append(f"5日涨{ret_5d:.1f}%（适中）")

            ma5 = np.mean(closes[:5])
            ma10 = np.mean(closes[:10])
            ma20 = np.mean(closes[:20])
            if float(close) > ma5 > ma10 > ma20:
                base_score += 10
                reasons.append("均线多头排列")
            elif ma5 > ma10 and float(close) > ma5:
                base_score += 6

            mkt_cap_yi = float(mkt_cap) / 1e8
            if 200 <= mkt_cap_yi <= 300:
                base_score += 10
            elif 300 < mkt_cap_yi <= 350:
                base_score += 7

            weekly_ret = self._weekly_returns_view(code, target_date)
            if weekly_ret.get("status") == "ok":
                strength_score = (
                    float(weekly_ret.get("ret_1w") or 0.0) * 0.45
                    + float(weekly_ret.get("ret_4w") or 0.0) * 0.35
                    + float(weekly_ret.get("ret_12w") or 0.0) * 0.2
                )
            else:
                ret_20d = (float(closes[0]) - float(closes[19])) / float(closes[19]) * 100.0 if float(closes[19]) > 0 else 0.0
                strength_score = (
                    float(pct_chg or 0.0) * 0.45
                    + float(ret_5d or 0.0) * 0.35
                    + float(ret_20d or 0.0) * 0.2
                )

            staged.append(
                {
                    "code": code,
                    "name": str(name or ""),
                    "sector": sector,
                    "mkt_cap": float(mkt_cap or 0.0),
                    "fundamentals": fundamentals,
                    "base_score": float(base_score),
                    "reasons": reasons,
                    "wave_phase": wave_phase,
                    "ret_5d": float(ret_5d),
                    "vol_ratio": float(vol_ratio),
                    "price_position": float(price_position),
                    "resonance": float(resonance),
                    "strength_score": float(strength_score),
                    "cup_ok": bool(cup_ok),
                }
            )

        conn.close()
        if not staged:
            return []

        by_sector: dict[str, list[dict]] = {}
        for item in staged:
            by_sector.setdefault(str(item.get("sector") or ""), []).append(item)

        sector_avg_strength: dict[str, float] = {}
        for sec, items in by_sector.items():
            sector_avg_strength[str(sec)] = float(
                np.mean([float(x.get("strength_score") or 0.0) for x in items]) if items else 0.0
            )

        role_by_code: dict[str, str] = {}
        for sec, items in by_sector.items():
            items.sort(key=lambda x: float(x.get("strength_score") or 0.0), reverse=True)
            for idx, item in enumerate(items):
                if idx <= 1:
                    role_by_code[str(item["code"])] = "龙头"
                elif idx <= 3:
                    role_by_code[str(item["code"])] = "中军"
                else:
                    role_by_code[str(item["code"])] = "跟随"

        candidates: list[StockCandidate] = []
        for item in staged:
            code = str(item["code"])
            sector = str(item.get("sector") or "")
            role = role_by_code.get(code) or "跟随"
            score = float(item.get("base_score") or 0.0)
            reasons = list(item.get("reasons") or [])
            rel_delta = float(item.get("strength_score") or 0.0) - float(sector_avg_strength.get(sector) or 0.0)
            bonus_cap = float(self.RELATIVE_STRENGTH_BONUS_CAP)
            if bonus_cap > 0 and rel_delta > 0:
                score += min(bonus_cap, float(rel_delta))
                reasons.append(f"相对板块强度+{rel_delta:.1f}")
            if role == "龙头":
                score += 15
                reasons.append("板块龙头（多因子）")
            elif role == "中军":
                score += 8
                reasons.append("板块中军（多因子）")

            mkt_cap_yi = float(item.get("mkt_cap") or 0.0) / 1e8
            fundamentals = item.get("fundamentals") or {}
            candidates.append(
                StockCandidate(
                    code=code,
                    name=str(item.get("name") or ""),
                    sector=sector,
                    market_cap_yi=round(mkt_cap_yi, 1),
                    role=role,
                    buy_score=float(score),
                    buy_reasons=reasons,
                    wave_phase=str(item.get("wave_phase") or ""),
                    ret_5d=round(float(item.get("ret_5d") or 0.0), 2),
                    vol_ratio=round(float(item.get("vol_ratio") or 0.0), 2),
                    price_position=round(float(item.get("price_position") or 0.0), 1),
                    pe_ttm=fundamentals.get("pe_ttm", 0),
                    profit_growth=fundamentals.get("profit_growth", 0),
                    revenue_growth=fundamentals.get("revenue_growth", 0),
                    roe=fundamentals.get("roe", 0),
                    sector_resonance=round(float(item.get("resonance") or 0.0), 2),
                    cup_handle_ok=bool(item.get("cup_ok") or False),
                )
            )

        candidates.sort(key=lambda x: x.buy_score, reverse=True)
        return candidates[: int(top_n)]

    def generate_buy_signals(self, target_date: date) -> dict:
        """生成买入信号 - v16增加市场情绪过滤"""
        # v16: 市场情绪检查
        if self.MARKET_FILTER_ENABLED:
            sentiment, market_score = self.get_market_sentiment(target_date)
            if market_score < self.MIN_MARKET_SCORE:
                logger.info(f"市场情绪{sentiment.value} ({market_score:.0f}分)，暂停买入")
                return {"buy_signals": [], "date": target_date.isoformat()}
            logger.info(f"市场情绪: {sentiment.value} ({market_score:.0f}分)")
        
        buy_signals = []
        conn = self._conn()
        cursor = conn.cursor()
        try:
            hot_sectors = self.get_hot_sectors(target_date, self.HOT_SECTOR_COUNT, cursor=cursor)
            logger.info(f"热门板块 Top {len(hot_sectors)}: {[s.sector for s in hot_sectors]}")

            for sh in hot_sectors:
                try:
                    candidates = self.get_sector_candidates(sh.sector, target_date, 2, cursor=cursor)  # v16: 每个板块只取前2
                    
                    for c in candidates:
                        required = float(self.BUY_THRESHOLD)
                        nonconfirm_bonus = float(self.CUP_HANDLE_NONCONFIRM_THRESHOLD_BONUS or 0.0)
                        if nonconfirm_bonus > 0 and not bool(getattr(c, "cup_handle_ok", False)):
                            required += nonconfirm_bonus
                        if c.buy_score >= required:
                            if c.role == "跟随":
                                logger.info(f"  跳过跟随股: {c.code} {c.name}")
                                continue

                            if c.sector_resonance < self.MIN_RESONANCE:
                                logger.info(f"  跳过共振不足: {c.code} {c.name} (共振{c.sector_resonance:.0%} < {self.MIN_RESONANCE:.0%})")
                                continue
                                
                            buy_signals.append({
                                "code": c.code,
                                "name": c.name,
                                "sector": c.sector,
                                "buy_score": c.buy_score,
                                "market_cap_yi": c.market_cap_yi,
                                "wave_phase": c.wave_phase,
                                "role": c.role,
                                "reasons": c.buy_reasons,
                                "pe": c.pe_ttm,
                                "profit_growth": c.profit_growth,
                                "resonance": c.sector_resonance,
                                "cup_handle_ok": bool(getattr(c, "cup_handle_ok", False)),
                            })
                except Exception as e:
                    logger.warning(f"板块 {sh.sector} 信号生成失败: {e}")
        finally:
            conn.close()

        if self.CROSS_SECTOR_SCAN_ENABLED and int(self.CROSS_SECTOR_MAX_SIGNALS) > 0:
            try:
                hot_sector_set = {str(s.sector) for s in hot_sectors}
                existing_codes = {str(s.get("code") or "") for s in buy_signals if isinstance(s, dict)}
                global_candidates = self.get_global_candidates(
                    target_date,
                    top_n=20,
                    exclude_sectors=hot_sector_set,
                    exclude_codes=existing_codes,
                )
                added = 0
                for c in global_candidates:
                    if added >= int(self.CROSS_SECTOR_MAX_SIGNALS):
                        break
                    if c.role == "跟随":
                        continue
                    if float(c.sector_resonance) < float(self.MIN_RESONANCE):
                        continue
                    if self.CROSS_SECTOR_WAVE3_ONLY and str(c.wave_phase) != WavePhase.WAVE_3.value:
                        continue
                    required = float(self.BUY_THRESHOLD) + float(self.CROSS_SECTOR_SCORE_MARGIN)
                    nonconfirm_bonus = float(self.CUP_HANDLE_NONCONFIRM_THRESHOLD_BONUS or 0.0)
                    if nonconfirm_bonus > 0 and not bool(getattr(c, "cup_handle_ok", False)):
                        required += nonconfirm_bonus
                    if float(c.buy_score) < required:
                        continue
                    buy_signals.append(
                        {
                            "code": c.code,
                            "name": c.name,
                            "sector": c.sector,
                            "buy_score": c.buy_score,
                            "market_cap_yi": c.market_cap_yi,
                            "wave_phase": c.wave_phase,
                            "role": c.role,
                            "reasons": ["跨板块扫描"] + list(c.buy_reasons),
                            "pe": c.pe_ttm,
                            "profit_growth": c.profit_growth,
                            "resonance": c.sector_resonance,
                            "cross_sector": True,
                            "cup_handle_ok": bool(getattr(c, "cup_handle_ok", False)),
                        }
                    )
                    added += 1
            except Exception as e:
                logger.warning(f"跨板块扫描失败: {e}")

        return {"buy_signals": buy_signals, "date": target_date.isoformat()}

    def check_sell_signal_v2(self, trade: TradeRecord, current_date: date) -> Optional[SellSignal]:
        """v16: 优化卖出信号 - 增加板块人气消散检测"""
        sell_price = self._get_price(trade.code, current_date)
        if not sell_price:
            return None

        # 更新峰值价格
        if sell_price > trade.peak_price:
            trade.peak_price = sell_price

        peak_return = (trade.peak_price - trade.buy_price) / trade.buy_price * 100
        current_return = (sell_price - trade.buy_price) / trade.buy_price * 100
        hold_days = self._count_trading_days(date.fromisoformat(trade.buy_date), current_date)

        trailing_active = bool(peak_return >= self.TRAILING_PROFIT_LEVEL)

        cooldown_confirm = self._sector_cooldown_confirmed(trade.sector, current_date)
        cooldown_info = cooldown_confirm.get("latest") if isinstance(cooldown_confirm, dict) else {}
        sector_cooling = bool(isinstance(cooldown_confirm, dict) and cooldown_confirm.get("confirmed"))

        # 优先级1: 板块人气消散（确认后直接离场）
        if sector_cooling:
            trend_state = str(cooldown_info.get("trend_state") or "")
            follower_weakness = float(cooldown_info.get("follower_weakness") or 0.0)
            leader_strength = float(cooldown_info.get("leader_strength") or 0.0)
            details = (
                f"板块人气消散离场 当前{current_return:.1f}% | 趋势:{trend_state or '未知'} "
                f"| 跟随弱势{follower_weakness:.0%} | 龙头强度{leader_strength:.0%}"
            )
            return SellSignal("sector_cooldown", 0.95, details)

        # 优先级2: 止损（亏损止损 + 盈利后的追踪止损）
        if trailing_active:
            dd_from_peak = (sell_price - trade.peak_price) / max(trade.peak_price, 1e-9) * 100.0
            if dd_from_peak <= float(self.TRAILING_STOP_PCT):
                details = f"追踪止损{dd_from_peak:.1f}%（自高点回撤） 当前{current_return:.1f}%"
                return SellSignal("stop_loss", 0.95, details)
        else:
            if current_return <= float(self.STOP_LOSS_PCT):
                days = int(self.STOP_LOSS_CONFIRM_DAYS)
                if days <= 1 or self._is_return_below_threshold_consecutive(
                    code=trade.code,
                    current_date=current_date,
                    buy_price=trade.buy_price,
                    threshold_pct=float(self.STOP_LOSS_PCT),
                    days=days,
                ):
                    return SellSignal("stop_loss", 0.95, f"止损{current_return:.1f}%")

        return None

    def run_backtest(self, start_date: date, end_date: date, 
                     initial_capital: float = 1000000.0, 
                     rebalance_days: int = 10) -> dict:
        """运行完整回测"""
        logger.info(f"低频交易回测 v16: {start_date} ~ {end_date}")

        trading_dates = self._get_trading_dates(start_date, end_date)
        logger.info(f"交易日: {len(trading_dates)}")

        capital = initial_capital
        positions: dict[str, TradeRecord] = {}
        all_trades: list[TradeRecord] = []
        daily_values = []

        for i, current_date in enumerate(trading_dates):
            # 检查持仓卖出信号
            closed_codes = []
            for code, trade in list(positions.items()):
                sell = self.check_sell_signal_v2(trade, current_date)
                if sell:
                    if sell.reason == "partial_profit" and not trade.partial_taken:
                        profit_shares = trade.shares // 2
                        if profit_shares > 0:
                            sell_price = self._get_price(code, current_date)
                            proceeds = profit_shares * sell_price
                            capital += proceeds
                            trade.shares -= profit_shares
                            trade.shares_sold += profit_shares
                            trade.partial_taken = True
                            partial_ret = (sell_price - trade.buy_price) / trade.buy_price * 100
                            partial_trade = TradeRecord(
                                code=trade.code, name=trade.name, sector=trade.sector,
                                buy_date=trade.buy_date, sell_date=current_date.isoformat(),
                                buy_price=trade.buy_price, sell_price=sell_price,
                                shares=profit_shares, return_pct=round(partial_ret, 2),
                                hold_days=self._count_trading_days(date.fromisoformat(trade.buy_date), current_date),
                                sell_reason=f"分批止盈50%", status="closed")
                            all_trades.append(partial_trade)
                            logger.info(f"  分批止盈: {code} 卖出{profit_shares}股 当前盈利{partial_ret:.1f}%")
                            continue
                    else:
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

            # 生成买入信号
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
                                code=sig["code"],
                                name=sig["name"],
                                sector=sig["sector"],
                                buy_date=current_date.isoformat(),
                                buy_price=price,
                                shares=shares,
                                buy_score=sig["buy_score"],
                                wave_phase=sig["wave_phase"],
                                peak_price=price,
                                role=sig.get("role", ""),  # v16: 记录角色
                                status="open",
                            )
                            logger.info(f"  买入: {sig['code']} {sig['name']} | "
                                       f"评分:{sig['buy_score']} | {sig['wave_phase']} | "
                                       f"角色:{sig['role']} | 共振:{sig.get('resonance', 0):.0%}")
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

        # 平仓所有持仓
        for code, trade in positions.items():
            sell_price = self._get_price(code, trading_dates[-1])
            if sell_price:
                ret = (sell_price - trade.buy_price) / trade.buy_price * 100
                capital += sell_price * trade.shares
                trade.sell_date = trading_dates[-1].isoformat()
                trade.sell_price = sell_price
                trade.return_pct = round(ret, 2)
                trade.hold_days = self._count_trading_days(
                    date.fromisoformat(trade.buy_date), trading_dates[-1])
                trade.sell_reason = "回测结束平仓"
                trade.status = "closed"
                all_trades.append(trade)

        return self._calc_metrics(daily_values, all_trades, initial_capital)

    def _calc_metrics(self, daily_values, trades, initial_capital):
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

        win_trades = [t for t in trades if t.return_pct > 0]
        lose_trades = [t for t in trades if t.return_pct <= 0]
        win_rate = len(win_trades) / len(trades) * 100 if trades else 0
        avg_win = np.mean([t.return_pct for t in win_trades]) if win_trades else 0
        avg_loss = np.mean([t.return_pct for t in lose_trades]) if lose_trades else 0
        pl_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else float('inf')

        target_hits_30 = [t for t in trades if t.return_pct >= 30]  # v17opt: 核心目标30%+
        target_hit_rate_30 = len(target_hits_30) / len(trades) * 100 if trades else 0
        target_hits_50 = [t for t in trades if t.return_pct >= 50]
        target_hit_rate_50 = len(target_hits_50) / len(trades) * 100 if trades else 0

        sell_reasons = {}
        for t in trades:
            reason_key = t.sell_reason.split(":")[0].strip() if t.sell_reason else "unknown"
            sell_reasons[reason_key] = sell_reasons.get(reason_key, 0) + 1

        return {
            "strategy": "low_freq_v16_advanced",
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
            "avg_return_pct": round(np.mean([t.return_pct for t in trades]) if trades else 0, 2),
            "profit_loss_ratio": round(pl_ratio, 2),
            "target_hit_rate_30_pct": round(target_hit_rate_30, 2),  # v17opt: 核心指标30%+
            "target_hits_30": len(target_hits_30),
            "target_hit_rate_50_pct": round(target_hit_rate_50, 2),
            "target_hits_50": len(target_hits_50),
            "sell_reasons": sell_reasons,
            "recent_trades": [
                {"code": t.code, "name": t.name, "sector": t.sector,
                 "buy_date": t.buy_date, "sell_date": t.sell_date,
                 "return_pct": t.return_pct, "hold_days": t.hold_days,
                 "buy_score": t.buy_score, "wave_phase": t.wave_phase,
                 "sell_reason": t.sell_reason, "role": t.role}
                for t in trades[-20:]
            ],
        }

    def _get_trading_dates(self, start: date, end: date) -> list[date]:
        conn = self._conn()
        cursor = conn.execute(
            "SELECT DISTINCT trade_date FROM daily_prices WHERE trade_date BETWEEN ? AND ? ORDER BY trade_date",
            (start.isoformat(), end.isoformat()))
        dates = [date.fromisoformat(r[0]) for r in cursor.fetchall()]
        conn.close()
        return dates

    def _get_price(self, code: str, target_date: date) -> Optional[float]:
        conn = self._conn()
        cursor = conn.execute(
            "SELECT close FROM daily_prices WHERE code = ? AND trade_date = ?",
            (code, target_date.isoformat()))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else None

    def _count_trading_days(self, start: date, end: date) -> int:
        dates = self._get_trading_dates(start, end)
        return len(dates)


def main():
    engine = LowFreqTradingEngineV16()
    
    start_date = date(2024, 11, 26)
    end_date = date(2026, 5, 22)
    
    print(f"\n{'='*70}")
    print(f"低频量化交易系统 v17 (跟随股溃散预警+龙头雷达)")
    print(f"{'='*70}")
    print(f"回测区间: {start_date} ~ {end_date}")
    print(f"选股范围: 市值 200-400 亿")
    print(f"买入阈值: 确定性评分 ≥ {engine.BUY_THRESHOLD}")
    print(f"目标收益: ≥ {engine.TARGET_RETURN}%")
    print(f"持仓周期: {engine.MIN_HOLD_DAYS}-{engine.MAX_HOLD_DAYS} 天")
    print(f"止损线: {engine.STOP_LOSS_PCT}% (盈利>{engine.TRAILING_PROFIT_LEVEL}%后提高到{engine.TRAILING_STOP_PCT}%)")
    print(f"分批止盈: 盈利>{engine.PARTIAL_PROFIT_LEVEL}%时卖出{engine.PARTIAL_PROFIT_PCT}%仓位")
    print(f"基本面筛选: PE<{engine.MAX_PE}, 净利增>{engine.MIN_PROFIT_GROWTH}%, ROE>{engine.MIN_ROE}%")
    print(f"市场情绪过滤: {'启用' if engine.MARKET_FILTER_ENABLED else '禁用'}")
    print(f"{'='*70}\n")
    
    result = engine.run_backtest(start_date, end_date)
    
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
    print(f"\n交易次数: {result['total_trades']}")
    print(f"胜率: {result['win_rate_pct']:.2f}%")
    print(f"平均收益: {result['avg_return_pct']:.2f}%")
    print(f"盈亏比: {result['profit_loss_ratio']:.2f}")
    print(f"\n【核心目标】30%+收益达成率: {result['target_hit_rate_30_pct']:.2f}% ({result['target_hits_30']}/{result['total_trades']})")
    print(f"【核心目标】50%+收益达成率: {result['target_hit_rate_50_pct']:.2f}% ({result['target_hits_50']}/{result['total_trades']})")
    
    print(f"\n卖出原因分布:")
    for reason, count in result['sell_reasons'].items():
        print(f"  {reason}: {count}次")
    
    print(f"\n最近交易记录:")
    for t in result['recent_trades']:
        print(f"  {t['code']} {t['name']} | {t['buy_date']}→{t['sell_date']} | "
              f"{t['hold_days']}天 | {t['return_pct']:+.1f}% | {t.get('role', '')}")
    
    print(f"\n{'='*70}\n")
    
    # 保存结果
    import json
    output_dir = Path("var/backtest_results")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"lowfreq_v16_{start_date}_{end_date}.json"
    with open(output_file, 'w') as f:
        json.dump(result, f, indent=2, default=str)
    print(f"结果已保存: {output_file}")


if __name__ == "__main__":
    main()
