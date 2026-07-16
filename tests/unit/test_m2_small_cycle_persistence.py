from __future__ import annotations

from pathlib import Path

from neotrade3.cycle_intelligence import (
    SmallCycle,
    build_small_cycle,
    build_small_cycle_record_id,
    materialize_small_cycle,
    read_small_cycle,
    read_small_cycle_artifact,
    read_small_cycle_ledger,
)


def _build_small_cycle() -> SmallCycle:
    return build_small_cycle(
        stock_code="600000",
        trade_date="2026-07-07",
        cycle_state="S2 Advancing",
        state_stability_level="stable",
        evidence_bundle={"e1_price_structure": {"status": "supported"}},
        confidence={"level": "high"},
        invalidation={"status": "not_triggered"},
        state_transition_log=[],
        input_data_version="m1_phase1.v1",
        rule_version="m2_small_cycle.v1alpha1",
    )


def test_materialize_small_cycle_writes_artifact_and_ledger(tmp_path: Path) -> None:
    small_cycle = _build_small_cycle()
    record_id = build_small_cycle_record_id(small_cycle=small_cycle)

    ledger_record = materialize_small_cycle(
        project_root=tmp_path,
        small_cycle=small_cycle,
    )
    artifact_payload = read_small_cycle_artifact(project_root=tmp_path, record_id=record_id)
    reconstructed = read_small_cycle(project_root=tmp_path, record_id=record_id)
    reconstructed_ledger = read_small_cycle_ledger(
        project_root=tmp_path,
        record_id=record_id,
    )

    assert ledger_record.record_id == record_id
    assert artifact_payload is not None
    assert artifact_payload["cycle_state"] == "S2 Advancing"
    assert reconstructed == small_cycle
    assert reconstructed_ledger == ledger_record
