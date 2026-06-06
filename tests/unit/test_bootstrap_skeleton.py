from __future__ import annotations

from datetime import date
from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
import sqlite3
import shutil
from threading import Thread
from urllib.request import Request, urlopen

from apps.api.main import (
    BootstrapApiRouter,
    BootstrapApiService,
    build_handler,
    format_api_error,
)
from apps.dashboard.main import (
    DashboardPageBuilder,
    build_handler as build_dashboard_handler,
)
from apps.worker.main import BootstrapWorkerApp
from neotrade3.config_contracts import ConfigContractError, build_config_contract_report
from neotrade3.data_control import DataControlPipeline, DataControlStage, SourceRegistry
from neotrade3.issue_center import IssueCenterCollector, IssueSeverity
from neotrade3.labs import LabRegistry, LabRuntimeAdapter
from neotrade3.learning import EvaluationDecision, LearningLoopPipeline
from neotrade3.migration import load_feature_inventory
from neotrade3.orchestration import (
    DailyMasterOrchestrator,
    DailyRunRequest,
    RunStatus,
    load_orchestrator_config,
)
from neotrade3.orchestration.config_loader import orchestrator_config_from_dict
from neotrade3.screeners.cli import build_parser as build_screener_cli_parser
from neotrade3.screeners.runtime import run_placeholder as run_screener_placeholder

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LABS_CONFIG = PROJECT_ROOT / "config/labs/labs_registry.json"
ORCHESTRATOR_CONFIG = (
    PROJECT_ROOT / "config/orchestrator/daily_master_orchestrator.json"
)
SOURCE_REGISTRY_CONFIG = PROJECT_ROOT / "config/data_control/source_registry.json"
FEATURE_INVENTORY_FILE = (
    PROJECT_ROOT / "docs/migration/neotrade2_feature_inventory.v3.json"
)


def test_lab_registry_loads_expected_bootstrap_labs() -> None:
    registry = LabRegistry.from_file(LABS_CONFIG)

    assert registry.version == 1
    assert len(registry.enabled_labs()) == 4
    assert registry.get_lab("cup_handle_lab") is not None
    assert (
        registry.get_lab("cup_handle_lab").daily_jobs[0].task_id
        == "cup_handle_lab.daily_review"
    )


def test_lab_job_contracts_align_with_orchestrator_tasks() -> None:
    registry = LabRegistry.from_file(LABS_CONFIG)
    orchestrator_config = load_orchestrator_config(ORCHESTRATOR_CONFIG)

    orchestrator_tasks = {
        task.task_id: task
        for task in orchestrator_config.tasks
        if task.lab_id is not None
    }

    for job in registry.all_job_contracts():
        assert job.task_id in orchestrator_tasks
        orchestrator_task = orchestrator_tasks[job.task_id]
        assert orchestrator_task.entrypoint == job.entrypoint
        assert orchestrator_task.trigger_type == job.trigger_type
        assert orchestrator_task.phase.value == job.phase
        assert orchestrator_task.depends_on == job.depends_on
        assert orchestrator_task.requires_publish_status == job.requires_publish_status
        assert orchestrator_task.outputs == job.outputs

    runtime_result = LabRuntimeAdapter.run_job("cup_handle_lab.daily_review")
    assert runtime_result["status"] == "pending_implementation"


def test_daily_master_orchestrator_builds_bootstrap_plan() -> None:
    orchestrator = DailyMasterOrchestrator.from_files(
        orchestrator_config_path=ORCHESTRATOR_CONFIG,
        labs_registry_path=LABS_CONFIG,
    )

    plan = orchestrator.build_run_plan(
        DailyRunRequest(target_date=date(2026, 5, 19), publish_succeeded=False)
    )

    assert len(plan.phases) == 6
    assert plan.preflight_report is not None
    assert len(plan.preflight_report.checks) == 4
    assert any(task.task_id == "data_control.capture" for task in plan.planned_tasks)
    assert any(
        task.task_id == "cup_handle_lab.daily_review"
        and task.outputs == ["lab_run_summary", "cup_handle_daily_report"]
        for task in plan.planned_tasks
    )
    assert any(
        task.task_id == "paper_simulation_lab.daily_run"
        and task.status == RunStatus.BLOCKED
        for task in plan.planned_tasks
    )


def test_daily_master_orchestrator_builds_placeholder_results_and_ledger() -> None:
    orchestrator = DailyMasterOrchestrator.from_files(
        orchestrator_config_path=ORCHESTRATOR_CONFIG,
        labs_registry_path=LABS_CONFIG,
    )

    plan = orchestrator.build_run_plan(
        DailyRunRequest(target_date=date(2026, 5, 19), publish_succeeded=False)
    )
    results = orchestrator.build_placeholder_task_results(plan)
    run_entry, task_entries = orchestrator.build_placeholder_run_ledger(plan)

    assert any(
        result.task_id == "data_control.capture"
        and result.status == RunStatus.PENDING_IMPLEMENTATION
        for result in results
    )
    assert any(
        result.task_id == "paper_simulation_lab.daily_run"
        and result.status == RunStatus.BLOCKED
        for result in results
    )
    assert run_entry.status == RunStatus.BLOCKED
    assert len(task_entries) == len(plan.planned_tasks)


def test_data_control_pipeline_exposes_capture_compose_publish_plan() -> None:
    pipeline = DataControlPipeline()

    plan = pipeline.build_plan(date(2026, 5, 19))

    assert [step.stage for step in plan.steps] == [
        DataControlStage.CAPTURE,
        DataControlStage.COMPOSE,
        DataControlStage.PUBLISH,
    ]


def test_screener_cli_parser_requires_screener_id() -> None:
    parser = build_screener_cli_parser()
    try:
        parser.parse_args([])
    except SystemExit as exc:
        exit_code = exc.code
    else:
        raise AssertionError("expected missing --screener-id to raise SystemExit")
    assert exit_code != 0


def test_screener_cli_parser_parses_target_date() -> None:
    parser = build_screener_cli_parser()
    args = parser.parse_args(
        ["--screener-id", "internal_formula_dummy", "--date", "2026-05-19"]
    )
    assert args.screener_id == "internal_formula_dummy"
    assert args.target_date == "2026-05-19"


def test_screener_runtime_placeholder_returns_expected_shape() -> None:
    result = run_screener_placeholder(
        screener_id="internal_formula_dummy", target_date=date(2026, 5, 19)
    )
    assert result["screener_id"] == "internal_formula_dummy"
    assert result["target_date"] == "2026-05-19"
    assert result["status"] == "pending_implementation"
    assert result["picks"] == []
    assert result["decision_trace"] == []


def test_data_control_source_registry_and_plan_ledger_load() -> None:
    registry = SourceRegistry.from_file(SOURCE_REGISTRY_CONFIG)
    pipeline = DataControlPipeline.from_registry_file(SOURCE_REGISTRY_CONFIG)

    plan = pipeline.build_plan(date(2026, 5, 19))
    ledger_entries = pipeline.build_plan_ledger(plan)

    assert registry.version == 1
    assert len(registry.enabled_sources()) == 2
    assert len(registry.sources_for_stage("capture")) >= 1
    assert len(ledger_entries) == 3
    assert any(entry.stage == "publish" for entry in ledger_entries)


def test_config_contract_report_is_clean_for_current_bootstrap_configs() -> None:
    report = build_config_contract_report(
        source_registry=SourceRegistry.from_file(SOURCE_REGISTRY_CONFIG),
        lab_registry=LabRegistry.from_file(LABS_CONFIG),
        orchestrator_config=load_orchestrator_config(ORCHESTRATOR_CONFIG),
    )

    assert report.status == "ok"
    assert report.issues == []
    assert report.enabled_source_count == 2
    assert report.enabled_lab_count == 4
    assert report.orchestrator_lab_task_count == 4


def test_neotrade2_feature_inventory_has_required_fields() -> None:
    items = load_feature_inventory(FEATURE_INVENTORY_FILE)

    assert len(items) >= 60
    assert any(item["feature_id"] == "nt2.cup-handle.lab" for item in items)
    assert any(item["feature_id"] == "nt2.pipeline.compose-publish" for item in items)
    assert any(item["feature_id"] == "nt2.screeners.bulk-run" for item in items)
    assert any(
        item["feature_id"] == "nt2.pipeline.publish-quality-gate" for item in items
    )
    assert any(
        item["feature_id"] == "nt2.strategy.runs.logs-and-artifacts" for item in items
    )
    assert any(
        item["feature_id"] == "nt2.five-flags.run-queue-registry" for item in items
    )
    assert any(item["feature_id"] == "nt2.assistant.rules-analyze" for item in items)
    assert all(item["definition"] for item in items)
    assert all(item["run_logic"] for item in items)
    assert all(item["data_sources"] for item in items)
    assert all(item["owner_modules"] for item in items)
    assert all(item["evidence"] for item in items)


def test_lab_registry_rejects_missing_artifact_contracts() -> None:
    payload = json.loads(LABS_CONFIG.read_text(encoding="utf-8"))
    payload["labs"][0]["daily_jobs"][0]["artifacts"] = ["missing_artifact"]

    try:
        LabRegistry.from_dict(payload)
    except ConfigContractError as exc:
        error = exc
    else:
        raise AssertionError(
            "expected invalid lab registry to raise ConfigContractError"
        )

    assert error.scope == "lab registry"
    assert any("undefined artifacts" in issue for issue in error.issues)


def test_source_registry_rejects_invalid_stage_support() -> None:
    payload = json.loads(SOURCE_REGISTRY_CONFIG.read_text(encoding="utf-8"))
    payload["sources"][0]["stage_support"] = ["capture", "invalid_stage"]

    try:
        SourceRegistry.from_dict(payload)
    except ConfigContractError as exc:
        error = exc
    else:
        raise AssertionError(
            "expected invalid source registry to raise ConfigContractError"
        )

    assert error.scope == "source registry"
    assert any("unsupported stage_support values" in issue for issue in error.issues)


def test_orchestrator_config_rejects_unknown_dependencies() -> None:
    payload = json.loads(ORCHESTRATOR_CONFIG.read_text(encoding="utf-8"))
    payload["tasks"][0]["depends_on"] = ["missing.task"]

    try:
        orchestrator_config_from_dict(payload)
    except ConfigContractError as exc:
        error = exc
    else:
        raise AssertionError(
            "expected invalid orchestrator config to raise ConfigContractError"
        )

    assert error.scope == "orchestrator config"
    assert any("undefined depends_on tasks" in issue for issue in error.issues)


def test_issue_center_collects_placeholder_orchestration_signals() -> None:
    orchestrator = DailyMasterOrchestrator.from_files(
        orchestrator_config_path=ORCHESTRATOR_CONFIG,
        labs_registry_path=LABS_CONFIG,
    )
    collector = IssueCenterCollector()

    plan = orchestrator.build_run_plan(
        DailyRunRequest(target_date=date(2026, 5, 19), publish_succeeded=False)
    )
    results = orchestrator.build_placeholder_task_results(plan)
    _, task_entries = orchestrator.build_placeholder_run_ledger(plan)
    snapshot = collector.collect(plan.target_date, results, task_entries)

    assert len(snapshot.events) == len(snapshot.cases)
    assert any(
        event.task_id == "paper_simulation_lab.daily_run"
        and event.severity == IssueSeverity.ERROR
        for event in snapshot.events
    )
    assert any(
        event.task_id == "data_control.capture" and event.severity == IssueSeverity.INFO
        for event in snapshot.events
    )


def test_learning_loop_builds_metrics_candidates_and_audit_records() -> None:
    orchestrator = DailyMasterOrchestrator.from_files(
        orchestrator_config_path=ORCHESTRATOR_CONFIG,
        labs_registry_path=LABS_CONFIG,
    )
    collector = IssueCenterCollector()
    learning_pipeline = LearningLoopPipeline()

    plan = orchestrator.build_run_plan(
        DailyRunRequest(target_date=date(2026, 5, 19), publish_succeeded=False)
    )
    results = orchestrator.build_placeholder_task_results(plan)
    _, task_entries = orchestrator.build_placeholder_run_ledger(plan)
    issue_snapshot = collector.collect(plan.target_date, results, task_entries)
    learning_snapshot = learning_pipeline.build_snapshot(
        target_date=plan.target_date,
        task_results=results,
        issue_snapshot=issue_snapshot,
    )

    assert learning_snapshot.metrics.total_tasks == len(results)
    assert learning_snapshot.metrics.blocked_tasks >= 1
    assert learning_snapshot.inputs.issue_case_count == len(issue_snapshot.cases)
    assert any(
        candidate.decision == EvaluationDecision.REVIEW_REQUIRED
        for candidate in learning_snapshot.adjustment_candidates
    )
    assert len(learning_snapshot.audit_records) == len(
        learning_snapshot.adjustment_candidates
    )


