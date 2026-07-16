from __future__ import annotations

import pytest

from neotrade3.decision_engine import (
    build_entry_state,
    build_hold_state,
    build_identify_state,
)


def test_build_identify_state_rejects_invalid_evidence_ref_type() -> None:
    with pytest.raises(TypeError):
        build_identify_state(
            stock_code="600000",
            trade_date="2026-07-07",
            status="identified",
            reason="unit_test",
            evidence_ref="not-a-mapping",
        )


def test_build_entry_state_rejects_invalid_blocking_reasons_type() -> None:
    with pytest.raises(TypeError):
        build_entry_state(
            stock_code="600000",
            trade_date="2026-07-07",
            status="blocked",
            decision="wait",
            actionable=False,
            blocking_reasons="not-a-list",
        )


def test_build_hold_state_rejects_warning_flags_empty_string() -> None:
    with pytest.raises(ValueError):
        build_hold_state(
            stock_code="600000",
            trade_date="2026-07-07",
            status="watch",
            hold_state="review_watch",
            warning_flags=[""],
        )
