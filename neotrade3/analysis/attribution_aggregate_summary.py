"""Aggregate summary helpers for lowfreq attribution report consumers."""

from __future__ import annotations

from typing import Any


def build_attribution_aggregate_summary(report_rows: list[dict[str, Any]], reason_buckets: dict[str, int]) -> dict[str, Any]:
    return {
        "count": len(report_rows),
        "candidate_picked_count": int(sum(1 for item in report_rows if item.get("candidate_picked"))),
        "entry_picked_count": int(sum(1 for item in report_rows if item.get("entry_picked"))),
        "picked_count": int(sum(1 for item in report_rows if item.get("entry_picked"))),
        "bought_count": int(sum(1 for item in report_rows if item.get("bought"))),
        "held_to_top_count": int(sum(1 for item in report_rows if item.get("held_to_top"))),
        "reason_buckets": dict(reason_buckets),
    }
