"""Placeholder run ledger models for NeoTrade3 orchestration bootstrap."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from .models import DailyRunPlan, PlannedTask, RunStatus


@dataclass
class OrchestratorRunLedgerEntry:
    """Top-level ledger summary for one orchestrator planning cycle."""

    orchestrator_run_id: str
    target_date: str
    status: RunStatus
    phase_count: int
    task_count: int
    blocked_task_count: int
    skipped_task_count: int
    created_at: str


@dataclass
class OrchestratorTaskLedgerEntry:
    """Per-task ledger placeholder derived from the bootstrap plan."""

    orchestrator_run_id: str
    task_id: str
    phase: str
    lab_id: str | None
    status: RunStatus
    dependency_refs: list[str]
    issue_summary: str | None


class OrchestratorLedgerBuilder:
    """Builds placeholder ledger entries without persisting them yet."""

    def build_run_entry(self, plan: DailyRunPlan) -> OrchestratorRunLedgerEntry:
        task_statuses = [task.status for task in plan.planned_tasks]
        status = RunStatus.PLANNED
        if any(task_status == RunStatus.BLOCKED for task_status in task_statuses):
            status = RunStatus.BLOCKED

        return OrchestratorRunLedgerEntry(
            orchestrator_run_id=str(uuid4()),
            target_date=plan.target_date.isoformat(),
            status=status,
            phase_count=len(plan.phases),
            task_count=len(plan.planned_tasks),
            blocked_task_count=sum(
                1 for item in task_statuses if item == RunStatus.BLOCKED
            ),
            skipped_task_count=sum(
                1 for item in task_statuses if item == RunStatus.SKIPPED
            ),
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    def build_task_entries(
        self,
        run_entry: OrchestratorRunLedgerEntry,
        planned_tasks: list[PlannedTask],
    ) -> list[OrchestratorTaskLedgerEntry]:
        return [
            OrchestratorTaskLedgerEntry(
                orchestrator_run_id=run_entry.orchestrator_run_id,
                task_id=task.task_id,
                phase=task.phase.value,
                lab_id=task.lab_id,
                status=task.status,
                dependency_refs=task.depends_on,
                issue_summary=task.skip_reason,
            )
            for task in planned_tasks
        ]
