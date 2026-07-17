"""Backtest source helpers for lowfreq report-runner consumers."""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Optional

from apps.api.main import BootstrapApiService
from neotrade3.analysis.attribution_backtest_payload import (
    build_attribution_backtest_payload,
)


def load_lowfreq_report_backtest_payload(
    *,
    service: BootstrapApiService,
    backtest_json: Optional[Path],
    start_date: date,
    end_date: date,
    initial_capital: float,
    max_positions_override: Optional[int],
    execution_one_price_limit_only: bool,
    generated_at: str,
) -> dict[str, Any]:
    if backtest_json and backtest_json.exists():
        return json.loads(backtest_json.read_text(encoding="utf-8"))

    engine = service._lowfreq_engine_v16()
    if max_positions_override is not None:
        engine.MAX_POSITIONS = int(max_positions_override)
    if execution_one_price_limit_only:
        engine.EXEC_BLOCK_ONLY_ONE_PRICE_LIMIT = True
    start_key = start_date.isoformat()
    end_key = end_date.isoformat()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report_id = f"lowfreq_v16_{start_key}_{end_key}__{stamp}_{uuid.uuid4().hex[:8]}"
    metrics = engine.run_backtest(
        start_date=start_date,
        end_date=end_date,
        initial_capital=float(initial_capital),
        include_trades=True,
        project_root=service.project_root,
        run_id=report_id,
        source_run_id=report_id,
    )
    trades = metrics.get("trades", []) if isinstance(metrics, dict) else []
    summary = dict(metrics) if isinstance(metrics, dict) else {}
    summary.pop("trades", None)
    payload = build_attribution_backtest_payload(
        requested_by="script",
        generated_at=str(generated_at or ""),
        summary=summary,
        trades=trades,
    )
    meta = payload.get("_meta")
    if not isinstance(meta, dict):
        raise RuntimeError("build_attribution_backtest_payload returned invalid _meta")
    meta["report_id"] = report_id
    return payload
