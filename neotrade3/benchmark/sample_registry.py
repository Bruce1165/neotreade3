"""Registry loader for NeoTrade3 M4 benchmark validation seed samples."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from .contracts import BenchmarkSample, build_benchmark_sample


def _copy_mapping(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise TypeError("mapping value must be a JSON object")
    return {str(key): item for key, item in value.items()}


def _copy_mapping_list(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise TypeError("evidence_refs must be a JSON array")
    items: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            raise TypeError("evidence_refs items must be JSON objects")
        items.append({str(key): val for key, val in item.items()})
    return items


def _copy_str_list(value: Any, *, field_name: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise TypeError(f"{field_name} must be a JSON array")
    return [str(item).strip() for item in value if str(item).strip()]


@dataclass(frozen=True)
class BenchmarkSeedSampleRegistration:
    sample_id: str
    fixture_id: str
    stock_code: str
    trade_date: str
    sample_bucket: str
    target_state_type: str
    expected_target_state: dict[str, Any] = field(default_factory=dict)
    evidence_refs: list[dict[str, Any]] = field(default_factory=list)
    scenario_tags: list[str] = field(default_factory=list)
    note: str = ""
    input_data_version: str = "m1_phase1.v1"
    rule_version: str = "m4_benchmark_seed.v1alpha1"

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "BenchmarkSeedSampleRegistration":
        sample_id = str(payload.get("sample_id") or "").strip()
        fixture_id = str(payload.get("fixture_id") or "").strip()
        stock_code = str(payload.get("stock_code") or "").strip()
        trade_date = str(payload.get("trade_date") or "").strip()
        sample_bucket = str(payload.get("sample_bucket") or "").strip()
        target_state_type = str(payload.get("target_state_type") or "").strip()
        if not sample_id:
            raise ValueError("sample_id must be non-empty")
        if not fixture_id:
            raise ValueError("fixture_id must be non-empty")
        if not stock_code:
            raise ValueError("stock_code must be non-empty")
        if not trade_date:
            raise ValueError("trade_date must be non-empty")
        if not sample_bucket:
            raise ValueError("sample_bucket must be non-empty")
        if not target_state_type:
            raise ValueError("target_state_type must be non-empty")
        return cls(
            sample_id=sample_id,
            fixture_id=fixture_id,
            stock_code=stock_code,
            trade_date=trade_date,
            sample_bucket=sample_bucket,
            target_state_type=target_state_type,
            expected_target_state=_copy_mapping(payload.get("expected_target_state")),
            evidence_refs=_copy_mapping_list(payload.get("evidence_refs")),
            scenario_tags=_copy_str_list(payload.get("scenario_tags"), field_name="scenario_tags"),
            note=str(payload.get("note", "") or "").strip(),
            input_data_version=str(payload.get("input_data_version") or "m1_phase1.v1").strip(),
            rule_version=str(payload.get("rule_version") or "m4_benchmark_seed.v1alpha1").strip(),
        )

    def to_benchmark_sample(self) -> BenchmarkSample:
        return build_benchmark_sample(
            stock_code=self.stock_code,
            trade_date=self.trade_date,
            sample_bucket=self.sample_bucket,
            target_state_type=self.target_state_type,
            expected_target_state=self.expected_target_state,
            evidence_refs=self.evidence_refs,
            scenario_tags=self.scenario_tags,
            note=self.note,
            input_data_version=self.input_data_version,
            rule_version=self.rule_version,
        )


@dataclass(frozen=True)
class BenchmarkSeedRegistry:
    version: int
    description: str
    samples: tuple[BenchmarkSeedSampleRegistration, ...]

    @classmethod
    def from_file(cls, file_path: str | Path) -> "BenchmarkSeedRegistry":
        payload = json.loads(Path(file_path).read_text(encoding="utf-8"))
        return cls.from_dict(payload)

    @classmethod
    def from_dict(cls, payload: Any) -> "BenchmarkSeedRegistry":
        if not isinstance(payload, dict):
            raise TypeError("benchmark seed registry root must be a JSON object")
        samples_raw = payload.get("samples", [])
        if not isinstance(samples_raw, list):
            raise TypeError("samples must be a JSON array")
        samples = tuple(
            BenchmarkSeedSampleRegistration.from_dict(item)
            for item in samples_raw
            if isinstance(item, dict)
        )
        registry = cls(
            version=int(payload.get("version", 1)),
            description=str(payload.get("description", "") or "").strip(),
            samples=samples,
        )
        sample_ids = [sample.sample_id for sample in registry.samples]
        if len(set(sample_ids)) != len(sample_ids):
            raise ValueError("benchmark seed registry sample_id values must be unique")
        return registry

    def get_sample(self, sample_id: str) -> BenchmarkSeedSampleRegistration:
        for sample in self.samples:
            if sample.sample_id == sample_id:
                return sample
        raise KeyError(f"unknown benchmark seed sample_id: {sample_id}")

    def samples_for_bucket(
        self,
        sample_bucket: str | None = None,
    ) -> tuple[BenchmarkSeedSampleRegistration, ...]:
        if sample_bucket is None:
            return self.samples
        return tuple(sample for sample in self.samples if sample.sample_bucket == sample_bucket)

    def build_benchmark_samples(
        self,
        sample_bucket: str | None = None,
    ) -> tuple[BenchmarkSample, ...]:
        registrations: Iterable[BenchmarkSeedSampleRegistration] = self.samples_for_bucket(
            sample_bucket
        )
        return tuple(sample.to_benchmark_sample() for sample in registrations)


def load_benchmark_seed_registry(file_path: str | Path) -> BenchmarkSeedRegistry:
    return BenchmarkSeedRegistry.from_file(file_path)