def test_bootstrap_worker_writes_snapshot_files(tmp_path: Path) -> None:
    app = BootstrapWorkerApp(project_root=PROJECT_ROOT)
    app.paths["ledgers_root"] = tmp_path / "ledgers"
    app.paths["artifacts_root"] = tmp_path / "artifacts"

    snapshot = app.run(
        target_date=date(2026, 5, 19),
        publish_succeeded=False,
        write_outputs=True,
    )

    assert snapshot["summary"]["planned_task_count"] >= 1
    assert (tmp_path / "ledgers/2026-05-19/data_control_plan_ledger.json").exists()
    assert (tmp_path / "ledgers/2026-05-19/orchestration_run_snapshot.json").exists()
    assert (tmp_path / "artifacts/2026-05-19/issue_center_snapshot.json").exists()
    assert (tmp_path / "artifacts/2026-05-19/learning_snapshot.json").exists()


def test_bootstrap_api_service_and_router_expose_read_only_snapshot() -> None:
    service = BootstrapApiService(project_root=PROJECT_ROOT)
    router = BootstrapApiRouter(service)

    health_status, health_payload = router.dispatch("/healthz")
    summary_status, summary_payload = router.dispatch(
        "/api/bootstrap-summary?date=2026-05-19&publish_succeeded=false"
    )
    snapshot_status, snapshot_payload = router.dispatch(
        "/api/bootstrap-snapshot?date=2026-05-19&publish_succeeded=false&write_outputs=false"
    )

    assert health_status == 200
    assert health_payload["status"] == "ok"
    assert summary_status == 200
    assert summary_payload["target_date"] == "2026-05-19"
    assert snapshot_status == 200
    assert snapshot_payload["summary"]["planned_task_count"] >= 1


def test_bootstrap_api_router_exposes_domain_endpoints() -> None:
    service = BootstrapApiService(project_root=PROJECT_ROOT)
    router = BootstrapApiRouter(service)

    data_status, data_payload = router.dispatch("/api/data-control?date=2026-05-19")
    orchestration_status, orchestration_payload = router.dispatch(
        "/api/orchestration?date=2026-05-19"
    )
    labs_status, labs_payload = router.dispatch("/api/labs")
    contracts_status, contracts_payload = router.dispatch("/api/config-contracts")
    screeners_status, screeners_payload = router.dispatch("/api/screeners")
    feature_manual_status, feature_manual_payload = router.dispatch(
        "/api/migration/feature-manual"
    )
    feature_mapping_status, feature_mapping_payload = router.dispatch(
        "/api/migration/feature-mapping?domain=strategy_and_lab"
    )
    assistant_mapping_status, assistant_mapping_payload = router.dispatch(
        "/api/migration/feature-mapping?domain=assistant"
    )
    operations_mapping_status, operations_mapping_payload = router.dispatch(
        "/api/migration/feature-mapping?domain=operations"
    )
    screeners_mapping_status, screeners_mapping_payload = router.dispatch(
        "/api/migration/feature-mapping?domain=screeners"
    )
    issue_status, issue_payload = router.dispatch("/api/issue-center?date=2026-05-19")
    learning_status, learning_payload = router.dispatch("/api/learning?date=2026-05-19")

    assert data_status == 200
    assert "source_registry" in data_payload
    assert data_payload["_meta"]["cache_status"] in {"hit", "miss"}
    assert data_payload["target_date"] == "2026-05-19"
    assert orchestration_status == 200
    assert "orchestration" in orchestration_payload
    assert labs_status == 200
    assert labs_payload["_meta"]["cache_status"] in {"hit", "miss"}
    assert len(labs_payload["labs"]) == 4
    assert contracts_status == 200
    assert contracts_payload["_meta"]["validation_status"] == "ok"
    assert contracts_payload["config_contracts"]["issues"] == []
    assert screeners_status == 200
    assert screeners_payload["_meta"]["runs_source"] == "var/ledgers/screener_runs"
    assert screeners_payload["screeners_registry"]["version"] == 1
    assert len(screeners_payload["screeners_registry"]["screeners"]) >= 3
    assert isinstance(screeners_payload["screener_runs"], list)
    assert feature_manual_status == 200
    assert (
        feature_manual_payload["_meta"]["source"] == "neotrade2_codebase_inventory_v3"
    )
    assert feature_manual_payload["feature_manual"]["feature_count"] >= 60
    assert feature_mapping_status == 200
    assert (
        feature_mapping_payload["_meta"]["source"]
        == "neotrade3_feature_mapping_strategy_and_lab_v1"
    )
    assert feature_mapping_payload["feature_mapping"]["mapping_count"] >= 20
    assert any(
        item["feature_id"] == "nt2.paper-trading.lab"
        for item in feature_mapping_payload["feature_mapping"]["mappings"]
    )
    assert assistant_mapping_status == 200
    assert (
        assistant_mapping_payload["_meta"]["source"]
        == "neotrade3_feature_mapping_assistant_v1"
    )
    assert assistant_mapping_payload["feature_mapping"]["mapping_count"] >= 8
    assert any(
        item["feature_id"] == "nt2.assistant.analysis"
        for item in assistant_mapping_payload["feature_mapping"]["mappings"]
    )
    assert operations_mapping_status == 200
    assert (
        operations_mapping_payload["_meta"]["source"]
        == "neotrade3_feature_mapping_operations_v1"
    )
    assert operations_mapping_payload["feature_mapping"]["mapping_count"] >= 7
    assert operations_mapping_payload["feature_mapping"]["mapping_count_total"] >= 7
    assert any(
        item["feature_id"] == "nt2.system.tasks-and-jobs"
        for item in operations_mapping_payload["feature_mapping"]["mappings"]
    )
    assert screeners_mapping_status == 200
    assert (
        screeners_mapping_payload["_meta"]["source"]
        == "neotrade3_feature_mapping_screeners_v1"
    )
    assert screeners_mapping_payload["feature_mapping"]["mapping_count"] >= 13
    assert any(
        item["feature_id"] == "nt2.screeners.registry-and-config"
        for item in screeners_mapping_payload["feature_mapping"]["mappings"]
    )
    assert issue_status == 200
    assert "issue_center" in issue_payload
    assert learning_status == 200
    assert "learning" in learning_payload


def test_bootstrap_api_feature_mapping_filters_work() -> None:
    service = BootstrapApiService(project_root=PROJECT_ROOT)
    router = BootstrapApiRouter(service)

    status, payload = router.dispatch(
        "/api/migration/feature-mapping?domain=strategy_and_lab&status=scaffolded"
    )
    assert status == 200
    assert payload["_meta"]["source"] == "neotrade3_feature_mapping_strategy_and_lab_v1"
    assert payload["feature_mapping"]["filters"]["status"] == "scaffolded"
    assert payload["feature_mapping"]["mapping_count_total"] >= 20
    assert payload["feature_mapping"]["mapping_count"] == 4


def test_bootstrap_api_feature_mapping_coverage_is_complete() -> None:
    service = BootstrapApiService(project_root=PROJECT_ROOT)
    router = BootstrapApiRouter(service)

    for domain, expected_min in (
        ("strategy_and_lab", 20),
        ("assistant", 8),
        ("operations", 7),
        ("screeners", 13),
    ):
        status, payload = router.dispatch(
            f"/api/migration/feature-mapping-coverage?domain={domain}"
        )
        assert status == 200
        assert (
            payload["_meta"]["source"]
            == f"neotrade3_feature_mapping_coverage_{domain}_v1"
        )
        report = payload["feature_mapping_coverage"]
        assert report["status"] == "ok"
        assert report["inventory_count"] >= expected_min
        assert report["mapped_count"] == report["inventory_count"]
        assert report["missing_count"] == 0
        assert report["extra_count"] == 0


def test_bootstrap_api_service_reads_stored_snapshot_files(tmp_path: Path) -> None:
    app = BootstrapWorkerApp(project_root=PROJECT_ROOT)
    app.paths["ledgers_root"] = tmp_path / "ledgers"
    app.paths["artifacts_root"] = tmp_path / "artifacts"
    app.run(
        target_date=date(2026, 5, 19),
        publish_succeeded=False,
        write_outputs=True,
    )

    service = BootstrapApiService(project_root=PROJECT_ROOT)
    service.worker_app.paths["ledgers_root"] = tmp_path / "ledgers"
    service.worker_app.paths["artifacts_root"] = tmp_path / "artifacts"
    router = BootstrapApiRouter(service)

    summary_status, summary_payload = router.dispatch(
        "/api/bootstrap-summary?date=2026-05-19"
    )
    issue_status, issue_payload = router.dispatch(
        "/api/issue-center?date=2026-05-19"
    )

    assert summary_status == 200
    assert summary_payload["_meta"]["cache_status"] in {"hit", "miss"}
    assert summary_payload["_meta"]["self_heal"] == "none"
    assert summary_payload["target_date"] == "2026-05-19"
    assert issue_status == 200
    assert issue_payload["_meta"]["self_heal"] == "none"
    assert "issue_center" in issue_payload


def test_bootstrap_api_reports_structured_errors_and_invalid_source(
    tmp_path: Path,
) -> None:
    service = BootstrapApiService(project_root=PROJECT_ROOT)
    service.worker_app.paths["ledgers_root"] = tmp_path / "ledgers"
    service.worker_app.paths["artifacts_root"] = tmp_path / "artifacts"
    router = BootstrapApiRouter(service)

    try:
        router.dispatch("/missing-path")
    except Exception as exc:
        not_found_status, not_found_payload = format_api_error(exc)
    else:
        raise AssertionError("expected missing path to raise ApiError")

    assert not_found_status == 404
    assert not_found_payload["error"]["code"] == "not_found"

    ok_status, ok_payload = router.dispatch(
        "/api/bootstrap-summary?date=2026-05-19&source=bad-mode"
    )
    assert ok_status == 200
    assert ok_payload["target_date"] == "2026-05-19"


def test_bootstrap_api_router_ignores_source_query_param() -> None:
    service = BootstrapApiService(project_root=PROJECT_ROOT)
    router = BootstrapApiRouter(service)

    status, payload = router.dispatch(
        "/api/bootstrap-summary?date=2026-05-19&source=bad-mode"
    )
    assert status == 200
    assert payload["target_date"] == "2026-05-19"


def test_bootstrap_api_service_cache_marks_hits() -> None:
    service = BootstrapApiService(project_root=PROJECT_ROOT)

    first = service.bootstrap_summary(date(2026, 5, 19))
    second = service.bootstrap_summary(date(2026, 5, 19))

    assert first["_meta"]["cache_status"] == "miss"
    assert second["_meta"]["cache_status"] == "hit"


def test_bootstrap_api_service_data_control_caches_source_registry() -> None:
    service = BootstrapApiService(project_root=PROJECT_ROOT)

    first = service.data_control_view(date(2026, 5, 19))
    second = service.data_control_view(date(2026, 5, 19))

    assert first["_meta"]["source_registry_cache_status"] == "miss"
    assert second["_meta"]["source_registry_cache_status"] == "hit"


