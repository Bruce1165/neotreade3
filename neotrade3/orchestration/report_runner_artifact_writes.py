"""Artifact write helpers for lowfreq report-runner consumers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from neotrade3.analysis.attribution_artifact_payload import (
    build_attribution_artifact_payload,
)
from neotrade3.analysis.attribution_markdown_report import (
    build_attribution_markdown_report,
)
from neotrade3.orchestration.report_runner_status import build_done_report_status
from neotrade3.orchestration.report_runner_status_writer import (
    write_lowfreq_report_status,
)


def write_lowfreq_report_artifacts(
    *,
    output_dir: Path,
    report_id: str,
    year: int,
    limit: int,
    ranking_path: Path,
    segments_path: Path,
    attribution_path: Path,
    report_path: Path,
    ranking: list[dict[str, Any]],
    segments: list[dict[str, Any]],
    aggregate: dict[str, Any],
    attribution_rows: list[dict[str, Any]],
    backtest_payload: dict[str, Any],
    generated_at: str,
) -> None:
    ranking_path.write_text(
        json.dumps(ranking, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    segments_path.write_text(
        json.dumps(segments, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    attribution_payload = build_attribution_artifact_payload(
        report_id=report_id,
        generated_at=generated_at,
        year=int(year),
        limit=int(limit),
        aggregate=aggregate,
        items=attribution_rows,
    )
    attribution_path.write_text(
        json.dumps(attribution_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    report_path.write_text(
        build_attribution_markdown_report(
            year=int(year),
            limit=int(limit),
            ranking=ranking,
            aggregate=aggregate,
            attribution_rows=attribution_rows,
            backtest_payload=backtest_payload,
        ),
        encoding="utf-8",
    )
    write_lowfreq_report_status(
        output_dir,
        **build_done_report_status(
            report_id=report_id,
            ranking_path=ranking_path,
            segments_path=segments_path,
            attribution_path=attribution_path,
            report_path=report_path,
        ),
    )
