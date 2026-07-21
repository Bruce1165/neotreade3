from __future__ import annotations

import json
from pathlib import Path

from neotrade3.orchestration.report_runner_status import (
    build_analysis_ready_report_status,
    build_backtest_ready_report_status,
    build_done_report_status,
)
from neotrade3.orchestration.report_runner_status_writer import write_lowfreq_report_status


def test_status_carries_step8_fields_across_stages(tmp_path: Path) -> None:
    output_dir = tmp_path
    output_dir.mkdir(parents=True, exist_ok=True)

    step8_fields = {
        "step8_quality_report_path": "var/artifacts/step8_quality_reports/r/quality.json",
        "step8_report_id": "r-step8",
        "step8_outputs_ready": "ready",
        "step8_quality_verdict": "pass",
        "step8_quality_fail_reason_codes": [],
        "backtest_report_id": "bt_run_1",
        "backtest_input_evidence_ready": True,
        "backtest_payload_path": "backtest_payload.json",
        "backtest_summary_path": "backtest_summary.json",
    }

    backtest_ready = build_backtest_ready_report_status(
        ranking_count=1,
        total_return_pct=1.0,
        total_trades=1,
    )
    backtest_ready.update(step8_fields)
    write_lowfreq_report_status(output_dir, **backtest_ready)

    analysis_ready = build_analysis_ready_report_status(
        ranking_count=1,
        aggregate={"ok": True},
    )
    analysis_ready.update(step8_fields)
    write_lowfreq_report_status(output_dir, **analysis_ready)

    payload = json.loads((output_dir / "status.json").read_text(encoding="utf-8"))
    assert payload["stage"] == "analysis_ready"
    assert payload["step8_quality_report_path"] == step8_fields["step8_quality_report_path"]
    assert payload["backtest_report_id"] == "bt_run_1"
    assert payload["backtest_payload_path"] == "backtest_payload.json"

    done = build_done_report_status(
        report_id="rid",
        ranking_path="a",
        segments_path="b",
        attribution_path="c",
        report_path="d",
    )
    done.update(step8_fields)
    write_lowfreq_report_status(output_dir, **done)
    done_payload = json.loads((output_dir / "status.json").read_text(encoding="utf-8"))
    assert done_payload["stage"] == "done"
    assert done_payload["step8_report_id"] == "r-step8"
