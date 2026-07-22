from __future__ import annotations

from contextlib import contextmanager
from datetime import date
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import shutil
import sqlite3
from threading import Thread
from urllib.request import Request, urlopen

from apps.api.main import BootstrapApiService, build_handler


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class _FastLabAdapter:
    def run_job(self, *, task_id, target_date, lab_id, project_root):
        return {
            "task_id": task_id,
            "lab_id": lab_id,
            "status": "skipped",
            "message": "integration fast stub",
            "target_date": (
                target_date.isoformat() if hasattr(target_date, "isoformat") else str(target_date)
            ),
            "artifacts": [],
        }


def _install_fast_lab_runtime(service: BootstrapApiService) -> None:
    service.worker_app._get_lab_adapter = lambda: _FastLabAdapter()


@contextmanager
def _serve(service: BootstrapApiService):
    server = ThreadingHTTPServer(("127.0.0.1", 0), build_handler(service))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def _read_json(url: str, *, origin: str | None = None) -> tuple[int, dict[str, str], dict]:
    headers = {}
    if origin:
        headers["Origin"] = origin
    request = Request(url, headers=headers)
    with urlopen(request, timeout=10) as response:
        status = int(getattr(response, "status", 200))
        body = json.loads(response.read().decode("utf-8"))
        return status, dict(response.headers.items()), body


def _post_json(
    url: str,
    payload: dict,
    *,
    origin: str | None = None,
) -> tuple[int, dict[str, str], dict]:
    headers = {"Content-Type": "application/json"}
    if origin:
        headers["Origin"] = origin
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urlopen(request, timeout=10) as response:
        status = int(getattr(response, "status", 200))
        body = json.loads(response.read().decode("utf-8"))
        return status, dict(response.headers.items()), body


def _read_bytes(url: str) -> tuple[int, dict[str, str], bytes]:
    request = Request(url)
    with urlopen(request, timeout=10) as response:
        status = int(getattr(response, "status", 200))
        return status, dict(response.headers.items()), response.read()


def _prepare_seeded_project_root(tmp_path: Path) -> Path:
    """构造带最小种子数据的临时项目根：让 bootstrap 主链在无真实行情库的环境（如 CI）也可复现。"""
    for relative_path in (
        Path("config/labs/labs_registry.json"),
        Path("config/orchestrator/daily_master_orchestrator.json"),
        Path("config/data_control/source_registry.json"),
    ):
        destination = tmp_path / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(PROJECT_ROOT / relative_path, destination)
    shutil.copytree(
        PROJECT_ROOT / "config/benchmark",
        tmp_path / "config/benchmark",
    )

    db_dir = tmp_path / "var/db"
    db_dir.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(db_dir / "stock_data.db")) as conn:
        conn.execute(
            """
            CREATE TABLE daily_prices (
                trade_date TEXT NOT NULL,
                code TEXT NOT NULL,
                open REAL, high REAL, low REAL, close REAL,
                preclose REAL, pct_change REAL, volume REAL, amount REAL,
                PRIMARY KEY (trade_date, code)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE stocks (
                code TEXT PRIMARY KEY,
                name TEXT,
                sector_lv1 TEXT,
                sector_lv2 TEXT,
                asset_type TEXT,
                is_delisted INTEGER,
                circulating_market_cap REAL
            )
            """
        )
        conn.executemany(
            "INSERT INTO stocks VALUES (?,?,?,?,?,?,?)",
            [
                ("000001", "平安银行", "金融", "银行", "stock", 0, 2.0e11),
                ("000002", "万科A", "地产", "房地产开发", "stock", 0, 1.0e11),
            ],
        )
        # 单位校验要求：pct_change 为百分制、volume 为股数（amount/volume ≈ close）
        conn.executemany(
            "INSERT INTO daily_prices VALUES (?,?,?,?,?,?,?,?,?,?)",
            [
                ("2026-05-19", "000001", 10.0, 10.6, 9.9, 10.5, 10.0, 5.0, 1_000_000.0, 10_500_000.0),
                ("2026-05-19", "000002", 20.0, 20.5, 19.5, 20.4, 20.0, 2.0, 500_000.0, 10_200_000.0),
                ("2026-05-18", "000001", 9.8, 10.1, 9.7, 10.0, 9.8, 2.04, 900_000.0, 9_000_000.0),
            ],
        )
    return tmp_path


