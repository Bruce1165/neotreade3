from __future__ import annotations

from datetime import date, timedelta

from lowfreq_engine_v16_advanced import LowFreqTradingEngineV16, TradeRecord


def _make_engine(
    *,
    price: float,
    market_exit_snapshot: dict | None = None,
    sector_exit_snapshot: dict | None = None,
) -> LowFreqTradingEngineV16:
    engine = LowFreqTradingEngineV16.__new__(LowFreqTradingEngineV16)
    engine._get_price = lambda code, current_date: float(price)
    engine._market_exit_snapshot = lambda trade, current_date, market_key=None: market_exit_snapshot
    engine._sector_exit_snapshot = lambda trade, current_date: sector_exit_snapshot
    engine._resolve_market_proxy = lambda code: "cyb"
    engine._get_trading_dates = lambda start, end: [
        start + timedelta(days=i) for i in range(max((end - start).days, 0) + 1)
    ]
    engine._count_trading_days = lambda start, end: (end - start).days + 1
    engine._sell_signal_audit_current_run = []
    engine.STOP_LOSS_PCT = -5.0
    engine.TRAILING_PROFIT_LEVEL = 20.0
    engine.TRAILING_STOP_PCT = -5.0
    engine.MIN_HOLD_DAYS = 15
    engine.MARKET_EXIT_CONFIRM_WINDOW = 5
    engine.MARKET_EXIT_CONFIRM_HITS = 3
    engine.SECTOR_EXIT_CONFIRM_WINDOW = 4
    engine.SECTOR_EXIT_CONFIRM_HITS = 3
    engine.LEADER_HOLD_MIN_PEAK_RETURN_PCT = 15.0
    engine.LEADER_CONFIRM_EXTRA_HITS = 1
    engine.SYSTEM_EXIT_GRACE_ENABLED = True
    engine.SYSTEM_EXIT_GRACE_MIN_PEAK_RETURN_PCT = 20.0
    engine.SYSTEM_EXIT_GRACE_REQUIRE_POSITIVE_RETURN = True
    engine.SYSTEM_EXIT_GRACE_MARKET_MIN_PEAK_RETURN_PCT = 20.0
    engine.SYSTEM_EXIT_GRACE_MARKET_MIN_CURRENT_PROFIT_PCT = 10.0
    engine.SYSTEM_EXIT_GRACE_MARKET_MIN_PROFIT_KEEP_RATIO = 0.50
    engine.SYSTEM_EXIT_GRACE_SECTOR_MIN_PEAK_RETURN_PCT = 10.0
    engine.SYSTEM_EXIT_GRACE_SECTOR_MIN_CURRENT_PROFIT_PCT = 10.0
    engine.SYSTEM_EXIT_GRACE_SECTOR_MIN_PROFIT_KEEP_RATIO = 0.60
    engine.SYSTEM_EXIT_GRACE_SECTOR_MAX_HOLD_DAYS = 10
    return engine


def _make_trade(
    *,
    code: str = "300001",
    buy_price: float = 100.0,
    peak_price: float = 100.0,
    role: str = "普通",
    wave_phase: str = "3浪",
    buy_progress_label: str = "早窗",
    hold_days: int = 0,
) -> TradeRecord:
    return TradeRecord(
        code=str(code),
        name="测试标的",
        sector="AI",
        buy_date="2026-01-05",
        buy_price=float(buy_price),
        peak_price=float(peak_price),
        shares=200,
        role=str(role),
        wave_phase=str(wave_phase),
        buy_progress_label=str(buy_progress_label),
        hold_days=int(hold_days),
    )


def _market_exit_hit_snapshot() -> dict:
    return {
        "scope": "market",
        "market_key": "cyb",
        "market_label": "创业板",
        "condition_pass": True,
        "evidence_count": 2,
        "details": "创业板见顶确认候选：趋势转弱=是 | 广度转弱=是 | 代理回撤-10.5%",
    }


def _sector_exit_hit_snapshot() -> dict:
    return {
        "scope": "sector",
        "sector": "AI",
        "condition_pass": True,
        "trend_state": "diverging",
        "evidence_count": 2,
        "details": "板块见顶确认候选：AI | 趋势=diverging | 跟随股弱势70% | 龙头强度48%",
    }


