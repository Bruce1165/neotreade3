from __future__ import annotations

from dataclasses import replace
from datetime import date
import json
from pathlib import Path

from apps.worker.main import BootstrapWorkerApp
from neotrade3.benchmark import (
    BenchmarkCandidateRunContext,
    load_benchmark_run_manifest,
    materialize_benchmark_batch_run,
    run_benchmark_manifest,
)
from neotrade3.governance.assembler import build_validation_result
from neotrade3.governance.handoff import build_governance_handoff_from_batch_run
from neotrade3.governance.runtime import run_governance_candidate_validation_outcome
from neotrade3.governance.run_ledger import (
    read_governance_candidate_validation_artifact,
    read_governance_candidate_validation_record,
    read_governance_final_validation_artifact,
    read_governance_final_validation_record,
    read_governance_handoff_artifact,
    read_governance_reject_execution_artifact,
    read_governance_reject_execution_ledger,
    read_governance_run_ledger,
    read_governance_status_transition_artifact,
    read_governance_status_transition_ledger,
)
from neotrade3.orchestration import (
    DailyMasterOrchestrator,
    DailyRunPlan,
    DailyRunRequest,
    OnDemandTaskItem,
    OnDemandTaskRequest,
    OrchestrationPhase,
    PlannedTask,
    RunStatus,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
LABS_CONFIG = PROJECT_ROOT / "config" / "labs" / "labs_registry.json"
ORCHESTRATOR_CONFIG = (
    PROJECT_ROOT / "config" / "orchestrator" / "daily_master_orchestrator.json"
)
BENCHMARK_CONFIG_DIR = PROJECT_ROOT / "config" / "benchmark"


def _prepare_project_root(tmp_path: Path) -> Path:
    benchmark_dir = tmp_path / "config" / "benchmark"
    benchmark_dir.mkdir(parents=True, exist_ok=True)
    for file_name in (
        "validation_seed_manifest.json",
        "validation_seed_v2_manifest.json",
        "validation_seed_samples.json",
    ):
        source = BENCHMARK_CONFIG_DIR / file_name
        (benchmark_dir / file_name).write_text(
            source.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
    return tmp_path


def _materialize_benchmark_run(project_root: Path, manifest_name: str) -> str:
    manifest = load_benchmark_run_manifest(
        project_root / "config" / "benchmark" / manifest_name
    )
    batch_result = run_benchmark_manifest(
        project_root=project_root,
        manifest=manifest,
    )
    materialize_benchmark_batch_run(
        project_root=project_root,
        batch_result=batch_result,
    )
    return batch_result.run_id


def _materialize_benchmark_run_with_candidate_context(
    project_root: Path, manifest_name: str
) -> str:
    manifest = load_benchmark_run_manifest(
        project_root / "config" / "benchmark" / manifest_name
    )
    batch_result = run_benchmark_manifest(
        project_root=project_root,
        manifest=manifest,
    )
    bundle = build_governance_handoff_from_batch_run(batch_result=batch_result)
    assert len(bundle.validation_results) == 1
    batch_result = replace(
        batch_result,
        candidate_run_context=BenchmarkCandidateRunContext(
            experiment_id=bundle.validation_results[0].experiment_id,
            candidate_run_id="candidate-run-orchestrator-fit",
            source_run_id=batch_result.run_id,
        ),
    )
    materialize_benchmark_batch_run(
        project_root=project_root,
        batch_result=batch_result,
    )
    return batch_result.run_id


def _run_governance_task(
    *,
    project_root: Path,
    benchmark_run_id: str,
    dry_run: bool,
) -> tuple[PlannedTask, object]:
    orchestrator = DailyMasterOrchestrator.from_files(
        orchestrator_config_path=ORCHESTRATOR_CONFIG,
        labs_registry_path=LABS_CONFIG,
    )
    app = BootstrapWorkerApp(project_root=project_root)
    task = PlannedTask(
        task_id="governance.materialize_handoff",
        phase=OrchestrationPhase.GOVERNANCE,
        lab_id=None,
        entrypoint="neotrade3.governance.runtime:run_governance_for_benchmark_run",
        depends_on=[],
        outputs=["governance_handoff_artifact", "governance_handoff_ledger"],
        requires_publish_status=False,
        args_template={"benchmark_run_id": benchmark_run_id},
    )
    plan = DailyRunPlan(
        target_date=date(2026, 5, 19),
        phases=[OrchestrationPhase.GOVERNANCE],
        planned_tasks=[task],
    )
    results = orchestrator.execute_run_plan(
        plan,
        {
            OrchestrationPhase.GOVERNANCE: app._create_governance_executor(),
        },
        {
            "target_date": date(2026, 5, 19),
            "project_root": str(project_root),
            "requested_by": "test.m5.governance.orchestrator_fit",
            "dry_run": dry_run,
        },
    )
    return task, results[0]


def _inject_rejected_validation(
    *,
    project_root: Path,
    source_run_id: str,
    validation_id: str,
) -> None:
    artifact_path = (
        project_root
        / "var/artifacts/governance_handoffs"
        / source_run_id
        / "governance_handoff_bundle.json"
    )
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    experiment_id = payload["experiment_requests"][0]["experiment_id"]
    payload["validation_results"].append(
        build_validation_result(
            validation_id=validation_id,
            experiment_id=experiment_id,
            baseline_run_id=source_run_id,
            candidate_run_id="candidate-run-1",
            outcome="rejected",
            introduced_risk_count=1,
            cleared_guardrail_codes=[],
            remaining_guardrail_codes=["interaction.local_global"],
            evidence_refs=[{"kind": "validation_result"}],
        ).to_payload()
    )
    artifact_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _run_governance_reject_task(
    *,
    project_root: Path,
    source_run_id: str,
    validation_id: str,
    dry_run: bool,
) -> tuple[PlannedTask, object]:
    orchestrator = DailyMasterOrchestrator.from_files(
        orchestrator_config_path=ORCHESTRATOR_CONFIG,
        labs_registry_path=LABS_CONFIG,
    )
    app = BootstrapWorkerApp(project_root=project_root)
    request = OnDemandTaskRequest(
        target_date=date(2026, 5, 19),
        tasks=[
            OnDemandTaskItem(
                task_id="governance.reject_execution",
                phase=OrchestrationPhase.GOVERNANCE,
                entrypoint="neotrade3.governance.runtime:run_governance_reject_execution",
                args_template={
                    "source_run_id": source_run_id,
                    "validation_id": validation_id,
                },
                outputs=["governance_reject_artifact", "governance_reject_ledger"],
            )
        ],
    )
    plan = orchestrator.build_on_demand_plan(request)
    task = plan.planned_tasks[0]
    results = orchestrator.execute_run_plan(
        plan,
        {
            OrchestrationPhase.GOVERNANCE: app._create_governance_executor(),
        },
        {
            "target_date": date(2026, 5, 19),
            "project_root": str(project_root),
            "requested_by": "test.m5.governance.orchestrator_fit.reject",
            "dry_run": dry_run,
        },
    )
    return task, results[0]


def _run_governance_status_transition_task(
    *,
    project_root: Path,
    source_run_id: str,
    validation_id: str,
    dry_run: bool,
) -> tuple[PlannedTask, object]:
    orchestrator = DailyMasterOrchestrator.from_files(
        orchestrator_config_path=ORCHESTRATOR_CONFIG,
        labs_registry_path=LABS_CONFIG,
    )
    app = BootstrapWorkerApp(project_root=project_root)
    request = OnDemandTaskRequest(
        target_date=date(2026, 5, 19),
        tasks=[
            OnDemandTaskItem(
                task_id="governance.status_transition",
                phase=OrchestrationPhase.GOVERNANCE,
                entrypoint="neotrade3.governance.runtime:run_governance_status_transition",
                args_template={
                    "source_run_id": source_run_id,
                    "validation_id": validation_id,
                },
                outputs=[
                    "governance_status_transition_artifact",
                    "governance_status_transition_ledger",
                ],
            )
        ],
    )
    plan = orchestrator.build_on_demand_plan(request)
    task = plan.planned_tasks[0]
    results = orchestrator.execute_run_plan(
        plan,
        {
            OrchestrationPhase.GOVERNANCE: app._create_governance_executor(),
        },
        {
            "target_date": date(2026, 5, 19),
            "project_root": str(project_root),
            "requested_by": "test.m5.governance.orchestrator_fit.status_transition",
            "dry_run": dry_run,
        },
    )
    return task, results[0]


def _materialize_candidate_validation_outcome(
    *,
    project_root: Path,
    source_run_id: str,
    validation_id: str,
) -> None:
    artifact_payload = read_governance_handoff_artifact(
        project_root=project_root,
        source_run_id=source_run_id,
    )
    assert artifact_payload is not None
    validation_payload = next(
        item
        for item in artifact_payload["validation_results"]
        if item["validation_id"] == validation_id
    )
    experiment_id = str(validation_payload["experiment_id"])
    validation_result = build_validation_result(
        validation_id=validation_id,
        experiment_id=experiment_id,
        baseline_run_id=source_run_id,
        candidate_run_id="candidate-run-1",
        outcome="rejected",
        introduced_risk_count=1,
        cleared_guardrail_codes=[],
        remaining_guardrail_codes=["interaction.local_global"],
        evidence_refs=[{"kind": "candidate_validation"}],
    )
    run_governance_candidate_validation_outcome(
        project_root=project_root,
        source_run_id=source_run_id,
        validation_result=validation_result,
        dry_run=False,
    )


def _run_governance_final_validation_selection_task(
    *,
    project_root: Path,
    source_run_id: str,
    dry_run: bool,
) -> tuple[PlannedTask, object]:
    orchestrator = DailyMasterOrchestrator.from_files(
        orchestrator_config_path=ORCHESTRATOR_CONFIG,
        labs_registry_path=LABS_CONFIG,
    )
    app = BootstrapWorkerApp(project_root=project_root)
    request = OnDemandTaskRequest(
        target_date=date(2026, 5, 19),
        tasks=[
            OnDemandTaskItem(
                task_id="governance.final_validation_selection",
                phase=OrchestrationPhase.GOVERNANCE,
                entrypoint=(
                    "neotrade3.governance.runtime:"
                    "run_governance_final_validation_selection"
                ),
                args_template={
                    "source_run_id": source_run_id,
                },
                outputs=[
                    "governance_final_validation_artifact",
                    "governance_final_validation_ledger",
                ],
            )
        ],
    )
    plan = orchestrator.build_on_demand_plan(request)
    task = plan.planned_tasks[0]
    results = orchestrator.execute_run_plan(
        plan,
        {
            OrchestrationPhase.GOVERNANCE: app._create_governance_executor(),
        },
        {
            "target_date": date(2026, 5, 19),
            "project_root": str(project_root),
            "requested_by": "test.m5.governance.orchestrator_fit.final_selection",
            "dry_run": dry_run,
        },
    )
    return task, results[0]


def _run_governance_candidate_outcome_upstream_task(
    *,
    project_root: Path,
    source_run_id: str,
    dry_run: bool,
) -> tuple[PlannedTask, object]:
    orchestrator = DailyMasterOrchestrator.from_files(
        orchestrator_config_path=ORCHESTRATOR_CONFIG,
        labs_registry_path=LABS_CONFIG,
    )
    app = BootstrapWorkerApp(project_root=project_root)
    request = OnDemandTaskRequest(
        target_date=date(2026, 5, 19),
        tasks=[
            OnDemandTaskItem(
                task_id="governance.candidate_outcome_upstream",
                phase=OrchestrationPhase.GOVERNANCE,
                entrypoint=(
                    "neotrade3.governance.runtime:"
                    "run_governance_candidate_outcome_upstream_producer"
                ),
                args_template={
                    "source_run_id": source_run_id,
                },
                outputs=[],
            )
        ],
    )
    plan = orchestrator.build_on_demand_plan(request)
    task = plan.planned_tasks[0]
    results = orchestrator.execute_run_plan(
        plan,
        {
            OrchestrationPhase.GOVERNANCE: app._create_governance_executor(),
        },
        {
            "target_date": date(2026, 5, 19),
            "project_root": str(project_root),
            "requested_by": "test.m5.governance.orchestrator_fit.candidate_outcome",
            "dry_run": dry_run,
        },
    )
    return task, results[0]


def _run_governance_candidate_outcome_bridge_task(
    *,
    project_root: Path,
    source_run_id: str,
    dry_run: bool,
) -> tuple[PlannedTask, object]:
    orchestrator = DailyMasterOrchestrator.from_files(
        orchestrator_config_path=ORCHESTRATOR_CONFIG,
        labs_registry_path=LABS_CONFIG,
    )
    app = BootstrapWorkerApp(project_root=project_root)
    request = OnDemandTaskRequest(
        target_date=date(2026, 5, 19),
        tasks=[
            OnDemandTaskItem(
                task_id="governance.candidate_outcome_bridge",
                phase=OrchestrationPhase.GOVERNANCE,
                entrypoint=(
                    "neotrade3.governance.runtime:"
                    "run_governance_candidate_outcome_bridge"
                ),
                args_template={
                    "source_run_id": source_run_id,
                },
                outputs=[
                    "governance_candidate_validation_artifact",
                    "governance_candidate_validation_ledger",
                ],
            )
        ],
    )
    plan = orchestrator.build_on_demand_plan(request)
    task = plan.planned_tasks[0]
    results = orchestrator.execute_run_plan(
        plan,
        {
            OrchestrationPhase.GOVERNANCE: app._create_governance_executor(),
        },
        {
            "target_date": date(2026, 5, 19),
            "project_root": str(project_root),
            "requested_by": "test.m5.governance.orchestrator_fit.candidate_bridge",
            "dry_run": dry_run,
        },
    )
    return task, results[0]


def test_build_on_demand_plan_preserves_explicit_task_shape() -> None:
    orchestrator = DailyMasterOrchestrator.from_files(
        orchestrator_config_path=ORCHESTRATOR_CONFIG,
        labs_registry_path=LABS_CONFIG,
    )
    request = OnDemandTaskRequest(
        target_date=date(2026, 5, 19),
        tasks=[
            OnDemandTaskItem(
                task_id="governance.reject_execution",
                phase=OrchestrationPhase.GOVERNANCE,
                entrypoint="neotrade3.governance.runtime:run_governance_reject_execution",
                args_template={
                    "source_run_id": "benchmark-run-1",
                    "validation_id": "validation-1",
                },
                outputs=["governance_reject_artifact", "governance_reject_ledger"],
            )
        ],
    )

    plan = orchestrator.build_on_demand_plan(request)

    assert plan.target_date == request.target_date
    assert plan.preflight_report is None
    assert plan.phases == [OrchestrationPhase.GOVERNANCE]
    assert len(plan.planned_tasks) == 1
    assert plan.planned_tasks[0].task_id == "governance.reject_execution"
    assert plan.planned_tasks[0].args_template["source_run_id"] == "benchmark-run-1"
    assert plan.planned_tasks[0].args_template["validation_id"] == "validation-1"


def _run_benchmark_then_governance_chain(
    *,
    project_root: Path,
    manifest: str,
    dry_run: bool,
) -> tuple[object, object]:
    orchestrator = DailyMasterOrchestrator.from_files(
        orchestrator_config_path=ORCHESTRATOR_CONFIG,
        labs_registry_path=LABS_CONFIG,
    )
    app = BootstrapWorkerApp(project_root=project_root)
    benchmark_task = PlannedTask(
        task_id="benchmark.materialize_run",
        phase=OrchestrationPhase.BENCHMARK,
        lab_id=None,
        entrypoint="neotrade3.benchmark.runtime:run_benchmark_for_manifest",
        depends_on=[],
        outputs=["benchmark_run_artifact", "benchmark_run_ledger"],
        requires_publish_status=False,
        args_template={"manifest": manifest},
    )
    governance_task = PlannedTask(
        task_id="governance.materialize_handoff",
        phase=OrchestrationPhase.GOVERNANCE,
        lab_id=None,
        entrypoint="neotrade3.governance.runtime:run_governance_for_benchmark_run",
        depends_on=["benchmark.materialize_run"],
        outputs=["governance_handoff_artifact", "governance_handoff_ledger"],
        requires_publish_status=False,
        args_template={
            "benchmark_run_id": {
                "from_task": "benchmark.materialize_run",
                "detail_key": "run_id",
            }
        },
    )
    plan = DailyRunPlan(
        target_date=date(2026, 5, 19),
        phases=[OrchestrationPhase.BENCHMARK, OrchestrationPhase.GOVERNANCE],
        planned_tasks=[benchmark_task, governance_task],
    )
    results = orchestrator.execute_run_plan(
        plan,
        {
            OrchestrationPhase.BENCHMARK: app._create_benchmark_executor(),
            OrchestrationPhase.GOVERNANCE: app._create_governance_executor(),
        },
        {
            "target_date": date(2026, 5, 19),
            "project_root": str(project_root),
            "requested_by": "test.m5.governance.orchestrator_fit",
            "dry_run": dry_run,
        },
    )
    return results[0], results[1]


def test_governance_phase_and_dynamic_benchmark_run_reference_survive_planning() -> None:
    orchestrator = DailyMasterOrchestrator.from_files(
        orchestrator_config_path=ORCHESTRATOR_CONFIG,
        labs_registry_path=LABS_CONFIG,
    )

    plan = orchestrator.build_run_plan(
        DailyRunRequest(target_date=date(2026, 5, 19), publish_succeeded=False)
    )
    governance_task = next(
        task
        for task in plan.planned_tasks
        if task.task_id == "governance.materialize_handoff"
    )

    assert OrchestrationPhase.GOVERNANCE in plan.phases
    assert OrchestrationPhase.BENCHMARK in plan.phases
    assert governance_task.phase == OrchestrationPhase.GOVERNANCE
    assert governance_task.depends_on == ["benchmark.materialize_run"]
    assert governance_task.args_template["benchmark_run_id"] == {
        "from_task": "benchmark.materialize_run",
        "detail_key": "run_id",
    }


def test_planned_task_args_template_defaults_to_empty_dict() -> None:
    task = PlannedTask(
        task_id="test.task",
        phase=OrchestrationPhase.GOVERNANCE,
        lab_id=None,
        entrypoint="fake.entrypoint",
        depends_on=[],
        outputs=["artifact"],
        requires_publish_status=False,
    )

    assert task.args_template == {}


def test_governance_executor_dry_run_via_execute_run_plan(tmp_path: Path) -> None:
    project_root = _prepare_project_root(tmp_path)
    run_id = _materialize_benchmark_run(project_root, "validation_seed_manifest.json")
    _, result = _run_governance_task(
        project_root=project_root,
        benchmark_run_id=run_id,
        dry_run=True,
    )

    assert result.status == RunStatus.OK
    assert result.details["source_run_id"] == run_id
    assert result.details["source_layer"] == "M4"
    assert isinstance(result.details["validation_result_count"], int)
    assert result.details["attention_item_count"] == 1
    assert isinstance(result.details["decision_record_count"], int)
    assert result.details["dry_run"] is True
    assert result.details["benchmark_run_id"] == run_id
    assert not (project_root / result.artifact_refs[0]).exists()
    assert not (project_root / result.artifact_refs[1]).exists()
    assert (
        read_governance_run_ledger(
            project_root=project_root,
            source_run_id=result.details["source_run_id"],
        )
        is None
    )
    assert (
        read_governance_handoff_artifact(
            project_root=project_root,
            source_run_id=result.details["source_run_id"],
        )
        is None
    )


def test_governance_executor_materializes_outputs_via_execute_run_plan(
    tmp_path: Path,
) -> None:
    project_root = _prepare_project_root(tmp_path)
    run_id = _materialize_benchmark_run(project_root, "validation_seed_v2_manifest.json")
    _, result = _run_governance_task(
        project_root=project_root,
        benchmark_run_id=run_id,
        dry_run=False,
    )

    artifact_path = project_root / result.artifact_refs[0]
    ledger_path = project_root / result.artifact_refs[1]
    ledger_record = read_governance_run_ledger(
        project_root=project_root,
        source_run_id=result.details["source_run_id"],
    )
    artifact_payload = read_governance_handoff_artifact(
        project_root=project_root,
        source_run_id=result.details["source_run_id"],
    )

    assert result.status == RunStatus.OK
    assert result.details["source_run_id"] == run_id
    assert result.details["source_layer"] == "M4"
    assert result.details["attention_item_count"] == 0
    assert result.details["validation_result_count"] == ledger_record.validation_result_count
    assert result.details["decision_record_count"] == ledger_record.decision_record_count
    assert result.details["dry_run"] is False
    assert result.details["benchmark_run_id"] == run_id
    assert artifact_path.exists()
    assert ledger_path.exists()
    assert ledger_record is not None
    assert artifact_payload is not None
    assert ledger_record.artifact_path == result.artifact_refs[0]
    assert ledger_record.ledger_path == result.artifact_refs[1]
    assert ledger_record.source_run_id == result.details["source_run_id"]
    assert ledger_record.diagnostic_count == result.details["diagnostic_count"]
    assert ledger_record.attention_item_count == result.details["attention_item_count"]
    assert artifact_payload["source_run_id"] == result.details["source_run_id"]
    assert artifact_payload["projected_assessment_count"] == result.details[
        "projected_assessment_count"
    ]
    assert len(artifact_payload["validation_results"]) == result.details["validation_result_count"]
    assert len(artifact_payload["attention_items"]) == result.details["attention_item_count"]
    assert len(artifact_payload["decision_records"]) == result.details["decision_record_count"]


def test_governance_executor_consumes_dynamic_benchmark_run_id_from_dependency(
    tmp_path: Path,
) -> None:
    project_root = _prepare_project_root(tmp_path)
    benchmark_result, governance_result = _run_benchmark_then_governance_chain(
        project_root=project_root,
        manifest="config/benchmark/validation_seed_v2_manifest.json",
        dry_run=False,
    )

    assert benchmark_result.status == RunStatus.OK
    assert governance_result.status == RunStatus.OK
    assert governance_result.details["benchmark_run_id"] == benchmark_result.details[
        "run_id"
    ]
    assert governance_result.details["source_run_id"] == benchmark_result.details[
        "run_id"
    ]
    assert governance_result.details["attention_item_count"] == 0


def test_governance_blocks_when_benchmark_dependency_is_not_satisfied(
    tmp_path: Path,
) -> None:
    project_root = _prepare_project_root(tmp_path)
    orchestrator = DailyMasterOrchestrator.from_files(
        orchestrator_config_path=ORCHESTRATOR_CONFIG,
        labs_registry_path=LABS_CONFIG,
    )
    app = BootstrapWorkerApp(project_root=project_root)
    task = PlannedTask(
        task_id="governance.materialize_handoff",
        phase=OrchestrationPhase.GOVERNANCE,
        lab_id=None,
        entrypoint="neotrade3.governance.runtime:run_governance_for_benchmark_run",
        depends_on=["benchmark.materialize_run"],
        outputs=["governance_handoff_artifact", "governance_handoff_ledger"],
        requires_publish_status=False,
        args_template={
            "benchmark_run_id": {
                "from_task": "benchmark.materialize_run",
                "detail_key": "run_id",
            }
        },
    )
    plan = DailyRunPlan(
        target_date=date(2026, 5, 19),
        phases=[OrchestrationPhase.GOVERNANCE],
        planned_tasks=[task],
    )
    results = orchestrator.execute_run_plan(
        plan,
        {
            OrchestrationPhase.GOVERNANCE: app._create_governance_executor(),
        },
        {
            "target_date": date(2026, 5, 19),
            "project_root": str(project_root),
            "requested_by": "test.m5.governance.orchestrator_fit",
            "dry_run": True,
        },
    )

    assert results[0].status == RunStatus.BLOCKED
    assert "benchmark.materialize_run" in results[0].message


def test_governance_executor_fails_for_missing_benchmark_run_id(tmp_path: Path) -> None:
    project_root = _prepare_project_root(tmp_path)
    _, result = _run_governance_task(
        project_root=project_root,
        benchmark_run_id="missing_benchmark_run",
        dry_run=False,
    )

    assert result.status == RunStatus.FAILED
    assert "missing_benchmark_run" in result.message


def test_governance_reject_executor_dry_run_via_execute_run_plan(
    tmp_path: Path,
) -> None:
    project_root = _prepare_project_root(tmp_path)
    run_id = _materialize_benchmark_run(project_root, "validation_seed_manifest.json")
    _run_governance_task(
        project_root=project_root,
        benchmark_run_id=run_id,
        dry_run=False,
    )
    _inject_rejected_validation(
        project_root=project_root,
        source_run_id=run_id,
        validation_id="validation-final-reject",
    )
    _materialize_candidate_validation_outcome(
        project_root=project_root,
        source_run_id=run_id,
        validation_id="validation-final-reject",
    )
    _, result = _run_governance_reject_task(
        project_root=project_root,
        source_run_id=run_id,
        validation_id="validation-final-reject",
        dry_run=True,
    )

    assert result.status == RunStatus.OK
    assert result.details["validation_id"] == "validation-final-reject"
    assert result.details["source_run_id"] == run_id
    assert result.details["decision"] == "reject"
    assert result.details["dry_run"] is True
    assert not (project_root / result.artifact_refs[0]).exists()
    assert not (project_root / result.artifact_refs[1]).exists()
    assert (
        read_governance_reject_execution_artifact(
            project_root=project_root,
            validation_id="validation-final-reject",
        )
        is None
    )
    assert (
        read_governance_reject_execution_ledger(
            project_root=project_root,
            validation_id="validation-final-reject",
        )
        is None
    )


def test_governance_reject_executor_materializes_outputs_via_execute_run_plan(
    tmp_path: Path,
) -> None:
    project_root = _prepare_project_root(tmp_path)
    run_id = _materialize_benchmark_run(project_root, "validation_seed_manifest.json")
    _run_governance_task(
        project_root=project_root,
        benchmark_run_id=run_id,
        dry_run=False,
    )
    _inject_rejected_validation(
        project_root=project_root,
        source_run_id=run_id,
        validation_id="validation-final-reject",
    )
    _materialize_candidate_validation_outcome(
        project_root=project_root,
        source_run_id=run_id,
        validation_id="validation-final-reject",
    )
    _, result = _run_governance_reject_task(
        project_root=project_root,
        source_run_id=run_id,
        validation_id="validation-final-reject",
        dry_run=False,
    )

    artifact_path = project_root / result.artifact_refs[0]
    ledger_path = project_root / result.artifact_refs[1]
    artifact_payload = read_governance_reject_execution_artifact(
        project_root=project_root,
        validation_id="validation-final-reject",
    )
    ledger_record = read_governance_reject_execution_ledger(
        project_root=project_root,
        validation_id="validation-final-reject",
    )

    assert result.status == RunStatus.OK
    assert result.details["validation_id"] == "validation-final-reject"
    assert result.details["source_run_id"] == run_id
    assert result.details["decision"] == "reject"
    assert result.details["dry_run"] is False
    assert artifact_path.exists()
    assert ledger_path.exists()
    assert artifact_payload is not None
    assert ledger_record is not None
    assert artifact_payload["decision_record"]["decision"] == "reject"
    assert ledger_record.validation_id == result.details["validation_id"]
    assert ledger_record.decision == result.details["decision"]


def test_governance_reject_executor_fails_for_missing_validation_id(
    tmp_path: Path,
) -> None:
    project_root = _prepare_project_root(tmp_path)
    run_id = _materialize_benchmark_run(project_root, "validation_seed_manifest.json")
    _run_governance_task(
        project_root=project_root,
        benchmark_run_id=run_id,
        dry_run=False,
    )
    _, result = _run_governance_reject_task(
        project_root=project_root,
        source_run_id=run_id,
        validation_id="missing-validation",
        dry_run=False,
    )

    assert result.status == RunStatus.FAILED
    assert "validation_result not found" in result.message


def test_governance_reject_executor_fails_for_missing_source_run_id(
    tmp_path: Path,
) -> None:
    project_root = _prepare_project_root(tmp_path)
    _, result = _run_governance_reject_task(
        project_root=project_root,
        source_run_id="",
        validation_id="validation-final-reject",
        dry_run=False,
    )

    assert result.status == RunStatus.FAILED
    assert "source_run_id must be provided" in result.message


def test_governance_status_transition_executor_dry_run_via_execute_run_plan(
    tmp_path: Path,
) -> None:
    project_root = _prepare_project_root(tmp_path)
    run_id = _materialize_benchmark_run(project_root, "validation_seed_manifest.json")
    _run_governance_task(
        project_root=project_root,
        benchmark_run_id=run_id,
        dry_run=False,
    )
    _inject_rejected_validation(
        project_root=project_root,
        source_run_id=run_id,
        validation_id="validation-final-reject",
    )
    _materialize_candidate_validation_outcome(
        project_root=project_root,
        source_run_id=run_id,
        validation_id="validation-final-reject",
    )
    _run_governance_reject_task(
        project_root=project_root,
        source_run_id=run_id,
        validation_id="validation-final-reject",
        dry_run=False,
    )
    _, result = _run_governance_status_transition_task(
        project_root=project_root,
        source_run_id=run_id,
        validation_id="validation-final-reject",
        dry_run=True,
    )

    assert result.status == RunStatus.OK
    assert result.details["validation_id"] == "validation-final-reject"
    assert result.details["source_run_id"] == run_id
    assert result.details["effective_attention_status"] == "resolved"
    assert result.details["effective_blocker_active"] is True
    assert result.details["dry_run"] is True
    assert not (project_root / result.artifact_refs[0]).exists()
    assert not (project_root / result.artifact_refs[1]).exists()
    assert (
        read_governance_status_transition_artifact(
            project_root=project_root,
            validation_id="validation-final-reject",
        )
        is None
    )
    assert (
        read_governance_status_transition_ledger(
            project_root=project_root,
            validation_id="validation-final-reject",
        )
        is None
    )


def test_governance_status_transition_executor_materializes_outputs_via_execute_run_plan(
    tmp_path: Path,
) -> None:
    project_root = _prepare_project_root(tmp_path)
    run_id = _materialize_benchmark_run(project_root, "validation_seed_manifest.json")
    _run_governance_task(
        project_root=project_root,
        benchmark_run_id=run_id,
        dry_run=False,
    )
    _inject_rejected_validation(
        project_root=project_root,
        source_run_id=run_id,
        validation_id="validation-final-reject",
    )
    _materialize_candidate_validation_outcome(
        project_root=project_root,
        source_run_id=run_id,
        validation_id="validation-final-reject",
    )
    reject_result = _run_governance_reject_task(
        project_root=project_root,
        source_run_id=run_id,
        validation_id="validation-final-reject",
        dry_run=False,
    )[1]
    _, result = _run_governance_status_transition_task(
        project_root=project_root,
        source_run_id=run_id,
        validation_id="validation-final-reject",
        dry_run=False,
    )

    artifact_path = project_root / result.artifact_refs[0]
    ledger_path = project_root / result.artifact_refs[1]
    artifact_payload = read_governance_status_transition_artifact(
        project_root=project_root,
        validation_id="validation-final-reject",
    )
    ledger_record = read_governance_status_transition_ledger(
        project_root=project_root,
        validation_id="validation-final-reject",
    )

    assert result.status == RunStatus.OK
    assert result.details["validation_id"] == "validation-final-reject"
    assert result.details["source_run_id"] == run_id
    assert result.details["decision_id"] == reject_result.details["decision_id"]
    assert result.details["effective_attention_status"] == "resolved"
    assert result.details["effective_blocker_active"] is True
    assert result.details["dry_run"] is False
    assert artifact_path.exists()
    assert ledger_path.exists()
    assert artifact_payload is not None
    assert ledger_record is not None
    assert artifact_payload["validation_id"] == result.details["validation_id"]
    assert artifact_payload["effective_attention_item"]["status"] == "resolved"
    assert artifact_payload["effective_promotion_blocker"]["active"] is True
    assert ledger_record.validation_id == result.details["validation_id"]
    assert ledger_record.decision_id == result.details["decision_id"]
    assert ledger_record.effective_attention_status == "resolved"
    assert ledger_record.effective_blocker_active is True


def test_governance_status_transition_executor_fails_for_missing_reject_proof(
    tmp_path: Path,
) -> None:
    project_root = _prepare_project_root(tmp_path)
    run_id = _materialize_benchmark_run(project_root, "validation_seed_manifest.json")
    _run_governance_task(
        project_root=project_root,
        benchmark_run_id=run_id,
        dry_run=False,
    )
    _inject_rejected_validation(
        project_root=project_root,
        source_run_id=run_id,
        validation_id="validation-final-reject",
    )
    _materialize_candidate_validation_outcome(
        project_root=project_root,
        source_run_id=run_id,
        validation_id="validation-final-reject",
    )
    _, result = _run_governance_status_transition_task(
        project_root=project_root,
        source_run_id=run_id,
        validation_id="validation-final-reject",
        dry_run=False,
    )

    assert result.status == RunStatus.FAILED
    assert "persisted governance reject execution not found" in result.message


def test_governance_final_validation_selection_executor_dry_run_via_execute_run_plan(
    tmp_path: Path,
) -> None:
    project_root = _prepare_project_root(tmp_path)
    run_id = _materialize_benchmark_run(project_root, "validation_seed_manifest.json")
    _run_governance_task(
        project_root=project_root,
        benchmark_run_id=run_id,
        dry_run=False,
    )
    _inject_rejected_validation(
        project_root=project_root,
        source_run_id=run_id,
        validation_id="validation-final-reject",
    )
    _materialize_candidate_validation_outcome(
        project_root=project_root,
        source_run_id=run_id,
        validation_id="validation-final-reject",
    )
    _, result = _run_governance_final_validation_selection_task(
        project_root=project_root,
        source_run_id=run_id,
        dry_run=True,
    )

    assert result.status == RunStatus.OK
    assert result.details["source_run_id"] == run_id
    assert result.details["selected_validation_id"] == "validation-final-reject"
    assert result.details["baseline_run_id"] == run_id
    assert result.details["candidate_run_id"] == "candidate-run-1"
    assert result.details["outcome"] == "rejected"
    assert result.details["dry_run"] is True
    assert not (project_root / result.artifact_refs[0]).exists()
    assert not (project_root / result.artifact_refs[1]).exists()
    assert (
        read_governance_final_validation_artifact(
            project_root=project_root,
            source_run_id=run_id,
        )
        is None
    )
    assert (
        read_governance_final_validation_record(
            project_root=project_root,
            source_run_id=run_id,
        )
        is None
    )


def test_governance_final_validation_selection_executor_materializes_outputs_via_execute_run_plan(
    tmp_path: Path,
) -> None:
    project_root = _prepare_project_root(tmp_path)
    run_id = _materialize_benchmark_run(project_root, "validation_seed_manifest.json")
    _run_governance_task(
        project_root=project_root,
        benchmark_run_id=run_id,
        dry_run=False,
    )
    _inject_rejected_validation(
        project_root=project_root,
        source_run_id=run_id,
        validation_id="validation-final-reject",
    )
    _materialize_candidate_validation_outcome(
        project_root=project_root,
        source_run_id=run_id,
        validation_id="validation-final-reject",
    )
    _, result = _run_governance_final_validation_selection_task(
        project_root=project_root,
        source_run_id=run_id,
        dry_run=False,
    )

    artifact_path = project_root / result.artifact_refs[0]
    ledger_path = project_root / result.artifact_refs[1]
    artifact_payload = read_governance_final_validation_artifact(
        project_root=project_root,
        source_run_id=run_id,
    )
    ledger_record = read_governance_final_validation_record(
        project_root=project_root,
        source_run_id=run_id,
    )

    assert result.status == RunStatus.OK
    assert result.details["source_run_id"] == run_id
    assert result.details["selected_validation_id"] == "validation-final-reject"
    assert result.details["baseline_run_id"] == run_id
    assert result.details["candidate_run_id"] == "candidate-run-1"
    assert result.details["outcome"] == "rejected"
    assert result.details["dry_run"] is False
    assert artifact_path.exists()
    assert ledger_path.exists()
    assert artifact_payload is not None
    assert ledger_record is not None
    assert artifact_payload["source_run_id"] == run_id
    assert artifact_payload["selected_validation_id"] == "validation-final-reject"
    assert artifact_payload["selection_basis"] == "unique_persisted_candidate_validation"
    assert ledger_record.source_run_id == run_id
    assert ledger_record.selected_validation_id == "validation-final-reject"
    assert ledger_record.outcome == "rejected"


def test_governance_final_validation_selection_executor_fails_without_candidate_outcome(
    tmp_path: Path,
) -> None:
    project_root = _prepare_project_root(tmp_path)
    run_id = _materialize_benchmark_run(project_root, "validation_seed_manifest.json")
    _run_governance_task(
        project_root=project_root,
        benchmark_run_id=run_id,
        dry_run=False,
    )
    _inject_rejected_validation(
        project_root=project_root,
        source_run_id=run_id,
        validation_id="validation-final-reject",
    )
    _, result = _run_governance_final_validation_selection_task(
        project_root=project_root,
        source_run_id=run_id,
        dry_run=False,
    )

    assert result.status == RunStatus.FAILED
    assert "no persisted candidate validation outcome found" in result.message


def test_governance_candidate_outcome_upstream_executor_dry_run_via_execute_run_plan(
    tmp_path: Path,
) -> None:
    project_root = _prepare_project_root(tmp_path)
    run_id = _materialize_benchmark_run_with_candidate_context(
        project_root,
        "validation_seed_manifest.json",
    )
    _run_governance_task(
        project_root=project_root,
        benchmark_run_id=run_id,
        dry_run=False,
    )
    _, result = _run_governance_candidate_outcome_upstream_task(
        project_root=project_root,
        source_run_id=run_id,
        dry_run=True,
    )

    assert result.status == RunStatus.OK
    assert result.details["source_run_id"] == run_id
    assert result.details["candidate_run_id"] == "candidate-run-orchestrator-fit"
    assert result.details["outcome"] == "rejected"
    assert result.details["dry_run"] is True
    assert result.details["validation_result"]["candidate_run_id"] == (
        "candidate-run-orchestrator-fit"
    )
    assert result.artifact_refs == []


def test_governance_candidate_outcome_upstream_executor_returns_validation_result_via_execute_run_plan(
    tmp_path: Path,
) -> None:
    project_root = _prepare_project_root(tmp_path)
    run_id = _materialize_benchmark_run_with_candidate_context(
        project_root,
        "validation_seed_manifest.json",
    )
    _run_governance_task(
        project_root=project_root,
        benchmark_run_id=run_id,
        dry_run=False,
    )
    _, result = _run_governance_candidate_outcome_upstream_task(
        project_root=project_root,
        source_run_id=run_id,
        dry_run=False,
    )

    assert result.status == RunStatus.OK
    assert result.details["source_run_id"] == run_id
    assert result.details["candidate_run_id"] == "candidate-run-orchestrator-fit"
    assert result.details["outcome"] == "rejected"
    assert result.details["validation_result"]["outcome"] == "rejected"
    assert result.details["validation_result"]["baseline_run_id"] == run_id
    assert result.artifact_refs == []


def test_governance_candidate_outcome_upstream_executor_fails_without_candidate_context(
    tmp_path: Path,
) -> None:
    project_root = _prepare_project_root(tmp_path)
    run_id = _materialize_benchmark_run(
        project_root,
        "validation_seed_manifest.json",
    )
    _run_governance_task(
        project_root=project_root,
        benchmark_run_id=run_id,
        dry_run=False,
    )
    _, result = _run_governance_candidate_outcome_upstream_task(
        project_root=project_root,
        source_run_id=run_id,
        dry_run=False,
    )

    assert result.status == RunStatus.FAILED
    assert "persisted benchmark candidate_run_context not found" in result.message
    assert result.artifact_refs == []


def test_governance_candidate_outcome_bridge_executor_dry_run_via_execute_run_plan(
    tmp_path: Path,
) -> None:
    project_root = _prepare_project_root(tmp_path)
    run_id = _materialize_benchmark_run_with_candidate_context(
        project_root,
        "validation_seed_manifest.json",
    )
    _run_governance_task(
        project_root=project_root,
        benchmark_run_id=run_id,
        dry_run=False,
    )
    _, result = _run_governance_candidate_outcome_bridge_task(
        project_root=project_root,
        source_run_id=run_id,
        dry_run=True,
    )

    assert result.status == RunStatus.OK
    assert result.details["source_run_id"] == run_id
    assert result.details["candidate_run_id"] == "candidate-run-orchestrator-fit"
    assert result.details["outcome"] == "rejected"
    assert result.details["dry_run"] is True
    assert not (project_root / result.artifact_refs[0]).exists()
    assert not (project_root / result.artifact_refs[1]).exists()
    assert (
        read_governance_candidate_validation_artifact(
            project_root=project_root,
            validation_id=result.details["validation_id"],
        )
        is None
    )
    assert (
        read_governance_candidate_validation_record(
            project_root=project_root,
            validation_id=result.details["validation_id"],
        )
        is None
    )


def test_governance_candidate_outcome_bridge_executor_materializes_candidate_validation_record_via_execute_run_plan(
    tmp_path: Path,
) -> None:
    project_root = _prepare_project_root(tmp_path)
    run_id = _materialize_benchmark_run_with_candidate_context(
        project_root,
        "validation_seed_manifest.json",
    )
    _run_governance_task(
        project_root=project_root,
        benchmark_run_id=run_id,
        dry_run=False,
    )
    _, result = _run_governance_candidate_outcome_bridge_task(
        project_root=project_root,
        source_run_id=run_id,
        dry_run=False,
    )

    artifact_path = project_root / result.artifact_refs[0]
    ledger_path = project_root / result.artifact_refs[1]
    artifact_payload = read_governance_candidate_validation_artifact(
        project_root=project_root,
        validation_id=result.details["validation_id"],
    )
    ledger_record = read_governance_candidate_validation_record(
        project_root=project_root,
        validation_id=result.details["validation_id"],
    )

    assert result.status == RunStatus.OK
    assert result.details["source_run_id"] == run_id
    assert result.details["candidate_run_id"] == "candidate-run-orchestrator-fit"
    assert result.details["outcome"] == "rejected"
    assert result.details["status"] == "completed"
    assert result.details["dry_run"] is False
    assert artifact_path.exists()
    assert ledger_path.exists()
    assert artifact_payload is not None
    assert ledger_record is not None
    assert artifact_payload["outcome"] == "rejected"
    assert artifact_payload["validation_result"]["candidate_run_id"] == (
        "candidate-run-orchestrator-fit"
    )
    assert ledger_record.validation_id == result.details["validation_id"]
    assert ledger_record.source_run_id == run_id
    assert ledger_record.candidate_run_id == "candidate-run-orchestrator-fit"


def test_governance_candidate_outcome_bridge_executor_fails_without_candidate_context(
    tmp_path: Path,
) -> None:
    project_root = _prepare_project_root(tmp_path)
    run_id = _materialize_benchmark_run(
        project_root,
        "validation_seed_manifest.json",
    )
    _run_governance_task(
        project_root=project_root,
        benchmark_run_id=run_id,
        dry_run=False,
    )
    _, result = _run_governance_candidate_outcome_bridge_task(
        project_root=project_root,
        source_run_id=run_id,
        dry_run=False,
    )

    assert result.status == RunStatus.FAILED
    assert "persisted benchmark candidate_run_context not found" in result.message
    assert result.artifact_refs == []


def test_orchestrator_config_declares_governance_task_dynamic_benchmark_reference() -> None:
    payload = json.loads(ORCHESTRATOR_CONFIG.read_text(encoding="utf-8"))
    governance_task = next(
        task
        for task in payload["tasks"]
        if task["task_id"] == "governance.materialize_handoff"
    )

    assert payload["phases"][-1] == OrchestrationPhase.GOVERNANCE.value
    assert payload["phases"][-2] == OrchestrationPhase.BENCHMARK.value
    assert governance_task["phase"] == OrchestrationPhase.GOVERNANCE.value
    assert governance_task["depends_on"] == ["benchmark.materialize_run"]
    assert governance_task["args_template"]["benchmark_run_id"] == {
        "from_task": "benchmark.materialize_run",
        "detail_key": "run_id",
    }
