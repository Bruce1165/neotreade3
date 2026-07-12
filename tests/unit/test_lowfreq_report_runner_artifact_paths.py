from __future__ import annotations

from pathlib import Path

from neotrade3.orchestration.report_runner_artifact_paths import (
    build_lowfreq_report_artifact_paths,
)


def test_build_lowfreq_report_artifact_paths_projects_current_keys() -> None:
    out = build_lowfreq_report_artifact_paths(
        output_dir=Path("/tmp/report-runner"),
        year=2025,
        limit=200,
    )

    assert out == {
        "ranking_path": "/tmp/report-runner/top200_2025_ranking.json",
        "segments_path": "/tmp/report-runner/top200_2025_wave_segments.json",
        "attribution_path": "/tmp/report-runner/top200_2025_model_attribution.json",
        "report_path": "/tmp/report-runner/report.md",
    }


def test_build_lowfreq_report_artifact_paths_keeps_current_int_coercions() -> None:
    out = build_lowfreq_report_artifact_paths(
        output_dir=Path("/tmp/report-runner"),
        year="2025",
        limit="50",
    )

    assert out["ranking_path"].endswith("/top50_2025_ranking.json")
    assert out["segments_path"].endswith("/top50_2025_wave_segments.json")
    assert out["attribution_path"].endswith("/top50_2025_model_attribution.json")


def test_build_lowfreq_report_artifact_paths_keeps_fixed_markdown_name() -> None:
    out = build_lowfreq_report_artifact_paths(
        output_dir=Path("/tmp/report-runner"),
        year=2026,
        limit=10,
    )

    assert out["report_path"] == "/tmp/report-runner/report.md"
