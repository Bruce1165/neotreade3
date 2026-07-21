from __future__ import annotations

from neotrade3.decision_engine.position_contract_snapshot import build_position_contract_snapshot


def _layer_contract_builder(**kwargs):
    return {
        "current_stage": str(kwargs.get("current_stage") or ""),
        "decision": str(kwargs.get("decision") or ""),
        "source_layer": str(kwargs.get("source_layer") or ""),
    }


def test_position_contract_snapshot_includes_chaos_snapshot() -> None:
    out = build_position_contract_snapshot(
        market_state="",
        sector_state="",
        market_reason="",
        sector_reason="",
        grace_used=False,
        grace_reason="",
        market_snapshot=None,
        sector_snapshot=None,
        trend_snapshot=None,
        sell_payload=None,
        hazard_snapshot=None,
        chaos_snapshot={"yin_value": 1.0, "yang_value": 2.0},
        current_date_key="2026-01-01",
        market_last_hit_date="",
        sector_last_hit_date="",
        grace_date="",
        layer_contract_builder=_layer_contract_builder,
    )
    assert out["chaos_snapshot"]["yin_value"] == 1.0
    assert out["chaos_snapshot"]["yang_value"] == 2.0

