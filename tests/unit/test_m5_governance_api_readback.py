from __future__ import annotations

import json
from http import HTTPStatus
from pathlib import Path

import pytest

from apps.api.main import BootstrapApiService
from apps.api.router import BootstrapApiRouter
from apps.api.shared import ApiBinaryResponse
from apps.api.shared import ApiError


def _write_governance_final_validation_fixtures(
    *,
    project_root: Path,
    source_run_id: str,
    written_at: str = "2026-07-15T00:00:00Z",
) -> None:
    artifact_rel = (
        f"var/artifacts/governance_final_validations/{source_run_id}/"
        "governance_final_validation.json"
    )
    ledger_rel = (
        f"var/ledgers/governance_final_validations/{source_run_id}/"
        "governance_final_validation_run.json"
    )
    artifact_path = project_root / artifact_rel
    ledger_path = project_root / ledger_rel
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(
        json.dumps(
            {
                "version": 1,
                "source_run_id": source_run_id,
                "selected_validation_id": "validation-1",
                "baseline_run_id": source_run_id,
                "candidate_run_id": "candidate-run-1",
                "outcome": "passed",
                "selection_basis": "test",
                "candidate_validation_artifact_path": "var/artifacts/governance_candidate_validations/validation-1/governance_candidate_validation.json",
                "candidate_validation_ledger_path": "var/ledgers/governance_candidate_validations/validation-1/governance_candidate_validation_run.json",
                "handoff_artifact_path": f"var/artifacts/governance_handoffs/{source_run_id}/governance_handoff_bundle.json",
                "written_at": written_at,
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
                "source_run_id": source_run_id,
                "status": "completed",
                "written_at": written_at,
                "artifact_path": artifact_rel,
                "ledger_path": ledger_rel,
                "selected_validation_id": "validation-1",
                "baseline_run_id": source_run_id,
                "candidate_run_id": "candidate-run-1",
                "outcome": "passed",
            },
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def test_governance_final_validation_readback_endpoint_returns_record_and_artifact(
    tmp_path: Path,
) -> None:
    source_run_id = "benchmark-run-1"
    _write_governance_final_validation_fixtures(
        project_root=tmp_path,
        source_run_id=source_run_id,
    )
    service = BootstrapApiService(project_root=tmp_path)
    router = BootstrapApiRouter(service)

    status, payload = router.dispatch(
        f"/api/governance/final-validations/{source_run_id}"
    )

    assert status == HTTPStatus.OK
    assert payload["_meta"]["status"] == "ok"
    assert payload["final_validation"]["source_run_id"] == source_run_id
    assert payload["final_validation_artifact"]["source_run_id"] == source_run_id


def test_governance_final_validation_readback_endpoint_returns_404_when_missing(
    tmp_path: Path,
) -> None:
    service = BootstrapApiService(project_root=tmp_path)
    router = BootstrapApiRouter(service)

    with pytest.raises(ApiError) as exc:
        router.dispatch("/api/governance/final-validations/benchmark-run-2")

    assert exc.value.status_code == HTTPStatus.NOT_FOUND
    assert exc.value.code == "governance_final_validation_not_found"


def test_governance_final_validations_list_endpoint_returns_latest_records(
    tmp_path: Path,
) -> None:
    _write_governance_final_validation_fixtures(
        project_root=tmp_path,
        source_run_id="benchmark-run-1",
        written_at="2026-07-15T00:00:00Z",
    )
    _write_governance_final_validation_fixtures(
        project_root=tmp_path,
        source_run_id="benchmark-run-2",
        written_at="2026-07-16T00:00:00Z",
    )
    _write_governance_final_validation_fixtures(
        project_root=tmp_path,
        source_run_id="benchmark-run-3",
        written_at="2026-07-14T00:00:00Z",
    )
    service = BootstrapApiService(project_root=tmp_path)
    router = BootstrapApiRouter(service)

    status, payload = router.dispatch("/api/governance/final-validations?limit=2")

    assert status == HTTPStatus.OK
    assert payload["_meta"]["returned_count"] == 2
    assert payload["final_validations"][0]["source_run_id"] == "benchmark-run-2"
    assert payload["final_validations"][1]["source_run_id"] == "benchmark-run-1"


def test_governance_final_validation_download_endpoint_returns_artifact(
    tmp_path: Path,
) -> None:
    source_run_id = "benchmark-run-1"
    _write_governance_final_validation_fixtures(
        project_root=tmp_path,
        source_run_id=source_run_id,
    )
    service = BootstrapApiService(project_root=tmp_path)
    router = BootstrapApiRouter(service)

    status, response = router.dispatch(
        f"/api/governance/final-validations/{source_run_id}/download"
    )

    assert status == HTTPStatus.OK
    assert isinstance(response, ApiBinaryResponse)
    assert "attachment" in response.headers.get("Content-Disposition", "")
    payload = json.loads(response.body.decode("utf-8"))
    assert payload["source_run_id"] == source_run_id