def test_http_smoke_healthz_allows_local_cors() -> None:
    service = BootstrapApiService(project_root=PROJECT_ROOT)

    with _serve(service) as server:
        status, headers, payload = _read_json(
            f"http://127.0.0.1:{server.server_port}/healthz",
            origin="http://localhost:5173",
        )

    assert status == 200
    assert headers.get("Access-Control-Allow-Origin") == "http://localhost:5173"
    assert payload.get("status") == "ok"


def test_http_smoke_bootstrap_summary_reads_stored_snapshot(tmp_path: Path) -> None:
    service = BootstrapApiService(project_root=_prepare_seeded_project_root(tmp_path))
    service.worker_app.paths["ledgers_root"] = tmp_path / "ledgers"
    service.worker_app.paths["artifacts_root"] = tmp_path / "artifacts"
    _install_fast_lab_runtime(service)

    service.worker_app.run(
        target_date=date(2026, 5, 19),
        publish_succeeded=False,
        write_outputs=True,
        requested_by="integration.http_smoke",
    )

    with _serve(service) as server:
        status, _, payload = _read_json(
            f"http://127.0.0.1:{server.server_port}/api/bootstrap-summary?date=2026-05-19"
        )

    assert status == 200
    assert payload.get("target_date") == "2026-05-19"
    assert payload.get("publish_succeeded") is True
    assert payload.get("summary", {}).get("planned_task_count") == 10
    assert payload.get("_meta", {}).get("self_heal") == "none"


def test_http_smoke_orchestration_run_round_trip(tmp_path: Path, monkeypatch) -> None:
    service = BootstrapApiService(project_root=PROJECT_ROOT)

    orchestrator_ledger_dir = tmp_path / "ledgers" / "orchestration_runs"
    orchestrator_artifact_dir = tmp_path / "artifacts" / "orchestration_runs"

    monkeypatch.setattr(service, "require_trading_day", lambda **_kwargs: None)
    monkeypatch.setattr(
        service,
        "_materialize_lab_runs_from_snapshot",
        lambda **_kwargs: None,
    )

    def fake_run(*, target_date, publish_succeeded, write_outputs, requested_by, dry_run):
        assert target_date.isoformat() == "2026-05-20"
        assert publish_succeeded is True
        assert write_outputs is False
        assert requested_by == "integration.http_smoke"
        assert dry_run is False
        return {
            "target_date": "2026-05-20",
            "publish_succeeded": True,
            "requested_publish_succeeded": True,
            "orchestration": {
                "task_results": [
                    {
                        "task_id": "data_control.capture",
                        "phase": "data_control",
                        "status": "ok",
                        "message": "capture completed",
                    },
                    {
                        "task_id": "data_control.publish",
                        "phase": "data_control",
                        "status": "ok",
                        "message": "publish completed",
                    },
                ]
            },
        }

    monkeypatch.setattr(service.worker_app, "run", fake_run)
    monkeypatch.setattr(
        service,
        "_orchestration_run_paths",
        lambda *, target_date: (
            orchestrator_ledger_dir / target_date / "orchestrator_run.json",
            orchestrator_artifact_dir / target_date / "orchestrator_result.json",
        ),
    )

    with _serve(service) as server:
        status, _, post_payload = _post_json(
            f"http://127.0.0.1:{server.server_port}/api/orchestration/run",
            {
                "date": "2026-05-20",
                "publish_succeeded": True,
                "requested_by": "integration.http_smoke",
            },
        )
        detail_status, _, detail_payload = _read_json(
            f"http://127.0.0.1:{server.server_port}/api/orchestration/runs/2026-05-20"
        )
        download_status, download_headers, download_body = _read_bytes(
            f"http://127.0.0.1:{server.server_port}/api/orchestration/runs/2026-05-20/download"
        )

    assert status == 200
    assert post_payload.get("_meta", {}).get("status") == "ok"
    post_run = post_payload.get("orchestrator_run", {})
    assert post_run.get("target_date") == "2026-05-20"
    assert post_run.get("publish_succeeded") is True
    assert post_run.get("requested_publish_succeeded") is True
    assert post_run.get("status_counts") == {"ok": 2}

    ledger_path = orchestrator_ledger_dir / "2026-05-20" / "orchestrator_run.json"
    artifact_path = orchestrator_artifact_dir / "2026-05-20" / "orchestrator_result.json"
    assert ledger_path.exists()
    assert artifact_path.exists()

    stored_ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    stored_artifact = json.loads(artifact_path.read_text(encoding="utf-8"))

    assert detail_status == 200
    assert detail_payload.get("_meta", {}).get("status") == "ok"
    assert detail_payload.get("orchestrator_run") == stored_ledger
    assert detail_payload.get("orchestrator_result") == stored_artifact
    assert detail_payload.get("orchestrator_run") == post_run

    assert download_status == 200
    assert (
        download_headers.get("Content-Disposition")
        == 'attachment; filename="orchestrator_result.json"'
    )
    assert json.loads(download_body.decode("utf-8")) == stored_artifact


