"""CLI success summary helpers for lowfreq report-runner consumers."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def build_lowfreq_report_success_summary(
    *,
    report_id: str,
    output_dir: Path,
    ranking_path: Path,
    segments_path: Path,
    attribution_path: Path,
    report_path: Path,
    aggregate: dict[str, Any],
) -> dict[str, Any]:
    return {
        "status": "ok",
        "report_id": str(report_id or ""),
        "output_dir": str(output_dir),
        "ranking_path": str(ranking_path),
        "segments_path": str(segments_path),
        "attribution_path": str(attribution_path),
        "report_path": str(report_path),
        "aggregate": aggregate,
    }
