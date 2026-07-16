from __future__ import annotations

import json
from pathlib import Path

from apps.api.main import BootstrapApiService
from neotrade3.strategy_config import StrategyConfig, save_strategy_config


def _write_daily_run_ledger(*, project_root: Path, target_date: str) -> None:
    ledger_dir = project_root / "var/ledgers/daily_runs"
    ledger_dir.mkdir(parents=True, exist_ok=True)
    (ledger_dir / f"{target_date}.json").write_text(
        json.dumps(
            {
                "target_date": target_date,
                "trade_date": target_date,
                "finished_at": f"{target_date}T08:10:00Z",
                "steps": [
                    {"step_id": "yesterday_closeout", "status": "ok", "outputs": {"summary": {}}},
                    {"step_id": "authoritative_update", "status": "ok", "outputs": {"trade_date": target_date}},
                    {"step_id": "screeners_bulk_run", "status": "ok", "outputs": {"status": "ok"}},
                    {"step_id": "lowfreq_sim_daily", "status": "ok", "outputs": {"pending_intents_after": 0}},
                ],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def test_ops_center_summary_includes_strategy_config_ok_status(tmp_path: Path, monkeypatch) -> None:
    target_date = "2026-06-09"
    _write_daily_run_ledger(project_root=tmp_path, target_date=target_date)
    save_strategy_config(
        project_root=tmp_path,
        config=StrategyConfig(strategy_id="lowfreq_v16", version=9, description="", parameters={}),
    )
    service = BootstrapApiService(project_root=tmp_path)
    monkeypatch.setattr(service, "_lowfreq_latest_trade_date", lambda: target_date)

    payload = service.ops_center_summary_view(target_date=target_date)

    assert payload["evidence"]["strategy_id"] == "lowfreq_v16"
    assert payload["evidence"]["strategy_config_status"] == "ok"
    assert payload["evidence"]["strategy_version"] == 9
    item = next(it for it in payload["checklist"] if it["item_id"] == "strategy_config")
    assert item["status"] == "ok"


def test_ops_center_summary_includes_strategy_config_degraded_status_when_missing(
    tmp_path: Path, monkeypatch
) -> None:
    target_date = "2026-06-09"
    _write_daily_run_ledger(project_root=tmp_path, target_date=target_date)
    service = BootstrapApiService(project_root=tmp_path)
    monkeypatch.setattr(service, "_lowfreq_latest_trade_date", lambda: target_date)

    payload = service.ops_center_summary_view(target_date=target_date)

    assert payload["evidence"]["strategy_id"] == "lowfreq_v16"
    assert payload["evidence"]["strategy_config_status"] == "degraded"
    assert payload["evidence"]["strategy_version"] is None
    item = next(it for it in payload["checklist"] if it["item_id"] == "strategy_config")
    assert item["status"] == "degraded"

