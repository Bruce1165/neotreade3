"""Persisted owner/readback helpers for NeoTrade3 M2 shadow bundles."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping


M2_SHADOW_BUNDLE_OBJECT_TYPE = "m2_shadow_bundle"
M2_SHADOW_BUNDLE_OBJECT_VERSION = 1


def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _copy_mapping(value: Any, *, field_name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{field_name} must be a JSON object")
    return {str(key): item for key, item in value.items()}


def _copy_payload(value: Any, *, field_name: str) -> dict[str, Any]:
    if hasattr(value, "to_payload"):
        payload = value.to_payload()
    else:
        payload = value
    return _copy_mapping(payload, field_name=field_name)


def _copy_mid_cycle_states(value: Any, *, field_name: str) -> dict[str, dict[str, Any]]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{field_name} must be a JSON object")
    copied = {
        str(scope): _copy_payload(state, field_name=f"{field_name}.{scope}")
        for scope, state in value.items()
    }
    if "fund_cycle" not in copied or "industry_cycle" not in copied:
        raise ValueError(
            f"{field_name} must include fund_cycle and industry_cycle entries"
        )
    return copied


@dataclass(frozen=True)
class ShadowCycleIntelligenceBundle:
    wave_hypothesis: dict[str, Any]
    mid_cycle_states: dict[str, dict[str, Any]]
    cycle_linkage_state: dict[str, Any]
    growth_potential_profile: dict[str, Any]
    top_risk_profile: dict[str, Any]
    object_type: str = M2_SHADOW_BUNDLE_OBJECT_TYPE
    object_version: int = M2_SHADOW_BUNDLE_OBJECT_VERSION

    def to_replay_payload(self) -> dict[str, Any]:
        return {
            "wave_hypothesis": _copy_mapping(
                self.wave_hypothesis, field_name="m2_shadow_bundle.wave_hypothesis"
            ),
            "mid_cycle_states": {
                str(scope): _copy_mapping(
                    state,
                    field_name=f"m2_shadow_bundle.mid_cycle_states.{scope}",
                )
                for scope, state in self.mid_cycle_states.items()
            },
            "cycle_linkage_state": _copy_mapping(
                self.cycle_linkage_state,
                field_name="m2_shadow_bundle.cycle_linkage_state",
            ),
            "growth_potential_profile": _copy_mapping(
                self.growth_potential_profile,
                field_name="m2_shadow_bundle.growth_potential_profile",
            ),
            "top_risk_profile": _copy_mapping(
                self.top_risk_profile,
                field_name="m2_shadow_bundle.top_risk_profile",
            ),
        }

    def to_payload(self) -> dict[str, Any]:
        return {
            "object_type": self.object_type,
            "object_version": self.object_version,
            "payload": self.to_replay_payload(),
        }

    @classmethod
    def from_bundle(
        cls,
        bundle: Mapping[str, Any],
    ) -> "ShadowCycleIntelligenceBundle":
        if not isinstance(bundle, Mapping):
            raise TypeError("m2_shadow_bundle payload must be a JSON object")
        return cls(
            wave_hypothesis=_copy_payload(
                bundle.get("wave_hypothesis"),
                field_name="m2_shadow_bundle.wave_hypothesis",
            ),
            mid_cycle_states=_copy_mid_cycle_states(
                bundle.get("mid_cycle_states"),
                field_name="m2_shadow_bundle.mid_cycle_states",
            ),
            cycle_linkage_state=_copy_payload(
                bundle.get("cycle_linkage_state"),
                field_name="m2_shadow_bundle.cycle_linkage_state",
            ),
            growth_potential_profile=_copy_payload(
                bundle.get("growth_potential_profile"),
                field_name="m2_shadow_bundle.growth_potential_profile",
            ),
            top_risk_profile=_copy_payload(
                bundle.get("top_risk_profile"),
                field_name="m2_shadow_bundle.top_risk_profile",
            ),
        )

    @classmethod
    def from_dict(cls, payload: Any) -> "ShadowCycleIntelligenceBundle":
        if not isinstance(payload, Mapping):
            raise TypeError("m2_shadow_bundle must be a JSON object")
        object_type = str(payload.get("object_type") or "").strip()
        if object_type != M2_SHADOW_BUNDLE_OBJECT_TYPE:
            raise ValueError(
                "m2_shadow_bundle.object_type must equal "
                f"{M2_SHADOW_BUNDLE_OBJECT_TYPE}"
            )
        object_version = payload.get("object_version")
        if object_version is None:
            raise ValueError("m2_shadow_bundle.object_version must be provided")
        if int(object_version) != M2_SHADOW_BUNDLE_OBJECT_VERSION:
            raise ValueError(
                "m2_shadow_bundle.object_version must equal "
                f"{M2_SHADOW_BUNDLE_OBJECT_VERSION}"
            )
        nested_payload = payload.get("payload")
        if not isinstance(nested_payload, Mapping):
            raise TypeError("m2_shadow_bundle.payload must be a JSON object")
        bundle = cls.from_bundle(nested_payload)
        return cls(
            wave_hypothesis=bundle.wave_hypothesis,
            mid_cycle_states=bundle.mid_cycle_states,
            cycle_linkage_state=bundle.cycle_linkage_state,
            growth_potential_profile=bundle.growth_potential_profile,
            top_risk_profile=bundle.top_risk_profile,
            object_type=object_type,
            object_version=int(object_version),
        )


def build_shadow_cycle_intelligence_bundle_record_id(
    *,
    stock_code: str,
    trade_date: str,
) -> str:
    normalized_stock_code = str(stock_code or "").strip()
    normalized_trade_date = str(trade_date or "").strip()
    if not normalized_stock_code:
        raise ValueError("stock_code must be non-empty")
    if not normalized_trade_date:
        raise ValueError("trade_date must be non-empty")
    return f"{normalized_stock_code}-{normalized_trade_date}"


@dataclass(frozen=True)
class ShadowCycleIntelligenceBundleArtifactRecord:
    record_id: str
    written_at: str
    artifact_path: str


@dataclass(frozen=True)
class ShadowCycleIntelligenceBundleLedgerRecord:
    record_id: str
    written_at: str
    stock_code: str
    trade_date: str
    artifact_path: str
    ledger_path: str

    @classmethod
    def from_dict(cls, payload: Any) -> "ShadowCycleIntelligenceBundleLedgerRecord":
        if not isinstance(payload, Mapping):
            raise TypeError("m2_shadow_bundle ledger root must be a JSON object")
        return cls(
            record_id=str(payload.get("record_id") or "").strip(),
            written_at=str(payload.get("written_at") or "").strip(),
            stock_code=str(payload.get("stock_code") or "").strip(),
            trade_date=str(payload.get("trade_date") or "").strip(),
            artifact_path=str(payload.get("artifact_path") or "").strip(),
            ledger_path=str(payload.get("ledger_path") or "").strip(),
        )


def _artifact_file(*, project_root: Path, record_id: str) -> Path:
    return project_root / "var/artifacts/m2_shadow_bundles" / record_id / "shadow_bundle.json"


def _ledger_file(*, project_root: Path, record_id: str) -> Path:
    return project_root / "var/ledgers/m2_shadow_bundles" / record_id / "shadow_bundle.json"


def write_shadow_cycle_intelligence_bundle_artifact(
    *,
    project_root: str | Path,
    record_id: str,
    bundle: ShadowCycleIntelligenceBundle,
    dry_run: bool = False,
) -> ShadowCycleIntelligenceBundleArtifactRecord:
    project_root_path = Path(project_root)
    artifact_file = _artifact_file(project_root=project_root_path, record_id=record_id)
    written_at = _now_iso()
    payload = {
        **bundle.to_payload(),
        "record_id": record_id,
        "written_at": written_at,
    }
    if not dry_run:
        artifact_file.parent.mkdir(parents=True, exist_ok=True)
        artifact_file.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return ShadowCycleIntelligenceBundleArtifactRecord(
        record_id=record_id,
        written_at=written_at,
        artifact_path=str(artifact_file.relative_to(project_root_path)),
    )


def write_shadow_cycle_intelligence_bundle_ledger(
    *,
    project_root: str | Path,
    record_id: str,
    bundle: ShadowCycleIntelligenceBundle,
    artifact_record: ShadowCycleIntelligenceBundleArtifactRecord,
    dry_run: bool = False,
) -> ShadowCycleIntelligenceBundleLedgerRecord:
    project_root_path = Path(project_root)
    ledger_file = _ledger_file(project_root=project_root_path, record_id=record_id)
    wave_payload = bundle.wave_hypothesis
    payload = {
        "record_id": record_id,
        "written_at": artifact_record.written_at,
        "stock_code": str(wave_payload.get("stock_code") or "").strip(),
        "trade_date": str(wave_payload.get("trade_date") or "").strip(),
        "artifact_path": artifact_record.artifact_path,
        "ledger_path": str(ledger_file.relative_to(project_root_path)),
    }
    if not dry_run:
        ledger_file.parent.mkdir(parents=True, exist_ok=True)
        ledger_file.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return ShadowCycleIntelligenceBundleLedgerRecord.from_dict(payload)


def materialize_shadow_cycle_intelligence_bundle(
    *,
    project_root: str | Path,
    bundle: ShadowCycleIntelligenceBundle,
    dry_run: bool = False,
) -> ShadowCycleIntelligenceBundleLedgerRecord:
    wave_payload = bundle.wave_hypothesis
    record_id = build_shadow_cycle_intelligence_bundle_record_id(
        stock_code=str(wave_payload.get("stock_code") or "").strip(),
        trade_date=str(wave_payload.get("trade_date") or "").strip(),
    )
    artifact_record = write_shadow_cycle_intelligence_bundle_artifact(
        project_root=project_root,
        record_id=record_id,
        bundle=bundle,
        dry_run=dry_run,
    )
    return write_shadow_cycle_intelligence_bundle_ledger(
        project_root=project_root,
        record_id=record_id,
        bundle=bundle,
        artifact_record=artifact_record,
        dry_run=dry_run,
    )


def read_shadow_cycle_intelligence_bundle_artifact(
    *,
    project_root: str | Path,
    record_id: str,
) -> dict[str, Any] | None:
    artifact_file = _artifact_file(project_root=Path(project_root), record_id=record_id)
    if not artifact_file.exists():
        return None
    payload = json.loads(artifact_file.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def read_shadow_cycle_intelligence_bundle(
    *,
    project_root: str | Path,
    record_id: str,
) -> ShadowCycleIntelligenceBundle | None:
    payload = read_shadow_cycle_intelligence_bundle_artifact(
        project_root=project_root,
        record_id=record_id,
    )
    if payload is None:
        return None
    return ShadowCycleIntelligenceBundle.from_dict(payload)


def read_shadow_cycle_intelligence_bundle_ledger(
    *,
    project_root: str | Path,
    record_id: str,
) -> ShadowCycleIntelligenceBundleLedgerRecord | None:
    ledger_file = _ledger_file(project_root=Path(project_root), record_id=record_id)
    if not ledger_file.exists():
        return None
    payload = json.loads(ledger_file.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return None
    return ShadowCycleIntelligenceBundleLedgerRecord.from_dict(payload)


def list_shadow_cycle_intelligence_bundle_ledgers(
    *,
    project_root: str | Path,
    limit: int = 200,
) -> list[ShadowCycleIntelligenceBundleLedgerRecord]:
    if limit <= 0:
        raise ValueError("limit must be a positive integer")
    root = Path(project_root) / "var/ledgers/m2_shadow_bundles"
    if not root.exists():
        return []

    records: list[ShadowCycleIntelligenceBundleLedgerRecord] = []
    for ledger_file in root.glob("*/shadow_bundle.json"):
        try:
            payload = json.loads(ledger_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        try:
            records.append(ShadowCycleIntelligenceBundleLedgerRecord.from_dict(payload))
        except Exception:
            continue

    records.sort(key=lambda item: (item.written_at, item.record_id), reverse=True)
    if len(records) > limit:
        records = records[:limit]
    return records
