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
import json
import numpy as np
from pathlib import Path
from datetime import date, timedelta
from dataclasses import dataclass, field
from typing import Optional, Any
from enum import Enum

from neotrade3.cycle_intelligence import build_small_cycle_from_m1
from neotrade3.data_control import (
    D7TradingDayStatus,
    project_d1_daily_price_fact,
    project_d7_security_master_minimal,
    project_pf1_trading_profile,
)
from neotrade3.decision_engine import (
    build_entry_state_from_formal_inputs,
    build_identify_state_from_formal_inputs,
    build_m1_constraints_ref,
    build_tracking_state_from_formal_inputs,
)

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
    signal_source: str = ""
    soft_flags: list = field(default_factory=list)


@dataclass
class SellSignal:
    """卖出信号"""
    reason: str
    confidence: float = 0.0
    details: str = ""
    source_layer: str = "exit"
    exit_scope: str = "position_only"
    invalidated_reason: str = ""
    invalidated_window: str = ""


@dataclass
class LayerContract:
    """统一的分层契约输出。"""
    current_stage: str = ""
    decision: str = ""
    score: Optional[float] = None
    reasons: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    source_layer: str = ""
    next_action: str = ""
    last_transition: str = ""

    def to_payload(self) -> dict[str, Any]:
        payload = {
            "current_stage": str(self.current_stage or ""),
            "decision": str(self.decision or ""),
            "reasons": [str(x) for x in list(self.reasons or []) if str(x or "").strip()],
            "evidence": [str(x) for x in list(self.evidence or []) if str(x or "").strip()],
            "flags": [str(x) for x in list(self.flags or []) if str(x or "").strip()],
            "source_layer": str(self.source_layer or ""),
            "next_action": str(self.next_action or ""),
            "last_transition": str(self.last_transition or ""),
        }
        if self.score is not None:
            payload["score"] = float(self.score)
        return payload

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
    buy_price_ref: float = 0.0
    sell_price_ref: float = 0.0
    shares: int = 0
    shares_sold: int = 0
    hold_days: int = 0
    return_pct: float = 0.0
    net_return_pct: float = 0.0
    buy_fee: float = 0.0
    sell_fee: float = 0.0
    buy_score: float = 0.0
    wave_phase: str = ""
    buy_progress_label: str = ""
    peak_price: float = 0.0
    partial_taken: bool = False
    sell_reason: str = ""
    status: str = "open"
    role: str = ""  # v16: 记录买入时的角色
    market_top_watch_start_date: str = ""
    market_top_watch_expire_date: str = ""
    market_top_watch_hits: int = 0
    market_top_watch_last_reason: str = ""
    market_top_watch_last_hit_date: str = ""
    market_exit_state: str = ""
    market_exit_start_date: str = ""
    market_exit_expire_date: str = ""
    market_exit_hits: int = 0
    market_exit_last_reason: str = ""
    market_exit_last_hit_date: str = ""
    sector_exit_state: str = ""
    sector_exit_start_date: str = ""
    sector_exit_expire_date: str = ""
    sector_exit_hits: int = 0
    sector_exit_last_reason: str = ""
    sector_exit_last_hit_date: str = ""
    system_exit_grace_used: bool = False
    system_exit_grace_date: str = ""
    system_exit_grace_scope: str = ""
    system_exit_grace_reason: str = ""


@dataclass
class TradeCostModel:
    commission_rate: float = 0.0
    stamp_tax_rate: float = 0.0
    slippage_bps: float = 0.0
    min_commission: float = 0.0


@dataclass
class ExecutionConstraints:
    min_amount_cny: float = 0.0
    max_participation_rate: float = 1.0
    block_on_limit_up: bool = True
    block_on_limit_down: bool = True
    limit_up_pct: float = 9.8
    limit_down_pct: float = -9.8
    lot_size: int = 100


@dataclass
class LowFreqV16Config:
    version: str = "low_freq_v16_advanced"
    cost_model: TradeCostModel = field(default_factory=TradeCostModel)
    execution: ExecutionConstraints = field(default_factory=ExecutionConstraints)

    MARKET_CAP_MAX: float = 2500e8
    MARKET_CAP_MIN: float = 100e8
    BUY_THRESHOLD: float = 85.0
    MIN_RESONANCE: float = 0.7
    TARGET_RETURN: float = 30.0
    PARTIAL_PROFIT_LEVEL: float = 25.0
    PARTIAL_PROFIT_PCT: int = 50
    TRAILING_PROFIT_LEVEL: float = 20.0
    TRAILING_STOP_PCT: float = -5.0
    MIN_HOLD_DAYS: int = 15
    MAX_HOLD_DAYS: int = 75
    STOP_LOSS_PCT: float = -5.0
    HOT_SECTOR_COUNT: int = 5
    HOT_SECTOR_CANDIDATE_LIMIT: int = 12
    MAX_POSITIONS: int = 3
    EXECUTION_MODE: str = "unbounded_opportunity"
    REBALANCE_DAYS: int = 15
    BUY_SIGNAL_MEMORY_DAYS: int = 5
    MARKET_TOP_WATCH_WINDOW: int = 3
    MARKET_TOP_CONFIRM_HITS: int = 2
    MARKET_EXIT_CONFIRM_WINDOW: int = 5
    MARKET_EXIT_CONFIRM_HITS: int = 3
    MARKET_EXIT_MIN_DRAWDOWN_PCT: float = -4.0
    STOP_LOSS_CONFIRM_DAYS: int = 1
    SECTOR_COOLDOWN_CONFIRM_WINDOW: int = 3
    SECTOR_COOLDOWN_CONFIRM_HITS: int = 2
    SECTOR_EXIT_CONFIRM_WINDOW: int = 4
    SECTOR_EXIT_CONFIRM_HITS: int = 3
    LEADER_HOLD_MIN_PEAK_RETURN_PCT: float = 15.0
    LEADER_CONFIRM_EXTRA_HITS: int = 1
    SYSTEM_EXIT_GRACE_ENABLED: bool = True
    SYSTEM_EXIT_GRACE_MIN_PEAK_RETURN_PCT: float = 20.0
    SYSTEM_EXIT_GRACE_REQUIRE_POSITIVE_RETURN: bool = True
    SYSTEM_EXIT_GRACE_MARKET_MIN_PEAK_RETURN_PCT: float = 20.0
    SYSTEM_EXIT_GRACE_MARKET_MIN_CURRENT_PROFIT_PCT: float = 10.0
    SYSTEM_EXIT_GRACE_MARKET_MIN_PROFIT_KEEP_RATIO: float = 0.50
    SYSTEM_EXIT_GRACE_SECTOR_MIN_PEAK_RETURN_PCT: float = 10.0
    SYSTEM_EXIT_GRACE_SECTOR_MIN_CURRENT_PROFIT_PCT: float = 10.0
    SYSTEM_EXIT_GRACE_SECTOR_MIN_PROFIT_KEEP_RATIO: float = 0.60
    SYSTEM_EXIT_GRACE_SECTOR_MAX_HOLD_DAYS: int = 10
    CHASE_ENTRY_BLOCK_ENABLED: bool = True
    CHASE_ENTRY_NEAR_HIGH_RATIO: float = 0.98
    CHASE_ENTRY_PRE3_RUNUP_PCT: float = 8.0
    CHASE_ENTRY_PRE5_RUNUP_PCT: float = 12.0
    EXECUTION_SIGNAL_GATE_ENABLED: bool = True
    EXECUTION_FOLLOWER_MIN_BUY_SCORE: float = 75.0
    EXECUTION_UNKNOWN_WAVE_MIN_BUY_SCORE: float = 80.0
    EXECUTION_ELITE_MIN_BUY_SCORE: float = 80.0
    EXECUTION_ELITE_UNKNOWN_LEADER_MIN_BUY_SCORE: float = 90.0
    EXECUTION_RESERVATION_ENABLED: bool = True
    EXECUTION_RESERVATION_MEMORY_DAYS: int = 3
    EXECUTION_ROTATION_ENABLED: bool = False
    EXECUTION_ROTATION_MIN_SCORE_MARGIN: float = 12.0
    EXECUTION_ROTATION_MIN_EVIDENCE_COUNT: int = 2
    EXECUTION_ROTATION_MAX_CURRENT_RETURN_PCT: float = 25.0

    CROSS_SECTOR_SCAN_ENABLED: bool = True
    CROSS_SECTOR_MAX_SIGNALS: int = 40
    CROSS_SECTOR_CANDIDATE_TOP_N: int = 120
    CROSS_SECTOR_SCORE_MARGIN: float = 8.0
    CROSS_SECTOR_SCAN_LIMIT: int = 500
    CROSS_SECTOR_WAVE3_ONLY: bool = True
    CROSS_SECTOR_ALLOW_WAVE1: bool = True

    WEEKLY_DUCK_HEAD_ENABLED: bool = True
    WEEKLY_DUCK_HEAD_MA_SHORT: int = 5
    WEEKLY_DUCK_HEAD_MA_MID: int = 10
    WEEKLY_DUCK_HEAD_MA_LONG: int = 15
    WEEKLY_DUCK_HEAD_MIN_WEEKS: int = 20
    WEEKLY_DUCK_HEAD_PULLBACK_WEEKS: int = 3
    WEEKLY_DUCK_HEAD_BREAKOUT_LOOKBACK_WEEKS: int = 2
    WEEKLY_DUCK_HEAD_OVEREXTEND_PCT: float = 25.0
    WEEKLY_DUCK_HEAD_LOOKBACK_DAYS: int = 520

    NO_LOOKAHEAD_ENFORCED: bool = True

    CUP_HANDLE_ENABLED: bool = True
    CUP_HANDLE_SCREENER_ID: str = "cup_handle_v4"
    CUP_HANDLE_TOP_N: int = 50
    STRUCTURE_CONFIRM_MODE: str = "duck_only"
    CUP_HANDLE_SCORE_BONUS: float = 6.0
    CUP_HANDLE_NONCONFIRM_THRESHOLD_BONUS: float = 0.0

    MAX_PE: float = 50.0
    MIN_PROFIT_GROWTH: float = 10.0
    MIN_ROE: float = 8.0

    MARKET_FILTER_ENABLED: bool = False