def test_market_proxy_resolution_matches_expected_board() -> None:
    engine = LowFreqTradingEngineV16.__new__(LowFreqTradingEngineV16)

    assert engine._resolve_market_proxy("688001") == "kcb"
    assert engine._resolve_market_proxy("300001") == "cyb"
    assert engine._resolve_market_proxy("301001") == "cyb"
    assert engine._resolve_market_proxy("600001") == "sse"
    assert engine._resolve_market_proxy("002001") == "szse"
    assert engine._resolve_market_proxy("000001") == "szse"
    assert engine._resolve_market_proxy("430001") is None


def test_entry_stop_loss_has_highest_priority() -> None:
    engine = _make_engine(
        price=94.0,
        market_exit_snapshot=_market_exit_hit_snapshot(),
        sector_exit_snapshot=_sector_exit_hit_snapshot(),
    )
    trade = _make_trade(role="龙头", peak_price=120.0)
    trade.buy_date = "2026-06-16"

    sell = engine.check_sell_signal_v2(trade, date(2026, 6, 18))

    assert sell is not None
    assert sell.reason == "thesis_invalidated"
    assert sell.source_layer == "invalidation"
    assert sell.invalidated_reason == "entry_stop_loss"
    assert sell.invalidated_window == "early"
    assert "硬证伪退出" in sell.details
    assert trade.market_exit_state == ""
    assert trade.sector_exit_state == ""


def test_old_stock_drawdown_no_longer_triggers_direct_sell() -> None:
    engine = _make_engine(price=100.0, market_exit_snapshot=None, sector_exit_snapshot=None)
    trade = _make_trade(peak_price=130.0)

    sell = engine.check_sell_signal_v2(trade, date(2026, 6, 18))

    assert sell is None


def test_trend_exhausted_triggers_for_profitable_trade_after_peak_drawdown() -> None:
    engine = _make_engine(price=116.0, market_exit_snapshot=None, sector_exit_snapshot=None)
    trade = _make_trade(peak_price=130.0, hold_days=20, buy_progress_label="其它")

    sell = engine.check_sell_signal_v2(trade, date(2026, 6, 18))

    assert sell is not None
    assert sell.reason == "trend_exhausted"
    assert sell.source_layer == "exit"
    assert sell.exit_scope == "position_only"
    assert "距峰值回撤" in sell.details
    events = [entry["event"] for entry in engine._sell_signal_audit_current_run]
    assert "trend_exhausted" in events


def test_trend_exhausted_does_not_trigger_before_min_hold_days() -> None:
    engine = _make_engine(price=116.0, market_exit_snapshot=None, sector_exit_snapshot=None)
    trade = _make_trade(peak_price=130.0, hold_days=8)

    sell = engine.check_sell_signal_v2(trade, date(2026, 6, 18))

    assert sell is None


def test_market_signal_first_hit_only_starts_observe() -> None:
    engine = _make_engine(price=100.0, market_exit_snapshot=_market_exit_hit_snapshot(), sector_exit_snapshot=None)
    trade = _make_trade()

    sell = engine.check_sell_signal_v2(trade, date(2026, 6, 18))

    assert sell is None
    assert trade.market_exit_state == "observe"
    assert trade.market_exit_start_date == "2026-06-18"
    assert trade.market_exit_hits == 1


def test_market_signal_second_hit_enters_review_not_sell() -> None:
    engine = _make_engine(price=100.0, market_exit_snapshot=_market_exit_hit_snapshot(), sector_exit_snapshot=None)
    trade = _make_trade()

    assert engine.check_sell_signal_v2(trade, date(2026, 6, 18)) is None
    second = engine.check_sell_signal_v2(trade, date(2026, 6, 19))

    assert second is None
    assert trade.market_exit_state == "review"
    assert trade.market_exit_hits == 2


def test_market_signal_third_hit_confirms_sell() -> None:
    engine = _make_engine(price=100.0, market_exit_snapshot=_market_exit_hit_snapshot(), sector_exit_snapshot=None)
    trade = _make_trade()

    assert engine.check_sell_signal_v2(trade, date(2026, 6, 18)) is None
    assert engine.check_sell_signal_v2(trade, date(2026, 6, 19)) is None
    third = engine.check_sell_signal_v2(trade, date(2026, 6, 20))

    assert third is not None
    assert third.reason == "market_top_confirmed"
    assert "创业板见顶确认" in third.details
    assert trade.market_exit_state == ""
    assert trade.market_exit_hits == 0


