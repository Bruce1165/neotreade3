from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from neotrade3.chaos.registry import ChaosFactorRegistry


@dataclass(frozen=True)
class ChaosProjectionContext:
    amount_rank: int
    amount_universe_size: int
    sector_amount_rank: int
    sector_count: int


@dataclass(frozen=True)
class ChaosFactorContribution:
    factor_id: str
    mode: str
    category: str
    normalized_value: float
    weight: float
    multiplier: float
    contrib_signed: float


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(float(lo), min(float(hi), float(v)))


def _safe_float(v: Any) -> float | None:
    if isinstance(v, bool):
        return 1.0 if v else 0.0
    if isinstance(v, (int, float)):
        return float(v)
    return None


def _rank_good_percentile(*, rank: int, total: int) -> float:
    r = int(rank)
    n = int(total)
    if n <= 1 or r <= 0:
        return 0.0
    x = 1.0 - float(r - 1) / float(n - 1)
    return _clamp(x, 0.0, 1.0)


def _rank_bad_percentile(*, rank: int, total: int) -> float:
    r = int(rank)
    n = int(total)
    if n <= 1 or r <= 0:
        return 0.0
    x = float(r - 1) / float(n - 1)
    return _clamp(x, 0.0, 1.0)


def _category_multiplier(category: str) -> float:
    c = str(category or "").strip()
    if c == "technical":
        return 0.3
    if c == "capital":
        return 0.4
    if c == "composite":
        return 0.3
    return 0.0


def _normalize_value(
    *,
    factor_id: str,
    normalization: str,
    value: float | None,
    ctx: ChaosProjectionContext,
) -> float | None:
    if value is None:
        return None
    n = str(normalization or "").strip()
    if n == "raw":
        return float(value)
    if n == "binary":
        return 1.0 if float(value) > 0 else 0.0
    if n == "score_0_100":
        return _clamp(float(value) / 100.0, 0.0, 1.0)
    if n == "score_0_5":
        return _clamp(float(value) / 5.0, 0.0, 1.0)
    if n == "score_0_4":
        return _clamp(float(value) / 4.0, 0.0, 1.0)
    if n == "count":
        return _clamp(float(value), 0.0, 10.0) / 10.0
    if n == "log1p":
        return math.log1p(max(0.0, float(value)))
    if n == "rank_percentile":
        fid = str(factor_id or "").strip()
        if fid == "amount":
            return _rank_good_percentile(rank=int(ctx.amount_rank), total=int(ctx.amount_universe_size))
        if fid == "amount_rank":
            return _rank_bad_percentile(rank=int(ctx.amount_rank), total=int(ctx.amount_universe_size))
        if fid == "sector_total_amount_today":
            return _rank_good_percentile(rank=int(ctx.sector_amount_rank), total=int(ctx.sector_count))
        return None
    return float(value)


def compute_factor_contributions_v1(
    *,
    raw_factors: dict[str, Any],
    registry: ChaosFactorRegistry,
    ctx: ChaosProjectionContext,
    weights_override: dict[str, float] | None = None,
) -> list[ChaosFactorContribution]:
    rf = dict(raw_factors or {})
    weights = dict(weights_override or {})
    out: list[ChaosFactorContribution] = []
    for f in registry.factors:
        fid = str(f.factor_id or "").strip()
        if not fid:
            continue
        w = float(weights.get(fid, f.default_weight))
        if w <= 0:
            continue
        m = _category_multiplier(f.category)
        if m <= 0:
            continue
        v0 = _safe_float(rf.get(fid))
        v = _normalize_value(
            factor_id=fid,
            normalization=str(f.normalization),
            value=v0,
            ctx=ctx,
        )
        if v is None:
            continue
        mode = str(f.yin_or_yang or "").strip()
        if mode not in ("yang", "yin", "signed", "neutral"):
            continue
        contrib = float(m) * float(w) * float(v)
        if mode == "neutral":
            contrib_signed = 0.0
        elif mode == "yang":
            contrib_signed = max(0.0, float(contrib))
        elif mode == "yin":
            contrib_signed = -max(0.0, float(contrib))
        else:
            contrib_signed = float(contrib)
        out.append(
            ChaosFactorContribution(
                factor_id=fid,
                mode=mode,
                category=str(f.category),
                normalized_value=float(v),
                weight=float(w),
                multiplier=float(m),
                contrib_signed=float(contrib_signed),
            )
        )
    return out


def project_chaos_yin_yang_v1(
    *,
    raw_factors: dict[str, Any],
    registry: ChaosFactorRegistry,
    ctx: ChaosProjectionContext,
    weights_override: dict[str, float] | None = None,
) -> dict[str, float | str]:
    yang = 0.0
    yin = 0.0
    for c in compute_factor_contributions_v1(
        raw_factors=raw_factors,
        registry=registry,
        ctx=ctx,
        weights_override=weights_override,
    ):
        if c.contrib_signed > 0:
            yang += float(c.contrib_signed)
        elif c.contrib_signed < 0:
            yin += abs(float(c.contrib_signed))
    net = float(yang) - float(yin)
    ratio = f"{int(round(float(yin)))}:{int(round(float(yang)))}"
    return {
        "yin_value": float(yin),
        "yang_value": float(yang),
        "net_energy": float(net),
        "yin_yang_ratio": ratio,
    }
