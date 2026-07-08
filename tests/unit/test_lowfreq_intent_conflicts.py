from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import sqlite3
from types import SimpleNamespace

import apps.api.main as api_main
from apps.api.main import BootstrapApiRouter, BootstrapApiService
from apps.api.shared import ApiBinaryResponse


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class _SellOnlyEngine:
    def __init__(self, *, sell_codes: set[str] | None = None):
        self.sell_codes = sell_codes or set()

    def check_sell_signal_v2(self, trade, requested_date):
        if str(getattr(trade, "code", "") or "") not in self.sell_codes:
            return None
        return SimpleNamespace(reason="full_exit", details="conflict-test")

    def generate_buy_signals(self, requested_date):
        return {"buy_signals": []}


class _BuyOnlyEngine:
    def __init__(self, *, signals: list[dict[str, object]]):
        self.signals = signals
        self.BUY_SIGNAL_MEMORY_DAYS = 5

    def check_sell_signal_v2(self, trade, requested_date):
        return None

    def generate_buy_signals(self, requested_date):
        return {"buy_signals": self.signals}


class _DatedBuyEngine:
    BUY_SIGNAL_MEMORY_DAYS = 5

    def __init__(self, *, signals_by_date: dict[str, list[dict[str, object]]]):
        self.signals_by_date = signals_by_date

    def check_sell_signal_v2(self, trade, requested_date):
        return None

    def generate_buy_signals(self, requested_date):
        key = requested_date.isoformat() if hasattr(requested_date, "isoformat") else str(requested_date)
        return {"buy_signals": list(self.signals_by_date.get(key, []))}


class _EntryAwareBuyEngine:
    BUY_SIGNAL_MEMORY_DAYS = 5

    def __init__(self, *, payload: dict[str, object]):
        self.payload = payload

    def check_sell_signal_v2(self, trade, requested_date):
        return None

    def generate_buy_signals(self, requested_date):
        return dict(self.payload)


def _make_service() -> BootstrapApiService:
    return BootstrapApiService(project_root=PROJECT_ROOT)


def test_lowfreq_backtest_with_trades_uses_engine_owned_backtest() -> None:
    service = _make_service()
    calls: list[tuple[str, str, float, bool]] = []

    class _BacktestEngine:
        def run_backtest(
            self,
            start_date,
            end_date,
            initial_capital=1_000_000.0,
            *,
            include_trades=False,
            include_daily_values=False,
        ):
            calls.append(
                (
                    start_date.isoformat(),
                    end_date.isoformat(),
                    float(initial_capital),
                    bool(include_trades),
                )
            )
            return {
                "total_return_pct": 12.34,
                "trades": [
                    {
                        "code": "300001",
                        "name": "特锐德",
                        "sector": "电力设备",
                        "buy_date": "2026-06-01",
                        "sell_date": "2026-06-10",
                        "buy_price": 10.0,
                        "sell_price": 12.0,
                        "buy_price_ref": 10.0,
                        "sell_price_ref": 12.0,
                        "shares": 1000,
                        "hold_days": 7,
                        "return_pct": 20.0,
                        "net_return_pct": 19.7,
                        "buy_fee": 5.0,
                        "sell_fee": 6.0,
                        "buy_score": 91.0,
                        "wave_phase": "3浪",
                        "buy_progress_label": "早窗",
                        "peak_price": 12.4,
                        "partial_taken": False,
                        "sell_reason": "回测结束平仓",
                        "status": "closed",
                        "role": "龙头",
                    }
                ],
            }

    metrics, trades = service._lowfreq_backtest_with_trades(
        engine=_BacktestEngine(),
        start_date=date(2026, 6, 1),
        end_date=date(2026, 6, 30),
        initial_capital=2_000_000.0,
    )

    assert calls == [("2026-06-01", "2026-06-30", 2_000_000.0, True)]
    assert metrics["total_return_pct"] == 12.34
    assert isinstance(trades, list)
    assert len(trades) == 1
    assert trades[0].code == "300001"
    assert trades[0].buy_progress_label == "早窗"
    assert trades[0].sell_reason == "回测结束平仓"


def test_generate_intents_skips_new_sell_when_older_pending_sell_exists(monkeypatch) -> None:
    service = _make_service()
    monkeypatch.setattr(service, "_lowfreq_next_trading_day", lambda after_date: "2026-06-16")
    state = {
        "positions": {
            "002407": {
                "code": "002407",
                "name": "多氟多",
                "sector": "化工",
                "role": "龙头",
            }
        },
        "manual": {
            "intents": [
                {
                    "intent_id": "older-sell",
                    "intent_type": "sell_intent",
                    "status": "pending",
                    "code": "002407",
                    "requested_date": "2026-06-13",
                    "execute_date": "2026-06-16",
                }
            ]
        },
    }

    out = service._lowfreq_generate_execution_intents_for_date(
        state=state,
        engine=_SellOnlyEngine(sell_codes={"002407"}),
        requested_date=date(2026, 6, 15),
    )

    intents = state["manual"]["intents"]
    assert len(intents) == 1
    assert out["created_sell"] == 0
    assert out["skipped_conflicts"] == [
        {
            "code": "002407",
            "intent_type": "sell_intent",
            "requested_date": "2026-06-15",
            "candidate_execute_date": "2026-06-16",
            "blocked_by_intent_id": "older-sell",
            "blocked_by_execute_date": "2026-06-16",
            "reason": "pending_conflict_older_intent_wins",
        }
    ]


def test_generate_intents_prefers_entry_signals_over_legacy_buy_signals(monkeypatch) -> None:
    service = _make_service()
    monkeypatch.setattr(service, "_lowfreq_next_trading_day", lambda after_date: "2026-06-16")
    state = {"positions": {}, "manual": {"intents": []}, "signal_memory": {"buy_signals": []}}

    out = service._lowfreq_generate_execution_intents_for_date(
        state=state,
        engine=_EntryAwareBuyEngine(
            payload={
                "buy_signals": [
                    {
                        "code": "600301",
                        "name": "华锡有色",
                        "sector": "有色",
                        "role": "龙头",
                        "buy_score": 88.0,
                        "wave_phase": "启动",
                    }
                ],
                "entry_signals": [
                    {
                        "code": "300308",
                        "name": "中际旭创",
                        "sector": "光模块",
                        "role": "龙头",
                        "buy_score": 93.0,
                        "wave_phase": "3浪",
                    }
                ],
            }
        ),
        requested_date=date(2026, 6, 15),
    )

    intents = state["manual"]["intents"]
    assert out["created_buy"] == 1
    assert len(intents) == 1
    assert intents[0]["code"] == "300308"
    assert state["signal_memory"]["buy_signals"] == []