def test_market_signal_expires_without_enough_hits() -> None:
    snapshots = {
        "2026-06-18": _market_exit_hit_snapshot(),
        "2026-06-19": None,
        "2026-06-20": None,
        "2026-06-21": None,
        "2026-06-22": None,
        "2026-06-23": None,
    }
    engine = _make_engine(price=100.0, market_exit_snapshot=None, sector_exit_snapshot=None)
    engine._market_exit_snapshot = lambda trade, current_date, market_key=None: snapshots.get(current_date.isoformat())
    trade = _make_trade()

    assert engine.check_sell_signal_v2(trade, date(2026, 6, 18)) is None
    assert engine.check_sell_signal_v2(trade, date(2026, 6, 19)) is None
    assert engine.check_sell_signal_v2(trade, date(2026, 6, 20)) is None
    assert engine.check_sell_signal_v2(trade, date(2026, 6, 21)) is None
    assert engine.check_sell_signal_v2(trade, date(2026, 6, 22)) is None
    assert engine.check_sell_signal_v2(trade, date(2026, 6, 23)) is None
    assert trade.market_exit_state == ""
    assert trade.market_exit_hits == 0


def test_market_signal_expire_then_same_day_hit_restarts_observe() -> None:
    snapshots = {
        "2026-06-18": _market_exit_hit_snapshot(),
        "2026-06-19": None,
        "2026-06-20": None,
        "2026-06-21": None,
        "2026-06-22": None,
        "2026-06-23": _market_exit_hit_snapshot(),
    }
    engine = _make_engine(price=100.0, market_exit_snapshot=None, sector_exit_snapshot=None)
    engine._market_exit_snapshot = lambda trade, current_date, market_key=None: snapshots.get(current_date.isoformat())
    trade = _make_trade()

    assert engine.check_sell_signal_v2(trade, date(2026, 6, 18)) is None
    assert engine.check_sell_signal_v2(trade, date(2026, 6, 19)) is None
    assert engine.check_sell_signal_v2(trade, date(2026, 6, 20)) is None
    assert engine.check_sell_signal_v2(trade, date(2026, 6, 21)) is None
    assert engine.check_sell_signal_v2(trade, date(2026, 6, 22)) is None

    restarted = engine.check_sell_signal_v2(trade, date(2026, 6, 23))

    assert restarted is None
    assert trade.market_exit_state == "observe"
    assert trade.market_exit_start_date == "2026-06-23"
    assert trade.market_exit_expire_date == "2026-06-27"
    assert trade.market_exit_hits == 1
    assert trade.market_exit_last_hit_date == "2026-06-23"
    assert "创业板见顶确认候选" in trade.market_exit_last_reason
    events = [entry["event"] for entry in engine._sell_signal_audit_current_run]
    assert events[-2:] == ["market_exit_watch_expired", "market_exit_watch_started"]


def test_sector_signal_third_hit_confirms_sell() -> None:
    engine = _make_engine(price=100.0, market_exit_snapshot=None, sector_exit_snapshot=_sector_exit_hit_snapshot())
    trade = _make_trade()

    assert engine.check_sell_signal_v2(trade, date(2026, 6, 18)) is None
    assert engine.check_sell_signal_v2(trade, date(2026, 6, 19)) is None
    third = engine.check_sell_signal_v2(trade, date(2026, 6, 20))

    assert third is not None
    assert third.reason == "sector_top_confirmed"
    assert "板块见顶确认" in third.details
    assert trade.sector_exit_state == ""
    assert trade.sector_exit_hits == 0


def test_leader_hold_requires_extra_hit_before_market_exit() -> None:
    engine = _make_engine(price=110.0, market_exit_snapshot=_market_exit_hit_snapshot(), sector_exit_snapshot=None)
    engine.SYSTEM_EXIT_GRACE_ENABLED = False
    trade = _make_trade(role="龙头", peak_price=120.0)

    assert engine.check_sell_signal_v2(trade, date(2026, 6, 18)) is None
    assert engine.check_sell_signal_v2(trade, date(2026, 6, 19)) is None
    third = engine.check_sell_signal_v2(trade, date(2026, 6, 20))

    assert third is None
    assert trade.market_exit_state == "review"
    assert trade.market_exit_hits == 3
    fourth = engine.check_sell_signal_v2(trade, date(2026, 6, 21))
    assert fourth is not None
    assert fourth.reason == "market_top_confirmed"


