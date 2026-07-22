#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from neotrade3.chaos.registry import load_chaos_factor_registry
from neotrade3.chaos.store import ensure_chaos_schema


def _utc_ts() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def _safe_ts() -> str:
    return datetime.utcnow().strftime("%Y%m%d_%H%M%S")


def _backup_if_exists(path: Path) -> None:
    if path.is_file():
        path.rename(path.with_name(f"{path.name}.bak_{_safe_ts()}"))



def _a_share_universe_sql() -> str:
    return """
        length(s.code) = 6
        AND (s.is_delisted IS NULL OR s.is_delisted = 0)
        AND (
            s.code GLOB '60[0-9][0-9][0-9][0-9]'
            OR s.code GLOB '688[0-9][0-9][0-9]'
            OR s.code GLOB '300[0-9][0-9][0-9]'
            OR s.code GLOB '301[0-9][0-9][0-9]'
            OR s.code GLOB '00[0-9][0-9][0-9][0-9]'
        )
    """


def _infer_trade_date_bounds(stock_conn: sqlite3.Connection) -> tuple[str, str]:
    row = stock_conn.execute("SELECT MIN(trade_date), MAX(trade_date) FROM daily_prices").fetchone()
    if not row or not row[0] or not row[1]:
        raise RuntimeError("daily_prices is empty; cannot infer trade date bounds")
    return str(row[0]), str(row[1])


def _load_trade_dates(stock_conn: sqlite3.Connection, *, start_date: str, end_date: str) -> list[str]:
    rows = stock_conn.execute(
        """
        SELECT DISTINCT trade_date
        FROM daily_prices
        WHERE trade_date BETWEEN ? AND ?
        ORDER BY trade_date ASC
        """,
        (str(start_date), str(end_date)),
    ).fetchall()
    return [str(r[0]) for r in rows if r and r[0]]


def _load_all_a_share_codes(stock_conn: sqlite3.Connection) -> list[str]:
    rows = stock_conn.execute(
        f"""
        SELECT s.code
        FROM stocks s
        WHERE {_a_share_universe_sql()}
        ORDER BY s.code ASC
        """
    ).fetchall()
    return [str(r[0]) for r in rows if r and r[0]]


def _chunks(items: list[str], *, size: int) -> list[list[str]]:
    n = int(size)
    if n <= 0:
        raise ValueError("batch size must be > 0")
    out: list[list[str]] = []
    for i in range(0, len(items), n):
        out.append(list(items[i : i + n]))
    return out


def _count_snapshots_for_batch(
    chaos_conn: sqlite3.Connection,
    *,
    codes: list[str],
    start_date: str,
    end_date: str,
    thresholds_version: str,
    registry_version: str,
    weights_version: str,
) -> tuple[int, int, int]:
    if not codes:
        return 0, 0, 0
    placeholders = ",".join(["?"] * len(codes))
    rows = chaos_conn.execute(
        f"""
        SELECT chaos_status, COUNT(*)
        FROM chaos_daily_snapshot
        WHERE code IN ({placeholders})
          AND trade_date BETWEEN ? AND ?
          AND thresholds_version = ?
          AND registry_version = ?
          AND weights_version = ?
        GROUP BY chaos_status
        """,
        tuple(codes)
        + (
            str(start_date),
            str(end_date),
            str(thresholds_version),
            str(registry_version),
            str(weights_version),
        ),
    ).fetchall()
    ready_n = 0
    pending_n = 0
    other_n = 0
    for status, n in rows:
        s = str(status or "").strip().lower()
        if s == "ready":
            ready_n = int(n or 0)
        elif s == "pending":
            pending_n = int(n or 0)
        else:
            other_n += int(n or 0)
    return int(ready_n), int(pending_n), int(other_n)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _ensure_chaos_db_ready(db_path: Path) -> None:
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute("PRAGMA busy_timeout=60000")
        ensure_chaos_schema(conn)


