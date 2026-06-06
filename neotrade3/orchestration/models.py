"""Core models for the NeoTrade3 orchestration bootstrap."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any


class OrchestrationPhase(str, Enum):
    """Documented phases for the daily master orchestrator."""

    PREFLIGHT = "preflight"
    DATA_PIPELINE = "data_pipeline"
    PUBLISH_GATED_JOBS = "publish_gated_jobs"
    DAILY_LAB_JOBS = "daily_lab_jobs"
    LEARNING_LOOP = "learning_loop"
    ISSUE_AGGREGATION_AND_CLOSEOUT = "issue_aggregation_and_closeout"


class RunStatus(str, Enum):
    """Shared run status vocabulary for bootstrap planning and execution results."""

    PLANNED = "planned"
    BLOCKED = "blocked"
    SKIPPED = "skipped"
    PENDING_IMPLEMENTATION = "pending_implementation"
    OK = "ok"
    FAILED = "failed"


class PreflightStatus(str, Enum):
    """Status values for bootstrap preflight checks."""

    PENDING_IMPLEMENTATION = "pending_implementation"
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"


@dataclass
class TaskRegistration:
    """Minimal registered task model loaded from orchestrator config."""

    task_id: str
    lab_id: str | None
    trigger_type: str
    phase: OrchestrationPhase
    entrypoint: str
    args_template: dict[str, object]
    depends_on: list[str]
    requires_publish_status: bool
    outputs: list[str]
    failure_policy: str
    retry_policy: str
    issue_tags: list[str]

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TaskRegistration":
        lab_id = payload.get("lab_id")
        args_template_raw = payload.get("args_template", {})
        args_template = args_template_raw if isinstance(args_template_raw, dict) else {}
        depends_on_raw = payload.get("depends_on", [])
        depends_on = (
            [str(item) for item in depends_on_raw]
            if isinstance(depends_on_raw, list)
            else []
        )
        outputs_raw = payload.get("outputs", [])
        outputs = (
            [str(item) for item in outputs_raw] if isinstance(outputs_raw, list) else []
        )
        issue_tags_raw = payload.get("issue_tags", [])
        issue_tags = (
            [str(item) for item in issue_tags_raw]
            if isinstance(issue_tags_raw, list)
            else []
        )
        return cls(
            task_id=str(payload["task_id"]),
            lab_id=None if lab_id is None else str(lab_id),
            trigger_type=str(payload["trigger_type"]),
            phase=OrchestrationPhase(str(payload["phase"])),
            entrypoint=str(payload["entrypoint"]),
            args_template=args_template,
            depends_on=depends_on,
            requires_publish_status=bool(payload.get("requires_publish_status", False)),
            outputs=outputs,
            failure_policy=str(payload["failure_policy"]),
            retry_policy=str(payload["retry_policy"]),
            issue_tags=issue_tags,
        )


@dataclass
class OrchestratorConfig:
    """Loaded orchestrator config for bootstrap planning."""

    version: int
    description: str
    phases: list[OrchestrationPhase]
    tasks: list[TaskRegistration]


@dataclass
class DailyRunRequest:
    """Minimal run request accepted by the orchestrator."""

    target_date: date
    publish_succeeded: bool = False


@dataclass
class PlannedTask:
    """Task planning result used before real execution exists."""

    task_id: str
    phase: OrchestrationPhase
    lab_id: str | None
    entrypoint: str
    depends_on: list[str]
    outputs: list[str]
    requires_publish_status: bool
    status: RunStatus = RunStatus.PLANNED
    skip_reason: str | None = None


@dataclass
class DailyRunPlan:
    """Bootstrap plan emitted by the orchestrator."""

    target_date: date
    phases: list[OrchestrationPhase]
    preflight_report: "PreflightReport | None" = None
    planned_tasks: list[PlannedTask] = field(default_factory=list)


@dataclass
class PreflightCheck:
    """Single bootstrap preflight check definition and current result."""

    check_id: str
    description: str
    status: PreflightStatus = PreflightStatus.PENDING_IMPLEMENTATION
    details: str = "Check logic has not been implemented in NeoTrade3 yet."


@dataclass
class PreflightReport:
    """Grouped preflight checks for a single orchestrator run."""

    target_date: date
    checks: list[PreflightCheck] = field(default_factory=list)
    overall_status: PreflightStatus = PreflightStatus.PENDING_IMPLEMENTATION


@dataclass
class TaskResult:
    """Task result from orchestrator execution."""

    task_id: str
    phase: OrchestrationPhase
    status: RunStatus
    lab_id: str | None = None
    message: str = ""
    artifact_refs: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)
