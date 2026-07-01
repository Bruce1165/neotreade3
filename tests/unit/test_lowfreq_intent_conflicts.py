from __future__ import annotations

from datetime import date
from pathlib import Path
from types import SimpleNamespace

from apps.api.main import BootstrapApiService


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
    assert trade.market_exit_last_hit_date == "2026-04-02"
    assert trade.sector_exit_state == "observe"
    assert trade.sector_exit_start_date == "2026-04-02"
    assert trade.sector_exit_expire_date == "2026-04-08"
    assert trade.sector_exit_hits == 1
    assert trade.sector_exit_last_hit_date == "2026-04-02"
    assert trade.system_exit_grace_used is True
    assert trade.system_exit_grace_date == "2026-04-03"
    assert trade.system_exit_grace_scope == "market"
    assert trade.system_exit_grace_reason == "创业板见顶确认候选：趋势转弱=是 | 广度转弱=是 | 代理回撤-10.5%"
