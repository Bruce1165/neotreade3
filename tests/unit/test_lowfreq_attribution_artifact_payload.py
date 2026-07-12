from __future__ import annotations

from neotrade3.analysis.attribution_artifact_payload import build_attribution_artifact_payload


def test_build_attribution_artifact_payload_projects_current_meta_envelope() -> None:
    aggregate = {"bought_count": 12}
    items = [{"code": "000001"}]

    out = build_attribution_artifact_payload(
        report_id="top200_2025_20260712T160000Z",
        generated_at="2026-07-12T16:00:00Z",
        year="2025",
        limit="200",
        aggregate=aggregate,
        items=items,
    )

    assert out == {
        "_meta": {
            "status": "ok",
            "report_id": "top200_2025_20260712T160000Z",
            "generated_at": "2026-07-12T16:00:00Z",
            "year": 2025,
            "limit": 200,
        },
        "aggregate": aggregate,
        "items": items,
    }


def test_build_attribution_artifact_payload_passes_through_aggregate_and_items() -> None:
    aggregate = {"candidate_picked_count": 7}
    items = [{"code": "600000", "name": "浦发银行"}]

    out = build_attribution_artifact_payload(
        report_id="r1",
        generated_at="2026-07-12T16:00:00Z",
        year=2025,
        limit=200,
        aggregate=aggregate,
        items=items,
    )

    assert out["aggregate"] is aggregate
    assert out["items"] is items


def test_build_attribution_artifact_payload_keeps_empty_string_fallbacks() -> None:
    out = build_attribution_artifact_payload(
        report_id="",
        generated_at="",
        year=2025,
        limit=200,
        aggregate={},
        items=[],
    )

    assert out["_meta"]["report_id"] == ""
    assert out["_meta"]["generated_at"] == ""
