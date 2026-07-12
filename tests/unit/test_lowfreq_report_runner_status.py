from __future__ import annotations

from pathlib import Path

from neotrade3.orchestration.report_runner_status import (
    ReportRunnerStage,
    build_analysis_ready_report_status,
    build_backtest_ready_report_status,
    build_done_report_status,
    build_initializing_report_status,
    build_ranking_ready_report_status,
)


def test_report_runner_stage_values_match_current_protocol() -> None:
    assert ReportRunnerStage.INITIALIZING.value == "initializing"
    assert ReportRunnerStage.RANKING_READY.value == "ranking_ready"
    assert ReportRunnerStage.BACKTEST_READY.value == "backtest_ready"
    assert ReportRunnerStage.ANALYSIS_READY.value == "analysis_ready"
    assert ReportRunnerStage.DONE.value == "done"


def test_build_initializing_report_status_projects_current_payload() -> None:
    out = build_initializing_report_status(
        year="2025",
        limit="200",
        report_id="top200_2025_20260712T170000Z",
    )

    assert out == {
        "stage": "initializing",
        "year": 2025,
        "limit": 200,
        "report_id": "top200_2025_20260712T170000Z",
    }


def test_build_ranking_ready_report_status_projects_current_count_payload() -> None:
    out = build_ranking_ready_report_status(ranking_count="7")

    assert out == {
        "stage": "ranking_ready",
        "ranking_count": 7,
    }


def test_build_backtest_ready_report_status_projects_current_summary_payload() -> None:
    out = build_backtest_ready_report_status(
        ranking_count="200",
        total_return_pct=32.5,
        total_trades=18,
    )

    assert out == {
        "stage": "backtest_ready",
        "ranking_count": 200,
        "total_return_pct": 32.5,
        "total_trades": 18,
    }


def test_build_analysis_ready_report_status_passes_through_aggregate() -> None:
    aggregate = {"bought_count": 12}

    out = build_analysis_ready_report_status(
        ranking_count=200,
        aggregate=aggregate,
    )

    assert out["stage"] == "analysis_ready"
    assert out["ranking_count"] == 200
    assert out["aggregate"] is aggregate


def test_build_done_report_status_projects_current_artifact_paths() -> None:
    out = build_done_report_status(
        report_id="top200_2025_20260712T170000Z",
        ranking_path=Path("/tmp/ranking.json"),
        segments_path=Path("/tmp/segments.json"),
        attribution_path=Path("/tmp/attribution.json"),
        report_path=Path("/tmp/report.md"),
    )

    assert out == {
        "stage": "done",
        "report_id": "top200_2025_20260712T170000Z",
        "ranking_path": "/tmp/ranking.json",
        "segments_path": "/tmp/segments.json",
        "attribution_path": "/tmp/attribution.json",
        "report_path": "/tmp/report.md",
    }
