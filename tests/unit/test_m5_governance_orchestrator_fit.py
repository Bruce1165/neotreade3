from __future__ import annotations

from datetime import date
import json
from pathlib import Path

from apps.worker.main import BootstrapWorkerApp
from neotrade3.governance.run_ledger import (
    read_governance_handoff_artifact,
    read_governance_run_ledger,
)
from neotrade3.governance.runtime import DEFAULT_GOVERNANCE_MANIFEST
from neotrade3.orchestration import (
    DailyMasterOrchestrator,
    DailyRunPlan,
    DailyRunRequest,
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


def _run_governance_task(
    *,
    project_root: Path,
    manifest: str,
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
        entrypoint="neotrade3.governance.runtime:run_governance_manifest",
        depends_on=[],
        outputs=["governance_handoff_artifact", "governance_handoff_ledger"],
        requires_publish_status=False,
        args_template={"manifest": manifest},
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


def test_governance_phase_and_manifest_survive_planning() -> None:
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
    assert governance_task.phase == OrchestrationPhase.GOVERNANCE
    assert governance_task.args_template["manifest"] == DEFAULT_GOVERNANCE_MANIFEST


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
    _, result = _run_governance_task(
        project_root=project_root,
        manifest=DEFAULT_GOVERNANCE_MANIFEST,
        dry_run=True,
    )

    assert result.status == RunStatus.OK
    assert result.details["source_run_id"] == "validation_seed_v1_batch"
    assert result.details["source_layer"] == "M4"
    assert result.details["dry_run"] is True
    assert result.details["manifest"] == str(
        project_root / DEFAULT_GOVERNANCE_MANIFEST
    )
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
    _, result = _run_governance_task(
        project_root=project_root,
        manifest="config/benchmark/validation_seed_v2_manifest.json",
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
    assert result.details["source_run_id"] == "validation_seed_v2_batch"
    assert result.details["source_layer"] == "M4"
    assert result.details["dry_run"] is False
    assert artifact_path.exists()
    assert ledger_path.exists()
    assert ledger_record is not None
    assert artifact_payload is not None
    assert ledger_record.artifact_path == result.artifact_refs[0]
    assert ledger_record.ledger_path == result.artifact_refs[1]
    assert ledger_record.source_run_id == result.details["source_run_id"]
    assert ledger_record.diagnostic_count == result.details["diagnostic_count"]
    assert artifact_payload["source_run_id"] == result.details["source_run_id"]
    assert artifact_payload["projected_assessment_count"] == result.details[
        "projected_assessment_count"
    ]


def test_orchestrator_config_declares_governance_task_manifest() -> None:
    payload = json.loads(ORCHESTRATOR_CONFIG.read_text(encoding="utf-8"))
    governance_task = next(
        task
        for task in payload["tasks"]
        if task["task_id"] == "governance.materialize_handoff"
    )

    assert payload["phases"][-1] == OrchestrationPhase.GOVERNANCE.value
    assert governance_task["phase"] == OrchestrationPhase.GOVERNANCE.value
    assert governance_task["args_template"]["manifest"] == DEFAULT_GOVERNANCE_MANIFEST
