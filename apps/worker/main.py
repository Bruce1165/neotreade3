"""Bootstrap worker entrypoint for NeoTrade3."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, is_dataclass, replace
from datetime import date, datetime
from datetime import timezone
from enum import Enum
from pathlib import Path
from typing import Any, cast

from neotrade3.benchmark.runtime import (
    DEFAULT_BENCHMARK_MANIFEST,
    run_benchmark_for_manifest,
)
from neotrade3.common.python_runtime import log_python_runtime, require_python_310
from neotrade3.data_control import DataControlPipeline
from neotrade3.governance.runtime import (
    run_governance_for_benchmark_run,
    run_governance_reject_execution,
    run_governance_status_transition,
)
from neotrade3.issue_center import IssueCenterCollector
from neotrade3.learning import LearningLoopPipeline
from neotrade3.labs.contracts import materialize_lab_runtime_artifacts
from neotrade3.labs.runtime import LabRuntimeAdapter
from neotrade3.orchestration import (
    DailyMasterOrchestrator,
    DailyRunRequest,
    OnDemandTaskItem,
    OnDemandTaskRequest,
    OrchestratorRunLedgerEntry,
    OrchestratorTaskLedgerEntry,
)
from neotrade3.orchestration.models import (
    DailyRunPlan,
    OrchestrationPhase,
    PlannedTask,
    RunStatus,
    TaskResult,
)


class BootstrapWorkerApp:
    """Builds and optionally persists the current NeoTrade3 bootstrap snapshots."""

    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root)
        self.paths = {
            "labs_config": self.project_root / "config/labs/labs_registry.json",
            "orchestrator_config": self.project_root
            / "config/orchestrator/daily_master_orchestrator.json",
            "source_registry_config": self.project_root
            / "config/data_control/source_registry.json",
            "ledgers_root": self.project_root / "var/ledgers/bootstrap_runs",
            "artifacts_root": self.project_root / "var/artifacts/bootstrap_runs",
        }
        self._lab_adapter: LabRuntimeAdapter | None = None

    def _get_lab_adapter(self) -> LabRuntimeAdapter:
        if self._lab_adapter is None:
            self._lab_adapter = LabRuntimeAdapter()
        return self._lab_adapter

    def _create_data_control_executor(
        self, data_control: DataControlPipeline
    ) -> "callable[[PlannedTask, dict[str, Any]], TaskResult]":
        """Create executor for DATA_PIPELINE phase tasks."""
        # Map task_id suffix to the actual pipeline method
        method_map = {
            "capture": data_control.capture,
            "compose": data_control.compose,
            "publish": data_control.publish,
        }

        def executor(task: PlannedTask, context: dict[str, Any]) -> TaskResult:
            target_date = context.get("target_date", date.today())
            requested_by = str(
                context.get("requested_by", f"worker.{task.task_id}")
            )
            dry_run = bool(context.get("dry_run", False))
            try:
                # Determine which pipeline method to call based on task_id
                method = None
                for suffix, fn in method_map.items():
                    if suffix in task.task_id:
                        method = fn
                        break
                if method is None:
                    # Fallback to full build_plan
                    plan = data_control.build_plan(target_date)
                    return TaskResult(
                        task_id=task.task_id,
                        phase=task.phase,
                        status=RunStatus.OK,
                        lab_id=task.lab_id,
                        message="data control plan built successfully",
                        artifact_refs=[],
                        details={"plan_stages": len(plan.stages) if hasattr(plan, 'stages') else 0},
                    )

                result = method(
                    target_date=target_date,
                    requested_by=requested_by,
                    dry_run=dry_run,
                )
                result_status = getattr(result, "status", "")
                is_ok = result_status == "ok"
                result_message = getattr(
                    result,
                    "message",
                    f"{task.task_id} completed successfully",
                )
                return TaskResult(
                    task_id=task.task_id,
                    phase=task.phase,
                    status=RunStatus.OK if is_ok else RunStatus.FAILED,
                    lab_id=task.lab_id,
                    message=result_message,
                    artifact_refs=[],
                    details={"task_id": task.task_id, "stage_status": result_status},
                )
            except Exception as e:
                return TaskResult(
                    task_id=task.task_id,
                    phase=task.phase,
                    status=RunStatus.FAILED,
                    lab_id=task.lab_id,
                    message=f"data control error: {e}",
                )
        return executor

    def _create_lab_executor(self) -> "callable[[PlannedTask, dict[str, Any]], TaskResult]":
        """Create executor for LABS phase tasks."""
        def executor(task: PlannedTask, context: dict[str, Any]) -> TaskResult:
            adapter = self._get_lab_adapter()
            target_date = context.get("target_date", date.today())
            requested_by = str(
                context.get("requested_by", f"worker.{task.task_id}")
            )
            dry_run = bool(context.get("dry_run", False))
            try:
                result = adapter.run_job(
                    task_id=task.task_id,
                    target_date=target_date,
                    lab_id=task.lab_id or "",
                    project_root=self.project_root,
                )
                raw_status = str(result.get("status", "")).strip().lower()
                if raw_status == "ok":
                    task_status = RunStatus.OK
                elif raw_status == "skipped":
                    task_status = RunStatus.SKIPPED
                elif raw_status == RunStatus.PENDING_IMPLEMENTATION.value:
                    task_status = RunStatus.PENDING_IMPLEMENTATION
                else:
                    task_status = RunStatus.FAILED
                runtime_artifact_refs = (
                    [str(item) for item in result.get("artifacts", []) if str(item).strip()]
                    if isinstance(result.get("artifacts", []), list)
                    else []
                )
                artifact_refs = list(runtime_artifact_refs)
                if task.lab_id and not dry_run:
                    _, _, contract_artifact_refs = materialize_lab_runtime_artifacts(
                        project_root=self.project_root,
                        labs_registry_path=self.paths["labs_config"],
                        lab_id=task.lab_id,
                        runtime_result=result,
                        target_date=(
                            target_date.isoformat()
                            if hasattr(target_date, "isoformat")
                            else str(target_date)
                        ),
                        requested_by=requested_by,
                        requested_at=datetime.now(timezone.utc).strftime(
                            "%Y-%m-%dT%H:%M:%SZ"
                        ),
                        run_status=raw_status or "failed",
                    )
                    for ref in contract_artifact_refs:
                        if ref not in artifact_refs:
                            artifact_refs.append(ref)
                return TaskResult(
                    task_id=task.task_id,
                    phase=task.phase,
                    status=task_status,
                    lab_id=task.lab_id,
                    message=result.get("message", ""),
                    artifact_refs=artifact_refs,
                    details={
                        "picks_count": result.get("picks_count", 0),
                        "lab_status": raw_status,
                    },
                )
            except Exception as e:
                return TaskResult(
                    task_id=task.task_id,
                    phase=task.phase,
                    status=RunStatus.FAILED,
                    lab_id=task.lab_id,
                    message=f"lab execution error: {e}",
                )
        return executor

    def _create_learning_executor(
        self, learning: LearningLoopPipeline
    ) -> "callable[[PlannedTask, dict[str, Any]], TaskResult]":
        """Create executor for LEARNING_LOOP phase tasks."""
        def executor(task: PlannedTask, context: dict[str, Any]) -> TaskResult:
            target_date = context.get("target_date", date.today())
            try:
                # Learning loop is executed post-hoc in self.run(),
                # so here we just mark it as OK with a summary.
                return TaskResult(
                    task_id=task.task_id,
                    phase=task.phase,
                    status=RunStatus.OK,
                    lab_id=task.lab_id,
                    message="learning loop pipeline ready for post-hoc execution",
                    artifact_refs=[],
                    details={"mode": "post_hoc"},
                )
            except Exception as e:
                return TaskResult(
                    task_id=task.task_id,
                    phase=task.phase,
                    status=RunStatus.FAILED,
                    lab_id=task.lab_id,
                    message=f"learning loop error: {e}",
                )
        return executor

    def _create_issue_executor(
        self, issue_center: IssueCenterCollector
    ) -> "callable[[PlannedTask, dict[str, Any]], TaskResult]":
        """Create executor for ISSUE_AGGREGATION_AND_CLOSEOUT phase tasks."""
        def executor(task: PlannedTask, context: dict[str, Any]) -> TaskResult:
            target_date = context.get("target_date", date.today())
            try:
                # Issue aggregation is executed post-hoc in self.run(),
                # so here we just mark it as OK with a summary.
                return TaskResult(
                    task_id=task.task_id,
                    phase=task.phase,
                    status=RunStatus.OK,
                    lab_id=task.lab_id,
                    message="issue aggregation ready for post-hoc execution",
                    artifact_refs=[],
                    details={"mode": "post_hoc"},
                )
            except Exception as e:
                return TaskResult(
                    task_id=task.task_id,
                    phase=task.phase,
                    status=RunStatus.FAILED,
                    lab_id=task.lab_id,
                    message=f"issue aggregation error: {e}",
                )
        return executor

    def _create_benchmark_executor(self) -> "callable[[PlannedTask, dict[str, Any]], TaskResult]":
        """Create executor for BENCHMARK phase tasks."""

        def executor(task: PlannedTask, context: dict[str, Any]) -> TaskResult:
            project_root = Path(context.get("project_root", self.project_root))
            dry_run = bool(context.get("dry_run", False))
            manifest = str(
                task.args_template.get("manifest", DEFAULT_BENCHMARK_MANIFEST)
                or DEFAULT_BENCHMARK_MANIFEST
            ).strip()
            try:
                record = run_benchmark_for_manifest(
                    project_root=project_root,
                    manifest=manifest,
                    dry_run=dry_run,
                )
                return TaskResult(
                    task_id=task.task_id,
                    phase=task.phase,
                    status=RunStatus.OK,
                    lab_id=task.lab_id,
                    message="benchmark run materialized successfully",
                    artifact_refs=[record.artifact_path, record.ledger_path],
                    details={
                        "run_id": record.run_id,
                        "status": record.status,
                        "sample_count": record.sample_count,
                        "executed_sample_ids": list(record.executed_sample_ids),
                        "grade_summary": dict(record.grade_summary),
                        "bucket_summary": dict(record.bucket_summary),
                        "registry_path": record.registry_path,
                        "manifest": manifest,
                        "dry_run": dry_run,
                    },
                )
            except Exception as e:
                return TaskResult(
                    task_id=task.task_id,
                    phase=task.phase,
                    status=RunStatus.FAILED,
                    lab_id=task.lab_id,
                    message=f"benchmark execution error: {e}",
                )

        return executor

    def _create_governance_executor(self) -> "callable[[PlannedTask, dict[str, Any]], TaskResult]":
        """Create executor for GOVERNANCE phase tasks."""

        def executor(task: PlannedTask, context: dict[str, Any]) -> TaskResult:
            project_root = Path(context.get("project_root", self.project_root))
            dry_run = bool(context.get("dry_run", False))
            benchmark_run_id = str(
                task.args_template.get("benchmark_run_id", "") or ""
            ).strip()
            source_run_id = str(
                task.args_template.get("source_run_id", "") or ""
            ).strip()
            validation_id = str(
                task.args_template.get("validation_id", "") or ""
            ).strip()
            try:
                if task.task_id == "governance.status_transition":
                    if not source_run_id:
                        raise ValueError(
                            "source_run_id must be provided when validation_id is set"
                        )
                    if not validation_id:
                        raise ValueError(
                            "validation_id must be provided when source_run_id is set"
                        )
                    record = run_governance_status_transition(
                        project_root=project_root,
                        source_run_id=source_run_id,
                        validation_id=validation_id,
                        dry_run=dry_run,
                    )
                    return TaskResult(
                        task_id=task.task_id,
                        phase=task.phase,
                        status=RunStatus.OK,
                        lab_id=task.lab_id,
                        message="governance status transition materialized successfully",
                        artifact_refs=[record.artifact_path, record.ledger_path],
                        details={
                            "validation_id": record.validation_id,
                            "source_run_id": record.source_run_id,
                            "status": record.status,
                            "baseline_run_id": record.baseline_run_id,
                            "candidate_run_id": record.candidate_run_id,
                            "decision_id": record.decision_id,
                            "effective_attention_id": record.effective_attention_id,
                            "effective_attention_status": record.effective_attention_status,
                            "effective_blocker_id": record.effective_blocker_id,
                            "effective_blocker_active": record.effective_blocker_active,
                            "dry_run": dry_run,
                        },
                    )

                if validation_id:
                    if not source_run_id:
                        raise ValueError(
                            "source_run_id must be provided when validation_id is set"
                        )
                    record = run_governance_reject_execution(
                        project_root=project_root,
                        source_run_id=source_run_id,
                        validation_id=validation_id,
                        dry_run=dry_run,
                    )
                    return TaskResult(
                        task_id=task.task_id,
                        phase=task.phase,
                        status=RunStatus.OK,
                        lab_id=task.lab_id,
                        message="governance reject execution materialized successfully",
                        artifact_refs=[record.artifact_path, record.ledger_path],
                        details={
                            "validation_id": record.validation_id,
                            "source_run_id": record.source_run_id,
                            "status": record.status,
                            "baseline_run_id": record.baseline_run_id,
                            "candidate_run_id": record.candidate_run_id,
                            "decision_id": record.decision_id,
                            "decision": record.decision,
                            "dry_run": dry_run,
                        },
                    )

                if not benchmark_run_id:
                    raise ValueError("benchmark_run_id must be provided")

                record = run_governance_for_benchmark_run(
                    project_root=project_root,
                    benchmark_run_id=benchmark_run_id,
                    dry_run=dry_run,
                )
                return TaskResult(
                    task_id=task.task_id,
                    phase=task.phase,
                    status=RunStatus.OK,
                    lab_id=task.lab_id,
                    message="governance handoff materialized successfully",
                    artifact_refs=[record.artifact_path, record.ledger_path],
                    details={
                        "source_run_id": record.source_run_id,
                        "status": record.status,
                        "source_layer": record.source_layer,
                        "projected_assessment_count": record.projected_assessment_count,
                        "projected_issue_count": record.projected_issue_count,
                        "diagnostic_count": record.diagnostic_count,
                        "change_request_count": record.change_request_count,
                        "experiment_request_count": record.experiment_request_count,
                        "validation_result_count": record.validation_result_count,
                        "promotion_blocker_count": record.promotion_blocker_count,
                        "attention_item_count": record.attention_item_count,
                        "decision_record_count": record.decision_record_count,
                        "dry_run": dry_run,
                        "benchmark_run_id": benchmark_run_id,
                    },
                )
            except Exception as e:
                return TaskResult(
                    task_id=task.task_id,
                    phase=task.phase,
                    status=RunStatus.FAILED,
                    lab_id=task.lab_id,
                    message=f"governance execution error: {e}",
                )

        return executor

    def _create_preflight_executor(self) -> "callable[[PlannedTask, dict[str, Any]], TaskResult]":
        """Create executor for PREFLIGHT phase tasks."""
        def executor(task: PlannedTask, context: dict[str, Any]) -> TaskResult:
            target_date = context.get("target_date", date.today())
            try:
                from neotrade3.orchestration.preflight import PreflightRunner
                runner = PreflightRunner()
                report = runner.build_report(target_date)
                all_passed = all(
                    check.status.value in ("passed", "warning")
                    for check in report.checks
                )
                return TaskResult(
                    task_id=task.task_id,
                    phase=task.phase,
                    status=RunStatus.OK if all_passed else RunStatus.FAILED,
                    lab_id=task.lab_id,
                    message=f"preflight checks: {len(report.checks)} items, "
                           f"{'all passed' if all_passed else 'some failed'}",
                    artifact_refs=[],
                    details={"check_count": len(report.checks)},
                )
            except Exception as e:
                return TaskResult(
                    task_id=task.task_id,
                    phase=task.phase,
                    status=RunStatus.FAILED,
                    lab_id=task.lab_id,
                    message=f"preflight error: {e}",
                )
        return executor

    @staticmethod
    def _build_execution_run_plan(run_plan):
        execution_tasks = []
        for task in run_plan.planned_tasks:
            if (
                task.requires_publish_status
                and task.status == RunStatus.BLOCKED
                and task.skip_reason == "publish_not_successful"
            ):
                execution_tasks.append(
                    replace(task, status=RunStatus.PLANNED, skip_reason=None)
                )
            else:
                execution_tasks.append(task)
        return replace(run_plan, planned_tasks=execution_tasks)

    @staticmethod
    def _effective_publish_succeeded(task_results: list[TaskResult]) -> bool:
        for result in task_results:
            if result.task_id == "data_control.publish":
                return result.status == RunStatus.OK
        return False

    def run(
        self,
        target_date: date,
        publish_succeeded: bool,
        write_outputs: bool,
        *,
        requested_by: str = "BootstrapWorkerApp.run",
        dry_run: bool = False,
    ) -> dict[str, object]:
        # ---- 运行锁获取 ----
        from neotrade3.orchestration.preflight import PreflightRunner
        lock_acquired, lock_msg = PreflightRunner.acquire_lock(
            project_root=self.project_root,
            requested_by=requested_by,
        )
        if not lock_acquired:
            return {
                "status": "blocked",
                "target_date": target_date.isoformat(),
                "message": lock_msg,
                "orchestration": {"task_results": []},
                "summary": {
                    "planned_task_count": 0,
                    "issue_case_count": 0,
                    "learning_candidate_count": 0,
                },
            }

        try:
            return self._run_inner(
                target_date,
                publish_succeeded,
                write_outputs,
                requested_by=requested_by,
                dry_run=dry_run,
            )
        finally:
            PreflightRunner.release_lock(self.project_root)

    def _run_inner(
        self,
        target_date: date,
        publish_succeeded: bool,
        write_outputs: bool,
        *,
        requested_by: str,
        dry_run: bool,
    ) -> dict[str, object]:
        data_control = DataControlPipeline.from_registry_file(
            self.paths["source_registry_config"]
        )
        orchestrator = DailyMasterOrchestrator.from_files(
            orchestrator_config_path=self.paths["orchestrator_config"],
            labs_registry_path=self.paths["labs_config"],
        )
        issue_center = IssueCenterCollector()
        learning = LearningLoopPipeline()

        data_plan = data_control.build_plan(target_date)
        data_plan_ledger = data_control.build_plan_ledger(data_plan)
        data_stage_summary = self._load_data_control_stage_summary(target_date)

        run_plan = orchestrator.build_run_plan(
            DailyRunRequest(
                target_date=target_date, publish_succeeded=publish_succeeded
            )
        )
        execution_run_plan = self._build_execution_run_plan(run_plan)

        # Build task executors for real execution
        # Map to actual OrchestrationPhase values used in config
        task_executors = {
            OrchestrationPhase.DATA_PIPELINE: self._create_data_control_executor(data_control),
            OrchestrationPhase.PUBLISH_GATED_JOBS: self._create_lab_executor(),
            OrchestrationPhase.DAILY_LAB_JOBS: self._create_lab_executor(),
            OrchestrationPhase.LEARNING_LOOP: self._create_learning_executor(learning),
            OrchestrationPhase.ISSUE_AGGREGATION_AND_CLOSEOUT: self._create_issue_executor(issue_center),
            OrchestrationPhase.BENCHMARK: self._create_benchmark_executor(),
            OrchestrationPhase.GOVERNANCE: self._create_governance_executor(),
            OrchestrationPhase.PREFLIGHT: self._create_preflight_executor(),
        }

        # Execute with real executors
        context = {
            "target_date": target_date,
            "project_root": str(self.project_root),
            "db_path": str(self.project_root / "var/data/neotrade3.db"),
            "requested_by": requested_by,
            "dry_run": dry_run,
        }
        task_results = orchestrator.execute_run_plan(
            execution_run_plan, task_executors, context
        )
        effective_publish_succeeded = self._effective_publish_succeeded(task_results)

        run_entry, task_entries = self._build_execution_run_ledger(
            target_date=target_date,
            execution_run_plan=execution_run_plan,
            task_results=task_results,
        )
        issue_snapshot = issue_center.collect(
            target_date,
            task_results,
            task_entries,
            data_control_stage_summary=data_stage_summary,
        )
        learning_snapshot = learning.build_snapshot(
            target_date,
            task_results,
            issue_snapshot,
            project_root=self.project_root,
        )

        snapshot = {
            "status": run_entry.status.value,
            "target_date": target_date.isoformat(),
            "publish_succeeded": effective_publish_succeeded,
            "requested_publish_succeeded": publish_succeeded,
            "data_control": {
                "source_summary": data_control.describe_sources(),
                "plan": self._to_jsonable(data_plan),
                "plan_ledger": self._to_jsonable(data_plan_ledger),
                "stage_summary": data_stage_summary,
            },
            "orchestration": {
                "plan": self._to_jsonable(execution_run_plan),
                "task_results": self._to_jsonable(task_results),
                "run_ledger": self._to_jsonable(run_entry),
                "task_ledger": self._to_jsonable(task_entries),
            },
            "issue_center": self._to_jsonable(issue_snapshot),
            "learning": self._to_jsonable(learning_snapshot),
            "summary": {
                "planned_task_count": len(execution_run_plan.planned_tasks),
                "issue_case_count": len(issue_snapshot.cases),
                "learning_candidate_count": len(
                    learning_snapshot.adjustment_candidates
                ),
            },
        }

        if write_outputs:
            self.write_outputs(target_date, snapshot)

        return snapshot

    def run_governance_reject_on_demand(
        self,
        *,
        target_date: date,
        source_run_id: str,
        validation_id: str,
        requested_by: str = "BootstrapWorkerApp.run_governance_reject_on_demand",
        dry_run: bool = False,
    ) -> dict[str, object]:
        orchestrator = DailyMasterOrchestrator.from_files(
            orchestrator_config_path=self.paths["orchestrator_config"],
            labs_registry_path=self.paths["labs_config"],
        )
        plan = orchestrator.build_on_demand_plan(
            OnDemandTaskRequest(
                target_date=target_date,
                tasks=[
                    OnDemandTaskItem(
                        task_id="governance.reject_execution",
                        phase=OrchestrationPhase.GOVERNANCE,
                        entrypoint=(
                            "neotrade3.governance.runtime:"
                            "run_governance_reject_execution"
                        ),
                        args_template={
                            "source_run_id": source_run_id,
                            "validation_id": validation_id,
                        },
                        outputs=[
                            "governance_reject_artifact",
                            "governance_reject_ledger",
                        ],
                    )
                ],
            )
        )
        task_results = orchestrator.execute_run_plan(
            plan,
            {
                OrchestrationPhase.GOVERNANCE: self._create_governance_executor(),
            },
            {
                "target_date": target_date,
                "project_root": str(self.project_root),
                "db_path": str(self.project_root / "var/data/neotrade3.db"),
                "requested_by": requested_by,
                "dry_run": dry_run,
            },
        )
        run_entry, task_entries = self._build_execution_run_ledger(
            target_date=target_date,
            execution_run_plan=plan,
            task_results=task_results,
        )
        return {
            "status": run_entry.status.value,
            "target_date": target_date.isoformat(),
            "orchestration": {
                "plan": self._to_jsonable(plan),
                "task_results": self._to_jsonable(task_results),
                "run_ledger": self._to_jsonable(run_entry),
                "task_ledger": self._to_jsonable(task_entries),
            },
            "summary": {
                "planned_task_count": len(plan.planned_tasks),
                "executed_task_count": len(task_results),
                "ok_task_count": sum(
                    1 for result in task_results if result.status == RunStatus.OK
                ),
            },
        }

    def run_governance_status_transition_on_demand(
        self,
        *,
        target_date: date,
        source_run_id: str,
        validation_id: str,
        requested_by: str = (
            "BootstrapWorkerApp.run_governance_status_transition_on_demand"
        ),
        dry_run: bool = False,
    ) -> dict[str, object]:
        orchestrator = DailyMasterOrchestrator.from_files(
            orchestrator_config_path=self.paths["orchestrator_config"],
            labs_registry_path=self.paths["labs_config"],
        )
        plan = orchestrator.build_on_demand_plan(
            OnDemandTaskRequest(
                target_date=target_date,
                tasks=[
                    OnDemandTaskItem(
                        task_id="governance.status_transition",
                        phase=OrchestrationPhase.GOVERNANCE,
                        entrypoint=(
                            "neotrade3.governance.runtime:"
                            "run_governance_status_transition"
                        ),
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
        )
        task_results = orchestrator.execute_run_plan(
            plan,
            {
                OrchestrationPhase.GOVERNANCE: self._create_governance_executor(),
            },
            {
                "target_date": target_date,
                "project_root": str(self.project_root),
                "db_path": str(self.project_root / "var/data/neotrade3.db"),
                "requested_by": requested_by,
                "dry_run": dry_run,
            },
        )
        run_entry, task_entries = self._build_execution_run_ledger(
            target_date=target_date,
            execution_run_plan=plan,
            task_results=task_results,
        )
        return {
            "status": run_entry.status.value,
            "target_date": target_date.isoformat(),
            "orchestration": {
                "plan": self._to_jsonable(plan),
                "task_results": self._to_jsonable(task_results),
                "run_ledger": self._to_jsonable(run_entry),
                "task_ledger": self._to_jsonable(task_entries),
            },
            "summary": {
                "planned_task_count": len(plan.planned_tasks),
                "executed_task_count": len(task_results),
                "ok_task_count": sum(
                    1 for result in task_results if result.status == RunStatus.OK
                ),
            },
        }

    def _build_execution_run_ledger(
        self,
        *,
        target_date: date,
        execution_run_plan: DailyRunPlan,
        task_results: list[TaskResult],
    ) -> tuple[OrchestratorRunLedgerEntry, list[OrchestratorTaskLedgerEntry]]:
        result_by_task = {result.task_id: result for result in task_results}
        task_statuses = [result.status for result in task_results]
        if any(status == RunStatus.FAILED for status in task_statuses):
            run_status = RunStatus.FAILED
        elif any(status == RunStatus.BLOCKED for status in task_statuses):
            run_status = RunStatus.BLOCKED
        elif any(status == RunStatus.SKIPPED for status in task_statuses):
            run_status = RunStatus.SKIPPED
        elif any(status == RunStatus.PENDING_IMPLEMENTATION for status in task_statuses):
            run_status = RunStatus.PENDING_IMPLEMENTATION
        else:
            run_status = RunStatus.OK

        run_entry = OrchestratorRunLedgerEntry(
            orchestrator_run_id=f"exec:{target_date.isoformat()}",
            target_date=target_date.isoformat(),
            status=run_status,
            phase_count=len(execution_run_plan.phases),
            task_count=len(execution_run_plan.planned_tasks),
            blocked_task_count=sum(
                1 for status in task_statuses if status == RunStatus.BLOCKED
            ),
            skipped_task_count=sum(
                1 for status in task_statuses if status == RunStatus.SKIPPED
            ),
            created_at=datetime.now().isoformat(),
        )
        task_entries = [
            OrchestratorTaskLedgerEntry(
                orchestrator_run_id=run_entry.orchestrator_run_id,
                task_id=task.task_id,
                phase=task.phase.value,
                lab_id=task.lab_id,
                status=(
                    result_by_task[task.task_id].status
                    if task.task_id in result_by_task
                    else task.status
                ),
                dependency_refs=task.depends_on,
                issue_summary=(
                    result_by_task[task.task_id].message
                    if task.task_id in result_by_task
                    else task.skip_reason
                ),
            )
            for task in execution_run_plan.planned_tasks
        ]
        return run_entry, task_entries

    def _load_data_control_stage_summary(self, target_date: date) -> dict[str, object]:
        date_key = target_date.isoformat()
        summary: dict[str, object] = {"target_date": date_key, "stages": {}}
        stages: dict[str, object] = {}
        for stage in ("capture", "compose", "publish"):
            ledger_path = (
                self.project_root
                / "var/ledgers/data_control"
                / date_key
                / f"data_control_{stage}_ledger.json"
            )
            artifact_path = (
                self.project_root
                / "var/artifacts/data_control"
                / date_key
                / f"data_control_{stage}_result.json"
            )
            if not ledger_path.exists():
                continue
            try:
                payload = json.loads(ledger_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(payload, dict):
                continue

            item: dict[str, object] = {
                "status": str(payload.get("status", "")),
                "message": str(payload.get("message", "")),
                "requested_at": str(payload.get("requested_at", "")),
                "ledger_path": str(ledger_path.relative_to(self.project_root)),
                "artifact_path": (
                    str(artifact_path.relative_to(self.project_root))
                    if artifact_path.exists()
                    else None
                ),
            }
            if stage in {"capture", "publish"}:
                units_validation = payload.get("units_validation")
                if isinstance(units_validation, dict):
                    item["units_validation"] = units_validation
            if stage == "compose":
                warnings = payload.get("warnings")
                if isinstance(warnings, list):
                    item["warnings"] = [str(w) for w in warnings]
                    item["warning_count"] = len(warnings)
                candidates = payload.get("candidate_universe")
                if isinstance(candidates, list):
                    item["candidate_count"] = len(candidates)
            m1_formal_artifacts = payload.get("m1_formal_artifacts")
            if isinstance(m1_formal_artifacts, dict):
                summary_payload = m1_formal_artifacts.get("summary")
                if isinstance(summary_payload, dict):
                    item["m1_formal_artifacts"] = summary_payload
            stages[stage] = item
        summary["stages"] = stages
        return summary

    def write_outputs(self, target_date: date, snapshot: dict[str, object]) -> None:
        date_key = target_date.isoformat()
        ledgers_dir = self.paths["ledgers_root"] / date_key
        artifacts_dir = self.paths["artifacts_root"] / date_key
        ledgers_dir.mkdir(parents=True, exist_ok=True)
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        self._write_json(
            ledgers_dir / "data_control_plan_ledger.json", snapshot["data_control"]
        )
        self._write_json(
            ledgers_dir / "orchestration_run_snapshot.json", snapshot["orchestration"]
        )
        self._write_json(
            artifacts_dir / "issue_center_snapshot.json", snapshot["issue_center"]
        )
        self._write_json(artifacts_dir / "learning_snapshot.json", snapshot["learning"])
        self._write_json(
            artifacts_dir / "bootstrap_run_summary.json",
            self._build_summary_artifact(snapshot),
        )

    @staticmethod
    def _write_json(file_path: Path, payload: object) -> None:
        file_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def _build_summary_artifact(snapshot: dict[str, object]) -> dict[str, object]:
        orchestration = snapshot.get("orchestration", {})
        task_results: object = []
        if isinstance(orchestration, dict):
            candidate = orchestration.get("task_results", [])
            if isinstance(candidate, list):
                task_results = candidate
        return {
            "target_date": snapshot.get("target_date"),
            "publish_succeeded": snapshot.get("publish_succeeded", False),
            "requested_publish_succeeded": snapshot.get(
                "requested_publish_succeeded", False
            ),
            "summary": snapshot.get("summary", {}),
            "orchestration": {
                "task_results": task_results,
            },
        }

    @classmethod
    def _to_jsonable(cls, value: object) -> object:
        if is_dataclass(value) and not isinstance(value, type):
            return cls._to_jsonable(asdict(cast(Any, value)))
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, (date, datetime)):
            return value.isoformat()
        if isinstance(value, dict):
            return {str(key): cls._to_jsonable(item) for key, item in value.items()}
        if isinstance(value, list):
            return [cls._to_jsonable(item) for item in value]
        return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the NeoTrade3 bootstrap worker.")
    parser.add_argument(
        "--mode",
        choices=("daily", "governance_reject", "governance_status_transition"),
        default="daily",
        help="Worker run mode. Defaults to the daily bootstrap flow.",
    )
    parser.add_argument(
        "--date", dest="target_date", help="Target date in YYYY-MM-DD format."
    )
    parser.add_argument(
        "--publish-succeeded",
        action="store_true",
        help="Mark publish-gated jobs as unblocked in the bootstrap plan.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build snapshots without writing files under var/.",
    )
    parser.add_argument(
        "--source-run-id",
        help="Governance handoff source run id for governance_reject mode.",
    )
    parser.add_argument(
        "--validation-id",
        help="Validation result id for governance_reject mode.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    log_python_runtime(entrypoint="apps.worker.main")
    try:
        require_python_310(entrypoint="apps.worker.main")
    except RuntimeError as exc:
        print(json.dumps({"entrypoint": "apps.worker.main", "status": "error", "error": str(exc)}, ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 2

    target_date = (
        date.fromisoformat(args.target_date) if args.target_date else date.today()
    )
    mode = str(getattr(args, "mode", "daily") or "daily").strip().lower()
    source_run_id = str(getattr(args, "source_run_id", "") or "").strip()
    validation_id = str(getattr(args, "validation_id", "") or "").strip()
    project_root = Path(__file__).resolve().parents[2]
    app = BootstrapWorkerApp(project_root=project_root)
    if mode == "governance_reject":
        if not source_run_id or not validation_id:
            parser.error(
                "--source-run-id and --validation-id are required when "
                "--mode governance_reject"
            )
        snapshot = app.run_governance_reject_on_demand(
            target_date=target_date,
            source_run_id=source_run_id,
            validation_id=validation_id,
            dry_run=bool(args.dry_run),
        )
    elif mode == "governance_status_transition":
        if not source_run_id or not validation_id:
            parser.error(
                "--source-run-id and --validation-id are required when "
                "--mode governance_status_transition"
            )
        snapshot = app.run_governance_status_transition_on_demand(
            target_date=target_date,
            source_run_id=source_run_id,
            validation_id=validation_id,
            dry_run=bool(args.dry_run),
        )
    else:
        snapshot = app.run(
            target_date=target_date,
            publish_succeeded=args.publish_succeeded,
            write_outputs=not args.dry_run,
        )
    orchestration = snapshot.get("orchestration", {})
    run_ledger_status = None
    if isinstance(orchestration, dict):
        run_ledger = orchestration.get("run_ledger", {})
        if isinstance(run_ledger, dict):
            run_ledger_status = run_ledger.get("status")
    status = str(snapshot.get("status") or run_ledger_status or "ok").strip().lower()
    print(
        json.dumps(
            {
                "status": status,
                "target_date": snapshot["target_date"],
                "summary": snapshot["summary"],
                "write_outputs": not args.dry_run,
            },
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