def test_bootstrap_api_handler_serves_screeners_endpoint() -> None:
    service = BootstrapApiService(project_root=PROJECT_ROOT)
    handler = build_handler(service)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        with urlopen(
            f"http://127.0.0.1:{server.server_port}/api/screeners"
        ) as response:
            assert response.status == 200
            payload = json.loads(response.read().decode("utf-8"))
            assert "screeners_registry" in payload
            assert "screener_runs" in payload
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_bootstrap_api_handler_accepts_screener_run_post() -> None:
    service = BootstrapApiService(project_root=PROJECT_ROOT, api_key="test-key")
    handler = build_handler(service)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        calendar_path = (
            PROJECT_ROOT / "var/ledgers/trading_calendar/trading_calendar.json"
        )
        calendar_path.parent.mkdir(parents=True, exist_ok=True)
        previous_calendar_text = (
            calendar_path.read_text(encoding="utf-8")
            if calendar_path.exists()
            else None
        )
        calendar_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "generated_at": "2026-05-20T00:00:00Z",
                    "generated_by": "test",
                    "source": {"type": "test"},
                    "trading_days": ["2026-05-19"],
                    "trading_day_count": 1,
                },
                indent=2,
                ensure_ascii=False,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        body = json.dumps(
            {
                "screener_id": "cup_handle_v4",
                "date": "2026-05-19",
                "requested_by": "test",
                "dry_run": False,
                "parameters": {},
            }
        ).encode("utf-8")
        request = Request(
            f"http://127.0.0.1:{server.server_port}/api/screeners/run",
            data=body,
            headers={"Content-Type": "application/json", "X-API-Key": "test-key"},
            method="POST",
        )
        with urlopen(request) as response:
            assert response.status == 200
            payload = json.loads(response.read().decode("utf-8"))
            assert payload["_meta"]["status"] == "ok"
            assert payload["screener_run"]["screener_id"] == "cup_handle_v4"
            assert payload["screener_run"]["target_date"] == "2026-05-19"

        with urlopen(
            f"http://127.0.0.1:{server.server_port}/api/screeners/runs/2026-05-19/cup_handle_v4"
        ) as response:
            assert response.status == 200
            payload = json.loads(response.read().decode("utf-8"))
            assert payload["_meta"]["status"] == "ok"
            assert payload["screener_run"]["screener_id"] == "cup_handle_v4"
            assert payload["screener_result"]["screener_id"] == "cup_handle_v4"
            assert (
                payload["screener_result"]["parameters"]["universe_filters"][
                    "min_market_cap"
                ]
                == 123
            )

        with urlopen(
            f"http://127.0.0.1:{server.server_port}/api/screeners/runs?date=2026-05-19&limit=10"
        ) as response:
            assert response.status == 200
            payload = json.loads(response.read().decode("utf-8"))
            assert payload["_meta"]["returned_count"] >= 1
            assert any(
                run["screener_id"] == "cup_handle_v4"
                for run in payload["screener_runs"]
            )

        with urlopen(
            f"http://127.0.0.1:{server.server_port}/api/screeners/config/cup_handle_v4"
        ) as response:
            assert response.status == 200
            payload = json.loads(response.read().decode("utf-8"))
            assert payload["_meta"]["status"] == "ok"
            assert payload["screener_config"]["screener_id"] == "cup_handle_v4"
            assert "schema" in payload["screener_config"]
            assert "default_parameters" in payload["screener_config"]

        body = json.dumps(
            {
                "requested_by": "test",
                "current_parameters": {"universe_filters": {"min_market_cap": 123.0}},
            }
        ).encode("utf-8")
        request = Request(
            f"http://127.0.0.1:{server.server_port}/api/screeners/config/cup_handle_v4",
            data=body,
            headers={"Content-Type": "application/json", "X-API-Key": "test-key"},
            method="POST",
        )
        with urlopen(request) as response:
            assert response.status == 200
            payload = json.loads(response.read().decode("utf-8"))
            assert payload["_meta"]["status"] == "ok"
            assert payload["screener_config"]["screener_id"] == "cup_handle_v4"
            assert (
                payload["screener_config"]["current_parameters"]["universe_filters"][
                    "min_market_cap"
                ]
                == 123.0
            )

        body = json.dumps(
            {
                "screener_id": "cup_handle_v4",
                "date": "2026-05-19",
                "requested_by": "test",
                "dry_run": False,
                "parameters": {"universe_filters": {"min_market_cap": 456}},
            }
        ).encode("utf-8")
        request = Request(
            f"http://127.0.0.1:{server.server_port}/api/screeners/run",
            data=body,
            headers={"Content-Type": "application/json", "X-API-Key": "test-key"},
            method="POST",
        )
        with urlopen(request) as response:
            assert response.status == 200

        with urlopen(
            f"http://127.0.0.1:{server.server_port}/api/screeners/runs/2026-05-19/cup_handle_v4"
        ) as response:
            payload = json.loads(response.read().decode("utf-8"))
            assert (
                payload["screener_result"]["parameters"]["universe_filters"][
                    "min_market_cap"
                ]
                == 456
            )

        artifact_path = (
            PROJECT_ROOT
            / "var/artifacts/screener_runs/2026-05-19/screener_cup_handle_v4_result.json"
        )
        artifact_payload = json.loads(artifact_path.read_text(encoding="utf-8"))
        artifact_payload["status"] = "ok"
        artifact_payload["picks"] = ["000001.SZ"]
        artifact_path.write_text(
            json.dumps(artifact_payload, indent=2, ensure_ascii=False, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )

        with urlopen(
            f"http://127.0.0.1:{server.server_port}/api/screeners/runs/2026-05-19/cup_handle_v4/download.csv"
        ) as response:
            assert response.status == 200
            assert "attachment" in response.headers.get("Content-Disposition", "")
            csv_text = response.read().decode("utf-8-sig")
            lines = [line for line in csv_text.splitlines() if line.strip()]
            assert lines[0] == "rank,stock_code,stock_name"
            assert any(",000001," in line for line in lines[1:])

        bulk_result_path = (
            PROJECT_ROOT / "var/artifacts/screener_runs/2026-05-19/bulk_run_result.json"
        )
        bulk_result_path.parent.mkdir(parents=True, exist_ok=True)
        bulk_result_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "target_date": "2026-05-19",
                    "requested_by": "test",
                    "requested_at": "2026-05-20T00:00:00Z",
                    "status": "ok",
                    "summary": {"run_count": 1, "picks_count_total": 1},
                    "runs": [
                        {
                            "target_date": "2026-05-19",
                            "screener_id": "cup_handle_v4",
                            "status": "ok",
                            "requested_at": "2026-05-20T00:00:00Z",
                            "finished_at": None,
                            "picks_count": 1,
                            "artifact_path": str(artifact_path),
                        }
                    ],
                },
                indent=2,
                ensure_ascii=False,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        ledger_path = (
            PROJECT_ROOT
            / "var/ledgers/screener_runs/2026-05-19/screener_cup_handle_v4_run.json"
        )
        if ledger_path.exists():
            ledger_path.unlink()

        request = Request(
            f"http://127.0.0.1:{server.server_port}/api/check-stock?code=000001.SZ&date=2026-05-19&debug=1",
            headers={"X-API-Key": "test-key"},
            method="GET",
        )
        with urlopen(request) as response:
            assert response.status == 200
            payload = json.loads(response.read().decode("utf-8"))
            assert payload["_meta"]["status"] == "ok"
            assert payload["stock_code"] == "000001.SZ"
            screener_items = payload["checks"]["screeners"]["items"]
            cup_handle_item = next(
                item
                for item in screener_items
                if item.get("_debug", {}).get("screener_id") == "cup_handle_v4"
            )
            assert cup_handle_item["result"] is True
            assert cup_handle_item["name"] == "杯柄 V4"
            assert cup_handle_item["_debug"]["run_source"] == "bulk_run_result"
            assert payload["checks"]["picks_presence"]["result"] is True
            assert (
                payload["checks"]["tracking_lists"]["status"] == "ok"
            )

        body = json.dumps(
            {
                "date": "2026-05-19",
                "requested_by": "test",
                "dry_run": False,
                "screener_ids": ["cup_handle_v4", "jin_feng_huang"],
            }
        ).encode("utf-8")
        request = Request(
            f"http://127.0.0.1:{server.server_port}/api/screeners/bulk-run",
            data=body,
            headers={"Content-Type": "application/json", "X-API-Key": "test-key"},
            method="POST",
        )
        with urlopen(request) as response:
            assert response.status == 200
            payload = json.loads(response.read().decode("utf-8"))
            assert payload["_meta"]["status"] == "ok"
            assert payload["bulk_run"]["target_date"] == "2026-05-19"
            assert payload["bulk_run"]["run_count"] == 2

        with urlopen(
            f"http://127.0.0.1:{server.server_port}/api/screeners/bulk-runs?date=2026-05-19&limit=10"
        ) as response:
            assert response.status == 200
            payload = json.loads(response.read().decode("utf-8"))
            assert payload["_meta"]["returned_count"] >= 1
            assert any(
                item.get("target_date") == "2026-05-19" for item in payload["bulk_runs"]
            )

        with urlopen(
            f"http://127.0.0.1:{server.server_port}/api/screeners/bulk-runs/2026-05-19"
        ) as response:
            assert response.status == 200
            payload = json.loads(response.read().decode("utf-8"))
            assert payload["_meta"]["status"] == "ok"
            assert payload["bulk_run"]["target_date"] == "2026-05-19"
            assert payload["bulk_result"]["target_date"] == "2026-05-19"

        with urlopen(
            f"http://127.0.0.1:{server.server_port}/api/screeners/bulk-runs/2026-05-19/download"
        ) as response:
            assert response.status == 200
            assert "attachment" in response.headers.get("Content-Disposition", "")
            payload = json.loads(response.read().decode("utf-8"))
            assert payload["target_date"] == "2026-05-19"

        request = Request(
            f"http://127.0.0.1:{server.server_port}/api/check-stock?date=2026-05-19",
            method="GET",
        )
        try:
            urlopen(request)
            assert False, "expected request to fail"
        except Exception as exc:
            assert "HTTP Error 400" in str(exc)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        if "previous_calendar_text" in locals():
            if previous_calendar_text is None:
                if calendar_path.exists():
                    calendar_path.unlink()
            else:
                calendar_path.write_text(previous_calendar_text, encoding="utf-8")


def test_daily_hot_cold_screener_run_produces_picks_and_decision_trace() -> None:
    test_db_path = PROJECT_ROOT / "var/db/test_daily_hot_cold_stock_data.db"
    test_db_path.parent.mkdir(parents=True, exist_ok=True)
    if test_db_path.exists():
        test_db_path.unlink()

    conn = sqlite3.connect(str(test_db_path))
    try:
        cursor = conn.cursor()
        cursor.execute(
            "CREATE TABLE stocks (code TEXT PRIMARY KEY, name TEXT, asset_type TEXT, is_delisted INTEGER, circulating_market_cap REAL)"
        )
        cursor.execute(
            "CREATE TABLE daily_prices (trade_date TEXT, code TEXT, amount REAL)"
        )
        cursor.execute(
            "INSERT INTO stocks(code,name,asset_type,is_delisted,circulating_market_cap) VALUES (?,?,?,?,?)",
            ("000001", "平安银行", "stock", 0, 200_000_000_000.0),
        )
        cursor.execute(
            "INSERT INTO stocks(code,name,asset_type,is_delisted,circulating_market_cap) VALUES (?,?,?,?,?)",
            ("600519", "贵州茅台", "stock", 0, 900_000_000_000.0),
        )
        cursor.execute(
            "INSERT INTO daily_prices(trade_date,code,amount) VALUES (?,?,?)",
            ("2026-05-19", "000001", 11000.0),
        )
        cursor.execute(
            "INSERT INTO daily_prices(trade_date,code,amount) VALUES (?,?,?)",
            ("2026-05-19", "600519", 150000.0),
        )
        conn.commit()
    finally:
        conn.close()

    original_db_path = os.environ.get("NEOTRADE3_STOCK_DB_PATH")
    os.environ["NEOTRADE3_STOCK_DB_PATH"] = str(test_db_path)

    service = BootstrapApiService(project_root=PROJECT_ROOT, api_key="test-key")
    handler = build_handler(service)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        calendar_path = (
            PROJECT_ROOT / "var/ledgers/trading_calendar/trading_calendar.json"
        )
        calendar_path.parent.mkdir(parents=True, exist_ok=True)
        previous_calendar_text = (
            calendar_path.read_text(encoding="utf-8")
            if calendar_path.exists()
            else None
        )
        calendar_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "generated_at": "2026-05-20T00:00:00Z",
                    "generated_by": "test",
                    "source": {"type": "test"},
                    "trading_days": ["2026-05-19"],
                    "trading_day_count": 1,
                },
                indent=2,
                ensure_ascii=False,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        body = json.dumps(
            {
                "screener_id": "daily_hot_cold",
                "date": "2026-05-19",
                "requested_by": "test",
                "dry_run": False,
                "parameters": {"top_n": 1},
            }
        ).encode("utf-8")
        request = Request(
            f"http://127.0.0.1:{server.server_port}/api/screeners/run",
            data=body,
            headers={"Content-Type": "application/json", "X-API-Key": "test-key"},
            method="POST",
        )
        with urlopen(request) as response:
            assert response.status == 200

        with urlopen(
            f"http://127.0.0.1:{server.server_port}/api/screeners/runs/2026-05-19/daily_hot_cold"
        ) as response:
            assert response.status == 200
            payload = json.loads(response.read().decode("utf-8"))
            assert payload["screener_result"]["status"] == "ok"
            assert payload["screener_result"]["picks"] == ["600519"]
            assert isinstance(payload["screener_result"]["decision_trace"], list)
            assert payload["screener_result"]["decision_trace"]

        with urlopen(
            f"http://127.0.0.1:{server.server_port}/api/screeners/runs/2026-05-19/daily_hot_cold/download.csv"
        ) as response:
            assert response.status == 200
            csv_text = response.read().decode("utf-8-sig")
            lines = [line for line in csv_text.splitlines() if line.strip()]
            assert lines[0] == "rank,stock_code,stock_name"
            assert any(",600519," in line for line in lines[1:])

        with urlopen(
            f"http://127.0.0.1:{server.server_port}/api/pools?date=2026-05-19"
        ) as response:
            assert response.status == 200
            payload = json.loads(response.read().decode("utf-8"))
            assert "pools" in payload
            pool_ids = {item["pool_id"] for item in payload["pools"]}
            assert "screener__daily_hot_cold" in pool_ids

        with urlopen(
            f"http://127.0.0.1:{server.server_port}/api/pools/screener__daily_hot_cold?date=2026-05-19"
        ) as response:
            assert response.status == 200
            payload = json.loads(response.read().decode("utf-8"))
            assert "600519" in payload["pool"]["members"]

        body = json.dumps(
            {
                "date": "2026-05-19",
                "pool_id": "watch_A",
                "display_name": "观察池A",
                "members": ["600519", "000001"],
                "requested_by": "test",
                "dry_run": False,
            }
        ).encode("utf-8")
        request = Request(
            f"http://127.0.0.1:{server.server_port}/api/pools/manual/snapshot",
            data=body,
            headers={"Content-Type": "application/json", "X-API-Key": "test-key"},
            method="POST",
        )
        with urlopen(request) as response:
            assert response.status == 200

        with urlopen(
            f"http://127.0.0.1:{server.server_port}/api/pools/manual__watch_A?date=2026-05-19"
        ) as response:
            assert response.status == 200
            payload = json.loads(response.read().decode("utf-8"))
            assert payload["pool"]["display_name"] == "观察池A"
            assert "600519" in payload["pool"]["members"]

        with urlopen(
            f"http://127.0.0.1:{server.server_port}/api/pools/manual__watch_A/download.csv?date=2026-05-19"
        ) as response:
            assert response.status == 200
            csv_text = response.read().decode("utf-8-sig")
            lines = [line for line in csv_text.splitlines() if line.strip()]
            assert lines[0] == "rank,stock_code,stock_name"
            assert any(",600519," in line for line in lines[1:])
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        if original_db_path is None:
            os.environ.pop("NEOTRADE3_STOCK_DB_PATH", None)
        else:
            os.environ["NEOTRADE3_STOCK_DB_PATH"] = original_db_path
        shutil.rmtree(
            PROJECT_ROOT / "var/ledgers/pools" / "2026-05-19", ignore_errors=True
        )
        shutil.rmtree(
            PROJECT_ROOT / "var/artifacts/pools" / "2026-05-19", ignore_errors=True
        )
        if test_db_path.exists():
            test_db_path.unlink()
        if "previous_calendar_text" in locals():
            if previous_calendar_text is None:
                if calendar_path.exists():
                    calendar_path.unlink()
            else:
                calendar_path.write_text(previous_calendar_text, encoding="utf-8")