def test_http_smoke_governance_reject_orchestration_run_round_trip(
    tmp_path: Path, monkeypatch
) -> None:
    service = BootstrapApiService(project_root=PROJECT_ROOT)

    orchestrator_ledger_dir = tmp_path / "ledgers" / "orchestration_runs"
    orchestrator_artifact_dir = tmp_path / "artifacts" / "orchestration_runs"

    def fake_run_governance_reject_on_demand(
        *,
        target_date,
        source_run_id,
        validation_id,
        requested_by,
        dry_run,
    ):
        assert target_date.isoformat() == "2026-05-20"
        assert source_run_id == "benchmark-run-1"
        assert validation_id == "validation-1"
        assert requested_by == "integration.http_smoke"
        assert dry_run is False
        return {
            "status": "ok",
            "target_date": "2026-05-20",
            "orchestration": {
                "task_results": [
                    {
                        "task_id": "governance.reject_execution",
                        "phase": "governance",
                        "status": "ok",
                        "message": "reject execution materialized successfully",
                        "details": {
                            "source_run_id": source_run_id,
                            "validation_id": validation_id,
                        },
                    }
                ]
            },
        }

    monkeypatch.setattr(
        service.worker_app,
        "run_governance_reject_on_demand",
        fake_run_governance_reject_on_demand,
    )
    monkeypatch.setattr(
        service,
        "_orchestration_run_paths",
        lambda *, target_date: (
            orchestrator_ledger_dir / target_date / "orchestrator_run.json",
            orchestrator_artifact_dir / target_date / "orchestrator_result.json",
        ),
    )

    with _serve(service) as server:
        status, _, post_payload = _post_json(
            f"http://127.0.0.1:{server.server_port}/api/orchestration/run",
            {
                "date": "2026-05-20",
                "mode": "governance_reject",
                "source_run_id": "benchmark-run-1",
                "validation_id": "validation-1",
                "requested_by": "integration.http_smoke",
            },
        )
        detail_status, _, detail_payload = _read_json(
            f"http://127.0.0.1:{server.server_port}/api/orchestration/runs/2026-05-20"
        )
        download_status, download_headers, download_body = _read_bytes(
            f"http://127.0.0.1:{server.server_port}/api/orchestration/runs/2026-05-20/download"
        )

    assert status == 200
    assert post_payload.get("_meta", {}).get("status") == "ok"
    post_run = post_payload.get("orchestrator_run", {})
    assert post_run.get("target_date") == "2026-05-20"
    assert post_run.get("mode") == "governance_reject"
    assert post_run.get("status_counts") == {"ok": 1}

    ledger_path = orchestrator_ledger_dir / "2026-05-20" / "orchestrator_run.json"
    artifact_path = orchestrator_artifact_dir / "2026-05-20" / "orchestrator_result.json"
    assert ledger_path.exists()
    assert artifact_path.exists()

    stored_ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    stored_artifact = json.loads(artifact_path.read_text(encoding="utf-8"))

    assert stored_ledger.get("mode") == "governance_reject"
    assert stored_artifact.get("mode") == "governance_reject"
    assert stored_artifact.get("tasks", [])[0].get("task_id") == "governance.reject_execution"
    assert (
        stored_artifact.get("tasks", [])[0].get("details", {}).get("validation_id")
        == "validation-1"
    )

    assert detail_status == 200
    assert detail_payload.get("_meta", {}).get("status") == "ok"
    assert detail_payload.get("orchestrator_run") == stored_ledger
    assert detail_payload.get("orchestrator_result") == stored_artifact
    assert detail_payload.get("orchestrator_run") == post_run

    assert download_status == 200
    assert (
        download_headers.get("Content-Disposition")
        == 'attachment; filename="orchestrator_result.json"'
    )
    assert json.loads(download_body.decode("utf-8")) == stored_artifact


