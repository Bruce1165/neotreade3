"""Bootstrap config contract validation for NeoTrade3."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from neotrade3.data_control.source_registry import SourceRegistry
    from neotrade3.labs.registry import LabRegistry
    from neotrade3.orchestration.models import OrchestratorConfig


class ConfigContractError(ValueError):
    """Raised when bootstrap config contracts violate required invariants."""

    def __init__(self, scope: str, issues: list[str]) -> None:
        self.scope = scope
        self.issues = issues
        super().__init__(f"{scope} validation failed: {'; '.join(issues)}")


VALID_DATA_CONTROL_STAGES = {"capture", "compose", "publish"}


@dataclass
class ConfigContractReport:
    """Structured summary of current bootstrap config contract status."""

    status: str
    issues: list[str]
    source_count: int
    enabled_source_count: int
    lab_count: int
    enabled_lab_count: int
    orchestrator_task_count: int
    orchestrator_lab_task_count: int

    def to_payload(self) -> dict[str, object]:
        return {
            "status": self.status,
            "issues": self.issues,
            "summary": {
                "source_count": self.source_count,
                "enabled_source_count": self.enabled_source_count,
                "lab_count": self.lab_count,
                "enabled_lab_count": self.enabled_lab_count,
                "orchestrator_task_count": self.orchestrator_task_count,
                "orchestrator_lab_task_count": self.orchestrator_lab_task_count,
            },
        }


def _append_duplicate_issue(
    issues: list[str], scope: str, label: str, values: list[str]
) -> None:
    duplicates = sorted({value for value in values if values.count(value) > 1})
    if duplicates:
        issues.append(f"{scope} contains duplicate {label}: {', '.join(duplicates)}")


def validate_lab_registry(registry: LabRegistry) -> list[str]:
    issues: list[str] = []

    if not registry.labs:
        issues.append("labs registry must contain at least one lab")
        return issues

    _append_duplicate_issue(
        issues,
        "labs registry",
        "lab_id values",
        [lab.lab_id for lab in registry.labs],
    )

    all_task_ids: list[str] = []
    all_job_ids: list[str] = []

    for lab in registry.labs:
        if lab.enabled and not lab.daily_jobs:
            issues.append(
                f"enabled lab '{lab.lab_id}' must declare at least one daily job"
            )

        artifact_ids = [artifact.artifact_id for artifact in lab.artifacts]
        health_check_ids = [check.check_id for check in lab.health_checks]
        job_task_ids = [job.task_id for job in lab.daily_jobs]
        job_ids = [job.job_id for job in lab.daily_jobs]

        _append_duplicate_issue(
            issues,
            f"lab '{lab.lab_id}'",
            "artifact_id values",
            artifact_ids,
        )
        _append_duplicate_issue(
            issues,
            f"lab '{lab.lab_id}'",
            "health_check ids",
            health_check_ids,
        )
        _append_duplicate_issue(
            issues,
            f"lab '{lab.lab_id}'",
            "task_id values",
            job_task_ids,
        )
        _append_duplicate_issue(
            issues,
            f"lab '{lab.lab_id}'",
            "job_id values",
            job_ids,
        )

        declared_artifacts = set(artifact_ids)
        declared_health_checks = set(health_check_ids)

        for job in lab.daily_jobs:
            all_task_ids.append(job.task_id)
            all_job_ids.append(job.job_id)

            missing_artifacts = sorted(set(job.artifacts) - declared_artifacts)
            if missing_artifacts:
                issues.append(
                    f"job '{job.task_id}' in lab '{lab.lab_id}' references undefined artifacts: "
                    + ", ".join(missing_artifacts)
                )

            missing_health_checks = sorted(
                set(job.health_checks) - declared_health_checks
            )
            if missing_health_checks:
                issues.append(
                    f"job '{job.task_id}' in lab '{lab.lab_id}' references undefined health checks: "
                    + ", ".join(missing_health_checks)
                )

            missing_output_contracts = sorted(set(job.artifacts) - set(job.outputs))
            if missing_output_contracts:
                issues.append(
                    f"job '{job.task_id}' in lab '{lab.lab_id}' must include artifact outputs: "
                    + ", ".join(missing_output_contracts)
                )

    _append_duplicate_issue(
        issues,
        "labs registry",
        "job task_id values",
        all_task_ids,
    )
    _append_duplicate_issue(
        issues,
        "labs registry",
        "job_id values",
        all_job_ids,
    )
    return issues


def validate_source_registry(registry: SourceRegistry) -> list[str]:
    issues: list[str] = []

    if not registry.sources:
        issues.append("source registry must contain at least one source")
        return issues

    _append_duplicate_issue(
        issues,
        "source registry",
        "source_id values",
        [source.source_id for source in registry.sources],
    )

    enabled_stage_support: set[str] = set()

    for source in registry.sources:
        unique_stage_support = list(dict.fromkeys(source.stage_support))
        if len(unique_stage_support) != len(source.stage_support):
            issues.append(
                f"source '{source.source_id}' contains duplicate stage_support entries"
            )

        invalid_stage_support = sorted(
            set(source.stage_support) - VALID_DATA_CONTROL_STAGES
        )
        if invalid_stage_support:
            issues.append(
                f"source '{source.source_id}' contains unsupported stage_support values: "
                + ", ".join(invalid_stage_support)
            )

        if source.enabled:
            enabled_stage_support.update(source.stage_support)

    missing_stage_support = sorted(VALID_DATA_CONTROL_STAGES - enabled_stage_support)
    if missing_stage_support:
        issues.append(
            "enabled sources must cover all data-control stages: "
            + ", ".join(missing_stage_support)
        )

    return issues


def validate_orchestrator_config(config: OrchestratorConfig) -> list[str]:
    issues: list[str] = []

    if not config.phases:
        issues.append("orchestrator config must declare at least one phase")
    if not config.tasks:
        issues.append("orchestrator config must declare at least one task")
        return issues

    phase_values = [phase.value for phase in config.phases]
    _append_duplicate_issue(
        issues,
        "orchestrator config",
        "phase values",
        phase_values,
    )

    task_ids = [task.task_id for task in config.tasks]
    _append_duplicate_issue(
        issues,
        "orchestrator config",
        "task_id values",
        task_ids,
    )

    known_task_ids = set(task_ids)
    configured_phases = set(phase_values)

    for task in config.tasks:
        if task.phase.value not in configured_phases:
            issues.append(
                f"task '{task.task_id}' references undefined phase '{task.phase.value}'"
            )
        if task.task_id in task.depends_on:
            issues.append(f"task '{task.task_id}' cannot depend on itself")
        if not task.outputs:
            issues.append(f"task '{task.task_id}' must declare at least one output")

        unknown_dependencies = sorted(set(task.depends_on) - known_task_ids)
        if unknown_dependencies:
            issues.append(
                f"task '{task.task_id}' references undefined depends_on tasks: "
                + ", ".join(unknown_dependencies)
            )

    return issues


def build_config_contract_report(
    source_registry: SourceRegistry,
    lab_registry: LabRegistry,
    orchestrator_config: OrchestratorConfig,
) -> ConfigContractReport:
    issues: list[str] = []
    issues.extend(validate_source_registry(source_registry))
    issues.extend(validate_lab_registry(lab_registry))
    issues.extend(validate_orchestrator_config(orchestrator_config))

    enabled_labs = {lab.lab_id: lab for lab in lab_registry.enabled_labs()}
    lab_jobs_by_task = {
        job.task_id: (lab.lab_id, job)
        for lab in lab_registry.enabled_labs()
        for job in lab.daily_jobs
    }
    orchestrator_lab_tasks = {
        task.task_id: task
        for task in orchestrator_config.tasks
        if task.lab_id is not None
    }

    missing_orchestrator_tasks = sorted(
        set(lab_jobs_by_task) - set(orchestrator_lab_tasks)
    )
    if missing_orchestrator_tasks:
        issues.append(
            "labs registry jobs missing from orchestrator config: "
            + ", ".join(missing_orchestrator_tasks)
        )

    missing_lab_jobs = sorted(set(orchestrator_lab_tasks) - set(lab_jobs_by_task))
    if missing_lab_jobs:
        issues.append(
            "orchestrator lab tasks missing from labs registry: "
            + ", ".join(missing_lab_jobs)
        )

    for task_id, task in orchestrator_lab_tasks.items():
        if task.lab_id not in enabled_labs:
            issues.append(
                f"orchestrator task '{task_id}' references unknown or disabled lab_id '{task.lab_id}'"
            )

        if task_id not in lab_jobs_by_task:
            continue

        lab_id, job = lab_jobs_by_task[task_id]
        if task.lab_id != lab_id:
            issues.append(
                f"task '{task_id}' lab_id mismatch between orchestrator ('{task.lab_id}') and labs registry ('{lab_id}')"
            )
        if task.entrypoint != job.entrypoint:
            issues.append(
                f"task '{task_id}' entrypoint mismatch between orchestrator and labs registry"
            )
        if task.trigger_type != job.trigger_type:
            issues.append(
                f"task '{task_id}' trigger_type mismatch between orchestrator and labs registry"
            )
        if task.phase.value != job.phase:
            issues.append(
                f"task '{task_id}' phase mismatch between orchestrator and labs registry"
            )
        if task.depends_on != job.depends_on:
            issues.append(
                f"task '{task_id}' depends_on mismatch between orchestrator and labs registry"
            )
        if task.requires_publish_status != job.requires_publish_status:
            issues.append(
                f"task '{task_id}' requires_publish_status mismatch between orchestrator and labs registry"
            )
        if task.outputs != job.outputs:
            issues.append(
                f"task '{task_id}' outputs mismatch between orchestrator and labs registry"
            )

    return ConfigContractReport(
        status="ok" if not issues else "invalid",
        issues=issues,
        source_count=len(source_registry.sources),
        enabled_source_count=len(source_registry.enabled_sources()),
        lab_count=len(lab_registry.labs),
        enabled_lab_count=len(lab_registry.enabled_labs()),
        orchestrator_task_count=len(orchestrator_config.tasks),
        orchestrator_lab_task_count=len(orchestrator_lab_tasks),
    )


def raise_for_contract_issues(scope: str, issues: list[str]) -> None:
    if issues:
        raise ConfigContractError(scope=scope, issues=issues)