def test_generate_intents_skips_new_buy_when_older_pending_buy_exists(monkeypatch) -> None:
    service = _make_service()
    monkeypatch.setattr(service, "_lowfreq_next_trading_day", lambda after_date: "2026-06-16")
    state = {
        "positions": {},
        "manual": {
            "intents": [
                {
                    "intent_id": "older-buy",
                    "intent_type": "buy_intent",
                    "status": "pending",
                    "code": "600301",
                    "requested_date": "2026-06-13",
                    "execute_date": "2026-06-16",
                }
            ]
        },
    }

    out = service._lowfreq_generate_execution_intents_for_date(
        state=state,
        engine=_BuyOnlyEngine(
            signals=[
                {
                    "code": "600301",
                    "name": "华锡有色",
                    "sector": "有色",
                    "role": "龙头",
                    "buy_score": 88.0,
                    "wave_phase": "启动",
                }
            ]
        ),
        requested_date=date(2026, 6, 15),
    )

    intents = state["manual"]["intents"]
    assert len(intents) == 1
    assert out["created_buy"] == 0
    assert out["skipped_conflicts"] == [
        {
            "code": "600301",
            "intent_type": "buy_intent",
            "requested_date": "2026-06-15",
            "candidate_execute_date": "2026-06-16",
            "blocked_by_intent_id": "older-buy",
            "blocked_by_execute_date": "2026-06-16",
            "reason": "pending_conflict_older_intent_wins",
        }
    ]


def test_generate_intents_allows_new_intent_when_old_one_is_not_pending(monkeypatch) -> None:
    service = _make_service()
    monkeypatch.setattr(service, "_lowfreq_next_trading_day", lambda after_date: "2026-06-16")
    state = {
        "positions": {},
        "manual": {
            "intents": [
                {
                    "intent_id": "executed-buy",
                    "intent_type": "buy_intent",
                    "status": "executed",
                    "code": "600301",
                    "requested_date": "2026-06-13",
                    "execute_date": "2026-06-16",
                }
            ]
        },
    }

    out = service._lowfreq_generate_execution_intents_for_date(
        state=state,
        engine=_BuyOnlyEngine(
            signals=[
                {
                    "code": "600301",
                    "name": "华锡有色",
                    "sector": "有色",
                    "role": "龙头",
                    "buy_score": 88.0,
                    "wave_phase": "启动",
                }
            ]
        ),
        requested_date=date(2026, 6, 15),
    )

    intents = state["manual"]["intents"]
    assert len(intents) == 2
    assert intents[-1]["intent_type"] == "buy_intent"
    assert intents[-1]["status"] == "pending"
    assert out["created_buy"] == 1
    assert out["skipped_conflicts"] == []


def test_buy_signal_memory_reuses_recent_signal_after_pending_conflict_clears(monkeypatch) -> None:
    service = _make_service()
    next_day = {
        "2026-06-15": "2026-06-16",
        "2026-06-16": "2026-06-17",
        "2026-06-17": "2026-06-18",
        "2026-06-18": "2026-06-19",
        "2026-06-19": "2026-06-20",
        "2026-06-20": "2026-06-23",
    }
    monkeypatch.setattr(service, "_lowfreq_next_trading_day", lambda after_date: next_day[str(after_date)])
    state = {
        "positions": {},
        "manual": {
            "intents": [
                {
                    "intent_id": "older-buy",
                    "intent_type": "buy_intent",
                    "status": "pending",
                    "code": "600301",
                    "requested_date": "2026-06-13",
                    "execute_date": "2026-06-16",
                }
            ]
        },
        "signal_memory": {"buy_signals": []},
    }
    engine = _DatedBuyEngine(
        signals_by_date={
            "2026-06-15": [
                {
                    "code": "600301",
                    "name": "华锡有色",
                    "sector": "有色",
                    "role": "龙头",
                    "buy_score": 88.0,
                    "wave_phase": "启动",
                }
            ]
        }
    )

    first = service._lowfreq_generate_execution_intents_for_date(
        state=state,
        engine=engine,
        requested_date=date(2026, 6, 15),
    )

    assert first["created_buy"] == 0
    assert state["signal_memory"]["buy_signals"][0]["code"] == "600301"
    assert state["signal_memory"]["buy_signals"][0]["source_date"] == "2026-06-15"

    state["manual"]["intents"][0]["status"] = "executed"

    second = service._lowfreq_generate_execution_intents_for_date(
        state=state,
        engine=engine,
        requested_date=date(2026, 6, 16),
    )

    assert second["created_buy"] == 1
    assert state["manual"]["intents"][-1]["code"] == "600301"
    assert state["manual"]["intents"][-1]["source"] == "model_signal_memory"
    assert state["manual"]["intents"][-1]["source_date"] == "2026-06-15"
    assert state["signal_memory"]["buy_signals"] == []


def test_lowfreq_trade_from_payload_preserves_reference_prices_and_fees() -> None:
    service = _make_service()

    trade = service._lowfreq_trade_from_payload(
        {
            "code": "301396",
            "name": "宏景科技",
            "sector": "I65",
            "buy_date": "2026-03-31",
            "sell_date": "2026-04-03",
            "buy_price": 153.29,
            "sell_price": 166.5,
            "buy_price_ref": 153.29,
            "sell_price_ref": 166.5,
            "shares": 1900,
            "return_pct": 8.62,
            "net_return_pct": 8.21,
            "buy_fee": 123.0,
            "sell_fee": 111.0,
            "buy_score": 103.0,
            "wave_phase": "3浪",
            "buy_progress_label": "早窗",
            "peak_price": 172.19,
            "sell_reason": "test",
            "status": "closed",
            "role": "龙头",
            "market_top_watch_start_date": "2026-04-01",
            "market_top_watch_expire_date": "2026-04-03",
            "market_top_watch_hits": 1,
            "market_top_watch_last_reason": "创业板见顶：跌破20日线=是 | 20日线走弱=是 | 站上20日线占比28%",
            "market_top_watch_last_hit_date": "2026-04-01",
            "market_exit_state": "review",
            "market_exit_start_date": "2026-04-01",
            "market_exit_expire_date": "2026-04-07",
            "market_exit_hits": 2,
            "market_exit_last_reason": "创业板见顶确认候选：趋势转弱=是 | 广度转弱=是 | 代理回撤-10.5%",
            "market_exit_last_hit_date": "2026-04-02",
            "sector_exit_state": "observe",
            "sector_exit_start_date": "2026-04-02",
            "sector_exit_expire_date": "2026-04-08",
            "sector_exit_hits": 1,
            "sector_exit_last_reason": "板块见顶确认候选：I65 | 趋势=diverging | 跟随股弱势70% | 龙头强度48%",
            "sector_exit_last_hit_date": "2026-04-02",
            "system_exit_grace_used": True,
            "system_exit_grace_date": "2026-04-03",
            "system_exit_grace_scope": "market",
            "system_exit_grace_reason": "创业板见顶确认候选：趋势转弱=是 | 广度转弱=是 | 代理回撤-10.5%",
        }
    )

    assert trade.buy_price_ref == 153.29
    assert trade.sell_price_ref == 166.5
    assert trade.net_return_pct == 8.21
    assert trade.buy_fee == 123.0
    assert trade.sell_fee == 111.0
    assert trade.buy_progress_label == "早窗"
    assert trade.market_top_watch_start_date == "2026-04-01"
    assert trade.market_top_watch_expire_date == "2026-04-03"
    assert trade.market_top_watch_hits == 1
    assert trade.market_top_watch_last_hit_date == "2026-04-01"
    assert trade.market_exit_state == "review"
    assert trade.market_exit_start_date == "2026-04-01"
    assert trade.market_exit_expire_date == "2026-04-07"
    assert trade.market_exit_hits == 2