def test_http_smoke_governance_status_transition_orchestration_run_round_trip(
    tmp_path: Path, monkeypatch
) -> None:
    service = BootstrapApiService(project_root=PROJECT_ROOT)

    orchestrator_ledger_dir = tmp_path / "ledgers" / "orchestration_runs"
    orchestrator_artifact_dir = tmp_path / "artifacts" / "orchestration_runs"

    def fake_run_governance_status_transition_on_demand(
        *,
        target_date,
        source_run_id,
        validation_id,
        requested_by,
        dry_run,
    ):
        assert target_date.isoformat() == "2026-05-20"
        assert source_run_id == "benchmark-run-1"
        assert validation_id == "validation-1"
        assert requested_by == "integration.http_smoke"
        assert dry_run is False
        return {
            "status": "ok",
            "target_date": "2026-05-20",
            "orchestration": {
                "task_results": [
                    {
                        "task_id": "governance.status_transition",
                        "phase": "governance",
                        "status": "ok",
                        "message": "status transition materialized successfully",
                        "details": {
                            "source_run_id": source_run_id,
                            "validation_id": validation_id,
                        },
                    }
                ]
            },
        }

    monkeypatch.setattr(
        service.worker_app,
        "run_governance_status_transition_on_demand",
        fake_run_governance_status_transition_on_demand,
    )
    monkeypatch.setattr(
        service,
        "_orchestration_run_paths",
        lambda *, target_date: (
            orchestrator_ledger_dir / target_date / "orchestrator_run.json",
            orchestrator_artifact_dir / target_date / "orchestrator_result.json",
        ),
    )

    with _serve(service) as server:
        status, _, post_payload = _post_json(
            f"http://127.0.0.1:{server.server_port}/api/orchestration/run",
            {
                "date": "2026-05-20",
                "mode": "governance_status_transition",
                "source_run_id": "benchmark-run-1",
                "validation_id": "validation-1",
                "requested_by": "integration.http_smoke",
            },
        )
        detail_status, _, detail_payload = _read_json(
            f"http://127.0.0.1:{server.server_port}/api/orchestration/runs/2026-05-20"
        )
        download_status, download_headers, download_body = _read_bytes(
            f"http://127.0.0.1:{server.server_port}/api/orchestration/runs/2026-05-20/download"
        )

    assert status == 200
    assert post_payload.get("_meta", {}).get("status") == "ok"
    post_run = post_payload.get("orchestrator_run", {})
    assert post_run.get("target_date") == "2026-05-20"
    assert post_run.get("mode") == "governance_status_transition"
    assert post_run.get("status_counts") == {"ok": 1}

    ledger_path = orchestrator_ledger_dir / "2026-05-20" / "orchestrator_run.json"
    artifact_path = orchestrator_artifact_dir / "2026-05-20" / "orchestrator_result.json"
    assert ledger_path.exists()
    assert artifact_path.exists()

    stored_ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    stored_artifact = json.loads(artifact_path.read_text(encoding="utf-8"))

    assert stored_ledger.get("mode") == "governance_status_transition"
    assert stored_artifact.get("mode") == "governance_status_transition"
    assert stored_artifact.get("tasks", [])[0].get("task_id") == "governance.status_transition"
    assert (
        stored_artifact.get("tasks", [])[0].get("details", {}).get("validation_id")
        == "validation-1"
    )

    assert detail_status == 200
    assert detail_payload.get("_meta", {}).get("status") == "ok"
    assert detail_payload.get("orchestrator_run") == stored_ledger
    assert detail_payload.get("orchestrator_result") == stored_artifact
    assert detail_payload.get("orchestrator_run") == post_run

    assert download_status == 200
    assert (
        download_headers.get("Content-Disposition")
        == 'attachment; filename="orchestrator_result.json"'
    )
    assert json.loads(download_body.decode("utf-8")) == stored_artifact


