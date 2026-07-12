"""Shared status-file writer for lowfreq report-runner consumers."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def write_lowfreq_report_status(output_dir: Path, *, stage: str, **extra: Any) -> None:
    payload = {
        "stage": str(stage),
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    if extra:
        payload.update(extra)
    (output_dir / "status.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