def test_lowfreq_portfolio_view_includes_phase1_contract_fields() -> None:
    service = _make_service()

    class _FakeCursor:
        def execute(self, *_args, **_kwargs):
            return None

        def fetchall(self):
            return []

    class _FakeConn:
        def cursor(self):
            return _FakeCursor()

        def close(self):
            return None

    class _PortfolioEngine:
        def _conn(self):
            return _FakeConn()

        def _get_price(self, code, target_date):
            return 11.5

        def check_sell_signal_v2(self, trade, target_date):
            return None

        def _peak_return_pct(self, trade):
            return 18.0

        def _count_trading_days(self, start, end):
            return 4

        def _position_contract_snapshot(self, *, trade, current_date, sell):
            return {
                "hold_state": "holding",
                "noise_evidence": ["趋势未破坏"],
                "not_exit_reasons": ["未触发正式退出条件"],
                "warning_flags": [],
                "exit_ready": False,
                "exit_scope": "",
                "exit_reason_type": "",
                "exit_evidence_bundle": [],
                "current_stage": "hold_confirmed",
                "decision": "hold",
                "reasons": ["未触发正式退出条件"],
                "evidence": ["趋势未破坏"],
                "flags": [],
                "source_layer": "hold",
                "next_action": "hold",
                "last_transition": "2026-06-18",
            }

        def _layer_contract_payload(
            self,
            *,
            current_stage,
            decision,
            score=None,
            reasons=None,
            evidence=None,
            flags=None,
            source_layer,
            next_action,
            last_transition="",
        ):
            payload = {
                "current_stage": current_stage,
                "decision": decision,
                "reasons": list(reasons or []),
                "evidence": list(evidence or []),
                "flags": list(flags or []),
                "source_layer": source_layer,
                "next_action": next_action,
                "last_transition": last_transition,
            }
            if score is not None:
                payload["score"] = float(score)
            return payload

    state = {
        "strategy": "low_freq_v16_advanced",
        "initial_capital": 1_000_000.0,
        "cash": 800_000.0,
        "last_date": "2026-06-18",
        "positions": {
            "300001": {
                "code": "300001",
                "name": "特锐德",
                "sector": "电力设备",
                "buy_date": "2026-06-15",
                "buy_price": 10.0,
                "shares": 1000,
                "buy_score": 92.0,
                "wave_phase": "3浪",
                "role": "龙头",
                "status": "open",
            }
        },
        "closed_trades": [
            {
                "code": "300002",
                "name": "神州泰岳",
                "sector": "AI",
                "buy_date": "2026-06-01",
                "buy_price": 8.0,
                "sell_date": "2026-06-10",
                "sell_price": 10.0,
                "shares": 1000,
                "return_pct": 25.0,
                "sell_reason": "板块见顶确认：AI退潮",
                "status": "closed",
            }
        ],
        "manual": {
            "intents": [
                {
                    "intent_id": "buy-1",
                    "intent_type": "buy_intent",
                    "status": "pending",
                    "code": "300003",
                    "name": "中际旭创",
                    "sector": "光模块",
                    "requested_date": "2026-06-18",
                    "execute_date": "2026-06-19",
                    "last_attempt_reason": "no_slots",
                }
            ]
        },
    }

    portfolio = service._lowfreq_portfolio_view(
        engine=_PortfolioEngine(),
        state=state,
        target_date=date(2026, 6, 18),
    )

    open_pos = portfolio["open_positions"][0]
    assert open_pos["hold_state"] == "holding"
    assert open_pos["current_stage"] == "hold_confirmed"
    assert open_pos["decision"] == "hold"
    assert open_pos["source_layer"] == "hold"
    assert open_pos["not_exit_reasons"] == ["未触发正式退出条件"]

    closed_trade = portfolio["closed_trades"][0]
    assert closed_trade["hold_state"] == "closed"
    assert closed_trade["current_stage"] == "exited"
    assert closed_trade["decision"] == "exit"
    assert closed_trade["source_layer"] == "exit"
    manual_intent = portfolio["manual_intents"][0]
    assert manual_intent["source_layer"] == "execution"
    assert manual_intent["action_type"] == "buy"
    assert manual_intent["order_action"] == "buy"
    assert manual_intent["execution_status"] == "pending"
    assert manual_intent["execution_block_reason"] == ""


def test_lowfreq_backtest_run_view_projects_signal_and_execution_summaries(monkeypatch, tmp_path: Path) -> None:
    service = _make_service()
    service._lowfreq_backtest_artifacts_dir = tmp_path
    monkeypatch.setattr(service, "_lowfreq_trade_date_range", lambda: ("2026-06-01", "2026-06-15"))
    monkeypatch.setattr(
        service,
        "_lowfreq_backtest_with_trades",
        lambda **kwargs: (
            {
                "start_date": "2026-06-01",
                "end_date": "2026-06-15",
                "execution_action_summary": {"buy": 2, "reserve": 1},
                "config_snapshot": {"execution_mode": "unbounded_opportunity"},
            },
            [],
        ),
    )
    monkeypatch.setattr(service, "_render_lowfreq_backtest_pdf", lambda **kwargs: None)

    class _DateCursor:
        def execute(self, *_args, **_kwargs):
            return None

        def fetchone(self):
            return ("2026-06-16",)

    class _DateConn:
        def cursor(self):
            return _DateCursor()

        def close(self):
            return None

    class _ReportEngine:
        def generate_buy_signals(self, _requested_date):
            return {
                "candidate_signals": [
                    {"code": "600460", "name": "士兰微", "sector": "半导体", "role": "龙头", "buy_score": 92.0}
                ],
                "entry_signals": [
                    {
                        "code": "300308",
                        "name": "中际旭创",
                        "sector": "光模块",
                        "role": "龙头",
                        "buy_score": 97.0,
                        "wave_phase": "3浪",
                        "resonance": 0.9,
                        "reasons": ["正式建仓"],
                    }
                ],
                "signal_summary": {"candidate_count": 1, "entry_count": 1, "soft_retained_count": 0},
            }

    monkeypatch.setattr(service, "_lowfreq_engine_v16", lambda: _ReportEngine())
    monkeypatch.setattr(api_main.sqlite3, "connect", lambda *_args, **_kwargs: _DateConn())

    payload = service.lowfreq_backtest_run_view(async_run=False, report_id="phase5_projection_case")

    assert payload["execution_mode"] == "unbounded_opportunity"
    assert payload["execution_action_summary"] == {"buy": 2, "reserve": 1}
    assert payload["next_session"]["signal_summary"] == {
        "candidate_count": 1,
        "entry_count": 1,
        "soft_retained_count": 0,
    }
    assert payload["next_session"]["candidates"][0]["code"] == "300308"


