from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ChaosWeights:
    version: str
    weights: dict[str, float]


def load_chaos_weights(*, project_root: str | Path, weights_version: str) -> ChaosWeights:
    root = Path(project_root)
    ver = str(weights_version).strip()
    if not ver:
        raise ValueError("weights_version is required")
    suffix = ver
    if ver.startswith("chaos_weights_"):
        suffix = ver[len("chaos_weights_") :]
    p = root / "config" / "chaos" / f"chaos_weights_{suffix}.json"
    payload = json.loads(p.read_text(encoding="utf-8"))
    version = str(payload.get("version") or "").strip() or ver
    weights_raw = payload.get("weights")
    if not isinstance(weights_raw, dict):
        weights_raw = {}
    weights: dict[str, float] = {}
    for k, v in weights_raw.items():
        if not k:
            continue
        if isinstance(v, (int, float)):
            weights[str(k)] = float(v)
    return ChaosWeights(version=version, weights=weights)

