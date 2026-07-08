from __future__ import annotations

from datetime import date
from pathlib import Path

from apps.api.main import BootstrapApiService


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _make_service() -> BootstrapApiService:
    return BootstrapApiService(project_root=PROJECT_ROOT)


class _DatedBuyEngine:
    BUY_SIGNAL_MEMORY_DAYS = 5

    def __init__(self, *, signals_by_date: dict[str, list[dict[str, object]]]):
        self.signals_by_date = signals_by_date

    def check_sell_signal_v2(self, trade, requested_date):
        return None

    def generate_buy_signals(self, requested_date):
        key = requested_date.isoformat() if hasattr(requested_date, "isoformat") else str(requested_date)
        return {"buy_signals": list(self.signals_by_date.get(key, []))}


class _ImmediateBuyEngine:
    BUY_SIGNAL_MEMORY_DAYS = 0

    def __init__(self, *, signals: list[dict[str, object]]):
        self.signals = signals

    def check_sell_signal_v2(self, trade, requested_date):
        return None

    def generate_buy_signals(self, requested_date):
        return {"buy_signals": list(self.signals)}


def _formal_signal(*, code: str) -> dict[str, object]:
    return {
        "code": code,
        "name": "华锡有色",
        "sector": "有色",
        "role": "龙头",
        "buy_score": 88.0,
        "wave_phase": "启动",
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


def test_buy_signal_memory_merge_path_carries_formal_front(monkeypatch) -> None:
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
    monkeypatch.setattr(service, "_lowfreq_nth_next_trading_day", lambda after_date, n: "2026-06-20")
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
    engine = _DatedBuyEngine(signals_by_date={"2026-06-15": [_formal_signal(code="600301")]})

    out = service._lowfreq_generate_execution_intents_for_date(
        state=state,
        engine=engine,
        requested_date=date(2026, 6, 15),
    )

    assert out["created_buy"] == 0
    entry = state["signal_memory"]["buy_signals"][0]
    assert entry["code"] == "600301"
    assert entry["source"] == "model_signal_memory"
    assert entry["formal_front"]["status"] == "ok"
    assert entry["formal_front"]["tracking_state"]["status"] == "tracking"
    assert entry["formal_front"]["entry_state"]["status"] == "not_ready"


def test_buy_signal_memory_fallback_path_carries_formal_front(monkeypatch) -> None:
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
        "signal_memory": {"buy_signals": []},
    }

    out = service._lowfreq_generate_execution_intents_for_date(
        state=state,
        engine=_ImmediateBuyEngine(signals=[_formal_signal(code="600301")]),
        requested_date=date(2026, 6, 15),
    )

    assert out["created_buy"] == 0
    entry = state["signal_memory"]["buy_signals"][0]
    assert entry["code"] == "600301"
    assert entry["source"] == "model"
    assert entry["formal_front"]["status"] == "ok"
    assert entry["formal_front"]["small_cycle"]["cycle_state"] == "S1 Emerging"
    assert entry["formal_front"]["entry_state"]["blocking_reasons"] == ["tracking_not_mature"]
