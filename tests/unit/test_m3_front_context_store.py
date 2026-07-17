from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from neotrade3.cycle_intelligence import (
    ShadowCycleIntelligenceBundle,
    build_shadow_cycle_intelligence_from_m1,
    build_small_cycle,
)
from neotrade3.data_control import D1DailyPriceFact, D7SecurityMasterMinimal, D7TradingDayStatus, PF1TradingProfile
from neotrade3.decision_engine import (
    DecisionM3FrontContext,
    build_decision_m3_front_context_record_id,
    build_entry_state_from_formal_inputs,
    build_identify_state_from_formal_inputs,
    build_m1_constraints_ref,
    build_tracking_state_from_formal_inputs,
    materialize_decision_m3_front_context,
    list_decision_m3_front_context_ledgers,
    read_decision_m3_front_context,
    read_decision_m3_front_context_artifact,
    read_decision_m3_front_context_ledger,
)


def _build_front_context() -> DecisionM3FrontContext:
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
    trading_day_status = D7TradingDayStatus(
        target_date="2026-07-07",
        is_trading_day=True,
        nearest_trading_day="2026-07-07",
        min_trading_day="2026-06-01",
        max_trading_day="2026-07-07",
        calendar_covered_until="2026-07-07",
        calendar_source="trading_calendar_cache",
    )
    d1_fact = D1DailyPriceFact(
        stock_code="600000",
        trade_date="2026-07-07",
        open_price=10.0,
        high_price=10.5,
        low_price=9.9,
        close_price=10.3,
        preclose_price=10.0,
        pct_change=2.0,
        volume_shares=1_000_000.0,
        amount_cny=200_000_000.0,
        turnover_rate=3.0,
        updated_at="2026-07-07T15:00:00Z",
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
    shadow_bundle = ShadowCycleIntelligenceBundle.from_bundle(
        build_shadow_cycle_intelligence_from_m1(
            cycle=cycle,
            security_master=security,
            trading_profile=profile,
        )
    )
    cycle_linkage_state_ref = shadow_bundle.to_replay_payload()["cycle_linkage_state"]
    constraints = build_m1_constraints_ref(
        d1_fact=d1_fact,
        security_master=security,
        trading_day_status=trading_day_status,
        trading_profile=profile,
    )
    run_id = "run-001"
    source_run_id = "source-001"
    return DecisionM3FrontContext(
        run_id=run_id,
        source_run_id=source_run_id,
        m1_constraints_ref=dict(constraints),
        identify_state=build_identify_state_from_formal_inputs(
            cycle=cycle,
            run_id=run_id,
            source_run_id=source_run_id,
            m1_constraints_ref=constraints,
            cycle_linkage_state_ref=cycle_linkage_state_ref,
        ).to_payload(),
        tracking_state=build_tracking_state_from_formal_inputs(
            cycle=cycle,
            run_id=run_id,
            source_run_id=source_run_id,
            m1_constraints_ref=constraints,
            cycle_linkage_state_ref=cycle_linkage_state_ref,
        ).to_payload(),
        entry_state=build_entry_state_from_formal_inputs(
            cycle=cycle,
            run_id=run_id,
            source_run_id=source_run_id,
            m1_constraints_ref=constraints,
            cycle_linkage_state_ref=cycle_linkage_state_ref,
        ).to_payload(),
    )


def test_materialize_decision_m3_front_context(tmp_path: Path) -> None:
    front_context = _build_front_context()
    record_id = build_decision_m3_front_context_record_id(
        stock_code="600000",
        trade_date="2026-07-07",
    )

    ledger_record = materialize_decision_m3_front_context(
        project_root=tmp_path,
        record_id=record_id,
        front_context=front_context,
    )
    artifact_payload = read_decision_m3_front_context_artifact(
        project_root=tmp_path,
        record_id=record_id,
    )
    reconstructed = read_decision_m3_front_context(
        project_root=tmp_path,
        record_id=record_id,
    )
    reconstructed_ledger = read_decision_m3_front_context_ledger(
        project_root=tmp_path,
        record_id=record_id,
    )

    assert ledger_record.record_id == record_id
    assert ledger_record.stock_code == "600000"
    assert ledger_record.trade_date == "2026-07-07"
    assert ledger_record.run_id == "run-001"
    assert ledger_record.source_run_id == "source-001"
    assert ledger_record.identify_status == front_context.identify_state["status"]
    assert ledger_record.tracking_status == front_context.tracking_state["status"]
    assert ledger_record.entry_status == front_context.entry_state["status"]
    assert ledger_record.entry_decision == front_context.entry_state["decision"]
    assert ledger_record.entry_actionable == front_context.entry_state["actionable"]
    assert ledger_record.entry_blocking_reasons == front_context.entry_state["blocking_reasons"]
    assert ledger_record.m1_blocked == front_context.m1_constraints_ref["blocked"]
    assert ledger_record.m1_blocking_reasons == front_context.m1_constraints_ref["blocking_reasons"]
    assert ledger_record.m2_cycle_record_id == "600000-2026-07-07"
    assert ledger_record.m2_cycle_state
    assert ledger_record.m2_state_stability_level
    assert artifact_payload is not None
    assert artifact_payload["identify_state"]["object_type"] == "identify_state"
    assert reconstructed == front_context
    assert reconstructed_ledger == ledger_record

    artifact_file = _artifact_file(project_root=tmp_path, record_id=record_id)
    artifact_text = artifact_file.read_text(encoding="utf-8")
    assert ledger_record.artifact_sha256 == hashlib.sha256(
        artifact_text.encode("utf-8")
    ).hexdigest()


def _artifact_file(*, project_root: Path, record_id: str) -> Path:
    return (
        project_root
        / "var/artifacts/m3_front_contexts"
        / record_id
        / "front_context.json"
    )


def _ledger_file(*, project_root: Path, record_id: str) -> Path:
    return (
        project_root
        / "var/ledgers/m3_front_contexts"
        / record_id
        / "front_context.json"
    )


def test_read_decision_m3_front_context_artifact_fail_closed_on_invalid_json(
    tmp_path: Path,
) -> None:
    record_id = "600000-2026-07-07"
    artifact_file = _artifact_file(project_root=tmp_path, record_id=record_id)
    artifact_file.parent.mkdir(parents=True, exist_ok=True)
    artifact_file.write_text("{", encoding="utf-8")

    with pytest.raises(ValueError):
        read_decision_m3_front_context_artifact(project_root=tmp_path, record_id=record_id)


def test_read_decision_m3_front_context_artifact_fail_closed_on_non_object_json(
    tmp_path: Path,
) -> None:
    record_id = "600000-2026-07-07"
    artifact_file = _artifact_file(project_root=tmp_path, record_id=record_id)
    artifact_file.parent.mkdir(parents=True, exist_ok=True)
    artifact_file.write_text("[]", encoding="utf-8")

    with pytest.raises(TypeError):
        read_decision_m3_front_context_artifact(project_root=tmp_path, record_id=record_id)


def test_read_decision_m3_front_context_fail_closed_on_contract_mismatch(
    tmp_path: Path,
) -> None:
    record_id = "600000-2026-07-07"
    artifact_file = _artifact_file(project_root=tmp_path, record_id=record_id)
    artifact_file.parent.mkdir(parents=True, exist_ok=True)
    artifact_file.write_text(
        json.dumps(
            {
                "object_type": "wrong_type",
                "object_version": 2,
                "record_id": record_id,
                "written_at": "2026-07-07T00:00:00Z",
                "run_id": "run-001",
                "source_run_id": "source-001",
                "m1_constraints_ref": {},
                "identify_state": {},
                "tracking_state": {},
                "entry_state": {},
            },
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        read_decision_m3_front_context(project_root=tmp_path, record_id=record_id)


def test_read_decision_m3_front_context_fail_closed_on_missing_object_type(
    tmp_path: Path,
) -> None:
    record_id = "600000-2026-07-07"
    artifact_file = _artifact_file(project_root=tmp_path, record_id=record_id)
    artifact_file.parent.mkdir(parents=True, exist_ok=True)
    artifact_file.write_text(
        json.dumps(
            {
                "object_version": 2,
                "record_id": record_id,
                "written_at": "2026-07-07T00:00:00Z",
                "run_id": "run-001",
                "source_run_id": "source-001",
                "m1_constraints_ref": {},
                "identify_state": {},
                "tracking_state": {},
                "entry_state": {},
            },
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        read_decision_m3_front_context(project_root=tmp_path, record_id=record_id)


def test_read_decision_m3_front_context_fail_closed_on_missing_object_version(
    tmp_path: Path,
) -> None:
    record_id = "600000-2026-07-07"
    artifact_file = _artifact_file(project_root=tmp_path, record_id=record_id)
    artifact_file.parent.mkdir(parents=True, exist_ok=True)
    artifact_file.write_text(
        json.dumps(
            {
                "object_type": "m3_front_context",
                "record_id": record_id,
                "written_at": "2026-07-07T00:00:00Z",
                "run_id": "run-001",
                "source_run_id": "source-001",
                "m1_constraints_ref": {},
                "identify_state": {},
                "tracking_state": {},
                "entry_state": {},
            },
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        read_decision_m3_front_context(project_root=tmp_path, record_id=record_id)


def test_read_decision_m3_front_context_fail_closed_on_v1_payload(
    tmp_path: Path,
) -> None:
    record_id = "600000-2026-07-07"
    artifact_file = _artifact_file(project_root=tmp_path, record_id=record_id)
    artifact_file.parent.mkdir(parents=True, exist_ok=True)
    artifact_file.write_text(
        json.dumps(
            {
                "object_type": "m3_front_context",
                "object_version": 1,
                "record_id": record_id,
                "written_at": "2026-07-07T00:00:00Z",
                "run_id": "run-001",
                "source_run_id": "source-001",
                "m1_constraints_ref": {},
                "identify_state": {},
                "tracking_state": {},
                "entry_state": {},
            },
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        read_decision_m3_front_context(project_root=tmp_path, record_id=record_id)


def test_read_decision_m3_front_context_fail_closed_on_unknown_fields(
    tmp_path: Path,
) -> None:
    record_id = "600000-2026-07-07"
    artifact_file = _artifact_file(project_root=tmp_path, record_id=record_id)
    artifact_file.parent.mkdir(parents=True, exist_ok=True)
    artifact_file.write_text(
        json.dumps(
            {
                "object_type": "m3_front_context",
                "object_version": 2,
                "record_id": record_id,
                "written_at": "2026-07-07T00:00:00Z",
                "run_id": "run-001",
                "source_run_id": "source-001",
                "m1_constraints_ref": {},
                "identify_state": {},
                "tracking_state": {},
                "entry_state": {},
                "extra": 1,
            },
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        read_decision_m3_front_context(project_root=tmp_path, record_id=record_id)


def test_read_decision_m3_front_context_ledger_fail_closed_on_invalid_json(
    tmp_path: Path,
) -> None:
    record_id = "600000-2026-07-07"
    ledger_file = _ledger_file(project_root=tmp_path, record_id=record_id)
    ledger_file.parent.mkdir(parents=True, exist_ok=True)
    ledger_file.write_text("{", encoding="utf-8")

    with pytest.raises(ValueError):
        read_decision_m3_front_context_ledger(project_root=tmp_path, record_id=record_id)


def test_read_decision_m3_front_context_ledger_fail_closed_on_non_object_json(
    tmp_path: Path,
) -> None:
    record_id = "600000-2026-07-07"
    ledger_file = _ledger_file(project_root=tmp_path, record_id=record_id)
    ledger_file.parent.mkdir(parents=True, exist_ok=True)
    ledger_file.write_text("[]", encoding="utf-8")

    with pytest.raises(TypeError):
        read_decision_m3_front_context_ledger(project_root=tmp_path, record_id=record_id)


def test_read_decision_m3_front_context_ledger_fail_closed_on_missing_fields(
    tmp_path: Path,
) -> None:
    record_id = "600000-2026-07-07"
    ledger_file = _ledger_file(project_root=tmp_path, record_id=record_id)
    ledger_file.parent.mkdir(parents=True, exist_ok=True)
    ledger_file.write_text(
        json.dumps(
            {
                "written_at": "2026-07-07T00:00:00Z",
                "artifact_path": "var/artifacts/m3_front_contexts/x/front_context.json",
                "ledger_path": "var/ledgers/m3_front_contexts/x/front_context.json",
            },
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        read_decision_m3_front_context_ledger(project_root=tmp_path, record_id=record_id)


def test_list_decision_m3_front_context_ledgers_orders_and_limits(
    tmp_path: Path,
) -> None:
    payload_a = {
        "record_id": "600000-2026-07-06",
        "written_at": "2026-07-06T00:00:00Z",
        "artifact_path": "var/artifacts/m3_front_contexts/600000-2026-07-06/front_context.json",
        "ledger_path": "var/ledgers/m3_front_contexts/600000-2026-07-06/front_context.json",
    }
    payload_b = {
        "record_id": "600000-2026-07-07",
        "written_at": "2026-07-07T00:00:00Z",
        "artifact_path": "var/artifacts/m3_front_contexts/600000-2026-07-07/front_context.json",
        "ledger_path": "var/ledgers/m3_front_contexts/600000-2026-07-07/front_context.json",
    }

    file_a = _ledger_file(project_root=tmp_path, record_id=payload_a["record_id"])
    file_a.parent.mkdir(parents=True, exist_ok=True)
    file_a.write_text(
        json.dumps(payload_a, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    file_b = _ledger_file(project_root=tmp_path, record_id=payload_b["record_id"])
    file_b.parent.mkdir(parents=True, exist_ok=True)
    file_b.write_text(
        json.dumps(payload_b, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    records = list_decision_m3_front_context_ledgers(project_root=tmp_path, limit=10)
    assert [item.record_id for item in records] == [
        "600000-2026-07-07",
        "600000-2026-07-06",
    ]

    limited = list_decision_m3_front_context_ledgers(project_root=tmp_path, limit=1)
    assert [item.record_id for item in limited] == ["600000-2026-07-07"]


def test_list_decision_m3_front_context_ledgers_fail_closed_on_invalid_json(
    tmp_path: Path,
) -> None:
    ledger_file = _ledger_file(project_root=tmp_path, record_id="600000-2026-07-07")
    ledger_file.parent.mkdir(parents=True, exist_ok=True)
    ledger_file.write_text("{", encoding="utf-8")

    with pytest.raises(ValueError):
        list_decision_m3_front_context_ledgers(project_root=tmp_path, limit=10)
