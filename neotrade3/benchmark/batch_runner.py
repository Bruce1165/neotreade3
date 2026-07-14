"""Batch runner for NeoTrade3 M4 benchmark validation seed manifests."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping

from neotrade3.cycle_intelligence import SmallCycle
from .contracts import build_benchmark_sample
from .assembler import build_benchmark_assessment_from_m2_shadow
from .contracts import BenchmarkAssessmentResult
from .fixture_catalog import build_benchmark_fixture_bundle
from .sample_registry import (
    BenchmarkSeedRegistry,
    BenchmarkSeedSampleRegistration,
    load_benchmark_seed_registry,
)

INLINE_REPLAY_REGISTRY_PATH = "inline_replay_manifest"


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


def _copy_mapping(value: Any, *, field_name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{field_name} must be a JSON object")
    return {str(key): item for key, item in value.items()}


def _copy_mapping_list(value: Any, *, field_name: str) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise TypeError(f"{field_name} must be a JSON array")
    items: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, Mapping):
            raise TypeError(f"{field_name} items must be JSON objects")
        items.append({str(key): val for key, val in item.items()})
    return items


def _require_text(value: Any, *, field_name: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError(f"{field_name} must be non-empty")
    return raw


@dataclass(frozen=True)
class BenchmarkCandidateRunContext:
    experiment_id: str
    candidate_run_id: str
    source_run_id: str

    def to_payload(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "candidate_run_id": self.candidate_run_id,
            "source_run_id": self.source_run_id,
        }

    @classmethod
    def from_dict(
        cls,
        payload: Any,
        *,
        default_source_run_id: str = "",
    ) -> "BenchmarkCandidateRunContext":
        if not isinstance(payload, Mapping):
            raise TypeError("candidate_run_context must be a JSON object")
        experiment_id = str(payload.get("experiment_id") or "").strip()
        candidate_run_id = str(payload.get("candidate_run_id") or "").strip()
        source_run_id = str(
            payload.get("source_run_id") or default_source_run_id or ""
        ).strip()
        if not experiment_id:
            raise ValueError("experiment_id must be non-empty")
        if not candidate_run_id:
            raise ValueError("candidate_run_id must be non-empty")
        if not source_run_id:
            raise ValueError("source_run_id must be non-empty")
        return cls(
            experiment_id=experiment_id,
            candidate_run_id=candidate_run_id,
            source_run_id=source_run_id,
        )


@dataclass(frozen=True)
class BenchmarkReplaySample:
    sample_id: str
    sample_bucket: str
    stock_code: str
    trade_date: str
    target_state_type: str
    expected_target_state: dict[str, Any] = field(default_factory=dict)
    m2_cycle: dict[str, Any] = field(default_factory=dict)
    m2_shadow_bundle: dict[str, Any] = field(default_factory=dict)
    m3_context: dict[str, Any] = field(default_factory=dict)
    m1_context: dict[str, Any] = field(default_factory=dict)
    evidence_refs: list[dict[str, Any]] = field(default_factory=list)
    scenario_tags: tuple[str, ...] = ()
    note: str = ""
    input_data_version: str = "m1_phase1.v1"
    rule_version: str = "m4_benchmark_replay.v1alpha1"

    @classmethod
    def from_dict(cls, payload: Any) -> "BenchmarkReplaySample":
        if not isinstance(payload, Mapping):
            raise TypeError("replay_sample must be a JSON object")
        return cls(
            sample_id=_require_text(payload.get("sample_id"), field_name="sample_id"),
            sample_bucket=_require_text(
                payload.get("sample_bucket"),
                field_name="sample_bucket",
            ),
            stock_code=_require_text(payload.get("stock_code"), field_name="stock_code"),
            trade_date=_require_text(payload.get("trade_date"), field_name="trade_date"),
            target_state_type=_require_text(
                payload.get("target_state_type"),
                field_name="target_state_type",
            ),
            expected_target_state=_copy_mapping(
                payload.get("expected_target_state"),
                field_name="expected_target_state",
            ),
            m2_cycle=_copy_mapping(payload.get("m2_cycle"), field_name="m2_cycle"),
            m2_shadow_bundle=_copy_mapping(
                payload.get("m2_shadow_bundle"),
                field_name="m2_shadow_bundle",
            ),
            m3_context=_copy_mapping(payload.get("m3_context"), field_name="m3_context"),
            m1_context=(
                {}
                if payload.get("m1_context") is None
                else _copy_mapping(payload.get("m1_context"), field_name="m1_context")
            ),
            evidence_refs=_copy_mapping_list(
                payload.get("evidence_refs"),
                field_name="evidence_refs",
            ),
            scenario_tags=_copy_str_list(
                payload.get("scenario_tags"),
                field_name="scenario_tags",
            ),
            note=str(payload.get("note", "") or "").strip(),
            input_data_version=str(
                payload.get("input_data_version") or "m1_phase1.v1"
            ).strip(),
            rule_version=str(
                payload.get("rule_version") or "m4_benchmark_replay.v1alpha1"
            ).strip(),
        )

    def to_benchmark_sample(self):
        return build_benchmark_sample(
            stock_code=self.stock_code,
            trade_date=self.trade_date,
            sample_bucket=self.sample_bucket,
            target_state_type=self.target_state_type,
            expected_target_state=self.expected_target_state,
            evidence_refs=self.evidence_refs,
            scenario_tags=list(self.scenario_tags),
            note=self.note,
            input_data_version=self.input_data_version,
            rule_version=self.rule_version,
        )


@dataclass(frozen=True)
class BenchmarkRunManifest:
    run_id: str
    registry_path: str = ""
    sample_ids: tuple[str, ...] = ()
    description: str = ""
    candidate_run_context: BenchmarkCandidateRunContext | None = None
    replay_sample: BenchmarkReplaySample | None = None

    @classmethod
    def from_dict(cls, payload: Any) -> "BenchmarkRunManifest":
        if not isinstance(payload, dict):
            raise TypeError("benchmark run manifest root must be a JSON object")
        run_id = str(payload.get("run_id") or "").strip()
        registry_path = str(payload.get("registry_path") or "").strip()
        if not run_id:
            raise ValueError("run_id must be non-empty")
        candidate_run_context_payload = payload.get("candidate_run_context")
        replay_sample_payload = payload.get("replay_sample")
        if not registry_path and replay_sample_payload is None:
            raise ValueError("registry_path must be non-empty")
        return cls(
            run_id=run_id,
            registry_path=registry_path or INLINE_REPLAY_REGISTRY_PATH,
            sample_ids=_copy_str_list(payload.get("sample_ids"), field_name="sample_ids"),
            description=str(payload.get("description", "") or "").strip(),
            candidate_run_context=(
                None
                if candidate_run_context_payload is None
                else BenchmarkCandidateRunContext.from_dict(
                    candidate_run_context_payload,
                    default_source_run_id=run_id,
                )
            ),
            replay_sample=(
                None
                if replay_sample_payload is None
                else BenchmarkReplaySample.from_dict(replay_sample_payload)
            ),
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
    candidate_run_context: BenchmarkCandidateRunContext | None = None

    def to_payload(self) -> dict[str, Any]:
        payload = {
            "run_id": self.run_id,
            "registry_path": self.registry_path,
            "executed_sample_ids": list(self.executed_sample_ids),
            "grade_summary": dict(self.grade_summary),
            "bucket_summary": dict(self.bucket_summary),
            "results": [item.to_payload() for item in self.results],
        }
        if self.candidate_run_context is not None:
            payload["candidate_run_context"] = self.candidate_run_context.to_payload()
        return payload

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
        candidate_run_context_payload = payload.get("candidate_run_context")
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
            candidate_run_context=(
                None
                if candidate_run_context_payload is None
                else BenchmarkCandidateRunContext.from_dict(
                    candidate_run_context_payload,
                    default_source_run_id=run_id,
                )
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


def _build_small_cycle_from_payload(payload: Mapping[str, Any]) -> SmallCycle:
    return SmallCycle(
        stock_code=_require_text(payload.get("stock_code"), field_name="m2_cycle.stock_code"),
        trade_date=_require_text(payload.get("trade_date"), field_name="m2_cycle.trade_date"),
        cycle_state=_require_text(payload.get("cycle_state"), field_name="m2_cycle.cycle_state"),
        state_stability_level=_require_text(
            payload.get("state_stability_level"),
            field_name="m2_cycle.state_stability_level",
        ),
        evidence_bundle=_copy_mapping(
            payload.get("evidence_bundle", {}),
            field_name="m2_cycle.evidence_bundle",
        ),
        confidence=_copy_mapping(
            payload.get("confidence", {}),
            field_name="m2_cycle.confidence",
        ),
        invalidation=_copy_mapping(
            payload.get("invalidation", {}),
            field_name="m2_cycle.invalidation",
        ),
        state_transition_log=_copy_mapping_list(
            payload.get("state_transition_log", []),
            field_name="m2_cycle.state_transition_log",
        ),
        input_data_version=_require_text(
            payload.get("input_data_version"),
            field_name="m2_cycle.input_data_version",
        ),
        rule_version=_require_text(
            payload.get("rule_version"),
            field_name="m2_cycle.rule_version",
        ),
        object_type=str(payload.get("object_type") or "small_cycle"),
        object_version=int(payload.get("object_version", 1)),
    )


def _run_benchmark_replay_manifest(
    *,
    manifest: BenchmarkRunManifest,
) -> BenchmarkBatchRunResult:
    replay_sample = manifest.replay_sample
    if replay_sample is None:
        raise ValueError("replay_sample is required for replay benchmark manifests")
    sample = replay_sample.to_benchmark_sample()
    cycle = _build_small_cycle_from_payload(replay_sample.m2_cycle)
    result = build_benchmark_assessment_from_m2_shadow(
        sample=sample,
        cycle=cycle,
        shadow_bundle=replay_sample.m2_shadow_bundle,
        m1_context=replay_sample.m1_context,
        m3_context=replay_sample.m3_context,
    )
    grade = result.summary.assessment_grade
    return BenchmarkBatchRunResult(
        run_id=manifest.run_id,
        registry_path=manifest.registry_path,
        executed_sample_ids=(replay_sample.sample_id,),
        grade_summary={grade: 1},
        bucket_summary={replay_sample.sample_bucket: 1},
        results=(result,),
        candidate_run_context=manifest.candidate_run_context,
    )


def run_benchmark_manifest(
    *,
    project_root: str | Path,
    manifest: BenchmarkRunManifest,
    fixture_provider: Callable[[BenchmarkSeedSampleRegistration], Mapping[str, Any]]
    | None = None,
) -> BenchmarkBatchRunResult:
    if manifest.replay_sample is not None:
        return _run_benchmark_replay_manifest(manifest=manifest)

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
        candidate_run_context=manifest.candidate_run_context,
    )