def test_er_ban_hui_tiao_screener_run_produces_picks_and_decision_trace() -> None:
    test_db_path = PROJECT_ROOT / "var/db/test_er_ban_hui_tiao_stock_data.db"
    test_db_path.parent.mkdir(parents=True, exist_ok=True)
    if test_db_path.exists():
        test_db_path.unlink()

    conn = sqlite3.connect(str(test_db_path))
    try:
        cursor = conn.cursor()
        cursor.execute(
            "CREATE TABLE stocks (code TEXT PRIMARY KEY, name TEXT, asset_type TEXT, is_delisted INTEGER, circulating_market_cap REAL)"
        )
        cursor.execute(
            "CREATE TABLE daily_prices (trade_date TEXT, code TEXT, open REAL, high REAL, low REAL, close REAL, pct_change REAL, amount REAL, volume REAL)"
        )
        cursor.execute(
            "INSERT INTO stocks(code,name,asset_type,is_delisted,circulating_market_cap) VALUES (?,?,?,?,?)",
            ("000001", "平安银行", "stock", 0, 200_000_000_000.0),
        )
        cursor.execute(
            "INSERT INTO stocks(code,name,asset_type,is_delisted,circulating_market_cap) VALUES (?,?,?,?,?)",
            ("600519", "贵州茅台", "stock", 0, 900_000_000_000.0),
        )
        cursor.execute(
            "INSERT INTO daily_prices(trade_date,code,open,high,low,close,pct_change,amount,volume) VALUES (?,?,?,?,?,?,?,?,?)",
            ("2026-05-15", "000001", 10.0, 11.0, 9.9, 11.0, 10.0, 21000.0, 1000.0),
        )
        cursor.execute(
            "INSERT INTO daily_prices(trade_date,code,open,high,low,close,pct_change,amount,volume) VALUES (?,?,?,?,?,?,?,?,?)",
            ("2026-05-16", "000001", 11.0, 12.0, 10.8, 12.0, 10.0, 11000.0, 1500.0),
        )
        cursor.execute(
            "INSERT INTO daily_prices(trade_date,code,open,high,low,close,pct_change,amount,volume) VALUES (?,?,?,?,?,?,?,?,?)",
            ("2026-05-14", "000001", 9.0, 9.5, 8.8, 9.0, 1.0, 5000.0, 800.0),
        )
        cursor.execute(
            "INSERT INTO daily_prices(trade_date,code,open,high,low,close,pct_change,amount,volume) VALUES (?,?,?,?,?,?,?,?,?)",
            ("2026-05-19", "000001", 12.5, 13.5, 12.0, 13.0, 8.0, 25000.0, 900.0),
        )
        cursor.execute(
            "INSERT INTO daily_prices(trade_date,code,open,high,low,close,pct_change,amount,volume) VALUES (?,?,?,?,?,?,?,?,?)",
            (
                "2026-05-15",
                "600519",
                1500.0,
                1510.0,
                1490.0,
                1505.0,
                1.0,
                150000.0,
                100.0,
            ),
        )
        cursor.execute(
            "INSERT INTO daily_prices(trade_date,code,open,high,low,close,pct_change,amount,volume) VALUES (?,?,?,?,?,?,?,?,?)",
            (
                "2026-05-16",
                "600519",
                1505.0,
                1515.0,
                1495.0,
                1510.0,
                1.0,
                150000.0,
                100.0,
            ),
        )
        cursor.execute(
            "INSERT INTO daily_prices(trade_date,code,open,high,low,close,pct_change,amount,volume) VALUES (?,?,?,?,?,?,?,?,?)",
            (
                "2026-05-19",
                "600519",
                1510.0,
                1520.0,
                1500.0,
                1515.0,
                1.0,
                150000.0,
                100.0,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    original_db_path = os.environ.get("NEOTRADE3_STOCK_DB_PATH")
    os.environ["NEOTRADE3_STOCK_DB_PATH"] = str(test_db_path)

    service = BootstrapApiService(project_root=PROJECT_ROOT, api_key="test-key")
    handler = build_handler(service)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        calendar_path = (
            PROJECT_ROOT / "var/ledgers/trading_calendar/trading_calendar.json"
        )
        calendar_path.parent.mkdir(parents=True, exist_ok=True)
        previous_calendar_text = (
            calendar_path.read_text(encoding="utf-8")
            if calendar_path.exists()
            else None
        )
        calendar_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "generated_at": "2026-05-20T00:00:00Z",
                    "generated_by": "test",
                    "source": {"type": "test"},
                    "trading_days": [
                        "2026-05-14",
                        "2026-05-15",
                        "2026-05-16",
                        "2026-05-19",
                    ],
                    "trading_day_count": 4,
                },
                indent=2,
                ensure_ascii=False,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        body = json.dumps(
            {
                "screener_id": "er_ban_hui_tiao",
                "date": "2026-05-19",
                "requested_by": "test",
                "dry_run": False,
                "parameters": {
                    "top_n": 10,
                    "limit_days": 14,
                    "limit_up_threshold": 9.9,
                    "first_board_volume_ratio": 2.0,
                },
            }
        ).encode("utf-8")
        request = Request(
            f"http://127.0.0.1:{server.server_port}/api/screeners/run",
            data=body,
            headers={"Content-Type": "application/json", "X-API-Key": "test-key"},
            method="POST",
        )
        with urlopen(request) as response:
            assert response.status == 200

        with urlopen(
            f"http://127.0.0.1:{server.server_port}/api/screeners/runs/2026-05-19/er_ban_hui_tiao"
        ) as response:
            assert response.status == 200
            payload = json.loads(response.read().decode("utf-8"))
            assert payload["screener_result"]["status"] == "ok"
            assert "000001" in payload["screener_result"]["picks"]
            assert isinstance(payload["screener_result"]["decision_trace"], list)
            assert payload["screener_result"]["decision_trace"]

        with urlopen(
            f"http://127.0.0.1:{server.server_port}/api/screeners/runs/2026-05-19/er_ban_hui_tiao/download.csv"
        ) as response:
            assert response.status == 200
            csv_text = response.read().decode("utf-8-sig")
            lines = [line for line in csv_text.splitlines() if line.strip()]
            assert lines[0] == "rank,stock_code,stock_name"
            assert any(",000001," in line for line in lines[1:])
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        if original_db_path is None:
            os.environ.pop("NEOTRADE3_STOCK_DB_PATH", None)
        else:
            os.environ["NEOTRADE3_STOCK_DB_PATH"] = original_db_path
        if test_db_path.exists():
            test_db_path.unlink()
        if "previous_calendar_text" in locals():
            if previous_calendar_text is None:
                if calendar_path.exists():
                    calendar_path.unlink()
            else:
                calendar_path.write_text(previous_calendar_text, encoding="utf-8")


def test_zhang_ting_bei_liang_yin_screener_run_produces_picks_and_decision_trace() -> (
    None
):
    test_db_path = PROJECT_ROOT / "var/db/test_zhang_ting_bei_liang_yin_stock_data.db"
    test_db_path.parent.mkdir(parents=True, exist_ok=True)
    if test_db_path.exists():
        test_db_path.unlink()

    conn = sqlite3.connect(str(test_db_path))
    try:
        cursor = conn.cursor()
        cursor.execute(
            "CREATE TABLE stocks (code TEXT PRIMARY KEY, name TEXT, asset_type TEXT, is_delisted INTEGER, circulating_market_cap REAL)"
        )
        cursor.execute(
            "CREATE TABLE daily_prices (trade_date TEXT, code TEXT, open REAL, high REAL, low REAL, close REAL, pct_change REAL, amount REAL)"
        )
        cursor.execute(
            "INSERT INTO stocks(code,name,asset_type,is_delisted,circulating_market_cap) VALUES (?,?,?,?,?)",
            ("000001", "平安银行", "stock", 0, 200_000_000_000.0),
        )
        cursor.execute(
            "INSERT INTO stocks(code,name,asset_type,is_delisted,circulating_market_cap) VALUES (?,?,?,?,?)",
            ("600519", "贵州茅台", "stock", 0, 900_000_000_000.0),
        )

        cursor.execute(
            "INSERT INTO daily_prices(trade_date,code,open,high,low,close,pct_change,amount) VALUES (?,?,?,?,?,?,?,?)",
            ("2026-05-14", "000001", 10.0, 10.5, 9.9, 10.4, 10.0, 10000.0),
        )
        cursor.execute(
            "INSERT INTO daily_prices(trade_date,code,open,high,low,close,pct_change,amount) VALUES (?,?,?,?,?,?,?,?)",
            ("2026-05-15", "000001", 10.6, 10.61, 10.29, 10.3, -0.9, 25000.0),
        )
        cursor.execute(
            "INSERT INTO daily_prices(trade_date,code,open,high,low,close,pct_change,amount) VALUES (?,?,?,?,?,?,?,?)",
            ("2026-05-16", "000001", 10.3, 10.4, 10.2, 10.25, -0.5, 1000.0),
        )
        cursor.execute(
            "INSERT INTO daily_prices(trade_date,code,open,high,low,close,pct_change,amount) VALUES (?,?,?,?,?,?,?,?)",
            ("2026-05-19", "000001", 10.5, 10.8, 10.2, 10.7, 1.0, 3000.0),
        )

        cursor.execute(
            "INSERT INTO daily_prices(trade_date,code,open,high,low,close,pct_change,amount) VALUES (?,?,?,?,?,?,?,?)",
            ("2026-05-14", "600519", 1500.0, 1510.0, 1490.0, 1505.0, 1.0, 150000.0),
        )
        cursor.execute(
            "INSERT INTO daily_prices(trade_date,code,open,high,low,close,pct_change,amount) VALUES (?,?,?,?,?,?,?,?)",
            ("2026-05-15", "600519", 1505.0, 1515.0, 1495.0, 1510.0, 1.0, 150000.0),
        )
        cursor.execute(
            "INSERT INTO daily_prices(trade_date,code,open,high,low,close,pct_change,amount) VALUES (?,?,?,?,?,?,?,?)",
            ("2026-05-16", "600519", 1510.0, 1520.0, 1500.0, 1515.0, 1.0, 150000.0),
        )
        cursor.execute(
            "INSERT INTO daily_prices(trade_date,code,open,high,low,close,pct_change,amount) VALUES (?,?,?,?,?,?,?,?)",
            ("2026-05-19", "600519", 1515.0, 1525.0, 1505.0, 1520.0, 1.0, 150000.0),
        )
        conn.commit()
    finally:
        conn.close()

    original_db_path = os.environ.get("NEOTRADE3_STOCK_DB_PATH")
    os.environ["NEOTRADE3_STOCK_DB_PATH"] = str(test_db_path)

    service = BootstrapApiService(project_root=PROJECT_ROOT, api_key="test-key")
    handler = build_handler(service)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        calendar_path = (
            PROJECT_ROOT / "var/ledgers/trading_calendar/trading_calendar.json"
        )
        calendar_path.parent.mkdir(parents=True, exist_ok=True)
        previous_calendar_text = (
            calendar_path.read_text(encoding="utf-8")
            if calendar_path.exists()
            else None
        )
        calendar_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "generated_at": "2026-05-20T00:00:00Z",
                    "generated_by": "test",
                    "source": {"type": "test"},
                    "trading_days": [
                        "2026-05-14",
                        "2026-05-15",
                        "2026-05-16",
                        "2026-05-19",
                    ],
                    "trading_day_count": 4,
                },
                indent=2,
                ensure_ascii=False,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        body = json.dumps(
            {
                "screener_id": "zhang_ting_bei_liang_yin",
                "date": "2026-05-19",
                "requested_by": "test",
                "dry_run": False,
                "parameters": {"top_n": 10},
            }
        ).encode("utf-8")
        request = Request(
            f"http://127.0.0.1:{server.server_port}/api/screeners/run",
            data=body,
            headers={"Content-Type": "application/json", "X-API-Key": "test-key"},
            method="POST",
        )
        with urlopen(request) as response:
            assert response.status == 200

        with urlopen(
            f"http://127.0.0.1:{server.server_port}/api/screeners/runs/2026-05-19/zhang_ting_bei_liang_yin"
        ) as response:
            assert response.status == 200
            payload = json.loads(response.read().decode("utf-8"))
            assert payload["screener_result"]["status"] == "ok"
            assert "000001" in payload["screener_result"]["picks"]
            assert isinstance(payload["screener_result"]["decision_trace"], list)
            assert payload["screener_result"]["decision_trace"]

        with urlopen(
            f"http://127.0.0.1:{server.server_port}/api/screeners/runs/2026-05-19/zhang_ting_bei_liang_yin/download.csv"
        ) as response:
            assert response.status == 200
            csv_text = response.read().decode("utf-8-sig")
            lines = [line for line in csv_text.splitlines() if line.strip()]
            assert lines[0] == "rank,stock_code,stock_name"
            assert any(",000001," in line for line in lines[1:])
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        if original_db_path is None:
            os.environ.pop("NEOTRADE3_STOCK_DB_PATH", None)
        else:
            os.environ["NEOTRADE3_STOCK_DB_PATH"] = original_db_path
        if test_db_path.exists():
            test_db_path.unlink()
        if "previous_calendar_text" in locals():
            if previous_calendar_text is None:
                if calendar_path.exists():
                    calendar_path.unlink()
            else:
                calendar_path.write_text(previous_calendar_text, encoding="utf-8")


