"""Daily master orchestrator bootstrap for NeoTrade3."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from neotrade3.labs import LabRegistry

from .config_loader import load_orchestrator_config
from .ledger import (
    OrchestratorLedgerBuilder,
    OrchestratorRunLedgerEntry,
    OrchestratorTaskLedgerEntry,
)
from .models import (
    DailyRunPlan,
    DailyRunRequest,
    OrchestratorConfig,
    OrchestrationPhase,
    PlannedTask,
    RunStatus,
    TaskResult,
)
from .preflight import PreflightRunner

# Type alias for task executors
TaskExecutor = Callable[[PlannedTask, dict[str, Any]], TaskResult]


class DailyMasterOrchestrator:
    """Builds an execution plan from config without running real jobs yet."""

    def __init__(self, config: OrchestratorConfig, lab_registry: LabRegistry) -> None:
        self.config = config
        self.lab_registry = lab_registry
        self.preflight_runner = PreflightRunner()
        self.ledger_builder = OrchestratorLedgerBuilder()

    @classmethod
    def from_files(
        cls,
        orchestrator_config_path: str | Path,
        labs_registry_path: str | Path,
    ) -> "DailyMasterOrchestrator":
        config = load_orchestrator_config(orchestrator_config_path)
        lab_registry = LabRegistry.from_file(labs_registry_path)
        return cls(config=config, lab_registry=lab_registry)

    def build_run_plan(self, request: DailyRunRequest) -> DailyRunPlan:
        enabled_lab_ids = {lab.lab_id for lab in self.lab_registry.enabled_labs()}
        planned_tasks: list[PlannedTask] = []
        preflight_report = self.preflight_runner.build_report(request.target_date)

        for task in self.config.tasks:
            status = RunStatus.PLANNED
            skip_reason = None

            if task.lab_id and task.lab_id not in enabled_lab_ids:
                status = RunStatus.SKIPPED
                skip_reason = "lab_disabled"
            elif task.requires_publish_status and not request.publish_succeeded:
                status = RunStatus.BLOCKED
                skip_reason = "publish_not_successful"

            planned_tasks.append(
                PlannedTask(
                    task_id=task.task_id,
                    phase=task.phase,
                    lab_id=task.lab_id,
                    entrypoint=task.entrypoint,
                    depends_on=task.depends_on,
                    outputs=task.outputs,
                    requires_publish_status=task.requires_publish_status,
                    status=status,
                    skip_reason=skip_reason,
                )
            )

        return DailyRunPlan(
            target_date=request.target_date,
            phases=self.config.phases,
            preflight_report=preflight_report,
            planned_tasks=planned_tasks,
        )

    def describe(self) -> dict[str, int]:
        enabled_labs = len(self.lab_registry.enabled_labs())
        return {
            "phase_count": len(self.config.phases),
            "task_count": len(self.config.tasks),
            "enabled_lab_count": enabled_labs,
        }

    def build_placeholder_task_results(self, plan: DailyRunPlan) -> list[TaskResult]:
        return [
            TaskResult(
                task_id=task.task_id,
                phase=task.phase,
                status=(
                    task.status
                    if task.status in {RunStatus.BLOCKED, RunStatus.SKIPPED}
                    else RunStatus.PENDING_IMPLEMENTATION
                ),
                lab_id=task.lab_id,
                message=(
                    f"Task is {task.status.value} during plan construction."
                    if task.status in {RunStatus.BLOCKED, RunStatus.SKIPPED}
                    else "Task execution has not been implemented in NeoTrade3 yet."
                ),
            )
            for task in plan.planned_tasks
        ]

    def build_placeholder_run_ledger(
        self,
        plan: DailyRunPlan,
    ) -> tuple[OrchestratorRunLedgerEntry, list[OrchestratorTaskLedgerEntry]]:
        run_entry = self.ledger_builder.build_run_entry(plan)
        task_entries = self.ledger_builder.build_task_entries(
            run_entry, plan.planned_tasks
        )
        return run_entry, task_entries

    def execute_run_plan(
        self,
        plan: DailyRunPlan,
        task_executors: dict[OrchestrationPhase, TaskExecutor],
        context: dict[str, Any] | None = None,
    ) -> list[TaskResult]:
        """Execute a run plan using provided task executors.

        Args:
            plan: The run plan to execute
            task_executors: Mapping of phase to executor function
            context: Shared context for all tasks (db paths, date, etc.)

        Returns:
            List of TaskResult for each task in the plan
        """
        if context is None:
            context = {}

        results: list[TaskResult] = []
        completed_tasks: dict[str, TaskResult] = {}

        for task in plan.planned_tasks:
            # Handle pre-determined statuses
            if task.status == RunStatus.SKIPPED:
                skipped_result = TaskResult(
                    task_id=task.task_id,
                    phase=task.phase,
                    status=RunStatus.SKIPPED,
                    lab_id=task.lab_id,
                    message=task.skip_reason or "skipped",
                )
                results.append(skipped_result)
                completed_tasks[task.task_id] = skipped_result
                continue

            if task.status == RunStatus.BLOCKED:
                blocked_result = TaskResult(
                    task_id=task.task_id,
                    phase=task.phase,
                    status=RunStatus.BLOCKED,
                    lab_id=task.lab_id,
                    message=task.skip_reason or "blocked",
                )
                results.append(blocked_result)
                completed_tasks[task.task_id] = blocked_result
                continue

            # Check dependencies
            missing_deps = [dep for dep in task.depends_on if dep not in completed_tasks]
            if missing_deps:
                blocked_result = TaskResult(
                    task_id=task.task_id,
                    phase=task.phase,
                    status=RunStatus.BLOCKED,
                    lab_id=task.lab_id,
                    message=(
                        "blocked by incomplete dependencies: "
                        f"{missing_deps}"
                    ),
                )
                results.append(blocked_result)
                completed_tasks[task.task_id] = blocked_result
                continue

            dep_results = [completed_tasks[dep] for dep in task.depends_on]
            non_ok_deps = [r for r in dep_results if r.status != RunStatus.OK]
            if non_ok_deps:
                blocked_result = TaskResult(
                    task_id=task.task_id,
                    phase=task.phase,
                    status=RunStatus.BLOCKED,
                    lab_id=task.lab_id,
                    message=(
                        "blocked by non-ok dependencies: "
                        f"{[d.task_id for d in non_ok_deps]}"
                    ),
                )
                results.append(blocked_result)
                completed_tasks[task.task_id] = blocked_result
                continue

            # Find and execute
            executor = self._find_executor(task, task_executors)
            if executor is None:
                results.append(
                    TaskResult(
                        task_id=task.task_id,
                        phase=task.phase,
                        status=RunStatus.PENDING_IMPLEMENTATION,
                        lab_id=task.lab_id,
                        message="no executor registered for this phase",
                    )
                )
                continue

            try:
                result = executor(task, context)
                results.append(result)
                completed_tasks[task.task_id] = result
            except Exception as e:
                result = TaskResult(
                    task_id=task.task_id,
                    phase=task.phase,
                    status=RunStatus.FAILED,
                    lab_id=task.lab_id,
                    message=f"execution error: {e}",
                )
                results.append(result)
                completed_tasks[task.task_id] = result

        return results

    def _find_executor(
        self,
        task: PlannedTask,
        task_executors: dict[OrchestrationPhase, TaskExecutor],
    ) -> TaskExecutor | None:
        """Find the appropriate executor for a task."""
        return task_executors.get(task.phase)