def test_lowfreq_workbench_view_aggregates_authoritative_sections(monkeypatch, tmp_path: Path) -> None:
    service = _make_service()
    service._daily_runs_dir = tmp_path / "daily_runs"
    service._daily_runs_dir.mkdir(parents=True, exist_ok=True)
    (service._daily_runs_dir / "2026-06-09.json").write_text(
        (
            '{'
            '"target_date":"2026-06-09",'
            '"trade_date":"2026-06-09",'
            '"started_at":"2026-06-09T07:45:00Z",'
            '"finished_at":"2026-06-09T08:10:00Z",'
            '"steps":['
            '{"step_id":"yesterday_closeout","status":"ok","outputs":{"summary":{"overdue_shifted_count":2,"inconsistency_count":0}}},'
            '{"step_id":"authoritative_update","status":"ok","outputs":{"trade_date":"2026-06-09","provider":"tushare"}},'
            '{"step_id":"screeners_bulk_run","status":"ok","outputs":{"status":"ok"}},'
            '{"step_id":"lowfreq_sim_daily","status":"ok","outputs":{"pending_intents_after":3}},'
            '{"step_id":"confidence_daily","status":"ok","outputs":{}},'
            '{"step_id":"auto_optimize","status":"ok","outputs":{}}'
            ']'
            '}\n'
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(service, "_lowfreq_latest_trade_date", lambda: "2026-06-09")
    monkeypatch.setattr(
        service,
        "_lowfreq_engine_v16",
        lambda: SimpleNamespace(_resolve_execution_mode=lambda: "unbounded_opportunity"),
    )
    monkeypatch.setattr(service, "_load_lowfreq_sim_state", lambda: {"settings": {"autopilot_enabled": True}})
    monkeypatch.setattr(
        service,
        "market_phase_view",
        lambda target_date=None: {
            "market_phase": {
                "phase": "bull",
                "confidence": 0.72,
                "market_breadth": 0.61,
                "amount_trend": "rising",
            }
        },
    )
    monkeypatch.setattr(
        service,
        "market_intelligence_decision_summary_view",
        lambda trade_date=None, top_n=10: {"signals": {"focus_theme": "机器人"}},
    )
    monkeypatch.setattr(
        service,
        "lowfreq_execution_queue_view",
        lambda **kwargs: {
            "queue": [
                {
                    "code": "600001",
                    "source_date": "2026-06-09",
                    "created_at": "2026-06-09T09:35:00Z",
                    "requested_date": "2026-06-09",
                }
            ]
        },
    )
    monkeypatch.setattr(
        service,
        "lowfreq_hot_sectors_view",
        lambda **kwargs: {
            "sectors": [
                {
                    "code": "BK001",
                    "name": "机器人",
                    "heat_score": 88.5,
                    "meta": {"mainline_rank": 1, "trend_state": "rising", "risk_level": "ok"},
                    "upwave": {"status": "upwave"},
                    "leaders": [
                        {
                            "code": "600001",
                            "name": "领涨一号",
                            "sector": "机器人",
                            "role": "龙头",
                            "buy_signal": False,
                            "certainty_prob": 0.82,
                            "reasons": ["突破确认"],
                            "formal_front": {
                                "status": "ok",
                                "small_cycle": {
                                    "cycle_state": "S2 Advancing",
                                    "state_stability_level": "stable",
                                },
                                "identify_state": {
                                    "status": "identified",
                                    "reason": "small_cycle_enters_formal_watch_scope",
                                },
                                "tracking_state": {
                                    "status": "tracking",
                                    "maturity": "ready_for_entry",
                                    "transition_reason": "small_cycle_supports_formal_action",
                                },
                                "entry_state": {
                                    "status": "ready",
                                    "decision": "enter",
                                    "actionable": True,
                                    "blocking_reasons": [],
                                },
                                "m1_constraints": {
                                    "blocked": False,
                                    "blocking_reasons": [],
                                    "profile_window_ready": True,
                                },
                            },
                            "manual": {"buy_intent_pending": False},
                        }
                    ],
                    "middle": [],
                    "followers": [],
                }
            ],
            "portfolio": {
                "open_positions": [
                    {
                        "code": "600001",
                        "name": "领涨一号",
                        "sector": "机器人",
                        "role": "龙头",
                        "buy_price": 10.0,
                        "current_price": 10.8,
                        "unrealized_pnl_pct": 8.0,
                        "buy_date": "2026-06-03",
                        "hold_days": 4,
                        "hold_state": "holding",
                        "exit_ready": False,
                        "not_exit_reasons": ["未触发正式退出条件"],
                        "warning_flags": [],
                        "shares": 1000,
                        "buy_progress_label": "早窗",
                    }
                ],
                "closed_trades": [],
                "manual_intents": [
                    {
                        "intent_id": "buy-1",
                        "intent_type": "buy_intent",
                        "status": "executed",
                        "code": "600001",
                        "name": "领涨一号",
                        "sector": "机器人",
                        "executed_date": "2026-06-09",
                        "executed_price": 10.0,
                        "executed_shares": 1000,
                        "source": "manual",
                        "requested_date": "2026-06-08",
                        "buy_score": 92.0,
                    }
                ],
            },
        },
    )

    payload = service.lowfreq_workbench_view(target_date="2026-06-09")

    assert payload["_meta"]["status"] == "ok"
    assert payload["meta"]["execution_mode"] == "unbounded_opportunity"
    assert payload["meta"]["autopilot_enabled"] is True
    assert payload["meta"]["daily_ops_status"] == "ok"
    assert payload["meta"]["latest_data_synced"] is True
    assert payload["market_summary"]["phase_label"] == "进攻阶段"
    assert payload["market_summary"]["summary_text"] == "当前处于进攻阶段，操作倾向进攻，风险低，关注机器人，自动执行开启"
    assert payload["market_summary"]["evidence"][-1] == "focus_theme=机器人"
    assert payload["daily_ops"]["run_date"] == "2026-06-09"
    assert payload["daily_ops"]["provider"] == "tushare"
    assert payload["daily_ops"]["overdue_shifted_count"] == 2
    assert payload["daily_ops"]["pending_intents_after"] == 3
    assert payload["hot_sectors"][0]["status_text"] == "主升"
    assert payload["positions"][0]["position_status_text"] == "稳定"
    assert payload["trade_ledger"][0]["source_text"] == "人工"

def test_ops_center_summary_view_aggregates_authoritative_sections(monkeypatch, tmp_path: Path) -> None:
    service = _make_service()
    service.project_root = tmp_path
    service._daily_runs_dir = tmp_path / "var/ledgers/daily_runs"
    service._daily_runs_dir.mkdir(parents=True, exist_ok=True)
    service._daily_runs_dir.joinpath("2026-06-09.json").write_text(
        json.dumps(
            {
                "target_date": "2026-06-09",
                "trade_date": "2026-06-09",
                "finished_at": "2026-06-09T08:10:00Z",
                "steps": [
                    {
                        "step_id": "yesterday_closeout",
                        "status": "ok",
                        "outputs": {"summary": {"overdue_shifted_count": 2, "inconsistency_count": 0}},
                    },
                    {
                        "step_id": "authoritative_update",
                        "status": "ok",
                        "outputs": {"trade_date": "2026-06-09", "provider": "tushare"},
                    },
                    {"step_id": "screeners_bulk_run", "status": "ok", "outputs": {"status": "ok"}},
                    {"step_id": "lowfreq_sim_daily", "status": "ok", "outputs": {"pending_intents_after": 3}},
                    {
                        "step_id": "confidence_daily",
                        "status": "ok",
                        "outputs": {"labels_updated": 12, "buckets_written": 8},
                    },
                    {"step_id": "auto_optimize", "status": "ok", "outputs": {}},
                ],
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    bulk_dir = tmp_path / "var/ledgers/screener_runs/2026-06-09"
    bulk_dir.mkdir(parents=True, exist_ok=True)
    bulk_dir.joinpath("bulk_run_ledger.json").write_text(
        json.dumps(
            {
                "target_date": "2026-06-09",
                "status": "ok",
                "run_count": 6,
                "finished_at": "2026-06-09T08:05:00Z",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(service, "_lowfreq_latest_trade_date", lambda: "2026-06-09")

    payload = service.ops_center_summary_view(target_date="2026-06-09")

    assert payload["_meta"]["status"] == "ok"
    assert payload["meta"]["as_of_date"] == "2026-06-09"
    assert payload["inspection"]["overall_status"] == "ok"
    assert payload["inspection"]["risk_level"] == "low"
    assert payload["checklist"][0]["item_id"] == "data_freshness"
    assert payload["checklist"][0]["status"] == "ok"
    assert payload["pipeline_steps"][0]["step_id"] == "authoritative_update"
    assert payload["pipeline_steps"][1]["finished_at"] == "2026-06-09T08:05:00Z"
    assert payload["exceptions"] == []
    assert payload["evidence"]["latest_run_date"] == "2026-06-09"
    assert payload["evidence"]["pending_intents_after"] == 3


def test_ops_center_summary_view_surfaces_severe_and_high_exceptions(
    monkeypatch, tmp_path: Path
) -> None:
    service = _make_service()
    service.project_root = tmp_path
    service._daily_runs_dir = tmp_path / "var/ledgers/daily_runs"
    service._daily_runs_dir.mkdir(parents=True, exist_ok=True)
    service._daily_runs_dir.joinpath("2026-06-09.json").write_text(
        json.dumps(
            {
                "target_date": "2026-06-09",
                "trade_date": "2026-06-08",
                "finished_at": "2026-06-09T08:10:00Z",
                "steps": [
                    {
                        "step_id": "yesterday_closeout",
                        "status": "ok",
                        "outputs": {"summary": {"overdue_shifted_count": 1, "inconsistency_count": 2}},
                    },
                    {
                        "step_id": "authoritative_update",
                        "status": "failed",
                        "outputs": {"trade_date": "2026-06-08", "provider": "tushare"},
                    },
                    {"step_id": "screeners_bulk_run", "status": "failed", "outputs": {"status": "failed"}},
                    {"step_id": "lowfreq_sim_daily", "status": "failed", "outputs": {"pending_intents_after": 5}},
                ],
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    bulk_dir = tmp_path / "var/ledgers/screener_runs/2026-06-09"
    bulk_dir.mkdir(parents=True, exist_ok=True)
    bulk_dir.joinpath("bulk_run_ledger.json").write_text(
        json.dumps(
            {
                "target_date": "2026-06-09",
                "status": "failed",
                "run_count": 6,
                "finished_at": "2026-06-09T08:05:00Z",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(service, "_lowfreq_latest_trade_date", lambda: "2026-06-10")

    payload = service.ops_center_summary_view(target_date="2026-06-09")
    exception_ids = {item["exception_id"] for item in payload["exceptions"]}

    assert payload["inspection"]["overall_status"] == "critical"
    assert payload["inspection"]["risk_level"] == "severe"
    assert "latest_data_not_synced" in exception_ids
    assert "authoritative_update_failed" in exception_ids
    assert "lowfreq_daily_run_failed" in exception_ids
    assert "screeners_bulk_run_failed" in exception_ids
    assert "trade_closeout_inconsistency" in exception_ids
    assert "pipeline_steps_missing" in exception_ids


def test_lowfreq_score_views_return_compact_sync_meta(monkeypatch) -> None:
    service = _make_service()
    sync_meta = {
        "target_date": "2026-06-09",
        "persisted": False,
        "synced_tracking": 3,
        "synced_holding": 2,
        "synced_closed": 1,
        "synced_events": 4,
        "synced_snapshots": 5,
        "synced_summaries": 6,
        "pool": [{"code": "600001"}, {"code": "600002"}],
        "events": [{"code": "600001"}, {"code": "600002"}, {"code": "600003"}],
        "snapshots": [{"code": "600001"}],
        "summaries": [{"period_type": "week"}, {"period_type": "month"}],
    }

    monkeypatch.setattr(service, "_lowfreq_score_sync_state", lambda target_date=None: sync_meta)

    pool_payload = service.lowfreq_score_pool_view(target_date="2026-06-09")
    events_payload = service.lowfreq_score_events_view(target_date="2026-06-09", limit=2)
    summary_payload = service.lowfreq_score_summary_view(target_date="2026-06-09", limit=1)

    assert pool_payload["meta"]["sync"]["pool_count"] == 2
    assert pool_payload["meta"]["sync"]["events_count"] == 3
    assert "pool" not in pool_payload["meta"]["sync"]
    assert "events" not in pool_payload["meta"]["sync"]
    assert len(events_payload["events"]) == 2
    assert "summaries" not in events_payload["meta"]["sync"]
    assert len(summary_payload["summaries"]) == 1
    assert summary_payload["meta"]["sync"]["summaries_count"] == 2


def test_router_dispatches_lowfreq_workbench_endpoint() -> None:
    class _StubService:
        def lowfreq_workbench_view(self, *, target_date=None, requested_by="api", ensure_generated=True):
            return {
                "_meta": {"status": "ok"},
                "meta": {
                    "as_of_date": target_date,
                    "requested_by": requested_by,
                    "ensure_generated": ensure_generated,
                },
            }

    router = BootstrapApiRouter(service=_StubService())
    status, payload = router.dispatch("/api/lowfreq/workbench?date=2026-06-09&ensure_generated=false")

    assert int(status) == 200
    assert payload["meta"]["as_of_date"] == "2026-06-09"
    assert payload["meta"]["requested_by"] == "api"
    assert payload["meta"]["ensure_generated"] is False


def test_router_dispatches_ops_center_summary_endpoint() -> None:
    class _StubService:
        def ops_center_summary_view(self, *, target_date=None):
            return {"_meta": {"status": "ok"}, "meta": {"as_of_date": target_date}}

    router = BootstrapApiRouter(service=_StubService())
    status, payload = router.dispatch("/api/ops-center/summary?date=2026-06-09")

    assert int(status) == 200
    assert payload["meta"]["as_of_date"] == "2026-06-09"


def test_lowfreq_portfolio_view_marks_deprecated_contract(monkeypatch) -> None:
    service = _make_service()
    monkeypatch.setattr(service, "_lowfreq_latest_trade_date", lambda: "2026-06-18")
    monkeypatch.setattr(service, "_lowfreq_engine_v16", lambda: SimpleNamespace())
    monkeypatch.setattr(service, "_load_lowfreq_sim_state", lambda: {})
    monkeypatch.setattr(service, "_lowfreq_portfolio_view", lambda **_kwargs: {"open_positions": []})
    monkeypatch.setattr(service, "_save_lowfreq_sim_state", lambda _state: None)

    payload = service.lowfreq_portfolio_view()

    assert payload["_meta"]["deprecated"]["is_deprecated"] is True
    assert payload["_meta"]["deprecated"]["replacement_endpoint"] == "/api/lowfreq-score/pool"


def test_lowfreq_score_views_ensure_schema_and_read_authoritative_facts(tmp_path: Path) -> None:
    service = _make_service()
    db_path = tmp_path / "lowfreq_score.db"
    service._stock_db_default_path = db_path
    store = service._lowfreq_score_store()
    service._lowfreq_latest_trade_date = lambda: "2026-06-10"
    service._load_lowfreq_sim_state = lambda: {"positions": {}, "closed_trades": []}
    service._lowfreq_engine_v16 = lambda: SimpleNamespace(
        generate_buy_signals=lambda _d: {"candidate_signals": []}
    )

    pool_payload = service.lowfreq_score_pool_view(state="跟踪", limit=20)
    assert pool_payload["_meta"]["authoritative_layer"] == "operation_logic"
    assert pool_payload["_meta"]["contract"] == "lowfreq-score/pool.v1alpha1"
    assert pool_payload["meta"]["as_of_date"] == "2026-06-10"
    assert pool_payload["meta"]["states"] == ["跟踪", "持有中", "已清仓"]
    assert pool_payload["summary"]["pool_size"] == 0
    assert pool_payload["ui_contract"]["state_enum"] == ["跟踪", "持有中", "已清仓"]
    assert pool_payload["pool"] == []

    with sqlite3.connect(str(db_path)) as conn:
        table_names = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'lowfreq_score_%'"
            ).fetchall()
        }
    assert {
        "lowfreq_score_pool_current",
        "lowfreq_score_pool_events",
        "lowfreq_score_daily_price_snapshots",
        "lowfreq_score_period_summaries",
    }.issubset(table_names)

    store.upsert_pool_current(
        {
            "code": "600001",
            "name": "领涨一号",
            "sector": "I65",
            "sector_name": "机器人",
            "state": "持有中",
            "state_since": "2026-06-09",
            "tracking_since": "2026-06-03",
            "buy_date": "2026-06-09",
            "buy_price": 10.0,
            "last_trade_date": "2026-06-10",
            "last_price": 10.8,
            "current_return_pct": 8.0,
            "engine_snapshot_ref": "engine://snapshot/2026-06-09/600001",
            "updated_at": "2026-06-10T15:00:00Z",
        }
    )
    store.append_event(
        {
            "event_id": "evt-1",
            "code": "600001",
            "sector_name": "机器人",
            "event_type": "entered_holding",
            "event_date": "2026-06-09",
            "from_state": "跟踪",
            "to_state": "持有中",
            "trigger_source": "engine",
            "engine_evidence_ref": "engine://snapshot/2026-06-09/600001",
            "price": 10.0,
            "note": "正式买点成立",
            "created_at": "2026-06-09T09:35:00Z",
        }
    )
    store.upsert_period_summary(
        {
            "period_type": "week",
            "period_start": "2026-06-08",
            "period_end": "2026-06-12",
            "tracked_count": 12,
            "holding_count": 3,
            "closed_count": 1,
            "entered_count": 2,
            "holding_return_pct": 6.5,
            "realized_return_pct": 3.2,
            "pool_return_pct": 5.1,
            "capture_quality": 0.66,
            "top_exit_quality": 0.52,
            "updated_at": "2026-06-12T15:00:00Z",
        }
    )
    service._lowfreq_score_sync_state = lambda target_date=None: {
        "target_date": "2026-06-10",
        "synced_tracking": 0,
        "synced_holding": 0,
        "synced_closed": 0,
        "synced_events": 0,
    }

    item_payload = service.lowfreq_score_pool_item_view(code="600001", event_limit=10)
    assert item_payload["item"]["state"] == "持有中"
    assert item_payload["item"]["sector_name"] == "机器人"
    assert item_payload["meta"]["as_of_date"] == "2026-06-10"
    assert item_payload["events"][0]["event_type"] == "entered_holding"
    assert item_payload["events"][0]["sector_name"] == "机器人"
    assert item_payload["snapshots"] == []

    summary_payload = service.lowfreq_score_summary_view(period_type="week", limit=5)
    assert summary_payload["summaries"][0]["period_type"] == "week"
    assert summary_payload["summaries"][0]["tracked_count"] == 12


def test_lowfreq_score_sync_maps_engine_candidates_positions_and_closed_trades(tmp_path: Path) -> None:
    service = _make_service()
    db_path = tmp_path / "lowfreq_score_sync.db"
    service._stock_db_default_path = db_path
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            """
            CREATE TABLE stocks (
              code TEXT PRIMARY KEY,
              name TEXT,
              sector_lv1 TEXT,
              sector_lv2 TEXT
            )
            """
        )
        conn.executemany(
            "INSERT INTO stocks(code, name, sector_lv1, sector_lv2) VALUES (?, ?, ?, ?)",
            [
                ("600001", "跟踪股", "科技", "机器人"),
                ("600002", "持有股", "科技", "机器人"),
                ("600003", "已清仓股", "科技", "人工智能"),
            ],
        )
        conn.commit()
    service._lowfreq_latest_trade_date = lambda: "2026-06-10"
    service._load_lowfreq_sim_state = lambda: {
        "positions": {
            "600002": {
                "code": "600002",
                "name": "持有股",
                "sector": "I65",
                "buy_date": "2026-06-05",
                "buy_price": 10.0,
                "shares": 1000,
                "buy_score": 96.0,
                "wave_phase": "3浪",
                "status": "open",
                "role": "龙头",
            }
        },
        "closed_trades": [
            {
                "code": "600003",
                "name": "已清仓股",
                "sector": "C42",
                "buy_date": "2026-05-20",
                "buy_price": 8.0,
                "sell_date": "2026-06-07",
                "sell_price": 10.0,
                "shares": 1000,
                "return_pct": 25.0,
                "sell_reason": "板块见顶确认",
                "status": "closed",
                "role": "中军",
            }
        ],
    }

    class _ScoreEngine:
        def generate_buy_signals(self, _target_date):
            return {
                "candidate_signals": [
                    {
                        "code": "600001",
                        "name": "跟踪股",
                        "sector": "I88",
                        "entry_ready": False,
                        "buy_score": 88.0,
                        "reasons": ["候选识别成立"],
                        "formal": {
                            "status": "ok",
                            "small_cycle": {
                                "cycle_state": "S1 Emerging",
                                "state_stability_level": "watch",
                            },
                            "identify_state": {
                                "status": "identified",
                                "reason": "small_cycle_enters_formal_watch_scope",
                            },
                            "tracking_state": {
                                "status": "tracking",
                                "maturity": "observe",
                                "transition_reason": "small_cycle_requires_more_confirmation",
                            },
                            "entry_state": {
                                "status": "not_ready",
                                "decision": "wait",
                                "actionable": False,
                                "blocking_reasons": ["tracking_not_mature"],
                            },
                            "m1_constraints_ref": {
                                "blocked": False,
                                "blocking_reasons": [],
                                "profile_window_ready": True,
                            },
                        },
                    }
                ]
            }

        def _get_price(self, code, _target_date):
            return {"600001": 12.3, "600002": 10.8}.get(code)

        def check_sell_signal_v2(self, trade, _target_date):
            if str(getattr(trade, "code", "")) == "600002":
                return SimpleNamespace(reason="sector_top_confirmed", details="板块见顶确认")
            return None

    service._lowfreq_engine_v16 = lambda: _ScoreEngine()

    pool_payload = service.lowfreq_score_pool_view(limit=20)
    pool_by_code = {item["code"]: item for item in pool_payload["pool"]}
    assert pool_payload["meta"]["as_of_date"] == "2026-06-10"
    assert pool_payload["summary"]["pool_size"] == 3
    assert pool_payload["summary"]["tracked_count"] == 1
    assert pool_payload["summary"]["holding_count"] == 1
    assert pool_payload["summary"]["closed_count"] == 1
    assert pool_by_code["600001"]["state"] == "跟踪"
    assert pool_by_code["600001"]["sector_name"] == "机器人"
    assert pool_by_code["600002"]["state"] == "持有中"
    assert pool_by_code["600002"]["sector_name"] == "机器人"
    assert pool_by_code["600003"]["state"] == "已清仓"
    assert pool_by_code["600003"]["sector_name"] == "人工智能"
    assert pool_by_code["600002"]["current_return_pct"] == 8.0
    assert pool_by_code["600003"]["realized_return_pct"] == 25.0

    events_payload = service.lowfreq_score_events_view(limit=20)
    event_types_by_code = {}
    for event in events_payload["events"]:
        event_types_by_code.setdefault(event["code"], set()).add(event["event_type"])
    assert "tracked" in event_types_by_code["600001"]
    assert "entered_holding" in event_types_by_code["600002"]
    assert "top_detected" in event_types_by_code["600002"]
    assert "closed" in event_types_by_code["600003"]
    assert {
        event["code"]: event["sector_name"]
        for event in events_payload["events"]
        if event["event_type"] in {"tracked", "entered_holding", "top_detected", "closed"}
    }["600001"] == "机器人"

    item_payload = service.lowfreq_score_pool_item_view(code="600002", event_limit=10)
    assert item_payload["ui_contract"]["event_type_enum"][0] == "tracked"
    assert item_payload["snapshots"][0]["trade_date"] == "2026-06-10"
    assert item_payload["snapshots"][0]["state"] == "持有中"
    assert item_payload["snapshots"][0]["unrealized_return_pct"] == 8.0

    day_summary = service.lowfreq_score_summary_view(period_type="day", limit=5)["summaries"][0]
    assert day_summary["period_type"] == "day"
    assert day_summary["period_start"] == "2026-06-10"
    assert day_summary["tracked_count"] == 1
    assert day_summary["holding_count"] == 1
    assert day_summary["entered_count"] == 0
    assert day_summary["holding_return_pct"] == 8.0
    assert day_summary["pool_return_pct"] == 8.0

    month_summary = service.lowfreq_score_summary_view(period_type="month", limit=5)["summaries"][0]
    assert month_summary["period_type"] == "month"
    assert month_summary["period_start"] == "2026-06-01"
    assert month_summary["holding_count"] == 1
    assert month_summary["closed_count"] == 1
    assert month_summary["entered_count"] == 1
    assert month_summary["realized_return_pct"] == 25.0
    assert month_summary["pool_return_pct"] == 16.5
    assert month_summary["capture_quality"] == 0.5
    assert month_summary["top_exit_quality"] == 1.0


def test_lowfreq_score_historical_query_uses_projection_without_mutating_store(tmp_path: Path) -> None:
    db_path = tmp_path / "lowfreq-score-history.db"
    service = _make_service()
    service._stock_db_default_path = db_path
    service._lowfreq_latest_trade_date = lambda: "2026-06-10"
    service._load_lowfreq_sim_state = lambda: {
        "positions": {
            "600002": {
                "code": "600002",
                "name": "持有二号",
                "sector": "机器人",
                "buy_date": "2026-06-05",
                "buy_price": 11.0,
                "role": "leader",
            }
        },
        "closed_trades": [
            {
                "code": "600003",
                "name": "已清仓三号",
                "sector": "机器人",
                "buy_date": "2026-05-28",
                "sell_date": "2026-06-07",
                "buy_price": 8.0,
                "sell_price": 9.2,
                "return_pct": 15.0,
                "net_return_pct": 14.5,
                "sell_reason": "见顶",
                "role": "leader",
            }
        ],
    }

    class _HistoricalEngine:
        BUY_SIGNAL_MEMORY_DAYS = 5

        def generate_buy_signals(self, requested_date):
            return {
                "candidate_signals": [
                    {
                        "code": "600001",
                        "name": "跟踪一号",
                        "sector": "机器人",
                        "reasons": ["候选成立"],
                    }
                ]
            }

        def check_sell_signal_v2(self, trade, requested_date):
            return None

        def _get_price(self, code, requested_date):
            return {
                "600001": 10.0,
                "600002": 11.5,
                "600003": 8.6,
            }.get(str(code), 0.0)

    service._lowfreq_engine_v16 = lambda: _HistoricalEngine()

    payload = service.lowfreq_score_pool_view(
        target_date="2026-06-01",
        requested_by="pytest",
    )

    pool_by_code = {
        str(item["code"]): item
        for item in payload["pool"]
        if isinstance(item, dict) and item.get("code")
    }
    assert set(pool_by_code.keys()) == {"600001", "600003"}
    assert pool_by_code["600001"]["state"] == "跟踪"
    assert pool_by_code["600003"]["state"] == "持有中"
    assert pool_by_code["600003"]["buy_date"] == "2026-05-28"
    assert pool_by_code["600003"]["sell_date"] is None
    assert payload["meta"]["sync"]["persisted"] is False

    store = api_main.LowfreqScoreStore(db_path=db_path)
    store.ensure_schema()
    assert store.list_pool_current(limit=50) == []


def test_lowfreq_score_manual_wrappers_expose_new_contract(monkeypatch) -> None:
    service = _make_service()

    monkeypatch.setattr(
        service,
        "lowfreq_manual_buy_intent_view",
        lambda **_kwargs: {
            "_meta": {
                "status": "ok",
                "requested_by": "dashboard.react",
                "deprecated": {"is_deprecated": True},
            },
            "intent": {"intent_id": "buy-1", "intent_type": "buy_intent"},
        },
    )
    monkeypatch.setattr(
        service,
        "lowfreq_manual_abandon_view",
        lambda **_kwargs: {
            "_meta": {
                "status": "ok",
                "requested_by": "dashboard.react",
                "deprecated": {"is_deprecated": True},
            },
            "intent": {"intent_id": "abandon-1", "intent_type": "abandon"},
        },
    )

    buy_payload = service.lowfreq_score_manual_buy_intent_view(
        code="600001",
        requested_date="2026-06-10",
        requested_by="dashboard.react",
    )
    abandon_payload = service.lowfreq_score_manual_abandon_view(
        code="600001",
        requested_date="2026-06-10",
        requested_by="dashboard.react",
    )

    assert buy_payload["_meta"]["contract"] == "lowfreq-score/manual-buy-intent.v1alpha1"
    assert buy_payload["_meta"]["authoritative_layer"] == "operation_logic"
    assert "deprecated" not in buy_payload["_meta"]
    assert buy_payload["intent"]["intent_id"] == "buy-1"

    assert abandon_payload["_meta"]["contract"] == "lowfreq-score/manual-abandon.v1alpha1"
    assert abandon_payload["_meta"]["authoritative_layer"] == "operation_logic"
    assert "deprecated" not in abandon_payload["_meta"]
    assert abandon_payload["intent"]["intent_id"] == "abandon-1"


def test_lowfreq_backtest_status_view_includes_summary_when_json_exists(tmp_path: Path) -> None:
    service = _make_service()
    service._lowfreq_backtest_artifacts_dir = tmp_path / "artifacts"
    report_dir = service._lowfreq_backtest_artifacts_dir / "report-1"
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "status.json").write_text(
        '{"status":"done","report_id":"report-1"}\n',
        encoding="utf-8",
    )
    (report_dir / "trades.json").write_text(
        (
            '{"execution_mode":"unbounded_opportunity","summary":'
            '{"total_return_pct":12.34,"annualized_return_pct":8.76,'
            '"max_drawdown_pct":-3.21,"sharpe_ratio":1.11}}\n'
        ),
        encoding="utf-8",
    )

    payload = service.lowfreq_backtest_status_view(report_id="report-1")

    assert payload["job"]["status"] == "done"
    assert payload["execution_mode"] == "unbounded_opportunity"
    assert payload["summary"]["total_return_pct"] == 12.34


def test_lowfreq_backtest_report_download_view_returns_binary_pdf(tmp_path: Path) -> None:
    service = _make_service()
    service._lowfreq_backtest_artifacts_dir = tmp_path / "artifacts"
    report_dir = service._lowfreq_backtest_artifacts_dir / "report-1"
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "trades.pdf").write_bytes(b"%PDF-1.4\nmock\n")

    payload = service.lowfreq_backtest_report_download_view(
        report_id="report-1", format="pdf"
    )

    assert isinstance(payload, ApiBinaryResponse)
    assert payload.body.startswith(b"%PDF-1.4")
    assert payload.content_type == "application/pdf"
    assert payload.headers["Content-Disposition"] == 'attachment; filename="report-1.pdf"'


def test_lowfreq_backtest_report_detail_view_returns_structured_payload(
    tmp_path: Path,
) -> None:
    service = _make_service()
    service._lowfreq_backtest_artifacts_dir = tmp_path / "artifacts"
    report_dir = service._lowfreq_backtest_artifacts_dir / "report-1"
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "trades.pdf").write_bytes(b"%PDF-1.4\nmock\n")
    (report_dir / "trades.json").write_text(
        json.dumps(
            {
                "execution_mode": "unbounded_opportunity",
                "summary": {
                    "total_return_pct": 12.34,
                    "total_trades": 2,
                    "trades": [{"code": "ignored"}],
                    "buy_signal_audit": [{"code": "ignored"}],
                },
                "execution_action_summary": {"buy": 2},
                "trade_blocks": {"buy_limit_up": 1},
                "config_snapshot": {"execution_mode": "unbounded_opportunity"},
                "coverage_gaps": {"missing_daily_basic_days": 0},
                "exit_quality": {
                    "count": 2,
                    "lookahead_trading_days": 10,
                    "per_trade": [{"code": "ignored"}],
                },
                "next_session": {"next_trading_day": "2026-06-10"},
                "buy_dates": [{"buy_date": "2026-06-01", "count": 1}],
                "trades": [
                    {
                        "code": "600001",
                        "name": "领涨一号",
                        "sector": "I65",
                        "buy_date": "2026-06-01",
                        "sell_date": "2026-06-05",
                        "buy_price": 10.0,
                        "sell_price": 12.0,
                        "return_pct": 20.0,
                        "hold_days": 4,
                        "role": "龙头",
                        "status": "closed",
                        "sell_reason": "测试卖出",
                    }
                ],
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    payload = service.lowfreq_backtest_report_detail_view(report_id="report-1")

    assert payload["report_id"] == "report-1"
    assert payload["summary"]["total_return_pct"] == 12.34
    assert payload["execution_action_summary"] == {"buy": 2}
    assert payload["trade_blocks"] == {"buy_limit_up": 1}
    assert payload["coverage_gaps"] == {"missing_daily_basic_days": 0}
    assert "trades" not in payload["summary"]
    assert "buy_signal_audit" not in payload["summary"]
    assert "per_trade" not in payload["exit_quality"]
    assert payload["recent_trades"][0]["code"] == "600001"
    assert payload["pdf_url"] == "/api/lowfreq/backtest/reports/report-1.pdf"
    assert payload["json_url"] == "/api/lowfreq/backtest/reports/report-1.json"


def test_router_dispatches_lowfreq_score_pool_endpoint() -> None:
    class _StubService:
        def lowfreq_score_pool_view(self, *, state=None, limit=500, target_date=None, requested_by="api"):
            return {
                "_meta": {"status": "ok"},
                "meta": {
                    "state_filter": state,
                    "limit": limit,
                    "target_date": target_date,
                    "requested_by": requested_by,
                },
                "pool": [],
            }

    router = BootstrapApiRouter(service=_StubService())
    status, payload = router.dispatch("/api/lowfreq-score/pool?state=跟踪&limit=20&date=2026-06-10")

    assert int(status) == 200
    assert payload["meta"]["state_filter"] == "跟踪"
    assert payload["meta"]["limit"] == 20
    assert payload["meta"]["target_date"] == "2026-06-10"
    assert payload["meta"]["requested_by"] == "api"


def test_router_dispatches_lowfreq_score_manual_post_endpoints() -> None:
    class _StubService:
        def lowfreq_score_manual_buy_intent_view(
            self,
            *,
            code,
            requested_date,
            name="",
            sector="",
            role="",
            buy_score=0.0,
            requested_by="api",
        ):
            return {
                "_meta": {"status": "ok", "contract": "lowfreq-score/manual-buy-intent.v1alpha1"},
                "intent": {
                    "code": code,
                    "requested_date": requested_date,
                    "name": name,
                    "sector": sector,
                    "role": role,
                    "buy_score": buy_score,
                    "requested_by": requested_by,
                },
            }

        def lowfreq_score_manual_abandon_view(
            self,
            *,
            code,
            requested_date,
            requested_by="api",
        ):
            return {
                "_meta": {"status": "ok", "contract": "lowfreq-score/manual-abandon.v1alpha1"},
                "intent": {
                    "code": code,
                    "requested_date": requested_date,
                    "requested_by": requested_by,
                },
            }

    router = BootstrapApiRouter(service=_StubService())

    buy_status, buy_payload = router.dispatch_post(
        "/api/lowfreq-score/manual/buy-intent",
        {
            "code": "600001",
            "name": "领涨一号",
            "sector": "机器人",
            "role": "leader",
            "buy_score": 92,
            "requested_date": "2026-06-10",
            "requested_by": "dashboard.react",
        },
    )
    abandon_status, abandon_payload = router.dispatch_post(
        "/api/lowfreq-score/manual/abandon",
        {
            "code": "600001",
            "requested_date": "2026-06-10",
            "requested_by": "dashboard.react",
        },
    )

    assert int(buy_status) == 200
    assert buy_payload["_meta"]["contract"] == "lowfreq-score/manual-buy-intent.v1alpha1"
    assert buy_payload["intent"]["code"] == "600001"
    assert buy_payload["intent"]["requested_by"] == "dashboard.react"

    assert int(abandon_status) == 200
    assert abandon_payload["_meta"]["contract"] == "lowfreq-score/manual-abandon.v1alpha1"
    assert abandon_payload["intent"]["code"] == "600001"
    assert abandon_payload["intent"]["requested_by"] == "dashboard.react"
