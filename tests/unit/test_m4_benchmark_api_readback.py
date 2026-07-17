from __future__ import annotations

import json
from http import HTTPStatus
from pathlib import Path

import pytest

from apps.api.main import BootstrapApiService
from apps.api.router import BootstrapApiRouter
from apps.api.shared import ApiBinaryResponse, ApiError


def _write_benchmark_run_fixtures(
    *,
    project_root: Path,
    run_id: str,
    written_at: str,
    registry_path: str = "config/benchmark/validation_seed_samples.json",
    executed_sample_ids: list[str] | None = None,
) -> None:
    sample_ids = ["sample-1"] if executed_sample_ids is None else executed_sample_ids
    artifact_rel = f"var/artifacts/benchmark_runs/{run_id}/benchmark_batch_result.json"
    ledger_rel = f"var/ledgers/benchmark_runs/{run_id}/benchmark_batch_run.json"
    artifact_path = project_root / artifact_rel
    ledger_path = project_root / ledger_rel
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(
        json.dumps(
            {
                "run_id": run_id,
                "registry_path": registry_path,
                "executed_sample_ids": sample_ids,
                "grade_summary": {"A": 1},
                "bucket_summary": {"seed": 1},
                "results": [],
                "written_at": written_at,
                "sample_count": 1,
            },
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    ledger_path.write_text(
        json.dumps(
            {
                "run_id": run_id,
                "status": "completed",
                "written_at": written_at,
                "sample_count": 1,
                "registry_path": registry_path,
                "artifact_path": artifact_rel,
                "ledger_path": ledger_rel,
                "executed_sample_ids": sample_ids,
                "grade_summary": {"A": 1},
                "bucket_summary": {"seed": 1},
            },
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _write_seed_registry_fixture(
    *,
    project_root: Path,
    registry_path: str = "config/benchmark/validation_seed_samples.json",
    samples: list[dict[str, object]],
) -> None:
    path = project_root / registry_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {"version": 1, "description": "test registry", "samples": samples},
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _write_benchmark_projection_fixtures(
    *,
    project_root: Path,
    record_id: str,
) -> None:
    paths = [
        project_root
        / "var/artifacts/benchmark_m1_contexts"
        / record_id
        / "m1_context_projection.json",
        project_root
        / "var/ledgers/benchmark_m1_contexts"
        / record_id
        / "m1_context_projection.json",
        project_root
        / "var/artifacts/benchmark_m3_contexts"
        / record_id
        / "m3_context_projection.json",
        project_root
        / "var/ledgers/benchmark_m3_contexts"
        / record_id
        / "m3_context_projection.json",
    ]
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}", encoding="utf-8")


def test_m4_benchmark_runs_list_endpoint_returns_records_sorted_and_limited(
    tmp_path: Path,
) -> None:
    _write_benchmark_run_fixtures(
        project_root=tmp_path,
        run_id="run-a",
        written_at="2026-07-10T00:00:00Z",
    )
    _write_benchmark_run_fixtures(
        project_root=tmp_path,
        run_id="run-b",
        written_at="2026-07-11T00:00:00Z",
    )
    service = BootstrapApiService(project_root=tmp_path)
    router = BootstrapApiRouter(service)

    status, payload = router.dispatch("/api/m4/benchmark-runs?limit=1")
    assert status == HTTPStatus.OK
    assert payload["_meta"]["matched_count"] == 2
    assert payload["_meta"]["returned_count"] == 1
    assert payload["_meta"]["limit"] == 1
    assert payload["benchmark_runs"][0]["run_id"] == "run-b"
    assert payload["benchmark_runs"][0]["url"] == "/api/m4/benchmark-runs/run-b"
    assert payload["benchmark_runs"][0]["download_url"] == "/api/m4/benchmark-runs/run-b/download"
    assert (
        payload["benchmark_runs"][0]["download_ledger_url"]
        == "/api/m4/benchmark-runs/run-b/download-ledger"
    )


def test_m4_benchmark_run_view_reads_ledger_and_artifact(tmp_path: Path) -> None:
    _write_benchmark_run_fixtures(
        project_root=tmp_path,
        run_id="run-a",
        written_at="2026-07-11T00:00:00Z",
    )
    _write_seed_registry_fixture(
        project_root=tmp_path,
        samples=[
            {
                "sample_id": "sample-1",
                "fixture_id": "fixture-1",
                "stock_code": "600000",
                "trade_date": "2026-07-11",
                "sample_bucket": "seed",
                "target_state_type": "front_state",
                "expected_target_state": {},
                "evidence_refs": [{"kind": "m1", "ref": "var/db/stock_data.db"}],
                "scenario_tags": ["t1"],
                "note": "n1",
                "input_data_version": "m1_phase1.v1",
                "rule_version": "m4_benchmark_seed.v1alpha1",
            }
        ],
    )
    _write_benchmark_projection_fixtures(project_root=tmp_path, record_id="600000-2026-07-11")
    service = BootstrapApiService(project_root=tmp_path)
    router = BootstrapApiRouter(service)

    status, payload = router.dispatch("/api/m4/benchmark-runs/run-a")
    assert status == HTTPStatus.OK
    assert payload["_meta"]["status"] == "ok"
    assert payload["benchmark_run"]["run_id"] == "run-a"
    assert payload["benchmark_run_artifact"]["run_id"] == "run-a"
    assert payload["evidence"]["seed_registry"]["registry_path"] == "config/benchmark/validation_seed_samples.json"
    assert payload["evidence"]["samples"][0]["sample_id"] == "sample-1"
    assert payload["evidence"]["samples"][0]["m1_context_projection"]["record_id"] == "600000-2026-07-11"
    assert payload["evidence"]["samples"][0]["m3_context_projection"]["record_id"] == "600000-2026-07-11"


def test_m4_benchmark_run_download_endpoints_return_binary_response(
    tmp_path: Path,
) -> None:
    _write_benchmark_run_fixtures(
        project_root=tmp_path,
        run_id="run-a",
        written_at="2026-07-11T00:00:00Z",
    )
    service = BootstrapApiService(project_root=tmp_path)
    router = BootstrapApiRouter(service)

    status, response = router.dispatch("/api/m4/benchmark-runs/run-a/download")
    assert status == HTTPStatus.OK
    assert isinstance(response, ApiBinaryResponse)
    assert "attachment" in response.headers.get("Content-Disposition", "")
    assert response.content_type.startswith("application/json")

    status, response = router.dispatch("/api/m4/benchmark-runs/run-a/download-ledger")
    assert status == HTTPStatus.OK
    assert isinstance(response, ApiBinaryResponse)
    assert "attachment" in response.headers.get("Content-Disposition", "")
    assert response.content_type.startswith("application/json")


def test_m4_benchmark_run_view_returns_404_when_missing(tmp_path: Path) -> None:
    service = BootstrapApiService(project_root=tmp_path)
    router = BootstrapApiRouter(service)

    with pytest.raises(ApiError) as exc:
        router.dispatch("/api/m4/benchmark-runs/missing-run")

    assert exc.value.status_code == HTTPStatus.NOT_FOUND
    assert exc.value.code == "benchmark_run_not_found"


def test_m4_benchmark_run_view_rejects_invalid_run_id(tmp_path: Path) -> None:
    service = BootstrapApiService(project_root=tmp_path)
    router = BootstrapApiRouter(service)

    with pytest.raises(ApiError) as exc:
        router.dispatch("/api/m4/benchmark-runs/..")

    assert exc.value.status_code == HTTPStatus.BAD_REQUEST
    assert exc.value.code == "invalid_run_id"


def test_m4_benchmark_run_view_returns_500_when_seed_registry_missing(tmp_path: Path) -> None:
    _write_benchmark_run_fixtures(
        project_root=tmp_path,
        run_id="run-a",
        written_at="2026-07-11T00:00:00Z",
    )
    service = BootstrapApiService(project_root=tmp_path)
    router = BootstrapApiRouter(service)

    with pytest.raises(ApiError) as exc:
        router.dispatch("/api/m4/benchmark-runs/run-a")
    assert exc.value.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert exc.value.code == "benchmark_seed_registry_not_found"


def test_m4_benchmark_run_view_returns_500_when_seed_sample_missing(tmp_path: Path) -> None:
    _write_benchmark_run_fixtures(
        project_root=tmp_path,
        run_id="run-a",
        written_at="2026-07-11T00:00:00Z",
    )
    _write_seed_registry_fixture(
        project_root=tmp_path,
        samples=[
            {
                "sample_id": "sample-x",
                "fixture_id": "fixture-1",
                "stock_code": "600000",
                "trade_date": "2026-07-11",
                "sample_bucket": "seed",
                "target_state_type": "front_state",
            }
        ],
    )
    service = BootstrapApiService(project_root=tmp_path)
    router = BootstrapApiRouter(service)

    with pytest.raises(ApiError) as exc:
        router.dispatch("/api/m4/benchmark-runs/run-a")
    assert exc.value.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert exc.value.code == "benchmark_seed_sample_not_found"


def test_m4_benchmark_run_view_returns_500_when_seed_registry_path_escapes(
    tmp_path: Path,
) -> None:
    _write_benchmark_run_fixtures(
        project_root=tmp_path,
        run_id="run-a",
        written_at="2026-07-11T00:00:00Z",
        registry_path="../evil.json",
    )
    service = BootstrapApiService(project_root=tmp_path)
    router = BootstrapApiRouter(service)

    with pytest.raises(ApiError) as exc:
        router.dispatch("/api/m4/benchmark-runs/run-a")
    assert exc.value.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert exc.value.code == "benchmark_seed_registry_path_escape"
