from __future__ import annotations

from pathlib import Path

import pytest

from neotrade3.benchmark import (
    BenchmarkBatchRunResult,
    load_benchmark_run_manifest,
    materialize_benchmark_batch_run,
    read_benchmark_batch_run_result,
    run_benchmark_manifest,
)
from neotrade3.benchmark.batch_runner import INLINE_REPLAY_REGISTRY_PATH, BenchmarkRunManifest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPLAY_MANIFEST = PROJECT_ROOT / "config" / "benchmark" / "formal_replay_manifest.json"


def test_replay_manifest_parses_without_registry_path() -> None:
    manifest = load_benchmark_run_manifest(REPLAY_MANIFEST)

    assert manifest.run_id == "formal_replay_v1_batch"
    assert manifest.registry_path == INLINE_REPLAY_REGISTRY_PATH
    assert manifest.replay_sample is not None
    assert manifest.replay_sample.sample_id == "formal_front_replay_seed_v1"
    assert manifest.replay_sample.sample_bucket == "R1_formal_front_replay"


def test_replay_manifest_materializes_benchmark_artifact(tmp_path: Path) -> None:
    manifest = load_benchmark_run_manifest(REPLAY_MANIFEST)
    batch_result = run_benchmark_manifest(
        project_root=PROJECT_ROOT,
        manifest=manifest,
    )
    materialize_benchmark_batch_run(
        project_root=tmp_path,
        batch_result=batch_result,
    )

    reconstructed = read_benchmark_batch_run_result(
        project_root=tmp_path,
        run_id=batch_result.run_id,
    )

    assert batch_result.executed_sample_ids == ("formal_front_replay_seed_v1",)
    assert batch_result.grade_summary == {"pass": 1}
    assert batch_result.bucket_summary == {"R1_formal_front_replay": 1}
    assert reconstructed == batch_result
    assert reconstructed is not None
    assert reconstructed.results[0].summary.assessment_grade == "pass"


def test_replay_manifest_fails_closed_when_m2_shadow_bundle_missing() -> None:
    with pytest.raises(TypeError, match="m2_shadow_bundle must be a JSON object"):
        BenchmarkRunManifest.from_dict(
            {
                "run_id": "broken_replay_batch",
                "replay_sample": {
                    "sample_id": "broken_replay_seed",
                    "sample_bucket": "R1_formal_front_replay",
                    "stock_code": "600000",
                    "trade_date": "2026-07-07",
                    "target_state_type": "T3_strong_target",
                    "expected_target_state": {},
                    "m2_cycle": {},
                    "m3_context": {},
                },
            }
        )


def test_replay_artifact_round_trips_from_dict_with_inline_registry_marker() -> None:
    manifest = load_benchmark_run_manifest(REPLAY_MANIFEST)
    batch_result = run_benchmark_manifest(
        project_root=PROJECT_ROOT,
        manifest=manifest,
    )

    reconstructed = BenchmarkBatchRunResult.from_dict(
        {
            **batch_result.to_payload(),
            "sample_count": 1,
            "written_at": "2026-07-14T12:00:00Z",
        }
    )

    assert reconstructed == batch_result
    assert reconstructed.registry_path == INLINE_REPLAY_REGISTRY_PATH