def test_system_exit_grace_downgrades_first_confirm_for_eligible_leader() -> None:
    engine = _make_engine(price=110.0, market_exit_snapshot=_market_exit_hit_snapshot(), sector_exit_snapshot=None)
    engine.LEADER_CONFIRM_EXTRA_HITS = 0
    trade = _make_trade(role="龙头", peak_price=120.0)

    assert engine.check_sell_signal_v2(trade, date(2026, 6, 18)) is None
    assert engine.check_sell_signal_v2(trade, date(2026, 6, 19)) is None
    third = engine.check_sell_signal_v2(trade, date(2026, 6, 20))

    assert third is None
    assert trade.system_exit_grace_used is True
    assert trade.system_exit_grace_scope == "market"
    assert trade.market_exit_state == ""
    assert trade.sector_exit_state == ""
    events = [entry["event"] for entry in engine._sell_signal_audit_current_run]
    assert events[-1] == "system_exit_downgraded"


def test_system_exit_grace_only_applies_once_then_later_confirm_sells() -> None:
    engine = _make_engine(price=110.0, market_exit_snapshot=_market_exit_hit_snapshot(), sector_exit_snapshot=None)
    engine.LEADER_CONFIRM_EXTRA_HITS = 0
    trade = _make_trade(role="龙头", peak_price=120.0)

    assert engine.check_sell_signal_v2(trade, date(2026, 6, 18)) is None
    assert engine.check_sell_signal_v2(trade, date(2026, 6, 19)) is None
    assert engine.check_sell_signal_v2(trade, date(2026, 6, 20)) is None
    assert engine.check_sell_signal_v2(trade, date(2026, 6, 21)) is None
    assert engine.check_sell_signal_v2(trade, date(2026, 6, 22)) is None
    sixth = engine.check_sell_signal_v2(trade, date(2026, 6, 23))

    assert sixth is not None
    assert sixth.reason == "market_top_confirmed"
    events = [entry["event"] for entry in engine._sell_signal_audit_current_run]
    assert "system_exit_downgraded" in events
    assert "system_exit_downgraded_then_confirmed" in events


def test_system_exit_grace_requires_peak_profit_cushion() -> None:
    engine = _make_engine(price=110.0, market_exit_snapshot=_market_exit_hit_snapshot(), sector_exit_snapshot=None)
    engine.LEADER_CONFIRM_EXTRA_HITS = 0
    engine.SYSTEM_EXIT_GRACE_MIN_PEAK_RETURN_PCT = 30.0
    trade = _make_trade(role="龙头", peak_price=120.0)

    assert engine.check_sell_signal_v2(trade, date(2026, 6, 18)) is None
    assert engine.check_sell_signal_v2(trade, date(2026, 6, 19)) is None
    third = engine.check_sell_signal_v2(trade, date(2026, 6, 20))

    assert third is not None
    assert third.reason == "market_top_confirmed"
    assert trade.system_exit_grace_used is False


def test_system_exit_grace_requires_early_buy_progress_label() -> None:
    engine = _make_engine(price=115.0, market_exit_snapshot=_market_exit_hit_snapshot(), sector_exit_snapshot=None)
    engine.LEADER_CONFIRM_EXTRA_HITS = 0
    trade = _make_trade(role="龙头", peak_price=125.0, buy_progress_label="其它")

    assert engine.check_sell_signal_v2(trade, date(2026, 6, 18)) is None
    assert engine.check_sell_signal_v2(trade, date(2026, 6, 19)) is None
    third = engine.check_sell_signal_v2(trade, date(2026, 6, 20))

    assert third is not None
    assert third.reason == "market_top_confirmed"
    assert trade.system_exit_grace_used is False


def test_system_exit_grace_requires_profit_keep_ratio() -> None:
    engine = _make_engine(price=112.0, market_exit_snapshot=_market_exit_hit_snapshot(), sector_exit_snapshot=None)
    engine.LEADER_CONFIRM_EXTRA_HITS = 0
    trade = _make_trade(role="龙头", peak_price=140.0, buy_progress_label="早窗")

    assert engine.check_sell_signal_v2(trade, date(2026, 6, 18)) is None
    assert engine.check_sell_signal_v2(trade, date(2026, 6, 19)) is None
    third = engine.check_sell_signal_v2(trade, date(2026, 6, 20))

    assert third is not None
    assert third.reason == "market_top_confirmed"
    assert trade.system_exit_grace_used is False