def test_jin_feng_huang_screener_run_produces_picks_and_decision_trace() -> None:
    test_db_path = PROJECT_ROOT / "var/db/test_jin_feng_huang_stock_data.db"
    test_db_path.parent.mkdir(parents=True, exist_ok=True)
    if test_db_path.exists():
        test_db_path.unlink()

    conn = sqlite3.connect(str(test_db_path))
    try:
        cursor = conn.cursor()
        cursor.execute(
            "CREATE TABLE stocks (code TEXT PRIMARY KEY, name TEXT, asset_type TEXT, is_delisted INTEGER, circulating_market_cap REAL)"
        )
        cursor.execute(
            "CREATE TABLE daily_prices (trade_date TEXT, code TEXT, open REAL, high REAL, low REAL, close REAL, pct_change REAL, amount REAL)"
        )
        cursor.execute(
            "INSERT INTO stocks(code,name,asset_type,is_delisted,circulating_market_cap) VALUES (?,?,?,?,?)",
            ("000001", "平安银行", "stock", 0, 200_000_000_000.0),
        )
        cursor.execute(
            "INSERT INTO stocks(code,name,asset_type,is_delisted,circulating_market_cap) VALUES (?,?,?,?,?)",
            ("600519", "贵州茅台", "stock", 0, 900_000_000_000.0),
        )

        cursor.execute(
            "INSERT INTO daily_prices(trade_date,code,open,high,low,close,pct_change,amount) VALUES (?,?,?,?,?,?,?,?)",
            ("2026-05-14", "000001", 9.5, 9.8, 9.4, 9.6, 1.0, 5000.0),
        )
        cursor.execute(
            "INSERT INTO daily_prices(trade_date,code,open,high,low,close,pct_change,amount) VALUES (?,?,?,?,?,?,?,?)",
            ("2026-05-15", "000001", 10.0, 11.2, 9.9, 11.0, 10.0, 12000.0),
        )
        cursor.execute(
            "INSERT INTO daily_prices(trade_date,code,open,high,low,close,pct_change,amount) VALUES (?,?,?,?,?,?,?,?)",
            ("2026-05-16", "000001", 11.3, 11.6, 11.25, 11.5, 1.0, 25000.0),
        )
        cursor.execute(
            "INSERT INTO daily_prices(trade_date,code,open,high,low,close,pct_change,amount) VALUES (?,?,?,?,?,?,?,?)",
            ("2026-05-17", "000001", 11.4, 11.5, 11.3, 11.35, -0.5, 10000.0),
        )
        cursor.execute(
            "INSERT INTO daily_prices(trade_date,code,open,high,low,close,pct_change,amount) VALUES (?,?,?,?,?,?,?,?)",
            ("2026-05-19", "000001", 11.6, 12.0, 11.4, 11.8, 1.0, 30000.0),
        )

        cursor.execute(
            "INSERT INTO daily_prices(trade_date,code,open,high,low,close,pct_change,amount) VALUES (?,?,?,?,?,?,?,?)",
            ("2026-05-14", "600519", 1500.0, 1510.0, 1490.0, 1505.0, 1.0, 150000.0),
        )
        cursor.execute(
            "INSERT INTO daily_prices(trade_date,code,open,high,low,close,pct_change,amount) VALUES (?,?,?,?,?,?,?,?)",
            ("2026-05-15", "600519", 1505.0, 1515.0, 1495.0, 1510.0, 1.0, 150000.0),
        )
        cursor.execute(
            "INSERT INTO daily_prices(trade_date,code,open,high,low,close,pct_change,amount) VALUES (?,?,?,?,?,?,?,?)",
            ("2026-05-16", "600519", 1510.0, 1520.0, 1500.0, 1515.0, 1.0, 150000.0),
        )
        cursor.execute(
            "INSERT INTO daily_prices(trade_date,code,open,high,low,close,pct_change,amount) VALUES (?,?,?,?,?,?,?,?)",
            ("2026-05-17", "600519", 1515.0, 1525.0, 1505.0, 1520.0, 1.0, 150000.0),
        )
        cursor.execute(
            "INSERT INTO daily_prices(trade_date,code,open,high,low,close,pct_change,amount) VALUES (?,?,?,?,?,?,?,?)",
            ("2026-05-19", "600519", 1520.0, 1530.0, 1510.0, 1525.0, 1.0, 150000.0),
        )
        conn.commit()
    finally:
        conn.close()

    original_db_path = os.environ.get("NEOTRADE3_STOCK_DB_PATH")
    os.environ["NEOTRADE3_STOCK_DB_PATH"] = str(test_db_path)

    service = BootstrapApiService(project_root=PROJECT_ROOT, api_key="test-key")
    handler = build_handler(service)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        calendar_path = (
            PROJECT_ROOT / "var/ledgers/trading_calendar/trading_calendar.json"
        )
        calendar_path.parent.mkdir(parents=True, exist_ok=True)
        previous_calendar_text = (
            calendar_path.read_text(encoding="utf-8")
            if calendar_path.exists()
            else None
        )
        calendar_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "generated_at": "2026-05-20T00:00:00Z",
                    "generated_by": "test",
                    "source": {"type": "test"},
                    "trading_days": [
                        "2026-05-14",
                        "2026-05-15",
                        "2026-05-16",
                        "2026-05-17",
                        "2026-05-19",
                    ],
                    "trading_day_count": 5,
                },
                indent=2,
                ensure_ascii=False,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        body = json.dumps(
            {
                "screener_id": "jin_feng_huang",
                "date": "2026-05-19",
                "requested_by": "test",
                "dry_run": False,
                "parameters": {"top_n": 10},
            }
        ).encode("utf-8")
        request = Request(
            f"http://127.0.0.1:{server.server_port}/api/screeners/run",
            data=body,
            headers={"Content-Type": "application/json", "X-API-Key": "test-key"},
            method="POST",
        )
        with urlopen(request) as response:
            assert response.status == 200

        with urlopen(
            f"http://127.0.0.1:{server.server_port}/api/screeners/runs/2026-05-19/jin_feng_huang"
        ) as response:
            assert response.status == 200
            payload = json.loads(response.read().decode("utf-8"))
            assert payload["screener_result"]["status"] == "ok"
            assert "000001" in payload["screener_result"]["picks"]
            assert isinstance(payload["screener_result"]["decision_trace"], list)
            assert payload["screener_result"]["decision_trace"]

        with urlopen(
            f"http://127.0.0.1:{server.server_port}/api/screeners/runs/2026-05-19/jin_feng_huang/download.csv"
        ) as response:
            assert response.status == 200
            csv_text = response.read().decode("utf-8-sig")
            lines = [line for line in csv_text.splitlines() if line.strip()]
            assert lines[0] == "rank,stock_code,stock_name"
            assert any(",000001," in line for line in lines[1:])
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        if original_db_path is None:
            os.environ.pop("NEOTRADE3_STOCK_DB_PATH", None)
        else:
            os.environ["NEOTRADE3_STOCK_DB_PATH"] = original_db_path
        if test_db_path.exists():
            test_db_path.unlink()
        if "previous_calendar_text" in locals():
            if previous_calendar_text is None:
                if calendar_path.exists():
                    calendar_path.unlink()
            else:
                calendar_path.write_text(previous_calendar_text, encoding="utf-8")


