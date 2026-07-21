from __future__ import annotations

from neotrade3.chaos.projection_v1 import ChaosProjectionContext, project_chaos_yin_yang_v1
from neotrade3.chaos.registry import ChaosFactorDefinition, ChaosFactorRegistry


def test_projection_signed_splits_into_yin_yang() -> None:
    registry = ChaosFactorRegistry(
        version="test",
        factors=(
            ChaosFactorDefinition(
                factor_id="pct_change",
                yin_or_yang="signed",
                category="technical",
                normalization="raw",
                default_weight=1.0,
            ),
        ),
    )
    ctx = ChaosProjectionContext(amount_rank=1, amount_universe_size=10, sector_amount_rank=1, sector_count=10)
    out_pos = project_chaos_yin_yang_v1(raw_factors={"pct_change": 2.0}, registry=registry, ctx=ctx)
    assert out_pos["yang_value"] > 0
    assert out_pos["yin_value"] == 0.0
    out_neg = project_chaos_yin_yang_v1(raw_factors={"pct_change": -2.0}, registry=registry, ctx=ctx)
    assert out_neg["yin_value"] > 0
    assert out_neg["yang_value"] == 0.0


def test_projection_rank_percentile_uses_context_rank() -> None:
    registry = ChaosFactorRegistry(
        version="test",
        factors=(
            ChaosFactorDefinition(
                factor_id="amount",
                yin_or_yang="yang",
                category="capital",
                normalization="rank_percentile",
                default_weight=1.0,
            ),
            ChaosFactorDefinition(
                factor_id="amount_rank",
                yin_or_yang="yin",
                category="capital",
                normalization="rank_percentile",
                default_weight=1.0,
            ),
        ),
    )
    ctx_best = ChaosProjectionContext(amount_rank=1, amount_universe_size=100, sector_amount_rank=1, sector_count=10)
    out_best = project_chaos_yin_yang_v1(raw_factors={"amount": 1.0, "amount_rank": 1.0}, registry=registry, ctx=ctx_best)
    assert float(out_best["yang_value"]) > 0
    assert float(out_best["yin_value"]) == 0.0
    ctx_worst = ChaosProjectionContext(amount_rank=100, amount_universe_size=100, sector_amount_rank=1, sector_count=10)
    out_worst = project_chaos_yin_yang_v1(raw_factors={"amount": 1.0, "amount_rank": 100.0}, registry=registry, ctx=ctx_worst)
    assert float(out_worst["yin_value"]) > 0


def test_projection_weights_override_changes_magnitude() -> None:
    registry = ChaosFactorRegistry(
        version="test",
        factors=(
            ChaosFactorDefinition(
                factor_id="pct_change",
                yin_or_yang="signed",
                category="technical",
                normalization="raw",
                default_weight=1.0,
            ),
        ),
    )
    ctx = ChaosProjectionContext(amount_rank=1, amount_universe_size=10, sector_amount_rank=1, sector_count=10)
    out_a = project_chaos_yin_yang_v1(raw_factors={"pct_change": 2.0}, registry=registry, ctx=ctx, weights_override={"pct_change": 1.0})
    out_b = project_chaos_yin_yang_v1(raw_factors={"pct_change": 2.0}, registry=registry, ctx=ctx, weights_override={"pct_change": 2.0})
    assert float(out_b["yang_value"]) > float(out_a["yang_value"])