def test_sector_system_exit_grace_uses_stricter_scope_thresholds() -> None:
    engine = _make_engine(price=108.0, market_exit_snapshot=None, sector_exit_snapshot=_sector_exit_hit_snapshot())
    engine.LEADER_CONFIRM_EXTRA_HITS = 0
    trade = _make_trade(role="龙头", peak_price=120.0, buy_progress_label="前置布局")

    assert engine.check_sell_signal_v2(trade, date(2026, 6, 18)) is None
    assert engine.check_sell_signal_v2(trade, date(2026, 6, 19)) is None
    third = engine.check_sell_signal_v2(trade, date(2026, 6, 20))

    assert third is not None
    assert third.reason == "sector_top_confirmed"
    assert trade.system_exit_grace_used is False


def test_sector_system_exit_grace_allows_ultra_early_high_keep_trade() -> None:
    engine = _make_engine(price=111.73, market_exit_snapshot=None, sector_exit_snapshot=_sector_exit_hit_snapshot())
    engine.LEADER_CONFIRM_EXTRA_HITS = 0
    engine.SYSTEM_EXIT_GRACE_SECTOR_MIN_CURRENT_PROFIT_PCT = 10.0
    trade = _make_trade(
        role="中军",
        peak_price=111.73,
        buy_progress_label="早窗",
        hold_days=4,
    )

    assert engine.check_sell_signal_v2(trade, date(2026, 6, 18)) is None
    assert engine.check_sell_signal_v2(trade, date(2026, 6, 19)) is None
    third = engine.check_sell_signal_v2(trade, date(2026, 6, 20))

    assert third is None
    assert trade.system_exit_grace_used is True
    assert trade.system_exit_grace_scope == "sector"


def test_sector_system_exit_grace_rejects_longer_hold_even_if_profitable() -> None:
    engine = _make_engine(price=124.0, market_exit_snapshot=None, sector_exit_snapshot=_sector_exit_hit_snapshot())
    engine.LEADER_CONFIRM_EXTRA_HITS = 0
    engine.SYSTEM_EXIT_GRACE_SECTOR_MIN_CURRENT_PROFIT_PCT = 10.0
    trade = _make_trade(
        role="中军",
        peak_price=130.0,
        buy_progress_label="前置布局",
        hold_days=33,
    )

    assert engine.check_sell_signal_v2(trade, date(2026, 6, 18)) is None
    assert engine.check_sell_signal_v2(trade, date(2026, 6, 19)) is None
    third = engine.check_sell_signal_v2(trade, date(2026, 6, 20))

    assert third is not None
    assert third.reason == "sector_top_confirmed"
    assert trade.system_exit_grace_used is False


def test_entry_stop_loss_never_uses_system_exit_grace() -> None:
    engine = _make_engine(price=94.0, market_exit_snapshot=_market_exit_hit_snapshot(), sector_exit_snapshot=None)
    trade = _make_trade(role="龙头", peak_price=125.0)
    trade.buy_date = "2026-06-19"
    trade.system_exit_grace_used = True
    trade.system_exit_grace_scope = "market"
    trade.system_exit_grace_date = "2026-06-20"
    trade.system_exit_grace_reason = "grace-used"

    sell = engine.check_sell_signal_v2(trade, date(2026, 6, 21))

    assert sell is not None
    assert sell.reason == "thesis_invalidated"
    assert sell.source_layer == "invalidation"
    assert sell.invalidated_reason == "entry_stop_loss"
    events = [entry["event"] for entry in engine._sell_signal_audit_current_run]
    assert "system_exit_downgraded_then_stop_loss" in events


def test_system_exit_grace_skips_same_day_sector_confirmation() -> None:
    engine = _make_engine(
        price=110.0,
        market_exit_snapshot=_market_exit_hit_snapshot(),
        sector_exit_snapshot=_sector_exit_hit_snapshot(),
    )
    engine.LEADER_CONFIRM_EXTRA_HITS = 0
    trade = _make_trade(role="龙头", peak_price=120.0)

    assert engine.check_sell_signal_v2(trade, date(2026, 6, 18)) is None
    assert engine.check_sell_signal_v2(trade, date(2026, 6, 19)) is None
    third = engine.check_sell_signal_v2(trade, date(2026, 6, 20))

    assert third is None
    assert trade.system_exit_grace_used is True
    assert trade.market_exit_state == ""
    assert trade.sector_exit_state == ""


