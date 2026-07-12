from __future__ import annotations

from pathlib import Path

from neotrade3.orchestration.report_runner_run_context import (
    build_lowfreq_report_run_context,
)


def test_build_lowfreq_report_run_context_projects_current_payload() -> None:
    out = build_lowfreq_report_run_context(
        project_root=Path("/tmp/project"),
        year=2025,
        limit=200,
        report_id="top200_2025_20260712T190000Z",
        timestamp="20260712T190000Z",
    )

    assert out == {
        "top_label": "top200",
        "report_id": "top200_2025_20260712T190000Z",
        "output_dir": Path("/tmp/project/var/artifacts/lowfreq_top200_attribution/top200_2025_20260712T190000Z"),
    }


def test_build_lowfreq_report_run_context_keeps_current_report_id_fallback() -> None:
    out = build_lowfreq_report_run_context(
        project_root=Path("/tmp/project"),
        year="2025",
        limit="50",
        report_id="",
        timestamp="20260712T191500Z",
    )

    assert out == {
        "top_label": "top50",
        "report_id": "top50_2025_20260712T191500Z",
        "output_dir": Path("/tmp/project/var/artifacts/lowfreq_top50_attribution/top50_2025_20260712T191500Z"),
    }


def test_build_lowfreq_report_run_context_keeps_explicit_report_id_override() -> None:
    out = build_lowfreq_report_run_context(
        project_root=Path("/tmp/project"),
        year=2026,
        limit=10,
        report_id="manual_run_id",
        timestamp="ignored",
    )

    assert out["top_label"] == "top10"
    assert out["report_id"] == "manual_run_id"
    assert out["output_dir"] == Path(
        "/tmp/project/var/artifacts/lowfreq_top10_attribution/manual_run_id"
    )
