"""Batch runner for NeoTrade3 M4 benchmark validation seed manifests."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping

from .assembler import build_benchmark_assessment_from_m2_shadow
from .contracts import BenchmarkAssessmentResult
from .fixture_catalog import build_benchmark_fixture_bundle
from .sample_registry import (
    BenchmarkSeedRegistry,
    BenchmarkSeedSampleRegistration,
    load_benchmark_seed_registry,
)


def _copy_str_list(value: Any, *, field_name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise TypeError(f"{field_name} must be a JSON array")
    return tuple(str(item).strip() for item in value if str(item).strip())


def _copy_int_dict(value: Any, *, field_name: str) -> dict[str, int]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise TypeError(f"{field_name} must be a JSON object")
    return {str(key): int(item) for key, item in value.items()}


@dataclass(frozen=True)
class BenchmarkRunManifest:
    run_id: str
    registry_path: str
    sample_ids: tuple[str, ...] = ()
    description: str = ""

    @classmethod
    def from_dict(cls, payload: Any) -> "BenchmarkRunManifest":
        if not isinstance(payload, dict):
            raise TypeError("benchmark run manifest root must be a JSON object")
        run_id = str(payload.get("run_id") or "").strip()
        registry_path = str(payload.get("registry_path") or "").strip()
        if not run_id:
            raise ValueError("run_id must be non-empty")
        if not registry_path:
            raise ValueError("registry_path must be non-empty")
        return cls(
            run_id=run_id,
            registry_path=registry_path,
            sample_ids=_copy_str_list(payload.get("sample_ids"), field_name="sample_ids"),
            description=str(payload.get("description", "") or "").strip(),
        )

    @classmethod
    def from_file(cls, file_path: str | Path) -> "BenchmarkRunManifest":
        payload = json.loads(Path(file_path).read_text(encoding="utf-8"))
        return cls.from_dict(payload)


@dataclass(frozen=True)
class BenchmarkBatchRunResult:
    run_id: str
    registry_path: str
    executed_sample_ids: tuple[str, ...]
    grade_summary: dict[str, int] = field(default_factory=dict)
    bucket_summary: dict[str, int] = field(default_factory=dict)
    results: tuple[BenchmarkAssessmentResult, ...] = ()

    def to_payload(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "registry_path": self.registry_path,
            "executed_sample_ids": list(self.executed_sample_ids),
            "grade_summary": dict(self.grade_summary),
            "bucket_summary": dict(self.bucket_summary),
            "results": [item.to_payload() for item in self.results],
        }

    @classmethod
    def from_dict(cls, payload: Any) -> "BenchmarkBatchRunResult":
        if not isinstance(payload, dict):
            raise TypeError("benchmark batch run result root must be a JSON object")
        run_id = str(payload.get("run_id") or "").strip()
        registry_path = str(payload.get("registry_path") or "").strip()
        if not run_id:
            raise ValueError("run_id must be non-empty")
        if not registry_path:
            raise ValueError("registry_path must be non-empty")

        results_payload = payload.get("results", [])
        if not isinstance(results_payload, list):
            raise TypeError("results must be a JSON array")

        return cls(
            run_id=run_id,
            registry_path=registry_path,
            executed_sample_ids=_copy_str_list(
                payload.get("executed_sample_ids"),
                field_name="executed_sample_ids",
            ),
            grade_summary=_copy_int_dict(
                payload.get("grade_summary"),
                field_name="grade_summary",
            ),
            bucket_summary=_copy_int_dict(
                payload.get("bucket_summary"),
                field_name="bucket_summary",
            ),
            results=tuple(
                BenchmarkAssessmentResult.from_dict(item) for item in results_payload
            ),
        )


def load_benchmark_run_manifest(file_path: str | Path) -> BenchmarkRunManifest:
    return BenchmarkRunManifest.from_file(file_path)


def _resolve_registry_path(project_root: str | Path, registry_path: str) -> Path:
    base = Path(project_root)
    candidate = Path(registry_path)
    if candidate.is_absolute():
        return candidate
    return base / registry_path


def _select_samples(
    manifest: BenchmarkRunManifest,
    registry: BenchmarkSeedRegistry,
) -> tuple[BenchmarkSeedSampleRegistration, ...]:
    if not manifest.sample_ids:
        return registry.samples
    return tuple(registry.get_sample(sample_id) for sample_id in manifest.sample_ids)


def run_benchmark_manifest(
    *,
    project_root: str | Path,
    manifest: BenchmarkRunManifest,
    fixture_provider: Callable[[BenchmarkSeedSampleRegistration], Mapping[str, Any]]
    | None = None,
) -> BenchmarkBatchRunResult:
    registry_path = _resolve_registry_path(project_root, manifest.registry_path)
    registry = load_benchmark_seed_registry(registry_path)
    registrations = _select_samples(manifest, registry)
    active_fixture_provider = fixture_provider or build_benchmark_fixture_bundle

    results: list[BenchmarkAssessmentResult] = []
    grade_summary: dict[str, int] = {}
    bucket_summary: dict[str, int] = {}
    executed_sample_ids: list[str] = []

    for registration in registrations:
        fixture = dict(active_fixture_provider(registration))
        cycle = fixture["cycle"]
        shadow_bundle = fixture["shadow_bundle"]
        m1_context = fixture.get("m1_context")
        m3_context = fixture.get("m3_context")
        sample = registration.to_benchmark_sample()
        result = build_benchmark_assessment_from_m2_shadow(
            sample=sample,
            cycle=cycle,
            shadow_bundle=shadow_bundle,
            m1_context=m1_context,
            m3_context=m3_context,
        )
        results.append(result)
        executed_sample_ids.append(registration.sample_id)
        grade = result.summary.assessment_grade
        grade_summary[grade] = grade_summary.get(grade, 0) + 1
        bucket_summary[registration.sample_bucket] = (
            bucket_summary.get(registration.sample_bucket, 0) + 1
        )

    return BenchmarkBatchRunResult(
        run_id=manifest.run_id,
        registry_path=str(manifest.registry_path),
        executed_sample_ids=tuple(executed_sample_ids),
        grade_summary=grade_summary,
        bucket_summary=bucket_summary,
        results=tuple(results),
    )
