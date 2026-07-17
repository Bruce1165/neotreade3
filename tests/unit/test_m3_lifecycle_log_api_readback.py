from __future__ import annotations

import hashlib
import json
from http import HTTPStatus
from pathlib import Path

import pytest

from apps.api.main import BootstrapApiService
from apps.api.router import BootstrapApiRouter
from apps.api.shared import ApiBinaryResponse, ApiError


def _write_lifecycle_log_fixtures(
    *,
    project_root: Path,
    record_id: str,
    written_at: str,
    stock_code: str = "300001",
    run_id: str = "2026-06-20",
) -> None:
    artifact_rel = f"var/artifacts/m3_lifecycle_logs/{record_id}/lifecycle_log.json"
    ledger_rel = f"var/ledgers/m3_lifecycle_logs/{record_id}/lifecycle_log.json"
    artifact_path = project_root / artifact_rel
    ledger_path = project_root / ledger_rel
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)

    artifact_payload = {
        "object_type": "decision_lifecycle_log",
        "object_version": 2,
        "stock_code": stock_code,
        "run_id": run_id,
        "source_run_id": run_id,
        "events": [
            {
                "object_type": "decision_lifecycle_event",
                "object_version": 2,
                "stock_code": stock_code,
                "trade_date": "2026-06-20",
                "run_id": run_id,
                "source_run_id": run_id,
                "event": "market_exit_confirmed",
                "source_layer": "sell",
                "stage": "exit_ready",
                "decision": "exit",
                "exit_scope": "portfolio",
                "details": "",
                "position_contract_snapshot": {},
                "evidence_ref": {},
            }
        ],
    }
    artifact_text = (
        json.dumps(artifact_payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    )
    artifact_sha256 = hashlib.sha256(artifact_text.encode("utf-8")).hexdigest()
    artifact_path.write_text(artifact_text, encoding="utf-8")

    ledger_path.write_text(
        json.dumps(
            {
                "record_id": record_id,
                "written_at": written_at,
                "stock_code": stock_code,
                "run_id": run_id,
                "source_run_id": run_id,
                "events_count": 1,
                "first_trade_date": "2026-06-20",
                "last_trade_date": "2026-06-20",
                "last_event": "market_exit_confirmed",
                "last_stage": "exit_ready",
                "last_decision": "exit",
                "last_exit_scope": "portfolio",
                "artifact_sha256": artifact_sha256,
                "artifact_path": artifact_rel,
                "ledger_path": ledger_rel,
            },
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def test_m3_lifecycle_logs_list_endpoint_returns_records_sorted_and_limited(
    tmp_path: Path,
) -> None:
    _write_lifecycle_log_fixtures(
        project_root=tmp_path,
        record_id="300001-2026-06-19",
        written_at="2026-06-19T00:00:00Z",
    )
    _write_lifecycle_log_fixtures(
        project_root=tmp_path,
        record_id="300001-2026-06-20",
        written_at="2026-06-20T00:00:00Z",
    )

    service = BootstrapApiService(project_root=tmp_path)
    router = BootstrapApiRouter(service)

    status, payload = router.dispatch("/api/m3/lifecycle-logs?limit=20")

    assert status == HTTPStatus.OK
    assert payload["_meta"]["returned_count"] == 2
    assert payload["_meta"]["matched_count"] == 2
    assert payload["_meta"]["limit"] == 20
    assert payload["_meta"]["offset"] == 0
    assert [item["record_id"] for item in payload["lifecycle_logs"]] == [
        "300001-2026-06-20",
        "300001-2026-06-19",
    ]

    status, payload = router.dispatch("/api/m3/lifecycle-logs?limit=1")
    assert status == HTTPStatus.OK
    assert payload["_meta"]["returned_count"] == 1
    assert payload["_meta"]["matched_count"] == 2
    assert payload["_meta"]["limit"] == 1
    assert payload["_meta"]["offset"] == 0
    assert [item["record_id"] for item in payload["lifecycle_logs"]] == [
        "300001-2026-06-20"
    ]

    status, payload = router.dispatch("/api/m3/lifecycle-logs?limit=1&offset=1")
    assert status == HTTPStatus.OK
    assert payload["_meta"]["returned_count"] == 1
    assert payload["_meta"]["matched_count"] == 2
    assert payload["_meta"]["limit"] == 1
    assert payload["_meta"]["offset"] == 1
    assert [item["record_id"] for item in payload["lifecycle_logs"]] == [
        "300001-2026-06-19"
    ]

    status, payload = router.dispatch("/api/m3/lifecycle-logs?limit=1&offset=2")
    assert status == HTTPStatus.OK
    assert payload["_meta"]["returned_count"] == 0
    assert payload["_meta"]["matched_count"] == 2
    assert payload["_meta"]["limit"] == 1
    assert payload["_meta"]["offset"] == 2
    assert payload["lifecycle_logs"] == []


def test_m3_lifecycle_log_readback_endpoint_returns_payload(tmp_path: Path) -> None:
    _write_lifecycle_log_fixtures(
        project_root=tmp_path,
        record_id="300001-2026-06-20",
        written_at="2026-06-20T00:00:00Z",
    )
    service = BootstrapApiService(project_root=tmp_path)
    router = BootstrapApiRouter(service)

    status, payload = router.dispatch("/api/m3/lifecycle-logs/300001-2026-06-20")

    assert status == HTTPStatus.OK
    assert payload["_meta"]["status"] == "ok"
    assert payload["lifecycle_log"]["record_id"] == "300001-2026-06-20"
    assert payload["lifecycle_log_payload"]["object_type"] == "decision_lifecycle_log"
    assert payload["lifecycle_log_artifact"]["object_type"] == "decision_lifecycle_log"


def test_m3_lifecycle_log_download_endpoint_returns_attachment(tmp_path: Path) -> None:
    _write_lifecycle_log_fixtures(
        project_root=tmp_path,
        record_id="300001-2026-06-20",
        written_at="2026-06-20T00:00:00Z",
    )
    service = BootstrapApiService(project_root=tmp_path)
    router = BootstrapApiRouter(service)

    status, response = router.dispatch("/api/m3/lifecycle-logs/300001-2026-06-20/download")

    assert status == HTTPStatus.OK
    assert isinstance(response, ApiBinaryResponse)
    assert "attachment" in response.headers.get("Content-Disposition", "")
    payload = json.loads(response.body.decode("utf-8"))
    assert payload["object_type"] == "decision_lifecycle_log"
    assert payload["stock_code"] == "300001"


def test_m3_lifecycle_log_download_ledger_endpoint_returns_attachment(
    tmp_path: Path,
) -> None:
    _write_lifecycle_log_fixtures(
        project_root=tmp_path,
        record_id="300001-2026-06-20",
        written_at="2026-06-20T00:00:00Z",
    )
    service = BootstrapApiService(project_root=tmp_path)
    router = BootstrapApiRouter(service)

    status, response = router.dispatch(
        "/api/m3/lifecycle-logs/300001-2026-06-20/download-ledger"
    )

    assert status == HTTPStatus.OK
    assert isinstance(response, ApiBinaryResponse)
    assert "attachment" in response.headers.get("Content-Disposition", "")
    payload = json.loads(response.body.decode("utf-8"))
    assert payload["record_id"] == "300001-2026-06-20"
    assert "artifact_path" in payload


def test_m3_lifecycle_log_readback_endpoint_returns_400_for_path_traversal_record_id(
    tmp_path: Path,
) -> None:
    service = BootstrapApiService(project_root=tmp_path)
    router = BootstrapApiRouter(service)

    with pytest.raises(ApiError) as exc:
        router.dispatch("/api/m3/lifecycle-logs/..")

    assert exc.value.status_code == HTTPStatus.BAD_REQUEST
    assert exc.value.code == "invalid_record_id"


def test_m3_lifecycle_logs_list_endpoint_filters_by_run_id(tmp_path: Path) -> None:
    _write_lifecycle_log_fixtures(
        project_root=tmp_path,
        record_id="300001-run_a",
        written_at="2026-06-20T00:00:00Z",
        stock_code="300001",
        run_id="run_a",
    )
    _write_lifecycle_log_fixtures(
        project_root=tmp_path,
        record_id="300002-run_a",
        written_at="2026-06-19T00:00:00Z",
        stock_code="300002",
        run_id="run_a",
    )
    _write_lifecycle_log_fixtures(
        project_root=tmp_path,
        record_id="300003-run_b",
        written_at="2026-06-21T00:00:00Z",
        stock_code="300003",
        run_id="run_b",
    )

    service = BootstrapApiService(project_root=tmp_path)
    router = BootstrapApiRouter(service)

    status, payload = router.dispatch("/api/m3/lifecycle-logs?run_id=run_a&limit=20")
    assert status == HTTPStatus.OK
    assert payload["_meta"]["run_id"] == "run_a"
    assert payload["_meta"]["returned_count"] == 2
    assert payload["_meta"]["matched_count"] == 2
    assert payload["_meta"]["limit"] == 20
    assert payload["_meta"]["offset"] == 0
    assert [item["record_id"] for item in payload["lifecycle_logs"]] == [
        "300001-run_a",
        "300002-run_a",
    ]
    for item in payload["lifecycle_logs"]:
        assert item["run_id"] == "run_a"


def test_m3_lifecycle_logs_list_endpoint_returns_400_for_invalid_run_id(
    tmp_path: Path,
) -> None:
    service = BootstrapApiService(project_root=tmp_path)
    router = BootstrapApiRouter(service)

    with pytest.raises(ApiError) as exc:
        router.dispatch("/api/m3/lifecycle-logs?run_id=..")

    assert exc.value.status_code == HTTPStatus.BAD_REQUEST
    assert exc.value.code == "invalid_run_id"

    with pytest.raises(ApiError) as exc:
        router.dispatch("/api/m3/lifecycle-logs?run_id=%20")

    assert exc.value.status_code == HTTPStatus.BAD_REQUEST
    assert exc.value.code == "invalid_run_id"


def test_m3_lifecycle_logs_list_endpoint_returns_400_for_invalid_offset(
    tmp_path: Path,
) -> None:
    service = BootstrapApiService(project_root=tmp_path)
    router = BootstrapApiRouter(service)

    with pytest.raises(ApiError) as exc:
        router.dispatch("/api/m3/lifecycle-logs?offset=-1")

    assert exc.value.status_code == HTTPStatus.BAD_REQUEST
    assert exc.value.code == "invalid_offset"

    with pytest.raises(ApiError) as exc:
        router.dispatch("/api/m3/lifecycle-logs?offset=abc")

    assert exc.value.status_code == HTTPStatus.BAD_REQUEST
    assert exc.value.code == "invalid_offset"


def test_m3_lifecycle_logs_list_endpoint_fails_closed_when_invalid_json_exists(
    tmp_path: Path,
) -> None:
    record_id = "300001-2026-06-20"
    ledger_path = (
        tmp_path / f"var/ledgers/m3_lifecycle_logs/{record_id}/lifecycle_log.json"
    )
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.write_text("{", encoding="utf-8")

    service = BootstrapApiService(project_root=tmp_path)
    router = BootstrapApiRouter(service)

    with pytest.raises(ApiError) as exc:
        router.dispatch("/api/m3/lifecycle-logs")

    assert exc.value.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert exc.value.code == "m3_lifecycle_log_ledger_invalid"