def test_market_confirmation_resets_sector_state() -> None:
    engine = _make_engine(
        price=100.0,
        market_exit_snapshot=_market_exit_hit_snapshot(),
        sector_exit_snapshot=_sector_exit_hit_snapshot(),
    )
    trade = _make_trade()

    assert engine.check_sell_signal_v2(trade, date(2026, 6, 18)) is None
    assert trade.market_exit_state == "observe"
    assert trade.sector_exit_state == "observe"
    assert engine.check_sell_signal_v2(trade, date(2026, 6, 19)) is None
    third = engine.check_sell_signal_v2(trade, date(2026, 6, 20))

    assert third is not None
    assert third.reason == "market_top_confirmed"
    assert trade.sector_exit_state == ""


def test_market_exit_snapshot_allows_confirmation_without_large_drawdown() -> None:
    engine = LowFreqTradingEngineV16.__new__(LowFreqTradingEngineV16)
    engine._resolve_market_proxy = lambda code: "cyb"
    engine.MARKET_EXIT_MIN_DRAWDOWN_PCT = -4.0
    engine._market_top_snapshot = lambda trade, current_date, market_key=None: {
        "market_key": "cyb",
        "market_label": "创业板",
        "break_ma20": True,
        "ma20_weak": True,
        "breadth_ratio": 0.25,
    }
    engine._market_drawdown_snapshot = lambda trade, current_date, market_key=None: {
        "market_label": "创业板",
        "drawdown_pct": -2.5,
    }
    trade = _make_trade()

    snapshot = engine._market_exit_snapshot(trade, date(2026, 6, 18), market_key="cyb")

    assert snapshot is not None
    assert snapshot["price_trend_weak"] is True
    assert snapshot["breadth_weak"] is True
    assert snapshot["drawdown_weak"] is False
    assert snapshot["drawdown_is_observation_only"] is True
    assert snapshot["condition_pass"] is True


def test_market_exit_snapshot_keeps_large_drawdown_as_observation_evidence() -> None:
    engine = LowFreqTradingEngineV16.__new__(LowFreqTradingEngineV16)
    engine._resolve_market_proxy = lambda code: "cyb"
    engine.MARKET_EXIT_MIN_DRAWDOWN_PCT = -4.0
    engine._market_top_snapshot = lambda trade, current_date, market_key=None: {
        "market_key": "cyb",
        "market_label": "创业板",
        "break_ma20": True,
        "ma20_weak": True,
        "breadth_ratio": 0.22,
    }
    engine._market_drawdown_snapshot = lambda trade, current_date, market_key=None: {
        "market_label": "创业板",
        "drawdown_pct": -4.5,
    }
    trade = _make_trade()

    snapshot = engine._market_exit_snapshot(trade, date(2026, 6, 18), market_key="cyb")

    assert snapshot is not None
    assert snapshot["drawdown_weak"] is True
    assert snapshot["condition_pass"] is True
    assert snapshot["drawdown_is_observation_only"] is True


def test_market_exit_snapshot_drawdown_only_does_not_confirm_exit() -> None:
    engine = LowFreqTradingEngineV16.__new__(LowFreqTradingEngineV16)
    engine._resolve_market_proxy = lambda code: "cyb"
    engine.MARKET_EXIT_MIN_DRAWDOWN_PCT = -4.0
    engine._market_top_snapshot = lambda trade, current_date, market_key=None: {
        "market_key": "cyb",
        "market_label": "创业板",
        "break_ma20": False,
        "ma20_weak": False,
        "breadth_ratio": 0.58,
    }
    engine._market_drawdown_snapshot = lambda trade, current_date, market_key=None: {
        "market_label": "创业板",
        "drawdown_pct": -6.5,
    }
    trade = _make_trade()

    snapshot = engine._market_exit_snapshot(trade, date(2026, 6, 18), market_key="cyb")

    assert snapshot is not None
    assert snapshot["price_trend_weak"] is False
    assert snapshot["breadth_weak"] is False
    assert snapshot["drawdown_weak"] is True
    assert snapshot["condition_pass"] is False
    assert snapshot["drawdown_is_observation_only"] is True


