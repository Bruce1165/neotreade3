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
    outcome: str = "passed",
    selected_validation_id: str = "validation-1",
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
                "selected_validation_id": selected_validation_id,
                "baseline_run_id": source_run_id,
                "candidate_run_id": "candidate-run-1",
                "outcome": outcome,
                "selection_basis": "test",
                "candidate_validation_artifact_path": f"var/artifacts/governance_candidate_validations/{selected_validation_id}/governance_candidate_validation.json",
                "candidate_validation_ledger_path": f"var/ledgers/governance_candidate_validations/{selected_validation_id}/governance_candidate_validation_run.json",
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
                "selected_validation_id": selected_validation_id,
                "baseline_run_id": source_run_id,
                "candidate_run_id": "candidate-run-1",
                "outcome": outcome,
            },
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _write_governance_reject_execution_fixtures(
    *,
    project_root: Path,
    source_run_id: str,
    validation_id: str,
    written_at: str = "2026-07-15T00:00:00Z",
) -> None:
    artifact_rel = (
        f"var/artifacts/governance_rejections/{validation_id}/"
        "governance_reject_execution.json"
    )
    ledger_rel = (
        f"var/ledgers/governance_rejections/{validation_id}/"
        "governance_reject_execution_run.json"
    )
    artifact_path = project_root / artifact_rel
    ledger_path = project_root / ledger_rel
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(
        json.dumps(
            {
                "version": 1,
                "validation_id": validation_id,
                "source_run_id": source_run_id,
                "written_at": written_at,
                "decision_id": "decision-1",
                "decision": "reject",
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
                "validation_id": validation_id,
                "source_run_id": source_run_id,
                "status": "completed",
                "written_at": written_at,
                "artifact_path": artifact_rel,
                "ledger_path": ledger_rel,
                "baseline_run_id": source_run_id,
                "candidate_run_id": "candidate-run-1",
                "decision_id": "decision-1",
                "decision": "reject",
            },
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _write_governance_status_transition_fixtures(
    *,
    project_root: Path,
    source_run_id: str,
    validation_id: str,
    written_at: str = "2026-07-15T00:00:00Z",
) -> None:
    artifact_rel = (
        f"var/artifacts/governance_status_transitions/{validation_id}/"
        "governance_status_transition.json"
    )
    ledger_rel = (
        f"var/ledgers/governance_status_transitions/{validation_id}/"
        "governance_status_transition_run.json"
    )
    artifact_path = project_root / artifact_rel
    ledger_path = project_root / ledger_rel
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(
        json.dumps(
            {
                "version": 1,
                "validation_id": validation_id,
                "source_run_id": source_run_id,
                "written_at": written_at,
                "decision_id": "decision-1",
                "effective_attention_item": {"attention_id": "att-1", "status": "active"},
                "effective_promotion_blocker": {"blocker_id": "blk-1", "active": True},
                "dry_run": False,
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
                "validation_id": validation_id,
                "source_run_id": source_run_id,
                "status": "completed",
                "written_at": written_at,
                "artifact_path": artifact_rel,
                "ledger_path": ledger_rel,
                "baseline_run_id": source_run_id,
                "candidate_run_id": "candidate-run-1",
                "decision_id": "decision-1",
                "effective_attention_id": "att-1",
                "effective_attention_status": "active",
                "effective_blocker_id": "blk-1",
                "effective_blocker_active": True,
            },
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

def _write_governance_candidate_validation_fixtures(
    *,
    project_root: Path,
    source_run_id: str,
    validation_id: str,
    written_at: str = "2026-07-15T00:00:00Z",
    outcome: str = "rejected",
) -> None:
    artifact_rel = (
        f"var/artifacts/governance_candidate_validations/{validation_id}/"
        "governance_candidate_validation.json"
    )
    ledger_rel = (
        f"var/ledgers/governance_candidate_validations/{validation_id}/"
        "governance_candidate_validation_run.json"
    )
    artifact_path = project_root / artifact_rel
    ledger_path = project_root / ledger_rel
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(
        json.dumps(
            {
                "version": 1,
                "validation_id": validation_id,
                "source_run_id": source_run_id,
                "written_at": written_at,
                "validation_result": {
                    "validation_id": validation_id,
                    "baseline_run_id": source_run_id,
                    "candidate_run_id": "candidate-run-1",
                    "outcome": outcome,
                },
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
                "validation_id": validation_id,
                "source_run_id": source_run_id,
                "status": "completed",
                "written_at": written_at,
                "artifact_path": artifact_rel,
                "ledger_path": ledger_rel,
                "baseline_run_id": source_run_id,
                "candidate_run_id": "candidate-run-1",
                "outcome": outcome,
            },
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _write_governance_handoff_fixtures(
    *,
    project_root: Path,
    source_run_id: str,
    written_at: str = "2026-07-15T00:00:00Z",
) -> None:
    artifact_rel = (
        f"var/artifacts/governance_handoffs/{source_run_id}/governance_handoff_bundle.json"
    )
    ledger_rel = (
        f"var/ledgers/governance_handoffs/{source_run_id}/governance_handoff_run.json"
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
                "written_at": written_at,
                "source_layer": "test",
                "projected_assessments": [],
                "projected_issues": [],
                "diagnostics": [],
                "change_requests": [],
                "experiment_requests": [],
                "validation_results": [],
                "promotion_blockers": [],
                "attention_items": [],
                "decision_records": [],
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
                "source_layer": "test",
                "projected_assessment_count": 0,
                "projected_issue_count": 0,
                "diagnostic_count": 0,
                "change_request_count": 0,
                "experiment_request_count": 0,
                "validation_result_count": 0,
                "promotion_blocker_count": 0,
                "attention_item_count": 0,
                "decision_record_count": 0,
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


def test_governance_final_validation_download_ledger_endpoint_returns_ledger(
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
        f"/api/governance/final-validations/{source_run_id}/download-ledger"
    )

    assert status == HTTPStatus.OK
    assert isinstance(response, ApiBinaryResponse)
    assert "attachment" in response.headers.get("Content-Disposition", "")
    payload = json.loads(response.body.decode("utf-8"))
    assert payload["source_run_id"] == source_run_id


def test_governance_final_validation_download_endpoint_rejects_path_traversal_source_run_id(
    tmp_path: Path,
) -> None:
    service = BootstrapApiService(project_root=tmp_path)
    router = BootstrapApiRouter(service)

    with pytest.raises(ApiError) as exc:
        router.dispatch("/api/governance/final-validations/../download")

    assert exc.value.status_code == HTTPStatus.BAD_REQUEST
    assert exc.value.code == "invalid_source_run_id"


def test_governance_reject_execution_download_endpoint_rejects_path_traversal_validation_id(
    tmp_path: Path,
) -> None:
    service = BootstrapApiService(project_root=tmp_path)
    router = BootstrapApiRouter(service)

    with pytest.raises(ApiError) as exc:
        router.dispatch("/api/governance/rejections/../download")

    assert exc.value.status_code == HTTPStatus.BAD_REQUEST
    assert exc.value.code == "invalid_validation_id"


def test_governance_reject_transition_chain_readback_endpoint_returns_aggregated_payload_when_rejected(
    tmp_path: Path,
) -> None:
    source_run_id = "benchmark-run-1"
    validation_id = "validation-1"
    _write_governance_final_validation_fixtures(
        project_root=tmp_path,
        source_run_id=source_run_id,
        outcome="rejected",
        selected_validation_id=validation_id,
    )
    _write_governance_reject_execution_fixtures(
        project_root=tmp_path,
        source_run_id=source_run_id,
        validation_id=validation_id,
    )
    _write_governance_status_transition_fixtures(
        project_root=tmp_path,
        source_run_id=source_run_id,
        validation_id=validation_id,
    )
    service = BootstrapApiService(project_root=tmp_path)
    router = BootstrapApiRouter(service)

    status, payload = router.dispatch(
        f"/api/governance/reject-transition-chains/{source_run_id}"
    )

    assert status == HTTPStatus.OK
    assert payload["_meta"]["status"] == "ok"
    assert payload["final_validation"]["source_run_id"] == source_run_id
    assert payload["final_validation"]["outcome"] == "rejected"
    assert payload["reject_execution"]["validation_id"] == validation_id
    assert payload["status_transition"]["validation_id"] == validation_id


def test_governance_reject_transition_chain_readback_endpoint_returns_final_validation_when_not_rejected(
    tmp_path: Path,
) -> None:
    source_run_id = "benchmark-run-1"
    _write_governance_final_validation_fixtures(
        project_root=tmp_path,
        source_run_id=source_run_id,
        outcome="passed",
    )
    service = BootstrapApiService(project_root=tmp_path)
    router = BootstrapApiRouter(service)

    status, payload = router.dispatch(
        f"/api/governance/reject-transition-chains/{source_run_id}"
    )

    assert status == HTTPStatus.OK
    assert payload["_meta"]["status"] == "ok"
    assert payload["final_validation"]["outcome"] == "passed"
    assert "reject_execution" not in payload
    assert "status_transition" not in payload


def test_governance_reject_transition_chain_readback_endpoint_returns_404_when_missing(
    tmp_path: Path,
) -> None:
    service = BootstrapApiService(project_root=tmp_path)
    router = BootstrapApiRouter(service)

    with pytest.raises(ApiError) as exc:
        router.dispatch("/api/governance/reject-transition-chains/benchmark-run-2")

    assert exc.value.status_code == HTTPStatus.NOT_FOUND
    assert exc.value.code == "governance_reject_transition_chain_not_found"


def test_governance_reject_transition_chains_list_endpoint_returns_only_rejected_records(
    tmp_path: Path,
) -> None:
    _write_governance_final_validation_fixtures(
        project_root=tmp_path,
        source_run_id="benchmark-run-1",
        written_at="2026-07-15T00:00:00Z",
        outcome="passed",
    )
    _write_governance_final_validation_fixtures(
        project_root=tmp_path,
        source_run_id="benchmark-run-2",
        written_at="2026-07-16T00:00:00Z",
        outcome="rejected",
    )
    _write_governance_final_validation_fixtures(
        project_root=tmp_path,
        source_run_id="benchmark-run-3",
        written_at="2026-07-14T00:00:00Z",
        outcome="rejected",
    )
    service = BootstrapApiService(project_root=tmp_path)
    router = BootstrapApiRouter(service)

    status, payload = router.dispatch("/api/governance/reject-transition-chains?limit=10")

    assert status == HTTPStatus.OK
    assert payload["_meta"]["returned_count"] == 2
    assert payload["reject_transition_chains"][0]["source_run_id"] == "benchmark-run-2"
    assert payload["reject_transition_chains"][1]["source_run_id"] == "benchmark-run-3"


def test_governance_reject_transition_chain_download_endpoint_returns_aggregated_payload(
    tmp_path: Path,
) -> None:
    source_run_id = "benchmark-run-1"
    validation_id = "validation-1"
    _write_governance_final_validation_fixtures(
        project_root=tmp_path,
        source_run_id=source_run_id,
        outcome="rejected",
        selected_validation_id=validation_id,
    )
    _write_governance_reject_execution_fixtures(
        project_root=tmp_path,
        source_run_id=source_run_id,
        validation_id=validation_id,
    )
    _write_governance_status_transition_fixtures(
        project_root=tmp_path,
        source_run_id=source_run_id,
        validation_id=validation_id,
    )
    service = BootstrapApiService(project_root=tmp_path)
    router = BootstrapApiRouter(service)

    status, response = router.dispatch(
        f"/api/governance/reject-transition-chains/{source_run_id}/download"
    )

    assert status == HTTPStatus.OK
    assert isinstance(response, ApiBinaryResponse)
    payload = json.loads(response.body.decode("utf-8"))
    assert payload["final_validation"]["source_run_id"] == source_run_id
    assert payload["reject_execution"]["validation_id"] == validation_id


def test_governance_candidate_validation_readback_endpoint_returns_record_and_artifact(
    tmp_path: Path,
) -> None:
    source_run_id = "benchmark-run-1"
    validation_id = "validation-1"
    _write_governance_candidate_validation_fixtures(
        project_root=tmp_path,
        source_run_id=source_run_id,
        validation_id=validation_id,
    )
    service = BootstrapApiService(project_root=tmp_path)
    router = BootstrapApiRouter(service)

    status, payload = router.dispatch(
        f"/api/governance/candidate-validations/{validation_id}"
    )

    assert status == HTTPStatus.OK
    assert payload["_meta"]["status"] == "ok"
    assert payload["candidate_validation"]["validation_id"] == validation_id
    assert payload["candidate_validation_artifact"]["validation_id"] == validation_id


def test_governance_candidate_validation_readback_endpoint_returns_404_when_missing(
    tmp_path: Path,
) -> None:
    service = BootstrapApiService(project_root=tmp_path)
    router = BootstrapApiRouter(service)

    with pytest.raises(ApiError) as exc:
        router.dispatch("/api/governance/candidate-validations/validation-missing")

    assert exc.value.status_code == HTTPStatus.NOT_FOUND
    assert exc.value.code == "governance_candidate_validation_not_found"


def test_governance_candidate_validations_list_endpoint_returns_latest_records_for_source_run(
    tmp_path: Path,
) -> None:
    source_run_id = "benchmark-run-1"
    _write_governance_candidate_validation_fixtures(
        project_root=tmp_path,
        source_run_id=source_run_id,
        validation_id="validation-1",
        written_at="2026-07-15T00:00:00Z",
    )
    _write_governance_candidate_validation_fixtures(
        project_root=tmp_path,
        source_run_id=source_run_id,
        validation_id="validation-2",
        written_at="2026-07-16T00:00:00Z",
    )
    _write_governance_candidate_validation_fixtures(
        project_root=tmp_path,
        source_run_id=source_run_id,
        validation_id="validation-3",
        written_at="2026-07-14T00:00:00Z",
    )
    service = BootstrapApiService(project_root=tmp_path)
    router = BootstrapApiRouter(service)

    status, payload = router.dispatch(
        f"/api/governance/candidate-validations?source_run_id={source_run_id}&limit=2"
    )

    assert status == HTTPStatus.OK
    assert payload["_meta"]["returned_count"] == 2
    assert payload["candidate_validations"][0]["validation_id"] == "validation-2"
    assert payload["candidate_validations"][1]["validation_id"] == "validation-1"


def test_governance_candidate_validation_download_endpoint_returns_artifact(
    tmp_path: Path,
) -> None:
    source_run_id = "benchmark-run-1"
    validation_id = "validation-1"
    _write_governance_candidate_validation_fixtures(
        project_root=tmp_path,
        source_run_id=source_run_id,
        validation_id=validation_id,
    )
    service = BootstrapApiService(project_root=tmp_path)
    router = BootstrapApiRouter(service)

    status, response = router.dispatch(
        f"/api/governance/candidate-validations/{validation_id}/download"
    )

    assert status == HTTPStatus.OK
    assert isinstance(response, ApiBinaryResponse)
    payload = json.loads(response.body.decode("utf-8"))
    assert payload["validation_id"] == validation_id


def test_governance_candidate_validation_download_ledger_endpoint_returns_ledger(
    tmp_path: Path,
) -> None:
    source_run_id = "benchmark-run-1"
    validation_id = "validation-1"
    _write_governance_candidate_validation_fixtures(
        project_root=tmp_path,
        source_run_id=source_run_id,
        validation_id=validation_id,
    )
    service = BootstrapApiService(project_root=tmp_path)
    router = BootstrapApiRouter(service)

    status, response = router.dispatch(
        f"/api/governance/candidate-validations/{validation_id}/download-ledger"
    )

    assert status == HTTPStatus.OK
    assert isinstance(response, ApiBinaryResponse)
    payload = json.loads(response.body.decode("utf-8"))
    assert payload["validation_id"] == validation_id


def test_governance_reject_execution_readback_endpoint_returns_record_and_artifact(
    tmp_path: Path,
) -> None:
    source_run_id = "benchmark-run-1"
    validation_id = "validation-1"
    _write_governance_reject_execution_fixtures(
        project_root=tmp_path,
        source_run_id=source_run_id,
        validation_id=validation_id,
    )
    service = BootstrapApiService(project_root=tmp_path)
    router = BootstrapApiRouter(service)

    status, payload = router.dispatch(f"/api/governance/rejections/{validation_id}")

    assert status == HTTPStatus.OK
    assert payload["_meta"]["status"] == "ok"
    assert payload["reject_execution"]["validation_id"] == validation_id
    assert payload["reject_execution_artifact"]["validation_id"] == validation_id


def test_governance_reject_execution_readback_endpoint_returns_404_when_missing(
    tmp_path: Path,
) -> None:
    service = BootstrapApiService(project_root=tmp_path)
    router = BootstrapApiRouter(service)

    with pytest.raises(ApiError) as exc:
        router.dispatch("/api/governance/rejections/validation-missing")

    assert exc.value.status_code == HTTPStatus.NOT_FOUND
    assert exc.value.code == "governance_reject_execution_not_found"


def test_governance_reject_executions_list_endpoint_returns_latest_records(
    tmp_path: Path,
) -> None:
    _write_governance_reject_execution_fixtures(
        project_root=tmp_path,
        source_run_id="benchmark-run-1",
        validation_id="validation-1",
        written_at="2026-07-15T00:00:00Z",
    )
    _write_governance_reject_execution_fixtures(
        project_root=tmp_path,
        source_run_id="benchmark-run-1",
        validation_id="validation-2",
        written_at="2026-07-16T00:00:00Z",
    )
    _write_governance_reject_execution_fixtures(
        project_root=tmp_path,
        source_run_id="benchmark-run-1",
        validation_id="validation-3",
        written_at="2026-07-14T00:00:00Z",
    )
    service = BootstrapApiService(project_root=tmp_path)
    router = BootstrapApiRouter(service)

    status, payload = router.dispatch("/api/governance/rejections?limit=2")

    assert status == HTTPStatus.OK
    assert payload["_meta"]["returned_count"] == 2
    assert payload["reject_executions"][0]["validation_id"] == "validation-2"
    assert payload["reject_executions"][1]["validation_id"] == "validation-1"


def test_governance_reject_execution_download_endpoint_returns_artifact(
    tmp_path: Path,
) -> None:
    source_run_id = "benchmark-run-1"
    validation_id = "validation-1"
    _write_governance_reject_execution_fixtures(
        project_root=tmp_path,
        source_run_id=source_run_id,
        validation_id=validation_id,
    )
    service = BootstrapApiService(project_root=tmp_path)
    router = BootstrapApiRouter(service)

    status, response = router.dispatch(
        f"/api/governance/rejections/{validation_id}/download"
    )

    assert status == HTTPStatus.OK
    assert isinstance(response, ApiBinaryResponse)
    payload = json.loads(response.body.decode("utf-8"))
    assert payload["validation_id"] == validation_id


def test_governance_reject_execution_download_ledger_endpoint_returns_ledger(
    tmp_path: Path,
) -> None:
    source_run_id = "benchmark-run-1"
    validation_id = "validation-1"
    _write_governance_reject_execution_fixtures(
        project_root=tmp_path,
        source_run_id=source_run_id,
        validation_id=validation_id,
    )
    service = BootstrapApiService(project_root=tmp_path)
    router = BootstrapApiRouter(service)

    status, response = router.dispatch(
        f"/api/governance/rejections/{validation_id}/download-ledger"
    )

    assert status == HTTPStatus.OK
    assert isinstance(response, ApiBinaryResponse)
    payload = json.loads(response.body.decode("utf-8"))
    assert payload["validation_id"] == validation_id


def test_governance_status_transition_readback_endpoint_returns_record_and_artifact(
    tmp_path: Path,
) -> None:
    source_run_id = "benchmark-run-1"
    validation_id = "validation-1"
    _write_governance_status_transition_fixtures(
        project_root=tmp_path,
        source_run_id=source_run_id,
        validation_id=validation_id,
    )
    service = BootstrapApiService(project_root=tmp_path)
    router = BootstrapApiRouter(service)

    status, payload = router.dispatch(
        f"/api/governance/status-transitions/{validation_id}"
    )

    assert status == HTTPStatus.OK
    assert payload["_meta"]["status"] == "ok"
    assert payload["status_transition"]["validation_id"] == validation_id
    assert payload["status_transition_artifact"]["validation_id"] == validation_id


def test_governance_status_transition_readback_endpoint_returns_404_when_missing(
    tmp_path: Path,
) -> None:
    service = BootstrapApiService(project_root=tmp_path)
    router = BootstrapApiRouter(service)

    with pytest.raises(ApiError) as exc:
        router.dispatch("/api/governance/status-transitions/validation-missing")

    assert exc.value.status_code == HTTPStatus.NOT_FOUND
    assert exc.value.code == "governance_status_transition_not_found"


def test_governance_status_transitions_list_endpoint_returns_latest_records(
    tmp_path: Path,
) -> None:
    _write_governance_status_transition_fixtures(
        project_root=tmp_path,
        source_run_id="benchmark-run-1",
        validation_id="validation-1",
        written_at="2026-07-15T00:00:00Z",
    )
    _write_governance_status_transition_fixtures(
        project_root=tmp_path,
        source_run_id="benchmark-run-1",
        validation_id="validation-2",
        written_at="2026-07-16T00:00:00Z",
    )
    _write_governance_status_transition_fixtures(
        project_root=tmp_path,
        source_run_id="benchmark-run-1",
        validation_id="validation-3",
        written_at="2026-07-14T00:00:00Z",
    )
    service = BootstrapApiService(project_root=tmp_path)
    router = BootstrapApiRouter(service)

    status, payload = router.dispatch("/api/governance/status-transitions?limit=2")

    assert status == HTTPStatus.OK
    assert payload["_meta"]["returned_count"] == 2
    assert payload["status_transitions"][0]["validation_id"] == "validation-2"
    assert payload["status_transitions"][1]["validation_id"] == "validation-1"


def test_governance_status_transition_download_endpoint_returns_artifact(
    tmp_path: Path,
) -> None:
    source_run_id = "benchmark-run-1"
    validation_id = "validation-1"
    _write_governance_status_transition_fixtures(
        project_root=tmp_path,
        source_run_id=source_run_id,
        validation_id=validation_id,
    )
    service = BootstrapApiService(project_root=tmp_path)
    router = BootstrapApiRouter(service)

    status, response = router.dispatch(
        f"/api/governance/status-transitions/{validation_id}/download"
    )

    assert status == HTTPStatus.OK
    assert isinstance(response, ApiBinaryResponse)
    payload = json.loads(response.body.decode("utf-8"))
    assert payload["validation_id"] == validation_id


def test_governance_status_transition_download_ledger_endpoint_returns_ledger(
    tmp_path: Path,
) -> None:
    source_run_id = "benchmark-run-1"
    validation_id = "validation-1"
    _write_governance_status_transition_fixtures(
        project_root=tmp_path,
        source_run_id=source_run_id,
        validation_id=validation_id,
    )
    service = BootstrapApiService(project_root=tmp_path)
    router = BootstrapApiRouter(service)

    status, response = router.dispatch(
        f"/api/governance/status-transitions/{validation_id}/download-ledger"
    )

    assert status == HTTPStatus.OK
    assert isinstance(response, ApiBinaryResponse)
    payload = json.loads(response.body.decode("utf-8"))
    assert payload["validation_id"] == validation_id


def test_governance_handoff_readback_endpoint_returns_record_and_artifact(
    tmp_path: Path,
) -> None:
    source_run_id = "benchmark-run-1"
    _write_governance_handoff_fixtures(project_root=tmp_path, source_run_id=source_run_id)
    service = BootstrapApiService(project_root=tmp_path)
    router = BootstrapApiRouter(service)

    status, payload = router.dispatch(f"/api/governance/handoffs/{source_run_id}")

    assert status == HTTPStatus.OK
    assert payload["_meta"]["status"] == "ok"
    assert payload["handoff"]["source_run_id"] == source_run_id
    assert payload["handoff_artifact"]["source_run_id"] == source_run_id


def test_governance_handoff_readback_endpoint_returns_404_when_missing(
    tmp_path: Path,
) -> None:
    service = BootstrapApiService(project_root=tmp_path)
    router = BootstrapApiRouter(service)

    with pytest.raises(ApiError) as exc:
        router.dispatch("/api/governance/handoffs/benchmark-run-missing")

    assert exc.value.status_code == HTTPStatus.NOT_FOUND
    assert exc.value.code == "governance_handoff_not_found"


def test_governance_handoffs_list_endpoint_returns_latest_records(
    tmp_path: Path,
) -> None:
    _write_governance_handoff_fixtures(
        project_root=tmp_path,
        source_run_id="benchmark-run-1",
        written_at="2026-07-15T00:00:00Z",
    )
    _write_governance_handoff_fixtures(
        project_root=tmp_path,
        source_run_id="benchmark-run-2",
        written_at="2026-07-16T00:00:00Z",
    )
    _write_governance_handoff_fixtures(
        project_root=tmp_path,
        source_run_id="benchmark-run-3",
        written_at="2026-07-14T00:00:00Z",
    )
    service = BootstrapApiService(project_root=tmp_path)
    router = BootstrapApiRouter(service)

    status, payload = router.dispatch("/api/governance/handoffs?limit=2")

    assert status == HTTPStatus.OK
    assert payload["_meta"]["returned_count"] == 2
    assert payload["handoffs"][0]["source_run_id"] == "benchmark-run-2"
    assert payload["handoffs"][1]["source_run_id"] == "benchmark-run-1"


def test_governance_handoff_download_endpoint_returns_artifact(
    tmp_path: Path,
) -> None:
    source_run_id = "benchmark-run-1"
    _write_governance_handoff_fixtures(project_root=tmp_path, source_run_id=source_run_id)
    service = BootstrapApiService(project_root=tmp_path)
    router = BootstrapApiRouter(service)

    status, response = router.dispatch(f"/api/governance/handoffs/{source_run_id}/download")

    assert status == HTTPStatus.OK
    assert isinstance(response, ApiBinaryResponse)
    payload = json.loads(response.body.decode("utf-8"))
    assert payload["source_run_id"] == source_run_id


def test_governance_handoff_download_ledger_endpoint_returns_ledger(
    tmp_path: Path,
) -> None:
    source_run_id = "benchmark-run-1"
    _write_governance_handoff_fixtures(project_root=tmp_path, source_run_id=source_run_id)
    service = BootstrapApiService(project_root=tmp_path)
    router = BootstrapApiRouter(service)

    status, response = router.dispatch(
        f"/api/governance/handoffs/{source_run_id}/download-ledger"
    )

    assert status == HTTPStatus.OK
    assert isinstance(response, ApiBinaryResponse)
    payload = json.loads(response.body.decode("utf-8"))
    assert payload["source_run_id"] == source_run_id


def test_governance_index_endpoint_returns_availability_and_links(
    tmp_path: Path,
) -> None:
    _write_governance_handoff_fixtures(
        project_root=tmp_path,
        source_run_id="benchmark-run-1",
        written_at="2026-07-15T00:00:00Z",
    )
    _write_governance_final_validation_fixtures(
        project_root=tmp_path,
        source_run_id="benchmark-run-1",
        written_at="2026-07-15T00:00:00Z",
        outcome="passed",
        selected_validation_id="validation-1",
    )
    _write_governance_candidate_validation_fixtures(
        project_root=tmp_path,
        source_run_id="benchmark-run-1",
        validation_id="validation-1",
        written_at="2026-07-15T00:00:00Z",
        outcome="passed",
    )

    _write_governance_handoff_fixtures(
        project_root=tmp_path,
        source_run_id="benchmark-run-2",
        written_at="2026-07-16T00:00:00Z",
    )
    _write_governance_final_validation_fixtures(
        project_root=tmp_path,
        source_run_id="benchmark-run-2",
        written_at="2026-07-16T00:00:00Z",
        outcome="rejected",
        selected_validation_id="validation-2",
    )
    _write_governance_candidate_validation_fixtures(
        project_root=tmp_path,
        source_run_id="benchmark-run-2",
        validation_id="validation-2",
        written_at="2026-07-16T00:00:00Z",
        outcome="rejected",
    )
    _write_governance_reject_execution_fixtures(
        project_root=tmp_path,
        source_run_id="benchmark-run-2",
        validation_id="validation-2",
        written_at="2026-07-16T00:00:00Z",
    )
    _write_governance_status_transition_fixtures(
        project_root=tmp_path,
        source_run_id="benchmark-run-2",
        validation_id="validation-2",
        written_at="2026-07-16T00:00:00Z",
    )

    service = BootstrapApiService(project_root=tmp_path)
    router = BootstrapApiRouter(service)

    status, payload = router.dispatch("/api/governance/index?limit=2")

    assert status == HTTPStatus.OK
    assert payload["_meta"]["returned_count"] == 2
    assert payload["governance_index"][0]["source_run_id"] == "benchmark-run-2"
    assert payload["governance_index"][1]["source_run_id"] == "benchmark-run-1"

    run2 = payload["governance_index"][0]
    assert run2["handoff"]["available"] is True
    assert run2["final_validation"]["available"] is True
    assert run2["final_validation"]["outcome"] == "rejected"
    assert run2["selected_candidate_validation"]["available"] is True
    assert run2["reject_execution"]["available"] is True
    assert run2["status_transition"]["available"] is True
    assert run2["reject_transition_chain"]["available"] is True
    assert run2["handoff"]["url"] == "/api/governance/handoffs/benchmark-run-2"
    assert (
        run2["final_validation"]["url"]
        == "/api/governance/final-validations/benchmark-run-2"
    )
    assert (
        run2["reject_execution"]["url"]
        == "/api/governance/rejections/validation-2"
    )
    assert (
        run2["status_transition"]["url"]
        == "/api/governance/status-transitions/validation-2"
    )

    run1 = payload["governance_index"][1]
    assert run1["handoff"]["available"] is True
    assert run1["final_validation"]["available"] is True
    assert run1["final_validation"]["outcome"] == "passed"
    assert run1["selected_candidate_validation"]["available"] is True
    assert run1["reject_execution"]["available"] is False
    assert run1["status_transition"]["available"] is False
    assert run1["reject_transition_chain"]["available"] is True


def test_governance_index_endpoint_marks_missing_artifact_as_unavailable(
    tmp_path: Path,
) -> None:
    source_run_id = "benchmark-run-1"
    _write_governance_handoff_fixtures(project_root=tmp_path, source_run_id=source_run_id)
    artifact_path = (
        tmp_path
        / f"var/artifacts/governance_handoffs/{source_run_id}/governance_handoff_bundle.json"
    )
    artifact_path.unlink()

    service = BootstrapApiService(project_root=tmp_path)
    router = BootstrapApiRouter(service)

    status, payload = router.dispatch("/api/governance/index?limit=10")

    assert status == HTTPStatus.OK
    assert payload["_meta"]["returned_count"] == 1
    assert payload["governance_index"][0]["source_run_id"] == source_run_id
    assert payload["governance_index"][0]["handoff"]["available"] is False