class LowFreqTradingEngineV16:
    """低频量化交易引擎 v16 - 高级优化版"""

    # ===== 参数配置 =====
    COMMISSION_RATE = 0.0
    STAMP_TAX_RATE = 0.0
    SLIPPAGE_BPS = 0.0
    MIN_COMMISSION = 0.0

    EXEC_MIN_AMOUNT_CNY = 0.0
    EXEC_MAX_PARTICIPATION_RATE = 1.0
    EXEC_BLOCK_ON_LIMIT_UP = True
    EXEC_BLOCK_ON_LIMIT_DOWN = True
    EXEC_BLOCK_ONLY_ONE_PRICE_LIMIT = False
    EXEC_LIMIT_UP_PCT = 9.8
    EXEC_LIMIT_DOWN_PCT = -9.8
    EXEC_LOT_SIZE = 100

    MARKET_CAP_MAX = 2500e8
    MARKET_CAP_MIN = 100e8
    BUY_THRESHOLD = 85               # v16opt: 提高到85，更严格
    MIN_RESONANCE = 0.7              # v16opt: 新增共振度最低要求
    TARGET_RETURN = 30.0
    PARTIAL_PROFIT_LEVEL = 25.0
    PARTIAL_PROFIT_PCT = 50
    TRAILING_PROFIT_LEVEL = 20.0
    TRAILING_STOP_PCT = -5.0
    MIN_HOLD_DAYS = 15
    MAX_HOLD_DAYS = 75               # v17opt: 延长到75天，让趋势股跑完
    STOP_LOSS_PCT = -5.0
    HOT_SECTOR_COUNT = 5
    HOT_SECTOR_CANDIDATE_LIMIT = 12
    MAX_POSITIONS = 3
    REBALANCE_DAYS = 15              # v16opt: 调仓周期延长到15天
    BUY_SIGNAL_MEMORY_DAYS = 5
    MARKET_TOP_WATCH_WINDOW = 3
    MARKET_TOP_CONFIRM_HITS = 2
    MARKET_EXIT_CONFIRM_WINDOW = 5
    MARKET_EXIT_CONFIRM_HITS = 3
    MARKET_EXIT_MIN_DRAWDOWN_PCT = -4.0
    STOP_LOSS_CONFIRM_DAYS = 1
    SECTOR_COOLDOWN_CONFIRM_WINDOW = 3
    SECTOR_COOLDOWN_CONFIRM_HITS = 2
    SECTOR_EXIT_CONFIRM_WINDOW = 4
    SECTOR_EXIT_CONFIRM_HITS = 3
    LEADER_HOLD_MIN_PEAK_RETURN_PCT = 15.0
    LEADER_CONFIRM_EXTRA_HITS = 1
    SYSTEM_EXIT_GRACE_ENABLED = True
    SYSTEM_EXIT_GRACE_MIN_PEAK_RETURN_PCT = 20.0
    SYSTEM_EXIT_GRACE_REQUIRE_POSITIVE_RETURN = True
    SYSTEM_EXIT_GRACE_MARKET_MIN_PEAK_RETURN_PCT = 20.0
    SYSTEM_EXIT_GRACE_MARKET_MIN_CURRENT_PROFIT_PCT = 10.0
    SYSTEM_EXIT_GRACE_MARKET_MIN_PROFIT_KEEP_RATIO = 0.50
    SYSTEM_EXIT_GRACE_SECTOR_MIN_PEAK_RETURN_PCT = 10.0
    SYSTEM_EXIT_GRACE_SECTOR_MIN_CURRENT_PROFIT_PCT = 10.0
    SYSTEM_EXIT_GRACE_SECTOR_MIN_PROFIT_KEEP_RATIO = 0.60
    SYSTEM_EXIT_GRACE_SECTOR_MAX_HOLD_DAYS = 10
    CHASE_ENTRY_BLOCK_ENABLED = True
    CHASE_ENTRY_NEAR_HIGH_RATIO = 0.98
    CHASE_ENTRY_PRE3_RUNUP_PCT = 8.0
    CHASE_ENTRY_PRE5_RUNUP_PCT = 12.0
    EXECUTION_SIGNAL_GATE_ENABLED = True
    EXECUTION_FOLLOWER_MIN_BUY_SCORE = 75.0
    EXECUTION_UNKNOWN_WAVE_MIN_BUY_SCORE = 80.0
    EXECUTION_ELITE_MIN_BUY_SCORE = 80.0
    EXECUTION_ELITE_UNKNOWN_LEADER_MIN_BUY_SCORE = 90.0
    EXECUTION_RESERVATION_ENABLED = True
    EXECUTION_RESERVATION_MEMORY_DAYS = 3
    EXECUTION_ROTATION_ENABLED = False
    EXECUTION_ROTATION_MIN_SCORE_MARGIN = 12.0
    EXECUTION_ROTATION_MIN_EVIDENCE_COUNT = 2
    EXECUTION_ROTATION_MAX_CURRENT_RETURN_PCT = 25.0
    ROTATION_SCORE_DELTA = 8.0
    ROTATION_MIN_RETURN_PCT = -100.0

    CROSS_SECTOR_SCAN_ENABLED = True
    CROSS_SECTOR_MAX_SIGNALS = 40
    CROSS_SECTOR_CANDIDATE_TOP_N = 120
    CROSS_SECTOR_SCORE_MARGIN = 8.0
    CROSS_SECTOR_SCAN_LIMIT = 500
    CROSS_SECTOR_WAVE3_ONLY = True
    CROSS_SECTOR_ALLOW_WAVE1 = True

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

    def __init__(self, db_path: Path = DB_PATH, *, config: Optional[LowFreqV16Config] = None):
        self.db_path = db_path
        self.config = config or LowFreqV16Config()
        self._apply_config(self.config)
        self.project_root = Path(__file__).resolve().parent
        self._themes_snapshot_dir = self.project_root / "var" / "ledgers" / "team_themes"
        self._market_intelligence_config_dir = self.project_root / "config" / "market_intelligence"
        # v16: 缓存板块历史数据用于趋势判断
        self._sector_history_cache = {}
        self._weekly_duck_head_cache: dict[tuple[str, str], dict] = {}
        self._cup_handle_cache: dict[str, set[str]] = {}
        self._has_financial_reports: Optional[bool] = None
        self._sector_cooldown_cache: dict[tuple[str, str], dict] = {}
        self._indexes_ready = False
        self._sector_members_cache: dict[str, dict[str, Any]] = {}
        self._stock_concepts_cache: Optional[dict[str, list[dict[str, str]]]] = None
        self._penetration_keywords_cache: Optional[tuple[str, ...]] = None
        self._market_focus_cache: dict[tuple[str, str], dict[str, Any]] = {}
        self._nonempty_table_cache: dict[str, bool] = {}
        self._market_proxy_series_cache: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
        self._market_breadth_cache: dict[tuple[str, str], Optional[float]] = {}

    def _apply_config(self, config: LowFreqV16Config) -> None:
        cm = getattr(config, "cost_model", None)
        if isinstance(cm, TradeCostModel):
            self.COMMISSION_RATE = float(cm.commission_rate)
            self.STAMP_TAX_RATE = float(cm.stamp_tax_rate)
            self.SLIPPAGE_BPS = float(cm.slippage_bps)
            self.MIN_COMMISSION = float(cm.min_commission)
        ex = getattr(config, "execution", None)
        if isinstance(ex, ExecutionConstraints):
            self.EXEC_MIN_AMOUNT_CNY = float(ex.min_amount_cny)
            self.EXEC_MAX_PARTICIPATION_RATE = float(ex.max_participation_rate)
            self.EXEC_BLOCK_ON_LIMIT_UP = bool(ex.block_on_limit_up)
            self.EXEC_BLOCK_ON_LIMIT_DOWN = bool(ex.block_on_limit_down)
            self.EXEC_LIMIT_UP_PCT = float(ex.limit_up_pct)
            self.EXEC_LIMIT_DOWN_PCT = float(ex.limit_down_pct)
            self.EXEC_LOT_SIZE = int(ex.lot_size)
        for k, v in vars(config).items():
            if k in ("cost_model", "execution", "version"):
                continue
            try:
                setattr(self, str(k), v)
            except Exception:
                continue

    def get_config_snapshot(self) -> dict[str, Any]:
        cfg = self.config if isinstance(self.config, LowFreqV16Config) else LowFreqV16Config()
        out = {
            "version": str(getattr(cfg, "version", "low_freq_v16_advanced")),
            "execution_mode": self._resolve_execution_mode(),
        }
        cm = getattr(cfg, "cost_model", None)
        ex = getattr(cfg, "execution", None)
        base_cm = cm if isinstance(cm, TradeCostModel) else TradeCostModel()
        base_ex = ex if isinstance(ex, ExecutionConstraints) else ExecutionConstraints()
        out["cost_model"] = {
            "commission_rate": float(getattr(self, "COMMISSION_RATE", base_cm.commission_rate) or 0.0),
            "stamp_tax_rate": float(getattr(self, "STAMP_TAX_RATE", base_cm.stamp_tax_rate) or 0.0),
            "slippage_bps": float(getattr(self, "SLIPPAGE_BPS", base_cm.slippage_bps) or 0.0),
            "min_commission": float(getattr(self, "MIN_COMMISSION", base_cm.min_commission) or 0.0),
        }
        out["execution"] = {
            "min_amount_cny": float(getattr(self, "EXEC_MIN_AMOUNT_CNY", base_ex.min_amount_cny) or 0.0),
            "max_participation_rate": float(
                getattr(self, "EXEC_MAX_PARTICIPATION_RATE", base_ex.max_participation_rate) or 1.0
            ),
            "block_on_limit_up": bool(getattr(self, "EXEC_BLOCK_ON_LIMIT_UP", base_ex.block_on_limit_up)),
            "block_on_limit_down": bool(getattr(self, "EXEC_BLOCK_ON_LIMIT_DOWN", base_ex.block_on_limit_down)),
            "block_only_one_price_limit": bool(getattr(self, "EXEC_BLOCK_ONLY_ONE_PRICE_LIMIT", False)),
            "limit_up_pct": float(getattr(self, "EXEC_LIMIT_UP_PCT", base_ex.limit_up_pct) or 9.8),
            "limit_down_pct": float(getattr(self, "EXEC_LIMIT_DOWN_PCT", base_ex.limit_down_pct) or -9.8),
            "lot_size": int(getattr(self, "EXEC_LOT_SIZE", base_ex.lot_size) or 100),
        }
        for k in (
            "MARKET_CAP_MIN",
            "MARKET_CAP_MAX",
            "BUY_THRESHOLD",
            "MIN_RESONANCE",
            "TARGET_RETURN",
            "PARTIAL_PROFIT_LEVEL",
            "PARTIAL_PROFIT_PCT",
            "TRAILING_PROFIT_LEVEL",
            "TRAILING_STOP_PCT",
            "MIN_HOLD_DAYS",
            "MAX_HOLD_DAYS",
            "STOP_LOSS_PCT",
            "HOT_SECTOR_CANDIDATE_LIMIT",
            "MAX_POSITIONS",
            "EXECUTION_MODE",
            "REBALANCE_DAYS",
            "BUY_SIGNAL_MEMORY_DAYS",
            "MARKET_TOP_WATCH_WINDOW",
            "MARKET_TOP_CONFIRM_HITS",
            "MARKET_EXIT_CONFIRM_WINDOW",
            "MARKET_EXIT_CONFIRM_HITS",
            "MARKET_EXIT_MIN_DRAWDOWN_PCT",
            "CROSS_SECTOR_CANDIDATE_TOP_N",
            "STOP_LOSS_CONFIRM_DAYS",
            "SECTOR_COOLDOWN_CONFIRM_WINDOW",
            "SECTOR_COOLDOWN_CONFIRM_HITS",
            "SECTOR_EXIT_CONFIRM_WINDOW",
            "SECTOR_EXIT_CONFIRM_HITS",
            "LEADER_HOLD_MIN_PEAK_RETURN_PCT",
            "LEADER_CONFIRM_EXTRA_HITS",
            "SYSTEM_EXIT_GRACE_ENABLED",
            "SYSTEM_EXIT_GRACE_MIN_PEAK_RETURN_PCT",
            "SYSTEM_EXIT_GRACE_REQUIRE_POSITIVE_RETURN",
            "SYSTEM_EXIT_GRACE_MARKET_MIN_PEAK_RETURN_PCT",
            "SYSTEM_EXIT_GRACE_MARKET_MIN_CURRENT_PROFIT_PCT",
            "SYSTEM_EXIT_GRACE_MARKET_MIN_PROFIT_KEEP_RATIO",
            "SYSTEM_EXIT_GRACE_SECTOR_MIN_PEAK_RETURN_PCT",
            "SYSTEM_EXIT_GRACE_SECTOR_MIN_CURRENT_PROFIT_PCT",
            "SYSTEM_EXIT_GRACE_SECTOR_MIN_PROFIT_KEEP_RATIO",
            "SYSTEM_EXIT_GRACE_SECTOR_MAX_HOLD_DAYS",
            "CHASE_ENTRY_BLOCK_ENABLED",
            "CHASE_ENTRY_NEAR_HIGH_RATIO",
            "CHASE_ENTRY_PRE3_RUNUP_PCT",
            "CHASE_ENTRY_PRE5_RUNUP_PCT",
            "EXECUTION_SIGNAL_GATE_ENABLED",
            "EXECUTION_FOLLOWER_MIN_BUY_SCORE",
            "EXECUTION_UNKNOWN_WAVE_MIN_BUY_SCORE",
            "EXECUTION_ELITE_MIN_BUY_SCORE",
            "EXECUTION_ELITE_UNKNOWN_LEADER_MIN_BUY_SCORE",
            "EXECUTION_RESERVATION_ENABLED",
            "EXECUTION_RESERVATION_MEMORY_DAYS",
            "EXECUTION_ROTATION_ENABLED",
            "EXECUTION_ROTATION_MIN_SCORE_MARGIN",
            "EXECUTION_ROTATION_MIN_EVIDENCE_COUNT",
            "EXECUTION_ROTATION_MAX_CURRENT_RETURN_PCT",
            "MARKET_FILTER_ENABLED",
            "NO_LOOKAHEAD_ENFORCED",
            "STRUCTURE_CONFIRM_MODE",
            "CUP_HANDLE_ENABLED",
            "CROSS_SECTOR_ALLOW_WAVE1",
        ):
            try:
                out[str(k)] = getattr(self, str(k))
            except Exception:
                continue
        return out

    def _position_contract_snapshot(
        self,
        *,
        trade: TradeRecord,
        current_date: date,
        sell: Optional[SellSignal],
    ) -> dict[str, Any]:
        current_price = self._get_price(trade.code, current_date)
        market_snapshot = self._market_exit_snapshot(
            trade,
            current_date,
            market_key=self._resolve_market_proxy(trade.code),
        )
        sector_snapshot = self._sector_exit_snapshot(trade, current_date)
        trend_snapshot = (
            self._trend_exhaustion_snapshot(trade, current_date, current_price=float(current_price))
            if current_price
            else None
        )
        market_state = str(getattr(trade, "market_exit_state", "") or "").strip()
        sector_state = str(getattr(trade, "sector_exit_state", "") or "").strip()
        market_reason = str(getattr(trade, "market_exit_last_reason", "") or "").strip()
        sector_reason = str(getattr(trade, "sector_exit_last_reason", "") or "").strip()
        grace_reason = str(getattr(trade, "system_exit_grace_reason", "") or "").strip()
        evidence: list[str] = []
        flags: list[str] = []
        if market_state:
            flags.append(f"market_exit_state:{market_state}")
        if sector_state:
            flags.append(f"sector_exit_state:{sector_state}")
        if bool(getattr(trade, "system_exit_grace_used", False)):
            flags.append("system_exit_grace_used")
        if market_reason:
            evidence.append(market_reason)
        if sector_reason:
            evidence.append(sector_reason)
        if grace_reason:
            evidence.append(grace_reason)
        if isinstance(market_snapshot, dict):
            market_details = str(market_snapshot.get("details") or "").strip()
            if market_details and market_details not in evidence:
                evidence.append(market_details)
            if bool(market_snapshot.get("price_trend_weak")):
                flags.append("market_price_trend_weak")
            if bool(market_snapshot.get("breadth_weak")):
                flags.append("market_breadth_weak")
            if bool(market_snapshot.get("drawdown_weak")):
                flags.append("market_drawdown_weak")
        if isinstance(sector_snapshot, dict):
            sector_details = str(sector_snapshot.get("details") or "").strip()
            if sector_details and sector_details not in evidence:
                evidence.append(sector_details)
            if bool(sector_snapshot.get("cooldown_detected")):
                flags.append("sector_cooldown_detected")
            if bool(sector_snapshot.get("trend_deteriorating")):
                flags.append("sector_trend_deteriorating")
            if bool(sector_snapshot.get("leader_rollover")):
                flags.append("sector_leader_rollover")
            if bool(sector_snapshot.get("follower_weak")):
                flags.append("sector_follower_weak")
        if isinstance(trend_snapshot, dict):
            trend_details = str(trend_snapshot.get("details") or "").strip()
            if trend_details and trend_details not in evidence:
                evidence.append(trend_details)
            if bool(trend_snapshot.get("armed")):
                flags.append("trend_exhaustion_armed")
            if bool(trend_snapshot.get("drawdown_from_peak_triggered")):
                flags.append("trend_exhaustion_triggered")
        last_transition = ""
        for value in (
            str(getattr(trade, "market_exit_last_hit_date", "") or "").strip(),
            str(getattr(trade, "sector_exit_last_hit_date", "") or "").strip(),
            str(getattr(trade, "system_exit_grace_date", "") or "").strip(),
        ):
            if value and (not last_transition or value > last_transition):
                last_transition = value
        if sell is not None:
            exit_scope = str(getattr(sell, "exit_scope", "") or "position_only")
            source_layer = str(getattr(sell, "source_layer", "") or "exit")
            exit_reason_type = str(sell.reason or "")
            exit_contract = self._layer_contract_payload(
                current_stage="exit_ready",
                decision="exit",
                score=float(getattr(sell, "confidence", 0.0) or 0.0),
                reasons=[str(sell.details or sell.reason or "")],
                evidence=evidence + [str(sell.details or sell.reason or "")],
                flags=flags,
                source_layer=source_layer,
                next_action="exit",
                last_transition=last_transition or current_date.isoformat(),
            )
            return {
                "hold_state": "exit_ready",
                "noise_evidence": [],
                "not_exit_reasons": [],
                "warning_flags": list(flags),
                "hold_attribution_bucket": "",
                "exit_attribution_bucket": (
                    "invalidation_exit"
                    if exit_reason_type == "thesis_invalidated"
                    else (
                        "trend_exhaustion_exit"
                        if exit_reason_type == "trend_exhausted"
                        else (
                            "market_timing_exit"
                            if exit_reason_type == "market_top_confirmed"
                            else (
                                "sector_timing_exit"
                                if exit_reason_type == "sector_top_confirmed"
                                else "exit_other"
                            )
                        )
                    )
                ),
                "exit_ready": True,
                "exit_scope": str(exit_scope),
                "exit_reason_type": exit_reason_type,
                "exit_evidence_bundle": evidence + [str(sell.details or sell.reason or "")],
                **exit_contract,
            }
        hold_state = "holding"
        if market_state == "review" or sector_state == "review":
            hold_state = "review_watch"
        elif market_state or sector_state:
            hold_state = "observe_watch"
        elif bool(
            (isinstance(market_snapshot, dict) and int(market_snapshot.get("evidence_count") or 0) > 0)
            or (isinstance(sector_snapshot, dict) and int(sector_snapshot.get("evidence_count") or 0) > 0)
        ):
            hold_state = "noise_watch"
        elif bool(getattr(trade, "system_exit_grace_used", False)):
            hold_state = "grace_hold"
        not_exit_reasons: list[str] = []
        if market_state or sector_state:
            not_exit_reasons.append("系统退出证据尚未达到正式确认门槛")
        elif hold_state == "noise_watch":
            not_exit_reasons.append("存在弱化证据，但仍属于观察态，未达到正式退出确认")
        else:
            not_exit_reasons.append("未触发正式退出条件")
        if isinstance(trend_snapshot, dict) and bool(trend_snapshot.get("armed")) and not bool(trend_snapshot.get("condition_pass")):
            not_exit_reasons.append("盈利仓存在回撤，但仍未达到 trend_exhausted 正式退出条件")
        if bool(getattr(trade, "system_exit_grace_used", False)):
            not_exit_reasons.append("系统退出宽限仍有效，继续持有观察")
        hold_contract = self._layer_contract_payload(
            current_stage="hold_confirmed",
            decision="hold",
            reasons=not_exit_reasons,
            evidence=evidence,
            flags=flags,
            source_layer="hold",
            next_action="hold",
            last_transition=last_transition,
        )
        return {
            "hold_state": str(hold_state),
            "noise_evidence": list(evidence),
            "not_exit_reasons": list(not_exit_reasons),
            "warning_flags": list(flags),
            "hold_attribution_bucket": (
                "hold_grace"
                if hold_state == "grace_hold"
                else ("hold_noise_watch" if hold_state in {"review_watch", "observe_watch", "noise_watch"} else "hold_confirmed")
            ),
            "exit_attribution_bucket": "",
            "exit_ready": False,
            "exit_scope": "",
            "exit_reason_type": "",
            "exit_evidence_bundle": list(evidence),
            **hold_contract,
        }

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

    @staticmethod
    def _ts_code_for_stock_code(code: str) -> str:
        c = str(code or "").strip()
        if not c:
            return ""
        if "." in c and len(c.split(".", 1)[0]) == 6:
            return c
        suffix = "SH" if c.startswith("6") else "SZ"
        return f"{c}.{suffix}"

    @staticmethod
    def _match_market_keywords(*, texts: list[str], keywords: tuple[str, ...]) -> list[str]:
        hits: list[str] = []
        seen: set[str] = set()
        normalized_texts = [
            str(text or "").strip().lower()
            for text in texts
            if str(text or "").strip()
        ]
        for keyword in keywords:
            raw_keyword = str(keyword or "").strip()
            if not raw_keyword:
                continue
            key = raw_keyword.lower()
            if key in seen:
                continue
            if any(key in text for text in normalized_texts):
                hits.append(raw_keyword)
                seen.add(key)
        return hits

    @staticmethod
    def _market_ai_keywords() -> tuple[str, ...]:
        return (
            "AI",
            "人工智能",
            "算力",
            "国产算力",
            "AIDC",
            "数据中心",
            "东数西算",
            "液冷",
            "服务器",
            "光模块",
            "CPO",
            "铜缆",
            "GPU",
            "芯片",
            "半导体",
            "存储",
            "HBM",
            "先进封装",
            "机器人",
            "人形机器人",
            "减速器",
            "伺服",
            "传感器",
            "控制器",
            "自动驾驶",
            "智驾",
        )

    @classmethod
    def _market_kshape_up_keywords(cls) -> tuple[str, ...]:
        return cls._market_ai_keywords() + (
            "商业航天",
            "低空经济",
            "卫星",
            "火箭",
            "创新药",
            "医疗器械",
            "高端医疗器械",
            "新材料",
            "电子特气",
            "靶材",
            "光刻",
            "晶圆",
            "算力底座",
        )

    @staticmethod
    def _market_kshape_down_keywords() -> tuple[str, ...]:
        return (
            "高股息",
            "电力",
            "公用事业",
            "银行",
            "煤炭",
            "有色",
            "港口",
            "高速",
            "铁路",
            "基建",
            "消费",
            "物流",
            "文创",
            "互联网",
            "保险",
            "券商",
            "财富管理",
            "公募",
            "资管",
            "ESG",
            "信披",
            "数据服务",
        )

    @staticmethod
    def _market_head_broker_names() -> tuple[str, ...]:
        return (
            "中信证券",
            "华泰证券",
            "国泰海通",
            "东方财富",
            "中金公司",
        )

    @staticmethod
    def _table_exists(cursor: sqlite3.Cursor, table: str) -> bool:
        row = cursor.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
            (table,),
        ).fetchone()
        return row is not None

    def _table_has_rows(self, cursor: sqlite3.Cursor, table: str) -> bool:
        cached = self._nonempty_table_cache.get(str(table))
        if cached is not None:
            return bool(cached)
        if not self._table_exists(cursor, table):
            self._nonempty_table_cache[str(table)] = False
            return False
        row = cursor.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone()
        has_rows = row is not None
        self._nonempty_table_cache[str(table)] = bool(has_rows)
        return bool(has_rows)

    def _load_stock_concepts_cache(self) -> dict[str, list[dict[str, str]]]:
        if self._stock_concepts_cache is not None:
            return self._stock_concepts_cache

        concepts_cache_path = self._themes_snapshot_dir / "_tushare_concepts_cache.json"
        members_cache_path = self._themes_snapshot_dir / "_tushare_concept_members_cache.json"
        concept_name_by_code: dict[str, str] = {}
        stock_concepts: dict[str, list[dict[str, str]]] = {}

        try:
            if concepts_cache_path.exists():
                cache_doc = json.loads(concepts_cache_path.read_text(encoding="utf-8"))
            else:
                cache_doc = None
        except (OSError, json.JSONDecodeError):
            cache_doc = None
        items = cache_doc.get("items") if isinstance(cache_doc, dict) else None
        if isinstance(items, list):
            for item in items:
                if not isinstance(item, dict):
                    continue
                code = str(item.get("code") or "").strip()
                name = str(item.get("name") or "").strip()
                if code and name:
                    concept_name_by_code[code] = name

        try:
            if members_cache_path.exists():
                members_doc = json.loads(members_cache_path.read_text(encoding="utf-8"))
            else:
                members_doc = None
        except (OSError, json.JSONDecodeError):
            members_doc = None
        concepts_map = members_doc.get("concepts") if isinstance(members_doc, dict) else None
        if isinstance(concepts_map, dict):
            for concept_code, entry in concepts_map.items():
                if not isinstance(entry, dict):
                    continue
                concept_name = str(
                    concept_name_by_code.get(str(concept_code))
                    or entry.get("name")
                    or ""
                ).strip()
                stocks = entry.get("stocks")
                if not concept_name or not isinstance(stocks, list):
                    continue
                for stock in stocks:
                    if not isinstance(stock, dict):
                        continue
                    code = str(stock.get("code") or "").strip()
                    if not code:
                        continue
                    stock_concepts.setdefault(code, []).append(
                        {
                            "concept_code": str(concept_code),
                            "concept_name": concept_name,
                        }
                    )

        self._stock_concepts_cache = {
            str(code): [dict(item) for item in items]
            for code, items in stock_concepts.items()
        }
        return self._stock_concepts_cache

    def _load_penetration_keywords(self) -> tuple[str, ...]:
        if self._penetration_keywords_cache is not None:
            return tuple(self._penetration_keywords_cache)
        config_path = self._market_intelligence_config_dir / "penetration_stages.json"
        keywords: list[str] = []
        try:
            if config_path.exists():
                doc = json.loads(config_path.read_text(encoding="utf-8"))
            else:
                doc = None
        except (OSError, json.JSONDecodeError):
            doc = None
        items = doc.get("items") if isinstance(doc, dict) else None
        if isinstance(items, list):
            for item in items:
                if not isinstance(item, dict):
                    continue
                if str(item.get("match_type") or "").strip() != "keyword":
                    continue
                keyword = str(item.get("match_value") or "").strip()
                if keyword:
                    keywords.append(keyword)
        self._penetration_keywords_cache = tuple(dict.fromkeys(keywords))
        return tuple(self._penetration_keywords_cache)

    def _resolve_execution_mode(self) -> str:
        raw = str(getattr(self, "EXECUTION_MODE", "unbounded_opportunity") or "unbounded_opportunity").strip().lower()
        if raw in {"bounded", "unbounded_opportunity"}:
            return raw
        return "unbounded_opportunity"

    def _is_unbounded_opportunity_mode(self) -> bool:
        return self._resolve_execution_mode() == "unbounded_opportunity"

    def _opportunity_unit_budget(self, initial_capital: float) -> float:
        base_slots = max(int(getattr(self, "MAX_POSITIONS", 0) or 0), 1)
        return float(initial_capital) / float(base_slots)

    @staticmethod
    def _layer_contract_payload(
        *,
        current_stage: str,
        decision: str,
        score: Optional[float] = None,
        reasons: Optional[list[str]] = None,
        evidence: Optional[list[str]] = None,
        flags: Optional[list[str]] = None,
        source_layer: str,
        next_action: str,
        last_transition: str = "",
    ) -> dict[str, Any]:
        contract = LayerContract(
            current_stage=str(current_stage or ""),
            decision=str(decision or ""),
            score=float(score) if score is not None else None,
            reasons=list(reasons or []),
            evidence=list(evidence or []),
            flags=list(flags or []),
            source_layer=str(source_layer or ""),
            next_action=str(next_action or ""),
            last_transition=str(last_transition or ""),
        )
        return contract.to_payload()

    @classmethod
    def _normalize_execution_block_reason(cls, raw_reason: Optional[str]) -> str:
        reason = str(raw_reason or "").strip()
        if reason in {
            "reserved_due_to_full_book",
            "reservation_created",
            "no_slots",
            "buy_reserved_due_to_full_book",
        }:
            return "positions_full"
        if reason in {"no_cash", "buy_insufficient_cash"}:
            return "cash_insufficient"
        if reason in {"reservation_expired", "buy_reserved_expired"}:
            return "entry_window_missed"
        if reason in {"pending_conflict_older_intent_wins"}:
            return "conflict_with_exit"
        if reason in {
            "execution_signal_gate_blocked",
            "chase_entry_blocked",
            "elite_execution_candidate_rejected",
            "limit_up",
            "limit_down",
            "min_amount",
            "participation_rate",
            "missing_price_bar",
        }:
            return "execution_rule_blocked"
        return reason

    @classmethod
    def _candidate_tier_from_signal(cls, sig: dict[str, Any]) -> str:
        soft_flags = [str(x or "").strip() for x in list(sig.get("soft_flags") or []) if str(x or "").strip()]
        if soft_flags:
            return "soft_retained"
        return "execution_eligible"

    @classmethod
    def _execution_action_fields(
        cls,
        *,
        event_type: str,
        snapshot: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        snap = snapshot if isinstance(snapshot, dict) else {}
        event = str(event_type or "").strip()
        if event in {"tracking_started", "tracking_promoted_to_entry", "tracking_dropped"}:
            return {
                "action_type": "",
                "order_action": "",
                "reserve_action": "",
                "execution_status": "tracking",
            }
        if event == "reservation_created":
            return {
                "action_type": "reserve",
                "order_action": "block",
                "reserve_action": "reserve",
                "execution_status": "reserved",
            }
        if event == "reservation_released_into_buy":
            return {
                "action_type": "buy",
                "order_action": "buy",
                "reserve_action": "release",
                "execution_status": "executed",
            }
        if event == "buy_executed":
            reserve_action = "release" if str(snap.get("queue_name") or "") == "reserved" else ""
            return {
                "action_type": "buy",
                "order_action": "buy",
                "reserve_action": reserve_action,
                "execution_status": "executed",
            }
        if event == "reservation_expired":
            return {
                "action_type": "block",
                "order_action": "block",
                "reserve_action": "expire",
                "execution_status": "expired",
            }
        return {
            "action_type": "block",
            "order_action": "block",
            "reserve_action": "",
            "execution_status": "blocked",
        }

    def _tracking_snapshot_from_signal(self, sig: dict[str, Any]) -> dict[str, Any]:
        reasons = [str(x or "").strip() for x in list(sig.get("reasons") or []) if str(x or "").strip()]
        evidence = [str(x or "").strip() for x in list(sig.get("entry_reasons") or reasons) if str(x or "").strip()]
        flags = [str(x or "").strip() for x in list(sig.get("soft_flags") or []) if str(x or "").strip()]
        candidate_tier = str(sig.get("candidate_tier") or self._candidate_tier_from_signal(sig))
        entry_ready = bool(sig.get("entry_ready")) if "entry_ready" in sig else candidate_tier != "soft_retained"
        tracking_state = str(
            sig.get("tracking_state")
            or ("tracking_mature" if entry_ready else "tracking_observe")
        ).strip()
        tracking_days = max(int(sig.get("tracking_days") or 1), 1)
        transition_reason = str(
            sig.get("tracking_transition_reason")
            or ("candidate_meets_current_entry_contract" if entry_ready else "candidate_retained_for_tracking")
        ).strip()
        decision = "tracking_ready_for_entry" if entry_ready else "tracking_continue"
        next_action = "promote_to_entry" if entry_ready else "continue_tracking"
        current_stage = "entry_ready" if entry_ready else "candidate_detected"
        details = (
            "tracking 晋升：候选当前满足 entry 条件"
            if entry_ready
            else "tracking 继续：候选保留观察，尚未进入正式 entry"
        )
        return {
            "tracking_ready": bool(entry_ready),
            "tracking_state": tracking_state,
            "tracking_days": int(tracking_days),
            "tracking_transition_reason": transition_reason,
            "tracking_evidence_bundle": list(evidence or reasons),
            "tracking_flags": list(flags),
            "tracking_decision": decision,
            "tracking_next_action": next_action,
            "tracking_current_stage": current_stage,
            "tracking_details": details,
        }

    def _decorate_signal_with_phase1_contracts(self, sig: dict[str, Any]) -> dict[str, Any]:
        out = dict(sig)
        buy_score = float(out.get("buy_score") or 0.0)
        reasons = [str(x or "").strip() for x in list(out.get("reasons") or []) if str(x or "").strip()]
        soft_flags = [str(x or "").strip() for x in list(out.get("soft_flags") or []) if str(x or "").strip()]
        wave_phase = str(out.get("wave_phase") or "").strip()
        if bool(getattr(self, "WAVE1_TRACKING_ONLY_ENABLED", True)) and wave_phase == WavePhase.WAVE_1.value:
            if "wave1_tracking_only" not in soft_flags:
                soft_flags.append("wave1_tracking_only")
            if "capture-first: 1浪仅保留 tracking，不进入正式建仓" not in reasons:
                reasons.append("capture-first: 1浪仅保留 tracking，不进入正式建仓")
            out["soft_flags"] = list(soft_flags)
            out["reasons"] = list(reasons)
        signal_source = str(out.get("signal_source") or "buy_signal")
        candidate_tier = self._candidate_tier_from_signal(out)
        entry_ready = candidate_tier != "soft_retained"
        tracking_snapshot = self._tracking_snapshot_from_signal(
            {
                **out,
                "candidate_tier": candidate_tier,
                "entry_ready": entry_ready,
            }
        )
        candidate_contract = self._layer_contract_payload(
            current_stage="candidate_detected",
            decision="candidate_detected",
            score=buy_score,
            reasons=reasons,
            evidence=reasons,
            flags=soft_flags,
            source_layer="discovery",
            next_action="evaluate_entry",
        )
        tracking_contract = self._layer_contract_payload(
            current_stage=str(tracking_snapshot.get("tracking_current_stage") or "candidate_detected"),
            decision=str(tracking_snapshot.get("tracking_decision") or "tracking_continue"),
            score=buy_score,
            reasons=list(tracking_snapshot.get("tracking_evidence_bundle") or reasons),
            evidence=list(tracking_snapshot.get("tracking_evidence_bundle") or reasons),
            flags=list(tracking_snapshot.get("tracking_flags") or soft_flags),
            source_layer="tracking",
            next_action=str(tracking_snapshot.get("tracking_next_action") or "continue_tracking"),
        )
        entry_contract = self._layer_contract_payload(
            current_stage="entry_ready" if entry_ready else "candidate_detected",
            decision="entry_ready" if entry_ready else "candidate_only",
            score=buy_score,
            reasons=reasons,
            evidence=reasons,
            flags=soft_flags,
            source_layer="entry",
            next_action="queue_for_execution" if entry_ready else "observe_candidate",
        )
        out.update(
            {
                "candidate_detected": True,
                "candidate_score": buy_score,
                "candidate_reasons": list(reasons),
                "candidate_tier": str(candidate_tier),
                "entry_ready": bool(entry_ready),
                "tracking_ready": bool(tracking_snapshot.get("tracking_ready")),
                "tracking_state": str(tracking_snapshot.get("tracking_state") or ""),
                "tracking_days": int(tracking_snapshot.get("tracking_days") or 0),
                "tracking_transition_reason": str(tracking_snapshot.get("tracking_transition_reason") or ""),
                "tracking_evidence_bundle": list(tracking_snapshot.get("tracking_evidence_bundle") or []),
                "entry_signal_type": signal_source,
                "entry_confidence": buy_score,
                "entry_reasons": list(reasons),
                "entry_risk_flags": list(soft_flags),
                "candidate_contract": candidate_contract,
                "tracking_contract": tracking_contract,
                "entry_contract": entry_contract,
            }
        )
        return out

    def _market_focus_snapshot(
        self,
        cursor: sqlite3.Cursor,
        *,
        code: str,
        stock_name: str,
        target_date: date,
    ) -> dict[str, Any]:
        cache_key = (str(code), target_date.isoformat())
        if cache_key in self._market_focus_cache:
            return dict(self._market_focus_cache[cache_key])

        stock_concepts = self._load_stock_concepts_cache().get(str(code), [])
        concept_names = [
            str(item.get("concept_name") or "").strip()
            for item in stock_concepts
            if isinstance(item, dict)
        ]
        texts = [str(stock_name or "").strip(), str(code or "").strip(), *concept_names]
        ai_hits = self._match_market_keywords(
            texts=texts,
            keywords=self._market_ai_keywords(),
        )
        hardtech_hits = self._match_market_keywords(
            texts=texts,
            keywords=self._market_kshape_up_keywords(),
        )
        down_hits = self._match_market_keywords(
            texts=texts,
            keywords=self._market_kshape_down_keywords(),
        )
        penetration_hits = self._match_market_keywords(
            texts=texts,
            keywords=self._load_penetration_keywords(),
        )

        target_key = target_date.isoformat()
        ts_code = self._ts_code_for_stock_code(code)
        holder_etf_count = 0
        holder_fund_count = 0
        total_mkv = None
        avg_ratio = None
        index_count = 0

        fund_portfolios_ready = self._table_has_rows(cursor, "fund_portfolios")
        etf_basic_ready = self._table_has_rows(cursor, "etf_basic_info")
        index_weights_ready = self._table_has_rows(cursor, "index_weights")

        if fund_portfolios_ready:
            symbol_candidates = tuple(dict.fromkeys([str(code), ts_code]))
            symbol_placeholders = ",".join(["?"] * len(symbol_candidates))
            latest_ann_row = cursor.execute(
                f"SELECT MAX(ann_date) FROM fund_portfolios WHERE symbol IN ({symbol_placeholders}) AND ann_date <= ?",
                (*symbol_candidates, target_key),
            ).fetchone()
            latest_ann_date = (
                str(latest_ann_row[0]) if latest_ann_row and latest_ann_row[0] is not None else None
            )
            if latest_ann_date:
                agg = cursor.execute(
                    f"""
                    SELECT
                        COUNT(DISTINCT fp.ts_code),
                        COUNT(DISTINCT CASE WHEN eb.ts_code IS NOT NULL THEN fp.ts_code END),
                        SUM(fp.mkv),
                        AVG(fp.stk_mkv_ratio)
                    FROM fund_portfolios fp
                    LEFT JOIN etf_basic_info eb ON eb.ts_code = fp.ts_code
                    WHERE fp.symbol IN ({symbol_placeholders})
                      AND fp.ann_date = ?
                    """,
                    (*symbol_candidates, latest_ann_date),
                ).fetchone()
                holder_fund_count = int((agg[0] if agg else 0) or 0)
                holder_etf_count = int((agg[1] if agg else 0) or 0)
                total_mkv = float(agg[2]) if agg and isinstance(agg[2], (int, float)) else None
                avg_ratio = float(agg[3]) if agg and isinstance(agg[3], (int, float)) else None

        if index_weights_ready and ts_code:
            latest_index_row = cursor.execute(
                "SELECT MAX(trade_date) FROM index_weights WHERE con_code = ? AND trade_date <= ?",
                (ts_code, target_key),
            ).fetchone()
            latest_index_date = (
                str(latest_index_row[0]) if latest_index_row and latest_index_row[0] is not None else None
            )
            if latest_index_date:
                count_row = cursor.execute(
                    "SELECT COUNT(DISTINCT index_code) FROM index_weights WHERE con_code = ? AND trade_date = ?",
                    (ts_code, latest_index_date),
                ).fetchone()
                index_count = int((count_row[0] if count_row else 0) or 0)

        config_score = 0
        if holder_etf_count > 0:
            config_score += 1
        if holder_fund_count >= 3:
            config_score += 1
        if isinstance(total_mkv, (int, float)) and float(total_mkv) > 0:
            config_score += 1
        if isinstance(avg_ratio, (int, float)) and float(avg_ratio) >= 3.0:
            config_score += 1
        if index_count > 0:
            config_score += 1

        start_90 = (target_date - timedelta(days=90)).isoformat()
        start_180 = (target_date - timedelta(days=180)).isoformat()
        research_inst = 0
        consensus_orgs = 0
        survey_orgs = 0
        survey_count = 0

        if self._table_has_rows(cursor, "research_reports") and ts_code:
            row = cursor.execute(
                """
                SELECT COUNT(DISTINCT inst_csname)
                FROM research_reports
                WHERE ts_code = ?
                  AND trade_date >= ?
                  AND trade_date <= ?
                """,
                (ts_code, start_90, target_key),
            ).fetchone()
            research_inst = int((row[0] if row else 0) or 0)

        if self._table_has_rows(cursor, "report_consensus") and ts_code:
            row = cursor.execute(
                """
                SELECT COUNT(DISTINCT org_name)
                FROM report_consensus
                WHERE ts_code = ?
                  AND report_date <= ?
                """,
                (ts_code, target_key),
            ).fetchone()
            consensus_orgs = int((row[0] if row else 0) or 0)

        if self._table_has_rows(cursor, "institutional_surveys") and ts_code:
            row = cursor.execute(
                """
                SELECT COUNT(1), COUNT(DISTINCT rece_org)
                FROM institutional_surveys
                WHERE ts_code = ?
                  AND surv_date >= ?
                  AND surv_date <= ?
                """,
                (ts_code, start_180, target_key),
            ).fetchone()
            survey_count = int((row[0] if row else 0) or 0)
            survey_orgs = int((row[1] if row else 0) or 0)

        attention_score = 0
        if research_inst >= 1:
            attention_score += 1
        if consensus_orgs >= 1:
            attention_score += 1
        if survey_orgs >= 1:
            attention_score += 1
        if survey_count >= 1:
            attention_score += 1

        is_ai_metal_exception = "小金属" in "".join(texts) and bool(ai_hits)
        is_head_broker_exception = str(stock_name or "").strip() in self._market_head_broker_names()
        second_category_focus = bool(ai_hits or hardtech_hits or penetration_hits)
        allowed_exception = bool(is_ai_metal_exception or is_head_broker_exception)
        etf_index_data_ready = bool(etf_basic_ready or index_weights_ready)
        etf_index_evidence = bool(holder_etf_count > 0 or index_count > 0)
        fund_config_evidence = bool(
            holder_fund_count >= 3
            or (isinstance(avg_ratio, (int, float)) and float(avg_ratio) >= 3.0)
            or (isinstance(total_mkv, (int, float)) and float(total_mkv) > 0)
        )
        focus_pass = (
            (second_category_focus or allowed_exception)
            and config_score >= 2
            and (etf_index_evidence if etf_index_data_ready else fund_config_evidence)
        )
        focus_bonus = 12.0 if ai_hits else 8.0 if second_category_focus else 4.0 if allowed_exception else 0.0

        snapshot = {
            "focus_pass": bool(focus_pass),
            "focus_bonus": float(focus_bonus),
            "second_category_focus": bool(second_category_focus),
            "allowed_exception": bool(allowed_exception),
            "ai_hits": list(ai_hits),
            "hardtech_hits": list(hardtech_hits),
            "down_hits": list(down_hits),
            "penetration_hits": list(penetration_hits),
            "holder_etf_count": int(holder_etf_count),
            "holder_fund_count": int(holder_fund_count),
            "index_count": int(index_count),
            "config_score": int(config_score),
            "attention_score": int(attention_score),
            "research_inst": int(research_inst),
            "consensus_orgs": int(consensus_orgs),
            "survey_orgs": int(survey_orgs),
            "survey_count": int(survey_count),
            "etf_index_data_ready": bool(etf_index_data_ready),
            "etf_index_evidence": bool(etf_index_evidence),
            "fund_config_evidence": bool(fund_config_evidence),
        }
        self._market_focus_cache[cache_key] = dict(snapshot)
        return snapshot

    def _passes_core_focus_gate(
        self,
        cursor: sqlite3.Cursor,
        *,
        code: str,
        stock_name: str,
        role: str,
        target_date: date,
    ) -> tuple[bool, list[str], dict[str, Any]]:
        if str(role or "").strip() != "龙头":
            return False, ["仅允许细分赛道龙头进入正式买入主链"], {
                "focus_pass": False,
                "focus_bonus": 0.0,
            }
        snapshot = self._market_focus_snapshot(
            cursor,
            code=code,
            stock_name=stock_name,
            target_date=target_date,
        )
        if not bool(snapshot.get("focus_pass")):
            return False, ["未同时满足核心范围、配置高配与细分赛道龙头闸门"], snapshot

        reasons: list[str] = []
        if snapshot.get("ai_hits"):
            reasons.append(f"AI 主线命中：{', '.join(list(snapshot.get('ai_hits') or [])[:3])}")
        elif snapshot.get("hardtech_hits"):
            reasons.append(f"硬科技主线命中：{', '.join(list(snapshot.get('hardtech_hits') or [])[:3])}")
        if snapshot.get("penetration_hits"):
            reasons.append(
                f"命中渗透率重点赛道：{', '.join(list(snapshot.get('penetration_hits') or [])[:3])}"
            )
        if bool(snapshot.get("etf_index_data_ready")):
            reasons.append(
                f"ETF/指数证据通过：ETF持有人{int(snapshot.get('holder_etf_count') or 0)}，指数成分{int(snapshot.get('index_count') or 0)}，配置分{int(snapshot.get('config_score') or 0)}"
            )
        else:
            reasons.append(
                f"基金配置证据通过：基金数{int(snapshot.get('holder_fund_count') or 0)}，配置分{int(snapshot.get('config_score') or 0)}"
            )
        attention_score = int(snapshot.get("attention_score") or 0)
        if attention_score > 0:
            reasons.append(f"机构关注增强：关注分{attention_score}")
        else:
            reasons.append("机构关注未命中，本次按参考项处理")
        return True, reasons, snapshot

    def _apply_strong_leader_soft_release(
        self,
        *,
        score: float,
        role: str,
        wave_phase: str,
        soft_flags: list[str],
        reasons: list[str],
    ) -> tuple[float, list[str], list[str]]:
        """Narrow exception: release only strong 1/3-wave leaders blocked by focus/structure soft gates."""
        normalized_role = str(role or "").strip()
        normalized_wave = str(wave_phase or "").strip()
        normalized_flags = [str(flag or "").strip() for flag in list(soft_flags or []) if str(flag or "").strip()]
        if normalized_role != "龙头":
            return float(score), normalized_flags, list(reasons or [])
        if normalized_wave not in {WavePhase.WAVE_1.value, WavePhase.WAVE_3.value}:
            return float(score), normalized_flags, list(reasons or [])

        release_min_score = float(getattr(self, "EXECUTION_ELITE_MIN_BUY_SCORE", 80.0) or 80.0)
        if float(score) < float(release_min_score):
            return float(score), normalized_flags, list(reasons or [])

        allowed_flags = {"focus_soft_fail", "structure_soft_fail"}
        flag_set = set(normalized_flags)
        if not flag_set or not flag_set.issubset(allowed_flags):
            return float(score), normalized_flags, list(reasons or [])

        released_flags = [flag for flag in ("structure_soft_fail", "focus_soft_fail") if flag in flag_set]
        score_delta = 0.0
        if "structure_soft_fail" in flag_set:
            score_delta += 10.0
        if "focus_soft_fail" in flag_set:
            score_delta += 8.0

        filtered_reasons: list[str] = []
        for reason in list(reasons or []):
            text = str(reason or "")
            if text == "capture-first: 结构未确认，降权保留" and "structure_soft_fail" in flag_set:
                continue
            if text == "capture-first: focus gate 未过，降权保留" and "focus_soft_fail" in flag_set:
                continue
            if text.startswith("soft:") and flag_set:
                continue
            filtered_reasons.append(text)

        release_note = (
            f"capture-first: 高分龙头窄例外放行({'+'.join(released_flags)})"
        )
        filtered_reasons.append(release_note)
        return float(score) + float(score_delta), [], filtered_reasons

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
        artifact_path = (
            self.project_root
            / "var"
            / "artifacts"
            / "screener_runs"
            / key
            / "screener_cup_handle_v4_result.json"
        )
        if artifact_path.exists():
            try:
                payload = json.loads(artifact_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                payload = None
            picks = payload.get("picks") if isinstance(payload, dict) else None
            if isinstance(picks, list):
                out = {
                    str(item.get("code") if isinstance(item, dict) else item).split(".", 1)[0].strip()
                    for item in picks
                    if str(item.get("code") if isinstance(item, dict) else item).strip()
                }
                out = {x for x in out if len(x) == 6 and x.isdigit()}
                self._cup_handle_cache[key] = out
                return out
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

    def _ensure_market_proxy_caches(self) -> None:
        if not hasattr(self, "_market_proxy_series_cache") or not isinstance(
            getattr(self, "_market_proxy_series_cache"), dict
        ):
            self._market_proxy_series_cache = {}
        if not hasattr(self, "_market_breadth_cache") or not isinstance(
            getattr(self, "_market_breadth_cache"), dict
        ):
            self._market_breadth_cache = {}

    @staticmethod
    def _resolve_market_proxy(code: str) -> Optional[str]:
        code_s = str(code or "").strip()
        if len(code_s) != 6 or not code_s.isdigit():
            return None
        if code_s.startswith("688"):
            return "kcb"
        if code_s.startswith("300") or code_s.startswith("301"):
            return "cyb"
        if code_s.startswith("60"):
            return "sse"
        if code_s.startswith("00"):
            return "szse"
        return None

    @staticmethod
    def _market_proxy_label(market_key: str) -> str:
        labels = {
            "kcb": "科创板",
            "cyb": "创业板",
            "sse": "上证",
            "szse": "深圳",
        }
        return str(labels.get(str(market_key), "未知市场"))

    @staticmethod
    def _market_proxy_filter_sql(market_key: str) -> Optional[str]:
        key = str(market_key or "").strip()
        if key == "kcb":
            return "length(code) = 6 AND code GLOB '688[0-9][0-9][0-9]'"
        if key == "cyb":
            return (
                "length(code) = 6 AND ("
                "code GLOB '300[0-9][0-9][0-9]' "
                "OR code GLOB '301[0-9][0-9][0-9]'"
                ")"
            )
        if key == "sse":
            return "length(code) = 6 AND code GLOB '60[0-9][0-9][0-9][0-9]'"
        if key == "szse":
            return "length(code) = 6 AND code GLOB '00[0-9][0-9][0-9][0-9]'"
        return None

    def _market_proxy_series(self, market_key: str, start_date: date, end_date: date) -> list[dict[str, Any]]:
        self._ensure_market_proxy_caches()
        if end_date < start_date:
            return []
        where_sql = self._market_proxy_filter_sql(market_key)
        if not where_sql:
            return []
        cache_key = (str(market_key), start_date.isoformat(), end_date.isoformat())
        cached = self._market_proxy_series_cache.get(cache_key)
        if cached is not None:
            return [dict(item) for item in cached]

        conn = self._conn()
        try:
            rows = conn.execute(
                f"""
                SELECT trade_date, AVG(pct_change)
                FROM daily_prices
                WHERE {where_sql}
                  AND trade_date BETWEEN ? AND ?
                  AND pct_change IS NOT NULL
                GROUP BY trade_date
                ORDER BY trade_date ASC
                """,
                (start_date.isoformat(), end_date.isoformat()),
            ).fetchall()
        finally:
            conn.close()

        self._ensure_no_lookahead_trade_dates(
            rows,
            target_date=end_date,
            trade_date_index=0,
            context=f"_market_proxy_series({market_key})",
        )

        value = 100.0
        out: list[dict[str, Any]] = []
        for idx, row in enumerate(rows):
            if not row or row[0] is None:
                continue
            trade_date = str(row[0])
            avg_pct = float(row[1]) if row[1] is not None else 0.0
            if idx > 0:
                value *= 1.0 + avg_pct / 100.0
            out.append(
                {
                    "date": trade_date,
                    "value": float(value),
                    "avg_pct_change": float(avg_pct),
                }
            )
        self._market_proxy_series_cache[cache_key] = [dict(item) for item in out]
        return out

    def _market_drawdown_snapshot(
        self,
        trade: TradeRecord,
        current_date: date,
        *,
        market_key: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        proxy_key = str(market_key or self._resolve_market_proxy(trade.code) or "").strip()
        if not proxy_key:
            return None
        try:
            buy_date = date.fromisoformat(str(trade.buy_date))
        except Exception:
            return None
        series = self._market_proxy_series(proxy_key, buy_date, current_date)
        if not series:
            return None
        current_value = float(series[-1]["value"])
        peak_value = max(float(item["value"]) for item in series)
        if peak_value <= 0:
            return None
        drawdown_pct = (current_value - peak_value) / peak_value * 100.0
        return {
            "market_key": proxy_key,
            "market_label": self._market_proxy_label(proxy_key),
            "current_value": float(current_value),
            "peak_value": float(peak_value),
            "drawdown_pct": float(drawdown_pct),
        }

    def _market_above_ma20_ratio(self, market_key: str, current_date: date) -> Optional[float]:
        self._ensure_market_proxy_caches()
        proxy_key = str(market_key or "").strip()
        where_sql = self._market_proxy_filter_sql(proxy_key)
        if not where_sql:
            return None
        cache_key = (proxy_key, current_date.isoformat())
        cached = self._market_breadth_cache.get(cache_key)
        if cache_key in self._market_breadth_cache:
            return cached

        recent_dates = self._recent_trading_dates(current_date, limit=25)
        if len(recent_dates) < 20:
            self._market_breadth_cache[cache_key] = None
            return None
        start_date = recent_dates[0]

        conn = self._conn()
        try:
            rows = conn.execute(
                f"""
                SELECT code, trade_date, close
                FROM daily_prices
                WHERE {where_sql}
                  AND trade_date BETWEEN ? AND ?
                  AND close IS NOT NULL
                ORDER BY code ASC, trade_date ASC
                """,
                (start_date.isoformat(), current_date.isoformat()),
            ).fetchall()
        finally:
            conn.close()

        self._ensure_no_lookahead_trade_dates(
            rows,
            target_date=current_date,
            trade_date_index=1,
            context=f"_market_above_ma20_ratio({proxy_key})",
        )

        by_code: dict[str, list[tuple[date, float]]] = {}
        for row in rows:
            if not row or row[0] is None or row[1] is None or row[2] is None:
                continue
            code = str(row[0])
            try:
                trade_date = date.fromisoformat(str(row[1]))
            except Exception:
                continue
            by_code.setdefault(code, []).append((trade_date, float(row[2])))

        eligible = 0
        above = 0
        for items in by_code.values():
            if len(items) < 20:
                continue
            if items[-1][0] != current_date:
                continue
            closes = [float(close) for _, close in items]
            ma20 = float(np.mean(closes[-20:]))
            if ma20 <= 0:
                continue
            eligible += 1
            if float(closes[-1]) > ma20:
                above += 1

        ratio = float(above / eligible) if eligible > 0 else None
        self._market_breadth_cache[cache_key] = ratio
        return ratio

    def _market_top_snapshot(
        self,
        trade: TradeRecord,
        current_date: date,
        *,
        market_key: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        proxy_key = str(market_key or self._resolve_market_proxy(trade.code) or "").strip()
        if not proxy_key:
            return None

        recent_dates = self._recent_trading_dates(current_date, limit=40)
        if len(recent_dates) < 23:
            return None
        start_date = recent_dates[0]
        series = self._market_proxy_series(proxy_key, start_date, current_date)
        values = [float(item["value"]) for item in series if item.get("value") is not None]
        if len(values) < 23:
            return None

        ma20_today = self._sma_at(values, 20, len(values) - 1)
        ma20_3d_ago = self._sma_at(values, 20, len(values) - 4)
        breadth_ratio = self._market_above_ma20_ratio(proxy_key, current_date)
        if ma20_today is None or ma20_3d_ago is None or breadth_ratio is None:
            return None

        current_value = float(values[-1])
        cond_break_ma20 = current_value < float(ma20_today)
        cond_ma20_weak = float(ma20_today) <= float(ma20_3d_ago)
        cond_breadth_weak = float(breadth_ratio) < 0.40

        label = self._market_proxy_label(proxy_key)
        details = (
            f"{label}见顶：跌破20日线={'是' if cond_break_ma20 else '否'} | "
            f"20日线走弱={'是' if cond_ma20_weak else '否'} | "
            f"站上20日线占比{breadth_ratio:.0%}"
        )
        return {
            "market_key": proxy_key,
            "market_label": label,
            "break_ma20": bool(cond_break_ma20),
            "ma20_weak": bool(cond_ma20_weak),
            "breadth_ratio": float(breadth_ratio),
            "current_value": float(current_value),
            "ma20_today": float(ma20_today),
            "ma20_3d_ago": float(ma20_3d_ago),
            "condition_pass": bool(cond_breadth_weak and (cond_break_ma20 or cond_ma20_weak)),
            "details": details,
        }

    def _market_top_signal(
        self,
        trade: TradeRecord,
        current_date: date,
        *,
        market_key: Optional[str] = None,
    ) -> Optional[SellSignal]:
        snapshot = self._market_top_snapshot(trade, current_date, market_key=market_key)
        if not isinstance(snapshot, dict) or not bool(snapshot.get("condition_pass")):
            return None
        return SellSignal("market_top", 0.93, str(snapshot.get("details") or ""))

    def _reset_market_top_watch_state(self, trade: TradeRecord) -> None:
        trade.market_top_watch_start_date = ""
        trade.market_top_watch_expire_date = ""
        trade.market_top_watch_hits = 0
        trade.market_top_watch_last_reason = ""
        trade.market_top_watch_last_hit_date = ""

    def _market_top_watch_expire_date(self, current_date: date) -> str:
        window = max(int(getattr(self, "MARKET_TOP_WATCH_WINDOW", 3) or 3), 1)
        future_dates = self._get_trading_dates(
            current_date,
            current_date + timedelta(days=max(14, window * 5)),
        )
        if not future_dates:
            return current_date.isoformat()
        idx = min(len(future_dates) - 1, max(window - 1, 0))
        return future_dates[idx].isoformat()

    def _record_sell_signal_audit_event(
        self,
        *,
        event_type: str,
        trade: TradeRecord,
        current_date: date,
        snapshot: Optional[dict[str, Any]],
    ) -> None:
        audit_log = getattr(self, "_sell_signal_audit_current_run", None)
        if not isinstance(audit_log, list):
            return
        snap = snapshot if isinstance(snapshot, dict) else {}
        watch_day = 0
        if trade.market_top_watch_start_date:
            try:
                watch_day = self._count_trading_days(date.fromisoformat(trade.market_top_watch_start_date), current_date)
            except Exception:
                watch_day = 0
        audit_log.append(
            {
                "date": current_date.isoformat(),
                "event": str(event_type),
                "code": str(trade.code),
                "source_layer": "exit",
                "current_stage": (
                    "exit_ready"
                    if str(event_type) in {"market_top_confirmed", "sector_top_confirmed", "trend_exhausted"}
                    else "exit_watch"
                ),
                "exit_scope": (
                    "portfolio"
                    if str(event_type) == "market_top_confirmed"
                    else (
                        "sector_only"
                        if str(event_type) == "sector_top_confirmed"
                        else ("position_only" if str(event_type) == "trend_exhausted" else "")
                    )
                ),
                "exit_reason_type": str(event_type),
                "market_key": str(snap.get("market_key") or self._resolve_market_proxy(trade.code) or ""),
                "market_label": str(snap.get("market_label") or ""),
                "break_ma20": bool(snap.get("break_ma20")) if "break_ma20" in snap else None,
                "ma20_weak": bool(snap.get("ma20_weak")) if "ma20_weak" in snap else None,
                "breadth_ratio": (
                    round(float(snap.get("breadth_ratio")), 4)
                    if snap.get("breadth_ratio") is not None
                    else None
                ),
                "watch_day": int(watch_day),
                "watch_hits": int(getattr(trade, "market_top_watch_hits", 0) or 0),
                "details": str(snap.get("details") or getattr(trade, "market_top_watch_last_reason", "") or ""),
            }
        )

    def _apply_market_top_watch(
        self,
        trade: TradeRecord,
        current_date: date,
        *,
        snapshot: Optional[dict[str, Any]],
    ) -> Optional[SellSignal]:
        window = max(int(getattr(self, "MARKET_TOP_WATCH_WINDOW", 3) or 3), 1)
        confirm_hits = max(int(getattr(self, "MARKET_TOP_CONFIRM_HITS", 2) or 2), 1)
        watch_start = str(getattr(trade, "market_top_watch_start_date", "") or "").strip()
        if watch_start:
            try:
                elapsed = self._count_trading_days(date.fromisoformat(watch_start), current_date)
            except Exception:
                elapsed = window + 1
            if elapsed > window:
                self._record_sell_signal_audit_event(
                    event_type="market_top_watch_expired",
                    trade=trade,
                    current_date=current_date,
                    snapshot=snapshot,
                )
                self._reset_market_top_watch_state(trade)

        if not isinstance(snapshot, dict) or not bool(snapshot.get("condition_pass")):
            return None

        current_key = current_date.isoformat()
        if not str(getattr(trade, "market_top_watch_start_date", "") or "").strip():
            trade.market_top_watch_start_date = current_key
            trade.market_top_watch_expire_date = self._market_top_watch_expire_date(current_date)
            trade.market_top_watch_hits = 1
            trade.market_top_watch_last_reason = str(snapshot.get("details") or "")
            trade.market_top_watch_last_hit_date = current_key
            self._record_sell_signal_audit_event(
                event_type="market_top_watch_started",
                trade=trade,
                current_date=current_date,
                snapshot=snapshot,
            )
            if confirm_hits <= 1:
                self._record_sell_signal_audit_event(
                    event_type="market_top_confirmed",
                    trade=trade,
                    current_date=current_date,
                    snapshot=snapshot,
                )
                self._reset_market_top_watch_state(trade)
                return SellSignal("market_top", 0.93, str(snapshot.get("details") or ""))
            return None

        if str(getattr(trade, "market_top_watch_last_hit_date", "") or "") != current_key:
            trade.market_top_watch_hits = int(getattr(trade, "market_top_watch_hits", 0) or 0) + 1
            trade.market_top_watch_last_hit_date = current_key
        trade.market_top_watch_last_reason = str(snapshot.get("details") or "")
        if int(getattr(trade, "market_top_watch_hits", 0) or 0) >= confirm_hits:
            self._record_sell_signal_audit_event(
                event_type="market_top_confirmed",
                trade=trade,
                current_date=current_date,
                snapshot=snapshot,
            )
            self._reset_market_top_watch_state(trade)
            return SellSignal("market_top", 0.93, str(snapshot.get("details") or ""))
        return None

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
              AND s.total_market_cap >= ? AND s.total_market_cap <= ?
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
                  AND s.total_market_cap >= ? AND s.total_market_cap <= ?
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
        conn.close()

        return self._resonance_from_closes(stock_closes)

    def _resonance_from_closes(self, stock_closes: list[float]) -> float:
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
            SELECT
                code,
                report_date,
                ann_date,
                pe_ttm,
                profit_growth_yoy,
                revenue_growth_yoy,
                roe
            FROM financial_reports
            WHERE code IN ({placeholders})
              AND COALESCE(ann_date, report_date) <= ?
            ORDER BY code, COALESCE(ann_date, report_date) DESC, report_date DESC
            """,
            (*codes, target_date.isoformat()),
        )
        rows = cursor.fetchall()

        latest_by_code: dict[str, dict] = {}
        for code, _report_date, _ann_date, pe_ttm, profit_growth_yoy, revenue_growth_yoy, roe in rows:
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

    def _get_recent_price_history_batch(
        self,
        cursor: sqlite3.Cursor,
        codes: list[str],
        *,
        target_date: date,
        limit: int,
    ) -> dict[str, list[dict[str, Any]]]:
        codes = [str(c or "").strip() for c in (codes or []) if str(c or "").strip()]
        if not codes or int(limit) <= 0:
            return {}

        placeholders = ",".join(["?"] * len(codes))
        cursor.execute(
            f"""
            SELECT code, trade_date, close, volume, amount, high, low
            FROM (
                SELECT
                    code,
                    trade_date,
                    close,
                    volume,
                    amount,
                    high,
                    low,
                    row_number() OVER (PARTITION BY code ORDER BY trade_date DESC) AS rn
                FROM daily_prices
                WHERE code IN ({placeholders})
                  AND trade_date <= ?
            )
            WHERE rn <= ?
            ORDER BY code ASC, trade_date DESC
            """,
            (*codes, target_date.isoformat(), int(limit)),
        )
        rows = cursor.fetchall()

        out: dict[str, list[dict[str, Any]]] = {}
        for code, trade_date, close, volume, amount, high, low in rows:
            code_s = str(code or "").strip()
            if not code_s:
                continue
            out.setdefault(code_s, []).append(
                {
                    "trade_date": str(trade_date or ""),
                    "close": float(close) if close is not None else None,
                    "volume": float(volume) if volume is not None else None,
                    "amount": float(amount) if amount is not None else None,
                    "high": float(high) if high is not None else None,
                    "low": float(low) if low is not None else None,
                }
            )
        return out

    def _get_recent_price_history_for_formal_m1_batch(
        self,
        cursor: sqlite3.Cursor,
        codes: list[str],
        *,
        target_date: date,
        limit: int,
    ) -> dict[str, list[dict[str, Any]]]:
        codes = [str(c or "").strip() for c in (codes or []) if str(c or "").strip()]
        if not codes or int(limit) <= 0:
            return {}

        placeholders = ",".join(["?"] * len(codes))
        cursor.execute(
            f"""
            SELECT code, trade_date, open, high, low, close, volume, amount, turnover, preclose, pct_change
            FROM (
                SELECT
                    code,
                    trade_date,
                    open,
                    high,
                    low,
                    close,
                    volume,
                    amount,
                    turnover,
                    preclose,
                    pct_change,
                    row_number() OVER (PARTITION BY code ORDER BY trade_date DESC) AS rn
                FROM daily_prices
                WHERE code IN ({placeholders})
                  AND trade_date <= ?
            )
            WHERE rn <= ?
            ORDER BY code ASC, trade_date DESC
            """,
            (*codes, target_date.isoformat(), int(limit)),
        )
        rows = cursor.fetchall()

        out: dict[str, list[dict[str, Any]]] = {}
        for code, trade_date, open_, high, low, close, volume, amount, turnover, preclose, pct_change in rows:
            code_s = str(code or "").strip()
            if not code_s:
                continue
            out.setdefault(code_s, []).append(
                {
                    "trade_date": str(trade_date or ""),
                    "open": float(open_) if open_ is not None else None,
                    "high": float(high) if high is not None else None,
                    "low": float(low) if low is not None else None,
                    "close": float(close) if close is not None else None,
                    "volume": float(volume) if volume is not None else None,
                    "amount": float(amount) if amount is not None else None,
                    "turnover": float(turnover) if turnover is not None else None,
                    "preclose": float(preclose) if preclose is not None else None,
                    "pct_change": float(pct_change) if pct_change is not None else None,
                }
            )
        return out

    def _get_formal_d1_facts_batch(
        self,
        cursor: sqlite3.Cursor,
        codes: list[str],
        *,
        target_date: date,
    ) -> dict[str, Any]:
        codes = [str(c or "").strip() for c in (codes or []) if str(c or "").strip()]
        if not codes:
            return {}

        placeholders = ",".join(["?"] * len(codes))
        cursor.execute(
            f"""
            SELECT code, trade_date, open, high, low, close, volume, amount, turnover, preclose, pct_change, updated_at
            FROM daily_prices
            WHERE code IN ({placeholders})
              AND trade_date = ?
            """,
            (*codes, target_date.isoformat()),
        )
        rows = cursor.fetchall()
        out: dict[str, Any] = {}
        for row in rows:
            payload = {
                "code": row[0],
                "trade_date": row[1],
                "open": row[2],
                "high": row[3],
                "low": row[4],
                "close": row[5],
                "volume": row[6],
                "amount": row[7],
                "turnover": row[8],
                "preclose": row[9],
                "pct_change": row[10],
                "updated_at": row[11],
            }
            item = project_d1_daily_price_fact(payload)
            out[item.stock_code] = item
        return out

    def _get_formal_security_master_batch(
        self,
        cursor: sqlite3.Cursor,
        codes: list[str],
    ) -> dict[str, Any]:
        codes = [str(c or "").strip() for c in (codes or []) if str(c or "").strip()]
        if not codes:
            return {}

        placeholders = ",".join(["?"] * len(codes))
        cursor.execute(
            f"""
            SELECT code, name, asset_type, is_delisted, sector_lv1, sector_lv2, last_trade_date
            FROM stocks
            WHERE code IN ({placeholders})
            """,
            (*codes,),
        )
        rows = cursor.fetchall()
        out: dict[str, Any] = {}
        for row in rows:
            payload = {
                "code": row[0],
                "name": row[1],
                "asset_type": row[2],
                "is_delisted": row[3],
                "sector_lv1": row[4],
                "sector_lv2": row[5],
                "last_trade_date": row[6],
            }
            item = project_d7_security_master_minimal(payload)
            out[item.stock_code] = item
        return out

    def _build_formal_trading_day_status(
        self,
        cursor: sqlite3.Cursor,
        *,
        target_date: date,
    ) -> D7TradingDayStatus:
        target_key = target_date.isoformat()
        if self._table_exists(cursor, "trading_calendar_cache"):
            cursor.execute(
                "SELECT 1 FROM trading_calendar_cache WHERE trade_date = ? LIMIT 1",
                (target_key,),
            )
            is_trading_day = bool(cursor.fetchone())
            cursor.execute(
                "SELECT MIN(trade_date), MAX(trade_date) FROM trading_calendar_cache"
            )
            row = cursor.fetchone() or (None, None)
            min_trading_day = str(row[0] or "").strip() or None
            max_trading_day = str(row[1] or "").strip() or None
            covered_until = max_trading_day
            calendar_source = "trading_calendar_cache"
            if self._table_exists(cursor, "trading_calendar_meta"):
                cursor.execute(
                    "SELECT key, value FROM trading_calendar_meta WHERE key IN (?, ?)",
                    ("calendar_source", "calendar_covered_until"),
                )
                for key, value in cursor.fetchall():
                    if str(key or "") == "calendar_source" and str(value or "").strip():
                        calendar_source = str(value).strip()
                    if str(key or "") == "calendar_covered_until" and str(value or "").strip():
                        covered_until = str(value).strip()
            return D7TradingDayStatus(
                target_date=target_key,
                is_trading_day=is_trading_day,
                nearest_trading_day=target_key if is_trading_day else None,
                min_trading_day=min_trading_day,
                max_trading_day=max_trading_day,
                calendar_covered_until=covered_until,
                calendar_source=calendar_source,
            )

        cursor.execute(
            "SELECT MIN(trade_date), MAX(trade_date) FROM daily_prices"
        )
        row = cursor.fetchone() or (None, None)
        min_trading_day = str(row[0] or "").strip() or None
        max_trading_day = str(row[1] or "").strip() or None
        cursor.execute(
            "SELECT 1 FROM daily_prices WHERE trade_date = ? LIMIT 1",
            (target_key,),
        )
        is_trading_day = bool(cursor.fetchone())
        return D7TradingDayStatus(
            target_date=target_key,
            is_trading_day=is_trading_day,
            nearest_trading_day=target_key if is_trading_day else None,
            min_trading_day=min_trading_day,
            max_trading_day=max_trading_day,
            calendar_covered_until=max_trading_day,
            calendar_source="daily_prices_fallback",
        )

    def _attach_formal_front_payloads(
        self,
        signals: list[dict[str, Any]],
        *,
        formal_by_code: dict[str, dict[str, Any]],
    ) -> list[dict[str, Any]]:
        attached: list[dict[str, Any]] = []
        for raw_sig in signals:
            sig = dict(raw_sig)
            code = str(sig.get("code") or "").strip()
            sig["formal"] = dict(formal_by_code.get(code) or {"status": "unavailable"})
            attached.append(sig)
        return attached

    def _build_formal_front_chain_payload(
        self,
        *,
        target_date: date,
        candidate_signals: list[dict[str, Any]],
    ) -> dict[str, Any]:
        codes = [
            str(sig.get("code") or "").strip()
            for sig in candidate_signals
            if isinstance(sig, dict) and str(sig.get("code") or "").strip()
        ]
        if not codes:
            return {"status": "ok", "items_by_code": {}, "summary": {"total": 0, "ok": 0, "error": 0}}

        conn = self._conn()
        cursor = conn.cursor()
        try:
            d1_by_code = self._get_formal_d1_facts_batch(cursor, codes, target_date=target_date)
            security_by_code = self._get_formal_security_master_batch(cursor, codes)
            trading_day_status = self._build_formal_trading_day_status(cursor, target_date=target_date)
            history_by_code = self._get_recent_price_history_for_formal_m1_batch(
                cursor,
                codes,
                target_date=target_date,
                limit=20,
            )
        except Exception as exc:
            conn.close()
            message = str(exc) or exc.__class__.__name__
            return {
                "status": "error",
                "items_by_code": {
                    code: {
                        "status": "error",
                        "error_type": "formal_projection_failed",
                        "message": message,
                    }
                    for code in codes
                },
                "summary": {"total": len(codes), "ok": 0, "error": len(codes)},
            }
        finally:
            try:
                conn.close()
            except Exception:
                pass

        items_by_code: dict[str, dict[str, Any]] = {}
        ok_count = 0
        error_count = 0
        for code in codes:
            d1_fact = d1_by_code.get(code)
            security_master = security_by_code.get(code)
            price_rows = history_by_code.get(code) or []
            try:
                if d1_fact is None:
                    raise ValueError("d1_fact_missing")
                if security_master is None:
                    raise ValueError("security_master_missing")
                trading_profile = project_pf1_trading_profile(
                    stock_code=code,
                    price_rows=price_rows,
                )
                constraints = build_m1_constraints_ref(
                    d1_fact=d1_fact,
                    security_master=security_master,
                    trading_day_status=trading_day_status,
                    trading_profile=trading_profile,
                )
                small_cycle = build_small_cycle_from_m1(
                    d1_fact=d1_fact,
                    security_master=security_master,
                    trading_day_status=trading_day_status,
                    trading_profile=trading_profile,
                )
                identify_state = build_identify_state_from_formal_inputs(
                    cycle=small_cycle,
                    m1_constraints_ref=constraints,
                )
                tracking_state = build_tracking_state_from_formal_inputs(
                    cycle=small_cycle,
                    m1_constraints_ref=constraints,
                )
                entry_state = build_entry_state_from_formal_inputs(
                    cycle=small_cycle,
                    m1_constraints_ref=constraints,
                )
                items_by_code[code] = {
                    "status": "ok",
                    "small_cycle": small_cycle.to_payload(),
                    "identify_state": identify_state.to_payload(),
                    "tracking_state": tracking_state.to_payload(),
                    "entry_state": entry_state.to_payload(),
                    "m1_constraints_ref": dict(constraints),
                }
                ok_count += 1
            except Exception as exc:
                items_by_code[code] = {
                    "status": "error",
                    "error_type": "formal_projection_failed",
                    "message": str(exc) or exc.__class__.__name__,
                }
                error_count += 1

        return {
            "status": "ok" if error_count == 0 else "partial",
            "items_by_code": items_by_code,
            "summary": {
                "total": len(codes),
                "ok": ok_count,
                "error": error_count,
            },
        }

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
                WHERE code = ? AND COALESCE(ann_date, report_date) <= ?
                ORDER BY COALESCE(ann_date, report_date) DESC, report_date DESC LIMIT 1
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

        return self._detect_wave_phase_from_series(closes=closes, highs=highs, lows=lows)

    def _detect_wave_phase_from_series(
        self,
        *,
        closes: list[float],
        highs: list[float],
        lows: list[float],
    ) -> tuple[str, float]:
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
                      AND s.total_market_cap >= ? AND s.total_market_cap <= ?
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
              AND s.total_market_cap >= ? AND s.total_market_cap <= ?
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
              AND s.total_market_cap >= ? AND s.total_market_cap <= ?
              AND (s.is_delisted IS NULL OR s.is_delisted = 0)
              AND dp.close > 0
            ORDER BY dp.pct_change DESC
            LIMIT 80
        """, (sector, target_date.isoformat(), self.MARKET_CAP_MIN, self.MARKET_CAP_MAX))

        rows = cursor.fetchall()
        if not rows:
            if conn is not None:
                conn.close()
            return []

        staged = []
        top_rows = rows[:80]
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
            soft_flags: list[str] = []

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
                soft_flags.append("fundamentals_soft_fail")
                base_score -= 12.0
                reasons.append("capture-first: 基本面未过，降权保留")
                reasons.extend([f"soft:{r}" for r in fund_reasons])
            else:
                base_score += float(fund_score) * 0.3  # 基本面占30%
                reasons.extend(fund_reasons)

            structure = self._structure_confirm(code=str(code), target_date=target_date)
            if not structure.get("passed"):
                soft_flags.append("structure_soft_fail")
                base_score -= 10.0
                reasons.append("capture-first: 结构未确认，降权保留")
                reasons.extend([f"soft:{r}" for r in list(structure.get("reasons") or [])])
            else:
                reasons.extend(list(structure.get("reasons") or []))

            if cup_ok:
                base_score += float(self.CUP_HANDLE_SCORE_BONUS)
                if "杯柄确认（cup_handle_v4）" not in reasons:
                    reasons.append("杯柄确认（cup_handle_v4）")

            history = history_by_code.get(code) or []

            self._ensure_no_lookahead_trade_dates(history, target_date=target_date, context=f"get_sector_candidates.history({code})")

            closes = [h[1] for h in history if h[1] is not None]
            vols = [h[2] for h in history if h[2] is not None]
            if len(history) < 20 or len(closes) < 20:
                soft_flags.append("history_short")
                reasons.append("capture-first: 历史样本不足，保留但不做完整结构打分")
                base_score -= 6.0

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
            elif len(closes) >= 20:
                soft_flags.append("wave_uncertain")

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
            else:
                soft_flags.append("low_resonance")
                base_score -= 3.0
                reasons.append(f"capture-first: 共振偏弱{resonance:.0%}，降权保留")

            # 温和放量
            avg_vol_5d = np.mean(vols[1:6]) if len(vols) >= 6 else (np.mean(vols[1:]) if len(vols) > 1 else 0.0)
            vol_ratio = float(vols[0]) / avg_vol_5d if len(vols) > 0 and avg_vol_5d > 0 else 1.0
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
                    "soft_flags": soft_flags,
                }
            )

        if not staged:
            if conn is not None:
                conn.close()
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
            stock_name = str(item.get("name") or "")
            role = role_by_code.get(code) or "跟随"
            score = float(item["base_score"] or 0.0)
            reasons = list(item.get("reasons") or [])
            soft_flags = list(item.get("soft_flags") or [])
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

            passed_focus, focus_reasons, focus_snapshot = self._passes_core_focus_gate(
                cursor,
                code=code,
                stock_name=stock_name,
                role=role,
                target_date=target_date,
            )
            if not passed_focus:
                soft_flags.append("focus_soft_fail")
                score -= 8.0
                reasons.append("capture-first: focus gate 未过，降权保留")
                reasons.extend([f"soft:{r}" for r in focus_reasons])
            else:
                score += float(focus_snapshot.get("focus_bonus") or 0.0)
                reasons.extend(focus_reasons)

            if role == "跟随":
                soft_flags.append("follower_soft")
                score -= 4.0
                reasons.append("capture-first: 跟随股降权保留")

            score, soft_flags, reasons = self._apply_strong_leader_soft_release(
                score=float(score),
                role=role,
                wave_phase=str(item.get("wave_phase") or ""),
                soft_flags=soft_flags,
                reasons=reasons,
            )
            mkt_cap_yi = float(item.get("mkt_cap") or 0.0) / 1e8
            fundamentals = item.get("fundamentals") or {}
            candidates.append(
                StockCandidate(
                    code=code,
                    name=stock_name,
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
                    signal_source="hot_sector",
                    soft_flags=soft_flags,
                )
            )

        if conn is not None:
            conn.close()
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
              AND s.total_market_cap >= ? AND s.total_market_cap <= ?
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

        seed_rows: list[dict[str, Any]] = []
        candidate_codes: list[str] = []
        for code, name, sector, mkt_cap, close, pct_chg, amount, volume in rows:
            code_s = str(code or "").strip()
            sector_s = str(sector or "").strip()
            if not code_s or not sector_s:
                continue
            if code_s in exclude_codes:
                continue
            if sector_s in exclude_sectors:
                continue
            seed_rows.append(
                {
                    "code": code_s,
                    "name": str(name or ""),
                    "sector": sector_s,
                    "mkt_cap": float(mkt_cap or 0.0),
                    "close": float(close or 0.0),
                    "pct_chg": float(pct_chg or 0.0),
                    "amount": float(amount or 0.0),
                    "volume": float(volume or 0.0),
                }
            )
            candidate_codes.append(code_s)

        if not seed_rows:
            conn.close()
            return []

        dedup_codes = list(dict.fromkeys(candidate_codes))
        fundamentals_by_code = self._get_fundamentals_batch(cursor, dedup_codes, target_date)
        history_by_code = self._get_recent_price_history_batch(
            cursor,
            dedup_codes,
            target_date=target_date,
            limit=60,
        )

        staged: list[dict] = []
        for seed in seed_rows:
            code = str(seed["code"])
            name = str(seed["name"])
            sector = str(seed["sector"])
            mkt_cap = float(seed["mkt_cap"])
            close = float(seed["close"])
            pct_chg = float(seed["pct_chg"])
            reasons: list[str] = []
            base_score = 0.0
            cup_ok = str(code) in cup_picks
            soft_flags: list[str] = []

            fundamentals = fundamentals_by_code.get(code) or {
                "pe_ttm": 0,
                "profit_growth": 0,
                "revenue_growth": 0,
                "roe": 0,
                "table_exists": False,
            }
            fund_passed, fund_score, fund_reasons = self.check_fundamentals(fundamentals)
            if not fund_passed:
                soft_flags.append("fundamentals_soft_fail")
                base_score -= 12.0
                reasons.append("capture-first: 基本面未过，降权保留")
                reasons.extend([f"soft:{r}" for r in fund_reasons])
            else:
                base_score += float(fund_score) * 0.3
                reasons.extend(fund_reasons)

            structure = self._structure_confirm(code=str(code), target_date=target_date)
            if not structure.get("passed"):
                soft_flags.append("structure_soft_fail")
                base_score -= 10.0
                reasons.append("capture-first: 结构未确认，降权保留")
                reasons.extend([f"soft:{r}" for r in list(structure.get("reasons") or [])])
            else:
                reasons.extend(list(structure.get("reasons") or []))

            if cup_ok:
                base_score += float(self.CUP_HANDLE_SCORE_BONUS)
                if "杯柄确认（cup_handle_v4）" not in reasons:
                    reasons.append("杯柄确认（cup_handle_v4）")

            history = history_by_code.get(code) or []

            closes = [h["close"] for h in history[:30] if h.get("close") is not None]
            vols = [h["volume"] for h in history[:30] if h.get("volume") is not None]
            if len(history) < 20 or len(closes) < 20:
                soft_flags.append("history_short")
                base_score -= 6.0
                reasons.append("capture-first: 历史样本不足，保留但不做完整结构打分")

            price_position = 50.0
            if len(closes) >= 20:
                high_20 = max(closes[:20])
                low_20 = min(closes[:20])
                if high_20 > low_20:
                    price_position = (float(close) - low_20) / (high_20 - low_20) * 100.0
                if 60 <= price_position <= 90:
                    base_score += 20
                    reasons.append(f"价格位置{price_position:.0f}%（突破区间）")
                elif 40 <= price_position < 60:
                    base_score += 12

            wave_closes = [h["close"] for h in history if h.get("close") is not None]
            wave_highs = [h["high"] for h in history if h.get("high") is not None]
            wave_lows = [h["low"] for h in history if h.get("low") is not None]
            wave_phase, wave_confidence = self._detect_wave_phase_from_series(
                closes=wave_closes,
                highs=wave_highs,
                lows=wave_lows,
            )
            if wave_phase == WavePhase.WAVE_3.value:
                base_score += 20
                reasons.append("3浪主升浪")
            elif wave_phase == WavePhase.WAVE_1.value:
                base_score += 15
                reasons.append("1浪启动")
            elif len(closes) >= 20:
                soft_flags.append("wave_uncertain")

            resonance = self._resonance_from_closes(closes)
            if resonance >= 0.7:
                base_score += 15
                reasons.append(f"同频共振{resonance:.0%}")
            elif resonance >= 0.5:
                base_score += 8
                reasons.append(f"共振{resonance:.0%}")
            else:
                soft_flags.append("low_resonance")
                base_score -= 3.0
                reasons.append(f"capture-first: 共振偏弱{resonance:.0%}，降权保留")

            avg_vol_5d = np.mean(vols[1:6]) if len(vols) >= 6 else (np.mean(vols[1:]) if len(vols) > 1 else 0.0)
            vol_ratio = float(vols[0]) / float(avg_vol_5d) if len(vols) > 0 and avg_vol_5d > 0 else 1.0
            if 1.0 < vol_ratio <= 2.0:
                base_score += 15
                reasons.append(f"温和放量{vol_ratio:.1f}倍")

            ret_5d = (
                (float(closes[0]) - float(closes[4])) / float(closes[4]) * 100.0
                if len(closes) >= 5 and float(closes[4]) > 0
                else 0.0
            )
            if 2 <= ret_5d <= 10:
                base_score += 10
                reasons.append(f"5日涨{ret_5d:.1f}%（适中）")

            if len(closes) >= 20:
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
                ret_20d = (
                    (float(closes[0]) - float(closes[19])) / float(closes[19]) * 100.0
                    if len(closes) >= 20 and float(closes[19]) > 0
                    else 0.0
                )
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
                    "soft_flags": soft_flags,
                }
            )

        if not staged:
            conn.close()
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
            stock_name = str(item.get("name") or "")
            sector = str(item.get("sector") or "")
            role = role_by_code.get(code) or "跟随"
            score = float(item.get("base_score") or 0.0)
            reasons = list(item.get("reasons") or [])
            soft_flags = list(item.get("soft_flags") or [])
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

            passed_focus, focus_reasons, focus_snapshot = self._passes_core_focus_gate(
                cursor,
                code=code,
                stock_name=stock_name,
                role=role,
                target_date=target_date,
            )
            if not passed_focus:
                soft_flags.append("focus_soft_fail")
                score -= 8.0
                reasons.append("capture-first: focus gate 未过，降权保留")
                reasons.extend([f"soft:{r}" for r in focus_reasons])
            else:
                score += float(focus_snapshot.get("focus_bonus") or 0.0)
                reasons.extend(focus_reasons)

            if role == "跟随":
                soft_flags.append("follower_soft")
                score -= 4.0
                reasons.append("capture-first: 跟随股降权保留")

            score, soft_flags, reasons = self._apply_strong_leader_soft_release(
                score=float(score),
                role=role,
                wave_phase=str(item.get("wave_phase") or ""),
                soft_flags=soft_flags,
                reasons=reasons,
            )
            mkt_cap_yi = float(item.get("mkt_cap") or 0.0) / 1e8
            fundamentals = item.get("fundamentals") or {}
            candidates.append(
                StockCandidate(
                    code=code,
                    name=stock_name,
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
                    signal_source="cross_sector",
                    soft_flags=soft_flags,
                )
            )

        conn.close()
        candidates.sort(key=lambda x: x.buy_score, reverse=True)
        return candidates[: int(top_n)]

    def _build_signal_structure_payload(
        self,
        *,
        deduped_signals: dict[str, dict[str, Any]],
        target_date: date,
        market_filter_note: Optional[str],
    ) -> dict[str, Any]:
        candidate_signals = sorted(
            deduped_signals.values(),
            key=lambda x: (float(x.get("buy_score") or 0.0), float(x.get("resonance") or 0.0)),
            reverse=True,
        )
        entry_signals = [dict(sig) for sig in candidate_signals if bool(sig.get("entry_ready"))]
        return {
            "buy_signals": list(entry_signals),
            "candidate_signals": candidate_signals,
            "entry_signals": entry_signals,
            "signal_summary": {
                "candidate_count": len(candidate_signals),
                "entry_count": len(entry_signals),
                "soft_retained_count": sum(
                    1 for sig in candidate_signals if str(sig.get("candidate_tier") or "") == "soft_retained"
                ),
            },
            "date": target_date.isoformat(),
            "capture_first_mode": True,
            "market_filter_note": market_filter_note,
        }

    def generate_buy_signals(self, target_date: date) -> dict:
        """生成买入信号 - capture-first: 仅执行安全保持硬性。"""
        market_filter_note: Optional[str] = None
        if self.MARKET_FILTER_ENABLED:
            sentiment, market_score = self.get_market_sentiment(target_date)
            if market_score < self.MIN_MARKET_SCORE:
                market_filter_note = f"capture-first: 市场情绪{sentiment.value} ({market_score:.0f}分)，降权但不暂停买入"
                logger.info(market_filter_note)
            else:
                logger.info(f"市场情绪: {sentiment.value} ({market_score:.0f}分)")
        
        raw_signals: list[dict[str, Any]] = []
        hot_sectors = []
        conn = self._conn()
        cursor = conn.cursor()
        try:
            hot_sectors = self.get_hot_sectors(target_date, self.HOT_SECTOR_COUNT, cursor=cursor)
            logger.info(f"热门板块 Top {len(hot_sectors)}: {[s.sector for s in hot_sectors]}")

            for sh in hot_sectors:
                try:
                    candidates = self.get_sector_candidates(
                        sh.sector,
                        target_date,
                        int(getattr(self, "HOT_SECTOR_CANDIDATE_LIMIT", 12) or 12),
                        cursor=cursor,
                    )
                    for c in candidates:
                        reasons = list(c.buy_reasons)
                        if market_filter_note:
                            reasons.append(market_filter_note)
                        raw_signals.append(
                            self._decorate_signal_with_phase1_contracts(
                                {
                                    "code": c.code,
                                    "name": c.name,
                                    "sector": c.sector,
                                    "buy_score": float(c.buy_score),
                                    "market_cap_yi": c.market_cap_yi,
                                    "wave_phase": c.wave_phase,
                                    "role": c.role,
                                    "reasons": reasons,
                                    "pe": c.pe_ttm,
                                    "profit_growth": c.profit_growth,
                                    "resonance": c.sector_resonance,
                                    "cup_handle_ok": bool(getattr(c, "cup_handle_ok", False)),
                                    "signal_source": str(getattr(c, "signal_source", "") or "hot_sector"),
                                    "soft_flags": list(getattr(c, "soft_flags", []) or []),
                                }
                            )
                        )
                except Exception as e:
                    logger.warning(f"板块 {sh.sector} 信号生成失败: {e}")
        finally:
            conn.close()

        if self.CROSS_SECTOR_SCAN_ENABLED:
            try:
                hot_sector_set = {str(s.sector) for s in hot_sectors}
                existing_codes = {str(s.get("code") or "") for s in raw_signals if isinstance(s, dict)}
                global_candidates = self.get_global_candidates(
                    target_date,
                    top_n=int(getattr(self, "CROSS_SECTOR_CANDIDATE_TOP_N", 120) or 120),
                    exclude_sectors=hot_sector_set,
                    exclude_codes=existing_codes,
                )
                allowed_waves = {WavePhase.WAVE_3.value}
                if bool(getattr(self, "CROSS_SECTOR_ALLOW_WAVE1", True)):
                    allowed_waves.add(WavePhase.WAVE_1.value)
                for c in global_candidates:
                    reasons = ["跨板块扫描"] + list(c.buy_reasons)
                    soft_flags = list(getattr(c, "soft_flags", []) or [])
                    if self.CROSS_SECTOR_WAVE3_ONLY and str(c.wave_phase) not in allowed_waves:
                        reasons.append("capture-first: 波段不符，降权保留")
                        soft_flags.append("wave_uncertain")
                    if market_filter_note:
                        reasons.append(market_filter_note)
                    raw_signals.append(
                        self._decorate_signal_with_phase1_contracts(
                            {
                                "code": c.code,
                                "name": c.name,
                                "sector": c.sector,
                                "buy_score": float(c.buy_score),
                                "market_cap_yi": c.market_cap_yi,
                                "wave_phase": c.wave_phase,
                                "role": c.role,
                                "reasons": reasons,
                                "pe": c.pe_ttm,
                                "profit_growth": c.profit_growth,
                                "resonance": c.sector_resonance,
                                "cross_sector": True,
                                "cup_handle_ok": bool(getattr(c, "cup_handle_ok", False)),
                                "signal_source": str(getattr(c, "signal_source", "") or "cross_sector"),
                                "soft_flags": soft_flags,
                            }
                        )
                    )
            except Exception as e:
                logger.warning(f"跨板块扫描失败: {e}")

        deduped: dict[str, dict[str, Any]] = {}
        for sig in raw_signals:
            code = str(sig.get("code") or "").strip()
            if not code:
                continue
            current = deduped.get(code)
            if current is None or float(sig.get("buy_score") or 0.0) > float(current.get("buy_score") or 0.0):
                deduped[code] = dict(sig)

        signal_payload = self._build_signal_structure_payload(
            deduped_signals=deduped,
            target_date=target_date,
            market_filter_note=market_filter_note,
        )
        formal_payload = self._build_formal_front_chain_payload(
            target_date=target_date,
            candidate_signals=signal_payload.get("candidate_signals") or [],
        )
        candidate_signals = self._attach_formal_front_payloads(
            signal_payload.get("candidate_signals") or [],
            formal_by_code=dict(formal_payload.get("items_by_code") or {}),
        )
        entry_signals = [dict(sig) for sig in candidate_signals if bool(sig.get("entry_ready"))]
        signal_payload["candidate_signals"] = candidate_signals
        signal_payload["entry_signals"] = entry_signals
        signal_payload["buy_signals"] = list(entry_signals)
        signal_payload["formal"] = formal_payload
        return signal_payload

    def _system_exit_attr_names(self, scope: str) -> dict[str, str]:
        base = "market_exit" if str(scope) == "market" else "sector_exit"
        return {
            "state": f"{base}_state",
            "start": f"{base}_start_date",
            "expire": f"{base}_expire_date",
            "hits": f"{base}_hits",
            "last_reason": f"{base}_last_reason",
            "last_hit": f"{base}_last_hit_date",
        }

    def _reset_system_exit_state(self, trade: TradeRecord, scope: str) -> None:
        attrs = self._system_exit_attr_names(scope)
        setattr(trade, attrs["state"], "")
        setattr(trade, attrs["start"], "")
        setattr(trade, attrs["expire"], "")
        setattr(trade, attrs["hits"], 0)
        setattr(trade, attrs["last_reason"], "")
        setattr(trade, attrs["last_hit"], "")

    def _reset_all_system_exit_states(self, trade: TradeRecord) -> None:
        self._reset_system_exit_state(trade, "market")
        self._reset_system_exit_state(trade, "sector")

    def _peak_return_pct(self, trade: TradeRecord) -> float:
        buy_price = float(getattr(trade, "buy_price", 0.0) or 0.0)
        peak_price = float(getattr(trade, "peak_price", 0.0) or 0.0)
        if buy_price <= 0 or peak_price <= 0:
            return 0.0
        return (peak_price - buy_price) / max(buy_price, 1e-9) * 100.0

    def _current_return_pct(self, trade: TradeRecord, *, current_price: float) -> float:
        buy_price = float(getattr(trade, "buy_price", 0.0) or 0.0)
        if buy_price <= 0:
            return 0.0
        return (float(current_price) - buy_price) / max(buy_price, 1e-9) * 100.0

    def _resolve_buy_progress_label(
        self,
        *,
        signal: Optional[dict[str, Any]] = None,
        trade: Optional[TradeRecord] = None,
    ) -> str:
        raw_label = ""
        if isinstance(signal, dict):
            raw_label = str(signal.get("buy_progress_label") or "").strip()
            if raw_label:
                return raw_label
            raw_wave_phase = str(signal.get("wave_phase") or "").strip()
        else:
            raw_wave_phase = ""
        if trade is not None:
            trade_label = str(getattr(trade, "buy_progress_label", "") or "").strip()
            if trade_label:
                return trade_label
            if not raw_wave_phase:
                raw_wave_phase = str(getattr(trade, "wave_phase", "") or "").strip()
        if raw_wave_phase == WavePhase.WAVE_1.value:
            return "前置布局"
        if raw_wave_phase == WavePhase.WAVE_3.value:
            return "早窗"
        return "其它"

    def _profit_keep_ratio(self, *, current_return_pct: float, peak_return_pct: float) -> float:
        if float(peak_return_pct) <= 0.0:
            return 0.0
        return float(current_return_pct) / max(float(peak_return_pct), 1e-9)

    def _system_exit_grace_thresholds(self, *, scope: str) -> tuple[float, float, float, int]:
        if str(scope) == "sector":
            return (
                float(getattr(self, "SYSTEM_EXIT_GRACE_SECTOR_MIN_PEAK_RETURN_PCT", 10.0) or 10.0),
                float(getattr(self, "SYSTEM_EXIT_GRACE_SECTOR_MIN_CURRENT_PROFIT_PCT", 10.0) or 10.0),
                float(getattr(self, "SYSTEM_EXIT_GRACE_SECTOR_MIN_PROFIT_KEEP_RATIO", 0.60) or 0.60),
                int(getattr(self, "SYSTEM_EXIT_GRACE_SECTOR_MAX_HOLD_DAYS", 10) or 0),
            )
        return (
            float(getattr(self, "SYSTEM_EXIT_GRACE_MARKET_MIN_PEAK_RETURN_PCT", 20.0) or 20.0),
            float(getattr(self, "SYSTEM_EXIT_GRACE_MARKET_MIN_CURRENT_PROFIT_PCT", 10.0) or 10.0),
            float(getattr(self, "SYSTEM_EXIT_GRACE_MARKET_MIN_PROFIT_KEEP_RATIO", 0.50) or 0.50),
            0,
        )

    def _system_exit_expire_date(self, current_date: date, *, window: int) -> str:
        win = max(int(window or 0), 1)
        future_dates = self._get_trading_dates(
            current_date,
            current_date + timedelta(days=max(14, win * 5)),
        )
        if not future_dates:
            return current_date.isoformat()
        idx = min(len(future_dates) - 1, max(win - 1, 0))
        return future_dates[idx].isoformat()

    def _is_leader_hold_candidate(self, trade: TradeRecord) -> bool:
        if str(getattr(trade, "role", "") or "").strip() != "龙头":
            return False
        peak_return_pct = self._peak_return_pct(trade)
        threshold = float(getattr(self, "LEADER_HOLD_MIN_PEAK_RETURN_PCT", 15.0) or 15.0)
        return float(peak_return_pct) >= float(threshold)

    def _record_system_exit_grace_audit_event(
        self,
        *,
        event_type: str,
        trade: TradeRecord,
        current_date: date,
        scope: str,
        snapshot: Optional[dict[str, Any]],
        current_return_pct: Optional[float] = None,
        peak_return_pct: Optional[float] = None,
        profit_keep_ratio: Optional[float] = None,
    ) -> None:
        audit_log = getattr(self, "_sell_signal_audit_current_run", None)
        if not isinstance(audit_log, list):
            return
        snap = snapshot if isinstance(snapshot, dict) else {}
        audit_log.append(
            {
                "date": current_date.isoformat(),
                "event": str(event_type),
                "scope": str(scope),
                "code": str(trade.code),
                "sector": str(getattr(trade, "sector", "") or ""),
                "grace_used": bool(getattr(trade, "system_exit_grace_used", False)),
                "grace_scope": str(getattr(trade, "system_exit_grace_scope", "") or ""),
                "grace_date": str(getattr(trade, "system_exit_grace_date", "") or ""),
                "buy_progress_label": self._resolve_buy_progress_label(trade=trade),
                "current_return_pct": round(float(current_return_pct), 2) if current_return_pct is not None else None,
                "peak_return_pct": round(float(peak_return_pct), 2) if peak_return_pct is not None else None,
                "profit_keep_ratio": round(float(profit_keep_ratio), 4) if profit_keep_ratio is not None else None,
                "details": str(snap.get("details") or getattr(trade, "system_exit_grace_reason", "") or ""),
            }
        )

    def _eligible_for_system_exit_grace(
        self,
        trade: TradeRecord,
        *,
        snapshot: Optional[dict[str, Any]],
        scope: str,
        sell_price: float,
    ) -> bool:
        if not bool(getattr(self, "SYSTEM_EXIT_GRACE_ENABLED", True)):
            return False
        if bool(getattr(trade, "system_exit_grace_used", False)):
            return False
        grace_scope = str(scope or "")
        role = str(getattr(trade, "role", "") or "").strip()
        if grace_scope == "sector":
            if role not in {"龙头", "中军"}:
                return False
        elif not self._is_leader_hold_candidate(trade):
            return False
        if float(sell_price or 0.0) <= 0:
            return False
        peak_return_pct = self._peak_return_pct(trade)
        buy_progress_label = self._resolve_buy_progress_label(trade=trade)
        if buy_progress_label not in {"早窗", "前置布局"}:
            return False
        current_return_pct = self._current_return_pct(trade, current_price=float(sell_price))
        if bool(getattr(self, "SYSTEM_EXIT_GRACE_REQUIRE_POSITIVE_RETURN", True)) and float(current_return_pct) <= 0.0:
            return False
        min_peak_return_pct, min_current_profit_pct, min_profit_keep_ratio, max_hold_days = self._system_exit_grace_thresholds(
            scope=grace_scope
        )
        if grace_scope != "sector":
            min_peak_return_pct = max(
                float(min_peak_return_pct),
                float(getattr(self, "SYSTEM_EXIT_GRACE_MIN_PEAK_RETURN_PCT", 20.0) or 20.0),
            )
        if float(peak_return_pct) < float(min_peak_return_pct):
            return False
        if float(current_return_pct) < float(min_current_profit_pct):
            return False
        profit_keep_ratio = self._profit_keep_ratio(
            current_return_pct=current_return_pct,
            peak_return_pct=peak_return_pct,
        )
        if float(profit_keep_ratio) < float(min_profit_keep_ratio):
            return False
        if int(max_hold_days) > 0 and int(getattr(trade, "hold_days", 0) or 0) > int(max_hold_days):
            return False
        return True

    def _market_exit_snapshot(
        self,
        trade: TradeRecord,
        current_date: date,
        *,
        market_key: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        top_snapshot = self._market_top_snapshot(trade, current_date, market_key=market_key)
        drawdown_snapshot = self._market_drawdown_snapshot(trade, current_date, market_key=market_key)
        market_label = ""
        proxy_key = str(market_key or self._resolve_market_proxy(trade.code) or "")
        if isinstance(top_snapshot, dict):
            market_label = str(top_snapshot.get("market_label") or "")
            proxy_key = str(top_snapshot.get("market_key") or proxy_key)
        elif isinstance(drawdown_snapshot, dict):
            market_label = str(drawdown_snapshot.get("market_label") or "")
        if not market_label:
            market_label = "市场"
        breadth_ratio = top_snapshot.get("breadth_ratio") if isinstance(top_snapshot, dict) else None
        break_ma20 = bool(top_snapshot.get("break_ma20")) if isinstance(top_snapshot, dict) else False
        ma20_weak = bool(top_snapshot.get("ma20_weak")) if isinstance(top_snapshot, dict) else False
        price_trend_weak = bool(break_ma20 or ma20_weak)
        breadth_weak = breadth_ratio is not None and float(breadth_ratio) < 0.40
        drawdown_pct = drawdown_snapshot.get("drawdown_pct") if isinstance(drawdown_snapshot, dict) else None
        min_drawdown_pct = float(getattr(self, "MARKET_EXIT_MIN_DRAWDOWN_PCT", -4.0) or -4.0)
        drawdown_weak = drawdown_pct is not None and float(drawdown_pct) <= float(min_drawdown_pct)
        evidence_count = int(bool(price_trend_weak)) + int(bool(breadth_weak)) + int(bool(drawdown_weak))
        condition_pass = bool(price_trend_weak and breadth_weak and int(evidence_count) >= 2)
        if not condition_pass and not any((price_trend_weak, breadth_weak, drawdown_weak)):
            return None
        details = (
            f"{market_label}见顶确认候选：趋势转弱={'是' if price_trend_weak else '否'} | "
            f"广度转弱={'是' if breadth_weak else '否'} | "
            f"代理回撤{float(drawdown_pct):.1f}%"
            if drawdown_pct is not None
            else f"{market_label}见顶确认候选：趋势转弱={'是' if price_trend_weak else '否'} | "
            f"广度转弱={'是' if breadth_weak else '否'} | 代理回撤未知"
        )
        return {
            "scope": "market",
            "market_key": proxy_key,
            "market_label": market_label,
            "break_ma20": bool(break_ma20),
            "ma20_weak": bool(ma20_weak),
            "breadth_ratio": float(breadth_ratio) if breadth_ratio is not None else None,
            "drawdown_pct": float(drawdown_pct) if drawdown_pct is not None else None,
            "price_trend_weak": bool(price_trend_weak),
            "breadth_weak": bool(breadth_weak),
            "drawdown_weak": bool(drawdown_weak),
            "drawdown_is_observation_only": True,
            "evidence_count": int(evidence_count),
            "condition_pass": bool(condition_pass),
            "details": details,
        }

    def _sector_exit_snapshot(self, trade: TradeRecord, current_date: date) -> Optional[dict[str, Any]]:
        sector = str(getattr(trade, "sector", "") or "").strip()
        if not sector:
            return None
        info = self.detect_sector_cooldown(sector, current_date)
        if not isinstance(info, dict):
            return None
        follower_weakness = float(info.get("follower_weakness") or 0.0)
        leader_strength = float(info.get("leader_strength") or 0.0)
        leader_avg = float(info.get("leader_avg") or 0.0)
        trend_state = str(info.get("trend_state") or "unknown")
        cooldown_detected = bool(info.get("cooldown_detected"))
        follower_weak = follower_weakness > 0.6
        trend_deteriorating = trend_state in {"diverging", "falling"}
        leader_rollover = leader_strength < 0.55 or leader_avg < 8.0
        evidence_count = (
            int(bool(trend_deteriorating))
            + int(bool(follower_weak))
            + int(bool(cooldown_detected))
            + int(bool(leader_rollover))
        )
        condition_pass = bool(trend_deteriorating and follower_weak)
        if not condition_pass and not any((cooldown_detected, trend_deteriorating, leader_rollover)):
            return None
        details = (
            f"板块见顶确认候选：{sector} | 趋势={trend_state} | "
            f"跟随股弱势{follower_weakness:.0%} | 龙头强度{leader_strength:.0%}"
        )
        return {
            "scope": "sector",
            "sector": sector,
            "cooldown_detected": bool(cooldown_detected),
            "follower_weakness": float(follower_weakness),
            "leader_strength": float(leader_strength),
            "leader_avg": float(leader_avg),
            "trend_state": trend_state,
            "follower_weak": bool(follower_weak),
            "trend_deteriorating": bool(trend_deteriorating),
            "leader_rollover": bool(leader_rollover),
            "cooldown_is_observation_only": True,
            "leader_rollover_is_observation_only": True,
            "evidence_count": int(evidence_count),
            "condition_pass": bool(condition_pass),
            "details": details,
        }

    def _record_system_exit_audit_event(
        self,
        *,
        scope: str,
        event_type: str,
        trade: TradeRecord,
        current_date: date,
        snapshot: Optional[dict[str, Any]],
        leader_hold_active: bool,
        confirm_hits_required: int,
    ) -> None:
        audit_log = getattr(self, "_sell_signal_audit_current_run", None)
        if not isinstance(audit_log, list):
            return
        snap = snapshot if isinstance(snapshot, dict) else {}
        attrs = self._system_exit_attr_names(scope)
        start_value = str(getattr(trade, attrs["start"], "") or "")
        watch_day = 0
        if start_value:
            try:
                watch_day = self._count_trading_days(date.fromisoformat(start_value), current_date)
            except Exception:
                watch_day = 0
        audit_log.append(
            {
                "date": current_date.isoformat(),
                "event": str(event_type),
                "scope": str(scope),
                "code": str(trade.code),
                "sector": str(getattr(trade, "sector", "") or ""),
                "state": str(getattr(trade, attrs["state"], "") or ""),
                "watch_day": int(watch_day),
                "watch_hits": int(getattr(trade, attrs["hits"], 0) or 0),
                "confirm_hits_required": int(confirm_hits_required),
                "leader_hold_active": bool(leader_hold_active),
                "details": str(snap.get("details") or getattr(trade, attrs["last_reason"], "") or ""),
                "evidence_count": int(snap.get("evidence_count") or 0) if isinstance(snap, dict) else 0,
                "market_label": str(snap.get("market_label") or ""),
                "sector_label": str(snap.get("sector") or ""),
                "trend_state": str(snap.get("trend_state") or ""),
            }
        )

    def _apply_system_exit_state(
        self,
        trade: TradeRecord,
        current_date: date,
        *,
        scope: str,
        snapshot: Optional[dict[str, Any]],
        signal_reason: str,
        signal_confidence: float,
        sell_price: float,
    ) -> Optional[SellSignal]:
        attrs = self._system_exit_attr_names(scope)
        if str(scope) == "market":
            window = max(int(getattr(self, "MARKET_EXIT_CONFIRM_WINDOW", 5) or 5), 1)
            confirm_hits = max(int(getattr(self, "MARKET_EXIT_CONFIRM_HITS", 3) or 3), 1)
        else:
            window = max(int(getattr(self, "SECTOR_EXIT_CONFIRM_WINDOW", 4) or 4), 1)
            confirm_hits = max(int(getattr(self, "SECTOR_EXIT_CONFIRM_HITS", 3) or 3), 1)
        leader_hold_active = self._is_leader_hold_candidate(trade)
        confirm_hits += int(getattr(self, "LEADER_CONFIRM_EXTRA_HITS", 1) or 0) if leader_hold_active else 0

        start_value = str(getattr(trade, attrs["start"], "") or "").strip()
        if start_value:
            try:
                elapsed = self._count_trading_days(date.fromisoformat(start_value), current_date)
            except Exception:
                elapsed = window + 1
            if elapsed > window:
                self._record_system_exit_audit_event(
                    scope=scope,
                    event_type=f"{scope}_exit_watch_expired",
                    trade=trade,
                    current_date=current_date,
                    snapshot=snapshot,
                    leader_hold_active=leader_hold_active,
                    confirm_hits_required=confirm_hits,
                )
                self._reset_system_exit_state(trade, scope)

        if not isinstance(snapshot, dict) or not bool(snapshot.get("condition_pass")):
            return None

        current_key = current_date.isoformat()
        if not str(getattr(trade, attrs["start"], "") or "").strip():
            setattr(trade, attrs["state"], "observe")
            setattr(trade, attrs["start"], current_key)
            setattr(trade, attrs["expire"], self._system_exit_expire_date(current_date, window=window))
            setattr(trade, attrs["hits"], 1)
            setattr(trade, attrs["last_reason"], str(snapshot.get("details") or ""))
            setattr(trade, attrs["last_hit"], current_key)
            self._record_system_exit_audit_event(
                scope=scope,
                event_type=f"{scope}_exit_watch_started",
                trade=trade,
                current_date=current_date,
                snapshot=snapshot,
                leader_hold_active=leader_hold_active,
                confirm_hits_required=confirm_hits,
            )
            return None

        if str(getattr(trade, attrs["last_hit"], "") or "") != current_key:
            setattr(trade, attrs["hits"], int(getattr(trade, attrs["hits"], 0) or 0) + 1)
            setattr(trade, attrs["last_hit"], current_key)
        setattr(trade, attrs["last_reason"], str(snapshot.get("details") or ""))
        hit_count = int(getattr(trade, attrs["hits"], 0) or 0)

        if hit_count >= 2 and str(getattr(trade, attrs["state"], "") or "") != "review":
            setattr(trade, attrs["state"], "review")
            self._record_system_exit_audit_event(
                scope=scope,
                event_type=f"{scope}_exit_review_started",
                trade=trade,
                current_date=current_date,
                snapshot=snapshot,
                leader_hold_active=leader_hold_active,
                confirm_hits_required=confirm_hits,
            )

        if hit_count >= confirm_hits:
            current_return_pct = self._current_return_pct(trade, current_price=float(sell_price))
            peak_return_pct = self._peak_return_pct(trade)
            profit_keep_ratio = self._profit_keep_ratio(
                current_return_pct=current_return_pct,
                peak_return_pct=peak_return_pct,
            )
            if self._eligible_for_system_exit_grace(
                trade,
                snapshot=snapshot,
                scope=scope,
                sell_price=float(sell_price),
            ):
                trade.system_exit_grace_used = True
                trade.system_exit_grace_date = current_key
                trade.system_exit_grace_scope = str(scope)
                trade.system_exit_grace_reason = str(snapshot.get("details") or "")
                self._record_system_exit_grace_audit_event(
                    event_type="system_exit_downgraded",
                    trade=trade,
                    current_date=current_date,
                    scope=scope,
                    snapshot=snapshot,
                    current_return_pct=current_return_pct,
                    peak_return_pct=peak_return_pct,
                    profit_keep_ratio=profit_keep_ratio,
                )
                self._reset_all_system_exit_states(trade)
                return None
            if bool(getattr(trade, "system_exit_grace_used", False)):
                self._record_system_exit_grace_audit_event(
                    event_type="system_exit_downgraded_then_confirmed",
                    trade=trade,
                    current_date=current_date,
                    scope=scope,
                    snapshot=snapshot,
                    current_return_pct=current_return_pct,
                    peak_return_pct=peak_return_pct,
                    profit_keep_ratio=profit_keep_ratio,
                )
            self._record_system_exit_audit_event(
                scope=scope,
                event_type=f"{scope}_exit_confirmed",
                trade=trade,
                current_date=current_date,
                snapshot=snapshot,
                leader_hold_active=leader_hold_active,
                confirm_hits_required=confirm_hits,
            )
            self._reset_system_exit_state(trade, scope)
            confirmed_details = str(snapshot.get("details") or "").replace("确认候选", "确认")
            exit_scope = "portfolio" if str(scope) == "market" else "sector_only"
            return SellSignal(
                str(signal_reason),
                float(signal_confidence),
                confirmed_details,
                source_layer="exit",
                exit_scope=exit_scope,
            )
        return None

    def _thesis_invalidation_signal(
        self,
        trade: TradeRecord,
        *,
        sell_price: float,
        current_date: Optional[date] = None,
    ) -> Optional[SellSignal]:
        buy_price = float(getattr(trade, "buy_price", 0.0) or 0.0)
        if buy_price <= 0:
            return None
        current_return = (float(sell_price) - buy_price) / max(buy_price, 1e-9) * 100.0
        stop_loss_pct = float(getattr(self, "STOP_LOSS_PCT", -5.0) or -5.0)
        if current_return > stop_loss_pct:
            return None
        hold_days = int(getattr(trade, "hold_days", 0) or 0)
        if hold_days <= 0:
            try:
                target_day = current_date if isinstance(current_date, date) else date.today()
                hold_days = self._count_trading_days(date.fromisoformat(trade.buy_date), target_day)
            except Exception:
                hold_days = 0
        invalidated_window = "early" if int(hold_days) < 12 else "late"
        window_label = "建仓早期" if invalidated_window == "early" else "持仓期"
        details = f"{window_label}硬证伪退出：跌破买入价{current_return:.1f}%（阈值{stop_loss_pct:.1f}%）"
        return SellSignal(
            "thesis_invalidated",
            0.99,
            details,
            source_layer="invalidation",
            exit_scope="position_only",
            invalidated_reason="entry_stop_loss",
            invalidated_window=invalidated_window,
        )

    def _entry_stop_loss_signal(
        self,
        trade: TradeRecord,
        *,
        sell_price: float,
        current_date: Optional[date] = None,
    ) -> Optional[SellSignal]:
        return self._thesis_invalidation_signal(trade, sell_price=sell_price, current_date=current_date)

    def _trend_exhaustion_snapshot(
        self,
        trade: TradeRecord,
        current_date: date,
        *,
        current_price: float,
    ) -> Optional[dict[str, Any]]:
        buy_price = float(getattr(trade, "buy_price", 0.0) or 0.0)
        peak_price = float(getattr(trade, "peak_price", 0.0) or 0.0)
        if buy_price <= 0 or current_price <= 0:
            return None
        if peak_price <= 0:
            peak_price = float(buy_price)
        try:
            hold_days = int(getattr(trade, "hold_days", 0) or 0)
            if hold_days <= 0:
                hold_days = self._count_trading_days(date.fromisoformat(trade.buy_date), current_date)
        except Exception:
            hold_days = int(getattr(trade, "hold_days", 0) or 0)
        peak_return_pct = (float(peak_price) - float(buy_price)) / max(float(buy_price), 1e-9) * 100.0
        current_return_pct = (float(current_price) - float(buy_price)) / max(float(buy_price), 1e-9) * 100.0
        drawdown_from_peak_pct = float(current_return_pct) - float(peak_return_pct)
        armed_level = max(
            float(getattr(self, "TRAILING_PROFIT_LEVEL", 20.0) or 20.0),
            float(getattr(self, "PARTIAL_PROFIT_LEVEL", 25.0) or 25.0),
        )
        drawdown_trigger = float(getattr(self, "TRAILING_STOP_PCT", -5.0) or -5.0)
        min_hold_days = max(int(getattr(self, "MIN_HOLD_DAYS", 15) or 0), 0)
        buy_progress_label = str(getattr(trade, "buy_progress_label", "") or "").strip()
        armed = float(peak_return_pct) > float(armed_level)
        drawdown_triggered = float(drawdown_from_peak_pct) <= float(drawdown_trigger)
        hold_ready = int(hold_days) >= int(min_hold_days)
        current_profit_positive = float(current_return_pct) > 0.0
        early_quality_entry = buy_progress_label in {"早窗", "前置布局"}
        condition_pass = bool(armed and drawdown_triggered and hold_ready and current_profit_positive and not early_quality_entry)
        details = (
            f"趋势衰竭候选：峰值收益{peak_return_pct:.1f}% | 当前收益{current_return_pct:.1f}% | "
            f"距峰值回撤{drawdown_from_peak_pct:.1f}pct | 最小持有{hold_days}天"
        )
        return {
            "armed": bool(armed),
            "hold_ready": bool(hold_ready),
            "current_profit_positive": bool(current_profit_positive),
            "early_quality_entry": bool(early_quality_entry),
            "drawdown_from_peak_triggered": bool(drawdown_triggered),
            "condition_pass": bool(condition_pass),
            "peak_return_pct": round(float(peak_return_pct), 2),
            "current_return_pct": round(float(current_return_pct), 2),
            "drawdown_from_peak_pct": round(float(drawdown_from_peak_pct), 2),
            "details": details,
        }

    def _trend_exhaustion_signal(self, trade: TradeRecord, current_date: date, *, sell_price: float) -> Optional[SellSignal]:
        snapshot = self._trend_exhaustion_snapshot(trade, current_date, current_price=float(sell_price))
        if not isinstance(snapshot, dict) or not bool(snapshot.get("condition_pass")):
            return None
        return SellSignal(
            "trend_exhausted",
            0.88,
            str(snapshot.get("details") or "趋势衰竭退出"),
            source_layer="exit",
            exit_scope="position_only",
        )

    def _recent_closes_before_date(
        self,
        cursor: Any,
        *,
        code: str,
        target_date: date,
        lookback: int = 10,
    ) -> list[float]:
        try:
            rows = cursor.execute(
                """
                SELECT close
                FROM daily_prices
                WHERE code = ? AND trade_date < ? AND close IS NOT NULL
                ORDER BY trade_date DESC
                LIMIT ?
                """,
                (str(code), target_date.isoformat(), int(lookback)),
            ).fetchall()
        except Exception:
            return []
        closes = [float(row[0]) for row in rows if row and row[0] is not None]
        return list(reversed(closes))

    def _chase_entry_snapshot(
        self,
        cursor: Any,
        *,
        code: str,
        target_date: date,
        ref_price: float,
    ) -> Optional[dict[str, Any]]:
        if not bool(getattr(self, "CHASE_ENTRY_BLOCK_ENABLED", True)):
            return None
        if float(ref_price or 0.0) <= 0:
            return None
        closes = self._recent_closes_before_date(cursor, code=str(code), target_date=target_date, lookback=10)
        if len(closes) < 5:
            return None
        near_high_ratio = float(getattr(self, "CHASE_ENTRY_NEAR_HIGH_RATIO", 0.98) or 0.98)
        pre3_threshold = float(getattr(self, "CHASE_ENTRY_PRE3_RUNUP_PCT", 8.0) or 8.0)
        pre5_threshold = float(getattr(self, "CHASE_ENTRY_PRE5_RUNUP_PCT", 12.0) or 12.0)

        trailing5 = closes[-5:]
        trailing10 = closes[-10:] if len(closes) >= 10 else closes
        near_5d_high = bool(trailing5) and float(ref_price) >= max(trailing5) * float(near_high_ratio)
        near_10d_high = bool(trailing10) and float(ref_price) >= max(trailing10) * float(near_high_ratio)

        pre3_close = closes[-3] if len(closes) >= 3 else None
        pre5_close = closes[-5] if len(closes) >= 5 else None
        pre3_return_pct = (
            (float(ref_price) - float(pre3_close)) / max(float(pre3_close), 1e-9) * 100.0
            if pre3_close is not None
            else None
        )
        pre5_return_pct = (
            (float(ref_price) - float(pre5_close)) / max(float(pre5_close), 1e-9) * 100.0
            if pre5_close is not None
            else None
        )
        near_high_flag = bool(near_5d_high or near_10d_high)
        recent_runup_flag = bool(
            (pre3_return_pct is not None and float(pre3_return_pct) >= float(pre3_threshold))
            or (pre5_return_pct is not None and float(pre5_return_pct) >= float(pre5_threshold))
        )
        blocked = bool(near_high_flag and recent_runup_flag)
        details = (
            f"追高型买点硬禁：近5日高位={'是' if near_5d_high else '否'} | "
            f"近10日高位={'是' if near_10d_high else '否'} | "
            f"前3日涨幅{float(pre3_return_pct):.1f}% | 前5日涨幅{float(pre5_return_pct):.1f}%"
            if pre3_return_pct is not None and pre5_return_pct is not None
            else "追高型买点硬禁：历史窗口不足"
        )
        return {
            "blocked": bool(blocked),
            "near_high_flag": bool(near_high_flag),
            "recent_runup_flag": bool(recent_runup_flag),
            "near_5d_high": bool(near_5d_high),
            "near_10d_high": bool(near_10d_high),
            "pre3_return_pct": round(float(pre3_return_pct), 2) if pre3_return_pct is not None else None,
            "pre5_return_pct": round(float(pre5_return_pct), 2) if pre5_return_pct is not None else None,
            "details": details,
        }

    def _record_buy_signal_audit_event(
        self,
        *,
        event_type: str,
        current_date: date,
        code: str,
        sig: dict[str, Any],
        payload: Optional[dict[str, Any]],
        snapshot: Optional[dict[str, Any]],
    ) -> None:
        audit_log = getattr(self, "_buy_signal_audit_current_run", None)
        if not isinstance(audit_log, list):
            return
        snap = snapshot if isinstance(snapshot, dict) else {}
        source_payload = payload if isinstance(payload, dict) else {}
        event = str(event_type or "").strip()
        tracking_event = event in {"tracking_started", "tracking_promoted_to_entry", "tracking_dropped"}
        action_fields = self._execution_action_fields(event_type=str(event_type), snapshot=snap)
        audit_log.append(
            {
                "date": current_date.isoformat(),
                "event": event,
                "code": str(code),
                "source_layer": "tracking" if tracking_event else "execution",
                **action_fields,
                "funnel_stage": (
                    "candidate_detected"
                    if event == "tracking_started"
                    else (
                        "entry_ready"
                        if event == "tracking_promoted_to_entry"
                        else (
                            "expired"
                            if event == "tracking_dropped"
                            else (
                                "reserved"
                                if event == "reservation_created"
                                else (
                                    "expired"
                                    if event == "reservation_expired"
                                    else (
                                        "released"
                                        if event == "reservation_released_into_buy"
                                        else "blocked"
                                    )
                                )
                            )
                        )
                    )
                ),
                "name": str(sig.get("name") or ""),
                "sector": str(sig.get("sector") or ""),
                "buy_score": float(sig.get("buy_score") or 0.0),
                "wave_phase": str(sig.get("wave_phase") or ""),
                "role": str(sig.get("role") or ""),
                "signal_date": str(source_payload.get("first_date") or current_date.isoformat()),
                "blocked_reason": "" if tracking_event else str(snap.get("blocked_reason") or event),
                "execution_block_reason": (
                    ""
                    if tracking_event
                    else (
                        self._normalize_execution_block_reason(
                            str(snap.get("blocked_reason") or event)
                        )
                    )
                ),
                "queue_name": str(snap.get("queue_name") or ""),
                "position_delta": int(snap.get("position_delta") or 0),
                "near_high_flag": bool(snap.get("near_high_flag")),
                "recent_runup_flag": bool(snap.get("recent_runup_flag")),
                "near_5d_high": bool(snap.get("near_5d_high")),
                "near_10d_high": bool(snap.get("near_10d_high")),
                "pre3_return_pct": snap.get("pre3_return_pct"),
                "pre5_return_pct": snap.get("pre5_return_pct"),
                "min_score_required": snap.get("min_score_required"),
                "soft_role_blocked": bool(snap.get("soft_role_blocked")),
                "soft_wave_blocked": bool(snap.get("soft_wave_blocked")),
                "tracking_state": str(snap.get("tracking_state") or ""),
                "tracking_days": int(snap.get("tracking_days") or 0),
                "tracking_transition_reason": str(snap.get("tracking_transition_reason") or ""),
                "tracking_ready": bool(snap.get("tracking_ready")),
                "tracking_evidence_bundle": list(snap.get("tracking_evidence_bundle") or []),
                "details": str(snap.get("details") or ""),
            }
        )

    def _record_tracking_candidate_events(
        self,
        *,
        current_date: date,
        signals: Optional[dict[str, Any]],
        tracking_runtime_state: dict[str, dict[str, Any]],
        positions: Optional[dict[str, TradeRecord]] = None,
    ) -> list[dict[str, Any]]:
        signal_payload = signals if isinstance(signals, dict) else {}
        candidate_signals = signal_payload.get("candidate_signals")
        if not isinstance(candidate_signals, list):
            raw_buy_signals = signal_payload.get("buy_signals")
            return [dict(sig) for sig in raw_buy_signals] if isinstance(raw_buy_signals, list) else []
        active_positions = positions if isinstance(positions, dict) else {}
        current_tracking_codes: set[str] = set()
        promoted_entry_signals: list[dict[str, Any]] = []
        tracking_min_days = max(int(getattr(self, "TRACKING_MIN_DAYS", 2) or 0), 1)
        for raw_sig in candidate_signals:
            if not isinstance(raw_sig, dict):
                continue
            sig = dict(raw_sig)
            code = str(sig.get("code") or "").strip()
            if not code or code in active_positions:
                tracking_runtime_state.pop(code, None)
                continue
            tracking_snapshot = self._tracking_snapshot_from_signal(sig)
            prev = tracking_runtime_state.get(code)
            tracking_days = 1 if prev is None else int(prev.get("tracking_days") or 0) + 1
            raw_tracking_ready = bool(tracking_snapshot.get("tracking_ready"))
            tracking_ready = bool(raw_tracking_ready and tracking_days >= tracking_min_days)
            tracking_state = str(
                "tracking_mature"
                if tracking_ready
                else (
                    "tracking_observe"
                    if raw_tracking_ready
                    else (tracking_snapshot.get("tracking_state") or "tracking_observe")
                )
            )
            transition_reason = str(
                "tracking_min_days_satisfied"
                if tracking_ready
                else (
                    "tracking_wait_min_days"
                    if raw_tracking_ready
                    else (tracking_snapshot.get("tracking_transition_reason") or "candidate_retained_for_tracking")
                )
            )
            tracking_details = (
                f"tracking 晋升：连续观察 {tracking_days} 天，达到最小观察门槛 {tracking_min_days} 天"
                if tracking_ready
                else (
                    f"tracking 继续：连续观察 {tracking_days} 天，尚未达到最小观察门槛 {tracking_min_days} 天"
                    if raw_tracking_ready
                    else "tracking 继续：候选保留观察，当前未满足正式 entry 条件"
                )
            )
            first_date = str(
                (prev or {}).get("first_date") or current_date.isoformat()
            )
            event_snapshot = {
                **tracking_snapshot,
                "tracking_ready": tracking_ready,
                "tracking_state": tracking_state,
                "tracking_days": int(tracking_days),
                "tracking_transition_reason": transition_reason,
                "details": tracking_details,
            }
            event_payload = {
                "first_date": first_date,
                "tracking_days": int(tracking_days),
            }
            if prev is None:
                self._record_buy_signal_audit_event(
                    event_type="tracking_started",
                    current_date=current_date,
                    code=code,
                    sig=sig,
                    payload=event_payload,
                    snapshot=event_snapshot,
                )
            previously_promoted = bool((prev or {}).get("promoted"))
            if tracking_ready and not previously_promoted:
                self._record_buy_signal_audit_event(
                    event_type="tracking_promoted_to_entry",
                    current_date=current_date,
                    code=code,
                    sig=sig,
                    payload=event_payload,
                    snapshot=event_snapshot,
                )
            current_tracking_codes.add(code)
            promoted_sig = {
                **sig,
                "tracking_ready": tracking_ready,
                "tracking_state": tracking_state,
                "tracking_days": int(tracking_days),
                "tracking_transition_reason": transition_reason,
                "tracking_evidence_bundle": list(
                    event_snapshot.get("tracking_evidence_bundle") or sig.get("tracking_evidence_bundle") or []
                ),
            }
            tracking_runtime_state[code] = {
                "first_date": first_date,
                "tracking_days": int(tracking_days),
                "tracking_state": tracking_state,
                "tracking_ready": tracking_ready,
                "promoted": bool(tracking_ready),
                "sig": dict(promoted_sig),
            }
            if tracking_ready:
                promoted_entry_signals.append(promoted_sig)
        dropped_codes = [
            str(code)
            for code in list(tracking_runtime_state.keys())
            if str(code) not in current_tracking_codes and str(code) not in active_positions
        ]
        for code in dropped_codes:
            prev = tracking_runtime_state.pop(code, None)
            if not isinstance(prev, dict):
                continue
            sig = dict(prev.get("sig") or {})
            tracking_days = int(prev.get("tracking_days") or 0)
            self._record_buy_signal_audit_event(
                event_type="tracking_dropped",
                current_date=current_date,
                code=str(code),
                sig=sig,
                payload={
                    "first_date": str(prev.get("first_date") or current_date.isoformat()),
                    "tracking_days": tracking_days,
                },
                snapshot={
                    "tracking_state": "tracking_dropped",
                    "tracking_days": tracking_days,
                    "tracking_transition_reason": "candidate_missing_from_current_tracking_set",
                    "tracking_ready": False,
                    "tracking_evidence_bundle": list(sig.get("tracking_evidence_bundle") or sig.get("reasons") or []),
                    "details": "tracking 终止：候选已不在当前跟踪集合中",
                },
            )
        return promoted_entry_signals

    def _execution_signal_gate_snapshot(self, *, sig: dict[str, Any]) -> dict[str, Any]:
        if not bool(getattr(self, "EXECUTION_SIGNAL_GATE_ENABLED", True)):
            return {"blocked": False}

        role = str(sig.get("role") or "").strip()
        wave_phase = str(sig.get("wave_phase") or "").strip()
        buy_score = float(sig.get("buy_score") or 0.0)
        soft_role_blocked = False
        soft_wave_blocked = False
        min_score_required = 0.0
        reasons: list[str] = []

        follower_min_score = float(getattr(self, "EXECUTION_FOLLOWER_MIN_BUY_SCORE", 75.0) or 75.0)
        unknown_wave_min_score = float(getattr(self, "EXECUTION_UNKNOWN_WAVE_MIN_BUY_SCORE", 80.0) or 80.0)

        if role == "跟随" and buy_score < follower_min_score:
            soft_role_blocked = True
            min_score_required = max(min_score_required, follower_min_score)
            reasons.append(f"跟随股正式执行至少需要 {follower_min_score:.1f} 分")

        if wave_phase not in {WavePhase.WAVE_1.value, WavePhase.WAVE_3.value} and buy_score < unknown_wave_min_score:
            soft_wave_blocked = True
            min_score_required = max(min_score_required, unknown_wave_min_score)
            reasons.append(f"未知波段正式执行至少需要 {unknown_wave_min_score:.1f} 分")

        return {
            "blocked": bool(reasons),
            "blocked_reason": "execution_signal_gate_blocked",
            "soft_role_blocked": bool(soft_role_blocked),
            "soft_wave_blocked": bool(soft_wave_blocked),
            "min_score_required": float(min_score_required),
            "details": "；".join(reasons),
        }

    def _elite_execution_candidate_snapshot(self, *, sig: dict[str, Any]) -> dict[str, Any]:
        gate = self._execution_signal_gate_snapshot(sig=sig)
        if bool(gate.get("blocked")):
            return {
                "eligible": False,
                "blocked_reason": "elite_execution_candidate_rejected",
                "details": str(gate.get("details") or ""),
                "min_score_required": gate.get("min_score_required"),
            }

        role = str(sig.get("role") or "").strip()
        wave_phase = str(sig.get("wave_phase") or "").strip()
        buy_score = float(sig.get("buy_score") or 0.0)
        soft_flags = [str(x or "").strip() for x in list(sig.get("soft_flags") or []) if str(x or "").strip()]
        elite_min_score = float(getattr(self, "EXECUTION_ELITE_MIN_BUY_SCORE", 80.0) or 80.0)
        elite_unknown_leader_min_score = float(
            getattr(self, "EXECUTION_ELITE_UNKNOWN_LEADER_MIN_BUY_SCORE", 90.0) or 90.0
        )

        reasons: list[str] = []
        if role != "龙头":
            reasons.append("非龙头不进入 elite execution 资格")
        if soft_flags:
            reasons.append("存在 soft-retained 标记，不进入 elite execution 资格")

        min_score_required = elite_min_score
        if wave_phase in {WavePhase.WAVE_1.value, WavePhase.WAVE_3.value}:
            if buy_score < elite_min_score:
                reasons.append(f"1浪/3浪龙头正式保留至少需要 {elite_min_score:.1f} 分")
        else:
            min_score_required = elite_unknown_leader_min_score
            if buy_score < elite_unknown_leader_min_score:
                reasons.append(f"未知波段龙头正式保留至少需要 {elite_unknown_leader_min_score:.1f} 分")

        return {
            "eligible": not bool(reasons),
            "blocked_reason": "elite_execution_candidate_rejected",
            "details": "；".join(reasons),
            "soft_flags": soft_flags,
            "min_score_required": float(min_score_required),
        }

    def _rotation_candidate_snapshot(
        self,
        *,
        cursor: Any,
        trade: TradeRecord,
        current_date: date,
        incoming_sig: dict[str, Any],
        rotation_cache: Optional[dict[tuple[str, str], dict[str, Any]]] = None,
    ) -> Optional[dict[str, Any]]:
        if not bool(getattr(self, "EXECUTION_ROTATION_ENABLED", True)):
            return None

        incoming_score = float(incoming_sig.get("buy_score") or 0.0)
        held_score = float(getattr(trade, "buy_score", 0.0) or 0.0)
        score_gap = float(incoming_score) - float(held_score)
        min_score_margin = float(getattr(self, "EXECUTION_ROTATION_MIN_SCORE_MARGIN", 12.0) or 12.0)
        if float(score_gap) < float(min_score_margin):
            return None

        cache_key = (str(trade.code), current_date.isoformat())
        base_snapshot: Optional[dict[str, Any]] = None
        if isinstance(rotation_cache, dict):
            cached = rotation_cache.get(cache_key)
            if isinstance(cached, dict):
                base_snapshot = cached
        if base_snapshot is None:
            bar = self._get_bar(cursor, code=str(trade.code), d=current_date)
            current_price = float(bar.get("close") or 0.0) if isinstance(bar, dict) else 0.0
            if current_price <= 0.0:
                return None
            current_return_pct = self._current_return_pct(trade, current_price=current_price)
            market_key = self._resolve_market_proxy(trade.code)
            market_snapshot = self._market_exit_snapshot(trade, current_date, market_key=market_key)
            sector_snapshot = self._sector_exit_snapshot(trade, current_date)
            market_evidence = int(market_snapshot.get("evidence_count") or 0) if isinstance(market_snapshot, dict) else 0
            sector_evidence = int(sector_snapshot.get("evidence_count") or 0) if isinstance(sector_snapshot, dict) else 0
            watch_active = bool(
                str(getattr(trade, "market_exit_state", "") or "").strip()
                or str(getattr(trade, "sector_exit_state", "") or "").strip()
            )
            weakening = bool(
                watch_active
                or (isinstance(market_snapshot, dict) and bool(market_snapshot.get("price_trend_weak")))
                or (isinstance(sector_snapshot, dict) and bool(sector_snapshot.get("trend_deteriorating")))
                or (isinstance(sector_snapshot, dict) and bool(sector_snapshot.get("leader_rollover")))
                or (isinstance(sector_snapshot, dict) and bool(sector_snapshot.get("follower_weak")))
            )
            peak_return_pct = self._peak_return_pct(trade)
            base_snapshot = {
                "current_price": float(current_price),
                "current_return_pct": float(current_return_pct),
                "market_evidence": int(market_evidence),
                "sector_evidence": int(sector_evidence),
                "watch_active": bool(watch_active),
                "weakening": bool(weakening),
                "peak_return_pct": float(peak_return_pct),
            }
            if isinstance(rotation_cache, dict):
                rotation_cache[cache_key] = base_snapshot

        current_return_pct = float(base_snapshot.get("current_return_pct") or 0.0)
        max_current_return_pct = float(
            getattr(self, "EXECUTION_ROTATION_MAX_CURRENT_RETURN_PCT", 25.0) or 25.0
        )
        if float(current_return_pct) > float(max_current_return_pct):
            return None

        market_evidence = int(base_snapshot.get("market_evidence") or 0)
        sector_evidence = int(base_snapshot.get("sector_evidence") or 0)
        min_evidence = int(getattr(self, "EXECUTION_ROTATION_MIN_EVIDENCE_COUNT", 2) or 0)
        watch_active = bool(base_snapshot.get("watch_active"))
        weakening = bool(base_snapshot.get("weakening"))
        max_evidence = max(int(market_evidence), int(sector_evidence))
        if not bool(weakening) and int(max_evidence) < int(min_evidence):
            return None

        peak_return_pct = float(base_snapshot.get("peak_return_pct") or 0.0)
        profit_keep_ratio = self._profit_keep_ratio(
            current_return_pct=float(current_return_pct),
            peak_return_pct=float(peak_return_pct),
        )
        priority = (
            float(score_gap)
            + float(max_evidence) * 10.0
            + (5.0 if bool(watch_active) else 0.0)
            + (3.0 if bool(weakening) else 0.0)
            - max(float(current_return_pct), 0.0) * 0.1
        )
        details = (
            f"弱化持仓换仓候选 | score_gap={score_gap:.1f} | "
            f"market_evidence={market_evidence} | sector_evidence={sector_evidence} | "
            f"current_return={current_return_pct:.1f}% | keep_ratio={profit_keep_ratio:.2f}"
        )
        return {
            "code": str(trade.code),
            "current_price": float(base_snapshot.get("current_price") or 0.0),
            "current_return_pct": float(current_return_pct),
            "peak_return_pct": float(peak_return_pct),
            "profit_keep_ratio": float(profit_keep_ratio),
            "market_evidence": int(market_evidence),
            "sector_evidence": int(sector_evidence),
            "watch_active": bool(watch_active),
            "weakening": bool(weakening),
            "score_gap": float(score_gap),
            "priority": float(priority),
            "details": details,
        }

    def _select_rotation_candidate(
        self,
        *,
        cursor: Any,
        positions: dict[str, TradeRecord],
        current_date: date,
        incoming_sig: dict[str, Any],
        rotation_cache: Optional[dict[tuple[str, str], dict[str, Any]]] = None,
    ) -> Optional[tuple[str, dict[str, Any]]]:
        best_code: Optional[str] = None
        best_snapshot: Optional[dict[str, Any]] = None
        for code, trade in positions.items():
            snapshot = self._rotation_candidate_snapshot(
                cursor=cursor,
                trade=trade,
                current_date=current_date,
                incoming_sig=incoming_sig,
                rotation_cache=rotation_cache,
            )
            if not isinstance(snapshot, dict):
                continue
            if best_snapshot is None:
                best_code = str(code)
                best_snapshot = snapshot
                continue
            candidate_key = (
                float(snapshot.get("priority") or 0.0),
                float(snapshot.get("score_gap") or 0.0),
                -float(snapshot.get("current_return_pct") or 0.0),
            )
            best_key = (
                float(best_snapshot.get("priority") or 0.0),
                float(best_snapshot.get("score_gap") or 0.0),
                -float(best_snapshot.get("current_return_pct") or 0.0),
            )
            if candidate_key > best_key:
                best_code = str(code)
                best_snapshot = snapshot
        if best_code is None or best_snapshot is None:
            return None
        return best_code, best_snapshot

    def check_sell_signal_v2(self, trade: TradeRecord, current_date: date) -> Optional[SellSignal]:
        """正式离场主链只保留硬证伪退出、趋势衰竭退出、大盘见顶确认、板块见顶确认。"""
        sell_price = self._get_price(trade.code, current_date)
        if not sell_price:
            return None

        if float(getattr(trade, "peak_price", 0.0) or 0.0) <= 0:
            trade.peak_price = float(trade.buy_price)
        if sell_price > float(trade.peak_price):
            trade.peak_price = float(sell_price)

        hard_stop = self._thesis_invalidation_signal(
            trade,
            sell_price=float(sell_price),
            current_date=current_date,
        )
        if hard_stop is not None:
            if bool(getattr(trade, "system_exit_grace_used", False)):
                self._record_system_exit_grace_audit_event(
                    event_type="system_exit_downgraded_then_stop_loss",
                    trade=trade,
                    current_date=current_date,
                    scope=str(getattr(trade, "system_exit_grace_scope", "") or "stop_loss"),
                    snapshot=None,
                    current_return_pct=self._current_return_pct(trade, current_price=float(sell_price)),
                    peak_return_pct=self._peak_return_pct(trade),
                )
            self._reset_all_system_exit_states(trade)
            return hard_stop

        trend_sell = self._trend_exhaustion_signal(
            trade,
            current_date,
            sell_price=float(sell_price),
        )
        if trend_sell is not None:
            self._record_sell_signal_audit_event(
                event_type="trend_exhausted",
                trade=trade,
                current_date=current_date,
                snapshot=self._trend_exhaustion_snapshot(trade, current_date, current_price=float(sell_price)),
            )
            self._reset_all_system_exit_states(trade)
            return trend_sell

        market_key = self._resolve_market_proxy(trade.code)
        market_snapshot = self._market_exit_snapshot(trade, current_date, market_key=market_key)
        market_sell = self._apply_system_exit_state(
            trade,
            current_date,
            scope="market",
            snapshot=market_snapshot,
            signal_reason="market_top_confirmed",
            signal_confidence=0.92,
            sell_price=float(sell_price),
        )
        if market_sell is not None:
            self._reset_system_exit_state(trade, "sector")
            return market_sell
        if str(getattr(trade, "system_exit_grace_date", "") or "") == current_date.isoformat():
            return None

        sector_snapshot = self._sector_exit_snapshot(trade, current_date)
        sector_sell = self._apply_system_exit_state(
            trade,
            current_date,
            scope="sector",
            snapshot=sector_snapshot,
            signal_reason="sector_top_confirmed",
            signal_confidence=0.9,
            sell_price=float(sell_price),
        )
        if sector_sell is not None:
            self._reset_system_exit_state(trade, "market")
        return sector_sell

    def _slippage_adjust_price(self, *, price: float, side: str) -> float:
        bps = float(getattr(self, "SLIPPAGE_BPS", 0.0) or 0.0)
        if bps <= 0:
            return float(price)
        mult = 1.0 + (bps / 10000.0) if str(side) == "buy" else 1.0 - (bps / 10000.0)
        return float(price) * float(mult)

    def _calc_trade_fee(self, *, trade_value: float, side: str) -> float:
        commission = float(getattr(self, "COMMISSION_RATE", 0.0) or 0.0)
        min_commission = float(getattr(self, "MIN_COMMISSION", 0.0) or 0.0)
        stamp = float(getattr(self, "STAMP_TAX_RATE", 0.0) or 0.0)
        fee = float(trade_value) * float(commission)
        if min_commission > 0:
            fee = max(fee, min_commission)
        if str(side) == "sell" and stamp > 0:
            fee += float(trade_value) * float(stamp)
        return float(fee)

    def _get_bar(self, cursor, *, code: str, d: date) -> Optional[dict[str, Any]]:
        try:
            row = cursor.execute(
                "SELECT close, pct_change, amount, high, low FROM daily_prices WHERE code = ? AND trade_date = ?",
                (str(code), d.isoformat()),
            ).fetchone()
        except Exception:
            return None
        if not row:
            return None
        close = row[0] if len(row) > 0 else None
        pct_change = row[1] if len(row) > 1 else None
        amount = row[2] if len(row) > 2 else None
        high = row[3] if len(row) > 3 else None
        low = row[4] if len(row) > 4 else None
        if close is None:
            return None
        try:
            close_f = float(close)
        except Exception:
            return None
        if close_f <= 0:
            return None
        high_f = None
        if high is not None:
            try:
                high_f = float(high)
            except Exception:
                high_f = None
        low_f = None
        if low is not None:
            try:
                low_f = float(low)
            except Exception:
                low_f = None
        return {
            "close": close_f,
            "pct_change": float(pct_change) if pct_change is not None else None,
            "amount": float(amount) if amount is not None else None,
            "high": high_f,
            "low": low_f,
        }

    def _trade_block_reason(
        self,
        *,
        bar: Optional[dict[str, Any]],
        side: str,
        trade_value: float,
    ) -> Optional[str]:
        cfg = self.config if isinstance(self.config, LowFreqV16Config) else LowFreqV16Config()
        ex = getattr(cfg, "execution", ExecutionConstraints())
        base_ex = ex if isinstance(ex, ExecutionConstraints) else ExecutionConstraints()
        if not isinstance(bar, dict):
            return "missing_price_bar"
        pct = bar.get("pct_change")
        if pct is not None:
            limit_up = float(getattr(self, "EXEC_LIMIT_UP_PCT", base_ex.limit_up_pct) or 9.8)
            limit_down = float(getattr(self, "EXEC_LIMIT_DOWN_PCT", base_ex.limit_down_pct) or -9.8)
            one_price_only = bool(getattr(self, "EXEC_BLOCK_ONLY_ONE_PRICE_LIMIT", False))
            high = bar.get("high")
            low = bar.get("low")
            close = bar.get("close")
            is_one_price_board = (
                isinstance(high, (int, float))
                and isinstance(low, (int, float))
                and isinstance(close, (int, float))
                and abs(float(high) - float(low)) <= 1e-9
                and abs(float(high) - float(close)) <= 1e-9
            )
            buy_limit_hit = float(pct) >= limit_up and (is_one_price_board if one_price_only else True)
            sell_limit_hit = float(pct) <= limit_down and (is_one_price_board if one_price_only else True)
            if str(side) == "buy" and bool(getattr(self, "EXEC_BLOCK_ON_LIMIT_UP", base_ex.block_on_limit_up)) and buy_limit_hit:
                return "limit_up"
            if str(side) == "sell" and bool(getattr(self, "EXEC_BLOCK_ON_LIMIT_DOWN", base_ex.block_on_limit_down)) and sell_limit_hit:
                return "limit_down"
        amount = bar.get("amount")
        min_amount = float(getattr(self, "EXEC_MIN_AMOUNT_CNY", base_ex.min_amount_cny) or 0.0)
        if min_amount > 0 and isinstance(amount, (int, float)) and float(amount) < min_amount:
            return "min_amount"
        max_pr = float(getattr(self, "EXEC_MAX_PARTICIPATION_RATE", base_ex.max_participation_rate) or 1.0)
        if max_pr < 1.0 and isinstance(amount, (int, float)) and float(amount) > 0:
            if float(trade_value) > float(amount) * max_pr:
                return "participation_rate"
        return None

    def run_backtest(
        self,
        start_date: date,
        end_date: date,
        initial_capital: float = 1000000.0,
        rebalance_days: int = 10,
        *,
        include_daily_values: bool = False,
        include_trades: bool = False,
    ) -> dict:
        logger.info(f"低频交易回测 v16: {start_date} ~ {end_date}")

        trading_dates = self._get_trading_dates(start_date, end_date)
        logger.info(f"交易日: {len(trading_dates)}")

        unbounded_mode = self._is_unbounded_opportunity_mode()
        capital_gross = float(initial_capital)
        capital_net = float(initial_capital)
        positions: dict[str, TradeRecord] = {}
        all_trades: list[TradeRecord] = []
        daily_values_gross: list[dict[str, Any]] = []
        daily_values_net: list[dict[str, Any]] = []
        pending_buy_attempts: dict[str, dict[str, Any]] = {}
        pending_reserved_attempts: dict[str, dict[str, Any]] = {}
        tracking_runtime_state: dict[str, dict[str, Any]] = {}
        rotation_cache: dict[tuple[str, str], dict[str, Any]] = {}
        peak_gross = float(initial_capital)
        peak_net = float(initial_capital)
        max_dd_gross = 0.0
        max_dd_net = 0.0
        max_dd_trace_gross = {
            "date": start_date.isoformat(),
            "peak_value": round(float(initial_capital), 2),
            "trough_value": round(float(initial_capital), 2),
            "drawdown_pct": 0.0,
        }
        max_dd_trace_net = {
            "date": start_date.isoformat(),
            "peak_value": round(float(initial_capital), 2),
            "trough_value": round(float(initial_capital), 2),
            "drawdown_pct": 0.0,
        }
        min_value_gross = {
            "date": start_date.isoformat(),
            "total_value": round(float(initial_capital), 2),
        }
        min_value_net = {
            "date": start_date.isoformat(),
            "total_value": round(float(initial_capital), 2),
        }

        trade_blocks: dict[str, int] = {
            "buy_limit_up": 0,
            "sell_limit_down": 0,
            "buy_min_amount": 0,
            "sell_min_amount": 0,
            "buy_participation_rate": 0,
            "sell_participation_rate": 0,
            "buy_missing_price_bar": 0,
            "sell_missing_price_bar": 0,
            "buy_insufficient_cash": 0,
            "buy_chase_entry_blocked": 0,
            "buy_execution_signal_gate_blocked": 0,
            "buy_reserved_due_to_full_book": 0,
            "buy_reserved_expired": 0,
            "buy_reserved_released_into_buy": 0,
            "buy_rotation_sell": 0,
            "buy_rotation_sell_blocked": 0,
        }
        sell_signal_audit: list[dict[str, Any]] = []
        buy_signal_audit: list[dict[str, Any]] = []
        self._sell_signal_audit_current_run = sell_signal_audit
        self._buy_signal_audit_current_run = buy_signal_audit

        conn = self._conn()
        try:
            cursor = conn.cursor()
            buy_signal_memory_days = max(int(getattr(self, "BUY_SIGNAL_MEMORY_DAYS", 5) or 0), 0)
            for i, current_date in enumerate(trading_dates):
                rotation_cache.clear()
                # 检查持仓卖出信号
                closed_codes = []
                for code, trade in list(positions.items()):
                    sell = self.check_sell_signal_v2(trade, current_date)
                    if not sell:
                        continue
                    bar = self._get_bar(cursor, code=str(code), d=current_date)
                    ref_price = bar.get("close") if isinstance(bar, dict) else None
                    if not ref_price:
                        trade_blocks["sell_missing_price_bar"] += 1
                        continue
                    ratio = 0.5 if str(getattr(sell, "reason", "") or "") == "partial_profit" and not trade.partial_taken else 1.0
                    original_shares = int(trade.shares)
                    shares_to_sell = int(original_shares // 2) if ratio < 1.0 else int(original_shares)
                    if shares_to_sell <= 0:
                        continue
                    exec_price = self._slippage_adjust_price(price=float(ref_price), side="sell")
                    trade_value = float(exec_price) * int(shares_to_sell)
                    reason = self._trade_block_reason(bar=bar, side="sell", trade_value=trade_value)
                    if reason:
                        if reason == "limit_down":
                            trade_blocks["sell_limit_down"] += 1
                        elif reason == "min_amount":
                            trade_blocks["sell_min_amount"] += 1
                        elif reason == "participation_rate":
                            trade_blocks["sell_participation_rate"] += 1
                        elif reason == "missing_price_bar":
                            trade_blocks["sell_missing_price_bar"] += 1
                        continue
                    fee = self._calc_trade_fee(trade_value=trade_value, side="sell")
                    gross_proceeds = float(ref_price) * int(shares_to_sell)
                    net_proceeds = float(trade_value) - float(fee)
                    capital_gross += float(gross_proceeds)
                    capital_net += float(net_proceeds)

                    gross_ret = (float(ref_price) - float(trade.buy_price_ref or trade.buy_price)) / max(
                        float(trade.buy_price_ref or trade.buy_price), 1e-9
                    ) * 100.0
                    buy_value = float(trade.buy_price) * int(shares_to_sell)
                    buy_fee_total = float(trade.buy_fee or 0.0)
                    buy_fee_alloc = buy_fee_total * float(shares_to_sell) / max(float(original_shares), 1.0)
                    net_ret = (float(net_proceeds) - float(buy_value) - float(buy_fee_alloc)) / max(
                        float(buy_value) + float(buy_fee_alloc), 1e-9
                    ) * 100.0

                    closed_trade = TradeRecord(**trade.__dict__)
                    closed_trade.shares = int(shares_to_sell)
                    closed_trade.buy_fee = float(buy_fee_alloc)
                    closed_trade.sell_date = current_date.isoformat()
                    closed_trade.sell_price_ref = float(ref_price)
                    closed_trade.sell_price = float(exec_price)
                    closed_trade.sell_fee = float(fee)
                    closed_trade.return_pct = round(float(gross_ret), 2)
                    closed_trade.net_return_pct = round(float(net_ret), 2)
                    closed_trade.hold_days = self._count_trading_days(date.fromisoformat(trade.buy_date), current_date)
                    closed_trade.sell_reason = sell.details
                    closed_trade.status = "closed"
                    all_trades.append(closed_trade)

                    if ratio < 1.0:
                        trade.shares = int(original_shares - shares_to_sell)
                        trade.shares_sold += int(shares_to_sell)
                        trade.partial_taken = True
                        trade.buy_fee = max(float(buy_fee_total) - float(buy_fee_alloc), 0.0)
                        logger.info(
                            f"  卖出: {code} | {sell.reason} | 半仓{gross_ret:+.1f}% | 剩余{trade.shares}股 | {closed_trade.hold_days}天"
                        )
                    else:
                        closed_codes.append(code)
                        logger.info(f"  卖出: {code} | {sell.reason} | {gross_ret:+.1f}% | {closed_trade.hold_days}天")

                for code in closed_codes:
                    del positions[code]

                # 处理短窗口内待买入信号。reserved elite queue 先于普通 pending queue。
                ranked_reserved_attempts = sorted(
                    list(pending_reserved_attempts.items()),
                    key=lambda item: (
                        float(
                            (
                                item[1].get("sig", {}).get("buy_score")
                                if isinstance(item[1], dict) and isinstance(item[1].get("sig"), dict)
                                else 0.0
                            )
                            or 0.0
                        ),
                        str(item[1].get("first_date") or "") if isinstance(item[1], dict) else "",
                    ),
                    reverse=True,
                )
                ranked_pending_attempts = sorted(
                    list(pending_buy_attempts.items()),
                    key=lambda item: (
                        float(
                            (
                                item[1].get("sig", {}).get("buy_score")
                                if isinstance(item[1], dict) and isinstance(item[1].get("sig"), dict)
                                else 0.0
                            )
                            or 0.0
                        ),
                        str(item[1].get("first_date") or "") if isinstance(item[1], dict) else "",
                    ),
                    reverse=True,
                )
                for queue_name, queue_items in (
                    ("reserved", ranked_reserved_attempts),
                    ("pending", ranked_pending_attempts),
                ):
                    active_queue = pending_reserved_attempts if queue_name == "reserved" else pending_buy_attempts
                    for code, payload in queue_items:
                        if code in positions:
                            active_queue.pop(code, None)
                            continue
                        expire_idx = int(payload.get("expire_idx") or -1)
                        if i > expire_idx:
                            active_queue.pop(code, None)
                            if queue_name == "reserved":
                                trade_blocks["buy_reserved_expired"] += 1
                                sig = payload.get("sig") if isinstance(payload.get("sig"), dict) else {}
                                self._record_buy_signal_audit_event(
                                    event_type="reservation_expired",
                                    current_date=current_date,
                                    code=str(code),
                                    sig=sig,
                                    payload=payload,
                                    snapshot={
                                        "blocked_reason": "reservation_expired",
                                        "details": "elite reservation expired before a slot opened",
                                    },
                                )
                            continue

                        sig = payload.get("sig") if isinstance(payload.get("sig"), dict) else {}
                        execution_gate = self._execution_signal_gate_snapshot(sig=sig)
                        if isinstance(execution_gate, dict) and bool(execution_gate.get("blocked")):
                            trade_blocks["buy_execution_signal_gate_blocked"] += 1
                            self._record_buy_signal_audit_event(
                                event_type="execution_signal_gate_blocked",
                                current_date=current_date,
                                code=str(code),
                                sig=sig,
                                payload=payload,
                                snapshot=execution_gate,
                            )
                            continue
                        slots = int(self.MAX_POSITIONS) - len(positions)
                        if not unbounded_mode and slots <= 0:
                            if queue_name == "pending" and bool(getattr(self, "EXECUTION_RESERVATION_ENABLED", True)):
                                elite_snapshot = self._elite_execution_candidate_snapshot(sig=sig)
                                if bool(elite_snapshot.get("eligible")):
                                    reserve_days = max(
                                        int(getattr(self, "EXECUTION_RESERVATION_MEMORY_DAYS", 3) or 0),
                                        1,
                                    )
                                    reserve_expire_idx = min(len(trading_dates) - 1, i + reserve_days)
                                    reserve_payload = dict(payload)
                                    reserve_payload["reserved_from_date"] = current_date.isoformat()
                                    reserve_payload["reservation_source"] = "full_book"
                                    reserve_payload["expire_idx"] = max(
                                        int(reserve_payload.get("expire_idx") or reserve_expire_idx),
                                        int(reserve_expire_idx),
                                    )
                                    pending_reserved_attempts[str(code)] = reserve_payload
                                    pending_buy_attempts.pop(str(code), None)
                                    trade_blocks["buy_reserved_due_to_full_book"] += 1
                                    self._record_buy_signal_audit_event(
                                        event_type="reservation_created",
                                        current_date=current_date,
                                        code=str(code),
                                        sig=sig,
                                        payload=reserve_payload,
                                        snapshot={
                                            "blocked_reason": "reserved_due_to_full_book",
                                            "min_score_required": elite_snapshot.get("min_score_required"),
                                            "details": (
                                                f"elite candidate reserved because book is full | "
                                                f"reserve_until_idx={int(reserve_payload.get('expire_idx') or reserve_expire_idx)}"
                                            ),
                                        },
                                    )
                            continue
                        bar = self._get_bar(cursor, code=str(code), d=current_date)
                        ref_price = bar.get("close") if isinstance(bar, dict) else None
                        if not ref_price or float(ref_price) <= 0:
                            trade_blocks["buy_missing_price_bar"] += 1
                            continue
                        chase_snapshot = self._chase_entry_snapshot(
                            cursor,
                            code=str(code),
                            target_date=current_date,
                            ref_price=float(ref_price),
                        )
                        if isinstance(chase_snapshot, dict) and bool(chase_snapshot.get("blocked")):
                            trade_blocks["buy_chase_entry_blocked"] += 1
                            self._record_buy_signal_audit_event(
                                event_type="chase_entry_blocked",
                                current_date=current_date,
                                code=str(code),
                                sig=sig,
                                payload=payload,
                                snapshot=chase_snapshot,
                            )
                            continue

                        if unbounded_mode:
                            per_slot_gross = self._opportunity_unit_budget(float(initial_capital))
                            per_slot_net = self._opportunity_unit_budget(float(initial_capital))
                        else:
                            per_slot_gross = capital_gross / max(slots, 1)
                            per_slot_net = capital_net / max(slots, 1)
                        lot = int(
                            getattr(getattr(self.config, "execution", ExecutionConstraints()), "lot_size", 100) or 100
                        )
                        shares_gross = int(per_slot_gross / float(ref_price) / lot) * lot
                        shares_net = int(per_slot_net / float(ref_price) / lot) * lot
                        shares = int(min(shares_gross, shares_net))
                        if shares < lot:
                            continue
                        exec_price = self._slippage_adjust_price(price=float(ref_price), side="buy")
                        trade_value = float(exec_price) * int(shares)
                        reason = self._trade_block_reason(bar=bar, side="buy", trade_value=trade_value)
                        if reason:
                            if reason == "limit_up":
                                trade_blocks["buy_limit_up"] += 1
                            elif reason == "min_amount":
                                trade_blocks["buy_min_amount"] += 1
                            elif reason == "participation_rate":
                                trade_blocks["buy_participation_rate"] += 1
                            elif reason == "missing_price_bar":
                                trade_blocks["buy_missing_price_bar"] += 1
                            continue
                        fee = self._calc_trade_fee(trade_value=trade_value, side="buy")
                        gross_cost = float(ref_price) * int(shares)
                        net_cost = float(trade_value) + float(fee)
                        if (not unbounded_mode) and (gross_cost > capital_gross or net_cost > capital_net):
                            trade_blocks["buy_insufficient_cash"] += 1
                            continue
                        capital_gross -= float(gross_cost)
                        capital_net -= float(net_cost)
                        positions[code] = TradeRecord(
                            code=code,
                            name=str(sig.get("name") or ""),
                            sector=str(sig.get("sector") or ""),
                            buy_date=current_date.isoformat(),
                            buy_price=float(exec_price),
                            buy_price_ref=float(ref_price),
                            shares=shares,
                            buy_score=float(sig.get("buy_score") or 0.0),
                            wave_phase=str(sig.get("wave_phase") or ""),
                            buy_progress_label=self._resolve_buy_progress_label(signal=sig),
                            peak_price=float(exec_price),
                            role=str(sig.get("role") or ""),
                            buy_fee=float(fee),
                            status="open",
                        )
                        active_queue.pop(code, None)
                        if queue_name == "reserved":
                            trade_blocks["buy_reserved_released_into_buy"] += 1
                            self._record_buy_signal_audit_event(
                                event_type="reservation_released_into_buy",
                                current_date=current_date,
                                code=str(code),
                                sig=sig,
                                payload=payload,
                                snapshot={
                                    "blocked_reason": "reservation_released_into_buy",
                                    "details": "reserved elite candidate converted into a real position",
                                },
                            )
                        logger.info(
                            f"  买入: {code} {sig.get('name') or ''} | "
                            f"评分:{float(sig.get('buy_score') or 0.0):.1f} | {sig.get('wave_phase') or ''} | "
                            f"角色:{sig.get('role') or ''} | 来源信号日:{payload.get('first_date') or current_date.isoformat()} | "
                            f"队列:{queue_name}"
                        )

                # 每日记录正式买入信号到短窗口记忆，在后续交易日继续尝试。
                if buy_signal_memory_days > 0:
                    try:
                        signals = self.generate_buy_signals(current_date)
                        effective_entry_signals = self._record_tracking_candidate_events(
                            current_date=current_date,
                            signals=signals,
                            tracking_runtime_state=tracking_runtime_state,
                            positions=positions,
                        )
                        expire_idx = min(len(trading_dates) - 1, i + buy_signal_memory_days)
                        for sig in effective_entry_signals:
                            if not isinstance(sig, dict):
                                continue
                            code = str(sig.get("code") or "").strip()
                            if not code or code in positions:
                                continue
                            payload = {
                                "sig": dict(sig),
                                "first_date": current_date.isoformat(),
                                "expire_idx": int(expire_idx),
                            }
                            existing_reserved = pending_reserved_attempts.get(code)
                            if isinstance(existing_reserved, dict):
                                existing_expire = int(existing_reserved.get("expire_idx") or i)
                                existing_score = float(
                                    (
                                        existing_reserved.get("sig", {}).get("buy_score")
                                        if isinstance(existing_reserved.get("sig"), dict)
                                        else 0.0
                                    )
                                    or 0.0
                                )
                                new_score = float(sig.get("buy_score") or 0.0)
                                if existing_expire >= int(expire_idx) and existing_score >= new_score:
                                    continue
                                updated_reserved = dict(payload)
                                updated_reserved["reserved_from_date"] = str(
                                    existing_reserved.get("reserved_from_date") or current_date.isoformat()
                                )
                                updated_reserved["reservation_source"] = str(
                                    existing_reserved.get("reservation_source") or "full_book"
                                )
                                updated_reserved["expire_idx"] = max(int(expire_idx), existing_expire)
                                pending_reserved_attempts[code] = updated_reserved
                                continue
                            existing = pending_buy_attempts.get(code)
                            if isinstance(existing, dict):
                                existing_expire = int(existing.get("expire_idx") or i)
                                existing_score = float(
                                    (
                                        existing.get("sig", {}).get("buy_score")
                                        if isinstance(existing.get("sig"), dict)
                                        else 0.0
                                    )
                                    or 0.0
                                )
                                new_score = float(sig.get("buy_score") or 0.0)
                                if existing_expire >= int(expire_idx) and existing_score >= new_score:
                                    continue
                            pending_buy_attempts[code] = payload
                    except Exception as e:
                        logger.warning(f"信号生成失败 {current_date}: {e}")
                elif i % self.REBALANCE_DAYS == 0 and (unbounded_mode or len(positions) < self.MAX_POSITIONS):
                    try:
                        signals = self.generate_buy_signals(current_date)
                        effective_entry_signals = self._record_tracking_candidate_events(
                            current_date=current_date,
                            signals=signals,
                            tracking_runtime_state=tracking_runtime_state,
                            positions=positions,
                        )
                        expire_idx = i
                        for sig in effective_entry_signals:
                            if not isinstance(sig, dict):
                                continue
                            code = str(sig.get("code") or "").strip()
                            if not code or code in positions:
                                continue
                            payload = {
                                "sig": dict(sig),
                                "first_date": current_date.isoformat(),
                                "expire_idx": int(expire_idx),
                            }
                            existing_reserved = pending_reserved_attempts.get(code)
                            if isinstance(existing_reserved, dict):
                                existing_expire = int(existing_reserved.get("expire_idx") or i)
                                existing_score = float(
                                    (
                                        existing_reserved.get("sig", {}).get("buy_score")
                                        if isinstance(existing_reserved.get("sig"), dict)
                                        else 0.0
                                    )
                                    or 0.0
                                )
                                new_score = float(sig.get("buy_score") or 0.0)
                                if existing_expire >= int(expire_idx) and existing_score >= new_score:
                                    continue
                                updated_reserved = dict(payload)
                                updated_reserved["reserved_from_date"] = str(
                                    existing_reserved.get("reserved_from_date") or current_date.isoformat()
                                )
                                updated_reserved["reservation_source"] = str(
                                    existing_reserved.get("reservation_source") or "full_book"
                                )
                                updated_reserved["expire_idx"] = max(int(expire_idx), existing_expire)
                                pending_reserved_attempts[code] = updated_reserved
                                continue
                            existing = pending_buy_attempts.get(code)
                            if isinstance(existing, dict):
                                existing_expire = int(existing.get("expire_idx") or i)
                                existing_score = float(
                                    (
                                        existing.get("sig", {}).get("buy_score")
                                        if isinstance(existing.get("sig"), dict)
                                        else 0.0
                                    )
                                    or 0.0
                                )
                                new_score = float(sig.get("buy_score") or 0.0)
                                if existing_expire >= int(expire_idx) and existing_score >= new_score:
                                    continue
                            pending_buy_attempts[code] = payload
                    except Exception as e:
                        logger.warning(f"信号生成失败 {current_date}: {e}")

                # 计算总资产
                pos_value = 0.0
                for code, pos in positions.items():
                    bar = self._get_bar(cursor, code=str(code), d=current_date)
                    px = (
                        float(bar.get("close"))
                        if isinstance(bar, dict) and bar.get("close") is not None
                        else float(pos.buy_price_ref or pos.buy_price)
                    )
                    pos_value += float(px) * int(pos.shares)
                total_gross = float(capital_gross) + float(pos_value)
                total_net = float(capital_net) + float(pos_value)
                if total_gross > peak_gross:
                    peak_gross = float(total_gross)
                if total_net > peak_net:
                    peak_net = float(total_net)
                dd_gross = (float(peak_gross) - float(total_gross)) / float(peak_gross) * 100.0 if peak_gross > 0 else 0.0
                dd_net = (float(peak_net) - float(total_net)) / float(peak_net) * 100.0 if peak_net > 0 else 0.0
                if dd_gross > max_dd_gross:
                    max_dd_gross = float(dd_gross)
                    max_dd_trace_gross = {
                        "date": current_date.isoformat(),
                        "peak_value": round(float(peak_gross), 2),
                        "trough_value": round(float(total_gross), 2),
                        "drawdown_pct": round(float(dd_gross), 2),
                    }
                if dd_net > max_dd_net:
                    max_dd_net = float(dd_net)
                    max_dd_trace_net = {
                        "date": current_date.isoformat(),
                        "peak_value": round(float(peak_net), 2),
                        "trough_value": round(float(total_net), 2),
                        "drawdown_pct": round(float(dd_net), 2),
                    }
                if float(total_gross) < float(min_value_gross["total_value"]):
                    min_value_gross = {
                        "date": current_date.isoformat(),
                        "total_value": round(float(total_gross), 2),
                    }
                if float(total_net) < float(min_value_net["total_value"]):
                    min_value_net = {
                        "date": current_date.isoformat(),
                        "total_value": round(float(total_net), 2),
                    }
                daily_values_gross.append(
                    {
                        "date": current_date.isoformat(),
                        "total_value": round(total_gross, 2),
                        "positions": len(positions),
                    }
                )
                daily_values_net.append(
                    {
                        "date": current_date.isoformat(),
                        "total_value": round(total_net, 2),
                        "positions": len(positions),
                    }
                )

                if (i + 1) % 50 == 0:
                    logger.info(f"  {current_date}: 总资产={total_gross:,.0f}, 持仓={len(positions)}")
        finally:
            conn.close()

        if trading_dates:
            last_day = trading_dates[-1]
            conn2 = self._conn()
            try:
                cursor2 = conn2.cursor()
                for code, trade in list(positions.items()):
                    bar = self._get_bar(cursor2, code=str(code), d=last_day)
                    ref_price = bar.get("close") if isinstance(bar, dict) else None
                    if not ref_price:
                        continue
                    exec_price = self._slippage_adjust_price(price=float(ref_price), side="sell")
                    trade_value = float(exec_price) * int(trade.shares)
                    fee = self._calc_trade_fee(trade_value=trade_value, side="sell")
                    gross_proceeds = float(ref_price) * int(trade.shares)
                    net_proceeds = float(trade_value) - float(fee)
                    capital_gross += float(gross_proceeds)
                    capital_net += float(net_proceeds)

                    gross_ret = (float(ref_price) - float(trade.buy_price_ref or trade.buy_price)) / max(
                        float(trade.buy_price_ref or trade.buy_price), 1e-9
                    ) * 100.0
                    buy_value = float(trade.buy_price) * int(trade.shares)
                    buy_fee = float(trade.buy_fee or 0.0)
                    net_ret = (float(net_proceeds) - float(buy_value) - float(buy_fee)) / max(
                        float(buy_value) + float(buy_fee), 1e-9
                    ) * 100.0

                    trade.sell_date = last_day.isoformat()
                    trade.sell_price_ref = float(ref_price)
                    trade.sell_price = float(exec_price)
                    trade.sell_fee = float(fee)
                    trade.return_pct = round(float(gross_ret), 2)
                    trade.net_return_pct = round(float(net_ret), 2)
                    trade.hold_days = self._count_trading_days(date.fromisoformat(trade.buy_date), last_day)
                    trade.sell_reason = "回测结束平仓"
                    trade.status = "closed"
                    if bool(getattr(trade, "system_exit_grace_used", False)):
                        self._record_system_exit_grace_audit_event(
                            event_type="system_exit_downgraded_then_end_flat",
                            trade=trade,
                            current_date=last_day,
                            scope=str(getattr(trade, "system_exit_grace_scope", "") or "end_flat"),
                            snapshot=None,
                            current_return_pct=self._current_return_pct(trade, current_price=float(ref_price)),
                            peak_return_pct=self._peak_return_pct(trade),
                            profit_keep_ratio=self._profit_keep_ratio(
                                current_return_pct=self._current_return_pct(trade, current_price=float(ref_price)),
                                peak_return_pct=self._peak_return_pct(trade),
                            ),
                        )
                    all_trades.append(trade)
                positions.clear()
            finally:
                conn2.close()

            last_day_iso = last_day.isoformat()
            final_total_gross = round(float(capital_gross), 2)
            final_total_net = round(float(capital_net), 2)
            if daily_values_gross and daily_values_gross[-1].get("date") == last_day_iso:
                daily_values_gross[-1] = {
                    "date": last_day_iso,
                    "total_value": final_total_gross,
                    "positions": 0,
                }
            else:
                daily_values_gross.append(
                    {
                        "date": last_day_iso,
                        "total_value": final_total_gross,
                        "positions": 0,
                    }
                )
            if daily_values_net and daily_values_net[-1].get("date") == last_day_iso:
                daily_values_net[-1] = {
                    "date": last_day_iso,
                    "total_value": final_total_net,
                    "positions": 0,
                }
            else:
                daily_values_net.append(
                    {
                        "date": last_day_iso,
                        "total_value": final_total_net,
                        "positions": 0,
                    }
                )

            if final_total_gross > peak_gross:
                peak_gross = float(final_total_gross)
            if final_total_net > peak_net:
                peak_net = float(final_total_net)
            dd_gross = (
                (float(peak_gross) - float(final_total_gross)) / float(peak_gross) * 100.0
                if peak_gross > 0
                else 0.0
            )
            dd_net = (
                (float(peak_net) - float(final_total_net)) / float(peak_net) * 100.0
                if peak_net > 0
                else 0.0
            )
            if dd_gross > max_dd_gross:
                max_dd_gross = float(dd_gross)
                max_dd_trace_gross = {
                    "date": last_day_iso,
                    "peak_value": round(float(peak_gross), 2),
                    "trough_value": round(float(final_total_gross), 2),
                    "drawdown_pct": round(float(dd_gross), 2),
                }
            if dd_net > max_dd_net:
                max_dd_net = float(dd_net)
                max_dd_trace_net = {
                    "date": last_day_iso,
                    "peak_value": round(float(peak_net), 2),
                    "trough_value": round(float(final_total_net), 2),
                    "drawdown_pct": round(float(dd_net), 2),
                }
            if float(final_total_gross) < float(min_value_gross["total_value"]):
                min_value_gross = {
                    "date": last_day_iso,
                    "total_value": round(float(final_total_gross), 2),
                }
            if float(final_total_net) < float(min_value_net["total_value"]):
                min_value_net = {
                    "date": last_day_iso,
                    "total_value": round(float(final_total_net), 2),
                }

        gross_metrics = self._calc_metrics(daily_values_gross, all_trades, float(initial_capital))
        net_metrics = self._calc_metrics(daily_values_net, all_trades, float(initial_capital))
        gross_metrics["net_metrics"] = net_metrics
        gross_metrics["trade_blocks"] = trade_blocks
        gross_metrics["config_snapshot"] = self.get_config_snapshot()
        gross_metrics["drawdown_trace_gross"] = max_dd_trace_gross
        gross_metrics["drawdown_trace_net"] = max_dd_trace_net
        gross_metrics["min_value_gross"] = min_value_gross
        gross_metrics["min_value_net"] = min_value_net
        gross_metrics["coverage_gaps"] = {
            "market_cap_point_in_time": False,
            "north_south_flow": False,
            "l2_dragon_tiger": False,
        }
        gross_metrics["sell_signal_audit"] = sell_signal_audit
        gross_metrics["buy_signal_audit"] = buy_signal_audit
        if bool(include_daily_values):
            gross_metrics["daily_values_gross"] = daily_values_gross
            gross_metrics["daily_values_net"] = daily_values_net
        if bool(include_trades):
            from dataclasses import asdict

            gross_metrics["trades"] = [asdict(t) for t in all_trades]
        self._sell_signal_audit_current_run = None
        self._buy_signal_audit_current_run = None
        return gross_metrics


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
        if not row or row[0] is None:
            return None
        try:
            price = float(row[0])
        except Exception:
            return None
        return price if price > 0 else None

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