def test_position_contract_snapshot_keeps_partial_weakness_in_hold_layer() -> None:
    engine = _make_engine(
        price=108.0,
        market_exit_snapshot={
            "scope": "market",
            "market_key": "cyb",
            "market_label": "创业板",
            "condition_pass": False,
            "evidence_count": 1,
            "price_trend_weak": False,
            "breadth_weak": True,
            "drawdown_weak": False,
            "details": "创业板见顶确认候选：趋势转弱=否 | 广度转弱=是 | 代理回撤-2.0%",
        },
        sector_exit_snapshot=None,
    )
    trade = _make_trade(role="龙头", peak_price=118.0)

    snapshot = engine._position_contract_snapshot(
        trade=trade,
        current_date=date(2026, 6, 18),
        sell=None,
    )

    assert snapshot["hold_state"] == "noise_watch"
    assert snapshot["hold_attribution_bucket"] == "hold_noise_watch"
    assert snapshot["exit_attribution_bucket"] == ""
    assert snapshot["exit_ready"] is False
    assert snapshot["decision"] == "hold"
    assert "存在弱化证据，但仍属于观察态" in snapshot["not_exit_reasons"][0]
    assert "market_breadth_weak" in snapshot["warning_flags"]
    assert snapshot["source_layer"] == "hold"


def test_position_contract_snapshot_marks_trend_exhausted_exit_bucket() -> None:
    engine = _make_engine(price=116.0, market_exit_snapshot=None, sector_exit_snapshot=None)
    trade = _make_trade(peak_price=130.0, hold_days=20, buy_progress_label="其它")
    sell = engine.check_sell_signal_v2(trade, date(2026, 6, 18))

    snapshot = engine._position_contract_snapshot(
        trade=trade,
        current_date=date(2026, 6, 18),
        sell=sell,
    )

    assert snapshot["hold_state"] == "exit_ready"
    assert snapshot["exit_reason_type"] == "trend_exhausted"
    assert snapshot["exit_attribution_bucket"] == "trend_exhaustion_exit"
    assert snapshot["exit_scope"] == "position_only"


def test_sector_exit_snapshot_requires_trend_and_follower_weakness_to_confirm() -> None:
    engine = LowFreqTradingEngineV16.__new__(LowFreqTradingEngineV16)
    engine.detect_sector_cooldown = lambda sector, current_date: {
        "cooldown_detected": True,
        "follower_weakness": 0.72,
        "leader_strength": 0.49,
        "leader_avg": 7.5,
        "trend_state": "diverging",
    }
    trade = _make_trade()

    snapshot = engine._sector_exit_snapshot(trade, date(2026, 6, 18))

    assert snapshot is not None
    assert snapshot["trend_deteriorating"] is True
    assert snapshot["follower_weak"] is True
    assert snapshot["condition_pass"] is True
    assert snapshot["cooldown_is_observation_only"] is True
    assert snapshot["leader_rollover_is_observation_only"] is True


def test_sector_exit_snapshot_cooldown_and_leader_rollover_only_stay_observation() -> None:
    engine = LowFreqTradingEngineV16.__new__(LowFreqTradingEngineV16)
    engine.detect_sector_cooldown = lambda sector, current_date: {
        "cooldown_detected": True,
        "follower_weakness": 0.42,
        "leader_strength": 0.41,
        "leader_avg": 6.8,
        "trend_state": "sideways",
    }
    trade = _make_trade()

    snapshot = engine._sector_exit_snapshot(trade, date(2026, 6, 18))

    assert snapshot is not None
    assert snapshot["trend_deteriorating"] is False
    assert snapshot["follower_weak"] is False
    assert snapshot["leader_rollover"] is True
    assert snapshot["condition_pass"] is False
    assert snapshot["cooldown_is_observation_only"] is True
    assert snapshot["leader_rollover_is_observation_only"] is True


def test_sell_signal_audit_records_observe_review_confirm() -> None:
    engine = _make_engine(price=100.0, market_exit_snapshot=_market_exit_hit_snapshot(), sector_exit_snapshot=None)
    trade = _make_trade()

    assert engine.check_sell_signal_v2(trade, date(2026, 6, 18)) is None
    assert engine.check_sell_signal_v2(trade, date(2026, 6, 19)) is None
    assert engine.check_sell_signal_v2(trade, date(2026, 6, 20)) is not None

    events = [entry["event"] for entry in engine._sell_signal_audit_current_run]
    assert events == [
        "market_exit_watch_started",
        "market_exit_review_started",
        "market_exit_confirmed",
    ]
