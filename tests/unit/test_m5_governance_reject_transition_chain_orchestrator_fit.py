from __future__ import annotations

from datetime import date
from pathlib import Path

from apps.worker.main import BootstrapWorkerApp
from neotrade3.orchestration import (
    DailyMasterOrchestrator,
    OnDemandTaskItem,
    OnDemandTaskRequest,
    OrchestrationPhase,
    PlannedTask,
)
from tests.unit.test_m5_governance_candidate_validation_outcome import (
    _materialize_candidate_validation_outcome as _materialize_reference_candidate_validation_outcome,
    _materialize_reference_handoff,
)
from tests.unit.test_m5_governance_orchestrator_fit import (
    LABS_CONFIG,
    ORCHESTRATOR_CONFIG,
    _materialize_benchmark_run_with_candidate_context,
    _prepare_project_root,
    _run_governance_candidate_outcome_bridge_task,
    _run_governance_task,
)


def _run_governance_reject_transition_chain_task(
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
                task_id="governance.reject_transition_chain",
                phase=OrchestrationPhase.GOVERNANCE,
                entrypoint=(
                    "neotrade3.governance.runtime:"
                    "run_governance_reject_transition_chain"
                ),
                args_template={
                    "source_run_id": source_run_id,
                },
                outputs=[
                    "governance_final_validation_artifact",
                    "governance_final_validation_ledger",
                    "governance_reject_artifact",
                    "governance_reject_ledger",
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
            "requested_by": "test.m5.governance.orchestrator_fit.reject_chain",
            "dry_run": dry_run,
        },
    )
    return task, results[0]


def test_governance_reject_transition_chain_executor_runs_full_rejected_chain(
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
    _run_governance_candidate_outcome_bridge_task(
        project_root=project_root,
        source_run_id=run_id,
        dry_run=False,
    )
    _, result = _run_governance_reject_transition_chain_task(
        project_root=project_root,
        source_run_id=run_id,
        dry_run=False,
    )

    assert result.status.value == "ok"
    assert result.details["source_run_id"] == run_id
    assert result.details["outcome"] == "rejected"
    assert result.details["executed_reject_execution"] is True
    assert result.details["executed_status_transition"] is True
    assert len(result.artifact_refs) == 6


def test_governance_reject_transition_chain_executor_stops_after_passed_selection(
    tmp_path: Path,
) -> None:
    project_root = _prepare_project_root(tmp_path)
    bundle, _ = _materialize_reference_handoff(project_root)
    _materialize_reference_candidate_validation_outcome(
        tmp_path=project_root,
        bundle=bundle,
        outcome="passed",
        candidate_run_id="candidate-run-orchestrator-fit",
    )
    _, result = _run_governance_reject_transition_chain_task(
        project_root=project_root,
        source_run_id=bundle.source_run_id,
        dry_run=False,
    )

    assert result.status.value == "ok"
    assert result.details["source_run_id"] == bundle.source_run_id
    assert result.details["outcome"] == "passed"
    assert result.details["executed_reject_execution"] is False
    assert result.details["executed_status_transition"] is False
    assert len(result.artifact_refs) == 2


def test_governance_reject_transition_chain_executor_fails_without_candidate_outcome(
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
    _, result = _run_governance_reject_transition_chain_task(
        project_root=project_root,
        source_run_id=run_id,
        dry_run=False,
    )

    assert result.status.value == "failed"
    assert "no persisted candidate validation outcome found" in result.message
    assert result.artifact_refs == []

