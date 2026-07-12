from __future__ import annotations

import json
import re
from pathlib import Path

from neotrade3.orchestration.report_runner_status_writer import (
    write_lowfreq_report_status,
)


def test_write_lowfreq_report_status_preserves_current_json_shape(tmp_path: Path) -> None:
    output_dir = tmp_path / "artifacts"
    output_dir.mkdir()

    write_lowfreq_report_status(
        output_dir,
        stage="ranking_ready",
        ranking_count=17,
        total_return_pct=None,
    )

    status_path = output_dir / "status.json"
    text = status_path.read_text(encoding="utf-8")

    assert text.endswith("\n")
    payload = json.loads(text)
    assert payload["stage"] == "ranking_ready"
    assert payload["ranking_count"] == 17
    assert payload["total_return_pct"] is None
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", payload["updated_at"])


def test_write_lowfreq_report_status_preserves_done_style_forwarding(tmp_path: Path) -> None:
    output_dir = tmp_path / "artifacts"
    output_dir.mkdir()
    ranking_path = output_dir / "ranking.json"
    segments_path = output_dir / "segments.json"
    attribution_path = output_dir / "attribution.json"
    report_path = output_dir / "report.md"

    write_lowfreq_report_status(
        output_dir,
        stage="done",
        report_id="top200_2025_r1",
        ranking_path=str(ranking_path),
        segments_path=str(segments_path),
        attribution_path=str(attribution_path),
        report_path=str(report_path),
    )

    payload = json.loads((output_dir / "status.json").read_text(encoding="utf-8"))
    assert payload["stage"] == "done"
    assert payload["report_id"] == "top200_2025_r1"
    assert payload["ranking_path"] == str(ranking_path)
    assert payload["segments_path"] == str(segments_path)
    assert payload["attribution_path"] == str(attribution_path)
    assert payload["report_path"] == str(report_path)
