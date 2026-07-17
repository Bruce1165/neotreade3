from __future__ import annotations

import hashlib
from pathlib import Path

from neotrade3.decision_engine import (
    DecisionLifecycleLog,
    build_decision_lifecycle_logs,
    build_decision_m3_lifecycle_log_record_id,
    list_decision_m3_lifecycle_log_ledgers,
    materialize_decision_m3_lifecycle_log,
    read_decision_m3_lifecycle_log,
    read_decision_m3_lifecycle_log_artifact,
    read_decision_m3_lifecycle_log_ledger,
)


def _build_lifecycle_log() -> DecisionLifecycleLog:
    logs = build_decision_lifecycle_logs(
        [
            {
                "code": "300001",
                "date": "2026-06-18",
                "event": "market_exit_watch_started",
                "details": "进入市场退出观察态",
            },
            {
                "code": "300001",
                "date": "2026-06-19",
                "event": "market_exit_review_started",
                "details": "进入市场退出复核态",
            },
            {
                "code": "300001",
                "date": "2026-06-20",
                "event": "market_exit_confirmed",
                "details": "市场退出确认",
            },
        ],
        run_id="2026-06-20",
        source_run_id="2026-06-20",
    )
    return DecisionLifecycleLog.from_dict(logs[0])


def _artifact_file(*, project_root: Path, record_id: str) -> Path:
    return (
        project_root
        / "var/artifacts/m3_lifecycle_logs"
        / record_id
        / "lifecycle_log.json"
    )


def test_materialize_decision_m3_lifecycle_log(tmp_path: Path) -> None:
    lifecycle_log = _build_lifecycle_log()
    record_id = build_decision_m3_lifecycle_log_record_id(
        stock_code=lifecycle_log.stock_code,
        run_id=lifecycle_log.run_id,
    )
    ledger_record = materialize_decision_m3_lifecycle_log(
        project_root=tmp_path,
        record_id=record_id,
        lifecycle_log=lifecycle_log,
    )

    artifact = read_decision_m3_lifecycle_log_artifact(
        project_root=tmp_path,
        record_id=record_id,
    )
    reconstructed = read_decision_m3_lifecycle_log(
        project_root=tmp_path,
        record_id=record_id,
    )
    reconstructed_ledger = read_decision_m3_lifecycle_log_ledger(
        project_root=tmp_path,
        record_id=record_id,
    )
    records = list_decision_m3_lifecycle_log_ledgers(project_root=tmp_path, limit=10)

    assert artifact is not None
    assert artifact["object_type"] == "decision_lifecycle_log"
    assert reconstructed == lifecycle_log
    assert reconstructed_ledger == ledger_record
    assert [item.record_id for item in records] == [record_id]

    assert ledger_record.stock_code == "300001"
    assert ledger_record.run_id == "2026-06-20"
    assert ledger_record.source_run_id == "2026-06-20"
    assert ledger_record.events_count == 3
    assert ledger_record.first_trade_date == "2026-06-18"
    assert ledger_record.last_trade_date == "2026-06-20"
    assert ledger_record.last_event == "market_exit_confirmed"
    assert ledger_record.last_stage == "exit_ready"
    assert ledger_record.last_decision == "exit"
    assert ledger_record.last_exit_scope == "portfolio"

    artifact_text = _artifact_file(project_root=tmp_path, record_id=record_id).read_text(
        encoding="utf-8"
    )
    assert ledger_record.artifact_sha256 == hashlib.sha256(
        artifact_text.encode("utf-8")
    ).hexdigest()

