from __future__ import annotations

from pathlib import Path

from neotrade3.cycle_intelligence import (
    ShadowCycleIntelligenceBundle,
    build_shadow_cycle_intelligence_bundle_record_id,
    build_shadow_cycle_intelligence_from_m1,
    build_small_cycle,
    materialize_shadow_cycle_intelligence_bundle,
    read_shadow_cycle_intelligence_bundle,
    read_shadow_cycle_intelligence_bundle_artifact,
    read_shadow_cycle_intelligence_bundle_ledger,
)
from neotrade3.data_control import D7SecurityMasterMinimal, PF1TradingProfile


def _build_shadow_bundle() -> ShadowCycleIntelligenceBundle:
    cycle = build_small_cycle(
        stock_code="600000",
        trade_date="2026-07-07",
        cycle_state="S2 Advancing",
        state_stability_level="stable",
        evidence_bundle={"price_structure": {"status": "supported"}},
        confidence={"level": "high"},
        invalidation={"status": "not_triggered"},
        state_transition_log=[{"from": "S1 Emerging", "to": "S2 Advancing"}],
    )
    security = D7SecurityMasterMinimal(
        stock_code="600000",
        stock_name="浦发银行",
        asset_type="stock",
        is_delisted=False,
        sector_lv1="金融",
        sector_lv2="银行",
        last_trade_date="2026-07-07",
    )
    profile = PF1TradingProfile(
        stock_code="600000",
        as_of_trade_date="2026-07-07",
        latest_amount=220_000_000.0,
        avg_amount_5d=210_000_000.0,
        avg_amount_20d=180_000_000.0,
        latest_turnover=3.1,
        avg_turnover_5d=3.0,
        median_turnover_20d=2.2,
        return_20d=0.12,
        avg_pct_change_5d=0.8,
        positive_days_5d=4,
        window_5d_ready=True,
        window_20d_ready=True,
    )
    return ShadowCycleIntelligenceBundle.from_bundle(
        build_shadow_cycle_intelligence_from_m1(
            cycle=cycle,
            security_master=security,
            trading_profile=profile,
        )
    )


def test_materialize_shadow_bundle_writes_artifact_and_ledger(tmp_path: Path) -> None:
    shadow_bundle = _build_shadow_bundle()
    record_id = build_shadow_cycle_intelligence_bundle_record_id(
        stock_code="600000",
        trade_date="2026-07-07",
    )

    ledger_record = materialize_shadow_cycle_intelligence_bundle(
        project_root=tmp_path,
        bundle=shadow_bundle,
    )
    artifact_payload = read_shadow_cycle_intelligence_bundle_artifact(
        project_root=tmp_path,
        record_id=record_id,
    )
    reconstructed = read_shadow_cycle_intelligence_bundle(
        project_root=tmp_path,
        record_id=record_id,
    )
    reconstructed_ledger = read_shadow_cycle_intelligence_bundle_ledger(
        project_root=tmp_path,
        record_id=record_id,
    )

    assert ledger_record.record_id == record_id
    assert artifact_payload is not None
    assert artifact_payload["object_type"] == "m2_shadow_bundle"
    assert artifact_payload["payload"]["wave_hypothesis"]["stock_code"] == "600000"
    assert reconstructed == shadow_bundle
    assert reconstructed_ledger == ledger_record
