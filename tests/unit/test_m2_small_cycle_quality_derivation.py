from __future__ import annotations

from neotrade3.cycle_intelligence import build_small_cycle
from neotrade3.cycle_intelligence.contracts import (
    SMALL_CYCLE_QUALITY_REASON_INSUFFICIENT_EVIDENCE,
    SMALL_CYCLE_QUALITY_REASON_PF1_WINDOW_NOT_READY,
    SMALL_CYCLE_QUALITY_REASON_PRICE_AND_CONTINUITY_BROKEN,
    SMALL_CYCLE_QUALITY_REASON_SECURITY_DELISTED,
)


def test_build_small_cycle_derives_ok_quality_when_not_triggered() -> None:
    cycle = build_small_cycle(
        stock_code="600000",
        trade_date="2026-07-07",
        cycle_state="S2 Advancing",
        state_stability_level="stable",
        invalidation={"status": "not_triggered", "reasons": []},
    )
    payload = cycle.to_payload()
    assert payload["quality_status"] == "ok"
    assert payload["quality_reasons"] == []


def test_build_small_cycle_derives_blocked_quality_when_triggered_without_structure_break() -> None:
    cycle = build_small_cycle(
        stock_code="600000",
        trade_date="2026-07-07",
        cycle_state="S0 Neutral",
        state_stability_level="not_ready",
        invalidation={
            "status": "triggered",
            "reasons": [SMALL_CYCLE_QUALITY_REASON_PF1_WINDOW_NOT_READY],
        },
    )
    payload = cycle.to_payload()
    assert payload["quality_status"] == "blocked"
    assert payload["quality_reasons"] == [SMALL_CYCLE_QUALITY_REASON_PF1_WINDOW_NOT_READY]


def test_build_small_cycle_passes_through_blocked_reasons_in_order() -> None:
    invalidation_reasons = [
        SMALL_CYCLE_QUALITY_REASON_SECURITY_DELISTED,
        SMALL_CYCLE_QUALITY_REASON_PF1_WINDOW_NOT_READY,
    ]
    cycle = build_small_cycle(
        stock_code="600000",
        trade_date="2026-07-07",
        cycle_state="S0 Neutral",
        state_stability_level="not_ready",
        invalidation={
            "status": "triggered",
            "reasons": invalidation_reasons,
        },
    )
    payload = cycle.to_payload()
    assert payload["quality_status"] == "blocked"
    assert payload["quality_reasons"] == invalidation_reasons


def test_build_small_cycle_derives_invalidated_quality_when_structure_break_triggered() -> None:
    cycle = build_small_cycle(
        stock_code="600000",
        trade_date="2026-07-07",
        cycle_state="S4 Exhausting_or_Invalidated",
        state_stability_level="invalidated",
        invalidation={
            "status": "triggered",
            "reasons": [SMALL_CYCLE_QUALITY_REASON_PRICE_AND_CONTINUITY_BROKEN],
        },
    )
    payload = cycle.to_payload()
    assert payload["quality_status"] == "invalidated"
    assert payload["quality_reasons"] == [SMALL_CYCLE_QUALITY_REASON_PRICE_AND_CONTINUITY_BROKEN]


def test_build_small_cycle_derives_insufficient_evidence_when_state_flagged() -> None:
    cycle = build_small_cycle(
        stock_code="600000",
        trade_date="2026-07-07",
        cycle_state="S0 Neutral",
        state_stability_level="insufficient_evidence",
        invalidation={"status": "not_triggered", "reasons": []},
    )
    payload = cycle.to_payload()
    assert payload["quality_status"] == "insufficient_evidence"
    assert payload["quality_reasons"] == [SMALL_CYCLE_QUALITY_REASON_INSUFFICIENT_EVIDENCE]


def test_build_small_cycle_invalidation_takes_precedence_over_insufficient_evidence() -> None:
    cycle = build_small_cycle(
        stock_code="600000",
        trade_date="2026-07-07",
        cycle_state="S4 Exhausting_or_Invalidated",
        state_stability_level="insufficient_evidence",
        invalidation={
            "status": "triggered",
            "reasons": [SMALL_CYCLE_QUALITY_REASON_PRICE_AND_CONTINUITY_BROKEN],
        },
    )
    payload = cycle.to_payload()
    assert payload["quality_status"] == "invalidated"
    assert payload["quality_reasons"] == [SMALL_CYCLE_QUALITY_REASON_PRICE_AND_CONTINUITY_BROKEN]


def test_build_small_cycle_explicit_quality_overrides_invalidation_and_state_flags() -> None:
    explicit_reasons = [
        SMALL_CYCLE_QUALITY_REASON_SECURITY_DELISTED,
        SMALL_CYCLE_QUALITY_REASON_PF1_WINDOW_NOT_READY,
    ]
    cycle = build_small_cycle(
        stock_code="600000",
        trade_date="2026-07-07",
        cycle_state="S0 Neutral",
        state_stability_level="insufficient_evidence",
        quality_status="blocked",
        quality_reasons=explicit_reasons,
        invalidation={
            "status": "triggered",
            "reasons": [SMALL_CYCLE_QUALITY_REASON_PRICE_AND_CONTINUITY_BROKEN],
        },
    )
    payload = cycle.to_payload()
    assert payload["quality_status"] == "blocked"
    assert payload["quality_reasons"] == explicit_reasons