def test_http_smoke_governance_candidate_validation_outcome_orchestration_run_round_trip(
    tmp_path: Path, monkeypatch
) -> None:
    service = BootstrapApiService(project_root=PROJECT_ROOT)

    orchestrator_ledger_dir = tmp_path / "ledgers" / "orchestration_runs"
    orchestrator_artifact_dir = tmp_path / "artifacts" / "orchestration_runs"
    validation_result = {
        "validation_id": "validation-1",
        "experiment_id": "experiment-1",
        "baseline_run_id": "benchmark-run-1",
        "candidate_run_id": "candidate-run-1",
        "outcome": "rejected",
        "introduced_risk_count": 1,
        "cleared_guardrail_codes": [],
        "remaining_guardrail_codes": ["interaction.local_global"],
        "evidence_refs": [{"kind": "candidate_validation"}],
    }

    def fake_run_governance_candidate_validation_outcome_on_demand(
        *,
        target_date,
        source_run_id,
        validation_result,
        requested_by,
        dry_run,
    ):
        assert target_date.isoformat() == "2026-05-20"
        assert source_run_id == "benchmark-run-1"
        assert validation_result.validation_id == "validation-1"
        assert validation_result.outcome == "rejected"
        assert requested_by == "integration.http_smoke"
        assert dry_run is False
        return {
            "status": "ok",
            "target_date": "2026-05-20",
            "orchestration": {
                "task_results": [
                    {
                        "task_id": "governance.candidate_validation_outcome",
                        "phase": "governance",
                        "status": "ok",
                        "message": (
                            "candidate validation outcome materialized successfully"
                        ),
                        "details": {
                            "source_run_id": source_run_id,
                            "validation_id": validation_result.validation_id,
                            "outcome": validation_result.outcome,
                        },
                    }
                ]
            },
        }

    monkeypatch.setattr(
        service.worker_app,
        "run_governance_candidate_validation_outcome_on_demand",
        fake_run_governance_candidate_validation_outcome_on_demand,
    )
    monkeypatch.setattr(
        service,
        "_orchestration_run_paths",
        lambda *, target_date: (
            orchestrator_ledger_dir / target_date / "orchestrator_run.json",
            orchestrator_artifact_dir / target_date / "orchestrator_result.json",
        ),
    )

    with _serve(service) as server:
        status, _, post_payload = _post_json(
            f"http://127.0.0.1:{server.server_port}/api/orchestration/run",
            {
                "date": "2026-05-20",
                "mode": "governance_candidate_validation_outcome",
                "source_run_id": "benchmark-run-1",
                "validation_result": validation_result,
                "requested_by": "integration.http_smoke",
            },
        )
        detail_status, _, detail_payload = _read_json(
            f"http://127.0.0.1:{server.server_port}/api/orchestration/runs/2026-05-20"
        )
        download_status, download_headers, download_body = _read_bytes(
            f"http://127.0.0.1:{server.server_port}/api/orchestration/runs/2026-05-20/download"
        )

    assert status == 200
    assert post_payload.get("_meta", {}).get("status") == "ok"
    post_run = post_payload.get("orchestrator_run", {})
    assert post_run.get("target_date") == "2026-05-20"
    assert post_run.get("mode") == "governance_candidate_validation_outcome"
    assert post_run.get("status_counts") == {"ok": 1}

    ledger_path = orchestrator_ledger_dir / "2026-05-20" / "orchestrator_run.json"
    artifact_path = orchestrator_artifact_dir / "2026-05-20" / "orchestrator_result.json"
    assert ledger_path.exists()
    assert artifact_path.exists()

    stored_ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    stored_artifact = json.loads(artifact_path.read_text(encoding="utf-8"))

    assert stored_ledger.get("mode") == "governance_candidate_validation_outcome"
    assert stored_artifact.get("mode") == "governance_candidate_validation_outcome"
    assert (
        stored_artifact.get("tasks", [])[0].get("task_id")
        == "governance.candidate_validation_outcome"
    )
    assert (
        stored_artifact.get("tasks", [])[0].get("details", {}).get("validation_id")
        == "validation-1"
    )

    assert detail_status == 200
    assert detail_payload.get("_meta", {}).get("status") == "ok"
    assert detail_payload.get("orchestrator_run") == stored_ledger
    assert detail_payload.get("orchestrator_result") == stored_artifact
    assert detail_payload.get("orchestrator_run") == post_run

    assert download_status == 200
    assert (
        download_headers.get("Content-Disposition")
        == 'attachment; filename="orchestrator_result.json"'
    )
    assert json.loads(download_body.decode("utf-8")) == stored_artifact
