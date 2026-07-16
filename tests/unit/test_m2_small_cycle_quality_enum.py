from __future__ import annotations

import pytest

from neotrade3.cycle_intelligence import SmallCycle


def _payload(*, object_version: int = 2) -> dict[str, object]:
    return {
        "object_type": "small_cycle",
        "object_version": object_version,
        "stock_code": "600000",
        "trade_date": "2026-07-07",
        "cycle_state": "S2 Advancing",
        "state_stability_level": "stable",
        "quality_status": "ok",
        "quality_reasons": [],
        "evidence_bundle": {},
        "confidence": {},
        "invalidation": {"status": "not_triggered"},
        "state_transition_log": [],
        "input_data_version": "m1_phase1.v1",
        "rule_version": "m2_small_cycle.v1alpha1",
    }


def test_small_cycle_from_dict_rejects_v1_payload() -> None:
    with pytest.raises(ValueError, match="object_version"):
        SmallCycle.from_dict(_payload(object_version=1))


def test_small_cycle_from_dict_rejects_unknown_quality_status() -> None:
    payload = _payload()
    payload["quality_status"] = "unknown"
    payload["quality_reasons"] = ["pf1_window_not_ready"]
    with pytest.raises(ValueError, match="quality_status"):
        SmallCycle.from_dict(payload)


def test_small_cycle_from_dict_rejects_non_ok_without_reasons() -> None:
    payload = _payload()
    payload["quality_status"] = "blocked"
    payload["quality_reasons"] = []
    with pytest.raises(ValueError, match="quality_reasons"):
        SmallCycle.from_dict(payload)


def test_small_cycle_from_dict_rejects_unknown_quality_reason() -> None:
    payload = _payload()
    payload["quality_status"] = "blocked"
    payload["quality_reasons"] = ["unknown_reason"]
    with pytest.raises(ValueError, match="quality_reasons"):
        SmallCycle.from_dict(payload)
