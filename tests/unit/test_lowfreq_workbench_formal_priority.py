from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from apps.api.main import BootstrapApiService


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _make_service() -> BootstrapApiService:
    return BootstrapApiService(project_root=PROJECT_ROOT)


def _make_workbench_stock(
    *,
    buy_signal: bool,
    formal_front: dict[str, object],
    manual: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "code": "600001",
        "name": "领涨一号",
        "sector": "机器人",
        "role": "龙头",
        "buy_signal": buy_signal,
        "certainty_prob": 0.82,
        "reasons": ["突破确认"],
        "formal_front": formal_front,
        "manual": manual or {"buy_intent_pending": False},
    }


def _prepare_lowfreq_workbench_service(
    monkeypatch,
    tmp_path: Path,
    *,
    stock: dict[str, object],
) -> BootstrapApiService:
    service = _make_service()
    service._daily_runs_dir = tmp_path / "daily_runs"
    service._daily_runs_dir.mkdir(parents=True, exist_ok=True)
    (service._daily_runs_dir / "2026-06-09.json").write_text(
        json.dumps(
            {
                "target_date": "2026-06-09",
                "trade_date": "2026-06-09",
                "started_at": "2026-06-09T07:45:00Z",
                "finished_at": "2026-06-09T08:10:00Z",
                "steps": [
                    {"step_id": "yesterday_closeout", "status": "ok", "outputs": {"summary": {}}},
                    {"step_id": "authoritative_update", "status": "ok", "outputs": {"trade_date": "2026-06-09"}},
                    {"step_id": "screeners_bulk_run", "status": "ok", "outputs": {"status": "ok"}},
                    {"step_id": "lowfreq_sim_daily", "status": "ok", "outputs": {"pending_intents_after": 1}},
                ],
            },
            ensure_ascii=False,
        )
        + "\n",
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
        lambda **kwargs: {"queue": [{"code": "600001", "source_date": "2026-06-09"}]},
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
                    "leaders": [stock],
                    "middle": [],
                    "followers": [],
                }
            ],
            "portfolio": {"open_positions": [], "closed_trades": [], "manual_intents": []},
        },
    )
    return service


def test_lowfreq_workbench_view_prefers_formal_blocked_over_legacy_buy_signal(
    monkeypatch, tmp_path: Path
) -> None:
    service = _prepare_lowfreq_workbench_service(
        monkeypatch,
        tmp_path,
        stock=_make_workbench_stock(
            buy_signal=True,
            formal_front={
                "status": "ok",
                "identify_state": {"status": "identified", "reason": "watch_scope"},
                "tracking_state": {
                    "status": "tracking",
                    "maturity": "observe",
                    "transition_reason": "await_more_confirmation",
                },
                "entry_state": {
                    "status": "not_ready",
                    "decision": "wait",
                    "actionable": False,
                    "blocking_reasons": ["constraint_blocked"],
                },
                "m1_constraints": {
                    "blocked": True,
                    "blocking_reasons": ["constraint_blocked"],
                    "profile_window_ready": True,
                },
            },
        ),
    )

    payload = service.lowfreq_workbench_view(target_date="2026-06-09")

    assert payload["meta"]["strategy_config_url"] == "/api/strategies/lowfreq_v16"
    assert (
        payload["meta"]["strategy_config_download_url"]
        == "/api/strategies/lowfreq_v16/download"
    )
    assert payload["hot_sectors"][0]["representatives"][0]["tracking_status_text"] == "暂不参与"
    assert payload["tracking_list"][0]["tracking_stage"] == "candidate"
    assert payload["tracking_list"][0]["tracking_status"] == "blocked"
    assert payload["tracking_list"][0]["tracking_status_text"] == "暂不参与"


def test_lowfreq_workbench_view_keeps_formal_not_ready_in_tracking_bucket(
    monkeypatch, tmp_path: Path
) -> None:
    service = _prepare_lowfreq_workbench_service(
        monkeypatch,
        tmp_path,
        stock=_make_workbench_stock(
            buy_signal=True,
            formal_front={
                "status": "ok",
                "identify_state": {"status": "identified", "reason": "watch_scope"},
                "tracking_state": {
                    "status": "tracking",
                    "maturity": "observe",
                    "transition_reason": "await_more_confirmation",
                },
                "entry_state": {
                    "status": "not_ready",
                    "decision": "wait",
                    "actionable": False,
                    "blocking_reasons": ["tracking_not_mature"],
                },
                "m1_constraints": {
                    "blocked": False,
                    "blocking_reasons": [],
                    "profile_window_ready": True,
                },
            },
        ),
    )

    payload = service.lowfreq_workbench_view(target_date="2026-06-09")

    assert payload["hot_sectors"][0]["representatives"][0]["tracking_status_text"] == "跟踪"
    assert payload["tracking_list"][0]["tracking_stage"] == "candidate"
    assert payload["tracking_list"][0]["tracking_status"] == "watch"
    assert payload["tracking_list"][0]["tracking_status_text"] == "持续跟踪"


def test_lowfreq_workbench_view_falls_back_to_legacy_when_formal_errors(
    monkeypatch, tmp_path: Path
) -> None:
    service = _prepare_lowfreq_workbench_service(
        monkeypatch,
        tmp_path,
        stock=_make_workbench_stock(
            buy_signal=True,
            formal_front={
                "status": "error",
                "error_type": "formal_projection_failed",
                "message": "projection failed",
            },
        ),
    )

    payload = service.lowfreq_workbench_view(target_date="2026-06-09")

    assert payload["hot_sectors"][0]["representatives"][0]["tracking_status_text"] == "可建仓"
    assert payload["tracking_list"][0]["tracking_stage"] == "entry_ready"
    assert payload["tracking_list"][0]["tracking_status"] == "entry_ready"
    assert payload["tracking_list"][0]["tracking_status_text"] == "可建仓"