def test_yin_feng_huang_screener_run_produces_picks_and_decision_trace() -> None:
    test_db_path = PROJECT_ROOT / "var/db/test_yin_feng_huang_stock_data.db"
    test_db_path.parent.mkdir(parents=True, exist_ok=True)
    if test_db_path.exists():
        test_db_path.unlink()

    conn = sqlite3.connect(str(test_db_path))
    try:
        cursor = conn.cursor()
        cursor.execute(
            "CREATE TABLE stocks (code TEXT PRIMARY KEY, name TEXT, asset_type TEXT, is_delisted INTEGER, circulating_market_cap REAL)"
        )
        cursor.execute(
            "CREATE TABLE daily_prices (trade_date TEXT, code TEXT, open REAL, high REAL, low REAL, close REAL, pct_change REAL, amount REAL)"
        )
        cursor.execute(
            "INSERT INTO stocks(code,name,asset_type,is_delisted,circulating_market_cap) VALUES (?,?,?,?,?)",
            ("000001", "平安银行", "stock", 0, 200_000_000_000.0),
        )
        cursor.execute(
            "INSERT INTO stocks(code,name,asset_type,is_delisted,circulating_market_cap) VALUES (?,?,?,?,?)",
            ("600519", "贵州茅台", "stock", 0, 900_000_000_000.0),
        )

        cursor.execute(
            "INSERT INTO daily_prices(trade_date,code,open,high,low,close,pct_change,amount) VALUES (?,?,?,?,?,?,?,?)",
            ("2026-05-14", "000001", 9.5, 9.8, 9.4, 9.6, 1.0, 5000.0),
        )
        cursor.execute(
            "INSERT INTO daily_prices(trade_date,code,open,high,low,close,pct_change,amount) VALUES (?,?,?,?,?,?,?,?)",
            ("2026-05-15", "000001", 10.0, 11.2, 9.9, 11.0, 10.0, 12000.0),
        )
        cursor.execute(
            "INSERT INTO daily_prices(trade_date,code,open,high,low,close,pct_change,amount) VALUES (?,?,?,?,?,?,?,?)",
            ("2026-05-16", "000001", 11.0, 11.2, 10.1, 10.5, -4.5, 2000.0),
        )
        cursor.execute(
            "INSERT INTO daily_prices(trade_date,code,open,high,low,close,pct_change,amount) VALUES (?,?,?,?,?,?,?,?)",
            ("2026-05-17", "000001", 10.5, 10.8, 10.3, 10.7, 1.0, 6000.0),
        )

        cursor.execute(
            "INSERT INTO daily_prices(trade_date,code,open,high,low,close,pct_change,amount) VALUES (?,?,?,?,?,?,?,?)",
            ("2026-05-14", "600519", 1500.0, 1510.0, 1490.0, 1505.0, 1.0, 150000.0),
        )
        cursor.execute(
            "INSERT INTO daily_prices(trade_date,code,open,high,low,close,pct_change,amount) VALUES (?,?,?,?,?,?,?,?)",
            ("2026-05-15", "600519", 1505.0, 1515.0, 1495.0, 1510.0, 1.0, 150000.0),
        )
        cursor.execute(
            "INSERT INTO daily_prices(trade_date,code,open,high,low,close,pct_change,amount) VALUES (?,?,?,?,?,?,?,?)",
            ("2026-05-16", "600519", 1510.0, 1520.0, 1500.0, 1515.0, 1.0, 150000.0),
        )
        cursor.execute(
            "INSERT INTO daily_prices(trade_date,code,open,high,low,close,pct_change,amount) VALUES (?,?,?,?,?,?,?,?)",
            ("2026-05-17", "600519", 1515.0, 1525.0, 1505.0, 1520.0, 1.0, 150000.0),
        )
        conn.commit()
    finally:
        conn.close()

    original_db_path = os.environ.get("NEOTRADE3_STOCK_DB_PATH")
    os.environ["NEOTRADE3_STOCK_DB_PATH"] = str(test_db_path)

    service = BootstrapApiService(project_root=PROJECT_ROOT, api_key="test-key")
    handler = build_handler(service)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        calendar_path = (
            PROJECT_ROOT / "var/ledgers/trading_calendar/trading_calendar.json"
        )
        calendar_path.parent.mkdir(parents=True, exist_ok=True)
        previous_calendar_text = (
            calendar_path.read_text(encoding="utf-8")
            if calendar_path.exists()
            else None
        )
        calendar_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "generated_at": "2026-05-20T00:00:00Z",
                    "generated_by": "test",
                    "source": {"type": "test"},
                    "trading_days": [
                        "2026-05-14",
                        "2026-05-15",
                        "2026-05-16",
                        "2026-05-17",
                    ],
                    "trading_day_count": 4,
                },
                indent=2,
                ensure_ascii=False,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        body = json.dumps(
            {
                "screener_id": "yin_feng_huang",
                "date": "2026-05-17",
                "requested_by": "test",
                "dry_run": False,
                "parameters": {"top_n": 10},
            }
        ).encode("utf-8")
        request = Request(
            f"http://127.0.0.1:{server.server_port}/api/screeners/run",
            data=body,
            headers={"Content-Type": "application/json", "X-API-Key": "test-key"},
            method="POST",
        )
        with urlopen(request) as response:
            assert response.status == 200

        with urlopen(
            f"http://127.0.0.1:{server.server_port}/api/screeners/runs/2026-05-17/yin_feng_huang"
        ) as response:
            assert response.status == 200
            payload = json.loads(response.read().decode("utf-8"))
            assert payload["screener_result"]["status"] == "ok"
            assert "000001" in payload["screener_result"]["picks"]
            assert isinstance(payload["screener_result"]["decision_trace"], list)
            assert payload["screener_result"]["decision_trace"]

        with urlopen(
            f"http://127.0.0.1:{server.server_port}/api/screeners/runs/2026-05-17/yin_feng_huang/download.csv"
        ) as response:
            assert response.status == 200
            csv_text = response.read().decode("utf-8-sig")
            lines = [line for line in csv_text.splitlines() if line.strip()]
            assert lines[0] == "rank,stock_code,stock_name"
            assert any(",000001," in line for line in lines[1:])
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        if original_db_path is None:
            os.environ.pop("NEOTRADE3_STOCK_DB_PATH", None)
        else:
            os.environ["NEOTRADE3_STOCK_DB_PATH"] = original_db_path
        if test_db_path.exists():
            test_db_path.unlink()
        if "previous_calendar_text" in locals():
            if previous_calendar_text is None:
                if calendar_path.exists():
                    calendar_path.unlink()
            else:
                calendar_path.write_text(previous_calendar_text, encoding="utf-8")


def test_shi_pan_xian_screener_run_produces_picks_and_decision_trace() -> None:
    test_db_path = PROJECT_ROOT / "var/db/test_shi_pan_xian_stock_data.db"
    test_db_path.parent.mkdir(parents=True, exist_ok=True)
    if test_db_path.exists():
        test_db_path.unlink()

    target = date(2026, 5, 19)
    trading_days = [
        date.fromordinal(target.toordinal() - (54 - idx)).isoformat()
        for idx in range(55)
    ]

    conn = sqlite3.connect(str(test_db_path))
    try:
        cursor = conn.cursor()
        cursor.execute(
            "CREATE TABLE stocks (code TEXT PRIMARY KEY, name TEXT, asset_type TEXT, is_delisted INTEGER, circulating_market_cap REAL)"
        )
        cursor.execute(
            "CREATE TABLE daily_prices (trade_date TEXT, code TEXT, open REAL, high REAL, low REAL, close REAL, volume REAL, pct_change REAL)"
        )
        cursor.execute(
            "INSERT INTO stocks(code,name,asset_type,is_delisted,circulating_market_cap) VALUES (?,?,?,?,?)",
            ("000001", "平安银行", "stock", 0, 200_000_000_000.0),
        )

        for idx, day in enumerate(trading_days):
            open_price = 10.0
            high_price = 10.1
            low_price = 9.9
            close_price = 10.0
            volume = 100.0
            pct_change = 0.0

            if idx == 49:
                open_price = 10.0
                close_price = 10.5
                high_price = 10.6
                low_price = 9.95
                volume = 2000.0
                pct_change = 5.0
            elif idx == 50:
                open_price = 11.0
                close_price = 11.55
                high_price = 11.55
                low_price = 11.0
                volume = 1500.0
                pct_change = 10.0
            elif idx == 51:
                open_price = 11.5
                close_price = 11.3
                high_price = 11.5
                low_price = 11.1
                volume = 600.0
                pct_change = -2.0
            elif idx == 52:
                open_price = 11.4
                close_price = 11.2
                high_price = 11.4
                low_price = 11.05
                volume = 400.0
                pct_change = -1.0
            elif idx == 53:
                open_price = 11.2
                close_price = 11.25
                high_price = 11.35
                low_price = 11.1
                volume = 450.0
                pct_change = 0.5
            elif idx == 54:
                open_price = 11.25
                close_price = 11.3
                high_price = 11.4
                low_price = 11.1
                volume = 700.0
                pct_change = 0.4

            cursor.execute(
                "INSERT INTO daily_prices(trade_date,code,open,high,low,close,volume,pct_change) VALUES (?,?,?,?,?,?,?,?)",
                (
                    day,
                    "000001",
                    open_price,
                    high_price,
                    low_price,
                    close_price,
                    volume,
                    pct_change,
                ),
            )

        conn.commit()
    finally:
        conn.close()

    original_db_path = os.environ.get("NEOTRADE3_STOCK_DB_PATH")
    os.environ["NEOTRADE3_STOCK_DB_PATH"] = str(test_db_path)

    service = BootstrapApiService(project_root=PROJECT_ROOT, api_key="test-key")
    handler = build_handler(service)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        calendar_path = (
            PROJECT_ROOT / "var/ledgers/trading_calendar/trading_calendar.json"
        )
        calendar_path.parent.mkdir(parents=True, exist_ok=True)
        previous_calendar_text = (
            calendar_path.read_text(encoding="utf-8")
            if calendar_path.exists()
            else None
        )
        calendar_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "generated_at": "2026-05-20T00:00:00Z",
                    "generated_by": "test",
                    "source": {"type": "test"},
                    "trading_days": trading_days,
                    "trading_day_count": len(trading_days),
                },
                indent=2,
                ensure_ascii=False,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        body = json.dumps(
            {
                "screener_id": "shi_pan_xian",
                "date": target.isoformat(),
                "requested_by": "test",
                "dry_run": False,
                "parameters": {"top_n": 10},
            }
        ).encode("utf-8")
        request = Request(
            f"http://127.0.0.1:{server.server_port}/api/screeners/run",
            data=body,
            headers={"Content-Type": "application/json", "X-API-Key": "test-key"},
            method="POST",
        )
        with urlopen(request) as response:
            assert response.status == 200

        with urlopen(
            f"http://127.0.0.1:{server.server_port}/api/screeners/runs/{target.isoformat()}/shi_pan_xian"
        ) as response:
            assert response.status == 200
            payload = json.loads(response.read().decode("utf-8"))
            assert payload["screener_result"]["status"] == "ok"
            assert "000001" in payload["screener_result"]["picks"]
            assert isinstance(payload["screener_result"]["decision_trace"], list)
            assert payload["screener_result"]["decision_trace"]

        with urlopen(
            f"http://127.0.0.1:{server.server_port}/api/screeners/runs/{target.isoformat()}/shi_pan_xian/download.csv"
        ) as response:
            assert response.status == 200
            csv_text = response.read().decode("utf-8-sig")
            lines = [line for line in csv_text.splitlines() if line.strip()]
            assert lines[0] == "rank,stock_code,stock_name"
            assert any(",000001," in line for line in lines[1:])
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        if original_db_path is None:
            os.environ.pop("NEOTRADE3_STOCK_DB_PATH", None)
        else:
            os.environ["NEOTRADE3_STOCK_DB_PATH"] = original_db_path
        if test_db_path.exists():
            test_db_path.unlink()
        if "previous_calendar_text" in locals():
            if previous_calendar_text is None:
                if calendar_path.exists():
                    calendar_path.unlink()
            else:
                calendar_path.write_text(previous_calendar_text, encoding="utf-8")


def test_cup_handle_v4_screener_run_produces_picks_and_decision_trace() -> None:
    test_db_path = PROJECT_ROOT / "var/db/test_cup_handle_v4_stock_data.db"
    test_db_path.parent.mkdir(parents=True, exist_ok=True)
    if test_db_path.exists():
        test_db_path.unlink()

    target = date(2026, 5, 19)
    trading_days = [
        date.fromordinal(target.toordinal() - (116 - idx)).isoformat()
        for idx in range(117)
    ]

    conn = sqlite3.connect(str(test_db_path))
    try:
        cursor = conn.cursor()
        cursor.execute(
            "CREATE TABLE stocks (code TEXT PRIMARY KEY, name TEXT, asset_type TEXT, is_delisted INTEGER, circulating_market_cap REAL)"
        )
        cursor.execute(
            "CREATE TABLE daily_prices (trade_date TEXT, code TEXT, open REAL, high REAL, low REAL, close REAL, pct_change REAL, amount REAL)"
        )
        cursor.execute(
            "INSERT INTO stocks(code,name,asset_type,is_delisted,circulating_market_cap) VALUES (?,?,?,?,?)",
            ("000001", "平安银行", "stock", 0, 200_000_000_000.0),
        )
        cursor.execute(
            "INSERT INTO stocks(code,name,asset_type,is_delisted,circulating_market_cap) VALUES (?,?,?,?,?)",
            ("600519", "贵州茅台", "stock", 0, 900_000_000_000.0),
        )

        left_rim_idx = 30
        right_rim_idx = 105
        bottom_idx = 60

        for idx, day in enumerate(trading_days):
            base_close = 10.0 + idx * 0.01
            close_price = base_close
            open_price = close_price - 0.05
            high_price = close_price + 0.15
            low_price = close_price - 0.15
            amount = 2000.0
            pct_change = 0.0

            if idx == left_rim_idx:
                close_price = 19.0
                open_price = 18.8
                high_price = 20.0
                low_price = 18.6
                amount = 1200.0
            elif left_rim_idx < idx <= left_rim_idx + 11:
                step = idx - left_rim_idx
                close_price = 19.0 - step * (5.0 / 11.0)
                open_price = close_price + 0.05
                high_price = close_price + 0.10
                low_price = close_price - 0.20
                amount = 1000.0
            elif idx == bottom_idx:
                close_price = 14.2
                open_price = 14.4
                high_price = 14.6
                low_price = 14.0
                amount = 1500.0
            elif right_rim_idx - 11 <= idx < right_rim_idx:
                step = idx - (right_rim_idx - 11)
                close_price = 14.5 + step * (4.5 / 11.0)
                open_price = close_price - 0.05
                high_price = close_price + 0.15
                low_price = close_price - 0.20
                amount = 5000.0
            elif idx == right_rim_idx:
                close_price = 19.5
                open_price = 19.3
                high_price = 20.0
                low_price = 19.1
                amount = 5000.0
            elif idx > right_rim_idx:
                close_price = 18.5
                open_price = 18.4
                high_price = 19.0
                low_price = 18.2
                amount = 2500.0

            cursor.execute(
                "INSERT INTO daily_prices(trade_date,code,open,high,low,close,pct_change,amount) VALUES (?,?,?,?,?,?,?,?)",
                (
                    day,
                    "000001",
                    open_price,
                    high_price,
                    low_price,
                    close_price,
                    pct_change,
                    amount,
                ),
            )

            cursor.execute(
                "INSERT INTO daily_prices(trade_date,code,open,high,low,close,pct_change,amount) VALUES (?,?,?,?,?,?,?,?)",
                (
                    day,
                    "600519",
                    1500.0,
                    1510.0,
                    1490.0,
                    1505.0,
                    0.1,
                    150000.0,
                ),
            )

        conn.commit()
    finally:
        conn.close()

    original_db_path = os.environ.get("NEOTRADE3_STOCK_DB_PATH")
    os.environ["NEOTRADE3_STOCK_DB_PATH"] = str(test_db_path)

    service = BootstrapApiService(project_root=PROJECT_ROOT, api_key="test-key")
    handler = build_handler(service)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        calendar_path = (
            PROJECT_ROOT / "var/ledgers/trading_calendar/trading_calendar.json"
        )
        calendar_path.parent.mkdir(parents=True, exist_ok=True)
        previous_calendar_text = (
            calendar_path.read_text(encoding="utf-8")
            if calendar_path.exists()
            else None
        )
        calendar_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "generated_at": "2026-05-20T00:00:00Z",
                    "generated_by": "test",
                    "source": {"type": "test"},
                    "trading_days": trading_days,
                    "trading_day_count": len(trading_days),
                },
                indent=2,
                ensure_ascii=False,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        body = json.dumps(
            {
                "screener_id": "cup_handle_v4",
                "date": target.isoformat(),
                "requested_by": "test",
                "dry_run": False,
                "parameters": {
                    "top_n": 10,
                    "rim_interval_max": 80,
                    "history_buffer_days": 0,
                },
            }
        ).encode("utf-8")
        request = Request(
            f"http://127.0.0.1:{server.server_port}/api/screeners/run",
            data=body,
            headers={"Content-Type": "application/json", "X-API-Key": "test-key"},
            method="POST",
        )
        with urlopen(request) as response:
            assert response.status == 200

        with urlopen(
            f"http://127.0.0.1:{server.server_port}/api/screeners/runs/{target.isoformat()}/cup_handle_v4"
        ) as response:
            assert response.status == 200
            payload = json.loads(response.read().decode("utf-8"))
            assert payload["screener_result"]["status"] == "ok"
            assert "000001" in payload["screener_result"]["picks"]
            assert isinstance(payload["screener_result"]["decision_trace"], list)
            assert payload["screener_result"]["decision_trace"]

        with urlopen(
            f"http://127.0.0.1:{server.server_port}/api/screeners/runs/{target.isoformat()}/cup_handle_v4/download.csv"
        ) as response:
            assert response.status == 200
            csv_text = response.read().decode("utf-8-sig")
            lines = [line for line in csv_text.splitlines() if line.strip()]
            assert lines[0] == "rank,stock_code,stock_name"
            assert any(",000001," in line for line in lines[1:])
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        if original_db_path is None:
            os.environ.pop("NEOTRADE3_STOCK_DB_PATH", None)
        else:
            os.environ["NEOTRADE3_STOCK_DB_PATH"] = original_db_path
        if test_db_path.exists():
            test_db_path.unlink()
        if "previous_calendar_text" in locals():
            if previous_calendar_text is None:
                if calendar_path.exists():
                    calendar_path.unlink()
            else:
                calendar_path.write_text(previous_calendar_text, encoding="utf-8")