def _count_snapshots_for_batch_db(
    db_path: Path,
    *,
    codes: list[str],
    start_date: str,
    end_date: str,
    thresholds_version: str,
    registry_version: str,
    weights_version: str,
) -> tuple[int, int, int]:
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute("PRAGMA busy_timeout=60000")
        ensure_chaos_schema(conn)
        return _count_snapshots_for_batch(
            conn,
            codes=codes,
            start_date=start_date,
            end_date=end_date,
            thresholds_version=thresholds_version,
            registry_version=registry_version,
            weights_version=weights_version,
        )


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--start-date", default="")
    p.add_argument("--end-date", default="")
    p.add_argument("--batch-size", type=int, default=200)
    p.add_argument("--start-batch", type=int, default=1)
    p.add_argument("--end-batch", type=int, default=0)
    p.add_argument("--resume", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--max-batches", type=int, default=0)

    p.add_argument("--chaos-db", required=True)
    p.add_argument("--registry-id", default="v1")
    p.add_argument("--weights-version", default="chaos_weights_v1_2")
    p.add_argument("--thresholds-version", default="chaos_thresholds_v0")
    p.add_argument("--regime-confirm-days", type=int, default=3)
    p.add_argument("--regime-deadzone-eps", type=float, default=0.15)
    p.add_argument("--fixed-window-days", type=int, default=45)
    args = p.parse_args()

    stock_db = PROJECT_ROOT / "var" / "db" / "stock_data.db"
    if not stock_db.is_file():
        raise SystemExit(f"stock db not found: {stock_db}")

    chaos_db = Path(str(args.chaos_db).strip())
    if not str(chaos_db):
        raise SystemExit("missing --chaos-db")
    chaos_db.parent.mkdir(parents=True, exist_ok=True)

    registry = load_chaos_factor_registry(project_root=PROJECT_ROOT, registry_id=str(args.registry_id))
    registry_version = str(registry.version)
    weights_version = str(args.weights_version).strip()
    thresholds_version = str(args.thresholds_version).strip()

    with sqlite3.connect(str(stock_db)) as stock_conn:
        inferred_start, inferred_end = _infer_trade_date_bounds(stock_conn)
        start_date = str(args.start_date).strip() or inferred_start
        end_date = str(args.end_date).strip() or inferred_end
        trade_dates = _load_trade_dates(stock_conn, start_date=str(start_date), end_date=str(end_date))
        codes = _load_all_a_share_codes(stock_conn)

    if not trade_dates:
        raise SystemExit("no trade_dates in range")
    if not codes:
        raise SystemExit("no A-share codes found")

    batches = _chunks(codes, size=int(args.batch_size))
    total_batches = int(len(batches))
    expected_days = int(len(trade_dates))

    run_dir = PROJECT_ROOT / "var" / "ledgers" / "chaos_daily_snapshot_backfill" / str(end_date)
    run_dir.mkdir(parents=True, exist_ok=True)

    _backup_if_exists(run_dir / "backfill_summary_running.json")
    _backup_if_exists(run_dir / "backfill_summary_ok.json")
    _backup_if_exists(run_dir / "backfill_summary_failed.json")

    summary = {
        "_meta": {"status": "running", "requested_by": "backfill_chaos_daily_snapshot_all_a_share", "started_at": _utc_ts()},
        "range": {"start_date": str(start_date), "end_date": str(end_date), "trade_date_count": int(expected_days)},
        "universe": {"codes": int(len(codes)), "batch_size": int(args.batch_size), "batches": int(total_batches)},
        "versions": {
            "registry_id": str(args.registry_id),
            "registry_version": str(registry_version),
            "weights_version": str(weights_version),
            "thresholds_version": str(thresholds_version),
        },
        "chaos_db": str(chaos_db),
        "batches": [],
    }
    _write_json(run_dir / "backfill_summary_running.json", summary)

    build_script = PROJECT_ROOT / "scripts" / "build_chaos_daily_snapshot.py"
    if not build_script.is_file():
        raise SystemExit(f"build script not found: {build_script}")

    _ensure_chaos_db_ready(chaos_db)
    start_batch = max(1, int(args.start_batch))
    end_batch = int(args.end_batch)
    max_batches = int(args.max_batches)
    if start_batch > total_batches:
        raise SystemExit(f"start_batch out of range: {start_batch} > {total_batches}")
    for idx, batch_codes in enumerate(batches, start=1):
        if int(idx) < int(start_batch):
            continue
        if end_batch > 0 and int(idx) > int(end_batch):
            break
        if max_batches > 0 and int(idx) > int(max_batches):
            break
        batch_id = f"{idx:04d}"
        codes_path = run_dir / f"codes_batch_{batch_id}.json"
        _write_json(codes_path, list(batch_codes))

        expected_rows = int(len(batch_codes)) * int(expected_days)
        ready_n, pending_n, other_n = _count_snapshots_for_batch_db(
            chaos_db,
            codes=batch_codes,
            start_date=str(start_date),
            end_date=str(end_date),
            thresholds_version=str(thresholds_version),
            registry_version=str(registry_version),
            weights_version=str(weights_version),
        )
        existing_rows = int(ready_n + pending_n + other_n)
        if bool(args.resume) and existing_rows >= expected_rows and expected_rows > 0:
            ledger_path = run_dir / f"batch_{batch_id}_ledger.json"
            if ledger_path.is_file():
                existing_payload = None
                try:
                    existing_payload = json.loads(ledger_path.read_text(encoding="utf-8"))
                except Exception:
                    existing_payload = None
                if isinstance(existing_payload, dict) and str(existing_payload.get("status") or "").strip().lower() == "ok":
                    summary["batches"].append({k: v for k, v in existing_payload.items() if k not in ("stdout",)})
                    _write_json(run_dir / "backfill_summary_running.json", summary)
                    continue
            batch_payload = {
                "batch_id": batch_id,
                "status": "skipped",
                "skip_reason": "already_complete",
                "expected_rows": int(expected_rows),
                "existing_rows": int(existing_rows),
                "existing_ready_rows": int(ready_n),
                "existing_pending_rows": int(pending_n),
                "existing_other_rows": int(other_n),
                "codes_file": str(codes_path),
                "written_at": _utc_ts(),
            }
            _write_json(run_dir / f"batch_{batch_id}_ledger.json", batch_payload)
            summary["batches"].append(batch_payload)
            _write_json(run_dir / "backfill_summary_running.json", summary)
            continue

        t0 = time.time()
        cmd = [
            sys.executable,
            str(build_script),
            "--start-date",
            str(start_date),
            "--end-date",
            str(end_date),
            "--codes-file",
            str(codes_path),
            "--registry-id",
            str(args.registry_id),
            "--weights-version",
            str(weights_version),
            "--thresholds-version",
            str(thresholds_version),
            "--regime-confirm-days",
            str(int(args.regime_confirm_days)),
            "--regime-deadzone-eps",
            str(float(args.regime_deadzone_eps)),
            "--fixed-window-days",
            str(int(args.fixed_window_days)),
            "--chaos-db",
            str(chaos_db),
        ]
        p = subprocess.run(cmd, cwd=str(PROJECT_ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        elapsed = round(time.time() - t0, 3)

        build_payload = None
        try:
            build_payload = json.loads(p.stdout.strip())
        except Exception:
            build_payload = None

        ready_n2, pending_n2, other_n2 = _count_snapshots_for_batch_db(
            chaos_db,
            codes=batch_codes,
            start_date=str(start_date),
            end_date=str(end_date),
            thresholds_version=str(thresholds_version),
            registry_version=str(registry_version),
            weights_version=str(weights_version),
        )
        existing_rows2 = int(ready_n2 + pending_n2 + other_n2)

        batch_payload = {
            "batch_id": batch_id,
            "status": "ok" if int(p.returncode) == 0 else "failed",
            "expected_rows": int(expected_rows),
            "existing_rows_before": int(existing_rows),
            "existing_rows_after": int(existing_rows2),
            "ready_rows_after": int(ready_n2),
            "pending_rows_after": int(pending_n2),
            "other_rows_after": int(other_n2),
            "codes_file": str(codes_path),
            "cmd": cmd,
            "exit_code": int(p.returncode),
            "elapsed_seconds": float(elapsed),
            "build_payload": build_payload,
            "stdout": p.stdout[-20000:],
            "written_at": _utc_ts(),
        }
        _write_json(run_dir / f"batch_{batch_id}_ledger.json", batch_payload)
        summary["batches"].append({k: v for k, v in batch_payload.items() if k not in ("stdout",)})
        _write_json(run_dir / "backfill_summary_running.json", summary)

        if int(p.returncode) != 0:
            summary["_meta"]["status"] = "failed"
            summary["_meta"]["finished_at"] = _utc_ts()
            _write_json(run_dir / "backfill_summary_failed.json", summary)
            raise SystemExit(int(p.returncode))

    summary["_meta"]["status"] = "ok"
    summary["_meta"]["finished_at"] = _utc_ts()
    _write_json(run_dir / "backfill_summary_ok.json", summary)
    print("ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
