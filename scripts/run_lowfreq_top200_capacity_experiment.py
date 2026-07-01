#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from lowfreq_engine_v16_advanced import LowFreqTradingEngineV16


def _build_payload_path(*, start_date: str, end_date: str, report_id: str) -> Path:
    return (
        PROJECT_ROOT
        / "var"
        / "artifacts"
        / "lowfreq_backtest"
        / f"lowfreq_v16_capture_first_{start_date}_{end_date}_{report_id}_payload.json"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run isolated lowfreq Top200 capacity experiment.")
    parser.add_argument("--start-date", type=str, default="2024-12-18")
    parser.add_argument("--end-date", type=str, default="2025-12-31")
    parser.add_argument("--year", type=int, default=2025)
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--report-id", type=str, default="")
    parser.add_argument("--initial-capital", type=float, default=50_000_000.0)
    parser.add_argument("--max-positions", type=int, default=8)
    args = parser.parse_args()

    report_id = str(
        args.report_id
        or f"capture_first_top200_capacity_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    )
    payload_path = _build_payload_path(
        start_date=str(args.start_date),
        end_date=str(args.end_date),
        report_id=report_id,
    )
    payload_path.parent.mkdir(parents=True, exist_ok=True)

    engine = LowFreqTradingEngineV16()
    engine.MAX_POSITIONS = int(args.max_positions)
    engine.EXEC_BLOCK_ONLY_ONE_PRICE_LIMIT = True
    result = engine.run_backtest(
        date.fromisoformat(str(args.start_date)),
        date.fromisoformat(str(args.end_date)),
        initial_capital=float(args.initial_capital),
        include_trades=True,
    )
    trades = result.get("trades", []) if isinstance(result, dict) else []
    summary = dict(result) if isinstance(result, dict) else {}
    summary.pop("trades", None)
    payload = {
        "_meta": {
            "status": "ok",
            "requested_by": "capacity_experiment_script",
            "model": "lowfreq_engine_v16_advanced",
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "start_date": str(args.start_date),
            "end_date": str(args.end_date),
            "experiment": {
                "initial_capital": float(args.initial_capital),
                "max_positions": int(args.max_positions),
                "execution_one_price_limit_only": True,
            },
        },
        "summary": summary,
        "trade_blocks": summary.get("trade_blocks", {}) if isinstance(summary, dict) else {},
        "config_snapshot": summary.get("config_snapshot", {}) if isinstance(summary, dict) else {},
        "coverage_gaps": summary.get("coverage_gaps", {}) if isinstance(summary, dict) else {},
        "trades": trades,
    }
    payload_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report_cmd = [
        sys.executable,
        str(PROJECT_ROOT / "scripts" / "generate_lowfreq_top200_attribution_report.py"),
        "--year",
        str(int(args.year)),
        "--limit",
        str(int(args.limit)),
        "--backtest-json",
        str(payload_path),
        "--backtest-start",
        str(args.start_date),
        "--backtest-end",
        str(args.end_date),
        "--max-positions-override",
        str(int(args.max_positions)),
        "--execution-one-price-limit-only",
        "--report-id",
        report_id,
    ]
    proc = subprocess.run(report_cmd, cwd=str(PROJECT_ROOT), capture_output=True, text=True)
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr)
        return int(proc.returncode)

    report_output = json.loads(proc.stdout)
    print(
        json.dumps(
            {
                "status": "ok",
                "report_id": report_id,
                "payload_path": str(payload_path),
                "attribution_output": report_output,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
