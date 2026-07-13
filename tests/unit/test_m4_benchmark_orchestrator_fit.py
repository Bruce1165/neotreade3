from __future__ import annotations

from datetime import date
import json
from pathlib import Path

from apps.worker.main import BootstrapWorkerApp
from neotrade3.benchmark.runtime import DEFAULT_BENCHMARK_MANIFEST
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


def _run_benchmark_task(
    *,
    project_root: Path,
    manifest: str,
    dry_run: bool,
):
    orchestrator = DailyMasterOrchestrator.from_files(
        orchestrator_config_path=ORCHESTRATOR_CONFIG,
        labs_registry_path=LABS_CONFIG,
    )
    app = BootstrapWorkerApp(project_root=project_root)
    task = PlannedTask(
        task_id="benchmark.materialize_run",
        phase=OrchestrationPhase.BENCHMARK,
        lab_id=None,
        entrypoint="neotrade3.benchmark.runtime:run_benchmark_for_manifest",
        depends_on=[],
        outputs=["benchmark_run_artifact", "benchmark_run_ledger"],
        requires_publish_status=False,
        args_template={"manifest": manifest},
    )
    plan = DailyRunPlan(
        target_date=date(2026, 5, 19),
        phases=[OrchestrationPhase.BENCHMARK],
        planned_tasks=[task],
    )
    results = orchestrator.execute_run_plan(
        plan,
        {
            OrchestrationPhase.BENCHMARK: app._create_benchmark_executor(),
        },
        {
            "target_date": date(2026, 5, 19),
            "project_root": str(project_root),
            "requested_by": "test.m4.benchmark.orchestrator_fit",
            "dry_run": dry_run,
        },
    )
    return task, results[0]


def test_benchmark_phase_and_manifest_survive_planning() -> None:
    orchestrator = DailyMasterOrchestrator.from_files(
        orchestrator_config_path=ORCHESTRATOR_CONFIG,
        labs_registry_path=LABS_CONFIG,
    )

    plan = orchestrator.build_run_plan(
        DailyRunRequest(target_date=date(2026, 5, 19), publish_succeeded=False)
    )
    benchmark_task = next(
        task for task in plan.planned_tasks if task.task_id == "benchmark.materialize_run"
    )

    assert OrchestrationPhase.BENCHMARK in plan.phases
    assert benchmark_task.phase == OrchestrationPhase.BENCHMARK
    assert benchmark_task.args_template["manifest"] == DEFAULT_BENCHMARK_MANIFEST


def test_benchmark_executor_dry_run_via_execute_run_plan(tmp_path: Path) -> None:
    project_root = _prepare_project_root(tmp_path)
    _, result = _run_benchmark_task(
        project_root=project_root,
        manifest="config/benchmark/validation_seed_manifest.json",
        dry_run=True,
    )

    assert result.status == RunStatus.OK
    assert result.details["dry_run"] is True
    assert result.details["manifest"] == "config/benchmark/validation_seed_manifest.json"
    assert result.details["run_id"] == "validation_seed_v1_batch"
    assert not (project_root / result.artifact_refs[0]).exists()
    assert not (project_root / result.artifact_refs[1]).exists()


def test_benchmark_executor_materializes_outputs_via_execute_run_plan(
    tmp_path: Path,
) -> None:
    project_root = _prepare_project_root(tmp_path)
    _, result = _run_benchmark_task(
        project_root=project_root,
        manifest="config/benchmark/validation_seed_v2_manifest.json",
        dry_run=False,
    )

    artifact_path = project_root / result.artifact_refs[0]
    ledger_path = project_root / result.artifact_refs[1]

    assert result.status == RunStatus.OK
    assert result.details["dry_run"] is False
    assert result.details["run_id"] == "validation_seed_v2_batch"
    assert artifact_path.exists()
    assert ledger_path.exists()
    assert result.details["sample_count"] > 0
    assert "pass" in result.details["grade_summary"]


def test_orchestrator_config_declares_benchmark_task() -> None:
    payload = json.loads(ORCHESTRATOR_CONFIG.read_text(encoding="utf-8"))
    benchmark_task = next(
        task for task in payload["tasks"] if task["task_id"] == "benchmark.materialize_run"
    )

    assert OrchestrationPhase.BENCHMARK.value in payload["phases"]
    assert benchmark_task["phase"] == OrchestrationPhase.BENCHMARK.value
    assert benchmark_task["entrypoint"] == "neotrade3.benchmark.runtime:run_benchmark_for_manifest"
    assert benchmark_task["args_template"]["manifest"] == DEFAULT_BENCHMARK_MANIFEST
