from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ChaosFactorDefinition:
    factor_id: str
    yin_or_yang: str
    category: str
    normalization: str
    default_weight: float


@dataclass(frozen=True)
class ChaosFactorRegistry:
    version: str
    factors: tuple[ChaosFactorDefinition, ...]


def load_chaos_factor_registry(*, project_root: str | Path, registry_id: str = "v0") -> ChaosFactorRegistry:
    root = Path(project_root)
    p = root / "config" / "chaos" / f"chaos_factor_registry_{str(registry_id).strip()}.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    factors_raw = data.get("factors") if isinstance(data, dict) else []
    factors: list[ChaosFactorDefinition] = []
    for item in list(factors_raw or []):
        if not isinstance(item, dict):
            continue
        factors.append(
            ChaosFactorDefinition(
                factor_id=str(item.get("factor_id") or "").strip(),
                yin_or_yang=str(item.get("yin_or_yang") or "").strip(),
                category=str(item.get("category") or "").strip(),
                normalization=str(item.get("normalization") or "").strip(),
                default_weight=float(item.get("default_weight") or 0.0),
            )
        )
    return ChaosFactorRegistry(
        version=str(data.get("version") or "").strip() or f"chaos_registry_{str(registry_id).strip()}",
        factors=tuple(factors),
    )


def registry_to_payload(registry: ChaosFactorRegistry) -> dict:
    return {
        "version": str(registry.version),
        "factors": [
            {
                "factor_id": f.factor_id,
                "yin_or_yang": f.yin_or_yang,
                "category": f.category,
                "normalization": f.normalization,
                "default_weight": float(f.default_weight),
            }
            for f in registry.factors
        ],
    }
