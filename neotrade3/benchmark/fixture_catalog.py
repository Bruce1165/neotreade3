"""Formal fixture catalog for NeoTrade3 M4 benchmark validation seed."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from neotrade3.cycle_intelligence import (
    SmallCycle,
    build_cycle_linkage_state,
    build_growth_potential_profile_from_formal_inputs,
    build_mid_cycle_states_from_m1,
    build_shadow_cycle_intelligence_from_m1,
    build_small_cycle_from_m1,
    build_small_cycle_wave_hypothesis_from_formal_inputs,
    build_top_risk_profile_from_formal_inputs,
)
from neotrade3.data_control import (
    D1DailyPriceFact,
    D7SecurityMasterMinimal,
    D7TradingDayStatus,
    PF1TradingProfile,
)
from neotrade3.decision_engine import (
    build_entry_state_from_formal_inputs,
    build_identify_state_from_formal_inputs,
    build_m1_constraints_ref,
    build_tracking_state_from_formal_inputs,
)
from .sample_registry import BenchmarkSeedSampleRegistration


@dataclass(frozen=True)
class BenchmarkFixtureBundle:
    cycle: SmallCycle
    shadow_bundle: dict[str, Any]
    m1_context: dict[str, Any] = field(default_factory=dict)
    m3_context: dict[str, Any] = field(default_factory=dict)

    def to_runtime_payload(self) -> dict[str, Any]:
        return {
            "cycle": self.cycle,
            "shadow_bundle": dict(self.shadow_bundle),
            "m1_context": dict(self.m1_context),
            "m3_context": dict(self.m3_context),
        }


def _sample_m1_objects(
    *,
    return_20d: float = 0.12,
    positive_days_5d: int = 4,
) -> tuple[
    D1DailyPriceFact,
    D7SecurityMasterMinimal,
    D7TradingDayStatus,
    PF1TradingProfile,
]:
    d1 = D1DailyPriceFact(
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
    security = D7SecurityMasterMinimal(
        stock_code="600000",
        stock_name="浦发银行",
        asset_type="stock",
        is_delisted=False,
        sector_lv1="金融",
        sector_lv2="银行",
        last_trade_date="2026-07-07",
    )
    trading_day = D7TradingDayStatus(
        target_date="2026-07-07",
        is_trading_day=True,
        nearest_trading_day="2026-07-07",
        min_trading_day="2026-06-01",
        max_trading_day="2026-07-07",
        calendar_covered_until="2026-07-07",
        calendar_source="trading_calendar_cache",
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
        return_20d=return_20d,
        avg_pct_change_5d=0.8,
        positive_days_5d=positive_days_5d,
        window_5d_ready=True,
        window_20d_ready=True,
    )
    return d1, security, trading_day, profile


def _build_front_m3_context(
    *,
    cycle: SmallCycle,
    d1_fact: D1DailyPriceFact,
    security_master: D7SecurityMasterMinimal,
    trading_day_status: D7TradingDayStatus,
    trading_profile: PF1TradingProfile,
) -> dict[str, Any]:
    constraints = build_m1_constraints_ref(
        d1_fact=d1_fact,
        security_master=security_master,
        trading_day_status=trading_day_status,
        trading_profile=trading_profile,
    )
    identify_state = build_identify_state_from_formal_inputs(
        cycle=cycle,
        m1_constraints_ref=constraints,
    )
    tracking_state = build_tracking_state_from_formal_inputs(
        cycle=cycle,
        m1_constraints_ref=constraints,
    )
    entry_state = build_entry_state_from_formal_inputs(
        cycle=cycle,
        m1_constraints_ref=constraints,
    )
    return {
        "m1_constraints_ref": dict(constraints),
        "identify_state": identify_state.to_payload(),
        "tracking_state": tracking_state.to_payload(),
        "entry_state": entry_state.to_payload(),
    }


def _build_reference_cycle_and_shadow_bundle() -> BenchmarkFixtureBundle:
    d1, security, trading_day, profile = _sample_m1_objects()
    cycle = build_small_cycle_from_m1(
        d1_fact=d1,
        security_master=security,
        trading_day_status=trading_day,
        trading_profile=profile,
    )
    shadow_bundle = build_shadow_cycle_intelligence_from_m1(
        cycle=cycle,
        security_master=security,
        trading_profile=profile,
    )
    m1_context = {
        "d1_fact": {
            "stock_code": d1.stock_code,
            "trade_date": d1.trade_date,
            "pct_change": d1.pct_change,
        },
        "security_master": {
            "sector_lv1": security.sector_lv1,
            "sector_lv2": security.sector_lv2,
        },
        "trading_profile": {
            "return_20d": profile.return_20d,
            "positive_days_5d": profile.positive_days_5d,
        },
    }
    m3_context = _build_front_m3_context(
        cycle=cycle,
        d1_fact=d1,
        security_master=security,
        trading_day_status=trading_day,
        trading_profile=profile,
    )
    return BenchmarkFixtureBundle(
        cycle=cycle,
        shadow_bundle=shadow_bundle,
        m1_context=m1_context,
        m3_context=m3_context,
    )


def _build_advancing_reference_fixture() -> BenchmarkFixtureBundle:
    return _build_reference_cycle_and_shadow_bundle()


def _build_target_opportunity_reference_fixture() -> BenchmarkFixtureBundle:
    return _build_reference_cycle_and_shadow_bundle()


def _build_control_failure_reference_fixture() -> BenchmarkFixtureBundle:
    reference = _build_reference_cycle_and_shadow_bundle()
    linkage = reference.shadow_bundle["cycle_linkage_state"]
    bad_linkage = build_cycle_linkage_state(
        stock_code=reference.cycle.stock_code,
        trade_date=reference.cycle.trade_date,
        small_cycle_ref={
            "object_type": reference.cycle.object_type,
            "stock_code": reference.cycle.stock_code,
            "cycle_state": reference.cycle.cycle_state,
        },
        mid_cycle_ref={
            "fund_cycle_state": linkage.mid_cycle_ref["fund_cycle_state"],
            "industry_cycle_state": linkage.mid_cycle_ref["industry_cycle_state"],
        },
        linkage_phase="continuation_blocked",
        supports_continuation=False,
        local_end_vs_global_end="local_end_only",
        confidence={"level": "medium"},
        evidence_bundle={"override": "fixture_catalog_control_failure_seed"},
        rule_version="m2_cycle_linkage.v1alpha1",
    )
    return BenchmarkFixtureBundle(
        cycle=reference.cycle,
        shadow_bundle={
            **reference.shadow_bundle,
            "cycle_linkage_state": bad_linkage,
        },
        m1_context=reference.m1_context,
        m3_context=reference.m3_context,
    )


def _build_local_global_guardrail_fixture() -> BenchmarkFixtureBundle:
    reference = _build_reference_cycle_and_shadow_bundle()
    _, security, _, profile = _sample_m1_objects()
    mid_cycles = build_mid_cycle_states_from_m1(
        cycle=reference.cycle,
        security_master=security,
        trading_profile=profile,
    )
    bad_linkage = build_cycle_linkage_state(
        stock_code=reference.cycle.stock_code,
        trade_date=reference.cycle.trade_date,
        small_cycle_ref={
            "object_type": reference.cycle.object_type,
            "stock_code": reference.cycle.stock_code,
            "cycle_state": reference.cycle.cycle_state,
        },
        mid_cycle_ref={
            "fund_cycle_state": mid_cycles["fund_cycle"].to_payload()["state"],
            "industry_cycle_state": mid_cycles["industry_cycle"].to_payload()["state"],
        },
        linkage_phase="possible_global_transition",
        supports_continuation=False,
        local_end_vs_global_end="possible_global_end",
        confidence={"level": "low"},
        evidence_bundle={"override": "fixture_catalog_guardrail_seed"},
        rule_version="m2_cycle_linkage.v1alpha1",
    )
    return BenchmarkFixtureBundle(
        cycle=reference.cycle,
        shadow_bundle={
            "wave_hypothesis": build_small_cycle_wave_hypothesis_from_formal_inputs(
                cycle=reference.cycle
            ),
            "mid_cycle_states": mid_cycles,
            "cycle_linkage_state": bad_linkage,
            "growth_potential_profile": build_growth_potential_profile_from_formal_inputs(
                cycle=reference.cycle,
                fund_cycle_state=mid_cycles["fund_cycle"],
                industry_cycle_state=mid_cycles["industry_cycle"],
            ),
            "top_risk_profile": build_top_risk_profile_from_formal_inputs(
                cycle=reference.cycle,
                fund_cycle_state=mid_cycles["fund_cycle"],
                industry_cycle_state=mid_cycles["industry_cycle"],
            ),
        },
        m1_context=reference.m1_context,
        m3_context=reference.m3_context,
    )


@dataclass(frozen=True)
class BenchmarkFixtureCatalog:
    builders: dict[str, Callable[[], BenchmarkFixtureBundle]] = field(default_factory=dict)

    def build(self, fixture_id: str) -> BenchmarkFixtureBundle:
        builder = self.builders.get(fixture_id)
        if builder is None:
            raise KeyError(f"unknown benchmark fixture_id: {fixture_id}")
        return builder()


def build_default_benchmark_fixture_catalog() -> BenchmarkFixtureCatalog:
    return BenchmarkFixtureCatalog(
        builders={
            "m2_target_opportunity_reference": _build_target_opportunity_reference_fixture,
            "m2_control_failure_reference": _build_control_failure_reference_fixture,
            "m2_advancing_reference": _build_advancing_reference_fixture,
            "m2_local_global_guardrail_reference": _build_local_global_guardrail_fixture,
        }
    )


def build_benchmark_fixture_bundle(
    registration: BenchmarkSeedSampleRegistration,
    *,
    catalog: BenchmarkFixtureCatalog | None = None,
) -> dict[str, Any]:
    active_catalog = catalog or build_default_benchmark_fixture_catalog()
    fixture = active_catalog.build(registration.fixture_id)
    return fixture.to_runtime_payload()
