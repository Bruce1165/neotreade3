"""Run-context helpers for lowfreq report-runner consumers."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def build_lowfreq_report_run_context(
    *,
    project_root: Path,
    year: Any,
    limit: Any,
    report_id: Any,
    timestamp: Any,
) -> dict[str, Any]:
    normalized_year = int(year)
    top_label = f"top{int(limit)}"
    resolved_report_id = str(report_id or f"{top_label}_{normalized_year}_{timestamp}")
    return {
        "top_label": top_label,
        "report_id": resolved_report_id,
        "output_dir": project_root / "var/artifacts" / f"lowfreq_{top_label}_attribution" / resolved_report_id,
    }
