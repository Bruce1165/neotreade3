"""Artifact path helpers for lowfreq report-runner consumers."""

from __future__ import annotations

from pathlib import Path


def build_lowfreq_report_artifact_paths(
    *,
    output_dir: Path,
    year: int,
    limit: int,
) -> dict[str, str]:
    normalized_year = int(year)
    normalized_limit = int(limit)
    return {
        "ranking_path": str(output_dir / f"top{normalized_limit}_{normalized_year}_ranking.json"),
        "segments_path": str(output_dir / f"top{normalized_limit}_{normalized_year}_wave_segments.json"),
        "attribution_path": str(output_dir / f"top{normalized_limit}_{normalized_year}_model_attribution.json"),
        "report_path": str(output_dir / "report.md"),
    }
