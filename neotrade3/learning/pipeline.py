"""Learning bootstrap pipeline for NeoTrade3."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from neotrade3.issue_center import IssueCenterSnapshot
from neotrade3.orchestration import RunStatus, TaskResult

from .models import (
    AdjustmentCandidate,
    AuditRecord,
    EvaluationDecision,
    LearningCycleSnapshot,
    LearningInputSnapshot,
    MetricSnapshot,
)


class LearningLoopPipeline:
    """Builds placeholder learning-loop outputs from daily bootstrap signals."""

    def build_snapshot(
        self,
        target_date: date,
        task_results: list[TaskResult],
        issue_snapshot: IssueCenterSnapshot,
        project_root: Path | None = None,
    ) -> LearningCycleSnapshot:
        labs_seen = sorted({result.lab_id for result in task_results if result.lab_id})
        market_context = (
            self._load_market_context(project_root, target_date)
            if project_root is not None
            else {}
        )

        inputs = LearningInputSnapshot(
            target_date=target_date,
            task_result_count=len(task_results),
            issue_event_count=len(issue_snapshot.events),
            issue_case_count=len(issue_snapshot.cases),
            labs_seen=labs_seen,
            market_context=market_context,
        )

        metrics = MetricSnapshot(
            target_date=target_date,
            total_tasks=len(task_results),
            blocked_tasks=sum(
                1 for item in task_results if item.status == RunStatus.BLOCKED
            ),
            skipped_tasks=sum(
                1 for item in task_results if item.status == RunStatus.SKIPPED
            ),
            pending_tasks=sum(
                1
                for item in task_results
                if item.status == RunStatus.PENDING_IMPLEMENTATION
            ),
            issue_events=len(issue_snapshot.events),
            issue_cases=len(issue_snapshot.cases),
        )

        candidates = self._build_candidates(
            target_date=target_date,
            task_results=task_results,
            issue_snapshot=issue_snapshot,
            market_context=market_context,
        )
        audit_records = self._build_audit_records(target_date, metrics, candidates)

        return LearningCycleSnapshot(
            inputs=inputs,
            metrics=metrics,
            adjustment_candidates=candidates,
            audit_records=audit_records,
        )

    def _build_candidates(
        self,
        target_date: date,
        task_results: list[TaskResult],
        issue_snapshot: IssueCenterSnapshot,
        market_context: dict[str, object],
    ) -> list[AdjustmentCandidate]:
        candidates: list[AdjustmentCandidate] = []

        if any(item.status == RunStatus.BLOCKED for item in task_results):
            candidates.append(
                AdjustmentCandidate(
                    candidate_id=f"candidate:blocked:{target_date.isoformat()}",
                    target_date=target_date,
                    scope="daily_orchestration",
                    decision=EvaluationDecision.REVIEW_REQUIRED,
                    reason="At least one daily task is blocked before execution.",
                    recommended_action="Review publish gating and dependency declarations.",
                )
            )

        if issue_snapshot.cases:
            candidates.append(
                AdjustmentCandidate(
                    candidate_id=f"candidate:issues:{target_date.isoformat()}",
                    target_date=target_date,
                    scope="issue_center",
                    decision=EvaluationDecision.REVIEW_REQUIRED,
                    reason="Issue cases were generated from bootstrap orchestration signals.",
                    recommended_action="Review issue cases and define follow-up ownership.",
                )
            )

        phase = market_context.get("market_phase")
        if isinstance(phase, dict):
            phase_code = str(phase.get("code", "")).strip()
            if phase_code == "unknown":
                candidates.append(
                    AdjustmentCandidate(
                        candidate_id=f"candidate:market_phase:{target_date.isoformat()}",
                        target_date=target_date,
                        scope="market_phase",
                        decision=EvaluationDecision.REVIEW_REQUIRED,
                        reason="Market phase is unknown in current factor-matrix context.",
                        recommended_action="Provide phase labels (manual feedback) or implement phase detector and calibration.",
                    )
                )

        if not candidates:
            candidates.append(
                AdjustmentCandidate(
                    candidate_id=f"candidate:stable:{target_date.isoformat()}",
                    target_date=target_date,
                    scope="learning_loop",
                    decision=EvaluationDecision.STABLE,
                    reason="No blocking or issue signals were detected in the bootstrap inputs.",
                    recommended_action="Keep the current bootstrap configuration unchanged.",
                )
            )

        return candidates

    @staticmethod
    def _load_market_context(
        project_root: Path, target_date: date
    ) -> dict[str, object]:
        date_key = target_date.isoformat()
        artifact_path = (
            project_root
            / "var/artifacts/factor_matrix"
            / date_key
            / "factor_matrix_daily.json"
        )
        if not artifact_path.exists():
            return {}
        try:
            payload = json.loads(artifact_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        if not isinstance(payload, dict):
            return {}
        market_context = payload.get("market_context")
        if not isinstance(market_context, dict):
            return {}
        phase = market_context.get("market_phase")
        focus_themes = market_context.get("focus_themes")
        result: dict[str, object] = {"source": "factor_matrix_daily_artifact"}
        if isinstance(phase, dict):
            result["market_phase"] = {
                "code": str(phase.get("code", "")),
                "display": str(phase.get("display", "")),
            }
        if isinstance(focus_themes, list):
            result["focus_themes"] = [str(item) for item in focus_themes]
        return result

    @staticmethod
    def _build_audit_records(
        target_date: date,
        metrics: MetricSnapshot,
        candidates: list[AdjustmentCandidate],
    ) -> list[AuditRecord]:
        return [
            AuditRecord(
                audit_id=f"audit:{candidate.candidate_id}",
                target_date=target_date,
                decision=candidate.decision,
                summary=(
                    f"metrics(total={metrics.total_tasks}, blocked={metrics.blocked_tasks}, "
                    f"issues={metrics.issue_cases}); action={candidate.recommended_action}"
                ),
            )
            for candidate in candidates
        ]
