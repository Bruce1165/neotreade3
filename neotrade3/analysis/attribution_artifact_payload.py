"""Artifact payload helpers for lowfreq attribution report consumers."""

from __future__ import annotations

from typing import Any


def build_attribution_artifact_payload(
    *,
    report_id: str,
    generated_at: str,
    year: int,
    limit: int,
    analysis_mode: str | None = None,
    aggregate: dict[str, Any],
    items: list[dict[str, Any]],
) -> dict[str, Any]:
    meta = {
        "status": "ok",
        "report_id": str(report_id or ""),
        "generated_at": str(generated_at or ""),
        "year": int(year),
        "limit": int(limit),
    }
    mode = str(analysis_mode or "").strip()
    if mode:
        meta["analysis_mode"] = mode
    return {
        "_meta": {
            **meta,
        },
        "aggregate": aggregate,
        "items": items,
    }
