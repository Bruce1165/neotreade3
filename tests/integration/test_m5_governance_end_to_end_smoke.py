from __future__ import annotations

from contextlib import contextmanager
from datetime import date
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import shutil
from threading import Thread
from urllib.request import Request, urlopen

from apps.api.main import BootstrapApiService, build_handler
from neotrade3.governance.run_ledger import (
    read_governance_candidate_validation_artifact,
    read_governance_final_validation_artifact,
    read_governance_reject_execution_artifact,
    read_governance_status_transition_artifact,
)
from neotrade3.orchestration import DailyMasterOrchestrator, DailyRunPlan, DailyRunRequest, OrchestrationPhase


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _prepare_project_root(tmp_path: Path) -> Path:
    for relative_path in (
        Path("config/labs/labs_registry.json"),
        Path("config/orchestrator/daily_master_orchestrator.json"),
    ):
        destination = tmp_path / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(PROJECT_ROOT / relative_path, destination)

    benchmark_dir = tmp_path / "config" / "benchmark"
    benchmark_dir.mkdir(parents=True, exist_ok=True)
    for file_name in (
        "validation_seed_manifest.json",
        "validation_seed_v2_manifest.json",
        "validation_seed_samples.json",
    ):
        source = PROJECT_ROOT / "config" / "benchmark" / file_name
        shutil.copy(source, benchmark_dir / file_name)

    return tmp_path


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


def _post_json(url: str, payload: dict) -> tuple[int, dict[str, str], dict]:
    headers = {"Content-Type": "application/json"}
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urlopen(request, timeout=30) as response:
        status = int(getattr(response, "status", 200))
        body = json.loads(response.read().decode("utf-8"))
        return status, dict(response.headers.items()), body


def test_m5_governance_end_to_end_smoke_via_http(tmp_path: Path, monkeypatch) -> None:
    project_root = _prepare_project_root(tmp_path)
    service = BootstrapApiService(project_root=project_root)

    orchestrator_ledger_dir = tmp_path / "ledgers" / "orchestration_runs"
    orchestrator_artifact_dir = tmp_path / "artifacts" / "orchestration_runs"

    monkeypatch.setattr(service, "require_trading_day", lambda **_kwargs: None)
    monkeypatch.setattr(service, "_materialize_lab_runs_from_snapshot", lambda **_kwargs: None)
    monkeypatch.setattr(
        service,
        "_orchestration_run_paths",
        lambda *, target_date: (
            orchestrator_ledger_dir / target_date / "orchestrator_run.json",
            orchestrator_artifact_dir / target_date / "orchestrator_result.json",
        ),
    )

    def _run_governance_chain(*, target_date, publish_succeeded, write_outputs, requested_by, dry_run):
        orchestrator = DailyMasterOrchestrator.from_files(
            orchestrator_config_path=project_root / "config" / "orchestrator" / "daily_master_orchestrator.json",
            labs_registry_path=project_root / "config" / "labs" / "labs_registry.json",
        )
        full_plan = orchestrator.build_run_plan(
            DailyRunRequest(target_date=target_date, publish_succeeded=publish_succeeded)
        )
        selected_ids = (
            "benchmark.materialize_run",
            "governance.materialize_handoff",
            "governance.candidate_outcome_bridge",
            "governance.final_validation_selection",
        )
        selected_tasks = [task for task in full_plan.planned_tasks if task.task_id in selected_ids]
        plan = DailyRunPlan(
            target_date=full_plan.target_date,
            phases=[OrchestrationPhase.BENCHMARK, OrchestrationPhase.GOVERNANCE],
            planned_tasks=selected_tasks,
        )
        app = service.worker_app
        task_results = orchestrator.execute_run_plan(
            plan,
            {
                OrchestrationPhase.BENCHMARK: app._create_benchmark_executor(),
                OrchestrationPhase.GOVERNANCE: app._create_governance_executor(),
            },
            {
                "target_date": target_date,
                "project_root": str(project_root),
                "requested_by": requested_by,
                "dry_run": dry_run,
            },
        )
        return {
            "target_date": target_date.isoformat(),
            "publish_succeeded": False,
            "requested_publish_succeeded": publish_succeeded,
            "orchestration": {"task_results": app._to_jsonable(task_results)},
        }

    monkeypatch.setattr(service.worker_app, "run", _run_governance_chain)

    with _serve(service) as server:
        daily_status, _, daily_payload = _post_json(
            f"http://127.0.0.1:{server.server_port}/api/orchestration/run",
            {
                "date": "2026-05-20",
                "mode": "daily",
                "publish_succeeded": False,
                "requested_by": "integration.m5.governance.e2e_smoke",
                "dry_run": False,
            },
        )

        assert daily_status == 200
        assert daily_payload.get("_meta", {}).get("status") == "ok"
        stored_artifact = json.loads(
            (orchestrator_artifact_dir / "2026-05-20" / "orchestrator_result.json").read_text(
                encoding="utf-8"
            )
        )
        tasks = stored_artifact.get("tasks", [])
        task_by_id = {str(item.get("task_id")): item for item in tasks}
        assert task_by_id["benchmark.materialize_run"]["status"] == "ok"
        assert task_by_id["governance.materialize_handoff"]["status"] == "ok"
        assert task_by_id["governance.candidate_outcome_bridge"]["status"] == "ok"
        assert task_by_id["governance.final_validation_selection"]["status"] == "ok"

        source_run_id = task_by_id["governance.final_validation_selection"]["details"]["source_run_id"]
        validation_id = task_by_id["governance.candidate_outcome_bridge"]["details"]["validation_id"]
        assert (
            read_governance_candidate_validation_artifact(
                project_root=project_root,
                validation_id=validation_id,
            )
            is not None
        )
        final_validation = read_governance_final_validation_artifact(
            project_root=project_root,
            source_run_id=source_run_id,
        )
        assert final_validation is not None
        assert final_validation["candidate_run_id"] == "candidate-run-validation-seed-v1"

        chain_status, _, chain_payload = _post_json(
            f"http://127.0.0.1:{server.server_port}/api/orchestration/run",
            {
                "date": "2026-05-20",
                "mode": "governance_reject_transition_chain",
                "source_run_id": source_run_id,
                "requested_by": "integration.m5.governance.e2e_smoke",
                "dry_run": False,
            },
        )

    assert chain_status == 200
    assert chain_payload.get("_meta", {}).get("status") == "ok"
    chain_artifact = json.loads(
        (orchestrator_artifact_dir / "2026-05-20" / "orchestrator_result.json").read_text(
            encoding="utf-8"
        )
    )
    chain_task = chain_artifact.get("tasks", [])[0]
    selected_validation_id = chain_task.get("details", {}).get("selected_validation_id")
    assert isinstance(selected_validation_id, str) and selected_validation_id
    assert (
        read_governance_reject_execution_artifact(
            project_root=project_root,
            validation_id=selected_validation_id,
        )
        is not None
    )
    assert (
        read_governance_status_transition_artifact(
            project_root=project_root,
            validation_id=selected_validation_id,
        )
        is not None
    )

