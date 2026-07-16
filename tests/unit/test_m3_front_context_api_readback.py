from __future__ import annotations

import json
from http import HTTPStatus
from pathlib import Path

import pytest

from apps.api.main import BootstrapApiService
from apps.api.router import BootstrapApiRouter
from apps.api.shared import ApiBinaryResponse, ApiError


def _write_front_context_fixtures(
    *,
    project_root: Path,
    record_id: str,
    written_at: str,
) -> None:
    artifact_rel = f"var/artifacts/m3_front_contexts/{record_id}/front_context.json"
    ledger_rel = f"var/ledgers/m3_front_contexts/{record_id}/front_context.json"
    artifact_path = project_root / artifact_rel
    ledger_path = project_root / ledger_rel
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)

    artifact_path.write_text(
        json.dumps(
            {
                "object_type": "m3_front_context",
                "object_version": 1,
                "record_id": record_id,
                "written_at": written_at,
                "m1_constraints_ref": {},
                "identify_state": {},
                "tracking_state": {},
                "entry_state": {},
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
                "record_id": record_id,
                "written_at": written_at,
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


def test_m3_front_contexts_list_endpoint_returns_records_sorted_and_limited(
    tmp_path: Path,
) -> None:
    _write_front_context_fixtures(
        project_root=tmp_path,
        record_id="600000-2026-07-06",
        written_at="2026-07-06T00:00:00Z",
    )
    _write_front_context_fixtures(
        project_root=tmp_path,
        record_id="600000-2026-07-07",
        written_at="2026-07-07T00:00:00Z",
    )

    service = BootstrapApiService(project_root=tmp_path)
    router = BootstrapApiRouter(service)

    status, payload = router.dispatch("/api/m3/front-contexts?limit=20")

    assert status == HTTPStatus.OK
    assert payload["_meta"]["returned_count"] == 2
    assert [item["record_id"] for item in payload["front_contexts"]] == [
        "600000-2026-07-07",
        "600000-2026-07-06",
    ]

    status, payload = router.dispatch("/api/m3/front-contexts?limit=1")
    assert status == HTTPStatus.OK
    assert payload["_meta"]["returned_count"] == 1
    assert [item["record_id"] for item in payload["front_contexts"]] == [
        "600000-2026-07-07"
    ]


def test_m3_front_context_readback_endpoint_returns_payload(
    tmp_path: Path,
) -> None:
    _write_front_context_fixtures(
        project_root=tmp_path,
        record_id="600000-2026-07-07",
        written_at="2026-07-07T00:00:00Z",
    )
    service = BootstrapApiService(project_root=tmp_path)
    router = BootstrapApiRouter(service)

    status, payload = router.dispatch("/api/m3/front-contexts/600000-2026-07-07")

    assert status == HTTPStatus.OK
    assert payload["_meta"]["status"] == "ok"
    assert payload["front_context"]["record_id"] == "600000-2026-07-07"
    assert payload["front_context_payload"]["object_type"] == "m3_front_context"
    assert payload["front_context_artifact"]["object_type"] == "m3_front_context"


def test_m3_front_context_download_endpoint_returns_attachment(
    tmp_path: Path,
) -> None:
    _write_front_context_fixtures(
        project_root=tmp_path,
        record_id="600000-2026-07-07",
        written_at="2026-07-07T00:00:00Z",
    )
    service = BootstrapApiService(project_root=tmp_path)
    router = BootstrapApiRouter(service)

    status, response = router.dispatch("/api/m3/front-contexts/600000-2026-07-07/download")

    assert status == HTTPStatus.OK
    assert isinstance(response, ApiBinaryResponse)
    assert "attachment" in response.headers.get("Content-Disposition", "")
    payload = json.loads(response.body.decode("utf-8"))
    assert payload["object_type"] == "m3_front_context"
    assert payload["record_id"] == "600000-2026-07-07"


def test_m3_front_context_download_ledger_endpoint_returns_attachment(
    tmp_path: Path,
) -> None:
    _write_front_context_fixtures(
        project_root=tmp_path,
        record_id="600000-2026-07-07",
        written_at="2026-07-07T00:00:00Z",
    )
    service = BootstrapApiService(project_root=tmp_path)
    router = BootstrapApiRouter(service)

    status, response = router.dispatch(
        "/api/m3/front-contexts/600000-2026-07-07/download-ledger"
    )

    assert status == HTTPStatus.OK
    assert isinstance(response, ApiBinaryResponse)
    assert "attachment" in response.headers.get("Content-Disposition", "")
    payload = json.loads(response.body.decode("utf-8"))
    assert payload["record_id"] == "600000-2026-07-07"
    assert "artifact_path" in payload


def test_m3_front_context_readback_endpoint_returns_400_for_path_traversal_record_id(
    tmp_path: Path,
) -> None:
    service = BootstrapApiService(project_root=tmp_path)
    router = BootstrapApiRouter(service)

    with pytest.raises(ApiError) as exc:
        router.dispatch("/api/m3/front-contexts/..")

    assert exc.value.status_code == HTTPStatus.BAD_REQUEST
    assert exc.value.code == "invalid_record_id"


def test_m3_front_contexts_list_endpoint_fails_closed_when_invalid_json_exists(
    tmp_path: Path,
) -> None:
    record_id = "600000-2026-07-07"
    ledger_path = (
        tmp_path / f"var/ledgers/m3_front_contexts/{record_id}/front_context.json"
    )
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.write_text("{", encoding="utf-8")

    service = BootstrapApiService(project_root=tmp_path)
    router = BootstrapApiRouter(service)

    with pytest.raises(ApiError) as exc:
        router.dispatch("/api/m3/front-contexts")

    assert exc.value.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert exc.value.code == "m3_front_context_ledger_invalid"

