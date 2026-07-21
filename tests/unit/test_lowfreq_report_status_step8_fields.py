from __future__ import annotations

import json
from pathlib import Path

from neotrade3.orchestration.report_runner_status_writer import write_lowfreq_report_status


def test_status_writer_accepts_step8_fields(tmp_path: Path) -> None:
    tmp_path.mkdir(parents=True, exist_ok=True)
    write_lowfreq_report_status(
        tmp_path,
        stage="backtest_ready",
        ranking_count=1,
        backtest_report_id="bt_run_1",
        backtest_input_evidence_ready=True,
        backtest_payload_path="backtest_payload.json",
        backtest_summary_path="backtest_summary.json",
        step8_quality_report_path="var/artifacts/step8_quality_reports/x/y.json",
        step8_quality_verdict="fail",
        step8_quality_fail_reason_codes=["discipline_guard_blocked"],
        step8_proposal_path=None,
    )
    payload = json.loads((tmp_path / "status.json").read_text(encoding="utf-8"))
    assert payload["stage"] == "backtest_ready"
    assert payload["backtest_report_id"] == "bt_run_1"
    assert payload["backtest_input_evidence_ready"] is True
    assert payload["backtest_payload_path"] == "backtest_payload.json"
    assert payload["step8_quality_verdict"] == "fail"
    assert payload["step8_quality_fail_reason_codes"] == ["discipline_guard_blocked"]
