from __future__ import annotations

from pathlib import Path

from neotrade3.orchestration.report_runner_cli_summary import (
    build_lowfreq_report_success_summary,
)


def test_build_lowfreq_report_success_summary_projects_current_payload() -> None:
    aggregate = {"bought_count": 12}

    out = build_lowfreq_report_success_summary(
        report_id="top200_2025_20260712T180000Z",
        output_dir=Path("/tmp/report-runner"),
        ranking_path=Path("/tmp/report-runner/top200_2025_ranking.json"),
        segments_path=Path("/tmp/report-runner/top200_2025_wave_segments.json"),
        attribution_path=Path("/tmp/report-runner/top200_2025_model_attribution.json"),
        report_path=Path("/tmp/report-runner/report.md"),
        aggregate=aggregate,
    )

    assert out == {
        "status": "ok",
        "report_id": "top200_2025_20260712T180000Z",
        "output_dir": "/tmp/report-runner",
        "ranking_path": "/tmp/report-runner/top200_2025_ranking.json",
        "segments_path": "/tmp/report-runner/top200_2025_wave_segments.json",
        "attribution_path": "/tmp/report-runner/top200_2025_model_attribution.json",
        "report_path": "/tmp/report-runner/report.md",
        "aggregate": aggregate,
    }


def test_build_lowfreq_report_success_summary_passes_aggregate_by_reference() -> None:
    aggregate = {"candidate_picked_count": 7}

    out = build_lowfreq_report_success_summary(
        report_id="r1",
        output_dir=Path("/tmp/out"),
        ranking_path=Path("/tmp/out/ranking.json"),
        segments_path=Path("/tmp/out/segments.json"),
        attribution_path=Path("/tmp/out/attribution.json"),
        report_path=Path("/tmp/out/report.md"),
        aggregate=aggregate,
    )

    assert out["aggregate"] is aggregate


def test_build_lowfreq_report_success_summary_keeps_empty_report_id_fallback() -> None:
    out = build_lowfreq_report_success_summary(
        report_id="",
        output_dir=Path("/tmp/out"),
        ranking_path=Path("/tmp/out/ranking.json"),
        segments_path=Path("/tmp/out/segments.json"),
        attribution_path=Path("/tmp/out/attribution.json"),
        report_path=Path("/tmp/out/report.md"),
        aggregate={},
    )

    assert out["status"] == "ok"
    assert out["report_id"] == ""