def test_bootstrap_api_handler_allows_dashboard_cross_origin_reads() -> None:
    service = BootstrapApiService(project_root=PROJECT_ROOT)
    handler = build_handler(service)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        request = Request(
            f"http://127.0.0.1:{server.server_port}/healthz",
            headers={"Origin": "http://127.0.0.1:18031"},
        )
        with urlopen(request) as response:
            assert response.status == 200
            assert (
                response.headers["Access-Control-Allow-Origin"]
                == "http://127.0.0.1:18031"
            )
            assert "GET" in response.headers["Access-Control-Allow-Methods"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_factor_matrix_daily_output_supports_live_and_stored_modes() -> None:
    test_db_path = PROJECT_ROOT / "var/db/test_factor_matrix_stock_data.db"
    test_db_path.parent.mkdir(parents=True, exist_ok=True)
    if test_db_path.exists():
        test_db_path.unlink()

    conn = sqlite3.connect(str(test_db_path))
    try:
        cursor = conn.cursor()
        cursor.execute(
            "CREATE TABLE stocks (code TEXT PRIMARY KEY, name TEXT, sector_lv1 TEXT, sector_lv2 TEXT, asset_type TEXT, is_delisted INTEGER)"
        )
        cursor.execute(
            "CREATE TABLE daily_prices (trade_date TEXT, code TEXT, close REAL, preclose REAL, pct_change REAL, volume REAL, amount REAL)"
        )
        cursor.execute(
            "INSERT INTO stocks(code,name,sector_lv1,sector_lv2,asset_type,is_delisted) VALUES (?,?,?,?,?,?)",
            ("000001", "平安银行", "金融", "银行", "stock", 0),
        )
        cursor.execute(
            "INSERT INTO stocks(code,name,sector_lv1,sector_lv2,asset_type,is_delisted) VALUES (?,?,?,?,?,?)",
            ("600519", "贵州茅台", "消费", "白酒", "stock", 0),
        )
        cursor.execute(
            "INSERT INTO daily_prices(trade_date,code,close,preclose,pct_change,volume,amount) VALUES (?,?,?,?,?,?,?)",
            ("2026-05-19", "000001", 11.0, 10.0, 10.0, 1000.0, 11000.0),
        )
        cursor.execute(
            "INSERT INTO daily_prices(trade_date,code,close,preclose,pct_change,volume,amount) VALUES (?,?,?,?,?,?,?)",
            (
                "2026-05-19",
                "600519",
                1500.0,
                1490.0,
                0.6711409395973155,
                100.0,
                150000.0,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    original_db_path = os.environ.get("NEOTRADE3_STOCK_DB_PATH")
    os.environ["NEOTRADE3_STOCK_DB_PATH"] = str(test_db_path)

    service = BootstrapApiService(project_root=PROJECT_ROOT, api_key="test-key")
    handler = build_handler(service)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        calendar_path = (
            PROJECT_ROOT / "var/ledgers/trading_calendar/trading_calendar.json"
        )
        calendar_path.parent.mkdir(parents=True, exist_ok=True)
        previous_calendar_text = (
            calendar_path.read_text(encoding="utf-8")
            if calendar_path.exists()
            else None
        )
        calendar_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "generated_at": "2026-05-20T00:00:00Z",
                    "generated_by": "test",
                    "source": {"type": "test"},
                    "trading_days": ["2026-05-19"],
                    "trading_day_count": 1,
                },
                indent=2,
                ensure_ascii=False,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        with urlopen(
            f"http://127.0.0.1:{server.server_port}/api/factor-matrix/daily?date=2026-05-19"
        ) as response:
            assert response.status == 200
            payload = json.loads(response.read().decode("utf-8"))
            assert payload["_meta"]["status"] == "ok"
            assert payload["_meta"]["self_heal"] in {"none", "generated"}
            assert payload["target_date"] == "2026-05-19"
            assert payload["candidates_summary"]["candidate_count"] >= 1
            assert (
                payload["market_context"]["focus_themes_source"]
                == "top5_sectors_by_amount_proxy"
            )

        body = json.dumps(
            {
                "lab_id": "cup_handle_lab",
                "date": "2026-05-19",
                "requested_by": "test",
                "dry_run": False,
            }
        ).encode("utf-8")
        request = Request(
            f"http://127.0.0.1:{server.server_port}/api/labs/run",
            data=body,
            headers={"Content-Type": "application/json", "X-API-Key": "test-key"},
            method="POST",
        )
        with urlopen(request) as response:
            assert response.status == 200
            payload = json.loads(response.read().decode("utf-8"))
            assert payload["_meta"]["status"] == "ok"
            assert payload["lab_run"]["lab_id"] == "cup_handle_lab"

        with urlopen(
            f"http://127.0.0.1:{server.server_port}/api/labs/runs?date=2026-05-19&limit=10"
        ) as response:
            assert response.status == 200
            payload = json.loads(response.read().decode("utf-8"))
            assert payload["_meta"]["returned_count"] >= 1
            assert any(
                item.get("lab_id") == "cup_handle_lab" for item in payload["lab_runs"]
            )

        with urlopen(
            f"http://127.0.0.1:{server.server_port}/api/labs/runs/2026-05-19/cup_handle_lab"
        ) as response:
            assert response.status == 200
            payload = json.loads(response.read().decode("utf-8"))
            assert payload["_meta"]["status"] == "ok"
            assert payload["lab_result"]["lab_id"] == "cup_handle_lab"

        with urlopen(
            f"http://127.0.0.1:{server.server_port}/api/labs/runs/2026-05-19/cup_handle_lab/download"
        ) as response:
            assert response.status == 200
            assert "attachment" in response.headers.get("Content-Disposition", "")
            payload = json.loads(response.read().decode("utf-8"))
            assert payload["lab_id"] == "cup_handle_lab"

        body = json.dumps(
            {
                "date": "2026-05-19",
                "publish_succeeded": False,
                "requested_by": "test",
                "dry_run": False,
            }
        ).encode("utf-8")
        request = Request(
            f"http://127.0.0.1:{server.server_port}/api/orchestration/run",
            data=body,
            headers={"Content-Type": "application/json", "X-API-Key": "test-key"},
            method="POST",
        )
        with urlopen(request) as response:
            assert response.status == 200
            payload = json.loads(response.read().decode("utf-8"))
            assert payload["_meta"]["status"] == "ok"
            assert payload["orchestrator_run"]["target_date"] == "2026-05-19"

        with urlopen(
            f"http://127.0.0.1:{server.server_port}/api/orchestration/runs?date=2026-05-19&limit=10"
        ) as response:
            assert response.status == 200
            payload = json.loads(response.read().decode("utf-8"))
            assert payload["_meta"]["returned_count"] >= 1
            assert any(
                item.get("target_date") == "2026-05-19"
                for item in payload["orchestrator_runs"]
            )

        with urlopen(
            f"http://127.0.0.1:{server.server_port}/api/orchestration/runs/2026-05-19"
        ) as response:
            assert response.status == 200
            payload = json.loads(response.read().decode("utf-8"))
            assert payload["_meta"]["status"] == "ok"
            assert payload["orchestrator_run"]["target_date"] == "2026-05-19"
            assert payload["orchestrator_result"]["target_date"] == "2026-05-19"

        with urlopen(
            f"http://127.0.0.1:{server.server_port}/api/orchestration/runs/2026-05-19/download"
        ) as response:
            assert response.status == 200
            assert "attachment" in response.headers.get("Content-Disposition", "")
            payload = json.loads(response.read().decode("utf-8"))
            assert payload["target_date"] == "2026-05-19"

        with urlopen(
            f"http://127.0.0.1:{server.server_port}/api/labs/runs/2026-05-19/five_flags_lab"
        ) as response:
            assert response.status == 200
            payload = json.loads(response.read().decode("utf-8"))
            assert payload["lab_result"]["lab_id"] == "five_flags_lab"
            scan = payload["lab_result"]["artifacts"]["five_flags_scan_results"]
            assert scan["pool"]

        with urlopen(
            f"http://127.0.0.1:{server.server_port}/api/labs/runs/2026-05-19/paper_simulation_lab"
        ) as response:
            assert response.status == 200
            payload = json.loads(response.read().decode("utf-8"))
            assert payload["lab_result"]["lab_id"] == "paper_simulation_lab"
            positions = payload["lab_result"]["artifacts"]["paper_simulation_positions"]
            assert positions["cash_yuan"] > 0
            assert positions["universe_snapshot"]["candidate_count"] >= 1

        with urlopen(
            f"http://127.0.0.1:{server.server_port}/api/data-control/runs?date=2026-05-19&limit=10"
        ) as response:
            assert response.status == 200
            payload = json.loads(response.read().decode("utf-8"))
            assert payload["_meta"]["returned_count"] >= 1

        with urlopen(
            f"http://127.0.0.1:{server.server_port}/api/data-control/runs/2026-05-19/capture"
        ) as response:
            assert response.status == 200
            payload = json.loads(response.read().decode("utf-8"))
            assert payload["_meta"]["status"] == "ok"
            assert payload["data_control_run"]["target_date"] == "2026-05-19"

        with urlopen(
            f"http://127.0.0.1:{server.server_port}/api/data-control/runs/2026-05-19/capture/download"
        ) as response:
            assert response.status == 200
            assert "attachment" in response.headers.get("Content-Disposition", "")
            payload = json.loads(response.read().decode("utf-8"))
            assert payload["target_date"] == "2026-05-19"

        request = Request(
            f"http://127.0.0.1:{server.server_port}/api/factor-matrix/daily?date=2026-05-19&debug=1",
            method="GET",
        )
        try:
            urlopen(request)
            assert False, "expected request to fail"
        except Exception as exc:
            assert "HTTP Error 401" in str(exc)

        request = Request(
            f"http://127.0.0.1:{server.server_port}/api/factor-matrix/daily?date=2026-05-19&debug=1",
            headers={"X-API-Key": "test-key"},
            method="GET",
        )
        with urlopen(request) as response:
            assert response.status == 200
            payload = json.loads(response.read().decode("utf-8"))
            assert payload["_meta"]["debug"] is True
            first_bucket = (
                payload["tiers"]["ge_80"]
                or payload["tiers"]["ge_70"]
                or payload["tiers"]["ge_60"]
            )
            assert first_bucket
            first_signal = first_bucket[0]["signals"][0]
            assert "raw_refs" in first_signal

        body = json.dumps(
            {"date": "2026-05-19", "requested_by": "test", "dry_run": False}
        ).encode("utf-8")
        request = Request(
            f"http://127.0.0.1:{server.server_port}/api/factor-matrix/daily/run",
            data=body,
            headers={"Content-Type": "application/json", "X-API-Key": "test-key"},
            method="POST",
        )
        with urlopen(request) as response:
            assert response.status == 200
            payload = json.loads(response.read().decode("utf-8"))
            assert payload["_meta"]["status"] == "ok"
            assert payload["factor_matrix_run"]["target_date"] == "2026-05-19"

        with urlopen(
            f"http://127.0.0.1:{server.server_port}/api/factor-matrix/daily?date=2026-05-19"
        ) as response:
            assert response.status == 200
            payload = json.loads(response.read().decode("utf-8"))
            assert payload["_meta"]["status"] == "ok"
            assert payload["target_date"] == "2026-05-19"
            all_candidates = (
                payload["tiers"]["ge_80"]
                + payload["tiers"]["ge_70"]
                + payload["tiers"]["ge_60"]
            )
            assert all_candidates
            assert any(
                any(
                    sig.get("source") == "lab" and sig.get("name") == "老鸭头五图"
                    for sig in cand.get("signals", [])
                )
                for cand in all_candidates
            )
            assert any(
                any(
                    sig.get("source") == "lab"
                    and sig.get("name") == "量化模拟交易实验室"
                    for sig in cand.get("signals", [])
                )
                for cand in all_candidates
            )

        with urlopen(
            f"http://127.0.0.1:{server.server_port}/api/factor-matrix/daily/2026-05-19/download"
        ) as response:
            assert response.status == 200
            assert "attachment" in response.headers.get("Content-Disposition", "")
            payload = json.loads(response.read().decode("utf-8"))
            assert payload["target_date"] == "2026-05-19"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        if original_db_path is None:
            os.environ.pop("NEOTRADE3_STOCK_DB_PATH", None)
        else:
            os.environ["NEOTRADE3_STOCK_DB_PATH"] = original_db_path
        if "previous_calendar_text" in locals():
            if previous_calendar_text is None:
                if calendar_path.exists():
                    calendar_path.unlink()
            else:
                calendar_path.write_text(previous_calendar_text, encoding="utf-8")
        shutil.rmtree(
            PROJECT_ROOT / "var/ledgers/factor_matrix" / "2026-05-19",
            ignore_errors=True,
        )
        shutil.rmtree(
            PROJECT_ROOT / "var/artifacts/factor_matrix" / "2026-05-19",
            ignore_errors=True,
        )
        shutil.rmtree(
            PROJECT_ROOT / "var/ledgers/lab_runs" / "2026-05-19", ignore_errors=True
        )
        shutil.rmtree(
            PROJECT_ROOT / "var/artifacts/lab_runs" / "2026-05-19", ignore_errors=True
        )
        shutil.rmtree(
            PROJECT_ROOT / "var/ledgers/orchestration_runs" / "2026-05-19",
            ignore_errors=True,
        )
        shutil.rmtree(
            PROJECT_ROOT / "var/artifacts/orchestration_runs" / "2026-05-19",
            ignore_errors=True,
        )
        shutil.rmtree(
            PROJECT_ROOT / "var/ledgers/screener_runs" / "2026-05-19",
            ignore_errors=True,
        )
        shutil.rmtree(
            PROJECT_ROOT / "var/artifacts/screener_runs" / "2026-05-19",
            ignore_errors=True,
        )
        shutil.rmtree(
            PROJECT_ROOT / "var/ledgers/pools" / "2026-05-19",
            ignore_errors=True,
        )
        shutil.rmtree(
            PROJECT_ROOT / "var/artifacts/pools" / "2026-05-19",
            ignore_errors=True,
        )
        shutil.rmtree(
            PROJECT_ROOT / "var/ledgers/data_control" / "2026-05-19", ignore_errors=True
        )
        shutil.rmtree(
            PROJECT_ROOT / "var/artifacts/data_control" / "2026-05-19",
            ignore_errors=True,
        )
        if test_db_path.exists():
            test_db_path.unlink()


def test_dashboard_page_builder_renders_sections_and_api_base_url() -> None:
    dashboard_builder = DashboardPageBuilder(api_base_url="http://127.0.0.1:18030")
    dashboard_handler = build_dashboard_handler(dashboard_builder)
    dashboard_server = ThreadingHTTPServer(("127.0.0.1", 0), dashboard_handler)
    dashboard_thread = Thread(target=dashboard_server.serve_forever, daemon=True)
    dashboard_thread.start()

    try:
        try:
            urlopen(f"http://127.0.0.1:{dashboard_server.server_port}/")
            raise AssertionError("expected dashboard to be retired")
        except Exception as exc:
            assert getattr(exc, "code", None) == 410
            body = exc.read().decode("utf-8")
            assert "retired" in body.lower()
    finally:
        dashboard_server.shutdown()
        dashboard_server.server_close()
        dashboard_thread.join(timeout=2)


def test_dashboard_page_builder_loads_static_assets() -> None:
    dashboard_builder = DashboardPageBuilder(api_base_url="http://127.0.0.1:18030")
    dashboard_handler = build_dashboard_handler(dashboard_builder)
    dashboard_server = ThreadingHTTPServer(("127.0.0.1", 0), dashboard_handler)
    dashboard_thread = Thread(target=dashboard_server.serve_forever, daemon=True)
    dashboard_thread.start()

    try:
        try:
            urlopen(f"http://127.0.0.1:{dashboard_server.server_port}/healthz")
            raise AssertionError("expected dashboard to be retired")
        except Exception as exc:
            assert getattr(exc, "code", None) == 410
            payload = json.loads(exc.read().decode("utf-8"))
            assert payload["status"] == "gone"
    finally:
        dashboard_server.shutdown()
        dashboard_server.server_close()
        dashboard_thread.join(timeout=2)


def test_http_end_to_end_api_and_error_paths(tmp_path: Path) -> None:
    worker = BootstrapWorkerApp(project_root=PROJECT_ROOT)
    worker.paths["ledgers_root"] = tmp_path / "ledgers"
    worker.paths["artifacts_root"] = tmp_path / "artifacts"
    worker.run(
        target_date=date(2026, 5, 19),
        publish_succeeded=False,
        write_outputs=True,
    )

    service = BootstrapApiService(project_root=PROJECT_ROOT)
    service.worker_app.paths["ledgers_root"] = tmp_path / "ledgers"
    service.worker_app.paths["artifacts_root"] = tmp_path / "artifacts"
    handler = build_handler(service)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        base_url = f"http://127.0.0.1:{server.server_port}"

        with urlopen(
            f"{base_url}/api/bootstrap-summary?date=2026-05-19"
        ) as response:
            assert response.status == 200
            payload = json.loads(response.read().decode("utf-8"))

        with urlopen(f"{base_url}/api/config-contracts") as response:
            assert response.status == 200
            contracts_payload = json.loads(response.read().decode("utf-8"))

        with urlopen(f"{base_url}/api/migration/feature-manual") as response:
            assert response.status == 200
            feature_manual_payload = json.loads(response.read().decode("utf-8"))

        with urlopen(
            f"{base_url}/api/migration/feature-mapping?domain=strategy_and_lab"
        ) as response:
            assert response.status == 200
            feature_mapping_payload = json.loads(response.read().decode("utf-8"))

        with urlopen(
            f"{base_url}/api/migration/feature-mapping?domain=assistant"
        ) as response:
            assert response.status == 200
            assistant_mapping_payload = json.loads(response.read().decode("utf-8"))

        with urlopen(
            f"{base_url}/api/migration/feature-mapping?domain=operations"
        ) as response:
            assert response.status == 200
            operations_mapping_payload = json.loads(response.read().decode("utf-8"))

        with urlopen(
            f"{base_url}/api/migration/feature-mapping?domain=screeners"
        ) as response:
            assert response.status == 200
            screeners_mapping_payload = json.loads(response.read().decode("utf-8"))

        try:
            urlopen(f"{base_url}/api/bootstrap-summary?date=bad-date")
        except Exception as exc:
            error_response = exc
        else:
            raise AssertionError("expected invalid date request to fail")

        error_body = json.loads(error_response.read().decode("utf-8"))

        assert payload["summary"]
        assert contracts_payload["_meta"]["validation_status"] == "ok"
        assert contracts_payload["config_contracts"]["issues"] == []
        assert (
            feature_manual_payload["_meta"]["source"]
            == "neotrade2_codebase_inventory_v3"
        )
        assert feature_manual_payload["feature_manual"]["feature_count"] >= 60
        assert (
            feature_mapping_payload["_meta"]["source"]
            == "neotrade3_feature_mapping_strategy_and_lab_v1"
        )
        assert feature_mapping_payload["feature_mapping"]["mapping_count"] >= 20
        assert (
            assistant_mapping_payload["_meta"]["source"]
            == "neotrade3_feature_mapping_assistant_v1"
        )
        assert assistant_mapping_payload["feature_mapping"]["mapping_count"] >= 8
        assert (
            operations_mapping_payload["_meta"]["source"]
            == "neotrade3_feature_mapping_operations_v1"
        )
        assert operations_mapping_payload["feature_mapping"]["mapping_count"] >= 7
        assert (
            screeners_mapping_payload["_meta"]["source"]
            == "neotrade3_feature_mapping_screeners_v1"
        )
        assert screeners_mapping_payload["feature_mapping"]["mapping_count"] >= 13
        assert getattr(error_response, "code", None) == 400
        assert error_body["error"]["code"] == "bad_request"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_http_end_to_end_domain_endpoints_cover_current_api_views(
    tmp_path: Path,
) -> None:
    worker = BootstrapWorkerApp(project_root=PROJECT_ROOT)
    worker.paths["ledgers_root"] = tmp_path / "ledgers"
    worker.paths["artifacts_root"] = tmp_path / "artifacts"
    worker.run(
        target_date=date(2026, 5, 19),
        publish_succeeded=False,
        write_outputs=True,
    )

    service = BootstrapApiService(project_root=PROJECT_ROOT)
    service.worker_app.paths["ledgers_root"] = tmp_path / "ledgers"
    service.worker_app.paths["artifacts_root"] = tmp_path / "artifacts"
    handler = build_handler(service)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        base_url = f"http://127.0.0.1:{server.server_port}"
        endpoint_expectations = {
            "/api/data-control?date=2026-05-19": "data_control",
            "/api/orchestration?date=2026-05-19": "orchestration",
            "/api/labs": "labs",
            "/api/issue-center?date=2026-05-19": "issue_center",
            "/api/learning?date=2026-05-19": "learning",
            "/api/config-contracts": "config_contracts",
            "/api/migration/feature-manual": "feature_manual",
            "/api/migration/feature-mapping?domain=strategy_and_lab": "feature_mapping",
            "/api/migration/feature-mapping?domain=assistant": "feature_mapping",
            "/api/migration/feature-mapping?domain=operations": "feature_mapping",
            "/api/migration/feature-mapping?domain=screeners": "feature_mapping",
        }

        for path, expected_key in endpoint_expectations.items():
            with urlopen(f"{base_url}{path}") as response:
                assert response.status == 200
                payload = json.loads(response.read().decode("utf-8"))

            assert expected_key in payload
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_http_end_to_end_dashboard_shell_points_to_api() -> None:
    api_service = BootstrapApiService(project_root=PROJECT_ROOT)
    api_handler = build_handler(api_service)
    api_server = ThreadingHTTPServer(("127.0.0.1", 0), api_handler)
    api_thread = Thread(target=api_server.serve_forever, daemon=True)
    api_thread.start()

    dashboard_builder = DashboardPageBuilder(
        api_base_url=f"http://127.0.0.1:{api_server.server_port}"
    )
    dashboard_handler = build_dashboard_handler(dashboard_builder)
    dashboard_server = ThreadingHTTPServer(("127.0.0.1", 0), dashboard_handler)
    dashboard_thread = Thread(target=dashboard_server.serve_forever, daemon=True)
    dashboard_thread.start()

    try:
        try:
            urlopen(f"http://127.0.0.1:{dashboard_server.server_port}/")
            raise AssertionError("expected dashboard to be retired")
        except Exception as exc:
            assert getattr(exc, "code", None) == 410
            body = exc.read().decode("utf-8")
            assert "retired" in body.lower()
    finally:
        dashboard_server.shutdown()
        dashboard_server.server_close()
        dashboard_thread.join(timeout=2)
        api_server.shutdown()
        api_server.server_close()
        api_thread.join(timeout=2)
