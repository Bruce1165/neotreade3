"""Issue collection and deep analysis for NeoTrade3."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from neotrade3.orchestration import OrchestratorTaskLedgerEntry, RunStatus, TaskResult

from .models import (
    DegradationInfo,
    IssueCase,
    IssueCenterSnapshot,
    IssueEvent,
    IssueSeverity,
    Recommendation,
    RootCauseAnalysis,
)


class IssueCenterCollector:
    """Builds issue events, performs root cause analysis, detects degradation,
    and generates recommendations.
    """

    def __init__(self, project_root: Path | None = None) -> None:
        self.project_root = project_root or Path(__file__).resolve().parents[2]

    def collect(
        self,
        target_date: date,
        task_results: list[TaskResult],
        task_entries: list[OrchestratorTaskLedgerEntry],
    ) -> IssueCenterSnapshot:
        """Collect issues and perform deep analysis."""
        # Step 1: Build basic events and cases
        issues_by_task: dict[str, IssueEvent] = {}
        entry_by_task: dict[str, OrchestratorTaskLedgerEntry] = {
            e.task_id: e for e in task_entries
        }

        for result in task_results:
            severity = self._severity_for_status(result.status)
            if severity is None:
                continue

            issue = IssueEvent(
                event_id=f"{result.task_id}:{result.status.value}",
                target_date=target_date,
                source="orchestration.task_result",
                task_id=result.task_id,
                phase=result.phase.value,
                severity=severity,
                status=result.status.value,
                summary=result.message,
                lab_id=result.lab_id,
                dependency_refs=entry_by_task.get(result.task_id, None).dependency_refs if entry_by_task.get(result.task_id) else [],
            )
            issues_by_task[result.task_id] = issue

        events = list(issues_by_task.values())
        cases = [
            IssueCase(
                case_id=f"case:{event.task_id}",
                target_date=event.target_date,
                task_id=event.task_id,
                phase=event.phase,
                severity=event.severity,
                status=event.status,
                lab_id=event.lab_id,
                summary=event.summary,
                event_ids=[event.event_id],
            )
            for event in events
        ]

        # Step 2: Root cause analysis
        root_causes: dict[str, RootCauseAnalysis] = {}
        for case in cases:
            root_causes[case.case_id] = self._analyze_root_cause(
                case, issues_by_task.get(case.task_id), entry_by_task.get(case.task_id)
            )

        # Step 3: Degradation detection
        degradations: dict[str, DegradationInfo] = {}
        for case in cases:
            degradations[case.case_id] = self._detect_degradation(case, target_date)

        # Step 4: Generate recommendations
        recommendations: dict[str, list[Recommendation]] = {}
        for case in cases:
            recommendations[case.case_id] = self._generate_recommendations(
                case, root_causes.get(case.case_id), degradations.get(case.case_id)
            )

        return IssueCenterSnapshot(
            target_date=target_date,
            events=events,
            cases=cases,
            root_causes=root_causes,
            degradations=degradations,
            recommendations=recommendations,
        )

    def _analyze_root_cause(
        self,
        case: IssueCase,
        event: IssueEvent | None,
        entry: OrchestratorTaskLedgerEntry | None,
    ) -> RootCauseAnalysis:
        """Analyze root cause for an issue case."""
        evidence: list[str] = []
        upstream_tasks: list[str] = []

        # Check for dependency failures
        if event and event.dependency_refs:
            upstream_tasks = event.dependency_refs
            evidence.append(f"依赖任务失败: {', '.join(upstream_tasks)}")

        # Categorize by error message patterns
        message = (case.summary or "").lower()
        if "database" in message or "db" in message or "sqlite" in message:
            cause_category = "data"
            primary_cause = "数据库访问失败"
        elif "config" in message or "configuration" in message or "registry" in message:
            cause_category = "config"
            primary_cause = "配置缺失或错误"
        elif "not implemented" in message or "placeholder" in message or "todo" in message:
            cause_category = "implementation"
            primary_cause = "功能尚未实现"
        elif "file not found" in message or "path" in message or "directory" in message:
            cause_category = "environment"
            primary_cause = "文件系统或路径问题"
        elif "timeout" in message or "lock" in message:
            cause_category = "environment"
            primary_cause = "并发或资源锁定问题"
        elif upstream_tasks:
            cause_category = "dependency"
            primary_cause = "上游任务失败导致阻塞"
        else:
            cause_category = "implementation"
            primary_cause = "任务执行异常"

        evidence.append(f"任务状态: {case.status}")
        evidence.append(f"错误信息: {case.summary}")

        return RootCauseAnalysis(
            primary_cause=primary_cause,
            cause_category=cause_category,
            evidence=evidence,
            upstream_tasks=upstream_tasks,
        )

    def _detect_degradation(
        self,
        case: IssueCase,
        target_date: date,
    ) -> DegradationInfo:
        """Detect performance or success rate degradation."""
        # Load historical run data
        baseline = self._load_baseline(case.task_id, target_date)
        if baseline is None:
            return DegradationInfo(is_degradation=False)

        current_value = 0.0  # Failed/skipped = 0
        if case.status == "succeeded":
            current_value = 1.0

        baseline_value = baseline.get("success_rate", 0.5)
        change_pct = ((current_value - baseline_value) / baseline_value * 100) if baseline_value > 0 else 0

        # Degradation: success rate dropped by more than 30%
        is_degradation = current_value < baseline_value and abs(change_pct) > 30

        return DegradationInfo(
            is_degradation=is_degradation,
            baseline_date=baseline.get("date"),
            baseline_value=baseline_value,
            current_value=current_value,
            change_pct=change_pct,
            metric_name="success_rate",
        )

    def _load_baseline(
        self,
        task_id: str,
        target_date: date,
    ) -> dict[str, Any] | None:
        """Load historical baseline for degradation comparison."""
        # Look back up to 30 days
        for days_back in range(1, 30):
            baseline_date = target_date - timedelta(days=days_back)
            ledger_path = (
                self.project_root
                / "var/ledgers/bootstrap_runs"
                / baseline_date.isoformat()
                / "bootstrap_run_summary.json"
            )
            if not ledger_path.exists():
                continue

            try:
                data = json.loads(ledger_path.read_text(encoding="utf-8"))
                task_results = data.get("orchestration", {}).get("task_results", [])
                for tr in task_results:
                    if tr.get("task_id") == task_id:
                        status = tr.get("status", "")
                        success = 1.0 if status == "succeeded" else 0.0
                        return {
                            "date": baseline_date,
                            "success_rate": success,
                            "status": status,
                        }
            except (OSError, json.JSONDecodeError):
                continue

        return None

    def _generate_recommendations(
        self,
        case: IssueCase,
        root_cause: RootCauseAnalysis | None,
        degradation: DegradationInfo | None,
    ) -> list[Recommendation]:
        """Generate actionable recommendations."""
        recommendations: list[Recommendation] = []

        if root_cause is None:
            return recommendations

        # Category-specific recommendations
        if root_cause.cause_category == "dependency":
            recommendations.append(Recommendation(
                action="修复上游依赖任务",
                priority="high",
                rationale=f"当前任务被上游任务阻塞: {', '.join(root_cause.upstream_tasks[:3])}",
                expected_outcome="上游任务成功后，当前任务可正常执行",
            ))

        elif root_cause.cause_category == "data":
            recommendations.append(Recommendation(
                action="检查数据库连接和数据源状态",
                priority="high",
                rationale="数据库访问失败，可能是连接问题或数据缺失",
                expected_outcome="数据库恢复正常后重试",
            ))

        elif root_cause.cause_category == "config":
            recommendations.append(Recommendation(
                action="检查配置文件和注册表",
                priority="high",
                rationale="配置缺失或错误导致任务无法执行",
                expected_outcome="配置修复后重试",
            ))

        elif root_cause.cause_category == "implementation":
            if "not implemented" in case.summary.lower():
                recommendations.append(Recommendation(
                    action="跳过此任务或降低优先级",
                    priority="low",
                    rationale="功能尚未实现，不影响其他任务",
                    expected_outcome="等待后续版本实现",
                ))
            else:
                recommendations.append(Recommendation(
                    action="查看详细错误日志并修复代码",
                    priority="medium",
                    rationale="任务执行异常，需要代码层面的修复",
                    expected_outcome="修复后重试",
                ))

        elif root_cause.cause_category == "environment":
            recommendations.append(Recommendation(
                action="检查文件路径和权限",
                priority="medium",
                rationale="文件系统或路径问题导致任务失败",
                expected_outcome="路径修复后重试",
            ))

        # Degradation-specific recommendation
        if degradation and degradation.is_degradation:
            recommendations.append(Recommendation(
                action="调查性能退化原因",
                priority="high",
                rationale=f"成功率从 {degradation.baseline_value:.0%} 下降到 {degradation.current_value:.0%}",
                expected_outcome="恢复历史成功率水平",
            ))

        # Add generic retry recommendation for transient failures
        if case.status == "failed" and root_cause.cause_category in ("data", "environment"):
            recommendations.append(Recommendation(
                action="重试任务",
                priority="medium",
                rationale="可能是临时性问题，重试可能成功",
                expected_outcome="临时问题解决后任务成功",
                auto_fixable=True,
            ))

        return recommendations

    @staticmethod
    def _severity_for_status(status: RunStatus) -> IssueSeverity | None:
        if status == RunStatus.BLOCKED:
            return IssueSeverity.ERROR
        if status == RunStatus.SKIPPED:
            return IssueSeverity.WARNING
        if status == RunStatus.PENDING_IMPLEMENTATION:
            return IssueSeverity.INFO
        return None
