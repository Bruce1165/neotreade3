from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from neotrade3.orchestration.report_runner_artifact_writes import (
    write_lowfreq_report_artifacts,
)


def test_write_lowfreq_report_artifacts_preserves_current_writes_and_status(tmp_path: Path) -> None:
    output_dir = tmp_path / "artifacts"
    output_dir.mkdir()
    ranking_path = output_dir / "ranking.json"
    segments_path = output_dir / "segments.json"
    attribution_path = output_dir / "attribution.json"
    report_path = output_dir / "report.md"
    order: list[str] = []
    original_write_text = Path.write_text

    def record_write(self: Path, text: str, *, encoding: str | None = None) -> int:
        order.append(self.name)
        return original_write_text(self, text, encoding=encoding)

    attribution_rows = [
        {
            "code": "600000",
            "name": "浦发银行",
            "annual_return_pct": 18.5,
            "segment_start_date": "2025-01-10",
            "segment_top_date": "2025-06-20",
            "primary_reason": "market_filter_blocked",
            "reason_bucket": "market_filter_blocked",
            "candidate_picked": False,
            "entry_picked": False,
            "bought": False,
            "held_to_top": False,
        }
    ]

    with patch.object(Path, "write_text", autospec=True, side_effect=record_write):
        write_lowfreq_report_artifacts(
            output_dir=output_dir,
            report_id="top200_2025_r1",
            year=2025,
            limit=200,
            analysis_mode="seed_only",
            ranking_path=ranking_path,
            segments_path=segments_path,
            attribution_path=attribution_path,
            report_path=report_path,
            ranking=[{"code": "600000", "score": 98.5}],
            segments=[{"code": "600000", "segment": "trend"}],
            aggregate={"bought_count": 3},
            attribution_rows=attribution_rows,
            backtest_payload={"summary": {"total_return_pct": 11.5}, "trades": []},
            generated_at="2026-07-12T12:00:00Z",
        )

    assert order == [
        "ranking.json",
        "segments.json",
        "attribution.json",
        "report.md",
        "status.json",
    ]
    assert ranking_path.read_text(encoding="utf-8").endswith("\n")
    assert segments_path.read_text(encoding="utf-8").endswith("\n")
    assert attribution_path.read_text(encoding="utf-8").endswith("\n")

    attribution_payload = json.loads(attribution_path.read_text(encoding="utf-8"))
    assert attribution_payload["_meta"]["generated_at"] == "2026-07-12T12:00:00Z"
    assert attribution_payload["_meta"]["report_id"] == "top200_2025_r1"
    assert attribution_payload["_meta"]["analysis_mode"] == "seed_only"
    assert report_path.read_text(encoding="utf-8")

    status_payload = json.loads((output_dir / "status.json").read_text(encoding="utf-8"))
    assert status_payload["stage"] == "done"
    assert status_payload["report_id"] == "top200_2025_r1"
    assert status_payload["ranking_path"] == str(ranking_path)
    assert status_payload["segments_path"] == str(segments_path)
    assert status_payload["attribution_path"] == str(attribution_path)
    assert status_payload["report_path"] == str(report_path)
    assert status_payload["updated_at"]
