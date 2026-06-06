"""Placeholder ledger models for the NeoTrade3 data-control bootstrap."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from .models import DataControlPlan, DataControlStage, DataControlStepResult


@dataclass
class DataControlLedgerEntry:
    """Single ledger entry derived from a bootstrap data-control plan or result."""

    ledger_entry_id: str
    target_date: str
    stage: str
    status: str
    source_refs: list[str]
    writes_to_official_store: bool
    created_at: str
    notes: str


class DataControlLedgerBuilder:
    """Builds placeholder capture/compose/publish ledger entries."""

    def build_plan_entries(
        self,
        plan: DataControlPlan,
        stage_sources: dict[DataControlStage, list[str]],
    ) -> list[DataControlLedgerEntry]:
        created_at = datetime.now(timezone.utc).isoformat()
        return [
            DataControlLedgerEntry(
                ledger_entry_id=str(uuid4()),
                target_date=plan.target_date.isoformat(),
                stage=step.stage.value,
                status="planned",
                source_refs=stage_sources.get(step.stage, []),
                writes_to_official_store=step.writes_to_official_store,
                created_at=created_at,
                notes=step.description,
            )
            for step in plan.steps
        ]

    def build_result_entry(
        self,
        target_date: str,
        result: DataControlStepResult,
        source_refs: list[str],
    ) -> DataControlLedgerEntry:
        return DataControlLedgerEntry(
            ledger_entry_id=str(uuid4()),
            target_date=target_date,
            stage=result.stage.value,
            status=result.status,
            source_refs=source_refs,
            writes_to_official_store=result.stage == DataControlStage.PUBLISH,
            created_at=datetime.now(timezone.utc).isoformat(),
            notes=result.message,
        )
