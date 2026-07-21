from __future__ import annotations

import json
from datetime import date

from neotrade3.analysis.step8_artifact_writer import write_step8_quality_report_artifact
from neotrade3.governance.step8_artifact_writer import (
    write_step8_adjustment_proposal_artifact,
    write_step8_governance_decision_log_artifact,
)


def test_step8_quality_report_fails_when_discipline_block_days_positive(tmp_path) -> None:
    asof_date = date(2026, 6, 3).isoformat()
    source_run_id = "run_abc"
    backtest_report_id = "backtest_xyz"
    backtest_result = {
        "buy_signal_audit": [
            {"event": "buy_executed"},
            {"event": "trade_discipline_guard_blocked"},
        ],
        "trade_discipline_audit": [
            {"guard_verdict": {"status": "block"}},
        ],
    }
    record = write_step8_quality_report_artifact(
        project_root=tmp_path,
        asof_date=asof_date,
        source_run_id=source_run_id,
        backtest_result=backtest_result,
        backtest_report_id=backtest_report_id,
    )
    assert record.quality_verdict == "fail"
    assert record.backtest_report_id == backtest_report_id
    assert "discipline_block_days" in record.quality_fail_reason_codes
    p = tmp_path / record.artifact_path
    assert p.exists() is True
    payload = json.loads(p.read_text(encoding="utf-8"))
    assert payload["backtest_report_id"] == backtest_report_id
    report = payload["tracking_pool_quality_report"]
    assert report["quality_verdict"] == "fail"
    assert report["summary_metrics"]["discipline_block_days_n"] == 1
    assert "discipline_block_days" in report["quality_fail_reason_codes"]


def test_step8_quality_report_fails_when_discipline_guard_blocked_positive(tmp_path) -> None:
    asof_date = date(2026, 6, 3).isoformat()
    source_run_id = "run_abc"
    backtest_result = {
        "buy_signal_audit": [
            {"event": "trade_discipline_guard_blocked"},
        ],
        "trade_discipline_audit": [
            {"guard_verdict": {"status": "pass"}},
        ],
    }
    record = write_step8_quality_report_artifact(
        project_root=tmp_path,
        asof_date=asof_date,
        source_run_id=source_run_id,
        backtest_result=backtest_result,
    )
    assert record.backtest_report_id is None
    assert record.quality_verdict == "fail"
    payload = json.loads((tmp_path / record.artifact_path).read_text(encoding="utf-8"))
    assert payload["backtest_report_id"] is None
    report = payload["tracking_pool_quality_report"]
    assert report["summary_metrics"]["trade_discipline_guard_blocked_n"] == 1
    assert "discipline_guard_blocked" in report["quality_fail_reason_codes"]


def test_step8_quality_report_dry_run_does_not_create_files(tmp_path) -> None:
    asof_date = date(2026, 6, 3).isoformat()
    source_run_id = "run_abc"
    backtest_result = {
        "buy_signal_audit": [],
        "trade_discipline_audit": [],
    }
    record = write_step8_quality_report_artifact(
        project_root=tmp_path,
        asof_date=asof_date,
        source_run_id=source_run_id,
        backtest_result=backtest_result,
        dry_run=True,
    )
    assert (tmp_path / record.artifact_path).exists() is False


def test_step8_quality_report_writes_upstream_evidence_paths(tmp_path) -> None:
    asof_date = date(2026, 6, 3).isoformat()
    source_run_id = "run_abc"
    upstream = ["var/reports/x/backtest_payload.json", "var/reports/x/backtest_summary.json"]
    backtest_result = {
        "buy_signal_audit": [],
        "trade_discipline_audit": [],
    }
    record = write_step8_quality_report_artifact(
        project_root=tmp_path,
        asof_date=asof_date,
        source_run_id=source_run_id,
        backtest_result=backtest_result,
        upstream_evidence_paths=upstream,
    )
    payload = json.loads((tmp_path / record.artifact_path).read_text(encoding="utf-8"))
    report = payload["tracking_pool_quality_report"]
    assert upstream[0] in report["evidence_paths"]
    assert upstream[1] in report["evidence_paths"]
    trigger_inputs = payload["evaluation_trigger_inputs"]
    assert upstream[0] in trigger_inputs["evidence_paths"]
    assert upstream[1] in trigger_inputs["evidence_paths"]


def test_step8_quality_report_pending_has_empty_report_paths(tmp_path) -> None:
    asof_date = date(2026, 6, 3).isoformat()
    source_run_id = "run_abc"
    backtest_result = {}
    record = write_step8_quality_report_artifact(
        project_root=tmp_path,
        asof_date=asof_date,
        source_run_id=source_run_id,
        backtest_result=backtest_result,
    )
    assert record.outputs_ready == "pending"
    p = tmp_path / record.artifact_path
    payload = json.loads(p.read_text(encoding="utf-8"))
    outputs = payload["evaluation_outputs"]
    assert outputs["outputs_ready"] == "pending"
    assert outputs["report_paths"] == []


def test_step8_governance_proposal_and_decision_log_writers_write_single_files(tmp_path) -> None:
    asof_date = date(2026, 6, 3).isoformat()
    source_report_id = "run_abc-20260603-step8"
    upstream = ["var/artifacts/step8_quality_reports/run_abc-20260603-step8/tracking_pool_quality_report.json"]
    proposal_record = write_step8_adjustment_proposal_artifact(
        project_root=tmp_path,
        asof_date=asof_date,
        source_report_id=source_report_id,
        rb_ids_touched=["RB.M2.STEP2.CERTAINTY_SCORE.001"],
        proposed_changes=[{"target": "M2", "action": "raise_threshold", "before": "80", "after": "85"}],
        risk_notes="v0 test",
        upstream_evidence_paths=upstream,
    )
    assert (tmp_path / proposal_record.artifact_path).exists() is True
    proposal_payload = json.loads(
        (tmp_path / proposal_record.artifact_path).read_text(encoding="utf-8")
    )
    assert proposal_payload["adjustment_proposal"]["proposal_id"] == proposal_record.proposal_id
    assert upstream[0] in proposal_payload["adjustment_proposal"]["evidence_paths"]

    log_record = write_step8_governance_decision_log_artifact(
        project_root=tmp_path,
        asof_date=asof_date,
        source_proposal_id=proposal_record.proposal_id,
        decision="defer",
        rationale="v0 test",
        upstream_evidence_paths=upstream,
    )
    assert (tmp_path / log_record.artifact_path).exists() is True
    log_payload = json.loads(
        (tmp_path / log_record.artifact_path).read_text(encoding="utf-8")
    )
    assert log_payload["governance_decision_log"]["log_id"] == log_record.log_id
    assert upstream[0] in log_payload["governance_decision_log"]["evidence_paths"]
