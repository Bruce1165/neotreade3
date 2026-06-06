"""Minimal read-only API entrypoint for NeoTrade3 bootstrap."""

from __future__ import annotations

import argparse
import functools
from copy import deepcopy
import csv
from dataclasses import dataclass
import importlib
import io
import json
import logging
import multiprocessing
import os
import shutil
import sqlite3
import statistics
from datetime import date, datetime, timedelta, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re
import threading
import time
from typing import Any, Optional, Union
import urllib.request
import uuid
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo

from neotrade3.config_contracts import build_config_contract_report
from neotrade3.migration import (
    build_feature_inventory_payload,
    build_feature_mapping_coverage_payload,
    build_feature_mapping_payload,
)
from apps.worker.main import BootstrapWorkerApp
from neotrade3.data_control import SourceRegistry
from neotrade3.data_control.pipeline import DataControlPipeline
from neotrade3.labs import LabRegistry
from neotrade3.orchestration import load_orchestrator_config
from neotrade3.orchestration.daily_master_orchestrator import DailyMasterOrchestrator
from neotrade3.orchestration.models import DailyRunRequest
from neotrade3.screeners.registry import load_screener_registry
from neotrade3.screeners.storage import (
    list_bulk_runs,
    list_screener_runs,
    read_bulk_run_artifact,
    read_bulk_run_ledger,
    read_screener_run_artifact,
    read_screener_run_ledger,
    read_screener_config,
    write_screener_config,
    write_screener_run,
)
# New analysis modules
from neotrade3.analysis.market_phase import detect_market_phase
from neotrade3.analysis.resonance_scorer import ResonanceScorer
from neotrade3.analysis.sector_rotation import SectorRotationAnalyzer
from neotrade3.analysis.stock_tiering import StockTieringAnalyzer, StockTier
from neotrade3.analysis.signal_generator import SignalGenerator, SignalGrade
from neotrade3.analysis.backtest import SignalBacktester
from neotrade3.learning.evolution_report import EvolutionReportGenerator

from apps.api.router import BootstrapApiRouter
from apps.api.shared import ApiBinaryResponse, ApiError, _safe_ref_path, format_api_error

logger = logging.getLogger(__name__)


def _load_env_file() -> None:
    raw_path = os.environ.get("NEOTRADE3_ENV_FILE")
    if not (isinstance(raw_path, str) and raw_path.strip()):
        raw_path = str(Path.home() / "Library/Application Support/NeoTrade3/env.secrets")
    env_path = Path(str(raw_path or "")).expanduser() if raw_path else None
    if env_path is None or not env_path.exists() or not env_path.is_file():
        return
    try:
        text = env_path.read_text(encoding="utf-8")
    except OSError:
        return
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        key = k.strip()
        val = v.strip().strip('"').strip("'")
        if not key:
            continue
        os.environ[key] = val


_load_env_file()


@dataclass
class ApiCacheEntry:
    """Minimal in-memory cache entry for bootstrap API payloads."""

    payload: Any
    expires_at: float


class BootstrapApiService:
    """Read-only facade that exposes bootstrap snapshots as API payloads."""

    def __init__(self, project_root: Union[str, Path], *, api_key: Optional[str] = None) -> None:
        BootstrapApiService._load_env_file()
        self.project_root = Path(project_root)
        self.api_key = api_key.strip() if api_key and api_key.strip() else None
        self.worker_app = BootstrapWorkerApp(project_root=self.project_root)
        self._labs_config = self.project_root / "config/labs/labs_registry.json"
        self._source_registry_config = (
            self.project_root / "config/data_control/source_registry.json"
        )
        self._screeners_registry_config = (
            self.project_root / "config/screeners/screeners_registry.json"
        )
        self._screeners_config_dir = self.project_root / "config/screeners"
        self._trading_calendar_ledger_file = (
            self.project_root / "var/ledgers/trading_calendar/trading_calendar.json"
        )
        self._stock_db_default_path = self.project_root / "var/db/stock_data.db"
        self._stock_db_v2_snapshot_path = self.project_root / "var/imports/stock_data_v2.db"
        self._lowfreq_sim_state_file = (
            self.project_root / "var/ledgers/lowfreq_sim/state.json"
        )
        self._lowfreq_sim_overrides_file = (
            self.project_root / "var/ledgers/lowfreq_sim/overrides.json"
        )
        self._lowfreq_backtest_artifacts_dir = (
            self.project_root / "var/artifacts/lowfreq_backtest"
        )
        self._daily_runs_dir = self.project_root / "var/ledgers/daily_runs"
        self._themes_snapshot_dir = self.project_root / "var/ledgers/team_themes"
        self._tushare_status_file = self._themes_snapshot_dir / "_tushare_status.json"
        self._auto_opt_dir = self.project_root / "var/ledgers/auto_optimization"
        self._feature_inventory_file = (
            self.project_root / "docs/migration/neotrade2_feature_inventory.v3.json"
        )
        self._strategy_and_lab_mapping_file = (
            self.project_root
            / "docs/migration/mappings/neotrade3_feature_mapping_strategy_and_lab_v1.json"
        )
        self._assistant_mapping_file = (
            self.project_root
            / "docs/migration/mappings/neotrade3_feature_mapping_assistant_v1.json"
        )
        self._operations_mapping_file = (
            self.project_root
            / "docs/migration/mappings/neotrade3_feature_mapping_operations_v1.json"
        )
        self._screeners_mapping_file = (
            self.project_root
            / "docs/migration/mappings/neotrade3_feature_mapping_screeners_v1.json"
        )
        self._cache: dict[tuple[str, ...], ApiCacheEntry] = {}
        self._cache_lock = threading.RLock()
        self._cache_ttl_seconds = {
            "snapshot": 15.0,
            "source_registry": 300.0,
            "labs_registry": 300.0,
        }

    @staticmethod
    def _stock_db_v2_path() -> Optional[Path]:
        BootstrapApiService._load_env_file()
        raw = os.environ.get("NEOTRADE3_STOCK_DB_V2_PATH")
        if isinstance(raw, str) and raw.strip():
            return Path(raw.strip()).expanduser()
        return None

    @staticmethod
    def _load_env_file() -> None:
        raw_path = os.environ.get("NEOTRADE3_ENV_FILE")
        if not (isinstance(raw_path, str) and raw_path.strip()):
            raw_path = str(Path.home() / "Library/Application Support/NeoTrade3/env.secrets")
        env_path = Path(str(raw_path)).expanduser()
        if not env_path.exists() or not env_path.is_file():
            return
        try:
            text = env_path.read_text(encoding="utf-8")
        except OSError:
            return
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[len("export ") :].strip()
            if "=" not in line:
                continue
            k, v = line.split("=", 1)
            key = k.strip()
            val = v.strip().strip('"').strip("'")
            if not key:
                continue
            os.environ[key] = val

    @staticmethod
    def _now_cn() -> datetime:
        return datetime.now(ZoneInfo("Asia/Shanghai"))

    @classmethod
    def _is_market_closed_cn(cls, *, target_trade_date: str) -> bool:
        now = cls._now_cn()
        today = now.date().isoformat()
        if str(target_trade_date) != str(today):
            return True
        return now.time() >= datetime.strptime("15:10:00", "%H:%M:%S").time()

    def _backfill_daily_prices_from_tushare_daily(
        self,
        *,
        conn: sqlite3.Connection,
        v3_db_path: Path,
        target_date: str,
        requested_by: str,
        reason: str,
        tencent_trade_date: Optional[str],
    ) -> dict[str, Any]:
        self._load_env_file()
        raw_token = str(os.environ.get("TUSHARE_TOKEN") or "").strip()
        if not raw_token:
            return {
                "status": "skipped",
                "reason": "tushare_token_not_configured",
                "env_var": "TUSHARE_TOKEN",
            }
        try:
            import tushare as ts
        except Exception:
            return {"status": "skipped", "reason": "tushare_not_installed"}

        try:
            trade_date = date.fromisoformat(target_date).strftime("%Y%m%d")
        except Exception:
            return {"status": "skipped", "reason": "invalid_target_date", "target_date": target_date}

        try:
            pro = ts.pro_api(raw_token)
            df = pro.daily(
                trade_date=trade_date,
                fields="ts_code,open,high,low,close,vol,amount,pre_close,pct_chg",
            )
        except Exception as exc:
            return {"status": "skipped", "reason": "tushare_daily_failed", "error": str(exc)}

        try:
            records = df.to_dict("records") if hasattr(df, "to_dict") else []
        except Exception:
            records = []
        if not records:
            return {
                "status": "skipped",
                "reason": "tushare_has_no_rows_for_target_date",
                "target_date": target_date,
            }

        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(1) FROM daily_prices WHERE trade_date = ?", (target_date,))
        before = int(cursor.fetchone()[0] or 0)

        active_codes: set[str] = set()
        try:
            for row in conn.execute(
                "SELECT code FROM stocks WHERE COALESCE(is_delisted, 0) = 0 AND asset_type = 'stock'"
            ).fetchall():
                active_codes.add(str(row[0]))
        except Exception:
            active_codes = set()

        baseline_prev_date: Optional[str] = None
        baseline_codes: set[str] = set()
        try:
            row = conn.execute(
                "SELECT MAX(trade_date) FROM trading_calendar_cache WHERE trade_date < ?",
                (target_date,),
            ).fetchone()
            baseline_prev_date = str(row[0]) if row and row[0] else None
        except Exception:
            baseline_prev_date = None
        if baseline_prev_date:
            try:
                baseline_codes = {
                    str(r[0])
                    for r in conn.execute(
                        "SELECT code FROM daily_prices WHERE trade_date = ?",
                        (baseline_prev_date,),
                    ).fetchall()
                    if r and r[0]
                }
            except Exception:
                baseline_codes = set()

        updated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        payload_rows: list[tuple[object, ...]] = []
        inserted_codes: set[str] = set()
        for r in records:
            if not isinstance(r, dict):
                continue
            ts_code = str(r.get("ts_code") or "").strip()
            code = ts_code.split(".", 1)[0].strip() if ts_code else ""
            if not code or (active_codes and code not in active_codes):
                continue

            open_px = r.get("open")
            high = r.get("high")
            low = r.get("low")
            close = r.get("close")
            vol = r.get("vol")
            amount = r.get("amount")
            preclose = r.get("pre_close")
            pct_chg = r.get("pct_chg")

            volume_out = float(vol) * 100.0 if isinstance(vol, (int, float)) else None
            amount_out = float(amount) * 1000.0 if isinstance(amount, (int, float)) else None

            payload_rows.append(
                (
                    code,
                    target_date,
                    float(open_px) if isinstance(open_px, (int, float)) else None,
                    float(high) if isinstance(high, (int, float)) else None,
                    float(low) if isinstance(low, (int, float)) else None,
                    float(close) if isinstance(close, (int, float)) else None,
                    volume_out,
                    amount_out,
                    None,
                    float(preclose) if isinstance(preclose, (int, float)) else None,
                    float(pct_chg) if isinstance(pct_chg, (int, float)) else None,
                    updated_at,
                )
            )
            inserted_codes.add(code)

        synthesized_suspended_codes: list[str] = []
        if baseline_codes:
            missing_codes = sorted(baseline_codes - inserted_codes)
            if missing_codes:
                suspended_ts_codes: set[str] = set()
                try:
                    suspend_df = pro.suspend_d(trade_date=trade_date, fields="ts_code,suspend_type")
                    if hasattr(suspend_df, "__getitem__") and "ts_code" in suspend_df:
                        suspended_ts_codes = {str(x) for x in list(suspend_df["ts_code"]) if x}
                except Exception:
                    suspended_ts_codes = set()

                for code in missing_codes:
                    ts_code = f"{code}.SH" if str(code).startswith("6") else f"{code}.SZ"
                    if suspended_ts_codes and ts_code not in suspended_ts_codes:
                        continue
                    if not baseline_prev_date:
                        continue
                    row = conn.execute(
                        "SELECT close FROM daily_prices WHERE trade_date = ? AND code = ?",
                        (baseline_prev_date, code),
                    ).fetchone()
                    prev_close = float(row[0]) if row and row[0] is not None else None
                    if prev_close is None or prev_close <= 0:
                        continue
                    payload_rows.append(
                        (
                            code,
                            target_date,
                            prev_close,
                            prev_close,
                            prev_close,
                            prev_close,
                            0.0,
                            0.0,
                            None,
                            prev_close,
                            0.0,
                            updated_at,
                        )
                    )
                    synthesized_suspended_codes.append(code)

        if not payload_rows:
            return {"status": "skipped", "reason": "tushare_rows_filtered_out", "target_date": target_date}

        conn.executemany(
            """
            INSERT INTO daily_prices (
                code,
                trade_date,
                open,
                high,
                low,
                close,
                volume,
                amount,
                turnover,
                preclose,
                pct_change,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(code, trade_date) DO UPDATE SET
                open=excluded.open,
                high=excluded.high,
                low=excluded.low,
                close=excluded.close,
                volume=excluded.volume,
                amount=excluded.amount,
                turnover=excluded.turnover,
                preclose=excluded.preclose,
                pct_change=excluded.pct_change,
                updated_at=excluded.updated_at
            """,
            payload_rows,
        )
        conn.commit()

        cursor.execute("SELECT COUNT(1) FROM daily_prices WHERE trade_date = ?", (target_date,))
        after = int(cursor.fetchone()[0] or 0)

        volume_normalized_rows = int(
            self._normalize_daily_prices_volume_to_shares(db_path=v3_db_path, trade_date=target_date)
        )

        requested = int(len(payload_rows))
        close_ok = sum(1 for x in payload_rows if x[5] is not None)
        open_ok = sum(1 for x in payload_rows if x[2] is not None)
        amount_ok = sum(1 for x in payload_rows if x[7] is not None)
        coverage = {
            "close": close_ok / max(1, requested),
            "open": open_ok / max(1, requested),
            "amount": amount_ok / max(1, requested),
            "turnover": 0.0,
        }

        calendar_source, calendar_is_trading_day = self._calendar_membership(conn, target_date)
        publish_batch_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        if not conn.in_transaction:
            conn.execute(
                """
                INSERT INTO daily_price_publish_batches (
                    batch_id,
                    source,
                    target_date,
                    trade_date,
                    publish_status,
                    quality_gate_passed,
                    quality_gate_reason,
                    warning_reason,
                    calendar_source,
                    calendar_is_trading_day,
                    requested,
                    quotes_parsed,
                    db_upserted,
                    missing_codes_count,
                    coverage_close,
                    coverage_open,
                    coverage_amount,
                    coverage_turnover,
                    published_close,
                    published_amount,
                    published_turnover,
                    published_total_rows,
                    gate_reasons_json,
                    warning_reasons_json,
                    metadata_json,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    publish_batch_id,
                    "tushare_daily",
                    target_date,
                    target_date,
                    "ok",
                    1,
                    "",
                    "",
                    calendar_source,
                    None if calendar_is_trading_day is None else int(bool(calendar_is_trading_day)),
                    requested,
                    requested,
                    requested,
                    0,
                    float(coverage["close"]),
                    float(coverage["open"]),
                    float(coverage["amount"]),
                    float(coverage["turnover"]),
                    float(coverage["close"]),
                    float(coverage["amount"]),
                    float(coverage["turnover"]),
                    requested,
                    json.dumps([], ensure_ascii=False),
                    json.dumps([], ensure_ascii=False),
                    json.dumps(
                        {
                            "db_path": str(v3_db_path),
                            "requested_by": requested_by,
                            "reason": reason,
                            "tencent_trade_date": tencent_trade_date,
                        },
                        ensure_ascii=False,
                    ),
                    now,
                ),
            )
            conn.commit()

        return {
            "status": "ok",
            "source": "tushare_daily",
            "target_date": target_date,
            "before_rows": before,
            "after_rows": after,
            "db_upserted": requested,
            "coverage": coverage,
            "volume_normalized_rows": volume_normalized_rows,
            "synthesized_suspended_count": int(len(synthesized_suspended_codes)),
            "synthesized_suspended_codes": synthesized_suspended_codes,
        }

    def _backfill_daily_prices_from_v2(
        self,
        *,
        conn: sqlite3.Connection,
        v3_db_path: Path,
        target_date: str,
        requested_by: str,
        reason: str,
        tencent_trade_date: Optional[str],
    ) -> dict[str, Any]:
        v2_db_path = self._stock_db_v2_path()
        if v2_db_path is None:
            return {
                "status": "skipped",
                "reason": "v2_db_path_not_configured",
                "env_var": "NEOTRADE3_STOCK_DB_V2_PATH",
                "snapshot_path": _safe_ref_path(str(self._stock_db_v2_snapshot_path)),
            }
        if not v2_db_path.exists() or not v2_db_path.is_file():
            return {
                "status": "skipped",
                "reason": "v2_db_missing",
                "v2_db_path": _safe_ref_path(str(v2_db_path)),
                "env_var": "NEOTRADE3_STOCK_DB_V2_PATH",
                "snapshot_path": _safe_ref_path(str(self._stock_db_v2_snapshot_path)),
            }

        try:
            v2_conn = sqlite3.connect(str(v2_db_path))
            v2_conn.row_factory = sqlite3.Row
        except Exception:
            return {
                "status": "skipped",
                "reason": "v2_db_unavailable",
                "v2_db_path": _safe_ref_path(str(v2_db_path)),
            }

        rows: list[sqlite3.Row] = []
        try:
            rows = v2_conn.execute(
                """
                SELECT
                    code,
                    trade_date,
                    open,
                    high,
                    low,
                    close,
                    volume,
                    amount,
                    turnover,
                    preclose,
                    pct_change,
                    updated_at
                FROM daily_prices
                WHERE trade_date = ?
                ORDER BY code ASC
                """,
                (target_date,),
            ).fetchall()
        except sqlite3.Error:
            return {
                "status": "skipped",
                "reason": "v2_query_failed",
                "v2_db_path": _safe_ref_path(str(v2_db_path)),
            }
        finally:
            try:
                v2_conn.close()
            except Exception:
                pass

        if not rows:
            return {
                "status": "skipped",
                "reason": "v2_has_no_rows_for_target_date",
                "target_date": target_date,
                "v2_db_path": _safe_ref_path(str(v2_db_path)),
            }

        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(1) FROM daily_prices WHERE trade_date = ?", (target_date,))
        before = int(cursor.fetchone()[0] or 0)

        payload_rows: list[tuple[object, ...]] = []
        for r in rows:
            payload_rows.append(
                (
                    r["code"],
                    r["trade_date"],
                    r["open"],
                    r["high"],
                    r["low"],
                    r["close"],
                    r["volume"],
                    r["amount"],
                    r["turnover"],
                    r["preclose"],
                    r["pct_change"],
                    r["updated_at"],
                )
            )

        conn.executemany(
            """
            INSERT INTO daily_prices (
                code,
                trade_date,
                open,
                high,
                low,
                close,
                volume,
                amount,
                turnover,
                preclose,
                pct_change,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(code, trade_date) DO UPDATE SET
                open=excluded.open,
                high=excluded.high,
                low=excluded.low,
                close=excluded.close,
                volume=excluded.volume,
                amount=excluded.amount,
                turnover=excluded.turnover,
                preclose=excluded.preclose,
                pct_change=excluded.pct_change,
                updated_at=excluded.updated_at
            """,
            payload_rows,
        )
        conn.commit()

        cursor.execute("SELECT COUNT(1) FROM daily_prices WHERE trade_date = ?", (target_date,))
        after = int(cursor.fetchone()[0] or 0)

        volume_normalized_rows = int(
            self._normalize_daily_prices_volume_to_shares(db_path=v3_db_path, trade_date=target_date)
        )

        requested = int(len(payload_rows))
        close_ok = sum(1 for r in rows if r["close"] is not None)
        open_ok = sum(1 for r in rows if r["open"] is not None)
        amount_ok = sum(1 for r in rows if r["amount"] is not None)
        turnover_ok = sum(1 for r in rows if r["turnover"] is not None)
        coverage = {
            "close": close_ok / max(1, requested),
            "open": open_ok / max(1, requested),
            "amount": amount_ok / max(1, requested),
            "turnover": turnover_ok / max(1, requested),
        }

        calendar_source, calendar_is_trading_day = self._calendar_membership(conn, target_date)
        publish_batch_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        if not conn.in_transaction:
            conn.execute(
                """
                INSERT INTO daily_price_publish_batches (
                    batch_id,
                    source,
                    target_date,
                    trade_date,
                    publish_status,
                    quality_gate_passed,
                    quality_gate_reason,
                    warning_reason,
                    calendar_source,
                    calendar_is_trading_day,
                    requested,
                    quotes_parsed,
                    db_upserted,
                    missing_codes_count,
                    coverage_close,
                    coverage_open,
                    coverage_amount,
                    coverage_turnover,
                    published_close,
                    published_amount,
                    published_turnover,
                    published_total_rows,
                    gate_reasons_json,
                    warning_reasons_json,
                    metadata_json,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    publish_batch_id,
                    "v2",
                    target_date,
                    target_date,
                    "ok",
                    1,
                    "",
                    "",
                    calendar_source,
                    None if calendar_is_trading_day is None else int(bool(calendar_is_trading_day)),
                    requested,
                    requested,
                    requested,
                    0,
                    float(coverage["close"]),
                    float(coverage["open"]),
                    float(coverage["amount"]),
                    float(coverage["turnover"]),
                    float(coverage["close"]),
                    float(coverage["amount"]),
                    float(coverage["turnover"]),
                    after,
                    json.dumps([], ensure_ascii=False),
                    json.dumps([], ensure_ascii=False),
                    json.dumps(
                        {
                            "v3_db_path": str(v3_db_path),
                            "v2_db_path": str(v2_db_path),
                            "requested_by": requested_by,
                            "reason": reason,
                            "tencent_trade_date": tencent_trade_date,
                        },
                        ensure_ascii=False,
                    ),
                    now,
                ),
            )
            conn.commit()

        return {
            "status": "ok",
            "source": "v2",
            "target_date": target_date,
            "requested": requested,
            "db_rows_before": before,
            "db_rows_after": after,
            "volume_normalized_rows": volume_normalized_rows,
            "publish_batch_id": publish_batch_id,
            "coverage": coverage,
            "v2_db_path": _safe_ref_path(str(v2_db_path)),
        }

    def health(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "service": "neotrade3-bootstrap-api",
        }

    def infer_publish_succeeded(self, *, target_date: date) -> bool:
        date_key = target_date.isoformat()
        ledger_path = (
            self.project_root
            / "var/ledgers/data_control"
            / date_key
            / "data_control_publish_ledger.json"
        )
        if not ledger_path.exists():
            return False
        try:
            payload = json.loads(ledger_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False
        if not isinstance(payload, dict):
            return False
        return str(payload.get("status", "")) == "ok"

    def build_snapshot(
        self,
        target_date: date,
        publish_succeeded: bool = False,
        write_outputs: bool = False,
    ) -> dict[str, Any]:
        cache_key = ("snapshot", target_date.isoformat(), str(bool(publish_succeeded)))

        if write_outputs:
            self.worker_app.run(
                target_date=target_date,
                publish_succeeded=publish_succeeded,
                write_outputs=True,
            )
            snapshot = self.load_stored_snapshot(target_date)
            snapshot["_meta"] = {"cache_status": "bypass", "self_heal": "generated"}
            return snapshot

        with self._cache_lock:
            cached_snapshot = self._cache_get(cache_key)
            if cached_snapshot is not None:
                cached_snapshot["_meta"] = {
                    "cache_status": "hit",
                    "self_heal": "none",
                }
                return cached_snapshot

            self_heal = "none"
            try:
                snapshot = self.load_stored_snapshot(target_date)
            except ApiError as exc:
                if getattr(exc, "code", None) != "snapshot_not_found":
                    raise
                self.worker_app.run(
                    target_date=target_date,
                    publish_succeeded=publish_succeeded,
                    write_outputs=True,
                )
                snapshot = self.load_stored_snapshot(target_date)
                self_heal = "generated"

            snapshot["_meta"] = {"cache_status": "miss", "self_heal": self_heal}
            self._cache_set(cache_key, snapshot, self._cache_ttl_seconds["snapshot"])
        return snapshot

    def bootstrap_summary(
        self,
        target_date: date,
        publish_succeeded: bool = False,
    ) -> dict[str, Any]:
        snapshot = self.build_snapshot(
            target_date=target_date,
            publish_succeeded=publish_succeeded,
            write_outputs=False,
        )
        return {
            "target_date": snapshot["target_date"],
            "publish_succeeded": snapshot.get("publish_succeeded"),
            "_meta": snapshot.get("_meta", {}),
            "summary": snapshot["summary"],
        }

    def data_control_view(
        self,
        target_date: date,
        publish_succeeded: bool = False,
    ) -> dict[str, Any]:
        snapshot = self.build_snapshot(
            target_date=target_date,
            publish_succeeded=publish_succeeded,
            write_outputs=False,
        )
        with self._cache_lock:
            registry_payload = self._cache_get(("registry", "source_registry"))
            registry_cache_status = "hit"
            if registry_payload is None:
                registry = SourceRegistry.from_file(self._source_registry_config)
                registry_payload = {
                    "version": registry.version,
                    "description": registry.description,
                    "sources": [source.__dict__ for source in registry.sources],
                }
                self._cache_set(
                    ("registry", "source_registry"),
                    registry_payload,
                    self._cache_ttl_seconds["source_registry"],
                )
                registry_cache_status = "miss"
        return {
            "target_date": snapshot["target_date"],
            "_meta": {
                **snapshot.get("_meta", {}),
                "source_registry_cache_status": registry_cache_status,
            },
            "source_registry": registry_payload,
            "data_control": snapshot["data_control"],
        }

    def data_control_runs_view(
        self,
        *,
        target_date: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> dict[str, Any]:
        base_dir = self.project_root / "var/ledgers/data_control"
        if not base_dir.exists():
            return {"_meta": {"returned_count": 0}, "data_control_runs": []}

        date_dirs = []
        for item in base_dir.iterdir():
            if not item.is_dir():
                continue
            if target_date and item.name != target_date:
                continue
            date_dirs.append(item)
        date_dirs.sort(key=lambda p: p.name, reverse=True)

        runs: list[dict[str, Any]] = []
        for date_dir in date_dirs:
            for ledger_file in sorted(date_dir.glob("data_control_*_ledger.json")):
                payload: Optional[object]
                try:
                    payload = json.loads(ledger_file.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    payload = None
                if not isinstance(payload, dict):
                    continue
                runs.append(payload)
                if limit is not None and len(runs) >= limit:
                    return {
                        "_meta": {"returned_count": len(runs)},
                        "data_control_runs": runs,
                    }
        return {"_meta": {"returned_count": len(runs)}, "data_control_runs": runs}

    def data_control_run_detail_view(
        self, *, target_date: str, stage: str
    ) -> dict[str, Any]:
        stage = str(stage).strip().lower()
        if stage not in {"capture", "compose", "publish"}:
            raise ApiError(
                status_code=HTTPStatus.BAD_REQUEST,
                code="invalid_stage",
                message="unsupported data_control stage",
                details={
                    "supported": ["capture", "compose", "publish"],
                    "stage": stage,
                },
            )
        ledger_path, artifact_path = self._data_control_stage_paths(
            target_date=target_date, stage=stage
        )
        if not ledger_path.exists():
            raise ApiError(
                status_code=HTTPStatus.NOT_FOUND,
                code="data_control_run_not_found",
                message="data control ledger not found",
                details={"target_date": target_date, "stage": stage},
            )
        if not artifact_path.exists():
            raise ApiError(
                status_code=HTTPStatus.NOT_FOUND,
                code="data_control_run_artifact_not_found",
                message="data control artifact not found",
                details={"target_date": target_date, "stage": stage},
            )
        ledger_payload = json.loads(ledger_path.read_text(encoding="utf-8"))
        artifact_payload = json.loads(artifact_path.read_text(encoding="utf-8"))
        if not isinstance(ledger_payload, dict) or not isinstance(
            artifact_payload, dict
        ):
            raise ApiError(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                code="data_control_run_invalid",
                message="data control stored payloads are not JSON objects",
                details={"target_date": target_date, "stage": stage},
            )
        return {
            "_meta": {"status": "ok"},
            "data_control_run": ledger_payload,
            "data_control_result": artifact_payload,
        }

    def data_control_run_download_view(
        self, *, target_date: str, stage: str
    ) -> ApiBinaryResponse:
        stage = str(stage).strip().lower()
        if stage not in {"capture", "compose", "publish"}:
            raise ApiError(
                status_code=HTTPStatus.BAD_REQUEST,
                code="invalid_stage",
                message="unsupported data_control stage",
                details={
                    "supported": ["capture", "compose", "publish"],
                    "stage": stage,
                },
            )
        _, artifact_path = self._data_control_stage_paths(
            target_date=target_date, stage=stage
        )
        if not artifact_path.exists():
            raise ApiError(
                status_code=HTTPStatus.NOT_FOUND,
                code="data_control_run_artifact_not_found",
                message="data control artifact not found",
                details={"target_date": target_date, "stage": stage},
            )
        filename = artifact_path.name
        return ApiBinaryResponse(
            body=artifact_path.read_bytes(),
            content_type="application/json; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    def orchestration_view(
        self,
        target_date: date,
        publish_succeeded: bool = False,
    ) -> dict[str, Any]:
        snapshot = self.build_snapshot(
            target_date=target_date,
            publish_succeeded=publish_succeeded,
            write_outputs=False,
        )
        response_payload = {
            "target_date": snapshot["target_date"],
            "publish_succeeded": snapshot.get("publish_succeeded"),
            "_meta": snapshot.get("_meta", {}),
            "orchestration": snapshot["orchestration"],
        }
        return response_payload

    def orchestration_run_view(
        self,
        *,
        target_date: str,
        publish_succeeded: bool,
        requested_by: str,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        self.require_trading_day(target_date=target_date)
        if not requested_by.strip():
            raise ApiError(
                status_code=HTTPStatus.BAD_REQUEST,
                code="invalid_requested_by",
                message="requested_by must be a non-empty string",
            )

        orchestrator = DailyMasterOrchestrator.from_files(
            orchestrator_config_path=self.project_root
            / "config/orchestrator/daily_master_orchestrator.json",
            labs_registry_path=self._labs_config,
        )
        target_date_obj = date.fromisoformat(target_date)
        plan = orchestrator.build_run_plan(
            DailyRunRequest(
                target_date=target_date_obj, publish_succeeded=bool(publish_succeeded)
            )
        )

        ledger_path, artifact_path = self._orchestration_run_paths(
            target_date=target_date
        )
        requested_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        run_id = f"orchestrator:{target_date}:{int(time.time())}"

        task_results: list[dict[str, Any]] = []
        task_status: dict[str, str] = {}
        publish_ok = False

        for task in plan.planned_tasks:
            status: str
            message: str
            if task.status.value == "skipped":
                status = task.status.value
                message = task.skip_reason or ""
                task_results.append(
                    {
                        "task_id": task.task_id,
                        "phase": task.phase.value,
                        "lab_id": task.lab_id,
                        "status": status,
                        "message": message,
                        "artifact_refs": [],
                    }
                )
                task_status[task.task_id] = status
                continue

            if task.status.value == "blocked":
                if task.requires_publish_status and publish_ok:
                    pass
                else:
                    status = task.status.value
                    message = task.skip_reason or ""
                    task_results.append(
                        {
                            "task_id": task.task_id,
                            "phase": task.phase.value,
                            "lab_id": task.lab_id,
                            "status": status,
                            "message": message,
                            "artifact_refs": [],
                        }
                    )
                    task_status[task.task_id] = status
                    continue

            unmet = [
                dep
                for dep in task.depends_on
                if task_status.get(dep) not in {None, "ok", "pending_implementation"}
            ]
            if unmet:
                status = "blocked"
                message = f"dependency_not_ok: {', '.join(unmet)}"
                task_results.append(
                    {
                        "task_id": task.task_id,
                        "phase": task.phase.value,
                        "lab_id": task.lab_id,
                        "status": status,
                        "message": message,
                        "artifact_refs": [],
                    }
                )
                task_status[task.task_id] = status
                continue

            if task.task_id.startswith("data_control."):
                pipeline = DataControlPipeline.from_registry_file(
                    self._source_registry_config
                )
                stage_name = task.task_id.split(".", 1)[1]
                if stage_name == "capture":
                    result = pipeline.capture(
                        target_date=target_date_obj,
                        requested_by=requested_by.strip(),
                        dry_run=dry_run,
                    )
                elif stage_name == "compose":
                    result = pipeline.compose(
                        target_date=target_date_obj,
                        requested_by=requested_by.strip(),
                        dry_run=dry_run,
                    )
                elif stage_name == "publish":
                    result = pipeline.publish(
                        target_date=target_date_obj,
                        requested_by=requested_by.strip(),
                        dry_run=dry_run,
                    )
                else:
                    result = None

                if result is None:
                    status = "failed"
                    message = "unknown data_control stage"
                else:
                    status = str(getattr(result, "status", "pending_implementation"))
                    message = str(getattr(result, "message", ""))

                _, stage_artifact_path = self._data_control_stage_paths(
                    target_date=target_date,
                    stage=stage_name,
                )
                details: Optional[dict[str, Any]] = None
                if not dry_run and stage_artifact_path.exists():
                    try:
                        stage_payload = json.loads(
                            stage_artifact_path.read_text(encoding="utf-8")
                        )
                    except (OSError, json.JSONDecodeError):
                        stage_payload = None
                    if isinstance(stage_payload, dict):
                        if stage_name in {"capture", "publish"}:
                            units_validation = stage_payload.get("units_validation")
                            prerequisites = stage_payload.get("prerequisites")
                            details = {}
                            if isinstance(units_validation, dict):
                                details["units_validation"] = units_validation
                            if isinstance(prerequisites, dict):
                                details["prerequisites"] = prerequisites
                        elif stage_name == "compose":
                            warnings = stage_payload.get("warnings")
                            candidate_universe = stage_payload.get("candidate_universe")
                            details = {
                                "warning_count": (
                                    len(warnings) if isinstance(warnings, list) else 0
                                ),
                                "candidate_count": (
                                    len(candidate_universe)
                                    if isinstance(candidate_universe, list)
                                    else 0
                                ),
                                "warnings": (
                                    [str(item) for item in warnings]
                                    if isinstance(warnings, list)
                                    else []
                                ),
                            }
                task_results.append(
                    {
                        "task_id": task.task_id,
                        "phase": task.phase.value,
                        "lab_id": task.lab_id,
                        "status": status,
                        "message": message,
                        "details": details,
                        "artifact_refs": (
                            [self._safe_ref_path(str(stage_artifact_path))]
                            if (not dry_run and stage_artifact_path.exists())
                            else []
                        ),
                    }
                )
                task_status[task.task_id] = status
                if task.task_id == "data_control.publish":
                    publish_ok = status == "ok"
                continue

            if task.lab_id:
                response = self.lab_run_view(
                    target_date=target_date,
                    lab_id=task.lab_id,
                    requested_by=requested_by.strip(),
                    dry_run=dry_run,
                )
                ledger = response.get("lab_run")
                artifact_ref = (
                    ledger.get("artifact_path") if isinstance(ledger, dict) else None
                )
                task_results.append(
                    {
                        "task_id": task.task_id,
                        "phase": task.phase.value,
                        "lab_id": task.lab_id,
                        "status": "ok",
                        "message": "lab executed",
                        "artifact_refs": [artifact_ref] if artifact_ref else [],
                    }
                )
                task_status[task.task_id] = "ok"
                continue

            task_results.append(
                {
                    "task_id": task.task_id,
                    "phase": task.phase.value,
                    "lab_id": task.lab_id,
                    "status": "pending_implementation",
                    "message": "task execution has not been implemented",
                    "artifact_refs": [],
                }
            )
            task_status[task.task_id] = "pending_implementation"

        extra_task_results: list[dict[str, Any]] = []
        bulk = self.screeners_bulk_run_view(
            target_date=target_date,
            screener_ids=None,
            requested_by=requested_by.strip(),
            parameters=None,
            dry_run=dry_run,
        )
        bulk_ledger = bulk.get("bulk_run")
        bulk_artifact_ref = (
            bulk_ledger.get("artifact_path") if isinstance(bulk_ledger, dict) else None
        )
        extra_task_results.append(
            {
                "task_id": "screeners.bulk_run",
                "phase": "daily_lab_jobs",
                "lab_id": None,
                "status": "ok",
                "message": "screeners bulk-run executed",
                "artifact_refs": (
                    [self._safe_ref_path(str(bulk_artifact_ref))]
                    if bulk_artifact_ref
                    else []
                ),
            }
        )

        fm = self.factor_matrix_daily_run_view(
            target_date=target_date,
            requested_by=requested_by.strip(),
            dry_run=dry_run,
            debug=False,
        )
        fm_ledger = fm.get("factor_matrix_run")
        fm_artifact_ref = (
            fm_ledger.get("artifact_path") if isinstance(fm_ledger, dict) else None
        )
        extra_task_results.append(
            {
                "task_id": "factor_matrix.daily_run",
                "phase": "learning_loop",
                "lab_id": None,
                "status": "ok",
                "message": "factor matrix daily run executed",
                "artifact_refs": (
                    [self._safe_ref_path(str(fm_artifact_ref))]
                    if fm_artifact_ref
                    else []
                ),
            }
        )

        all_results = task_results + extra_task_results
        status_counts: dict[str, int] = {}
        for item in all_results:
            status_counts[str(item.get("status"))] = (
                status_counts.get(str(item.get("status")), 0) + 1
            )
        overall_status = "ok" if status_counts.get("failed", 0) == 0 else "partial"

        run_ledger_payload = {
            "version": 1,
            "orchestrator_run_id": run_id,
            "target_date": target_date,
            "publish_succeeded": bool(publish_ok),
            "requested_by": requested_by.strip(),
            "requested_at": requested_at,
            "status": overall_status,
            "task_count": len(all_results),
            "status_counts": dict(sorted(status_counts.items())),
            "artifact_path": self._safe_ref_path(str(artifact_path)),
        }
        run_artifact_payload = {
            "version": 1,
            "orchestrator_run_id": run_id,
            "target_date": target_date,
            "publish_succeeded": bool(publish_ok),
            "requested_by": requested_by.strip(),
            "requested_at": requested_at,
            "status": overall_status,
            "tasks": all_results,
        }

        if not dry_run:
            ledger_path.parent.mkdir(parents=True, exist_ok=True)
            artifact_path.parent.mkdir(parents=True, exist_ok=True)
            ledger_path.write_text(
                json.dumps(
                    run_ledger_payload, indent=2, ensure_ascii=False, sort_keys=True
                )
                + "\n",
                encoding="utf-8",
            )
            artifact_path.write_text(
                json.dumps(
                    run_artifact_payload, indent=2, ensure_ascii=False, sort_keys=True
                )
                + "\n",
                encoding="utf-8",
            )

        return {"_meta": {"status": "ok"}, "orchestrator_run": run_ledger_payload}

    def orchestration_runs_view(
        self,
        *,
        target_date: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> dict[str, Any]:
        base_dir = self.project_root / "var/ledgers/orchestration_runs"
        if not base_dir.exists():
            return {"_meta": {"returned_count": 0}, "orchestrator_runs": []}

        date_dirs = []
        for item in base_dir.iterdir():
            if not item.is_dir():
                continue
            if target_date and item.name != target_date:
                continue
            date_dirs.append(item)
        date_dirs.sort(key=lambda p: p.name, reverse=True)

        runs: list[dict[str, Any]] = []
        for date_dir in date_dirs:
            ledger_file = date_dir / "orchestrator_run.json"
            if not ledger_file.exists():
                continue
            payload: Optional[object]
            try:
                payload = json.loads(ledger_file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                payload = None
            if not isinstance(payload, dict):
                continue
            runs.append(payload)
            if limit is not None and len(runs) >= limit:
                return {
                    "_meta": {"returned_count": len(runs)},
                    "orchestrator_runs": runs,
                }
        return {"_meta": {"returned_count": len(runs)}, "orchestrator_runs": runs}

    def orchestration_run_detail_view(self, *, target_date: str) -> dict[str, Any]:
        ledger_path, artifact_path = self._orchestration_run_paths(
            target_date=target_date
        )
        if not ledger_path.exists():
            raise ApiError(
                status_code=HTTPStatus.NOT_FOUND,
                code="orchestrator_run_not_found",
                message="orchestrator run ledger not found",
                details={"target_date": target_date},
            )
        if not artifact_path.exists():
            raise ApiError(
                status_code=HTTPStatus.NOT_FOUND,
                code="orchestrator_run_artifact_not_found",
                message="orchestrator run artifact not found",
                details={"target_date": target_date},
            )
        ledger_payload = json.loads(ledger_path.read_text(encoding="utf-8"))
        artifact_payload = json.loads(artifact_path.read_text(encoding="utf-8"))
        if not isinstance(ledger_payload, dict) or not isinstance(
            artifact_payload, dict
        ):
            raise ApiError(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                code="orchestrator_run_invalid",
                message="orchestrator stored payloads are not JSON objects",
                details={"target_date": target_date},
            )
        return {
            "_meta": {"status": "ok"},
            "orchestrator_run": ledger_payload,
            "orchestrator_result": artifact_payload,
        }

    def orchestration_run_download_view(self, *, target_date: str) -> ApiBinaryResponse:
        _, artifact_path = self._orchestration_run_paths(target_date=target_date)
        if not artifact_path.exists():
            raise ApiError(
                status_code=HTTPStatus.NOT_FOUND,
                code="orchestrator_run_artifact_not_found",
                message="orchestrator run artifact not found",
                details={"target_date": target_date},
            )
        filename = artifact_path.name
        return ApiBinaryResponse(
            body=artifact_path.read_bytes(),
            content_type="application/json; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    def labs_view(self) -> dict[str, Any]:
        with self._cache_lock:
            registry_payload = self._cache_get(("registry", "labs"))
            cache_status = "hit"
            if registry_payload is None:
                registry = LabRegistry.from_file(self._labs_config)
                registry_payload = {
                    "version": registry.version,
                    "description": registry.description,
                    "labs": [
                        {
                            "lab_id": lab.lab_id,
                            "display_name": lab.display_name,
                            "domain": lab.domain,
                            "enabled": lab.enabled,
                            "input_dependencies": lab.input_dependencies,
                            "daily_jobs": [job.__dict__ for job in lab.daily_jobs],
                            "artifacts": [
                                artifact.__dict__ for artifact in lab.artifacts
                            ],
                            "health_checks": [
                                check.__dict__ for check in lab.health_checks
                            ],
                            "learning_inputs": lab.learning_inputs,
                        }
                        for lab in registry.labs
                    ],
                }
                self._cache_set(
                    ("registry", "labs"),
                    registry_payload,
                    self._cache_ttl_seconds["labs_registry"],
                )
                cache_status = "miss"
        return {
            "_meta": {"cache_status": cache_status},
            **registry_payload,
        }

    def config_contracts_view(self) -> dict[str, Any]:
        report = build_config_contract_report(
            source_registry=SourceRegistry.from_file(self._source_registry_config),
            lab_registry=LabRegistry.from_file(self._labs_config),
            orchestrator_config=load_orchestrator_config(
                self.project_root / "config/orchestrator/daily_master_orchestrator.json"
            ),
        )
        return {
            "_meta": {"validation_status": report.status},
            "config_contracts": report.to_payload(),
        }

    def screeners_view(self, *, target_date: Optional[str] = None) -> dict[str, Any]:
        registry = load_screener_registry(self._screeners_registry_config)
        runs = list_screener_runs(
            project_root=self.project_root, target_date=target_date
        )
        return {
            "_meta": {
                "registry_source": str(self._screeners_registry_config),
                "runs_source": "var/ledgers/screener_runs",
                "date_filter": target_date,
            },
            "screeners_registry": {
                "version": registry.version,
                "description": registry.description,
                "screeners": [screener.__dict__ for screener in registry.screeners],
            },
            "screener_runs": [run.__dict__ for run in runs],
        }

    def screener_runs_view(
        self,
        *,
        target_date: Optional[str] = None,
        screener_id: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> dict[str, Any]:
        runs = list_screener_runs(
            project_root=self.project_root, target_date=target_date
        )
        if screener_id:
            runs = [run for run in runs if run.screener_id == screener_id]
        total_count = len(runs)
        if limit is not None:
            runs = runs[:limit]
        return {
            "_meta": {
                "runs_source": "var/ledgers/screener_runs",
                "date_filter": target_date,
                "screener_id_filter": screener_id,
                "limit": limit,
                "total_count": total_count,
                "returned_count": len(runs),
            },
            "screener_runs": [run.__dict__ for run in runs],
        }

    def _execute_screener_entrypoint(
        self,
        *,
        entrypoint: str,
        screener_id: str,
        target_date: str,
        parameters: dict[str, Any],
    ) -> dict[str, Any]:
        parts = str(entrypoint).split(":")
        if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
            return {
                "screener_id": screener_id,
                "target_date": target_date,
                "status": "failed",
                "message": "invalid entrypoint",
                "parameters": parameters,
                "picks": [],
                "decision_trace": [
                    {
                        "step": "load_entrypoint",
                        "status": "failed",
                        "entrypoint": entrypoint,
                    }
                ],
            }
        module_name, attr_name = parts[0].strip(), parts[1].strip()
        try:
            module = importlib.import_module(module_name)
            func = getattr(module, attr_name)
        except Exception as exc:
            return {
                "screener_id": screener_id,
                "target_date": target_date,
                "status": "failed",
                "message": "failed to load entrypoint",
                "parameters": parameters,
                "picks": [],
                "decision_trace": [
                    {
                        "step": "load_entrypoint",
                        "status": "failed",
                        "entrypoint": entrypoint,
                        "reason": "failed to load entrypoint (see server logs for details)",
                    }
                ],
            }
        if not callable(func):
            return {
                "screener_id": screener_id,
                "target_date": target_date,
                "status": "failed",
                "message": "entrypoint is not callable",
                "parameters": parameters,
                "picks": [],
                "decision_trace": [
                    {
                        "step": "load_entrypoint",
                        "status": "failed",
                        "entrypoint": entrypoint,
                        "reason": "not_callable",
                    }
                ],
            }

        try:
            runtime_result = func(
                screener_id=screener_id,
                target_date=date.fromisoformat(target_date),
                parameters=parameters,
            )
        except Exception as exc:
            return {
                "screener_id": screener_id,
                "target_date": target_date,
                "status": "failed",
                "message": "screener runtime error",
                "parameters": parameters,
                "picks": [],
                "decision_trace": [
                    {
                        "step": "execute_entrypoint",
                        "status": "failed",
                        "entrypoint": entrypoint,
                        "reason": "screener runtime error (see server logs for details)",
                    }
                ],
            }

        if not isinstance(runtime_result, dict):
            return {
                "screener_id": screener_id,
                "target_date": target_date,
                "status": "failed",
                "message": "screener runtime returned non-dict payload",
                "parameters": parameters,
                "picks": [],
                "decision_trace": [
                    {
                        "step": "execute_entrypoint",
                        "status": "failed",
                        "entrypoint": entrypoint,
                        "reason": f"invalid_result_type: {type(runtime_result).__name__}",
                    }
                ],
            }
        return runtime_result

    def screeners_run_view(
        self,
        *,
        target_date: str,
        screener_id: str,
        requested_by: str,
        parameters: Optional[dict[str, Any]] = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        self.require_trading_day(target_date=target_date)
        registry = load_screener_registry(self._screeners_registry_config)
        enabled_ids = {
            screener.screener_id for screener in registry.screeners if screener.enabled
        }
        if screener_id not in enabled_ids:
            raise ApiError(
                status_code=HTTPStatus.BAD_REQUEST,
                code="invalid_screener_id",
                message=f"unknown or disabled screener_id: {screener_id}",
                details={"screener_id": screener_id, "enabled": sorted(enabled_ids)},
            )

        config_payload = (
            read_screener_config(
                config_dir=self._screeners_config_dir, screener_id=screener_id
            )
            or {}
        )
        effective_parameters = self._deep_merge_dicts(
            config_payload.get("default_parameters", {}),
            config_payload.get("current_parameters", {}),
        )
        if parameters:
            effective_parameters = self._deep_merge_dicts(
                effective_parameters, parameters
            )

        screener = next(
            (item for item in registry.screeners if item.screener_id == screener_id),
            None,
        )
        if screener is None:
            raise ApiError(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                code="screener_registry_inconsistent",
                message="enabled screener_id not found in registry",
                details={"screener_id": screener_id},
            )

        runtime_result = self._execute_screener_entrypoint(
            entrypoint=screener.entrypoint,
            screener_id=screener_id,
            target_date=target_date,
            parameters=effective_parameters,
        )
        record = write_screener_run(
            project_root=self.project_root,
            target_date=target_date,
            screener_id=screener_id,
            requested_by=requested_by,
            parameters=effective_parameters,
            runtime_result=runtime_result,
            dry_run=dry_run,
        )
        return {
            "_meta": {"status": "ok"},
            "screener_run": record.__dict__,
        }

    def screeners_bulk_run_view(
        self,
        *,
        target_date: str,
        screener_ids: Optional[list[str]],
        requested_by: str,
        parameters: Optional[dict[str, Any]] = None,
        dry_run: bool = False,
        async_run: bool = True,
    ) -> dict[str, Any]:
        self.require_trading_day(target_date=target_date)
        registry = load_screener_registry(self._screeners_registry_config)
        enabled_ids = {
            screener.screener_id for screener in registry.screeners if screener.enabled
        }

        if screener_ids is None:
            selected_ids = sorted(enabled_ids)
        else:
            selected_ids = []
            for item in screener_ids:
                if not isinstance(item, str) or not item.strip():
                    raise ApiError(
                        status_code=HTTPStatus.BAD_REQUEST,
                        code="invalid_screener_id",
                        message="screener_ids must be a list of non-empty strings",
                        details={"screener_id": item},
                    )
                selected_ids.append(item.strip())
            selected_ids = sorted(set(selected_ids))

        unknown = sorted(set(selected_ids) - enabled_ids)
        if unknown:
            raise ApiError(
                status_code=HTTPStatus.BAD_REQUEST,
                code="invalid_screener_id",
                message="unknown or disabled screener_id values in screener_ids",
                details={"unknown": unknown, "enabled": sorted(enabled_ids)},
            )

        if async_run and not dry_run:
            job_id = uuid.uuid4().hex
            bulk_requested_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            ledgers_dir = self.project_root / "var/ledgers/screener_runs" / target_date
            artifacts_dir = self.project_root / "var/artifacts/screener_runs" / target_date
            bulk_ledger_path = ledgers_dir / "bulk_run_ledger.json"
            bulk_artifact_path = artifacts_dir / "bulk_run_result.json"

            ledgers_dir.mkdir(parents=True, exist_ok=True)
            artifacts_dir.mkdir(parents=True, exist_ok=True)

            bulk_ledger_payload = {
                "version": 1,
                "job_id": job_id,
                "target_date": target_date,
                "requested_by": requested_by,
                "requested_at": bulk_requested_at,
                "status": "running",
                "screener_ids": selected_ids,
                "run_count": 0,
                "run_ledgers": [],
            }
            bulk_artifact_payload = {
                "version": 1,
                "job_id": job_id,
                "target_date": target_date,
                "requested_by": requested_by,
                "requested_at": bulk_requested_at,
                "status": "running",
                "summary": {"run_count": 0, "picks_count_total": 0},
                "runs": [],
            }
            bulk_ledger_path.write_text(
                json.dumps(
                    bulk_ledger_payload, indent=2, ensure_ascii=False, sort_keys=True
                )
                + "\n",
                encoding="utf-8",
            )
            bulk_artifact_path.write_text(
                json.dumps(
                    bulk_artifact_payload, indent=2, ensure_ascii=False, sort_keys=True
                )
                + "\n",
                encoding="utf-8",
            )

            ctx = multiprocessing.get_context("spawn")
            proc = ctx.Process(
                target=_screeners_bulk_run_worker,
                kwargs={
                    "project_root": str(self.project_root),
                    "target_date": target_date,
                    "screener_ids": selected_ids,
                    "requested_by": requested_by,
                    "parameters": parameters or {},
                    "job_id": job_id,
                },
                daemon=True,
            )
            proc.start()

            bulk_ledger_payload["pid"] = proc.pid
            bulk_artifact_payload["pid"] = proc.pid
            bulk_ledger_path.write_text(
                json.dumps(
                    bulk_ledger_payload, indent=2, ensure_ascii=False, sort_keys=True
                )
                + "\n",
                encoding="utf-8",
            )
            bulk_artifact_path.write_text(
                json.dumps(
                    bulk_artifact_payload, indent=2, ensure_ascii=False, sort_keys=True
                )
                + "\n",
                encoding="utf-8",
            )

            return {
                "_meta": {"status": "accepted"},
                "message": "已提交后台运行，请稍后刷新查看结果",
                "job": {
                    "job_id": job_id,
                    "pid": proc.pid,
                    "target_date": target_date,
                    "screener_ids": selected_ids,
                    "requested_at": bulk_requested_at,
                    "status": "running",
                    "bulk_ledger_url": f"/api/screeners/bulk-runs/{target_date}",
                    "bulk_artifact_url": f"/api/screeners/bulk-runs/{target_date}/download",
                },
            }

        run_records = []
        for screener_id in selected_ids:
            screener = next(
                (
                    item
                    for item in registry.screeners
                    if item.enabled and item.screener_id == screener_id
                ),
                None,
            )
            if screener is None:
                raise ApiError(
                    status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                    code="screener_registry_inconsistent",
                    message="enabled screener_id not found in registry",
                    details={"screener_id": screener_id},
                )
            config_payload = (
                read_screener_config(
                    config_dir=self._screeners_config_dir, screener_id=screener_id
                )
                or {}
            )
            effective_parameters = self._deep_merge_dicts(
                config_payload.get("default_parameters", {}),
                config_payload.get("current_parameters", {}),
            )
            if parameters:
                effective_parameters = self._deep_merge_dicts(
                    effective_parameters, parameters
                )
            runtime_result = self._execute_screener_entrypoint(
                entrypoint=screener.entrypoint,
                screener_id=screener_id,
                target_date=target_date,
                parameters=effective_parameters,
            )
            record = write_screener_run(
                project_root=self.project_root,
                target_date=target_date,
                screener_id=screener_id,
                requested_by=requested_by,
                parameters=effective_parameters,
                runtime_result=runtime_result,
                dry_run=dry_run,
            )
            run_records.append(record)

        bulk_requested_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        ledgers_dir = self.project_root / "var/ledgers/screener_runs" / target_date
        artifacts_dir = self.project_root / "var/artifacts/screener_runs" / target_date
        bulk_ledger_path = ledgers_dir / "bulk_run_ledger.json"
        bulk_artifact_path = artifacts_dir / "bulk_run_result.json"
        if any(record.status == "failed" for record in run_records):
            bulk_status = "failed"
        elif all(record.status == "ok" for record in run_records):
            bulk_status = "ok"
        else:
            bulk_status = "pending_implementation"

        bulk_ledger_payload = {
            "version": 1,
            "target_date": target_date,
            "requested_by": requested_by,
            "requested_at": bulk_requested_at,
            "status": bulk_status,
            "screener_ids": selected_ids,
            "run_count": len(run_records),
            "run_ledgers": [record.__dict__ for record in run_records],
        }
        bulk_artifact_payload = {
            "version": 1,
            "target_date": target_date,
            "requested_by": requested_by,
            "requested_at": bulk_requested_at,
            "status": bulk_status,
            "summary": {
                "run_count": len(run_records),
                "picks_count_total": sum(record.picks_count for record in run_records),
            },
            "runs": [record.__dict__ for record in run_records],
        }
        if not dry_run:
            ledgers_dir.mkdir(parents=True, exist_ok=True)
            artifacts_dir.mkdir(parents=True, exist_ok=True)
            bulk_ledger_path.write_text(
                json.dumps(
                    bulk_ledger_payload, indent=2, ensure_ascii=False, sort_keys=True
                )
                + "\n",
                encoding="utf-8",
            )
            bulk_artifact_path.write_text(
                json.dumps(
                    bulk_artifact_payload, indent=2, ensure_ascii=False, sort_keys=True
                )
                + "\n",
                encoding="utf-8",
            )

        return {
            "_meta": {"status": "ok"},
            "bulk_run": bulk_ledger_payload,
        }

    def check_stock_view(
        self,
        *,
        target_date: str,
        stock_code: str,
        screener_ids: Optional[list[str]] = None,
        debug: bool = False,
    ) -> dict[str, Any]:
        self.require_trading_day(target_date=target_date)

        normalized_code = stock_code.strip()
        registry = load_screener_registry(self._screeners_registry_config)
        enabled_screeners = [
            screener for screener in registry.screeners if screener.enabled
        ]
        normalized_screener_ids: Optional[set[str]]
        if isinstance(screener_ids, list) and screener_ids:
            normalized_screener_ids = {str(item).strip() for item in screener_ids if str(item).strip()}
        else:
            normalized_screener_ids = None
        if normalized_screener_ids is not None:
            enabled_screeners = [
                screener
                for screener in enabled_screeners
                if str(screener.screener_id).strip() in normalized_screener_ids
            ]

        universe_base = self._evaluate_universe_base_filters(stock_code=normalized_code)
        effective_parameters_by_screener_id: dict[str, dict[str, Any]] = {}
        for screener in enabled_screeners:
            config_payload = (
                read_screener_config(
                    config_dir=self._screeners_config_dir,
                    screener_id=screener.screener_id,
                )
                or {}
            )
            effective_parameters_by_screener_id[screener.screener_id] = (
                self._deep_merge_dicts(
                    config_payload.get("default_parameters", {}),
                    config_payload.get("current_parameters", {}),
                )
            )

        def _tri_state_message(value: Optional[bool]) -> str:
            if value is True:
                return "通过"
            if value is False:
                return "未通过"
            return "无法判断"

        def _normalize_code(value: object) -> str:
            return str(value or "").strip().split(".", 1)[0]

        def _pick_numeric_evidence(lines: object, limit: int) -> list[str]:
            if not isinstance(lines, list):
                return []
            items = [str(item).strip() for item in lines if str(item).strip()]
            picked: list[str] = []
            for item in items:
                if any(ch.isdigit() for ch in item):
                    picked.append(item)
                    if len(picked) >= limit:
                        return picked
            for item in items:
                if item in picked:
                    continue
                picked.append(item)
                if len(picked) >= limit:
                    return picked
            return picked

        def _build_bool_row(metric: str, *, passed: Optional[bool], note: str = "") -> dict[str, Any]:
            return {
                "metric": metric,
                "current": "是" if passed is True else "否" if passed is False else "无法判断",
                "threshold": "是",
                "result": _tri_state_message(passed),
                "note": note,
            }

        def _build_threshold_row(
            metric: str,
            *,
            current: object,
            threshold: object,
            ok: Optional[bool],
            note: str = "",
        ) -> dict[str, Any]:
            return {
                "metric": metric,
                "current": current,
                "threshold": threshold,
                "result": _tri_state_message(ok),
                "note": note,
            }

        def _screener_failure_detail(screener_id: str) -> Optional[str]:
            expected_root = self.project_root / "var/artifacts/screener_runs" / target_date
            artifact_path = expected_root / f"screener_{screener_id}_result.json"
            if not artifact_path.exists():
                return None
            try:
                payload = json.loads(artifact_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return None
            if not isinstance(payload, dict):
                return None
            trace = payload.get("decision_trace")
            if not isinstance(trace, list):
                return None
            normalized = _normalize_code(normalized_code)
            for step in trace:
                if not isinstance(step, dict):
                    continue
                rejected = step.get("rejected_examples")
                if not isinstance(rejected, list):
                    continue
                for ex in rejected:
                    if not isinstance(ex, dict):
                        continue
                    if _normalize_code(ex.get("code")) != normalized:
                        continue
                    detail = str(ex.get("detail") or "").strip()
                    if detail:
                        return detail
                    reason = str(ex.get("reason") or "").strip()
                    if reason == "missing_required_days":
                        missing_count = ex.get("missing_count")
                        if isinstance(missing_count, int) and missing_count > 0:
                            return f"数据不足：缺少 {missing_count} 个交易日数据"
                        return "数据不足：缺少必要交易日数据"
                    if reason:
                        return reason
            return None

        bulk_artifact = (
            read_bulk_run_artifact(
                project_root=self.project_root, target_date=target_date
            )
            or {}
        )
        bulk_run_refs: dict[str, dict[str, Any]] = {}
        runs = bulk_artifact.get("runs")
        if isinstance(runs, list):
            for run_entry in runs:
                if not isinstance(run_entry, dict):
                    continue
                screener_id = str(run_entry.get("screener_id", "")).strip()
                artifact_path_str = str(run_entry.get("artifact_path", "")).strip()
                if screener_id and artifact_path_str:
                    bulk_run_refs[screener_id] = run_entry

        screener_items: list[dict[str, Any]] = []
        appearances: list[dict[str, Any]] = []
        certainty_value: Optional[float] = None
        certainty_source: Optional[str] = None

        for screener in enabled_screeners:
            screener_id = screener.screener_id
            screener_name = screener.display_name.strip() or screener_id
            screener_parameters = effective_parameters_by_screener_id.get(
                screener_id, {}
            )
            try:
                runtime_parameters = self._deep_merge_dicts(
                    screener_parameters, {"trace_code": normalized_code}
                )
            except Exception:
                runtime_parameters = dict(screener_parameters or {})
                runtime_parameters["trace_code"] = normalized_code

            record = read_screener_run_ledger(
                project_root=self.project_root,
                target_date=target_date,
                screener_id=screener_id,
            )
            if record is None and bulk_run_refs.get(screener_id) is None:
                runtime_result = self._execute_screener_entrypoint(
                    entrypoint=screener.entrypoint,
                    screener_id=screener_id,
                    target_date=target_date,
                    parameters=runtime_parameters,
                )
                runtime_status = (
                    str(runtime_result.get("status") or "").strip()
                    if isinstance(runtime_result, dict)
                    else ""
                )
                picks = (
                    runtime_result.get("picks") if isinstance(runtime_result, dict) else None
                )
                picks_set = (
                    {str(x).strip() for x in picks} if isinstance(picks, list) else set()
                )
                passed = _normalize_code(normalized_code) in {
                    _normalize_code(x) for x in picks_set
                }
                def _extract_param_level_detail() -> Optional[str]:
                    if not isinstance(runtime_result, dict):
                        return None
                    trace_target = runtime_result.get("trace_target")
                    if isinstance(trace_target, list) and trace_target:
                        normalized = _normalize_code(normalized_code)
                        for entry in trace_target:
                            if not isinstance(entry, dict):
                                continue
                            if _normalize_code(entry.get("code")) != normalized:
                                continue
                            ok = entry.get("ok")
                            if ok is False:
                                reason = str(entry.get("reason") or "").strip()
                                detail = str(entry.get("detail") or "").strip()
                                parts: list[str] = []
                                if reason:
                                    parts.append(f"原因：{reason}")
                                if detail:
                                    parts.append(f"细节：{detail}")
                                for k, v in entry.items():
                                    if k in {"code", "ok", "reason", "detail"}:
                                        continue
                                    parts.append(f"{k}={v}")
                                return "；".join(parts) if parts else None
                    trace = runtime_result.get("decision_trace")
                    if not isinstance(trace, list):
                        return None
                    normalized = _normalize_code(normalized_code)
                    for step in trace:
                        if not isinstance(step, dict):
                            continue
                        tc = step.get("trace_candidate")
                        if (
                            isinstance(tc, dict)
                            and _normalize_code(tc.get("code")) == normalized
                        ):
                            if tc.get("picked") is False:
                                parts = ["原因：未进入 top_n"]
                                for k, v in tc.items():
                                    if k in {"code", "picked"}:
                                        continue
                                    parts.append(f"{k}={v}")
                                return "；".join(parts)
                        for k in ("rejected_examples", "threshold_rejected_examples"):
                            ex_list = step.get(k)
                            if not isinstance(ex_list, list):
                                continue
                            for ex in ex_list:
                                if not isinstance(ex, dict):
                                    continue
                                if _normalize_code(ex.get("code")) != normalized:
                                    continue
                                reason = str(ex.get("reason") or "").strip()
                                detail = str(ex.get("detail") or "").strip()
                                parts: list[str] = []
                                if reason:
                                    parts.append(f"原因：{reason}")
                                if detail:
                                    parts.append(f"细节：{detail}")
                                for field in (
                                    "pct_change",
                                    "amount_yuan",
                                    "min_amount_yuan",
                                    "market_cap_yuan",
                                    "min_market_cap_yuan",
                                    "missing_count",
                                ):
                                    if field in ex:
                                        parts.append(f"{field}={ex.get(field)}")
                                if (
                                    len(parts) == 1
                                    and reason
                                    and screener_id == "er_ban_hui_tiao"
                                    and isinstance(runtime_result.get("parameters"), dict)
                                ):
                                    p = runtime_result.get("parameters") or {}
                                    for k in (
                                        "limit_days",
                                        "limit_up_threshold",
                                        "first_board_volume_ratio",
                                        "top_n",
                                    ):
                                        if k in p:
                                            parts.append(f"{k}={p.get(k)}")
                                return "；".join(parts) if parts else None
                    return None

                if universe_base.get("result") is False:
                    passed = False

                if runtime_status and runtime_status != "ok":
                    passed = None
                    runtime_message = (
                        str(runtime_result.get("message") or "").strip()
                        if isinstance(runtime_result, dict)
                        else ""
                    )
                    explain_cn = (
                        f"无法判断：筛选器运行失败（{runtime_message or runtime_status}）"
                    )
                    msg = "无法判断"
                    reasons = [runtime_message or runtime_status]
                else:
                    explain_detail = _extract_param_level_detail()
                    if passed:
                        explain_cn = "通过：命中筛选器 picks。"
                        msg = "通过"
                        reasons = ["命中筛选器 picks"]
                    else:
                        msg = "未通过"
                        if explain_detail:
                            explain_cn = f"未通过：{explain_detail}"
                            reasons = [explain_detail]
                        else:
                            explain_cn = "未通过：未命中筛选器 picks（未获得参数级拒绝细节）。"
                            reasons = ["未命中筛选器 picks"]

                item_payload: dict[str, Any] = {
                    "screener_id": screener_id,
                    "name": screener_name,
                    "result": bool(passed) if passed in {True, False} else None,
                    "message": msg,
                    "explain_cn": explain_cn,
                    "reasons": reasons,
                    "evidence": [
                        f"日期：{target_date}",
                        f"筛选器：{screener_name}",
                        "证据来源：实时运行（单股核验触发）",
                    ],
                }
                if debug:
                    item_payload["_debug"] = {
                        "screener_id": screener_id,
                        "parameters": runtime_parameters,
                        "runtime_status": (
                            runtime_result.get("status")
                            if isinstance(runtime_result, dict)
                            else None
                        ),
                    }
                screener_items.append(item_payload)
                if passed:
                    appearances.append(
                        {
                            "screener_id": screener_id,
                            "name": screener_name,
                            "result": True,
                            "message": "通过",
                            "reasons": ["当日实时核验通过"],
                        }
                    )
                continue
            if record is None:
                ref = bulk_run_refs.get(screener_id)
                if ref is not None:
                    expected_root = (
                        self.project_root / "var/artifacts/screener_runs" / target_date
                    )
                    raw_artifact_ref = str(ref.get("artifact_path", "")).strip()
                    if raw_artifact_ref:
                        candidate = Path(raw_artifact_ref)
                        if str(candidate).startswith(str(expected_root)):
                            artifact_file_path = candidate
                        else:
                            artifact_file_path = expected_root / candidate.name
                    else:
                        artifact_file_path = (
                            expected_root / f"screener_{screener_id}_result.json"
                        )
                    artifact: Optional[dict[str, Any]]
                    if (
                        str(artifact_file_path).startswith(str(expected_root))
                        and artifact_file_path.exists()
                    ):
                        try:
                            payload = json.loads(
                                artifact_file_path.read_text(encoding="utf-8")
                            )
                        except (OSError, json.JSONDecodeError):
                            payload = None
                        artifact = payload if isinstance(payload, dict) else None
                    else:
                        artifact = None

                    if artifact is None:
                        missing_item: dict[str, Any] = {
                            "screener_id": screener_id,
                            "name": screener_name,
                            "result": None,
                            "message": "无法判断",
                            "explain_cn": "无法判断：当日运行记录缺失，且对应结果文件缺失。",
                            "reasons": [
                                "当日运行记录缺失，且批量运行结果文件中对应的结果文件缺失。"
                            ],
                            "evidence": [
                                f"日期：{target_date}",
                                f"筛选器：{screener_name}",
                                "证据来源：批量运行汇总",
                            ],
                        }
                        if universe_base.get("result") is False:
                            base_reasons = universe_base.get("reasons")
                            if isinstance(base_reasons, list) and base_reasons:
                                missing_item["result"] = False
                                missing_item["message"] = "未通过"
                                missing_item["reasons"] = [
                                    f"基础过滤：{str(reason)}"
                                    for reason in base_reasons
                                ]
                            base_evidence = universe_base.get("evidence")
                            if isinstance(base_evidence, list):
                                missing_item["evidence"] = list(
                                    missing_item.get("evidence", [])
                                ) + [f"基础过滤证据：{str(ev)}" for ev in base_evidence]
                        if debug:
                            missing_item["_debug"] = {
                                "screener_id": screener_id,
                                "run_status": str(ref.get("status", "unknown")),
                                "requested_at": str(ref.get("requested_at", "")),
                                "run_source": "bulk_run_result",
                            }
                        screener_items.append(missing_item)
                        continue

                    artifact_status = str(artifact.get("status", ""))
                    picks = artifact.get("picks")
                    parameters_source = "config"
                    artifact_parameters = artifact.get("parameters")
                    if isinstance(artifact_parameters, dict):
                        screener_parameters = self._deep_merge_dicts(
                            screener_parameters, artifact_parameters
                        )
                        parameters_source = "artifact"
                    if artifact_status == "pending_implementation":
                        passed = None
                    elif isinstance(picks, list):
                        passed = normalized_code in {str(item) for item in picks}
                    else:
                        passed = None

                    passed, reasons, extra_evidence = (
                        self._apply_universe_filters_to_screener_result(
                            passed=passed,
                            artifact_status=artifact_status,
                            universe_base=universe_base,
                            stock_code=normalized_code,
                            screener_parameters=screener_parameters,
                            parameters_source=parameters_source,
                        )
                    )

                    item: dict[str, Any] = {
                        "screener_id": screener_id,
                        "name": screener_name,
                        "result": passed,
                        "message": _tri_state_message(passed),
                        "explain_cn": (
                            "通过：当日筛选结果包含该股票。"
                            if passed is True
                            else (
                                "未通过：" + (_screener_failure_detail(screener_id) or "当日筛选结果未包含该股票。")
                                if passed is False
                                else "无法判断：筛选器结果结构不完整或尚未实现。"
                            )
                        ),
                        "reasons": reasons,
                        "evidence": [
                            f"日期：{target_date}",
                            f"筛选器：{screener_name}",
                            "证据来源：批量运行汇总",
                            f"结果状态：{artifact_status or 'unknown'}",
                            f"当日命中数量：{len(picks) if isinstance(picks, list) else 'unknown'}",
                            *extra_evidence,
                        ],
                    }
                    evidence_table: list[dict[str, Any]] = [
                        _build_bool_row("是否命中筛选器", passed=passed, note="根据当日运行结果判断"),
                    ]
                    hit_count_value: object = None
                    if isinstance(picks, list):
                        hit_count_value = len(picks)
                    evidence_table.append(
                        _build_threshold_row(
                            "当日命中数量",
                            current=hit_count_value if hit_count_value is not None else "未知",
                            threshold="—",
                            ok=None,
                            note="用于理解筛选器的当日命中规模",
                        )
                    )
                    for reason in reasons:
                        if not isinstance(reason, str):
                            continue
                        if "市值过滤未通过" in reason and "<" in reason and "阈值" in reason:
                            evidence_table.append(
                                _build_threshold_row(
                                    "流通市值",
                                    current="—",
                                    threshold="—",
                                    ok=False,
                                    note=str(reason),
                                )
                            )
                    item["evidence_table"] = evidence_table
                    if debug:
                        item["_debug"] = {
                            "screener_id": screener_id,
                            "run_status": str(ref.get("status", "unknown")),
                            "requested_at": str(ref.get("requested_at", "")),
                            "picks": picks if isinstance(picks, list) else None,
                            "parameters": (
                                artifact.get("parameters")
                                if isinstance(artifact.get("parameters"), dict)
                                else None
                            ),
                            "run_source": "bulk_run_result",
                        }
                    screener_items.append(item)
                    if passed is True:
                        app: dict[str, Any] = {
                            "screener_id": screener_id,
                            "name": screener_name,
                            "evidence": [
                                f"筛选器：{screener_name}",
                                f"日期：{target_date}",
                            ],
                        }
                        if debug:
                            app["_debug"] = {
                                "screener_id": screener_id,
                                "requested_at": str(ref.get("requested_at", "")),
                                "run_source": "bulk_run_result",
                            }
                        appearances.append(app)
                    continue

                item = {
                    "screener_id": screener_id,
                    "name": screener_name,
                    "result": None,
                    "message": "无法判断",
                    "explain_cn": "无法判断：当日该筛选器尚未运行。",
                    "reasons": ["当日该筛选器尚未运行。"],
                    "evidence": [f"日期：{target_date}", f"筛选器：{screener_name}"],
                }
                if universe_base.get("result") is False:
                    base_reasons = universe_base.get("reasons")
                    if isinstance(base_reasons, list) and base_reasons:
                        item["result"] = False
                        item["message"] = "未通过"
                        item["reasons"] = [
                            f"基础过滤：{str(reason)}" for reason in base_reasons
                        ]
                    base_evidence = universe_base.get("evidence")
                    if isinstance(base_evidence, list):
                        item["evidence"] = list(item.get("evidence", [])) + [
                            f"基础过滤证据：{str(ev)}" for ev in base_evidence
                        ]
                if debug:
                    item["_debug"] = {"screener_id": screener_id, "has_run": False}
                item["evidence_table"] = [
                    _build_bool_row("是否命中筛选器", passed=None, note="当日该筛选器尚未运行"),
                ]
                screener_items.append(item)
                continue

            artifact = read_screener_run_artifact(
                project_root=self.project_root,
                target_date=target_date,
                screener_id=screener_id,
            )
            if artifact is None:
                ref = bulk_run_refs.get(screener_id)
                if ref is not None:
                    artifact_file_path = Path(str(ref.get("artifact_path", "")))
                    expected_root = (
                        self.project_root / "var/artifacts/screener_runs" / target_date
                    )
                    if (
                        str(artifact_file_path).startswith(str(expected_root))
                        and artifact_file_path.exists()
                    ):
                        try:
                            payload = json.loads(
                                artifact_file_path.read_text(encoding="utf-8")
                            )
                        except (OSError, json.JSONDecodeError):
                            payload = None
                        if isinstance(payload, dict):
                            artifact = payload

                if artifact is None:
                    item = {
                        "screener_id": screener_id,
                        "name": screener_name,
                        "result": None,
                        "message": "无法判断",
                        "explain_cn": "无法判断：当日运行记录存在，但结果文件缺失。",
                        "reasons": ["当日运行记录存在，但结果文件缺失。"],
                        "evidence": [
                            f"日期：{target_date}",
                            f"筛选器：{screener_name}",
                        ],
                    }
                    if universe_base.get("result") is False:
                        base_reasons = universe_base.get("reasons")
                        if isinstance(base_reasons, list) and base_reasons:
                            item["result"] = False
                            item["message"] = "未通过"
                            item["reasons"] = [
                                f"基础过滤：{str(reason)}" for reason in base_reasons
                            ]
                        base_evidence = universe_base.get("evidence")
                        if isinstance(base_evidence, list):
                            item["evidence"] = list(item.get("evidence", [])) + [
                                f"基础过滤证据：{str(ev)}" for ev in base_evidence
                            ]
                    if debug:
                        item["_debug"] = {
                            "screener_id": screener_id,
                            "run_status": record.status,
                            "requested_at": record.requested_at,
                            "artifact_path": record.artifact_path,
                            "artifact_missing": True,
                        }
                    item["evidence_table"] = [
                        _build_bool_row("是否命中筛选器", passed=None, note="当日结果文件缺失"),
                    ]
                    screener_items.append(item)
                    continue

            artifact_status = str(artifact.get("status", ""))
            picks = artifact.get("picks")
            parameters_source = "config"
            artifact_parameters = artifact.get("parameters")
            if isinstance(artifact_parameters, dict):
                screener_parameters = self._deep_merge_dicts(
                    screener_parameters, artifact_parameters
                )
                parameters_source = "artifact"
            if artifact_status == "pending_implementation":
                passed = None
            elif isinstance(picks, list):
                passed = normalized_code in {str(item) for item in picks}
            else:
                passed = None

            passed, reasons, extra_evidence = (
                self._apply_universe_filters_to_screener_result(
                    passed=passed,
                    artifact_status=artifact_status,
                    universe_base=universe_base,
                    stock_code=normalized_code,
                    screener_parameters=screener_parameters,
                    parameters_source=parameters_source,
                )
            )

            item = {
                "screener_id": screener_id,
                "name": screener_name,
                "result": passed,
                "message": _tri_state_message(passed),
                "explain_cn": (
                    "通过：当日筛选结果包含该股票。"
                    if passed is True
                    else (
                        "未通过：" + (_screener_failure_detail(screener_id) or "当日筛选结果未包含该股票。")
                        if passed is False
                        else "无法判断：筛选器结果结构不完整或尚未实现。"
                    )
                ),
                "reasons": reasons,
                "evidence": [
                    f"日期：{target_date}",
                    f"筛选器：{screener_name}",
                    f"结果状态：{artifact_status or 'unknown'}",
                    f"当日命中数量：{len(picks) if isinstance(picks, list) else 'unknown'}",
                    *extra_evidence,
                ],
            }
            evidence_table: list[dict[str, Any]] = [
                _build_bool_row("是否命中筛选器", passed=passed, note="根据当日运行结果判断"),
            ]
            hit_count_value: object = None
            if isinstance(picks, list):
                hit_count_value = len(picks)
            evidence_table.append(
                _build_threshold_row(
                    "当日命中数量",
                    current=hit_count_value if hit_count_value is not None else "未知",
                    threshold="—",
                    ok=None,
                    note="用于理解筛选器的当日命中规模",
                )
            )
            item["evidence_table"] = evidence_table
            if debug:
                item["_debug"] = {
                    "screener_id": screener_id,
                    "run_status": record.status,
                    "requested_at": record.requested_at,
                    "artifact_path": record.artifact_path,
                    "picks": picks if isinstance(picks, list) else None,
                    "parameters": (
                        artifact.get("parameters")
                        if isinstance(artifact.get("parameters"), dict)
                        else None
                    ),
                }
            screener_items.append(item)

            if passed is True:
                app = {
                    "screener_id": screener_id,
                    "name": screener_name,
                    "evidence": [f"筛选器：{screener_name}", f"日期：{target_date}"],
                }
                if debug:
                    app["_debug"] = {
                        "screener_id": screener_id,
                        "artifact_path": record.artifact_path,
                        "requested_at": record.requested_at,
                    }
                appearances.append(app)

        any_true = any(item["result"] is True for item in screener_items)
        any_false = any(item["result"] is False for item in screener_items)
        present: Optional[bool]
        if any_true:
            present = True
        elif any_false:
            present = False
        else:
            present = None

        presence_message = _tri_state_message(present)
        presence_reasons: list[str] = []
        if present is True:
            names = [item["name"] for item in appearances]
            if names:
                presence_reasons.append(
                    "该股票当日通过以下筛选器：" + "、".join(names) + "。"
                )
            else:
                presence_reasons.append("该股票当日至少通过 1 个筛选器。")
        elif present is False:
            presence_reasons.append("该股票当日未通过任何已可判定的筛选器。")
        else:
            presence_reasons.append(
                "当日缺少可判定的筛选结果，无法判断是否通过任意筛选器。"
            )

        if universe_base.get("result") is False and present is not True:
            present = False
            presence_message = "未通过"
            base_reasons = universe_base.get("reasons")
            if isinstance(base_reasons, list) and base_reasons:
                presence_reasons = [
                    "基础过滤未通过：" + "；".join(str(item) for item in base_reasons)
                ]

        universe_evidence_table: list[dict[str, Any]] = [
            _build_bool_row(
                "基础过滤",
                passed=bool(universe_base.get("result")) if universe_base.get("result") in {True, False} else None,
                note="基础过滤用于排除明显不合规标的（例如市值阈值等）",
            )
        ]
        for item in universe_base.get("evidence", []):
            if not isinstance(item, str):
                continue
            if item.startswith("circulating_market_cap："):
                raw_value = item.split("：", 1)[-1].strip()
                universe_evidence_table.append(
                    _build_threshold_row(
                        "流通市值",
                        current=raw_value,
                        threshold="—",
                        ok=None,
                        note="来自行情库字段 circulating_market_cap",
                    )
                )

        universe_base["evidence_table"] = universe_evidence_table

        tracking_items: list[dict[str, Any]] = []
        tracking_checked = 0
        tracking_hit = 0

        ledger_path, artifact_path = self._factor_matrix_paths(target_date=target_date)
        factor_requested_at: Optional[str] = None
        if ledger_path.exists():
            try:
                ledger_payload = json.loads(ledger_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                ledger_payload = None
            if isinstance(ledger_payload, dict):
                ra = ledger_payload.get("requested_at")
                factor_requested_at = str(ra) if isinstance(ra, str) and ra.strip() else None
        if artifact_path.exists():
            try:
                fm_payload = json.loads(artifact_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                fm_payload = None
            if isinstance(fm_payload, dict):
                tiers = fm_payload.get("tiers")
                if isinstance(tiers, dict):
                    tier_labels = {"ge_80": ">=80", "ge_70": ">=70", "ge_60": ">=60"}
                    for tier_key, tier_label in tier_labels.items():
                        tracking_checked += 1
                        items = tiers.get(tier_key)
                        if not isinstance(items, list):
                            continue
                        hit_candidate = next(
                            (
                                item
                                for item in items
                                if isinstance(item, dict)
                                and _normalize_code(item.get("stock_code")) == _normalize_code(normalized_code)
                            ),
                            None,
                        )
                        if hit_candidate is None:
                            continue
                        tracking_hit += 1
                        subscores = hit_candidate.get("subscores") if isinstance(hit_candidate.get("subscores"), dict) else {}
                        score = subscores.get("overall", hit_candidate.get("certainty"))
                        certainty = hit_candidate.get("certainty", score)
                        if certainty_value is None and isinstance(certainty, (int, float)):
                            certainty_value = float(certainty)
                            certainty_source = "quant_matrix"
                        evidence = hit_candidate.get("evidence") if isinstance(hit_candidate.get("evidence"), dict) else {}
                        ev_lines = _pick_numeric_evidence(evidence.get("technical_evidence"), 2)
                        tracking_items.append(
                            {
                                "list_id": f"quant__{tier_key}",
                                "list_name": f"量化选股（{tier_label}）",
                                "list_type": "quant_matrix",
                                "result": True,
                                "observed_at": factor_requested_at,
                                "reasons": ["来源：量化矩阵候选（当日快照）"],
                                "evidence_table": [
                                    _build_threshold_row("评分", current=score, threshold=tier_label, ok=True, note="量化矩阵候选档位"),
                                    _build_threshold_row("确定性", current=certainty, threshold="—", ok=None, note="量化矩阵输出"),
                                    _build_threshold_row("关键证据", current="；".join(ev_lines) if ev_lines else "—", threshold="—", ok=None, note="来自量化矩阵 technical_evidence"),
                                ],
                            }
                        )

        def _append_lab_tracking(lab_id: str, list_name: str, extractor) -> None:
            nonlocal tracking_checked, tracking_hit
            tracking_checked += 1
            lab_ledger, lab_artifact = self._lab_run_paths(target_date=target_date, lab_id=lab_id)
            if not lab_ledger.exists() or not lab_artifact.exists():
                return
            try:
                ledger_payload = json.loads(lab_ledger.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                ledger_payload = None
            try:
                artifact_payload = json.loads(lab_artifact.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                artifact_payload = None
            if not isinstance(artifact_payload, dict):
                return
            requested_at = (
                str(ledger_payload.get("requested_at")).strip()
                if isinstance(ledger_payload, dict) and isinstance(ledger_payload.get("requested_at"), str)
                else None
            )
            members = extractor(artifact_payload)
            if not isinstance(members, list):
                return
            normalized_members = {_normalize_code(item) for item in members if _normalize_code(item)}
            if _normalize_code(normalized_code) not in normalized_members:
                return
            tracking_hit += 1
            tracking_items.append(
                {
                    "list_id": f"lab__{lab_id}",
                    "list_name": list_name,
                    "list_type": "lab_output",
                    "result": True,
                    "observed_at": requested_at,
                    "reasons": ["来源：实验室当日运行输出"],
                    "evidence_table": [
                        _build_bool_row("是否在输出池中", passed=True, note=f"{list_name} 当日输出包含该标的"),
                        _build_threshold_row("输出池规模", current=len(normalized_members), threshold="—", ok=None, note="用于理解当日输出范围"),
                    ],
                }
            )

        def _extract_five_flags(artifact_payload: dict[str, Any]) -> list[str]:
            artifacts = artifact_payload.get("artifacts")
            if not isinstance(artifacts, dict):
                return []
            scan = artifacts.get("five_flags_scan_results")
            if not isinstance(scan, dict):
                return []
            pool = scan.get("pool")
            return list(pool) if isinstance(pool, list) else []

        def _extract_cup_handle(artifact_payload: dict[str, Any]) -> list[str]:
            artifacts = artifact_payload.get("artifacts")
            if not isinstance(artifacts, dict):
                return []
            report = artifacts.get("cup_handle_daily_report")
            if not isinstance(report, dict):
                return []
            candidates = report.get("candidates")
            return list(candidates) if isinstance(candidates, list) else []

        _append_lab_tracking("five_flags_lab", "老鸭头五图（观察池）", _extract_five_flags)
        _append_lab_tracking("cup_handle_lab", "杯柄（观察池）", _extract_cup_handle)

        manual_root = self.project_root / "var/artifacts/pools" / target_date
        if manual_root.exists():
            for path in sorted(manual_root.glob("pool_manual__*_members.json")):
                tracking_checked += 1
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                if not isinstance(payload, dict):
                    continue
                members = payload.get("members")
                if not isinstance(members, list):
                    continue
                normalized_members = {_normalize_code(item) for item in members if _normalize_code(item)}
                if _normalize_code(normalized_code) not in normalized_members:
                    continue
                tracking_hit += 1
                requested_at = payload.get("requested_at")
                tracking_items.append(
                    {
                        "list_id": str(payload.get("pool_id", "")) or "manual__unknown",
                        "list_name": str(payload.get("display_name", "")) or "手工监控池",
                        "list_type": "manual_pool",
                        "result": True,
                        "observed_at": str(requested_at) if isinstance(requested_at, str) and str(requested_at).strip() else None,
                        "reasons": ["来源：手工录入监控池"],
                        "evidence_table": [
                            _build_bool_row("是否在监控池中", passed=True, note="手工录入/维护的观察池"),
                        ],
                    }
                )

        hot_presence: dict[str, Any] = {
            "status": "missing",
            "result": None,
            "message": "无法判断",
            "matches": [],
        }
        hot_certainty: Optional[float] = None
        try:
            hot = self.lowfreq_hot_sectors_view(target_date=target_date)
            sectors = hot.get("sectors") if isinstance(hot, dict) else None
            matches: list[dict[str, Any]] = []
            if isinstance(sectors, list):
                for sec in sectors:
                    if not isinstance(sec, dict):
                        continue
                    sec_name = str(sec.get("name") or "").strip()
                    sec_code = str(sec.get("code") or "").strip()
                    for role_key, role_label in (("leaders", "龙头"), ("middle", "中军"), ("followers", "跟随")):
                        items = sec.get(role_key)
                        if not isinstance(items, list):
                            continue
                        for s in items:
                            if not isinstance(s, dict):
                                continue
                            if _normalize_code(s.get("code")) != _normalize_code(normalized_code):
                                continue
                            matches.append(
                                {
                                    "sector": sec_name or sec_code or "未知板块",
                                    "sector_code": sec_code or None,
                                    "role": role_label,
                                    "buy_signal": (
                                        bool(s.get("buy_signal")) if s.get("buy_signal") in {True, False} else None
                                    ),
                                    "suggested_entry": s.get("suggested_entry"),
                                }
                            )
                            if hot_certainty is None and isinstance(s.get("certainty"), (int, float)):
                                hot_certainty = float(s.get("certainty"))
            hot_presence = {
                "status": "ok",
                "result": True if matches else False,
                "message": ("命中热门板块 Top5" if matches else "未命中热门板块 Top5"),
                "matches": matches,
            }
        except Exception:
            hot_presence = {"status": "error", "result": None, "message": "热门板块不可用", "matches": []}

        if certainty_value is None and hot_certainty is not None:
            certainty_value = hot_certainty
            certainty_source = "hot_sectors"

        duck_payload: dict[str, Any] = {
            "status": "missing",
            "passed": None,
            "reason": "unavailable",
            "explain_cn": "无法判断",
            "details": {},
        }
        try:
            engine = self._lowfreq_engine_v16()
            raw = engine.check_weekly_duck_head(
                _normalize_code(normalized_code), date.fromisoformat(target_date)
            )
            passed = (
                bool(raw.get("passed"))
                if isinstance(raw, dict) and raw.get("passed") in {True, False}
                else None
            )
            reason = str(raw.get("reason") or "").strip() if isinstance(raw, dict) else ""
            reason_cn = {
                "disabled": "已关闭（策略参数禁用）",
                "weekly_insufficient": "周线数据不足",
                "weekly_ma_unavailable": "均线不可用（数据不足）",
                "weekly_ma_not_bull": "周线均线未形成多头排列",
                "weekly_turn_not_confirmed": "周线拐头未确认",
                "weekly_pullback_missing": "回踩确认不足（未触及/回踩 MA10）",
                "weekly_close_below_ma10": "收盘价低于 MA10",
                "weekly_breakout_not_confirmed": "突破未确认（未超过近期高点）",
                "weekly_overextended": "过度乖离（距离 MA15 过远）",
                "weekly_duck_head_confirmed": "周线老鸭头形态确认",
            }.get(reason, reason or "未知")
            duck_payload = {
                "status": "ok",
                "passed": passed,
                "reason": reason or None,
                "explain_cn": (
                    ("通过：" + reason_cn)
                    if passed is True
                    else ("未通过：" + reason_cn)
                    if passed is False
                    else ("无法判断：" + reason_cn)
                ),
                "details": raw if isinstance(raw, dict) else {},
            }
        except Exception:
            duck_payload = {
                "status": "error",
                "passed": None,
                "reason": "error",
                "explain_cn": "无法判断",
                "details": {},
            }

        return {
            "_meta": {
                "status": "ok",
            },
            "target_date": target_date,
            "stock_code": normalized_code,
            "checks": {
                "universe_filters": universe_base,
                "screeners": {"items": screener_items},
                "hot_sectors": hot_presence,
                "weekly_duck_head": duck_payload,
                "certainty": {
                    "value": certainty_value,
                    "source": certainty_source,
                    "message": (
                        "来自量化矩阵候选"
                        if certainty_source == "quant_matrix"
                        else "来自热门板块 Top5"
                        if certainty_source == "hot_sectors"
                        else "暂无可用确定性来源"
                    ),
                },
                "picks_presence": {
                    "result": present,
                    "message": presence_message,
                    "reasons": presence_reasons,
                    "appearances": appearances,
                },
                "tracking_lists": {
                    "status": "ok",
                    "result": True if tracking_hit > 0 else False,
                    "message": f"命中观察池 {tracking_hit}/{tracking_checked}" if tracking_checked else "未检查观察池（无可用产物）",
                    "checked_count": tracking_checked,
                    "hit_count": tracking_hit,
                    "items": tracking_items,
                },
            },
        }

    def seed_stock_db_view(
        self,
        *,
        source_db_path: str,
        force: bool,
        requested_by: str,
        rebuild_trading_calendar: bool = True,
        strict: bool = True,
        normalize_volume_to: str = "share",
    ) -> dict[str, Any]:
        source_path = Path(source_db_path).expanduser()
        if not source_path.exists() or not source_path.is_file():
            raise ApiError(
                status_code=HTTPStatus.BAD_REQUEST,
                code="invalid_source_db_path",
                message="source_db_path must exist and be a file",
                details={"source_db_path": _safe_ref_path(str(source_path))},
            )

        dest_path = self._stock_db_default_path
        expected_root = self.project_root / "var/db"
        if not str(dest_path).startswith(str(expected_root)):
            raise ApiError(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                code="invalid_dest_db_path",
                message="dest stock db path is outside the expected var/db directory",
                details={
                    "dest_db_path": _safe_ref_path(str(dest_path)),
                    "expected_root": _safe_ref_path(str(expected_root)),
                },
            )

        if dest_path.exists() and not force:
            raise ApiError(
                status_code=HTTPStatus.CONFLICT,
                code="dest_db_exists",
                message="destination stock db already exists; set force=true to overwrite",
                details={"dest_db_path": _safe_ref_path(str(dest_path))},
            )

        dest_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = dest_path.with_suffix(".db.tmp")
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError as exc:
                logger.debug("failed to remove stale tmp db: %s", exc)

        shutil.copy2(str(source_path), str(tmp_path))

        conn: Optional[sqlite3.Connection] = None
        try:
            conn = sqlite3.connect(str(tmp_path))
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='daily_prices'"
            )
            has_daily_prices = cursor.fetchone() is not None
        except Exception as exc:
            raise ApiError(
                status_code=HTTPStatus.BAD_REQUEST,
                code="invalid_seed_db",
                message=f"seed db is not a usable sqlite database (see server logs)",
                details={"tmp_path": _safe_ref_path(str(tmp_path))},
            )
        finally:
            if conn is not None:
                try:
                    conn.close()
                except sqlite3.Error as exc:
                    logger.debug("failed to close seed db connection: %s", exc)

        if not has_daily_prices:
            raise ApiError(
                status_code=HTTPStatus.BAD_REQUEST,
                code="invalid_seed_db_schema",
                message="seed db is missing required table: daily_prices",
                details={"tmp_path": _safe_ref_path(str(tmp_path))},
            )

        units_before = self.validate_stock_db_view(
            sqlite_db_path=str(tmp_path), sample_limit=200
        )
        if strict and str(units_before.get("status")) != "ok":
            raise ApiError(
                status_code=HTTPStatus.BAD_REQUEST,
                code="invalid_seed_db_units",
                message="seed db failed unit validation; fix units before importing",
                details={"units_report": units_before},
            )

        normalization_actions: list[str] = []
        volume_unit_before = (
            units_before.get("recommended_units", {}).get("volume", {}).get("unit")
            if isinstance(units_before.get("recommended_units"), dict)
            else None
        )
        if normalize_volume_to not in {"share", "keep"}:
            raise ApiError(
                status_code=HTTPStatus.BAD_REQUEST,
                code="invalid_normalize_volume_to",
                message="normalize_volume_to must be 'share' or 'keep'",
                details={"normalize_volume_to": normalize_volume_to},
            )
        if normalize_volume_to == "share" and volume_unit_before == "lot_100_shares":
            self._normalize_daily_prices_volume_to_shares(db_path=tmp_path)
            normalization_actions.append(
                "normalized daily_prices.volume from lot(1=100 shares) to shares by multiplying 100"
            )

        units_after = self.validate_stock_db_view(
            sqlite_db_path=str(tmp_path), sample_limit=200
        )
        if strict and normalize_volume_to == "share":
            volume_unit_after = (
                units_after.get("recommended_units", {}).get("volume", {}).get("unit")
                if isinstance(units_after.get("recommended_units"), dict)
                else None
            )
            if volume_unit_after not in {"share", None}:
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="seed_db_normalization_failed",
                    message="failed to normalize volume to shares",
                    details={
                        "volume_unit_before": volume_unit_before,
                        "volume_unit_after": volume_unit_after,
                        "normalization_actions": normalization_actions,
                    },
                )

        if dest_path.exists():
            try:
                dest_path.unlink()
            except Exception as exc:
                raise ApiError(
                    status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                    code="dest_db_unlink_failed",
                    message=f"failed to overwrite existing destination db (see server logs)",
                    details={"dest_db_path": _safe_ref_path(str(dest_path))},
                )
        tmp_path.replace(dest_path)

        trading_calendar_payload: Optional[dict[str, Any]] = None
        if rebuild_trading_calendar:
            trading_calendar_payload = self.rebuild_trading_calendar_view(
                sqlite_db_path=str(dest_path),
                table="daily_prices",
                date_column="trade_date",
                requested_by=requested_by,
            )["trading_calendar"]

        stat = dest_path.stat()
        return {
            "_meta": {"status": "ok"},
            "source_db_path": _safe_ref_path(str(source_path)),
            "dest_db_path": _safe_ref_path(str(dest_path)),
            "dest_db_size_bytes": int(stat.st_size),
            "dest_db_mtime": time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", time.gmtime(stat.st_mtime)
            ),
            "units_validation": {
                "before": units_before,
                "after": units_after,
                "normalization_actions": normalization_actions,
                "normalize_volume_to": normalize_volume_to,
            },
            "trading_calendar": trading_calendar_payload,
        }

    @staticmethod
    def _normalize_daily_prices_volume_to_shares(
        *, db_path: Path, trade_date: Optional[str] = None
    ) -> int:
        try:
            conn = sqlite3.connect(str(db_path), timeout=30.0)
        except Exception as exc:
            raise ApiError(
                status_code=HTTPStatus.BAD_REQUEST,
                code="invalid_db",
                message=f"failed to open sqlite db for normalization (see server logs)",
                details={"db_path": _safe_ref_path(str(db_path))},
            )
        try:
            try:
                conn.execute("PRAGMA busy_timeout = 30000")
            except sqlite3.Error:
                pass

            where = (
                "WHERE trade_date = ? AND volume IS NOT NULL AND volume > 0 "
                "AND amount IS NOT NULL AND amount > 0 AND close IS NOT NULL AND close > 0 "
                "AND ABS((amount / (volume * 100.0)) - close) < ABS((amount / volume) - close)"
                if trade_date
                else "WHERE volume IS NOT NULL AND volume > 0 "
                "AND amount IS NOT NULL AND amount > 0 AND close IS NOT NULL AND close > 0 "
                "AND ABS((amount / (volume * 100.0)) - close) < ABS((amount / volume) - close)"
            )
            params: tuple[object, ...] = (trade_date,) if trade_date else ()

            changed = 0
            for attempt in range(6):
                try:
                    cursor = conn.cursor()
                    cursor.execute(
                        f"UPDATE daily_prices SET volume = volume * 100 {where}", params
                    )
                    cursor.execute("SELECT changes()")
                    changed = int(cursor.fetchone()[0] or 0)
                    conn.commit()
                    break
                except sqlite3.OperationalError as op_exc:
                    msg = str(op_exc).lower()
                    if "database is locked" not in msg and "database locked" not in msg:
                        raise
                    time.sleep(0.2 * (2**attempt))
            return int(changed)
        except Exception as exc:
            try:
                conn.rollback()
            except sqlite3.Error as rollback_exc:
                logger.debug(
                    "failed to rollback after normalization error: %s", rollback_exc
                )
            raise ApiError(
                status_code=HTTPStatus.BAD_REQUEST,
                code="normalization_failed",
                message=f"failed to normalize daily_prices.volume (see server logs)",
                details={"db_path": _safe_ref_path(str(db_path))},
            )
        finally:
            conn.close()

    @staticmethod
    def _normalize_daily_prices_volume_to_shares_in_conn(
        *, conn: sqlite3.Connection, trade_date: Optional[str] = None
    ) -> int:
        where = (
            "WHERE trade_date = ? AND volume IS NOT NULL AND volume > 0 "
            "AND amount IS NOT NULL AND amount > 0 AND close IS NOT NULL AND close > 0 "
            "AND ABS((amount / (volume * 100.0)) - close) < ABS((amount / volume) - close)"
            if trade_date
            else "WHERE volume IS NOT NULL AND volume > 0 "
            "AND amount IS NOT NULL AND amount > 0 AND close IS NOT NULL AND close > 0 "
            "AND ABS((amount / (volume * 100.0)) - close) < ABS((amount / volume) - close)"
        )
        params: tuple[object, ...] = (trade_date,) if trade_date else ()
        cursor = conn.cursor()
        cursor.execute(f"UPDATE daily_prices SET volume = volume * 100 {where}", params)
        cursor.execute("SELECT changes()")
        return int(cursor.fetchone()[0] or 0)

    def validate_stock_db_view(
        self, *, sqlite_db_path: str, sample_limit: int = 200
    ) -> dict[str, Any]:
        db_path = Path(sqlite_db_path).expanduser()
        if not db_path.exists() or not db_path.is_file():
            raise ApiError(
                status_code=HTTPStatus.BAD_REQUEST,
                code="invalid_db_path",
                message="sqlite_db_path must exist and be a file",
                details={"sqlite_db_path": "redacted"},
            )
        if not isinstance(sample_limit, int) or sample_limit <= 0:
            raise ApiError(
                status_code=HTTPStatus.BAD_REQUEST,
                code="invalid_sample_limit",
                message="sample_limit must be a positive integer",
                details={"sample_limit": sample_limit},
            )

        report = self._validate_units_in_stock_db(
            db_path=db_path, sample_limit=sample_limit
        )
        return report

    def sync_daily_prices_view(
        self,
        *,
        source_db_path: str,
        requested_by: str,
        dry_run: bool,
        rebuild_trading_calendar: bool = True,
        target_date: Optional[str] = None,
    ) -> dict[str, Any]:
        source_path = Path(source_db_path).expanduser()
        if not source_path.exists() or not source_path.is_file():
            raise ApiError(
                status_code=HTTPStatus.BAD_REQUEST,
                code="invalid_source_db_path",
                message="source_db_path must exist and be a file",
                details={"source_db_path": _safe_ref_path(str(source_path))},
            )
        if not requested_by.strip():
            raise ApiError(
                status_code=HTTPStatus.BAD_REQUEST,
                code="invalid_requested_by",
                message="requested_by must be a non-empty string",
            )
        if target_date is not None:
            if not isinstance(target_date, str) or not target_date.strip():
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_target_date",
                    message="target_date must be a non-empty string in YYYY-MM-DD format",
                    details={"target_date": target_date},
                )
            try:
                date.fromisoformat(target_date)
            except ValueError:
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_target_date",
                    message=f"invalid target_date: {target_date}",
                    details={"target_date": target_date},
                )

        dest_path = self._stock_db_default_path
        if not dest_path.exists():
            raise ApiError(
                status_code=HTTPStatus.SERVICE_UNAVAILABLE,
                code="dest_db_missing",
                message="destination stock db is missing; seed it first",
                details={
                    "dest_db_path": _safe_ref_path(str(dest_path)),
                    "hint": "POST /api/data-control/seed-stock-db",
                },
            )

        conn: Optional[sqlite3.Connection] = None
        inserted_count = 0
        would_insert_count: Optional[int] = None
        dest_max_before: Optional[str] = None
        dest_max_after: Optional[str] = None
        source_max: Optional[str] = None

        try:
            conn = sqlite3.connect(str(dest_path))
            cursor = conn.cursor()
            cursor.execute("ATTACH DATABASE ? AS source", (str(source_path),))
            cursor.execute(
                "SELECT 1 FROM source.sqlite_master WHERE type='table' AND name='daily_prices'"
            )
            if cursor.fetchone() is None:
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_source_db_schema",
                    message="source db is missing required table: daily_prices",
                    details={"source_db_path": _safe_ref_path(str(source_path))},
                )

            cursor.execute("SELECT MAX(trade_date) FROM daily_prices")
            row = cursor.fetchone()
            dest_max_before = str(row[0]) if row and row[0] is not None else None
            cursor.execute("SELECT MAX(trade_date) FROM source.daily_prices")
            row = cursor.fetchone()
            source_max = str(row[0]) if row and row[0] is not None else None

            where_parts = [
                "NOT EXISTS (SELECT 1 FROM daily_prices d WHERE d.code = s.code AND d.trade_date = s.trade_date)"
            ]
            params: list[object] = []
            if target_date is not None:
                where_parts.insert(0, "s.trade_date = ?")
                params.append(target_date)
            elif dest_max_before is not None:
                where_parts.insert(0, "s.trade_date > ?")
                params.append(dest_max_before)
            where_clause = " AND ".join(where_parts)

            if dry_run:
                cursor.execute(
                    f"SELECT COUNT(1) FROM source.daily_prices s WHERE {where_clause}",
                    params,
                )
                would_insert_count = int(cursor.fetchone()[0] or 0)
                conn.rollback()
            else:
                cursor.execute(
                    "INSERT INTO daily_prices (code, trade_date, open, high, low, close, volume, amount, turnover, preclose, pct_change, updated_at) "
                    f"SELECT s.code, s.trade_date, s.open, s.high, s.low, s.close, s.volume, s.amount, s.turnover, s.preclose, s.pct_change, s.updated_at "
                    f"FROM source.daily_prices s WHERE {where_clause}",
                    params,
                )
                cursor.execute("SELECT changes()")
                inserted_count = int(cursor.fetchone()[0] or 0)
                conn.commit()

            cursor.execute("SELECT MAX(trade_date) FROM daily_prices")
            row = cursor.fetchone()
            dest_max_after = str(row[0]) if row and row[0] is not None else None
        except ApiError:
            raise
        except Exception as exc:
            if conn is not None:
                try:
                    conn.rollback()
                except sqlite3.Error as rollback_exc:
                    logger.debug("failed to rollback sync daily_prices: %s", rollback_exc)
            raise ApiError(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                code="sync_failed",
                message=f"failed to sync daily_prices (see server logs)",
                details={
                    "dest_db_path": _safe_ref_path(str(dest_path)),
                    "source_db_path": _safe_ref_path(str(source_path)),
                },
            )
        finally:
            if conn is not None:
                try:
                    conn.close()
                except sqlite3.Error as close_exc:
                    logger.debug("failed to close dest db connection: %s", close_exc)

        trading_calendar_payload: Optional[dict[str, Any]] = None
        if rebuild_trading_calendar and not dry_run:
            trading_calendar_payload = self.rebuild_trading_calendar_view(
                sqlite_db_path=str(dest_path),
                table="daily_prices",
                date_column="trade_date",
                requested_by=requested_by.strip(),
            )

        return {
            "_meta": {"status": "ok"},
            "sync": {
                "dry_run": bool(dry_run),
                "requested_by": requested_by.strip(),
                "source_db_path": _safe_ref_path(str(source_path)),
                "dest_db_path": _safe_ref_path(str(dest_path)),
                "target_date": target_date,
                "dest_max_trade_date_before": dest_max_before,
                "source_max_trade_date": source_max,
                "dest_max_trade_date_after": dest_max_after,
                "inserted_count": inserted_count,
                "would_insert_count": would_insert_count,
            },
            "trading_calendar": trading_calendar_payload,
        }

    @staticmethod
    def _ensure_daily_price_capture_tables(conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS daily_price_capture_batches (
                capture_batch_id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                target_date TEXT NOT NULL,
                trade_date TEXT,
                capture_status TEXT NOT NULL,
                calendar_source TEXT,
                calendar_is_trading_day INTEGER,
                requested INTEGER NOT NULL,
                quotes_parsed INTEGER NOT NULL,
                captured_rows INTEGER NOT NULL,
                missing_codes_count INTEGER NOT NULL,
                coverage_close REAL,
                coverage_open REAL,
                coverage_amount REAL,
                coverage_turnover REAL,
                warning_reason TEXT,
                error_reason TEXT,
                metadata_json TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS daily_price_capture_rows (
                capture_batch_id TEXT NOT NULL,
                source TEXT NOT NULL,
                code TEXT NOT NULL,
                trade_date TEXT NOT NULL,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume REAL,
                amount REAL,
                turnover REAL,
                preclose REAL,
                pct_change REAL,
                row_status TEXT NOT NULL,
                metadata_json TEXT,
                created_at TEXT NOT NULL,
                PRIMARY KEY (capture_batch_id, code, trade_date)
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_daily_price_capture_batches_created_at "
            "ON daily_price_capture_batches(created_at DESC)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_daily_price_capture_batches_source_target "
            "ON daily_price_capture_batches(source, target_date DESC, created_at DESC)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_daily_price_capture_rows_batch "
            "ON daily_price_capture_rows(capture_batch_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_daily_price_capture_rows_code_date "
            "ON daily_price_capture_rows(code, trade_date)"
        )

    @staticmethod
    def _ensure_daily_price_publish_batch_table(conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS daily_price_publish_batches (
                batch_id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                target_date TEXT NOT NULL,
                trade_date TEXT,
                publish_status TEXT NOT NULL,
                quality_gate_passed INTEGER,
                quality_gate_reason TEXT,
                warning_reason TEXT,
                calendar_source TEXT,
                calendar_is_trading_day INTEGER,
                requested INTEGER NOT NULL,
                quotes_parsed INTEGER NOT NULL,
                db_upserted INTEGER NOT NULL,
                missing_codes_count INTEGER NOT NULL,
                coverage_close REAL,
                coverage_open REAL,
                coverage_amount REAL,
                coverage_turnover REAL,
                published_close REAL,
                published_amount REAL,
                published_turnover REAL,
                published_total_rows INTEGER,
                gate_reasons_json TEXT,
                warning_reasons_json TEXT,
                metadata_json TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_daily_price_publish_batches_created_at "
            "ON daily_price_publish_batches(created_at DESC)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_daily_price_publish_batches_source_target "
            "ON daily_price_publish_batches(source, target_date DESC, created_at DESC)"
        )

    @staticmethod
    def _calendar_membership(
        conn: sqlite3.Connection, trade_date: str
    ) -> tuple[str, Optional[bool]]:
        for table_name in ("trading_calendar_cache", "trading_calendar"):
            try:
                row = conn.execute(
                    f"SELECT 1 FROM {table_name} WHERE trade_date = ? LIMIT 1",
                    (trade_date,),
                ).fetchone()
            except sqlite3.Error:
                continue
            return table_name, bool(row)
        return "unavailable", None

    @staticmethod
    def _market_symbol(code: str) -> Optional[str]:
        code = (code or "").strip()
        if len(code) != 6 or not code.isdigit():
            return None
        if code.startswith("6"):
            return f"sh{code}"
        if code.startswith(("0", "3")):
            return f"sz{code}"
        return None

    @staticmethod
    def _safe_float(s: str) -> Optional[float]:
        s = (s or "").strip()
        if not s or s == "--":
            return None
        try:
            return float(s)
        except ValueError:
            return None

    @staticmethod
    def _parse_servertime_to_date_iso(v: str) -> Optional[str]:
        v = (v or "").strip()
        if len(v) < 8:
            return None
        ymd = v[:8]
        if not ymd.isdigit():
            return None
        return f"{ymd[0:4]}-{ymd[4:6]}-{ymd[6:8]}"

    @dataclass(frozen=True)
    class _TencentQuoteBar:
        code: str
        trade_date: str
        open: Optional[float]
        high: Optional[float]
        low: Optional[float]
        close: Optional[float]
        volume: Optional[float]
        amount: Optional[float]
        turnover: Optional[float]
        preclose: Optional[float]

    def _parse_tencent_quote_line(self, line: str) -> Optional[_TencentQuoteBar]:
        line = line.strip()
        if not line.startswith("v_") or "=\"" not in line:
            return None
        try:
            payload = line.split("=\"", 1)[1].rsplit("\"", 1)[0]
        except Exception:
            return None
        if not payload:
            return None
        parts = payload.split("~")
        if len(parts) < 6:
            return None

        code = (parts[2] or "").strip()
        close = self._safe_float(parts[3])
        preclose = self._safe_float(parts[4])
        open_px = self._safe_float(parts[5])
        volume = self._safe_float(parts[6]) if len(parts) > 6 else None

        servertime = parts[30].strip() if len(parts) > 30 else ""
        trade_date = self._parse_servertime_to_date_iso(servertime)
        if not trade_date:
            return None

        high = self._safe_float(parts[33]) if len(parts) > 33 else None
        low = self._safe_float(parts[34]) if len(parts) > 34 else None

        amount = None
        if len(parts) > 35 and parts[35]:
            segs = parts[35].split("/")
            if len(segs) >= 3:
                amount = self._safe_float(segs[2])

        return self._TencentQuoteBar(
            code=code,
            trade_date=trade_date,
            open=open_px,
            high=high,
            low=low,
            close=close,
            volume=volume,
            amount=amount,
            turnover=None,
            preclose=preclose,
        )

    @staticmethod
    def _compute_pct_change(preclose: Optional[float], close: Optional[float]) -> Optional[float]:
        if preclose and preclose > 0 and close is not None:
            return ((close / preclose) - 1.0) * 100.0
        return None

    def tencent_quote_meta_view(self, *, symbol: str = "sh000001", timeout_seconds: int = 10) -> dict[str, Any]:
        symbol = str(symbol or "").strip()
        if not symbol:
            raise ApiError(
                status_code=HTTPStatus.BAD_REQUEST,
                code="invalid_symbol",
                message="symbol must be a non-empty string",
                details={"symbol": symbol},
            )

        url = f"https://qt.gtimg.cn/q={symbol}"
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "*/*",
            },
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=int(timeout_seconds)) as resp:
            raw = resp.read()
        try:
            text = raw.decode("gbk", errors="ignore")
        except Exception:
            text = raw.decode("utf-8", errors="ignore")

        for seg in text.split(";"):
            seg = seg.strip()
            if not seg or not seg.startswith("v_") or "=\"" not in seg:
                continue
            try:
                payload = seg.split("=\"", 1)[1].rsplit("\"", 1)[0]
            except Exception:
                continue
            if not payload:
                continue
            parts = payload.split("~")
            servertime = parts[30].strip() if len(parts) > 30 else ""
            trade_date = self._parse_servertime_to_date_iso(servertime)
            bar = self._parse_tencent_quote_line(seg)
            if bar is None or trade_date is None:
                continue
            name = (parts[1] or "").strip() if len(parts) > 1 else ""
            close = self._safe_float(parts[3]) if len(parts) > 3 else None
            preclose = self._safe_float(parts[4]) if len(parts) > 4 else None
            open_px = self._safe_float(parts[5]) if len(parts) > 5 else None
            volume = self._safe_float(parts[6]) if len(parts) > 6 else None
            return {
                "status": "ok",
                "url": url,
                "symbol": symbol,
                "code": bar.code,
                "name": name,
                "servertime": servertime,
                "trade_date": trade_date,
                "close": close,
                "preclose": preclose,
                "open": open_px,
                "volume": volume,
            }

        return {
            "status": "error",
            "url": url,
            "symbol": symbol,
            "error": "no valid quote parsed",
        }

    def update_daily_prices_tencent_view(
        self,
        *,
        target_date: str,
        requested_by: str,
        chunk_size: int = 200,
        sleep_seconds: float = 0.2,
        timeout_seconds: int = 15,
        max_attempts: int = 3,
        min_close_coverage: float = 0.99,
        min_amount_coverage: float = 0.99,
        min_turnover_coverage: float = 0.0,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        if not requested_by.strip():
            raise ApiError(
                status_code=HTTPStatus.BAD_REQUEST,
                code="invalid_requested_by",
                message="requested_by must be a non-empty string",
            )
        try:
            date.fromisoformat(target_date)
        except ValueError:
            raise ApiError(
                status_code=HTTPStatus.BAD_REQUEST,
                code="invalid_date",
                message=f"invalid date: {target_date}",
                details={"date": target_date},
            )

        db_path = Path(
            os.environ.get("NEOTRADE3_STOCK_DB_PATH") or str(self._stock_db_default_path)
        ).expanduser()
        if not db_path.exists() or not db_path.is_file():
            raise ApiError(
                status_code=HTTPStatus.SERVICE_UNAVAILABLE,
                code="dest_db_missing",
                message="destination stock db is missing; seed it first",
                details={"dest_db_path": _safe_ref_path(str(db_path))},
            )

        conn = sqlite3.connect(str(db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        try:
            try:
                conn.execute("PRAGMA busy_timeout = 30000")
            except Exception:
                pass
            self._ensure_daily_price_capture_tables(conn)
            self._ensure_daily_price_publish_batch_table(conn)
            if not dry_run:
                try:
                    conn.commit()
                except Exception:
                    pass

            calendar_source, calendar_is_trading_day = self._calendar_membership(
                conn, target_date
            )

            today_cn = self._now_cn().date().isoformat()
            if str(target_date) != str(today_cn):
                if dry_run:
                    return {
                        "_meta": {"status": "ok"},
                        "tencent_update": {
                            "dry_run": True,
                            "requested_by": requested_by.strip(),
                            "target_date": target_date,
                            "trade_date": target_date,
                            "calendar_source": calendar_source,
                            "calendar_is_trading_day": calendar_is_trading_day,
                            "requested": 0,
                            "quotes_parsed": 0,
                            "missing_codes_count": 0,
                            "coverage": {
                                "close": 0.0,
                                "open": 0.0,
                                "amount": 0.0,
                                "turnover": 0.0,
                            },
                            "quality_gate": {
                                "passed": False,
                                "gate_reasons": ["dry_run_skipped"],
                                "min_close_coverage": float(min_close_coverage),
                                "min_amount_coverage": float(min_amount_coverage),
                                "min_turnover_coverage": float(min_turnover_coverage),
                            },
                            "capture_batch_id": None,
                            "publish_batch_id": None,
                            "db_upserted": 0,
                            "db_rows_before": None,
                            "db_rows_after": None,
                            "volume_normalized_rows": None,
                        },
                        "backfill": None,
                        "trading_calendar": None,
                    }

                tushare_backfill = self._backfill_daily_prices_from_tushare_daily(
                    conn=conn,
                    v3_db_path=db_path,
                    target_date=target_date,
                    requested_by=requested_by.strip(),
                    reason="historical_backfill",
                    tencent_trade_date=None,
                )
                backfill_ok = bool(
                    isinstance(tushare_backfill, dict) and tushare_backfill.get("status") == "ok"
                )
                trading_calendar_payload: Optional[dict[str, Any]] = None
                if backfill_ok:
                    trading_calendar_payload = self.rebuild_trading_calendar_view(
                        sqlite_db_path=str(db_path),
                        table="daily_prices",
                        date_column="trade_date",
                        requested_by=requested_by.strip(),
                    )

                return {
                    "_meta": {"status": "ok"},
                    "tencent_update": {
                        "dry_run": False,
                        "requested_by": requested_by.strip(),
                        "target_date": target_date,
                        "trade_date": target_date,
                        "calendar_source": calendar_source,
                        "calendar_is_trading_day": calendar_is_trading_day,
                        "requested": int(tushare_backfill.get("db_upserted") or 0)
                        if isinstance(tushare_backfill, dict)
                        else 0,
                        "quotes_parsed": 0,
                        "missing_codes_count": 0,
                        "coverage": (tushare_backfill.get("coverage") if isinstance(tushare_backfill, dict) else None)
                        or {"close": 0.0, "open": 0.0, "amount": 0.0, "turnover": 0.0},
                        "quality_gate": {
                            "passed": backfill_ok,
                            "gate_reasons": [] if backfill_ok else ["tushare_backfill_failed"],
                            "min_close_coverage": float(min_close_coverage),
                            "min_amount_coverage": float(min_amount_coverage),
                            "min_turnover_coverage": float(min_turnover_coverage),
                        },
                        "capture_batch_id": None,
                        "publish_batch_id": None,
                        "db_upserted": int(tushare_backfill.get("db_upserted") or 0)
                        if isinstance(tushare_backfill, dict)
                        else 0,
                        "db_rows_before": tushare_backfill.get("before_rows") if isinstance(tushare_backfill, dict) else None,
                        "db_rows_after": tushare_backfill.get("after_rows") if isinstance(tushare_backfill, dict) else None,
                        "volume_normalized_rows": tushare_backfill.get("volume_normalized_rows")
                        if isinstance(tushare_backfill, dict)
                        else None,
                    },
                    "backfill": tushare_backfill,
                    "trading_calendar": trading_calendar_payload,
                }

            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT code FROM stocks
                WHERE COALESCE(is_delisted, 0) = 0
                  AND asset_type = 'stock'
                  AND total_market_cap IS NOT NULL
                  AND sector_lv1 IS NOT NULL
                ORDER BY code ASC
                """
            )
            codes: list[str] = []
            for row in cursor.fetchall():
                code = str(row["code"])
                if self._market_symbol(code):
                    codes.append(code)

            requested = len(codes)
            if requested == 0:
                raise ApiError(
                    status_code=HTTPStatus.SERVICE_UNAVAILABLE,
                    code="no_active_codes",
                    message="no active codes available for update",
                )

            def chunks(items: list[str], size: int) -> list[list[str]]:
                if size <= 0:
                    return [items]
                return [items[i : i + size] for i in range(0, len(items), size)]

            bars: list[BootstrapApiService._TencentQuoteBar] = []
            missing_codes: list[str] = []
            trade_dates: list[str] = []

            for chunk in chunks(codes, chunk_size):
                symbols = [
                    symbol
                    for code in chunk
                    if (symbol := self._market_symbol(code)) is not None
                ]
                if not symbols:
                    continue

                url = f"https://qt.gtimg.cn/q={','.join(symbols)}"
                last_exc: Optional[Exception] = None
                text = ""
                for _ in range(max(1, max_attempts)):
                    try:
                        req = urllib.request.Request(
                            url,
                            headers={
                                "User-Agent": "Mozilla/5.0",
                                "Accept": "*/*",
                            },
                            method="GET",
                        )
                        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
                            raw = resp.read()
                        try:
                            text = raw.decode("gbk", errors="ignore")
                        except Exception:
                            text = raw.decode("utf-8", errors="ignore")
                        last_exc = None
                        break
                    except Exception as exc:
                        last_exc = exc
                        time.sleep(max(0.0, float(sleep_seconds)))
                if last_exc is not None:
                    continue

                parsed_codes: set[str] = set()
                got = 0
                for seg in text.split(";"):
                    seg = seg.strip()
                    if not seg:
                        continue
                    bar = self._parse_tencent_quote_line(seg)
                    if not bar:
                        continue
                    if bar.code in parsed_codes:
                        continue
                    parsed_codes.add(bar.code)
                    got += 1
                    trade_dates.append(bar.trade_date)
                    bars.append(bar)
                if got < len(chunk):
                    for code in chunk:
                        if code not in parsed_codes:
                            missing_codes.append(code)
                time.sleep(max(0.0, float(sleep_seconds)))

            quotes_parsed = len(bars)
            trade_date = sorted(set(trade_dates))[-1] if trade_dates else None

            close_ok = sum(1 for b in bars if b.close is not None)
            open_ok = sum(1 for b in bars if b.open is not None)
            amount_ok = sum(1 for b in bars if b.amount is not None)
            turnover_ok = sum(1 for b in bars if b.turnover is not None)
            coverage = {
                "close": close_ok / max(1, requested),
                "open": open_ok / max(1, requested),
                "amount": amount_ok / max(1, requested),
                "turnover": turnover_ok / max(1, requested),
            }

            capture_batch_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc).isoformat(timespec="seconds")

            capture_rows_payload = []
            for b in bars:
                capture_rows_payload.append(
                    (
                        capture_batch_id,
                        "tencent",
                        b.code,
                        b.trade_date,
                        b.open,
                        b.high,
                        b.low,
                        b.close,
                        b.volume,
                        b.amount,
                        b.turnover,
                        b.preclose,
                        self._compute_pct_change(b.preclose, b.close),
                        "normalized",
                        json.dumps({}, ensure_ascii=False),
                        now,
                    )
                )
            if not dry_run:
                try:
                    conn.execute("BEGIN IMMEDIATE")
                except Exception:
                    conn.execute("BEGIN")
            if capture_rows_payload and not dry_run:
                conn.executemany(
                    """
                    INSERT OR REPLACE INTO daily_price_capture_rows (
                        capture_batch_id,
                        source,
                        code,
                        trade_date,
                        open,
                        high,
                        low,
                        close,
                        volume,
                        amount,
                        turnover,
                        preclose,
                        pct_change,
                        row_status,
                        metadata_json,
                        created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    capture_rows_payload,
                )

            capture_status = "ok" if bars else "failed"
            capture_error_reason = "" if bars else "no quotes parsed"

            if not dry_run:
                conn.execute(
                    """
                    INSERT INTO daily_price_capture_batches (
                        capture_batch_id,
                        source,
                        target_date,
                        trade_date,
                        capture_status,
                        calendar_source,
                        calendar_is_trading_day,
                        requested,
                        quotes_parsed,
                        captured_rows,
                        missing_codes_count,
                        coverage_close,
                        coverage_open,
                        coverage_amount,
                        coverage_turnover,
                        warning_reason,
                        error_reason,
                        metadata_json,
                        created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        capture_batch_id,
                        "tencent",
                        target_date,
                        trade_date,
                        capture_status,
                        calendar_source,
                        None
                        if calendar_is_trading_day is None
                        else int(bool(calendar_is_trading_day)),
                        int(requested),
                        int(quotes_parsed),
                        int(len(capture_rows_payload)),
                        int(len(missing_codes)),
                        float(coverage["close"]),
                        float(coverage["open"]),
                        float(coverage["amount"]),
                        float(coverage["turnover"]),
                        "",
                        capture_error_reason,
                        json.dumps(
                            {"db_path": str(db_path), "requested_by": requested_by},
                            ensure_ascii=False,
                        ),
                        now,
                    ),
                )

            gate_reasons: list[str] = []
            if coverage["close"] < float(min_close_coverage):
                gate_reasons.append(
                    f"close coverage {coverage['close']:.4f} < {float(min_close_coverage):.4f}"
                )
            if coverage["amount"] < float(min_amount_coverage):
                gate_reasons.append(
                    f"amount coverage {coverage['amount']:.4f} < {float(min_amount_coverage):.4f}"
                )
            if coverage["turnover"] < float(min_turnover_coverage):
                gate_reasons.append(
                    f"turnover coverage {coverage['turnover']:.4f} < {float(min_turnover_coverage):.4f}"
                )
            if trade_date is None:
                gate_reasons.append("missing_trade_date")
            elif str(trade_date) != str(target_date):
                gate_reasons.append(f"trade_date_mismatch {trade_date} != {target_date}")
            if calendar_is_trading_day and not self._is_market_closed_cn(target_trade_date=target_date):
                gate_reasons.append("market_not_closed")

            publish_batch_id = str(uuid.uuid4())
            publish_ok = len(gate_reasons) == 0 and bool(bars)
            publish_status = "ok" if publish_ok else "blocked_by_quality_gate"

            db_upserted = 0
            rows_before: Optional[int] = None
            rows_after: Optional[int] = None
            volume_normalized_rows: Optional[int] = None
            if publish_ok and not dry_run:
                if trade_date is not None:
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT COUNT(1) FROM daily_prices WHERE trade_date = ?",
                        (trade_date,),
                    )
                    rows_before = int(cursor.fetchone()[0] or 0)
                upsert_rows = []
                updated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
                for b in bars:
                    upsert_rows.append(
                        (
                            b.code,
                            b.trade_date,
                            b.open,
                            b.high,
                            b.low,
                            b.close,
                            b.volume,
                            b.amount,
                            b.turnover,
                            b.preclose,
                            self._compute_pct_change(b.preclose, b.close),
                            updated_at,
                        )
                    )
                conn.executemany(
                    """
                    INSERT INTO daily_prices (
                        code,
                        trade_date,
                        open,
                        high,
                        low,
                        close,
                        volume,
                        amount,
                        turnover,
                        preclose,
                        pct_change,
                        updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(code, trade_date) DO UPDATE SET
                        open=excluded.open,
                        high=excluded.high,
                        low=excluded.low,
                        close=excluded.close,
                        volume=excluded.volume,
                        amount=excluded.amount,
                        turnover=excluded.turnover,
                        preclose=excluded.preclose,
                        pct_change=excluded.pct_change,
                        updated_at=excluded.updated_at
                    """,
                    upsert_rows,
                )
                db_upserted = int(len(upsert_rows))
                if trade_date is not None:
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT COUNT(1) FROM daily_prices WHERE trade_date = ?",
                        (trade_date,),
                    )
                    rows_after = int(cursor.fetchone()[0] or 0)
                    volume_normalized_rows = int(
                        self._normalize_daily_prices_volume_to_shares_in_conn(
                            conn=conn, trade_date=trade_date
                        )
                    )

            if not dry_run:
                conn.execute(
                    """
                    INSERT INTO daily_price_publish_batches (
                        batch_id,
                        source,
                        target_date,
                        trade_date,
                        publish_status,
                        quality_gate_passed,
                        quality_gate_reason,
                        warning_reason,
                        calendar_source,
                        calendar_is_trading_day,
                        requested,
                        quotes_parsed,
                        db_upserted,
                        missing_codes_count,
                        coverage_close,
                        coverage_open,
                        coverage_amount,
                        coverage_turnover,
                        published_close,
                        published_amount,
                        published_turnover,
                        published_total_rows,
                        gate_reasons_json,
                        warning_reasons_json,
                        metadata_json,
                        created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        publish_batch_id,
                        "tencent",
                        target_date,
                        trade_date,
                        publish_status,
                        int(bool(publish_ok)),
                        "; ".join(gate_reasons),
                        "",
                        calendar_source,
                        None
                        if calendar_is_trading_day is None
                        else int(bool(calendar_is_trading_day)),
                        int(requested),
                        int(quotes_parsed),
                        int(db_upserted),
                        int(len(missing_codes)),
                        float(coverage["close"]),
                        float(coverage["open"]),
                        float(coverage["amount"]),
                        float(coverage["turnover"]),
                        float(coverage["close"]),
                        float(coverage["amount"]),
                        float(coverage["turnover"]),
                        int(len(bars)),
                        json.dumps(gate_reasons, ensure_ascii=False),
                        json.dumps([], ensure_ascii=False),
                        json.dumps(
                            {
                                "db_path": str(db_path),
                                "requested_by": requested_by,
                                "capture_batch_id": capture_batch_id,
                            },
                            ensure_ascii=False,
                        ),
                        now,
                    ),
                )
                conn.commit()

            backfill_payload: Optional[dict[str, Any]] = None
            if not dry_run and calendar_is_trading_day:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT COUNT(1) FROM daily_prices WHERE trade_date = ?",
                    (target_date,),
                )
                target_rows = int(cursor.fetchone()[0] or 0)
                if target_rows == 0 and target_date != (trade_date or ""):
                    tushare_backfill = self._backfill_daily_prices_from_tushare_daily(
                        conn=conn,
                        v3_db_path=db_path,
                        target_date=target_date,
                        requested_by=requested_by.strip(),
                        reason="tencent_trade_date_mismatch",
                        tencent_trade_date=trade_date,
                    )
                    backfill_payload = tushare_backfill

            trading_calendar_payload: Optional[dict[str, Any]] = None
            should_rebuild_calendar = bool(publish_ok)
            if backfill_payload and backfill_payload.get("status") == "ok":
                should_rebuild_calendar = True
            if should_rebuild_calendar and not dry_run:
                trading_calendar_payload = self.rebuild_trading_calendar_view(
                    sqlite_db_path=str(db_path),
                    table="daily_prices",
                    date_column="trade_date",
                    requested_by=requested_by.strip(),
                )

            return {
                "_meta": {"status": "ok"},
                "tencent_update": {
                    "dry_run": bool(dry_run),
                    "requested_by": requested_by.strip(),
                    "target_date": target_date,
                    "trade_date": trade_date,
                    "calendar_source": calendar_source,
                    "calendar_is_trading_day": calendar_is_trading_day,
                    "requested": requested,
                    "quotes_parsed": quotes_parsed,
                    "missing_codes_count": len(missing_codes),
                    "coverage": coverage,
                    "quality_gate": {
                        "passed": bool(publish_ok),
                        "gate_reasons": gate_reasons,
                        "min_close_coverage": float(min_close_coverage),
                        "min_amount_coverage": float(min_amount_coverage),
                        "min_turnover_coverage": float(min_turnover_coverage),
                    },
                    "capture_batch_id": capture_batch_id,
                    "publish_batch_id": publish_batch_id,
                    "db_upserted": db_upserted,
                    "db_rows_before": rows_before,
                    "db_rows_after": rows_after,
                    "volume_normalized_rows": volume_normalized_rows,
                },
                "backfill": backfill_payload,
                "trading_calendar": trading_calendar_payload,
            }
        except ApiError:
            raise
        except Exception as exc:
            try:
                conn.rollback()
            except sqlite3.Error:
                pass
            raise ApiError(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                code="tencent_update_failed",
                message=f"failed to update daily_prices from tencent (see server logs)",
                details={
                    "exception_type": type(exc).__name__,
                    "exception": str(exc),
                    "dest_db_path": _safe_ref_path(str(db_path)),
                    "target_date": target_date,
                },
            )
        finally:
            conn.close()

    def factor_matrix_daily_view(
        self,
        *,
        target_date: str,
        debug: bool = False,
    ) -> dict[str, Any]:
        self.require_trading_day(target_date=target_date)
        from neotrade3.analysis.factor_matrix import FactorMatrixBuilder
        db_path = Path(
            os.environ.get("NEOTRADE3_STOCK_DB_PATH")
            or str(self._stock_db_default_path)
        ).expanduser()
        if debug:
            builder = FactorMatrixBuilder(
                db_path=str(db_path),
                project_root=self.project_root,
            )
            payload = builder.build(target_date=target_date, debug=True)
            meta = payload.get("_meta", {})
            if isinstance(meta, dict):
                meta.pop("source", None)
            meta.update({"status": "ok", "debug": True, "self_heal": "rebuilt_debug"})
            payload["_meta"] = meta
            return payload
        try:
            payload = FactorMatrixBuilder.load(
                project_root=self.project_root, target_date=target_date
            )
            if not isinstance(payload, dict):
                raise FileNotFoundError("factor matrix payload invalid")
            meta = payload.get("_meta", {})
            if isinstance(meta, dict):
                meta.pop("source", None)
            meta.update({"status": "ok", "debug": bool(debug), "self_heal": "none"})
            payload["_meta"] = meta
            return payload
        except FileNotFoundError:
            builder = FactorMatrixBuilder(
                db_path=str(db_path),
                project_root=self.project_root,
            )
            payload = builder.build(target_date=target_date, debug=debug)
            meta = payload.get("_meta", {})
            if isinstance(meta, dict):
                meta.pop("source", None)
                payload["_meta"] = meta
            FactorMatrixBuilder.save(
                payload, project_root=self.project_root, target_date=target_date
            )
            payload = FactorMatrixBuilder.load(
                project_root=self.project_root, target_date=target_date
            )
            if not isinstance(payload, dict):
                raise ApiError(
                    status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                    code="factor_matrix_invalid",
                    message="factor matrix stored payloads are not JSON objects",
                    details={"target_date": target_date},
                )
            meta = payload.get("_meta", {})
            if isinstance(meta, dict):
                meta.pop("source", None)
            meta.update({"status": "ok", "debug": bool(debug), "self_heal": "generated"})
            payload["_meta"] = meta
            return payload

    def factor_matrix_daily_run_view(
        self,
        *,
        target_date: str,
        requested_by: str,
        dry_run: bool = False,
        debug: bool = False,
    ) -> dict[str, Any]:
        self.require_trading_day(target_date=target_date)
        if not requested_by.strip():
            raise ApiError(
                status_code=HTTPStatus.BAD_REQUEST,
                code="invalid_requested_by",
                message="requested_by must be a non-empty string",
            )

        ledger_path, artifact_path = self._factor_matrix_paths(target_date=target_date)
        requested_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        # Use the independent factor_matrix module
        from neotrade3.analysis.factor_matrix import FactorMatrixBuilder
        db_path = Path(
            os.environ.get("NEOTRADE3_STOCK_DB_PATH")
            or str(self._stock_db_default_path)
        ).expanduser()
        builder = FactorMatrixBuilder(
            db_path=str(db_path),
            project_root=self.project_root,
        )
        payload = builder.build(target_date=target_date, debug=debug)
        meta = payload.get("_meta", {})
        if isinstance(meta, dict):
            meta.pop("source", None)
            payload["_meta"] = meta

        ledger_payload = {
            "version": 1,
            "target_date": target_date,
            "requested_by": requested_by,
            "requested_at": requested_at,
            "status": "ok",
            "artifact_path": self._safe_ref_path(str(artifact_path)),
            "inputs": {
                "stock_db_path": self._safe_ref_path(str(db_path)),
                "screeners_registry": self._safe_ref_path(
                    str(self._screeners_registry_config)
                ),
                "screeners_runs_root": self._safe_ref_path(
                    str(self.project_root / "var/artifacts/screener_runs" / target_date)
                ),
            },
        }

        if not dry_run:
            FactorMatrixBuilder.save(
                payload, project_root=self.project_root, target_date=target_date
            )

        return {
            "_meta": {"status": "ok"},
            "factor_matrix_run": ledger_payload,
        }

    def factor_matrix_daily_detail_view(self, *, target_date: str) -> dict[str, Any]:
        ledger_path, artifact_path = self._factor_matrix_paths(target_date=target_date)
        if not ledger_path.exists():
            raise ApiError(
                status_code=HTTPStatus.NOT_FOUND,
                code="factor_matrix_not_found",
                message="factor matrix run ledger not found",
                details={"target_date": target_date},
            )
        if not artifact_path.exists():
            raise ApiError(
                status_code=HTTPStatus.NOT_FOUND,
                code="factor_matrix_not_found",
                message="factor matrix daily artifact not found",
                details={"target_date": target_date},
            )

        ledger_payload = json.loads(ledger_path.read_text(encoding="utf-8"))
        artifact_payload = json.loads(artifact_path.read_text(encoding="utf-8"))
        if not isinstance(ledger_payload, dict) or not isinstance(
            artifact_payload, dict
        ):
            raise ApiError(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                code="factor_matrix_invalid",
                message="factor matrix stored payloads are not JSON objects",
                details={"target_date": target_date},
            )
        return {
            "_meta": {"status": "ok"},
            "factor_matrix_run": ledger_payload,
            "factor_matrix_daily": artifact_payload,
        }

    def factor_matrix_daily_download_view(
        self, *, target_date: str
    ) -> ApiBinaryResponse:
        _, artifact_path = self._factor_matrix_paths(target_date=target_date)
        if not artifact_path.exists():
            raise ApiError(
                status_code=HTTPStatus.NOT_FOUND,
                code="factor_matrix_not_found",
                message="factor matrix daily artifact not found",
                details={"target_date": target_date},
            )
        filename = artifact_path.name
        return ApiBinaryResponse(
            body=artifact_path.read_bytes(),
            content_type="application/json; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    def lab_run_view(
        self,
        *,
        target_date: str,
        lab_id: str,
        requested_by: str,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        self.require_trading_day(target_date=target_date)
        registry = LabRegistry.from_file(self._labs_config)
        lab = next((item for item in registry.labs if item.lab_id == lab_id), None)
        if lab is None:
            raise ApiError(
                status_code=HTTPStatus.BAD_REQUEST,
                code="invalid_lab_id",
                message="unknown lab_id",
                details={"lab_id": lab_id},
            )
        if not lab.enabled:
            raise ApiError(
                status_code=HTTPStatus.BAD_REQUEST,
                code="lab_disabled",
                message="lab is disabled",
                details={"lab_id": lab_id},
            )
        if not requested_by.strip():
            raise ApiError(
                status_code=HTTPStatus.BAD_REQUEST,
                code="invalid_requested_by",
                message="requested_by must be a non-empty string",
            )

        ledger_path, artifact_path = self._lab_run_paths(
            target_date=target_date, lab_id=lab_id
        )
        requested_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        compose_artifact = self._read_data_control_compose_artifact(
            target_date=target_date
        )
        publish_artifact = self._read_data_control_publish_artifact(
            target_date=target_date
        )
        jobs = getattr(lab, "daily_jobs", []) or []
        is_publish_gated = any(
            (str(getattr(job, "trigger_type", "") or "") == "post_publish_trigger")
            or bool(getattr(job, "requires_publish_status", False))
            for job in jobs
        )
        if is_publish_gated:
            if publish_artifact is None or str(publish_artifact.get("status")) != "ok":
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="published_daily_data_not_ready",
                    message="published_daily_data is not ready; run orchestration or data_control.publish first",
                    details={"lab_id": lab_id, "target_date": target_date},
                )

        artifacts_payload: dict[str, Any] = {}
        if lab_id == "cup_handle_lab":
            screener_artifact = read_screener_run_artifact(
                project_root=self.project_root,
                target_date=target_date,
                screener_id="cup_handle_v4",
            )
            picks = (
                screener_artifact.get("picks")
                if isinstance(screener_artifact, dict)
                else None
            )
            if isinstance(picks, list):
                codes = [str(item).split(".", 1)[0].strip() for item in picks]
                codes = [code for code in codes if re.fullmatch(r"\d{6}", code)]
            else:
                codes = []
            artifacts_payload["cup_handle_daily_report"] = {
                "version": 1,
                "target_date": target_date,
                "status": "pending_implementation",
                "message": "杯柄实验室运行逻辑尚未迁移；当前仅将 cup_handle_v4 命中结果作为候选输入。",
                "candidates": codes,
                "source_refs": {
                    "screener_id": "cup_handle_v4",
                    "artifact_path": self._safe_ref_path(
                        str(
                            self.project_root
                            / "var/artifacts/screener_runs"
                            / target_date
                            / "screener_cup_handle_v4_result.json"
                        )
                    ),
                },
            }
        elif lab_id == "five_flags_lab":
            candidates = self._extract_candidate_codes_from_compose(compose_artifact)
            artifacts_payload["five_flags_scan_results"] = {
                "version": 1,
                "target_date": target_date,
                "status": "pending_implementation",
                "message": "老鸭头五图扫描逻辑尚未迁移；当前输出候选输入快照（来自 data_control.compose）。",
                "pool": candidates,
                "sector_top5_by_amount": (
                    compose_artifact.get("sector_top5_by_amount")
                    if isinstance(compose_artifact, dict)
                    else []
                ),
                "source_refs": {
                    "compose_artifact_path": self._safe_ref_path(
                        str(
                            self.project_root
                            / "var/artifacts/data_control"
                            / target_date
                            / "data_control_compose_result.json"
                        )
                    )
                },
            }
        elif lab_id == "paper_simulation_lab":
            candidates = self._extract_candidate_codes_from_compose(compose_artifact)
            artifacts_payload["paper_simulation_positions"] = {
                "version": 1,
                "target_date": target_date,
                "status": "pending_implementation",
                "message": "量化模拟交易逻辑尚未迁移；当前输出候选输入快照与空持仓结构。",
                "cash_yuan": 1000000.0,
                "positions": [],
                "candidates": candidates,
                "universe_snapshot": {
                    "candidate_count": len(candidates),
                    "candidates": candidates[:200],
                },
                "source_refs": {
                    "compose_artifact_path": self._safe_ref_path(
                        str(
                            self.project_root
                            / "var/artifacts/data_control"
                            / target_date
                            / "data_control_compose_result.json"
                        )
                    )
                },
            }

        if not artifacts_payload:
            artifacts_payload = {
                artifact.artifact_id: {
                    "version": 1,
                    "target_date": target_date,
                    "status": "pending_implementation",
                    "message": "实验室运行逻辑尚未迁移。",
                }
                for artifact in lab.artifacts
            }

        run_payload = {
            "version": 1,
            "lab_id": lab.lab_id,
            "lab_name": lab.display_name,
            "target_date": target_date,
            "requested_by": requested_by,
            "requested_at": requested_at,
            "status": "ok",
            "artifact_path": self._safe_ref_path(str(artifact_path)),
            "artifacts": artifacts_payload,
        }
        ledger_payload = {
            "version": 1,
            "lab_id": lab.lab_id,
            "target_date": target_date,
            "requested_by": requested_by,
            "requested_at": requested_at,
            "status": "ok",
            "artifact_path": self._safe_ref_path(str(artifact_path)),
        }

        if not dry_run:
            ledger_path.parent.mkdir(parents=True, exist_ok=True)
            artifact_path.parent.mkdir(parents=True, exist_ok=True)
            ledger_path.write_text(
                json.dumps(ledger_payload, indent=2, ensure_ascii=False, sort_keys=True)
                + "\n",
                encoding="utf-8",
            )
            artifact_path.write_text(
                json.dumps(run_payload, indent=2, ensure_ascii=False, sort_keys=True)
                + "\n",
                encoding="utf-8",
            )

        return {"_meta": {"status": "ok"}, "lab_run": ledger_payload}

    def _read_data_control_compose_artifact(
        self, *, target_date: str
    ) -> Optional[dict[str, Any]]:
        artifact_path = (
            self.project_root
            / "var/artifacts/data_control"
            / target_date
            / "data_control_compose_result.json"
        )
        if not artifact_path.exists():
            return None
        try:
            payload = json.loads(artifact_path.read_text(encoding="utf-8"))
        except Exception:
            return None
        return payload if isinstance(payload, dict) else None

    def _read_data_control_publish_artifact(
        self, *, target_date: str
    ) -> Optional[dict[str, Any]]:
        artifact_path = (
            self.project_root
            / "var/artifacts/data_control"
            / target_date
            / "data_control_publish_result.json"
        )
        if not artifact_path.exists():
            return None
        try:
            payload = json.loads(artifact_path.read_text(encoding="utf-8"))
        except Exception:
            return None
        return payload if isinstance(payload, dict) else None

    @staticmethod
    def _extract_candidate_codes_from_compose(
        compose_artifact: Optional[dict[str, Any]],
    ) -> list[str]:
        if not isinstance(compose_artifact, dict):
            return []
        universe = compose_artifact.get("candidate_universe")
        if not isinstance(universe, list):
            return []
        codes = []
        for item in universe:
            if not isinstance(item, dict):
                continue
            raw_code = item.get("stock_code")
            if not isinstance(raw_code, str):
                continue
            code = raw_code.strip().split(".", 1)[0]
            if re.fullmatch(r"\d{6}", code):
                codes.append(code)
        return codes

    def lab_runs_view(
        self, *, target_date: Optional[str] = None, limit: Optional[int] = None
    ) -> dict[str, Any]:
        base_dir = self.project_root / "var/ledgers/lab_runs"
        if not base_dir.exists():
            return {"_meta": {"returned_count": 0}, "lab_runs": []}

        date_dirs = []
        for item in base_dir.iterdir():
            if not item.is_dir():
                continue
            if target_date and item.name != target_date:
                continue
            date_dirs.append(item)
        date_dirs.sort(key=lambda p: p.name, reverse=True)

        runs: list[dict[str, Any]] = []
        for date_dir in date_dirs:
            for ledger_file in sorted(date_dir.glob("lab_*_run.json")):
                payload: Optional[object]
                try:
                    payload = json.loads(ledger_file.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    payload = None
                if not isinstance(payload, dict):
                    continue
                runs.append(payload)
                if limit is not None and len(runs) >= limit:
                    return {"_meta": {"returned_count": len(runs)}, "lab_runs": runs}
        return {"_meta": {"returned_count": len(runs)}, "lab_runs": runs}

    def lab_run_detail_view(self, *, target_date: str, lab_id: str) -> dict[str, Any]:
        ledger_path, artifact_path = self._lab_run_paths(
            target_date=target_date, lab_id=lab_id
        )
        if not ledger_path.exists():
            raise ApiError(
                status_code=HTTPStatus.NOT_FOUND,
                code="lab_run_not_found",
                message="lab run ledger not found",
                details={"target_date": target_date, "lab_id": lab_id},
            )
        if not artifact_path.exists():
            raise ApiError(
                status_code=HTTPStatus.NOT_FOUND,
                code="lab_run_artifact_not_found",
                message="lab run artifact not found",
                details={"target_date": target_date, "lab_id": lab_id},
            )
        ledger_payload = json.loads(ledger_path.read_text(encoding="utf-8"))
        artifact_payload = json.loads(artifact_path.read_text(encoding="utf-8"))
        if not isinstance(ledger_payload, dict) or not isinstance(
            artifact_payload, dict
        ):
            raise ApiError(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                code="lab_run_invalid",
                message="lab run stored payloads are not JSON objects",
                details={"target_date": target_date, "lab_id": lab_id},
            )
        return {
            "_meta": {"status": "ok"},
            "lab_run": ledger_payload,
            "lab_result": artifact_payload,
        }

    def lab_run_download_view(
        self, *, target_date: str, lab_id: str
    ) -> ApiBinaryResponse:
        _, artifact_path = self._lab_run_paths(target_date=target_date, lab_id=lab_id)
        if not artifact_path.exists():
            raise ApiError(
                status_code=HTTPStatus.NOT_FOUND,
                code="lab_run_artifact_not_found",
                message="lab run artifact not found",
                details={"target_date": target_date, "lab_id": lab_id},
            )
        filename = artifact_path.name
        return ApiBinaryResponse(
            body=artifact_path.read_bytes(),
            content_type="application/json; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    def _factor_matrix_paths(self, *, target_date: str) -> tuple[Path, Path]:
        ledgers_dir = self.project_root / "var/ledgers/factor_matrix" / target_date
        artifacts_dir = self.project_root / "var/artifacts/factor_matrix" / target_date
        ledger_path = ledgers_dir / "factor_matrix_run.json"
        artifact_path = artifacts_dir / "factor_matrix_daily.json"
        return ledger_path, artifact_path

    def _lab_run_paths(self, *, target_date: str, lab_id: str) -> tuple[Path, Path]:
        safe_lab_id = re.sub(r"[^a-zA-Z0-9_\\-]+", "_", lab_id).strip("_") or "unknown"
        ledgers_dir = self.project_root / "var/ledgers/lab_runs" / target_date
        artifacts_dir = self.project_root / "var/artifacts/lab_runs" / target_date
        ledger_path = ledgers_dir / f"lab_{safe_lab_id}_run.json"
        artifact_path = artifacts_dir / f"lab_{safe_lab_id}_result.json"
        return ledger_path, artifact_path

    def _data_control_stage_paths(
        self, *, target_date: str, stage: str
    ) -> tuple[Path, Path]:
        ledgers_dir = self.project_root / "var/ledgers/data_control" / target_date
        artifacts_dir = self.project_root / "var/artifacts/data_control" / target_date
        ledger_path = ledgers_dir / f"data_control_{stage}_ledger.json"
        artifact_path = artifacts_dir / f"data_control_{stage}_result.json"
        return ledger_path, artifact_path

    def _orchestration_run_paths(self, *, target_date: str) -> tuple[Path, Path]:
        ledgers_dir = self.project_root / "var/ledgers/orchestration_runs" / target_date
        artifacts_dir = (
            self.project_root / "var/artifacts/orchestration_runs" / target_date
        )
        ledger_path = ledgers_dir / "orchestrator_run.json"
        artifact_path = artifacts_dir / "orchestrator_result.json"
        return ledger_path, artifact_path

    def _build_factor_matrix_daily_output(
        self,
        *,
        target_date: str,
        source_label: str,
        debug: bool,
    ) -> dict[str, Any]:
        db_path = Path(
            os.environ.get("NEOTRADE3_STOCK_DB_PATH")
            or str(self._stock_db_default_path)
        ).expanduser()
        if not db_path.exists() or not db_path.is_file():
            raise ApiError(
                status_code=HTTPStatus.SERVICE_UNAVAILABLE,
                code="stock_db_not_ready",
                message="NeoTrade3 stock db is not available; seed it first",
                details={"expected_path": _safe_ref_path(str(db_path))},
            )

        universe_rows = self._select_universe_rows(
            db_path=db_path, target_date=target_date, limit=300
        )
        focus_sectors = self._compute_focus_sectors_top5(universe_rows)
        sector_rank = {
            item["sector_lv1"]: idx + 1 for idx, item in enumerate(focus_sectors)
        }

        screener_hits = self._load_screener_hits_for_date(target_date=target_date)
        limit_up_reasons = self._load_limit_up_reasons_for_date(
            db_path=db_path, target_date=target_date
        )
        announcements = self._load_announcements_for_date(
            db_path=db_path, target_date=target_date
        )
        lab_hits, lab_artifact_status = self._load_lab_hits_for_target_date(
            target_date=target_date
        )
        candidates = []
        max_amount = float(universe_rows[0]["amount"]) if universe_rows else 0.0
        for idx, row in enumerate(universe_rows):
            stock_code = row["stock_code"]
            stock_name = row["stock_name"]
            sector_lv1 = row.get("sector_lv1")
            sector_lv2 = row.get("sector_lv2")
            amount = float(row.get("amount") or 0.0)
            pct_change = float(row.get("pct_change") or 0.0)

            hit_items = screener_hits.get(stock_code, [])
            hit_names = [
                str(item.get("screener_name") or item.get("screener_id") or "").strip()
                for item in hit_items
            ]
            hit_names = [name for name in hit_names if name]
            technical_score = min(
                100.0,
                max(
                    0.0,
                    40.0
                    + 10.0 * len(hit_names)
                    + 2.0 * max(-10.0, min(10.0, pct_change)),
                ),
            )

            rank_bonus = 0.0
            if sector_lv1 and sector_lv1 in sector_rank:
                rank_bonus = 30.0 - 5.0 * float(sector_rank[sector_lv1] - 1)
            amount_score = (
                min(70.0, max(0.0, (amount / max(1.0, max_amount)) * 70.0))
                if universe_rows
                else 0.0
            )
            sentiment_score = min(100.0, max(0.0, amount_score + rank_bonus))

            ann_titles = announcements.get(stock_code, [])
            composite_score = 0.0

            reason_items = limit_up_reasons.get(stock_code, [])
            reason_lines = []
            for item in reason_items[:3]:
                category = str(item.get("category") or "").strip()
                reason = str(item.get("reason") or "").strip()
                if category and reason:
                    reason_lines.append(f"涨停原因：{category} - {reason}")
                elif reason:
                    reason_lines.append(f"涨停原因：{reason}")
            if not reason_lines:
                reason_lines = ["涨停原因：无记录（或当日未涨停）。"]

            lab_items = lab_hits.get(stock_code, [])
            lab_tech_bonus = 0.0
            lab_sentiment_bonus = 0.0
            lab_tech_lines: list[str] = []
            lab_sentiment_lines: list[str] = []
            lab_note_lines: list[str] = []
            for item in lab_items:
                lab_id_value = str(item.get("lab_id") or "").strip()
                lab_name_value = (
                    str(item.get("lab_name") or lab_id_value).strip() or lab_id_value
                )
                if lab_id_value == "cup_handle_lab":
                    lab_tech_bonus += 8.0
                    lab_tech_lines.append(f"实验室信号：{lab_name_value}（候选输入）")
                elif lab_id_value == "five_flags_lab":
                    lab_sentiment_bonus += 10.0
                    lab_sentiment_lines.append(f"实验室信号：{lab_name_value}（在池）")
                elif lab_id_value == "paper_simulation_lab":
                    lab_note_lines.append(
                        f"实验室信号：{lab_name_value}（输入快照已生成，策略待迁移）"
                    )
                elif lab_name_value:
                    lab_note_lines.append(f"实验室信号：{lab_name_value}")

            if lab_items and not (
                lab_tech_lines or lab_sentiment_lines or lab_note_lines
            ):
                lab_hit_names = [
                    str(item.get("lab_name") or item.get("lab_id") or "").strip()
                    for item in lab_items
                ]
                lab_hit_names = [name for name in lab_hit_names if name]
                lab_note_lines = (
                    ["实验室命中：" + "、".join(lab_hit_names)] if lab_hit_names else []
                )

            technical_score = min(100.0, max(0.0, technical_score + lab_tech_bonus))
            sentiment_score = min(
                100.0, max(0.0, sentiment_score + lab_sentiment_bonus)
            )
            overall = min(
                100.0,
                max(
                    0.0,
                    0.5 * technical_score
                    + 0.4 * sentiment_score
                    + 0.1 * composite_score,
                ),
            )

            candidates.append(
                {
                    "stock_code": stock_code,
                    "stock_name": stock_name,
                    "sector_lv1": sector_lv1,
                    "sector_lv2": sector_lv2,
                    "certainty": round(overall, 2),
                    "subscores": {
                        "technical": round(technical_score, 2),
                        "sentiment": round(sentiment_score, 2),
                        "composite": round(composite_score, 2),
                        "overall": round(overall, 2),
                    },
                    "evidence": {
                        "technical_evidence": [
                            f"当日涨跌幅：{pct_change:.2f}%",
                            f"筛选器命中数：{len(hit_names)}",
                        ]
                        + (
                            ["命中筛选器：" + "、".join(hit_names)]
                            if hit_names
                            else ["未命中任何已运行筛选器（或筛选器尚未运行）。"]
                        )
                        + (lab_tech_lines if (lab_tech_lines or debug) else []),
                        "sentiment_evidence": [
                            f"当日成交额：{amount:.0f} 元",
                            (
                                f"板块聚焦：{sector_lv1}（Top5 by 成交额）"
                                if sector_lv1 in sector_rank
                                else "板块聚焦：不在当日 Top5 成交额板块中。"
                            ),
                            *reason_lines,
                        ]
                        + (
                            lab_sentiment_lines
                            if (lab_sentiment_lines or debug)
                            else []
                        )
                        + (
                            [f"成交额排名：{idx + 1}/{len(universe_rows)}"]
                            if universe_rows
                            else []
                        ),
                        "composite_evidence": [
                            *(
                                [f"公告：{title}" for title in ann_titles[:3]]
                                if ann_titles
                                else ["公告：无记录（或未在当日发布）。"]
                            ),
                            "综合面（行业/财报/新闻/政策/国际政治）尚未接入腾讯等外部数据源，当前仅能基于本地公告表做弱提示，暂不计分。",
                        ],
                        "notes": (lab_note_lines if (lab_note_lines or debug) else [])
                        + [
                            "v1 占位评分：overall=0.5*技术面 + 0.4*资金/情绪面 + 0.1*综合面（综合面当前为 0）。"
                        ],
                    },
                    "signals": self._build_factor_signals(
                        db_path=db_path,
                        target_date=target_date,
                        hit_names=hit_names,
                        hit_items=hit_items,
                        pct_change=pct_change,
                        amount=amount,
                        sector_lv1=sector_lv1,
                        sector_rank=sector_rank,
                        reason_items=reason_items,
                        reason_lines=reason_lines,
                        ann_titles=ann_titles,
                        lab_items=lab_items,
                    ),
                }
            )

        candidates.sort(
            key=lambda item: float(item.get("certainty") or 0.0), reverse=True
        )

        ge80 = [item for item in candidates if float(item["certainty"]) >= 80.0]
        ge70 = [
            item
            for item in candidates
            if float(item["certainty"]) >= 70.0 and float(item["certainty"]) < 80.0
        ]
        ge60 = [
            item
            for item in candidates
            if float(item["certainty"]) >= 60.0 and float(item["certainty"]) < 70.0
        ]

        payload = {
            "_meta": {
                "status": "ok",
                "source": source_label,
                "debug": bool(debug),
            },
            "target_date": target_date,
            "universe": {
                "selection": "top_by_amount",
                "limit": len(universe_rows),
                "filters": [
                    "exclude is_delisted=1",
                    "exclude index prefixes (399xxx)",
                    "exclude BSE prefixes (43/83/87/88)",
                    "exclude ST/PT by name keyword if available",
                ],
            },
            "market_context": {
                "market_phase": {
                    "code": "unknown",
                    "display": "未知（待学习/待接入阶段识别）",
                },
                "focus_themes": [
                    item["sector_lv1"]
                    for item in focus_sectors
                    if item.get("sector_lv1")
                ],
                "focus_themes_source": "top5_sectors_by_amount_proxy",
                "notes": [
                    "Top5 板块目前按成交额聚集度作为资金/情绪 proxy 生成；综合面（外部数据源）接入后，优先改为由综合面驱动筛选 Top5。",
                ],
                "evidence": focus_sectors,
            },
            "tiers": {
                "ge_80": ge80,
                "ge_70": ge70,
                "ge_60": ge60,
            },
            "candidates_summary": {
                "candidate_count": len(candidates),
                "ge_80_count": len(ge80),
                "ge_70_count": len(ge70),
                "ge_60_count": len(ge60),
                "dedupe_policy": "deduped by certainty tier bands",
            },
            "model_state": {
                "version": 1,
                "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "learning_modes": ["historical_backtest", "live_tracking"],
                "feedback_policy": [
                    "primary: certainty score outcomes + user feedback",
                    "secondary: realized return over 20-50 trading days",
                ],
                "integrations": {
                    "labs": lab_artifact_status,
                    "strategies": [
                        {
                            "strategy_id": "triple_screen",
                            "display_name": "三重滤网",
                            "status": "pending_implementation",
                        },
                        {
                            "strategy_id": "neil_turtle",
                            "display_name": "海龟",
                            "status": "pending_implementation",
                        },
                    ],
                    "composite_sources": [
                        {"source": "announcements", "status": "weak_hint_only"},
                        {"source": "tencent_external", "status": "pending_integration"},
                    ],
                },
            },
        }
        if not debug:
            self._strip_signal_raw_refs(payload)
        return payload

    @staticmethod
    def _strip_signal_raw_refs(payload: dict[str, Any]) -> None:
        tiers = payload.get("tiers")
        if not isinstance(tiers, dict):
            return
        for tier_items in tiers.values():
            if not isinstance(tier_items, list):
                continue
            for candidate in tier_items:
                if not isinstance(candidate, dict):
                    continue
                signals = candidate.get("signals")
                if not isinstance(signals, list):
                    continue
                for signal in signals:
                    if isinstance(signal, dict):
                        signal.pop("raw_refs", None)

    def _safe_ref_path(self, raw_path: str) -> str:
        raw_path = str(raw_path or "").strip()
        if not raw_path:
            return ""
        return "internal"

    def _build_factor_signals(
        self,
        *,
        db_path: Path,
        target_date: str,
        hit_names: list[str],
        hit_items: list[dict[str, Any]],
        pct_change: float,
        amount: float,
        sector_lv1: Optional[str],
        sector_rank: dict[str, int],
        reason_items: list[dict[str, Any]],
        reason_lines: list[str],
        ann_titles: list[str],
        lab_items: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        signals: list[dict[str, Any]] = [
            {
                "source": "screeners",
                "name": "internal_formula_hits",
                "value": float(len(hit_names)),
                "direction": "positive",
                "confidence_hint": None,
                "evidence": (
                    [f"命中筛选器：{item}" for item in hit_names] if hit_names else []
                ),
                "raw_refs": {},
            },
        ]

        for item in hit_items:
            name = str(
                item.get("screener_name") or item.get("screener_id") or ""
            ).strip()
            if not name:
                continue
            signals.append(
                {
                    "source": "screener",
                    "name": name,
                    "value": 1.0,
                    "direction": "positive",
                    "confidence_hint": None,
                    "evidence": [f"命中：{name}"],
                    "raw_refs": {
                        "screener_id": str(item.get("screener_id") or ""),
                        "artifact_path": self._safe_ref_path(
                            str(item.get("artifact_path") or "")
                        ),
                    },
                }
            )

        signals.extend(
            [
                {
                    "source": "market",
                    "name": "pct_change",
                    "value": float(pct_change),
                    "direction": "positive" if pct_change >= 0 else "negative",
                    "confidence_hint": None,
                    "evidence": [f"pct_change={pct_change:.4f}（单位：%）"],
                    "raw_refs": {
                        "db_path": self._safe_ref_path(str(db_path)),
                        "table": "daily_prices",
                        "trade_date": target_date,
                    },
                },
                {
                    "source": "market",
                    "name": "amount",
                    "value": float(amount),
                    "direction": "positive",
                    "confidence_hint": None,
                    "evidence": [f"amount={amount:.0f}（单位：元）"],
                    "raw_refs": {
                        "db_path": self._safe_ref_path(str(db_path)),
                        "table": "daily_prices",
                        "trade_date": target_date,
                    },
                },
                {
                    "source": "sector",
                    "name": "sector_lv1_top5_by_amount",
                    "value": 1.0 if (sector_lv1 and sector_lv1 in sector_rank) else 0.0,
                    "direction": "positive",
                    "confidence_hint": None,
                    "evidence": (
                        [f"sector_lv1={sector_lv1} rank={sector_rank[sector_lv1]}/5"]
                        if (sector_lv1 and sector_lv1 in sector_rank)
                        else [f"sector_lv1={sector_lv1 or 'unknown'} not_in_top5"]
                    ),
                    "raw_refs": {},
                },
                {
                    "source": "limit_up_reasons",
                    "name": "limit_up_reason_hits",
                    "value": float(len(reason_items)),
                    "direction": "positive",
                    "confidence_hint": None,
                    "evidence": reason_lines,
                    "raw_refs": {
                        "db_path": self._safe_ref_path(str(db_path)),
                        "table": "limit_up_reasons",
                        "trade_date": target_date,
                    },
                },
                {
                    "source": "announcements",
                    "name": "announcement_hits",
                    "value": float(len(ann_titles)),
                    "direction": "neutral",
                    "confidence_hint": None,
                    "evidence": (
                        [f"公告：{title}" for title in ann_titles[:3]]
                        if ann_titles
                        else []
                    ),
                    "raw_refs": {
                        "db_path": self._safe_ref_path(str(db_path)),
                        "table": "announcements",
                        "date": target_date,
                    },
                },
            ]
        )

        if lab_items:
            lab_names = [
                str(item.get("lab_name") or item.get("lab_id") or "").strip()
                for item in lab_items
            ]
            lab_names = [name for name in lab_names if name]
            signals.append(
                {
                    "source": "labs",
                    "name": "lab_hits",
                    "value": float(len(lab_names)),
                    "direction": "positive",
                    "confidence_hint": None,
                    "evidence": (
                        [f"命中实验室：{name}" for name in lab_names]
                        if lab_names
                        else []
                    ),
                    "raw_refs": {},
                }
            )
            for item in lab_items:
                lab_name = str(item.get("lab_name") or item.get("lab_id") or "").strip()
                if not lab_name:
                    continue
                signals.append(
                    {
                        "source": "lab",
                        "name": lab_name,
                        "value": 1.0,
                        "direction": "positive",
                        "confidence_hint": None,
                        "evidence": [f"实验室命中：{lab_name}"],
                        "raw_refs": {
                            "lab_id": str(item.get("lab_id") or ""),
                            "artifact_id": str(item.get("artifact_id") or ""),
                            "artifact_path": self._safe_ref_path(
                                str(item.get("artifact_path") or "")
                            ),
                        },
                    }
                )

        return signals

    def _load_lab_hits_for_target_date(
        self, *, target_date: str
    ) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
        registry = LabRegistry.from_file(self._labs_config)
        enabled_labs = [lab for lab in registry.labs if lab.enabled]

        hits: dict[str, list[dict[str, Any]]] = {}
        status_items: list[dict[str, Any]] = []

        for lab in enabled_labs:
            for artifact in lab.artifacts:
                artifact_id = str(getattr(artifact, "artifact_id", "") or "")
                run_ledger_path, run_artifact_path = self._lab_run_paths(
                    target_date=target_date, lab_id=lab.lab_id
                )
                candidate_files: list[Path] = []
                if run_artifact_path.exists():
                    candidate_files.append(run_artifact_path)
                artifact_path_text = str(getattr(artifact, "path", "") or "")
                if artifact_path_text:
                    candidate_files.append(
                        (self.project_root / artifact_path_text).resolve()
                    )
                if not candidate_files:
                    continue

                artifact_file = candidate_files[0]
                status_entry: dict[str, Any] = {
                    "lab_id": lab.lab_id,
                    "lab_name": lab.display_name,
                    "artifact_id": artifact_id,
                    "artifact_path": self._safe_ref_path(str(artifact_file)),
                    "status": "missing",
                    "target_date": target_date,
                    "extracted_stock_count": 0,
                }
                if not artifact_file.exists():
                    status_items.append(status_entry)
                    continue

                try:
                    raw_payload = json.loads(artifact_file.read_text(encoding="utf-8"))
                except Exception:
                    status_entry["status"] = "unparseable"
                    status_items.append(status_entry)
                    continue

                if not isinstance(raw_payload, (dict, list)):
                    status_entry["status"] = "unparseable"
                    status_items.append(status_entry)
                    continue

                if (
                    isinstance(raw_payload, dict)
                    and "artifacts" in raw_payload
                    and isinstance(raw_payload.get("artifacts"), dict)
                ):
                    codes = self._extract_stock_codes_from_payload(
                        raw_payload["artifacts"].get(artifact_id)
                    )
                else:
                    codes = self._extract_stock_codes_from_payload(raw_payload)
                status_entry["extracted_stock_count"] = len(codes)
                if not codes:
                    status_entry["status"] = "no_stock_list"
                    status_items.append(status_entry)
                    continue

                status_entry["status"] = "ok"
                status_items.append(status_entry)
                for code in sorted(codes):
                    hits.setdefault(code, []).append(
                        {
                            "lab_id": lab.lab_id,
                            "lab_name": lab.display_name,
                            "artifact_id": artifact_id,
                        }
                    )

        return hits, status_items

    @staticmethod
    def _extract_stock_codes_from_payload(payload: object) -> set[str]:
        codes: set[str] = set()

        def _maybe_add(value: object) -> None:
            if not isinstance(value, str):
                return
            text = value.strip()
            if not text:
                return
            core = text.split(".", 1)[0].strip()
            if re.fullmatch(r"\d{6}", core):
                codes.add(core)

        if isinstance(payload, dict):
            for key in ("stocks", "picks", "pool", "watch_pool", "candidates"):
                value = payload.get(key)
                if isinstance(value, list):
                    for item in value:
                        _maybe_add(item)
                        if isinstance(item, dict):
                            _maybe_add(item.get("code"))
                            _maybe_add(item.get("stock_code"))
            for value in payload.values():
                if isinstance(value, list):
                    for item in value:
                        _maybe_add(item)
                        if isinstance(item, dict):
                            _maybe_add(item.get("code"))
                            _maybe_add(item.get("stock_code"))
        elif isinstance(payload, list):
            for item in payload:
                _maybe_add(item)
                if isinstance(item, dict):
                    _maybe_add(item.get("code"))
                    _maybe_add(item.get("stock_code"))

        return codes

    @staticmethod
    def _compute_focus_sectors_top5(
        universe_rows: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        sector_amount: dict[str, float] = {}
        for row in universe_rows:
            sector = str(row.get("sector_lv1") or "").strip() or "unknown"
            amount = float(row.get("amount") or 0.0)
            sector_amount[sector] = sector_amount.get(sector, 0.0) + amount
        top5 = sorted(sector_amount.items(), key=lambda kv: kv[1], reverse=True)[:5]
        return [
            {"sector_lv1": key, "amount_sum": round(value, 2)} for key, value in top5
        ]

    @staticmethod
    def _select_universe_rows(
        *, db_path: Path, target_date: str, limit: int
    ) -> list[dict[str, Any]]:
        try:
            conn = sqlite3.connect(str(db_path))
        except Exception as exc:
            raise ApiError(
                status_code=HTTPStatus.BAD_REQUEST,
                code="invalid_db",
                message=f"failed to open sqlite db (see server logs)",
                details={"db_path": _safe_ref_path(str(db_path))},
            )

        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT dp.code, COALESCE(s.name,''), COALESCE(s.sector_lv1,''), COALESCE(s.sector_lv2,''), "
                "dp.close, dp.preclose, dp.pct_change, dp.amount "
                "FROM daily_prices dp "
                "JOIN stocks s ON s.code = dp.code "
                "WHERE dp.trade_date = ? "
                "AND COALESCE(s.asset_type, 'stock') = 'stock' "
                "AND COALESCE(s.is_delisted, 0) = 0 "
                "ORDER BY dp.amount DESC "
                "LIMIT ?",
                (target_date, int(limit)),
            )
            rows = cursor.fetchall()
        except Exception as exc:
            raise ApiError(
                status_code=HTTPStatus.BAD_REQUEST,
                code="invalid_db_query",
                message=f"failed to query sqlite db for universe rows (see server logs)",
                details={
                    "db_path": _safe_ref_path(str(db_path)),
                    "table": "daily_prices",
                    "trade_date": target_date,
                },
            )
        finally:
            conn.close()

        items: list[dict[str, Any]] = []
        for (
            code,
            name,
            sector_lv1,
            sector_lv2,
            close,
            preclose,
            pct_change,
            amount,
        ) in rows:
            code_str = str(code)
            name_str = str(name or "")
            if code_str.startswith("399"):
                continue
            if code_str.startswith(("43", "83", "87", "88")):
                continue
            if any(keyword in name_str for keyword in ("*ST", "ST", "PT")):
                continue
            items.append(
                {
                    "stock_code": code_str,
                    "stock_name": name_str,
                    "sector_lv1": str(sector_lv1 or "").strip() or None,
                    "sector_lv2": str(sector_lv2 or "").strip() or None,
                    "close": float(close) if close is not None else None,
                    "preclose": float(preclose) if preclose is not None else None,
                    "pct_change": float(pct_change) if pct_change is not None else None,
                    "amount": float(amount) if amount is not None else 0.0,
                }
            )
        items.sort(key=lambda item: float(item.get("amount") or 0.0), reverse=True)
        return items

    def _load_screener_hits_for_date(
        self, *, target_date: str
    ) -> dict[str, list[dict[str, str]]]:
        registry = load_screener_registry(self._screeners_registry_config)
        enabled = [s for s in registry.screeners if s.enabled]
        result: dict[str, list[dict[str, str]]] = {}
        for screener in enabled:
            screener_id = screener.screener_id
            screener_name = screener.display_name.strip() or screener_id
            artifact = read_screener_run_artifact(
                project_root=self.project_root,
                target_date=target_date,
                screener_id=screener_id,
            )
            picks = artifact.get("picks") if isinstance(artifact, dict) else None
            if not isinstance(picks, list):
                continue
            for item in picks:
                code = str(item).split(".", 1)[0].strip()
                if not code:
                    continue
                result.setdefault(code, []).append(
                    {
                        "screener_id": screener_id,
                        "screener_name": screener_name,
                    }
                )
        return result

    @staticmethod
    def _table_exists(*, db_path: Path, table: str) -> bool:
        try:
            conn = sqlite3.connect(str(db_path))
        except Exception:
            return False
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
            )
            return cursor.fetchone() is not None
        finally:
            conn.close()

    def _load_limit_up_reasons_for_date(
        self, *, db_path: Path, target_date: str
    ) -> dict[str, list[dict[str, Any]]]:
        if not self._table_exists(db_path=db_path, table="limit_up_reasons"):
            return {}
        try:
            conn = sqlite3.connect(str(db_path))
        except Exception:
            return {}
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT code, reason, category, source FROM limit_up_reasons WHERE trade_date = ?",
                (target_date,),
            )
            rows = cursor.fetchall()
        except Exception:
            return {}
        finally:
            conn.close()

        result: dict[str, list[dict[str, Any]]] = {}
        for code, reason, category, source in rows:
            code_str = str(code).split(".", 1)[0].strip()
            if not code_str:
                continue
            result.setdefault(code_str, []).append(
                {
                    "reason": str(reason or ""),
                    "category": str(category or ""),
                    "source": str(source or ""),
                }
            )
        return result

    def _load_announcements_for_date(
        self, *, db_path: Path, target_date: str
    ) -> dict[str, list[str]]:
        if not self._table_exists(db_path=db_path, table="announcements"):
            return {}
        try:
            conn = sqlite3.connect(str(db_path))
        except Exception:
            return {}
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT code, title, type FROM announcements WHERE DATE(publish_date) = ?",
                (target_date,),
            )
            rows = cursor.fetchall()
        except Exception:
            return {}
        finally:
            conn.close()

        result: dict[str, list[str]] = {}
        for code, title, type_value in rows:
            code_str = str(code).split(".", 1)[0].strip()
            if not code_str:
                continue
            title_str = str(title or "").strip()
            type_str = str(type_value or "").strip()
            if type_str and title_str:
                text = f"{type_str}：{title_str}"
            else:
                text = title_str
            if text:
                result.setdefault(code_str, []).append(text)
        return result

    def _validate_units_in_stock_db(
        self, *, db_path: Path, sample_limit: int
    ) -> dict[str, Any]:
        try:
            conn = sqlite3.connect(str(db_path))
        except Exception as exc:
            raise ApiError(
                status_code=HTTPStatus.BAD_REQUEST,
                code="invalid_db",
                message=f"failed to open sqlite db (see server logs)",
                details={"db_path": _safe_ref_path(str(db_path))},
            )

        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT trade_date, code, close, preclose, pct_change, volume, amount "
                "FROM daily_prices "
                "WHERE close IS NOT NULL AND preclose IS NOT NULL AND preclose > 0 "
                "AND volume IS NOT NULL AND volume > 0 "
                "AND amount IS NOT NULL AND amount > 0 "
                "ORDER BY trade_date DESC "
                "LIMIT ?",
                (int(sample_limit),),
            )
            rows = cursor.fetchall()
        except Exception as exc:
            raise ApiError(
                status_code=HTTPStatus.BAD_REQUEST,
                code="invalid_db_query",
                message=f"failed to query daily_prices for unit validation (see server logs)",
                details={"db_path": _safe_ref_path(str(db_path)), "table": "daily_prices"},
            )
        finally:
            conn.close()

        if not rows:
            return {
                "status": "warning",
                "message": "无法判断",
                "reasons": ["daily_prices 中没有足够的有效样本行用于单位校验。"],
                "evidence": ["table：daily_prices"],
            }

        pct_diffs_percent: list[float] = []
        pct_diffs_decimal: list[float] = []
        lot_rel_errors: list[float] = []
        share_rel_errors: list[float] = []
        evidence_samples: list[dict[str, Any]] = []

        for trade_date, code, close, preclose, pct_change, volume, amount in rows:
            close_f: Optional[float]
            preclose_f: Optional[float]
            pct_f: Optional[float]
            vol_f: Optional[float]
            amt_f: Optional[float]
            try:
                close_f = float(close)
                preclose_f = float(preclose)
                pct_f = float(pct_change)
                vol_f = float(volume)
                amt_f = float(amount)
            except (TypeError, ValueError):
                close_f = None
                preclose_f = None
                pct_f = None
                vol_f = None
                amt_f = None
            if (
                close_f is None
                or preclose_f is None
                or pct_f is None
                or vol_f is None
                or amt_f is None
            ):
                continue

            if close_f <= 0 or preclose_f <= 0 or vol_f <= 0 or amt_f <= 0:
                continue

            pct_calc_percent = (close_f - preclose_f) * 100.0 / preclose_f
            pct_calc_decimal = pct_calc_percent / 100.0
            pct_diffs_percent.append(abs(pct_f - pct_calc_percent))
            pct_diffs_decimal.append(abs(pct_f - pct_calc_decimal))

            avg_price_by_share = amt_f / vol_f
            avg_price_by_lot = amt_f / (vol_f * 100.0)
            share_rel_errors.append(abs(avg_price_by_share - close_f) / close_f)
            lot_rel_errors.append(abs(avg_price_by_lot - close_f) / close_f)

            if len(evidence_samples) < 8:
                evidence_samples.append(
                    {
                        "trade_date": str(trade_date),
                        "code": str(code),
                        "close": close_f,
                        "preclose": preclose_f,
                        "pct_change_db": pct_f,
                        "pct_change_calc_percent": pct_calc_percent,
                        "volume_db": vol_f,
                        "amount_db": amt_f,
                        "avg_price_amount_div_volume": avg_price_by_share,
                        "avg_price_amount_div_volume_x100": avg_price_by_lot,
                    }
                )

        if not pct_diffs_percent or not lot_rel_errors:
            return {
                "status": "warning",
                "message": "无法判断",
                "reasons": ["样本行存在，但数值字段无法解析或不满足校验条件。"],
                "evidence": ["table：daily_prices"],
            }

        pct_percent_median = statistics.median(pct_diffs_percent)
        pct_decimal_median = statistics.median(pct_diffs_decimal)
        if pct_percent_median <= pct_decimal_median:
            pct_unit = "percent"
            pct_median_abs_diff = pct_percent_median
        else:
            pct_unit = "decimal"
            pct_median_abs_diff = pct_decimal_median

        lot_median_rel_error = statistics.median(lot_rel_errors)
        share_median_rel_error = statistics.median(share_rel_errors)
        lot_wins = sum(1 for a, b in zip(lot_rel_errors, share_rel_errors) if a < b)
        share_wins = sum(1 for a, b in zip(lot_rel_errors, share_rel_errors) if b < a)
        total_compared = lot_wins + share_wins

        volume_unit: Optional[str]
        if total_compared == 0:
            volume_unit = None
        else:
            lot_win_ratio = lot_wins / total_compared
            share_win_ratio = share_wins / total_compared
            if lot_win_ratio >= 0.9 and lot_median_rel_error <= 0.2:
                volume_unit = "lot_100_shares"
            elif share_win_ratio >= 0.9 and share_median_rel_error <= 0.2:
                volume_unit = "share"
            else:
                volume_unit = None

        issues: list[str] = []
        if volume_unit is None:
            issues.append(
                "无法可靠判定 volume 的单位（股/手）；amount 与 close 的关系不够一致。"
            )
        if pct_median_abs_diff > 0.2:
            issues.append(
                "pct_change 与 (close-preclose)/preclose 的差异偏大，疑似单位或口径不一致。"
            )

        status = "ok" if not issues else "warning"
        message = "通过" if status == "ok" else "存在疑点"
        reasons: list[str] = []

        reasons.append("价格字段（open/high/low/close/preclose）：建议按 元/股 处理。")
        reasons.append("成交额字段（amount）：建议按 元 处理。")
        reasons.append(
            "市值字段（circulating_market_cap/total_market_cap）：建议按 元 处理。"
        )
        reasons.append(
            f"涨跌幅字段（pct_change）：更符合 {('百分比' if pct_unit == 'percent' else '小数')} 口径。"
        )
        if volume_unit == "lot_100_shares":
            reasons.append("成交量字段（volume）：更符合 手（1手=100股）口径。")
        elif volume_unit == "share":
            reasons.append("成交量字段（volume）：更符合 股 口径。")
        else:
            reasons.append("成交量字段（volume）：口径不明，需要在入库前明确。")

        evidence = [
            f"pct_change 口径候选：percent vs decimal；中位绝对差：{pct_median_abs_diff:.6f}",
            f"volume 口径候选：share vs lot(100 shares)；相对误差中位数：share={share_median_rel_error:.6f}, lot={lot_median_rel_error:.6f}",
            f"volume 判定对比胜率：share={share_wins}/{total_compared}, lot={lot_wins}/{total_compared}",
        ]

        if issues:
            evidence.extend([f"问题：{issue}" for issue in issues])

        recommended = {
            "price": {"unit": "yuan_per_share"},
            "amount": {"unit": "yuan"},
            "market_cap": {"unit": "yuan"},
            "pct_change": {"unit": pct_unit},
            "volume": {"unit": volume_unit or "unknown"},
        }

        return {
            "status": status,
            "message": message,
            "reasons": reasons,
            "recommended_units": recommended,
            "evidence": evidence,
            "sample_rows": evidence_samples,
        }

    def _evaluate_universe_base_filters(self, *, stock_code: str) -> dict[str, Any]:
        db_path = Path(
            os.environ.get("NEOTRADE3_STOCK_DB_PATH")
            or str(self._stock_db_default_path)
        ).expanduser()
        if not db_path.exists() or not db_path.is_file():
            return {
                "result": None,
                "message": "无法判断",
                "reasons": ["NeoTrade3 行情库未初始化（stock_data.db 不存在）。"],
                "evidence": ["可通过数据主链初始化行情库。"],
            }

        base_code = stock_code.strip().split(".", 1)[0]
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            cursor.execute(
                "SELECT code,name,is_delisted,circulating_market_cap,total_market_cap,asset_type FROM stocks WHERE code = ?",
                (base_code,),
            )
            row = cursor.fetchone()
        except Exception as exc:
            return {
                "result": None,
                "message": "无法判断",
                "reasons": [f"读取行情库失败 (see server logs)"],
                "evidence": ["表：stocks", f"code：{base_code}"],
            }
        finally:
            try:
                conn.close()
            except sqlite3.Error as exc:
                logger.debug("failed to close sqlite connection: %s", exc)

        if row is None:
            return {
                "result": None,
                "message": "无法判断",
                "reasons": ["行情库中不存在该股票代码（stocks 表无记录）。"],
                "evidence": ["表：stocks", f"code：{base_code}"],
            }

        (
            code,
            name,
            is_delisted,
            circulating_market_cap,
            total_market_cap,
            asset_type,
        ) = row
        stock_name = str(name or "").strip()
        reasons: list[str] = []

        if str(asset_type or "stock") != "stock":
            reasons.append(f"资产类型不是股票（asset_type={asset_type}）。")
        if str(code).startswith("399") or ("指数" in stock_name):
            reasons.append("指数标的排除。")
        if str(code).startswith(("43", "83", "87", "88")):
            reasons.append("北交所标的排除。")
        if int(is_delisted or 0) == 1:
            reasons.append("退市标的排除（is_delisted=1）。")
        if any(keyword in stock_name for keyword in ("*ST", "ST", "PT")):
            reasons.append("ST/退市风险标的排除（名称包含 ST/*ST/PT）。")

        result: bool = not reasons
        evidence = [
            f"code：{code}",
            f"name：{stock_name or 'unknown'}",
            f"is_delisted：{int(is_delisted or 0)}",
        ]
        if circulating_market_cap is not None:
            evidence.append(
                f"circulating_market_cap：{float(circulating_market_cap):.0f} 元"
            )
        if total_market_cap is not None:
            evidence.append(f"total_market_cap：{float(total_market_cap):.0f} 元")

        return {
            "result": result,
            "message": "通过" if result else "未通过",
            "reasons": ["基础过滤通过。"] if result else reasons,
            "evidence": evidence,
        }

    def stocks_lookup_view(self, *, stock_codes: list[str]) -> dict[str, Any]:
        normalized: list[str] = []
        seen: set[str] = set()
        for raw in stock_codes:
            value = str(raw or "").strip()
            if not value:
                continue
            base = value.split(".", 1)[0]
            if base in seen:
                continue
            seen.add(base)
            normalized.append(base)

        if not normalized:
            raise ApiError(
                status_code=HTTPStatus.BAD_REQUEST,
                code="invalid_stock_codes",
                message="stock_codes must contain at least one non-empty code",
            )

        db_path = Path(
            os.environ.get("NEOTRADE3_STOCK_DB_PATH")
            or str(self._stock_db_default_path)
        ).expanduser()
        if not db_path.exists() or not db_path.is_file():
            raise ApiError(
                status_code=HTTPStatus.SERVICE_UNAVAILABLE,
                code="stock_db_not_ready",
                message="NeoTrade3 行情库未初始化（stock_data.db 不存在）",
                details={"expected_path": _safe_ref_path(str(db_path))},
            )

        placeholders = ",".join("?" for _ in normalized)
        rows: list[tuple[object, object, object]] = []
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            cursor.execute(
                f"SELECT code,name,is_delisted FROM stocks WHERE code IN ({placeholders})",
                tuple(normalized),
            )
            fetched = cursor.fetchall()
            if isinstance(fetched, list):
                rows = fetched
        except Exception as exc:
            raise ApiError(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                code="stock_lookup_failed",
                message=f"读取行情库失败 (see server logs)",
                details={"db_path": _safe_ref_path(str(db_path))},
            )
        finally:
            try:
                conn.close()
            except Exception:
                pass

        by_code: dict[str, dict[str, Any]] = {}
        for code, name, is_delisted in rows:
            c = str(code or "").strip()
            if not c:
                continue
            by_code[c] = {
                "stock_code": c,
                "stock_name": str(name or "").strip() or c,
                "is_delisted": int(is_delisted or 0),
            }

        items: list[dict[str, Any]] = []
        for code in normalized:
            item = by_code.get(code)
            if item is None:
                items.append(
                    {
                        "stock_code": code,
                        "stock_name": code,
                        "is_delisted": None,
                        "missing": True,
                    }
                )
            else:
                items.append(item)

        return {
            "_meta": {"status": "ok"},
            "count": len(items),
            "items": items,
        }

    def stocks_coverage_view(self, *, target_date: date) -> dict[str, Any]:
        db_path = Path(
            os.environ.get("NEOTRADE3_STOCK_DB_PATH")
            or str(self._stock_db_default_path)
        ).expanduser()
        if not db_path.exists() or not db_path.is_file():
            raise ApiError(
                status_code=HTTPStatus.SERVICE_UNAVAILABLE,
                code="stock_db_not_ready",
                message="NeoTrade3 行情库未初始化（stock_data.db 不存在）",
                details={"expected_path": _safe_ref_path(str(db_path))},
            )

        active_stock_count = 0
        priced_stock_count = 0
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(1) FROM stocks "
                "WHERE COALESCE(asset_type, 'stock') = 'stock' "
                "AND COALESCE(is_delisted, 0) = 0"
            )
            active_stock_count = int(cursor.fetchone()[0] or 0)
            cursor.execute(
                "SELECT COUNT(1) FROM daily_prices dp "
                "JOIN stocks s ON s.code = dp.code "
                "WHERE dp.trade_date = ? "
                "AND COALESCE(s.asset_type, 'stock') = 'stock' "
                "AND COALESCE(s.is_delisted, 0) = 0",
                (target_date.isoformat(),),
            )
            priced_stock_count = int(cursor.fetchone()[0] or 0)
        except Exception as exc:
            raise ApiError(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                code="stock_coverage_failed",
                message=f"读取行情库失败 (see server logs)",
                details={"db_path": _safe_ref_path(str(db_path))},
            )
        finally:
            try:
                conn.close()
            except Exception:
                pass

        return {
            "_meta": {"status": "ok"},
            "target_date": target_date.isoformat(),
            "coverage": {
                "active_stock_count": active_stock_count,
                "priced_stock_count": priced_stock_count,
            },
        }

    def _apply_universe_filters_to_screener_result(
        self,
        *,
        passed: Optional[bool],
        artifact_status: str,
        universe_base: dict[str, Any],
        stock_code: str,
        screener_parameters: dict[str, Any],
        parameters_source: str,
    ) -> tuple[Optional[bool], list[str], list[str]]:
        reasons: list[str] = []
        extra_evidence: list[str] = []

        if passed is True:
            reasons.append("该股票出现在筛选结果中。")
        elif passed is False:
            reasons.append("该股票未出现在筛选结果中。")
        else:
            if artifact_status == "pending_implementation":
                reasons.append("该筛选器算法当前为占位状态，无法给出通过/未通过结论。")
            else:
                reasons.append("结果结构不完整，无法判定通过/未通过。")

        base_result = universe_base.get("result")
        if base_result is False:
            base_reasons = universe_base.get("reasons")
            if isinstance(base_reasons, list) and base_reasons:
                if passed is True:
                    reasons.append(
                        "基础过滤提示该股票应被排除，但当日筛选结果中仍出现。"
                    )
                    extra_evidence.append(
                        "提示：筛选器可能尚未接入基础过滤，或产物来自不同口径。"
                    )
                else:
                    passed = False
                    reasons = [f"基础过滤：{str(item)}" for item in base_reasons]
            base_evidence = universe_base.get("evidence")
            if isinstance(base_evidence, list):
                extra_evidence.extend(
                    [f"基础过滤证据：{str(item)}" for item in base_evidence]
                )

        if base_result is True:
            universe_filters = screener_parameters.get("universe_filters")
            if isinstance(universe_filters, dict):
                min_market_cap = universe_filters.get("min_market_cap")
            else:
                min_market_cap = None

            if isinstance(min_market_cap, (int, float)):
                extra_evidence.append(
                    f"市值阈值来源：{'当日运行参数' if parameters_source == 'artifact' else '筛选器配置当前值'}"
                )
                extra_evidence.append(
                    f"市值阈值(min_market_cap)：{float(min_market_cap)}（单位：元）"
                )

                cap_value: Optional[float] = None
                for item in universe_base.get("evidence", []):
                    if isinstance(item, str) and item.startswith(
                        "circulating_market_cap："
                    ):
                        raw = item.split("：", 1)[-1].strip().split(" ", 1)[0]
                        try:
                            cap_value = float(raw)
                        except ValueError:
                            cap_value = None
                        break

                if cap_value is None:
                    reasons.append("市值过滤无法判定：行情库缺少流通市值。")
                elif cap_value < float(min_market_cap):
                    if passed is True:
                        reasons.append(
                            "市值过滤提示该股票应被排除，但当日筛选结果中仍出现。"
                        )
                    else:
                        passed = False
                        reasons = [
                            f"市值过滤未通过：流通市值 {cap_value:.0f} 元 < 阈值 {float(min_market_cap):.0f} 元。"
                        ]
                else:
                    reasons.append("市值过滤通过。")

        return passed, reasons, extra_evidence

    @staticmethod
    def _deep_merge_dicts(base: object, override: object) -> dict[str, Any]:
        if not isinstance(base, dict):
            base = {}
        if not isinstance(override, dict):
            override = {}

        merged: dict[str, Any] = {str(key): value for key, value in base.items()}
        for key, value in override.items():
            key = str(key)
            existing = merged.get(key)
            if isinstance(existing, dict) and isinstance(value, dict):
                merged[key] = BootstrapApiService._deep_merge_dicts(existing, value)
            else:
                merged[key] = value
        return merged

    def screener_run_detail_view(
        self, *, target_date: str, screener_id: str
    ) -> dict[str, Any]:
        record = read_screener_run_ledger(
            project_root=self.project_root,
            target_date=target_date,
            screener_id=screener_id,
        )
        if record is None:
            raise ApiError(
                status_code=HTTPStatus.NOT_FOUND,
                code="screener_run_not_found",
                message="screener run ledger not found",
                details={"target_date": target_date, "screener_id": screener_id},
            )

        artifact = read_screener_run_artifact(
            project_root=self.project_root,
            target_date=target_date,
            screener_id=screener_id,
        )
        if artifact is None:
            raise ApiError(
                status_code=HTTPStatus.NOT_FOUND,
                code="screener_run_artifact_not_found",
                message="screener run artifact not found",
                details={"target_date": target_date, "screener_id": screener_id},
            )

        return {
            "_meta": {"status": "ok"},
            "screener_run": record.__dict__,
            "screener_result": artifact,
        }

    def screener_run_artifact_download_view(
        self,
        *,
        target_date: str,
        screener_id: str,
    ) -> ApiBinaryResponse:
        record = read_screener_run_ledger(
            project_root=self.project_root,
            target_date=target_date,
            screener_id=screener_id,
        )
        if record is None:
            raise ApiError(
                status_code=HTTPStatus.NOT_FOUND,
                code="screener_run_not_found",
                message="screener run ledger not found",
                details={"target_date": target_date, "screener_id": screener_id},
            )

        expected_root = self.project_root / "var/artifacts/screener_runs" / target_date
        artifact_filename = Path(str(record.artifact_path or "")).name.strip()
        if not artifact_filename:
            artifact_filename = f"screener_{screener_id}_result.json"
        artifact_path = expected_root / artifact_filename
        if not artifact_path.exists():
            raise ApiError(
                status_code=HTTPStatus.NOT_FOUND,
                code="screener_run_artifact_not_found",
                message="screener run artifact not found",
                details={"target_date": target_date, "screener_id": screener_id},
            )

        filename = artifact_path.name
        return ApiBinaryResponse(
            body=artifact_path.read_bytes(),
            content_type="application/json; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    def screener_run_csv_download_view(
        self,
        *,
        target_date: str,
        screener_id: str,
    ) -> ApiBinaryResponse:
        artifact = read_screener_run_artifact(
            project_root=self.project_root,
            target_date=target_date,
            screener_id=screener_id,
        )
        if artifact is None:
            raise ApiError(
                status_code=HTTPStatus.NOT_FOUND,
                code="screener_run_artifact_not_found",
                message="screener run artifact not found",
                details={"target_date": target_date, "screener_id": screener_id},
            )

        picks = artifact.get("picks")

        def normalize_code(value: object) -> Optional[str]:
            if value is None:
                return None
            if isinstance(value, str):
                v = value.strip()
                return v if v else None
            if isinstance(value, dict):
                code = value.get("code")
                if isinstance(code, str) and code.strip():
                    return code.strip()
            return None

        codes: list[str] = []
        if isinstance(picks, list):
            for item in picks:
                code = normalize_code(item)
                if code is None:
                    continue
                codes.append(code)
        codes = list(dict.fromkeys([c for c in codes if str(c).strip()]))

        if not codes:
            csv_body = "rank,stock_code,stock_name\r\n".encode("utf-8-sig")
            filename = f"screener_{screener_id}_{target_date}.csv"
            return ApiBinaryResponse(
                body=csv_body,
                content_type="text/csv; charset=utf-8",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )

        def base_code(code: str) -> str:
            return str(code).split(".", 1)[0].strip()

        lookup_keys = sorted(set([str(c).strip() for c in codes] + [base_code(c) for c in codes]))
        db_path = Path(
            os.environ.get("NEOTRADE3_STOCK_DB_PATH")
            or str(self._stock_db_default_path)
        ).expanduser()
        name_map: dict[str, str] = {}
        if db_path.exists() and db_path.is_file():
            placeholders = ",".join("?" for _ in lookup_keys)
            conn = sqlite3.connect(str(db_path))
            try:
                cursor = conn.cursor()
                cursor.execute(
                    f"SELECT code, name FROM stocks WHERE code IN ({placeholders})",
                    tuple(lookup_keys),
                )
                for row_code, row_name in cursor.fetchall():
                    c = str(row_code or "").strip()
                    n = str(row_name or "").strip()
                    if c and n:
                        name_map[c] = n
            finally:
                conn.close()

        missing: list[str] = []
        resolved: list[tuple[int, str, str]] = []
        for idx, code in enumerate(codes, start=1):
            c = str(code).strip()
            n = name_map.get(c) or name_map.get(base_code(c)) or ""
            n = str(n).strip()
            if not c or not n:
                missing.append(c or str(code))
                continue
            resolved.append((idx, c, n))
        if missing:
            raise ApiError(
                status_code=HTTPStatus.SERVICE_UNAVAILABLE,
                code="export_validation_failed",
                message="export requires non-empty stock_code and stock_name for every row",
                details={
                    "export": "screener_run_download_csv",
                    "screener_id": screener_id,
                    "target_date": target_date,
                    "missing_names": missing[:50],
                    "missing_count": len(missing),
                },
            )

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["rank", "stock_code", "stock_name"])
        for rank, code, name in resolved:
            writer.writerow([rank, code, name])

        csv_body = output.getvalue().encode("utf-8-sig")
        filename = f"screener_{screener_id}_{target_date}.csv"
        return ApiBinaryResponse(
            body=csv_body,
            content_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    def screener_run_export_csv_view(
        self,
        *,
        screener_id: str,
        target_date: str,
    ) -> ApiBinaryResponse:
        """导出筛选器运行结果为 CSV，包含 stock_code, stock_name, sector, signals, hit_reason 列。"""
        artifact = read_screener_run_artifact(
            project_root=self.project_root,
            target_date=target_date,
            screener_id=screener_id,
        )
        if artifact is None:
            raise ApiError(
                status_code=HTTPStatus.NOT_FOUND,
                code="screener_run_artifact_not_found",
                message="screener run artifact not found",
                details={"target_date": target_date, "screener_id": screener_id},
            )

        picks = artifact.get("picks")
        if not isinstance(picks, list) or not picks:
            # 空结果仍返回带表头的 CSV
            csv_body = (
                "stock_code,stock_name,sector,signals,hit_reason\r\n".encode("utf-8-sig")
            )
            filename = f"screener_{screener_id}_{target_date}_export.csv"
            return ApiBinaryResponse(
                body=csv_body,
                content_type="text/csv; charset=utf-8",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )

        # 提取纯代码列表
        codes: list[str] = []
        for item in picks:
            if isinstance(item, str):
                code = item.split(".", 1)[0].strip()
                if code:
                    codes.append(code)
            elif isinstance(item, dict):
                code = str(item.get("code", "")).split(".", 1)[0].strip()
                if code:
                    codes.append(code)

        # 从数据库批量查询股票名称和板块
        db_path = Path(
            os.environ.get("NEOTRADE3_STOCK_DB_PATH")
            or str(self._stock_db_default_path)
        ).expanduser()
        stock_info: dict[str, dict[str, str]] = {}
        if db_path.exists() and db_path.is_file() and codes:
            unique_codes = list(dict.fromkeys(codes))  # 去重保序
            placeholders = ",".join("?" for _ in unique_codes)
            try:
                conn = sqlite3.connect(str(db_path))
                cursor = conn.cursor()
                cursor.execute(
                    f"SELECT code, name, sector_lv1 FROM stocks WHERE code IN ({placeholders})",
                    tuple(unique_codes),
                )
                for row_code, row_name, row_sector in cursor.fetchall():
                    c = str(row_code or "").strip()
                    if c:
                        stock_info[c] = {
                            "name": str(row_name or "").strip() or c,
                            "sector": str(row_sector or "").strip(),
                        }
            except Exception:
                pass
            finally:
                try:
                    conn.close()
                except Exception:
                    pass

        # 从 decision_trace 中提取 picked_examples 以获取额外信息
        picked_examples_map: dict[str, dict[str, Any]] = {}
        decision_trace = artifact.get("decision_trace")
        if isinstance(decision_trace, list):
            for step in decision_trace:
                if not isinstance(step, dict):
                    continue
                examples = step.get("picked_examples")
                if not isinstance(examples, list):
                    continue
                for ex in examples:
                    if not isinstance(ex, dict):
                        continue
                    ex_code = str(ex.get("code", "")).split(".", 1)[0].strip()
                    if ex_code and ex_code not in picked_examples_map:
                        picked_examples_map[ex_code] = ex

        # 提取筛选器描述作为 signals/hit_reason 的补充
        screener_message = str(artifact.get("message", "")).strip()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["stock_code", "stock_name", "sector", "signals", "hit_reason"])

        missing_names: list[str] = []
        for code in codes:
            info = stock_info.get(code, {})
            stock_name = str(info.get("name") or "").strip()
            if not stock_name:
                missing_names.append(code)
                continue
            sector = info.get("sector", "")

            # signals: 优先从 picked_examples 获取信号日期等信息
            ex = picked_examples_map.get(code)
            signal_parts: list[str] = []
            if isinstance(ex, dict):
                for key, val in ex.items():
                    if key in ("code", "name"):
                        continue
                    if "signal" in key.lower() or "date" in key.lower():
                        signal_parts.append(f"{key}={val}")
            signals = "; ".join(signal_parts) if signal_parts else ""

            # hit_reason: 从 picked_examples 中提取 reason/detail，或用 screener message
            hit_reason = ""
            if isinstance(ex, dict):
                hit_reason = str(ex.get("reason", "") or ex.get("detail", "") or "").strip()
            if not hit_reason:
                hit_reason = screener_message

            writer.writerow([code, stock_name, sector, signals, hit_reason])

        if missing_names:
            raise ApiError(
                status_code=HTTPStatus.SERVICE_UNAVAILABLE,
                code="export_validation_failed",
                message="export requires non-empty stock_code and stock_name for every row",
                details={
                    "export": "screener_run_export_csv",
                    "screener_id": screener_id,
                    "target_date": target_date,
                    "missing_names": missing_names[:50],
                    "missing_count": len(missing_names),
                },
            )

        csv_body = output.getvalue().encode("utf-8-sig")
        filename = f"screener_{screener_id}_{target_date}_export.csv"
        return ApiBinaryResponse(
            body=csv_body,
            content_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    def pools_view(
        self,
        *,
        target_date: date,
        publish_succeeded: bool = False,
    ) -> dict[str, Any]:
        date_key = target_date.isoformat()
        pool_defs = self._build_pool_definitions(target_date=date_key)

        pools: list[dict[str, Any]] = []
        prev_date = self._previous_trading_day(date_key)

        for pool_def in pool_defs:
            pool_id = str(pool_def["pool_id"])
            members = self._resolve_pool_members(pool_id=pool_id, target_date=date_key)
            member_set = set(members)
            added_count = 0
            removed_count = 0
            if prev_date is not None:
                prev_members = self._resolve_pool_members(
                    pool_id=pool_id, target_date=prev_date
                )
                prev_set = set(prev_members)
                added_count = len(sorted(member_set - prev_set))
                removed_count = len(sorted(prev_set - member_set))

            pools.append(
                {
                    "pool_id": pool_id,
                    "display_name": pool_def.get("display_name", pool_id),
                    "pool_type": pool_def.get("pool_type", "unknown"),
                    "source": pool_def.get("source", {}),
                    "target_date": date_key,
                    "previous_date": prev_date,
                    "member_count": len(members),
                    "added_count": int(added_count),
                    "removed_count": int(removed_count),
                    "members_sample": members[:10],
                }
            )

        pools.sort(key=lambda item: str(item.get("pool_id", "")))
        return {
            "target_date": date_key,
            "_meta": {"status": "ok", "publish_succeeded": bool(publish_succeeded)},
            "pools": pools,
        }

    def pool_detail_view(
        self,
        *,
        target_date: date,
        pool_id: str,
        publish_succeeded: bool = False,
    ) -> dict[str, Any]:
        date_key = target_date.isoformat()
        pool_defs = {
            str(item["pool_id"]): item
            for item in self._build_pool_definitions(target_date=date_key)
        }
        pool_def = pool_defs.get(pool_id)
        if pool_def is None:
            raise ApiError(
                status_code=HTTPStatus.NOT_FOUND,
                code="pool_not_found",
                message="unknown pool_id",
                details={"pool_id": pool_id, "known_pools": sorted(pool_defs.keys())},
            )

        members = self._resolve_pool_members(pool_id=pool_id, target_date=date_key)
        prev_date = self._previous_trading_day(date_key)
        added: list[str] = []
        removed: list[str] = []
        if prev_date is not None:
            prev_members = self._resolve_pool_members(pool_id=pool_id, target_date=prev_date)
            added = sorted(set(members) - set(prev_members))
            removed = sorted(set(prev_members) - set(members))

        return {
            "target_date": date_key,
            "_meta": {"status": "ok", "publish_succeeded": bool(publish_succeeded)},
            "pool": {
                "pool_id": pool_id,
                "display_name": pool_def.get("display_name", pool_id),
                "pool_type": pool_def.get("pool_type", "unknown"),
                "source": pool_def.get("source", {}),
                "previous_date": prev_date,
                "member_count": len(members),
                "added_count": len(added),
                "removed_count": len(removed),
                "added": added,
                "removed": removed,
                "members": members,
            },
        }

    def pool_csv_download_view(
        self,
        *,
        target_date: date,
        pool_id: str,
    ) -> ApiBinaryResponse:
        date_key = target_date.isoformat()
        members = self._resolve_pool_members(pool_id=pool_id, target_date=date_key)
        members = list(dict.fromkeys([str(c).strip() for c in members if str(c).strip()]))
        if not members:
            csv_body = "rank,stock_code,stock_name\r\n".encode("utf-8-sig")
            filename = f"pool_{pool_id}_{date_key}.csv"
            return ApiBinaryResponse(
                body=csv_body,
                content_type="text/csv; charset=utf-8",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )

        def base_code(code: str) -> str:
            return str(code).split(".", 1)[0].strip()

        lookup_keys = sorted(set([str(c).strip() for c in members] + [base_code(c) for c in members]))
        db_path = Path(
            os.environ.get("NEOTRADE3_STOCK_DB_PATH")
            or str(self._stock_db_default_path)
        ).expanduser()
        name_map: dict[str, str] = {}
        if db_path.exists() and db_path.is_file():
            placeholders = ",".join("?" for _ in lookup_keys)
            conn = sqlite3.connect(str(db_path))
            try:
                cursor = conn.cursor()
                cursor.execute(
                    f"SELECT code, name FROM stocks WHERE code IN ({placeholders})",
                    tuple(lookup_keys),
                )
                for row_code, row_name in cursor.fetchall():
                    c = str(row_code or "").strip()
                    n = str(row_name or "").strip()
                    if c and n:
                        name_map[c] = n
            finally:
                conn.close()

        missing: list[str] = []
        resolved: list[tuple[int, str, str]] = []
        for idx, code in enumerate(members, start=1):
            c = str(code).strip()
            n = name_map.get(c) or name_map.get(base_code(c)) or ""
            n = str(n).strip()
            if not c or not n:
                missing.append(c or str(code))
                continue
            resolved.append((idx, c, n))
        if missing:
            raise ApiError(
                status_code=HTTPStatus.SERVICE_UNAVAILABLE,
                code="export_validation_failed",
                message="export requires non-empty stock_code and stock_name for every row",
                details={
                    "export": "pool_download_csv",
                    "pool_id": pool_id,
                    "target_date": date_key,
                    "missing_names": missing[:50],
                    "missing_count": len(missing),
                },
            )
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["rank", "stock_code", "stock_name"])
        for rank, code, name in resolved:
            writer.writerow([rank, code, name])
        csv_body = output.getvalue().encode("utf-8-sig")
        filename = f"pool_{pool_id}_{date_key}.csv"
        return ApiBinaryResponse(
            body=csv_body,
            content_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    def pool_manual_snapshot_view(
        self,
        *,
        target_date: str,
        pool_id: str,
        display_name: Optional[str],
        members: list[str],
        requested_by: str,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        self.require_trading_day(target_date=target_date)
        normalized_pool_id = pool_id.strip()
        if not normalized_pool_id:
            raise ApiError(
                status_code=HTTPStatus.BAD_REQUEST,
                code="invalid_pool_id",
                message="pool_id must be a non-empty string",
            )

        normalized_members = sorted({code.strip() for code in members if code.strip()})
        if not normalized_members:
            raise ApiError(
                status_code=HTTPStatus.BAD_REQUEST,
                code="invalid_members",
                message="members must contain at least one non-empty stock code",
            )

        artifact_path = self._manual_pool_artifact_path(
            target_date=target_date, pool_id=normalized_pool_id
        )
        ledger_path = self._manual_pool_ledger_path(
            target_date=target_date, pool_id=normalized_pool_id
        )
        requested_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        artifact_payload = {
            "version": 1,
            "target_date": target_date,
            "pool_id": f"manual__{normalized_pool_id}",
            "display_name": display_name.strip()
            if isinstance(display_name, str) and display_name.strip()
            else f"手工监控池：{normalized_pool_id}",
            "pool_type": "manual_snapshot",
            "requested_by": requested_by,
            "requested_at": requested_at,
            "member_count": len(normalized_members),
            "members": normalized_members,
        }
        ledger_payload = {
            "version": 1,
            "target_date": target_date,
            "pool_id": f"manual__{normalized_pool_id}",
            "status": "ok",
            "requested_by": requested_by,
            "requested_at": requested_at,
            "member_count": len(normalized_members),
            "artifact_path": self._safe_ref_path(str(artifact_path)),
        }
        if not dry_run:
            artifact_path.parent.mkdir(parents=True, exist_ok=True)
            ledger_path.parent.mkdir(parents=True, exist_ok=True)
            artifact_path.write_text(
                json.dumps(
                    artifact_payload, indent=2, ensure_ascii=False, sort_keys=True
                )
                + "\n",
                encoding="utf-8",
            )
            ledger_path.write_text(
                json.dumps(ledger_payload, indent=2, ensure_ascii=False, sort_keys=True)
                + "\n",
                encoding="utf-8",
            )
        return {
            "_meta": {"status": "ok"},
            "pool_run": ledger_payload,
        }

    def _manual_pool_artifact_path(self, *, target_date: str, pool_id: str) -> Path:
        return (
            self.project_root
            / "var/artifacts/pools"
            / target_date
            / f"pool_manual__{pool_id}_members.json"
        )

    def _manual_pool_ledger_path(self, *, target_date: str, pool_id: str) -> Path:
        return (
            self.project_root
            / "var/ledgers/pools"
            / target_date
            / f"pool_manual__{pool_id}_ledger.json"
        )

    def _list_manual_pool_definitions(self, *, target_date: str) -> list[dict[str, Any]]:
        root = self.project_root / "var/artifacts/pools" / target_date
        if not root.exists():
            return []
        pools: list[dict[str, Any]] = []
        for path in sorted(root.glob("pool_manual__*_members.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(payload, dict):
                continue
            pool_id = payload.get("pool_id")
            if not isinstance(pool_id, str) or not pool_id.strip():
                continue
            display_name = payload.get("display_name")
            pools.append(
                {
                    "pool_id": str(pool_id),
                    "display_name": str(display_name) if isinstance(display_name, str) else str(pool_id),
                    "pool_type": "manual_snapshot",
                    "source": {"type": "manual_snapshot", "artifact_path": self._safe_ref_path(str(path))},
                }
            )
        return pools

    def _build_pool_definitions(self, *, target_date: str) -> list[dict[str, Any]]:
        registry = load_screener_registry(self._screeners_registry_config)
        enabled = [s for s in registry.screeners if s.enabled]
        pools: list[dict[str, Any]] = [
            {
                "pool_id": "union__enabled_screeners",
                "display_name": "全量命中池（启用筛选器）",
                "pool_type": "derived_union",
                "source": {
                    "type": "screeners_union",
                    "screener_ids": [s.screener_id for s in enabled],
                },
            }
        ]
        for screener in enabled:
            pools.append(
                {
                    "pool_id": f"screener__{screener.screener_id}",
                    "display_name": f"筛选器命中池：{screener.display_name}",
                    "pool_type": "derived_screener_picks",
                    "source": {
                        "type": "screener_run",
                        "screener_id": screener.screener_id,
                    },
                }
            )
        pools.extend(self._list_manual_pool_definitions(target_date=target_date))
        return pools

    def _resolve_pool_members(self, *, pool_id: str, target_date: str) -> list[str]:
        if pool_id == "union__enabled_screeners":
            registry = load_screener_registry(self._screeners_registry_config)
            enabled_ids = [s.screener_id for s in registry.screeners if s.enabled]
            members: set[str] = set()
            for screener_id in enabled_ids:
                members.update(
                    self._resolve_pool_members(
                        pool_id=f"screener__{screener_id}", target_date=target_date
                    )
                )
            return sorted(members)

        if pool_id.startswith("screener__"):
            screener_id = pool_id.removeprefix("screener__")
            artifact = read_screener_run_artifact(
                project_root=self.project_root,
                target_date=target_date,
                screener_id=screener_id,
            )
            if artifact is None:
                return []
            picks = artifact.get("picks")
            if not isinstance(picks, list):
                return []

            def normalize(value: object) -> Optional[str]:
                if value is None:
                    return None
                if isinstance(value, str):
                    v = value.strip()
                    return v if v else None
                if isinstance(value, dict):
                    code = value.get("code")
                    if isinstance(code, str) and code.strip():
                        return code.strip()
                return None

            normalized = [normalize(item) for item in picks]
            return sorted({code for code in normalized if code is not None})

        if pool_id.startswith("manual__"):
            manual_id = pool_id.removeprefix("manual__").strip()
            if not manual_id:
                return []
            artifact_path = self._manual_pool_artifact_path(
                target_date=target_date, pool_id=manual_id
            )
            if not artifact_path.exists():
                return []
            try:
                payload = json.loads(artifact_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return []
            if not isinstance(payload, dict):
                return []
            members = payload.get("members")
            if not isinstance(members, list):
                return []
            normalized_members = [
                str(item).strip() for item in members if str(item).strip()
            ]
            return sorted(set(normalized_members))

        return []

    def _previous_trading_day(self, target_date: str) -> Optional[str]:
        if not self._trading_calendar_ledger_file.exists():
            return None
        payload = json.loads(self._trading_calendar_ledger_file.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return None
        trading_days = payload.get("trading_days")
        if not isinstance(trading_days, list) or not all(isinstance(item, str) for item in trading_days):
            return None
        days = [str(item) for item in trading_days]
        if target_date not in days:
            return None
        index = days.index(target_date)
        if index <= 0:
            return None
        return days[index - 1]

    def screener_bulk_runs_view(
        self,
        *,
        target_date: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> dict[str, Any]:
        ledgers = list_bulk_runs(
            project_root=self.project_root, target_date=target_date
        )
        total_count = len(ledgers)
        if limit is not None:
            ledgers = ledgers[:limit]
        return {
            "_meta": {
                "runs_source": "var/ledgers/screener_runs",
                "date_filter": target_date,
                "limit": limit,
                "total_count": total_count,
                "returned_count": len(ledgers),
            },
            "bulk_runs": ledgers,
        }

    def screener_bulk_run_detail_view(self, *, target_date: str) -> dict[str, Any]:
        ledger = read_bulk_run_ledger(
            project_root=self.project_root, target_date=target_date
        )
        if ledger is None:
            raise ApiError(
                status_code=HTTPStatus.NOT_FOUND,
                code="bulk_run_not_found",
                message="bulk run ledger not found",
                details={"target_date": target_date},
            )
        artifact = read_bulk_run_artifact(
            project_root=self.project_root, target_date=target_date
        )
        if artifact is None:
            raise ApiError(
                status_code=HTTPStatus.NOT_FOUND,
                code="bulk_run_artifact_not_found",
                message="bulk run artifact not found",
                details={"target_date": target_date},
            )
        return {
            "_meta": {"status": "ok"},
            "bulk_run": ledger,
            "bulk_result": artifact,
        }

    def screener_bulk_run_artifact_download_view(
        self, *, target_date: str
    ) -> ApiBinaryResponse:
        ledger = read_bulk_run_ledger(
            project_root=self.project_root, target_date=target_date
        )
        if ledger is None:
            raise ApiError(
                status_code=HTTPStatus.NOT_FOUND,
                code="bulk_run_not_found",
                message="bulk run ledger not found",
                details={"target_date": target_date},
            )
        expected_root = self.project_root / "var/artifacts/screener_runs" / target_date
        artifact_path = expected_root / "bulk_run_result.json"
        if not artifact_path.exists():
            raise ApiError(
                status_code=HTTPStatus.NOT_FOUND,
                code="bulk_run_artifact_not_found",
                message="bulk run artifact not found",
                details={"target_date": target_date},
            )
        filename = artifact_path.name
        return ApiBinaryResponse(
            body=artifact_path.read_bytes(),
            content_type="application/json; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    def screener_config_view(self, *, screener_id: str) -> dict[str, Any]:
        config_payload = read_screener_config(
            config_dir=self._screeners_config_dir, screener_id=screener_id
        )
        if config_payload is None:
            raise ApiError(
                status_code=HTTPStatus.NOT_FOUND,
                code="screener_config_not_found",
                message="screener config not found",
                details={"screener_id": screener_id},
            )
        return {
            "_meta": {"status": "ok"},
            "screener_config": config_payload,
        }

    def screener_config_update_view(
        self,
        *,
        screener_id: str,
        current_parameters: dict[str, Any],
        requested_by: str,
    ) -> dict[str, Any]:
        registry = load_screener_registry(self._screeners_registry_config)
        enabled_ids = {
            screener.screener_id for screener in registry.screeners if screener.enabled
        }
        if screener_id not in enabled_ids:
            raise ApiError(
                status_code=HTTPStatus.BAD_REQUEST,
                code="invalid_screener_id",
                message=f"unknown or disabled screener_id: {screener_id}",
                details={"screener_id": screener_id, "enabled": sorted(enabled_ids)},
            )

        config_payload = write_screener_config(
            config_dir=self._screeners_config_dir,
            screener_id=screener_id,
            current_parameters=current_parameters,
            requested_by=requested_by,
        )
        return {
            "_meta": {"status": "ok"},
            "screener_config": config_payload,
        }

    def _calendar_db_path(self) -> Path:
        return (
            Path(
                os.environ.get("NEOTRADE3_STOCK_DB_PATH")
                or str(self._stock_db_default_path)
            )
            .expanduser()
        )

    @staticmethod
    def _calendar_meta(conn: sqlite3.Connection) -> dict[str, str]:
        try:
            rows = conn.execute("SELECT key, value FROM trading_calendar_meta").fetchall()
        except Exception:
            return {}
        out: dict[str, str] = {}
        for row in rows:
            if not row or len(row) < 2:
                continue
            k = str(row[0] or "").strip()
            if not k:
                continue
            out[k] = str(row[1] or "").strip()
        return out

    @staticmethod
    def _parse_iso_date_or_none(value: object) -> Optional[date]:
        raw = str(value or "").strip()
        if not raw:
            return None
        try:
            return date.fromisoformat(raw)
        except ValueError:
            return None

    @staticmethod
    def _format_iso(d: date) -> str:
        return d.isoformat()

    @staticmethod
    def _calendar_cache_stats(conn: sqlite3.Connection) -> tuple[int, Optional[str], Optional[str]]:
        try:
            row = conn.execute(
                "SELECT COUNT(1), MIN(trade_date), MAX(trade_date) FROM trading_calendar_cache"
            ).fetchone()
        except Exception:
            return 0, None, None
        if not row:
            return 0, None, None
        count = int(row[0] or 0)
        min_day = str(row[1]) if row[1] else None
        max_day = str(row[2]) if row[2] else None
        return count, min_day, max_day

    def _ensure_trading_calendar_coverage(
        self,
        *,
        conn: sqlite3.Connection,
        target_date: str,
        horizon_days: int = 180,
    ) -> dict[str, Any]:
        today = date.today()
        meta = self._calendar_meta(conn)
        covered_until = self._parse_iso_date_or_none(meta.get("calendar_covered_until"))
        if covered_until is None:
            covered_until = self._parse_iso_date_or_none(meta.get("last_updated"))
        target_dt = date.fromisoformat(target_date)
        desired_until = max(target_dt, today) + timedelta(days=int(horizon_days))
        if covered_until is not None and covered_until >= desired_until:
            return {"status": "skipped", "covered_until": self._format_iso(covered_until)}

        from neotrade3.data_sources.tushare_concept_adapter import TushareConceptAdapter

        adapter = TushareConceptAdapter()
        if not adapter.configured:
            return {
                "status": "skipped",
                "reason": "tushare_token_not_configured",
                "covered_until": self._format_iso(covered_until) if covered_until else None,
            }

        start_dt = covered_until + timedelta(days=1) if covered_until else (today - timedelta(days=30))
        end_dt = desired_until
        try:
            days = adapter.fetch_trade_calendar(
                start_date=self._format_iso(start_dt),
                end_date=self._format_iso(end_dt),
                exchange="SSE",
            )
        except Exception as exc:
            return {"status": "failed", "reason": str(exc), "covered_until": self._format_iso(covered_until) if covered_until else None}

        open_days = [item.cal_date for item in days if item.is_open]
        if open_days:
            updated_at = datetime.now().isoformat(timespec="seconds")
            conn.execute("BEGIN")
            try:
                conn.executemany(
                    "INSERT OR IGNORE INTO trading_calendar_cache(trade_date, updated_at) VALUES (?, ?)",
                    [(d, updated_at) for d in open_days],
                )
                conn.executemany(
                    "INSERT OR REPLACE INTO trading_calendar(trade_date, source, updated_at) VALUES (?, ?, ?)",
                    [(d, "tushare.trade_cal", updated_at) for d in open_days],
                )
                conn.execute(
                    "INSERT OR REPLACE INTO trading_calendar_meta(key, value) VALUES (?, ?)",
                    ("calendar_source", "tushare.trade_cal"),
                )
                conn.execute(
                    "INSERT OR REPLACE INTO trading_calendar_meta(key, value) VALUES (?, ?)",
                    ("calendar_covered_from", self._format_iso(start_dt)),
                )
                conn.execute(
                    "INSERT OR REPLACE INTO trading_calendar_meta(key, value) VALUES (?, ?)",
                    ("calendar_covered_until", self._format_iso(end_dt)),
                )
                conn.execute(
                    "INSERT OR REPLACE INTO trading_calendar_meta(key, value) VALUES (?, ?)",
                    ("last_updated", self._format_iso(today)),
                )
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                return {"status": "failed", "reason": "db_write_failed"}
        return {
            "status": "ok",
            "covered_from": self._format_iso(start_dt),
            "covered_until": self._format_iso(end_dt),
            "inserted_open_days": len(open_days),
            "api_name": adapter.last_api_name,
            "api_code": adapter.last_code,
        }

    def _trading_day_from_calendar_cache(self, *, target_date: str) -> Optional[dict[str, Any]]:
        db_path = self._calendar_db_path()
        if not db_path.exists() or not db_path.is_file():
            return None
        try:
            conn = sqlite3.connect(str(db_path))
        except Exception:
            return None
        try:
            count, min_day, max_day = self._calendar_cache_stats(conn)
            if count <= 0:
                return None

            meta = self._calendar_meta(conn)
            covered_until = meta.get("calendar_covered_until") or meta.get("last_updated") or None
            covered_until_dt = self._parse_iso_date_or_none(covered_until)
            target_dt = date.fromisoformat(target_date)
            refresh = None
            if covered_until_dt is None or target_dt > covered_until_dt:
                refresh = self._ensure_trading_calendar_coverage(
                    conn=conn, target_date=target_date
                )
                meta = self._calendar_meta(conn)
                covered_until = meta.get("calendar_covered_until") or meta.get("last_updated") or None
                covered_until_dt = self._parse_iso_date_or_none(covered_until)

            row = conn.execute(
                "SELECT 1 FROM trading_calendar_cache WHERE trade_date = ? LIMIT 1",
                (target_date,),
            ).fetchone()
            if covered_until_dt is None or target_dt > covered_until_dt:
                is_trading: Optional[bool] = None
            else:
                is_trading = bool(row)

            nearest = None
            if is_trading is True:
                nearest = target_date
            else:
                r = conn.execute(
                    "SELECT MAX(trade_date) FROM trading_calendar_cache WHERE trade_date <= ?",
                    (target_date,),
                ).fetchone()
                nearest = str(r[0]) if r and r[0] else None

            source = meta.get("calendar_source") or "trading_calendar_cache"
            return {
                "_meta": {
                    "status": "ok",
                    "calendar_source": source,
                    "calendar_db": _safe_ref_path(str(db_path)),
                    "calendar_refresh": refresh,
                },
                "target_date": target_date,
                "is_trading_day": is_trading,
                "nearest_trading_day": nearest,
                "max_trading_day": max_day,
                "min_trading_day": min_day,
                "calendar_covered_until": self._format_iso(covered_until_dt) if covered_until_dt else None,
            }
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def trading_day_view(self, *, target_date: str) -> dict[str, Any]:
        cached = self._trading_day_from_calendar_cache(target_date=target_date)
        if cached is not None:
            return cached

        trading_days = self._load_trading_calendar_days()
        sorted_days = sorted(trading_days)
        is_trading = target_date in trading_days

        nearest = None
        if not is_trading:
            for d in reversed(sorted_days):
                if d <= target_date:
                    nearest = d
                    break
        else:
            nearest = target_date

        return {
            "_meta": {
                "status": "ok",
                "calendar_source": str(self._trading_calendar_ledger_file),
            },
            "target_date": target_date,
            "is_trading_day": is_trading,
            "nearest_trading_day": nearest,
            "max_trading_day": sorted_days[-1] if sorted_days else None,
            "min_trading_day": sorted_days[0] if sorted_days else None,
            "calendar_covered_until": sorted_days[-1] if sorted_days else None,
        }

    def rebuild_trading_calendar_view(
        self,
        *,
        sqlite_db_path: str,
        table: str,
        date_column: str,
        requested_by: str,
    ) -> dict[str, Any]:
        db_path = Path(sqlite_db_path).expanduser()
        if not db_path.exists() or not db_path.is_file():
            raise ApiError(
                status_code=HTTPStatus.BAD_REQUEST,
                code="invalid_db_path",
                message="sqlite_db_path must exist and be a file",
                details={"sqlite_db_path": "redacted"},
            )

        trading_days = self._extract_trading_days_from_sqlite(
            db_path=db_path, table=table, date_column=date_column
        )
        ledger_payload = {
            "version": 1,
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "generated_by": requested_by,
            "source": {
                "type": "sqlite",
                "table": table,
                "date_column": date_column,
            },
            "trading_days": trading_days,
            "trading_day_count": len(trading_days),
        }
        self._trading_calendar_ledger_file.parent.mkdir(parents=True, exist_ok=True)
        self._trading_calendar_ledger_file.write_text(
            json.dumps(ledger_payload, indent=2, ensure_ascii=False, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        return {
            "_meta": {"status": "ok"},
            "trading_calendar": ledger_payload,
        }

    def trading_calendar_meta_view(self) -> dict[str, Any]:
        db_path = self._calendar_db_path()
        if db_path.exists() and db_path.is_file():
            try:
                conn = sqlite3.connect(str(db_path))
            except Exception:
                conn = None
            if conn is not None:
                try:
                    count, min_day, max_day = self._calendar_cache_stats(conn)
                    if count > 0:
                        meta = self._calendar_meta(conn)
                        covered_until = meta.get("calendar_covered_until") or meta.get("last_updated") or None
                        return {
                            "_meta": {"status": "ok"},
                            "trading_day_count": count,
                            "min_trading_day": min_day,
                            "max_trading_day": max_day,
                            "calendar_source": meta.get("calendar_source") or "trading_calendar_cache",
                            "calendar_covered_until": covered_until,
                            "calendar_db": _safe_ref_path(str(db_path)),
                            "last_updated": meta.get("last_updated") or None,
                        }
                finally:
                    try:
                        conn.close()
                    except Exception:
                        pass

        trading_days = sorted(self._load_trading_calendar_days())
        min_day = trading_days[0] if trading_days else None
        max_day = trading_days[-1] if trading_days else None
        return {
            "_meta": {"status": "ok"},
            "trading_day_count": len(trading_days),
            "min_trading_day": min_day,
            "max_trading_day": max_day,
            "calendar_source": str(self._trading_calendar_ledger_file),
            "calendar_covered_until": max_day,
        }

    def require_trading_day(self, *, target_date: str) -> None:
        result = self.trading_day_view(target_date=target_date)
        is_trading = result.get("is_trading_day")
        if is_trading is True:
            return
        if is_trading is False:
            raise ApiError(
                status_code=HTTPStatus.BAD_REQUEST,
                code="not_trading_day",
                message="target date is not a trading day",
                details={"target_date": target_date},
            )
        raise ApiError(
            status_code=HTTPStatus.SERVICE_UNAVAILABLE,
            code="trading_calendar_out_of_range",
            message="trading calendar does not cover target date yet",
            details={
                "target_date": target_date,
                "calendar_covered_until": result.get("calendar_covered_until"),
            },
        )

    def _load_trading_calendar_days(self) -> set[str]:
        if not self._trading_calendar_ledger_file.exists():
            raise ApiError(
                status_code=HTTPStatus.SERVICE_UNAVAILABLE,
                code="trading_calendar_not_ready",
                message="trading calendar is not available yet; build it first",
                details={},
            )
        payload = json.loads(
            self._trading_calendar_ledger_file.read_text(encoding="utf-8")
        )
        if not isinstance(payload, dict):
            raise ApiError(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                code="trading_calendar_invalid",
                message="trading calendar ledger is not a JSON object",
                details={},
            )
        trading_days = payload.get("trading_days")
        if not isinstance(trading_days, list) or not all(
            isinstance(item, str) for item in trading_days
        ):
            raise ApiError(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                code="trading_calendar_invalid",
                message="trading calendar ledger must contain trading_days as a list of strings",
                details={},
            )
        return set(trading_days)

    @staticmethod
    def _extract_trading_days_from_sqlite(
        *, db_path: Path, table: str, date_column: str
    ) -> list[str]:
        allowed_sources = {("daily_prices", "trade_date")}
        if (table, date_column) not in allowed_sources:
            raise ApiError(
                status_code=HTTPStatus.BAD_REQUEST,
                code="invalid_trading_calendar_source",
                message="unsupported sqlite source for trading calendar extraction",
                details={
                    "supported": [
                        {"table": table_name, "date_column": column}
                        for table_name, column in sorted(allowed_sources)
                    ],
                    "table": table,
                    "date_column": date_column,
                },
            )
        try:
            conn = sqlite3.connect(str(db_path))
        except Exception as exc:
            raise ApiError(
                status_code=HTTPStatus.BAD_REQUEST,
                code="invalid_db",
                message=f"failed to open sqlite db (see server logs)",
                details={"db_path": _safe_ref_path(str(db_path))},
            )

        try:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT trade_date FROM daily_prices")
            rows = cursor.fetchall()
        except Exception as exc:
            raise ApiError(
                status_code=HTTPStatus.BAD_REQUEST,
                code="invalid_db_query",
                message=f"failed to query sqlite db (see server logs)",
                details={
                    "db_path": _safe_ref_path(str(db_path)),
                    "table": table,
                    "date_column": date_column,
                },
            )
        finally:
            conn.close()

        days: list[str] = []
        for (raw_value,) in rows:
            if raw_value is None:
                continue
            value = str(raw_value)
            try:
                date.fromisoformat(value)
            except ValueError:
                continue
            days.append(value)

        days = sorted(set(days))
        if not days:
            raise ApiError(
                status_code=HTTPStatus.BAD_REQUEST,
                code="no_trading_days_found",
                message="no ISO YYYY-MM-DD dates found from sqlite source",
                details={
                    "db_path": _safe_ref_path(str(db_path)),
                    "table": table,
                    "date_column": date_column,
                },
            )
        return days

    def migration_feature_manual_view(self) -> dict[str, Any]:
        feature_manual_payload = build_feature_inventory_payload(
            self._feature_inventory_file
        )
        return {
            "_meta": {"source": "neotrade2_codebase_inventory_v3"},
            "feature_manual": feature_manual_payload,
        }

    def migration_feature_mapping_view(
        self,
        domain: str,
        *,
        filter_status: Optional[str] = None,
        filter_strategy: Optional[str] = None,
    ) -> dict[str, Any]:
        mapping_files = {
            "strategy_and_lab": self._strategy_and_lab_mapping_file,
            "assistant": self._assistant_mapping_file,
            "operations": self._operations_mapping_file,
            "screeners": self._screeners_mapping_file,
        }
        mapping_file = mapping_files.get(domain)
        if mapping_file is None:
            raise ApiError(
                status_code=HTTPStatus.BAD_REQUEST,
                code="invalid_mapping_domain",
                message=f"unsupported mapping domain: {domain}",
                details={"supported": sorted(mapping_files.keys()), "domain": domain},
            )
        mapping_payload = build_feature_mapping_payload(
            mapping_file_path=mapping_file,
            inventory_file_path=self._feature_inventory_file,
            expected_scope_domain=domain,
            filter_status=filter_status,
            filter_strategy=filter_strategy,
        )
        return {
            "_meta": {"source": f"neotrade3_feature_mapping_{domain}_v1"},
            "feature_mapping": mapping_payload,
        }

    def migration_feature_mapping_coverage_view(self, domain: str) -> dict[str, Any]:
        mapping_files = {
            "strategy_and_lab": self._strategy_and_lab_mapping_file,
            "assistant": self._assistant_mapping_file,
            "operations": self._operations_mapping_file,
            "screeners": self._screeners_mapping_file,
        }
        mapping_file = mapping_files.get(domain)
        if mapping_file is None:
            raise ApiError(
                status_code=HTTPStatus.BAD_REQUEST,
                code="invalid_mapping_domain",
                message=f"unsupported mapping domain: {domain}",
                details={"supported": sorted(mapping_files.keys()), "domain": domain},
            )

        coverage_payload = build_feature_mapping_coverage_payload(
            mapping_file_path=mapping_file,
            inventory_file_path=self._feature_inventory_file,
            expected_scope_domain=domain,
        )
        return {
            "_meta": {"source": f"neotrade3_feature_mapping_coverage_{domain}_v1"},
            "feature_mapping_coverage": coverage_payload,
        }

    def issue_center_view(
        self,
        target_date: date,
        publish_succeeded: bool = False,
    ) -> dict[str, Any]:
        snapshot = self.build_snapshot(
            target_date=target_date,
            publish_succeeded=publish_succeeded,
            write_outputs=False,
        )
        return {
            "target_date": snapshot["target_date"],
            "_meta": snapshot.get("_meta", {}),
            "issue_center": snapshot["issue_center"],
        }

    def learning_view(
        self,
        target_date: date,
        publish_succeeded: bool = False,
    ) -> dict[str, Any]:
        snapshot = self.build_snapshot(
            target_date=target_date,
            publish_succeeded=publish_succeeded,
            write_outputs=False,
        )
        return {
            "target_date": snapshot["target_date"],
            "_meta": snapshot.get("_meta", {}),
            "learning": snapshot["learning"],
        }

    def market_phase_view(
        self,
        target_date: date,
        lookback_days: int = 60,
    ) -> dict[str, Any]:
        """Detect current market phase using aggregate market statistics."""
        cache_key = ("market_phase", target_date.isoformat(), str(lookback_days))
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        db_path = self._stock_db_default_path
        if not db_path.exists():
            raise ApiError(
                status_code=HTTPStatus.NOT_FOUND,
                code="database_not_found",
                message="stock database not found",
                details={"db_path": _safe_ref_path(str(db_path))},
            )
        try:
            result = detect_market_phase(
                db_path=str(db_path),
                target_date=target_date.isoformat(),
                lookback_days=lookback_days,
            )
            response = {
                "target_date": target_date.isoformat(),
                "_meta": {"status": "ok"},
                "market_phase": {
                    "phase": result.phase.value,
                    "confidence": result.confidence,
                    "market_return_20d": result.market_return_20d,
                    "market_return_60d": result.market_return_60d,
                    "market_breadth": result.market_breadth,
                    "ma20_slope": result.ma20_slope,
                    "ma60_slope": result.ma60_slope,
                    "total_amount": result.total_amount,
                    "amount_trend": result.amount_trend,
                },
            }
            self._cache_set(cache_key, response, 300.0)  # 5 min cache
            return response
        except Exception as e:
            raise ApiError(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                code="market_phase_error",
                message=f"failed to detect market phase (see server logs)",
            )

    def resonance_score_view(
        self,
        target_date: date,
        codes: list[str],
    ) -> dict[str, Any]:
        """Calculate three-dimensional resonance scores for given stocks."""
        if not codes:
            raise ApiError(
                status_code=HTTPStatus.BAD_REQUEST,
                code="invalid_codes",
                message="codes must be a non-empty list",
            )

        db_path = self._stock_db_default_path
        if not db_path.exists():
            raise ApiError(
                status_code=HTTPStatus.NOT_FOUND,
                code="database_not_found",
                message="stock database not found",
                details={"db_path": _safe_ref_path(str(db_path))},
            )

        try:
            # Detect market phase first for dynamic weights
            phase_result = detect_market_phase(
                db_path=str(db_path),
                target_date=target_date.isoformat(),
            )

            from neotrade3.analysis.resonance_scorer import ResonanceScorer, MarketPhase as MP
            phase_map = {
                "bull": MP.BULL, "bear": MP.BEAR,
                "range": MP.RANGE, "transition": MP.TRANSITION,
            }
            mp = phase_map.get(phase_result.phase.value, MP.TRANSITION)
            scorer = ResonanceScorer(market_phase=mp)

            # Fetch per-stock data from DB and compute scores
            import sqlite3 as _sqlite3
            conn = _sqlite3.connect(str(db_path))
            conn.row_factory = _sqlite3.Row
            td = target_date.isoformat()

            scores_out = []
            for code in codes:
                row = conn.execute(
                    "SELECT close, volume, amount, pct_change FROM daily_prices WHERE code=? AND trade_date=?",
                    (code, td),
                ).fetchone()
                if row is None:
                    # try nearest earlier date
                    row = conn.execute(
                        "SELECT close, volume, amount, pct_change FROM daily_prices WHERE code=? AND trade_date<=? ORDER BY trade_date DESC LIMIT 1",
                        (code, td),
                    ).fetchone()
                if row is None:
                    continue

                close = row["close"] or 0
                pct_chg = (row["pct_change"] or 0) / 100.0
                vol = row["volume"] or 0

                # Compute RPS-120 proxy from return rank
                ret_row = conn.execute(
                    "SELECT pct_change FROM daily_prices WHERE trade_date=? ORDER BY pct_change DESC",
                    (td,),
                ).fetchall()
                total = len(ret_row)
                rank = next((i for i, r in enumerate(ret_row) if r["pct_change"] == row["pct_change"]), total // 2)
                rps_120 = (1 - rank / max(total, 1)) * 100 if total > 0 else 50

                # Technical score
                tech = scorer.calculate_technical_score(
                    rps_120=rps_120, rps_250=rps_120 * 0.95,
                    price_trend=min(max(pct_chg + 0.5, 0), 1),
                    volume_trend=min(max(vol / 1e8, 0), 1) / 10,
                )
                # Capital score (proxy)
                cap = scorer.calculate_capital_score(
                    fund_flow_score=min(max(pct_chg + 0.5, 0), 1),
                    northbound_flow=0.5, institutional_score=0.5,
                )
                # Policy score (proxy)
                pol = scorer.calculate_policy_score(
                    sector_policy_score=0.5, policy_news=[],
                )
                total_score = (
                    tech * scorer.weights.technical_weight
                    + cap * scorer.weights.capital_weight
                    + pol * scorer.weights.policy_weight
                )

                # Grade
                if total_score >= 70:
                    grade = "A"
                elif total_score >= 50:
                    grade = "B"
                else:
                    grade = "C"

                scores_out.append({
                    "code": code,
                    "name": code,
                    "total_score": round(total_score, 2),
                    "grade": grade,
                    "technical_score": round(tech, 2),
                    "capital_score": round(cap, 2),
                    "policy_score": round(pol, 2),
                    "weights": {
                        "technical": scorer.weights.technical_weight,
                        "capital": scorer.weights.capital_weight,
                        "policy": scorer.weights.policy_weight,
                    },
                })
            conn.close()

            return {
                "target_date": target_date.isoformat(),
                "_meta": {
                    "status": "ok",
                    "market_phase": phase_result.phase.value,
                },
                "scores": scores_out,
            }
        except Exception as e:
            raise ApiError(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                code="resonance_score_error",
                message=f"failed to calculate resonance scores (see server logs)",
            )

    def sector_rotation_view(
        self,
        target_date: date,
        lookback_days: int = 20,
    ) -> dict[str, Any]:
        """Analyze sector rotation and RPS."""
        db_path = self._stock_db_default_path
        if not db_path.exists():
            raise ApiError(
                status_code=HTTPStatus.NOT_FOUND,
                code="database_not_found",
                message="stock database not found",
                details={"db_path": _safe_ref_path(str(db_path))},
            )

        try:
            analyzer = SectorRotationAnalyzer(db_path=str(db_path))
            result = analyzer.analyze(
                target_date=target_date.isoformat(),
                lookback_days=lookback_days,
            )

            mainline_sector_names = [s.sector_name for s in result.mainline_sectors]

            return {
                "target_date": target_date.isoformat(),
                "_meta": {"status": "ok"},
                "sector_rotation": {
                    "top_sectors": [
                        {
                            "sector": s.sector_name,
                            "rps_20": round(s.rps_20, 2),
                            "rps_60": round(s.rps_60, 2),
                            "rps_120": round(s.rps_120, 2),
                            "return_20d": round(s.return_20d, 4),
                            "return_60d": round(s.return_60d, 4),
                            "is_policy_mainline": s.is_mainline,
                            "mainline_category": s.mainline_category,
                        }
                        for s in result.top_sectors
                    ],
                    "weakening_sectors": [s.sector_name for s in result.weakening_sectors],
                    "mainline_sectors": mainline_sector_names,
                    "emerging_sectors": [s.sector_name for s in result.emerging_sectors],
                    "rotation_signal": result.rotation_signal,
                    "market_context": result.market_context,
                },
            }
        except Exception as e:
            raise ApiError(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                code="sector_rotation_error",
                message=f"failed to analyze sector rotation (see server logs)",
            )

    def stock_tiering_view(
        self,
        target_date: date,
        codes: Optional[list[str]] = None,
        lookback_days: int = 20,
    ) -> dict[str, Any]:
        """Analyze stock tiering (leader/core/follower) within sectors."""
        db_path = self._stock_db_default_path
        if not db_path.exists():
            raise ApiError(
                status_code=HTTPStatus.NOT_FOUND,
                code="database_not_found",
                message="stock database not found",
                details={"db_path": _safe_ref_path(str(db_path))},
            )

        try:
            analyzer = StockTieringAnalyzer(db_path=str(db_path))
            result = analyzer.analyze(
                codes=codes,
                target_date=target_date,
                lookback_days=lookback_days,
            )

            return {
                "target_date": target_date.isoformat(),
                "_meta": {"status": "ok", "lookback_days": lookback_days},
                "stock_tiering": {
                    "total_stocks": len(result.all_tiered_stocks),
                    "leader_count": len(result.get_by_tier(StockTier.LEADER)),
                    "core_count": len(result.get_by_tier(StockTier.CORE)),
                    "follower_count": len(result.get_by_tier(StockTier.FOLLOWER)),
                    "sectors": [
                        {
                            "sector": s.sector,
                            "total": s.total_stocks,
                            "leaders": [
                                {
                                    "code": t.code,
                                    "name": t.name,
                                    "confidence": t.tier_confidence,
                                    "leadership_score": t.metrics.leadership_score,
                                    "return_20d": t.metrics.return_20d,
                                }
                                for t in s.leaders
                            ],
                            "cores": [
                                {
                                    "code": t.code,
                                    "name": t.name,
                                    "confidence": t.tier_confidence,
                                    "leadership_score": t.metrics.leadership_score,
                                }
                                for t in s.cores
                            ],
                            "followers": [
                                {
                                    "code": t.code,
                                    "name": t.name,
                                    "confidence": t.tier_confidence,
                                }
                                for t in s.followers
                            ],
                        }
                        for s in result.sectors
                    ],
                },
            }
        except Exception as e:
            raise ApiError(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                code="stock_tiering_error",
                message=f"failed to analyze stock tiering (see server logs)",
            )

    def signals_view(
        self,
        target_date: date,
        codes: Optional[list[str]] = None,
        min_grade: str = "C",
    ) -> dict[str, Any]:
        """Generate comprehensive trading signals by multi-dimension resonance."""
        db_path = self._stock_db_default_path
        if not db_path.exists():
            raise ApiError(
                status_code=HTTPStatus.NOT_FOUND,
                code="database_not_found",
                message="stock database not found",
                details={"db_path": _safe_ref_path(str(db_path))},
            )

        try:
            grade_map = {"A": SignalGrade.A, "B": SignalGrade.B, "C": SignalGrade.C}
            grade = grade_map.get(min_grade.upper(), SignalGrade.C)

            generator = SignalGenerator(db_path=str(db_path))
            result = generator.generate(
                codes=codes,
                target_date=target_date,
                min_grade=grade,
            )

            payload = result.to_dict()
            target_date_str = target_date.isoformat()

            regime_snapshot = {
                "target_date": target_date_str,
                "market_phase": payload.get("market_phase"),
                "source": "signal_generator",
            }
            payload["regime_snapshot"] = regime_snapshot

            signal_items = payload.get("signals")
            if isinstance(signal_items, list) and signal_items:
                import sqlite3

                codes_in_payload: list[str] = []
                for item in signal_items:
                    if isinstance(item, dict):
                        code = str(item.get("code") or "").strip()
                        if code:
                            codes_in_payload.append(code)

                if codes_in_payload:
                    conn = sqlite3.connect(str(db_path))
                    try:
                        conn.row_factory = sqlite3.Row
                        cur = conn.cursor()
                        cur.execute(
                            "SELECT trade_date FROM trading_calendar_cache WHERE trade_date > ? ORDER BY trade_date ASC LIMIT 1",
                            (target_date_str,),
                        )
                        row = cur.fetchone()
                        next_trading_day = str(row["trade_date"]) if row and row["trade_date"] else None

                        placeholders = ",".join("?" for _ in codes_in_payload)
                        cur.execute(
                            f"""
                            SELECT
                                code,
                                open,
                                high,
                                low,
                                close,
                                volume,
                                amount,
                                preclose,
                                pct_change
                            FROM daily_prices
                            WHERE trade_date = ?
                              AND code IN ({placeholders})
                            """,
                            (target_date_str, *codes_in_payload),
                        )
                        by_code: dict[str, sqlite3.Row] = {str(r["code"]): r for r in cur.fetchall()}

                        next_open_by_code: dict[str, float] = {}
                        if next_trading_day:
                            cur.execute(
                                f"""
                                SELECT code, open
                                FROM daily_prices
                                WHERE trade_date = ?
                                  AND code IN ({placeholders})
                                """,
                                (next_trading_day, *codes_in_payload),
                            )
                            for r in cur.fetchall():
                                code = str(r["code"])
                                open_px = r["open"]
                                if isinstance(open_px, (int, float)):
                                    next_open_by_code[code] = float(open_px)
                    finally:
                        conn.close()

                    for item in signal_items:
                        if not isinstance(item, dict):
                            continue
                        code = str(item.get("code") or "").strip()
                        row = by_code.get(code)
                        has_price_bar = row is not None
                        amount_yuan = float(row["amount"]) if (row is not None and isinstance(row["amount"], (int, float))) else None
                        volume_shares = float(row["volume"]) if (row is not None and isinstance(row["volume"], (int, float))) else None
                        liquidity_ok = bool(
                            amount_yuan is not None
                            and volume_shares is not None
                            and amount_yuan > 0.0
                            and volume_shares > 0.0
                        )
                        blocked_reason = None
                        if not has_price_bar:
                            blocked_reason = "missing_price_bar"
                        elif not liquidity_ok:
                            blocked_reason = "illiquid_or_suspended"

                        item["constraint"] = {
                            "trade_mode": {
                                "settlement": "T+1_stock",
                                "execution_convention": "signal_day->next_trading_day_open",
                            },
                            "tradability": {
                                "trade_date": target_date_str,
                                "has_price_bar": has_price_bar,
                                "amount_yuan": amount_yuan,
                                "volume_shares": volume_shares,
                                "liquidity_ok": liquidity_ok,
                                "blocked_reason": blocked_reason,
                                "next_trading_day": next_trading_day,
                                "next_day_open": next_open_by_code.get(code),
                                "next_day_open_available": code in next_open_by_code,
                            },
                        }

                        item["regime_snapshot"] = regime_snapshot

            return payload
        except Exception as e:
            raise ApiError(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                code="signals_error",
                message=f"failed to generate signals (see server logs)",
            )

    def backtest_view(
        self,
        start_date: date,
        end_date: date,
        min_grade: str = "C",
        codes: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """Run backtest for signals over a date range."""
        db_path = self._stock_db_default_path
        if not db_path.exists():
            raise ApiError(
                status_code=HTTPStatus.NOT_FOUND,
                code="database_not_found",
                message="stock database not found",
                details={"db_path": _safe_ref_path(str(db_path))},
            )

        try:
            backtester = SignalBacktester(db_path=str(db_path))
            result = backtester.run(
                start_date=start_date,
                end_date=end_date,
                min_grade=min_grade,
                codes=codes,
            )
            return result.to_dict()
        except Exception as e:
            raise ApiError(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                code="backtest_error",
                message=f"failed to run backtest (see server logs)",
            )

    def evolution_view(
        self,
        start_date: date,
        end_date: date,
        market_phase: str = "bull",
    ) -> dict[str, Any]:
        """Generate self-evolution report."""
        db_path = self._stock_db_default_path
        if not db_path.exists():
            raise ApiError(
                status_code=HTTPStatus.NOT_FOUND,
                code="database_not_found",
                message="stock database not found",
                details={"db_path": _safe_ref_path(str(db_path))},
            )

        try:
            generator = EvolutionReportGenerator(db_path=str(db_path))
            report = generator.generate(
                start_date=start_date,
                end_date=end_date,
                market_phase=market_phase,
            )
            return report.to_dict()
        except Exception as e:
            raise ApiError(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                code="evolution_error",
                message=f"failed to generate evolution report (see server logs)",
            )

    def load_stored_snapshot(self, target_date: date) -> dict[str, Any]:
        stored_paths = self._stored_snapshot_paths(target_date)
        return {
            "target_date": target_date.isoformat(),
            "data_control": self._read_json(stored_paths["data_control"]),
            "orchestration": self._read_json(stored_paths["orchestration"]),
            "issue_center": self._read_json(stored_paths["issue_center"]),
            "learning": self._read_json(stored_paths["learning"]),
            "summary": self._read_json(stored_paths["summary"]),
        }

    def _stored_snapshot_paths(self, target_date: date) -> dict[str, Path]:
        date_key = target_date.isoformat()
        ledgers_root = Path(self.worker_app.paths["ledgers_root"])
        artifacts_root = Path(self.worker_app.paths["artifacts_root"])
        return {
            "data_control": ledgers_root / date_key / "data_control_plan_ledger.json",
            "orchestration": ledgers_root
            / date_key
            / "orchestration_run_snapshot.json",
            "issue_center": artifacts_root / date_key / "issue_center_snapshot.json",
            "learning": artifacts_root / date_key / "learning_snapshot.json",
            "summary": artifacts_root / date_key / "bootstrap_run_summary.json",
        }

    @staticmethod
    def _read_json(file_path: Path) -> dict[str, Any]:
        if not file_path.exists():
            raise ApiError(
                status_code=HTTPStatus.NOT_FOUND,
                code="snapshot_not_found",
                message=f"stored snapshot file not found: {file_path}",
                details={"file_path": str(file_path)},
            )
        return json.loads(file_path.read_text(encoding="utf-8"))

    def _cache_get(self, key: tuple[str, ...]) -> Optional[Any]:
        entry = self._cache.get(key)
        if entry is None:
            return None
        if entry.expires_at < time.time():
            self._cache.pop(key, None)
            return None
        return deepcopy(entry.payload)

    def _cache_set(
        self, key: tuple[str, ...], payload: Any, ttl_seconds: float
    ) -> None:
        self._cache[key] = ApiCacheEntry(
            payload=deepcopy(payload),
            expires_at=time.time() + ttl_seconds,
        )

    # ------------------------------------------------------------------
    # ML 预测服务
    # ------------------------------------------------------------------

    def prediction_signals_view(self, query: dict) -> dict:
        """
        返回当日 ML 模型预测信号

        GET /api/prediction/signals?date=YYYY-MM-DD&threshold=0.6&top_n=20
        """
        import sqlite3, json, numpy as np
        from pathlib import Path

        target_date_str = query.get("date", [None])[0]
        threshold = float(query.get("threshold", [0.6])[0])
        top_n = int(query.get("top_n", [20])[0])

        if not target_date_str:
            # 默认最新交易日
            conn = sqlite3.connect(str(self._stock_db_default_path))
            cur = conn.execute("SELECT MAX(trade_date) FROM daily_prices")
            target_date_str = cur.fetchone()[0]
            conn.close()

        model_path = self.project_root / "var/models/autore_v2_best.pkl"
        if not model_path.exists():
            return {
                "date": target_date_str,
                "signals": [],
                "model_loaded": False,
                "message": "模型文件不存在，请先训练模型",
            }

        # 延迟加载模型（首次调用时加载，后续复用）
        if not hasattr(self, '_ml_trainer'):
            from neotrade3.ml.autore.train import MLTrainer
            self._ml_trainer = MLTrainer(self._stock_db_default_path)
            self._ml_trainer.load_model(str(model_path))

        trainer = self._ml_trainer

        # 获取 Top 100 股票
        conn = sqlite3.connect(str(self._stock_db_default_path))
        cur = conn.execute(
            """
            SELECT s.code, s.name FROM stocks s
            JOIN daily_prices dp ON s.code = dp.code
            WHERE dp.trade_date = ? AND (s.is_delisted IS NULL OR s.is_delisted = 0)
            ORDER BY dp.amount DESC LIMIT 100
        """,
            (target_date_str,),
        )
        stocks = cur.fetchall()
        conn.close()

        signals = []
        for code, name in stocks:
            features = trainer._extract_features_for_date(code, date.fromisoformat(target_date_str))
            if features is None:
                continue
            X = np.array([[features[f] for f in trainer._feature_names]])
            proba = trainer._model.predict_proba(X)[0]
            prob_up = float(proba[1])

            if prob_up >= threshold or prob_up <= (1 - threshold):
                signals.append({
                    "code": code,
                    "name": name,
                    "signal": "buy" if prob_up >= threshold else "sell",
                    "probability": round(prob_up, 4),
                    "confidence": round(abs(prob_up - 0.5) * 2, 4),
                })

        # 按置信度排序
        signals.sort(key=lambda x: x["confidence"], reverse=True)
        signals = signals[:top_n]

        buy_count = len([s for s in signals if s["signal"] == "buy"])
        sell_count = len([s for s in signals if s["signal"] == "sell"])

        return {
            "date": target_date_str,
            "threshold": threshold,
            "model_loaded": True,
            "summary": {
                "total_signals": len(signals),
                "buy_signals": buy_count,
                "sell_signals": sell_count,
            },
            "signals": signals,
        }

    def prediction_backtest_view(self, query: dict) -> dict:
        """
        返回最近回测结果摘要

        GET /api/prediction/backtest
        """
        import json
        from pathlib import Path

        results_dir = self.project_root / "var/backtest_results"
        if not results_dir.exists():
            return {"backtests": [], "message": "无回测数据"}

        # 找到最新的回测结果
        files = sorted(results_dir.glob("backtest_*.json"), reverse=True)
        if not files:
            return {"backtests": [], "message": "无回测数据"}

        # 读取最近3次回测
        results = []
        for f in files[:3]:
            with open(f, 'r') as fp:
                data = json.load(fp)
                data['file'] = f.name
                results.append(data)

        return {
            "backtests": results,
            "latest": results[0] if results else None,
        }

    # ------------------------------------------------------------------
    # 板块轮动服务
    # ------------------------------------------------------------------

    def sector_rotation_signals_view(self, query: dict) -> dict:
        """
        板块轮动周级别交易信号

        GET /api/sector-rotation/signals?date=YYYY-MM-DD&top_sectors=3&top_stocks=3
        """
        from datetime import date as _date

        target_date_str = query.get("date", [None])[0]
        top_sectors = int(query.get("top_sectors", [3])[0])
        top_stocks = int(query.get("top_stocks", [3])[0])

        if not target_date_str:
            conn = sqlite3.connect(str(self._stock_db_default_path))
            cur = conn.execute("SELECT MAX(trade_date) FROM daily_prices")
            target_date_str = cur.fetchone()[0]
            conn.close()

        # 延迟导入避免启动开销
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "sector_rotation",
            self.project_root / "sector_rotation.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        engine = mod.SectorRotationEngine(self._stock_db_default_path)

        result = engine.generate_weekly_signals(_date.fromisoformat(target_date_str))
        return result

    def sector_rotation_ranking_view(self, query: dict) -> dict:
        """
        板块强度排名

        GET /api/sector-rotation/ranking?date=YYYY-MM-DD&top_n=10
        """
        from datetime import date as _date

        target_date_str = query.get("date", [None])[0]
        top_n = int(query.get("top_n", [10])[0])

        if not target_date_str:
            conn = sqlite3.connect(str(self._stock_db_default_path))
            cur = conn.execute("SELECT MAX(trade_date) FROM daily_prices")
            target_date_str = cur.fetchone()[0]
            conn.close()

        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "sector_rotation",
            self.project_root / "sector_rotation.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        engine = mod.SectorRotationEngine(self._stock_db_default_path)

        scores = engine.get_sector_strength(_date.fromisoformat(target_date_str))
        return {
            "date": target_date_str,
            "total_sectors": len(scores),
            "ranking": [
                {
                    "sector": s.sector,
                    "name": s.name,
                    "score": s.composite_score,
                    "momentum_5d": s.momentum_5d,
                    "momentum_20d": s.momentum_20d,
                    "advance_ratio": s.advance_ratio,
                    "volume_ratio": s.volume_ratio,
                    "stock_count": s.stock_count,
                }
                for s in scores[:top_n]
            ],
        }

    def _lowfreq_engine_v16(self):
        from lowfreq_engine_v16_advanced import LowFreqTradingEngineV16

        engine = getattr(self, "_lowfreq_engine_v16_cached", None)
        if not isinstance(engine, LowFreqTradingEngineV16):
            engine = LowFreqTradingEngineV16(db_path=self._stock_db_default_path)
            setattr(self, "_lowfreq_engine_v16_cached", engine)
        params = self._load_lowfreq_model_params(model_id="lowfreq_engine_v16_advanced")
        if isinstance(params, dict) and params:
            for k, v in params.items():
                try:
                    setattr(engine, str(k), v)
                except Exception:
                    continue
        if self._lowfreq_sim_overrides_file.exists():
            try:
                overrides_payload = json.loads(
                    self._lowfreq_sim_overrides_file.read_text(encoding="utf-8")
                )
            except (OSError, json.JSONDecodeError):
                overrides_payload = None
            if isinstance(overrides_payload, dict):
                effective_from = str(overrides_payload.get("effective_from") or "").strip()
                try:
                    latest_trade_date = self._lowfreq_latest_trade_date()
                except Exception:
                    latest_trade_date = ""
                should_apply = False
                if not effective_from:
                    should_apply = True
                else:
                    try:
                        should_apply = date.fromisoformat(effective_from) <= date.fromisoformat(
                            str(latest_trade_date)
                        )
                    except Exception:
                        should_apply = False
                if should_apply:
                    overrides = overrides_payload.get("overrides")
                    if isinstance(overrides, dict):
                        for k, v in overrides.items():
                            try:
                                setattr(engine, str(k), v)
                            except Exception:
                                continue
        return engine

    def _load_lowfreq_model_params(self, *, model_id: str) -> Optional[dict[str, Any]]:
        model_id = str(model_id).strip()
        if not model_id:
            return None
        conn = sqlite3.connect(str(self._stock_db_default_path))
        try:
            row = conn.execute(
                "SELECT params_json FROM lowfreq_model_store WHERE model_id = ?",
                (model_id,),
            ).fetchone()
        except sqlite3.Error:
            return None
        finally:
            conn.close()
        if not row or not row[0]:
            return None
        try:
            payload = json.loads(str(row[0]))
        except Exception:
            return None
        return payload if isinstance(payload, dict) else None

    def _save_lowfreq_model_params(
        self,
        *,
        model_id: str,
        params: dict[str, Any],
        source: str,
        requested_by: str,
    ) -> dict[str, Any]:
        model_id = str(model_id).strip()
        if not model_id:
            raise ApiError(
                status_code=HTTPStatus.BAD_REQUEST,
                code="invalid_model_id",
                message="model_id must be a non-empty string",
            )
        if not isinstance(params, dict):
            raise ApiError(
                status_code=HTTPStatus.BAD_REQUEST,
                code="invalid_model_params",
                message="params must be a dict",
            )
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        params_json = json.dumps(params, ensure_ascii=False, sort_keys=True)
        conn = sqlite3.connect(str(self._stock_db_default_path))
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS lowfreq_model_store (
                    model_id TEXT PRIMARY KEY,
                    params_json TEXT NOT NULL,
                    source TEXT NOT NULL,
                    requested_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                INSERT INTO lowfreq_model_store (
                    model_id,
                    params_json,
                    source,
                    requested_by,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(model_id) DO UPDATE SET
                    params_json = excluded.params_json,
                    source = excluded.source,
                    requested_by = excluded.requested_by,
                    updated_at = excluded.updated_at
                """,
                (model_id, params_json, str(source), str(requested_by), now, now),
            )
            conn.commit()
        finally:
            conn.close()
        return {
            "status": "ok",
            "model_id": model_id,
            "params": params,
            "source": str(source),
            "requested_by": str(requested_by),
            "updated_at": now,
        }

    def _lowfreq_latest_trade_date(self) -> str:
        conn = sqlite3.connect(str(self._stock_db_default_path))
        try:
            row = conn.execute("SELECT MAX(trade_date) FROM daily_prices").fetchone()
        finally:
            conn.close()
        latest = row[0] if row else None
        if not latest:
            raise ApiError(
                status_code=HTTPStatus.CONFLICT,
                code="stock_db_empty",
                message="stock db has no daily_prices",
                details={},
            )
        return str(latest)

    def _lowfreq_trade_date_range(self) -> tuple[str, str]:
        conn = sqlite3.connect(str(self._stock_db_default_path))
        try:
            row = conn.execute(
                "SELECT MIN(trade_date), MAX(trade_date) FROM daily_prices"
            ).fetchone()
        finally:
            conn.close()
        if not row or not row[0] or not row[1]:
            raise ApiError(
                status_code=HTTPStatus.CONFLICT,
                code="stock_db_empty",
                message="stock db has no daily_prices",
                details={},
            )
        return str(row[0]), str(row[1])

    def _load_lowfreq_sim_state(self) -> dict[str, Any]:
        state_path = self._lowfreq_sim_state_file
        if not state_path.exists():
            return {
                "strategy": "low_freq_v16_advanced",
                "initial_capital": 1_000_000.0,
                "cash": 1_000_000.0,
                "day_index": 0,
                "last_date": None,
                "positions": {},
                "closed_trades": [],
                "settings": {"autopilot_enabled": False},
                "manual": {"intents": []},
            }
        try:
            payload = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        payload.setdefault("strategy", "low_freq_v16_advanced")
        payload.setdefault("initial_capital", 1_000_000.0)
        payload.setdefault("cash", 1_000_000.0)
        payload.setdefault("day_index", 0)
        payload.setdefault("last_date", None)
        payload.setdefault("positions", {})
        payload.setdefault("closed_trades", [])
        payload.setdefault("settings", {"autopilot_enabled": False})
        payload.setdefault("manual", {"intents": []})
        if not isinstance(payload["positions"], dict):
            payload["positions"] = {}
        if not isinstance(payload["closed_trades"], list):
            payload["closed_trades"] = []
        if not isinstance(payload["manual"], dict):
            payload["manual"] = {"intents": []}
        if not isinstance(payload.get("settings"), dict):
            payload["settings"] = {"autopilot_enabled": False}
        payload["settings"].setdefault("autopilot_enabled", False)
        payload["manual"].setdefault("intents", [])
        if not isinstance(payload["manual"]["intents"], list):
            payload["manual"]["intents"] = []
        return payload

    def _lowfreq_next_trading_day(self, after_date: str) -> str:
        db_path = Path(
            os.environ.get("NEOTRADE3_STOCK_DB_PATH") or str(self._stock_db_default_path)
        ).expanduser()
        conn = sqlite3.connect(str(db_path))
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT MIN(trade_date) FROM trading_calendar_cache WHERE trade_date > ?",
                (after_date,),
            )
            row = cursor.fetchone()
            next_trading_day = str(row[0]) if row and row[0] else ""
        finally:
            conn.close()
        if not next_trading_day:
            raise ApiError(
                status_code=HTTPStatus.CONFLICT,
                code="next_trading_day_unavailable",
                message="next trading day unavailable",
                details={"after_date": after_date},
            )
        return next_trading_day

    def _lowfreq_get_open_price(self, *, engine, code: str, trade_date: date) -> Optional[float]:
        code = str(code or "").strip()
        if not code:
            return None
        conn = None
        try:
            conn = engine._conn()
            cursor = conn.execute(
                "SELECT open FROM daily_prices WHERE code = ? AND trade_date = ?",
                (code, trade_date.isoformat()),
            )
            row = cursor.fetchone()
            if row and row[0] is not None:
                return float(row[0])
            return None
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

    def _lowfreq_execute_pending_intents_for_date(
        self, *, state: dict[str, Any], engine, execute_date: date
    ) -> dict[str, Any]:
        positions: dict[str, dict[str, Any]] = state.get("positions", {})
        cash = float(state.get("cash") or 0.0)
        closed_trades: list[dict[str, Any]] = state.get("closed_trades", [])
        manual = state.get("manual") if isinstance(state.get("manual"), dict) else {"intents": []}
        intents = manual.get("intents") if isinstance(manual.get("intents"), list) else []

        abandon_pairs: set[tuple[str, str]] = set()
        for intent in intents:
            if not isinstance(intent, dict):
                continue
            if str(intent.get("intent_type") or "") != "abandon":
                continue
            code = str(intent.get("code") or "").strip()
            requested_date = str(intent.get("requested_date") or "").strip()
            if code and requested_date:
                abandon_pairs.add((code, requested_date))

        executed_buy = 0
        executed_sell = 0
        executed_key = execute_date.isoformat()

        for intent in intents:
            if not isinstance(intent, dict):
                continue
            intent_type = str(intent.get("intent_type") or "")
            if intent_type not in {"buy_intent", "sell_intent"}:
                continue
            if str(intent.get("status") or "pending") != "pending":
                continue
            if str(intent.get("execute_date") or "").strip() != executed_key:
                continue

            code = str(intent.get("code") or "").strip()
            if not code:
                intent["status"] = "cancelled"
                intent["cancel_reason"] = "invalid_code"
                intent["cancelled_at"] = datetime.now(timezone.utc).isoformat()
                continue

            requested_date = str(intent.get("requested_date") or "").strip()
            if requested_date and (code, requested_date) in abandon_pairs:
                intent["status"] = "cancelled"
                intent["cancel_reason"] = "abandoned"
                intent["cancelled_at"] = datetime.now(timezone.utc).isoformat()
                continue

            px = self._lowfreq_get_open_price(engine=engine, code=code, trade_date=execute_date)
            if not px or float(px) <= 0:
                intent["attempt_count"] = int(intent.get("attempt_count") or 0) + 1
                intent["last_attempt_date"] = executed_key
                intent["last_attempt_reason"] = "no_open_price"
                try:
                    intent["execute_date"] = self._lowfreq_next_trading_day(executed_key)
                except Exception:
                    pass
                continue

            if intent_type == "buy_intent":
                if code in positions and isinstance(positions.get(code), dict):
                    intent["status"] = "cancelled"
                    intent["cancel_reason"] = "already_holding"
                    intent["cancelled_at"] = datetime.now(timezone.utc).isoformat()
                    continue

                slots = int(engine.MAX_POSITIONS) - len(positions)
                if slots <= 0:
                    intent["attempt_count"] = int(intent.get("attempt_count") or 0) + 1
                    intent["last_attempt_date"] = executed_key
                    intent["last_attempt_reason"] = "no_slots"
                    try:
                        intent["execute_date"] = self._lowfreq_next_trading_day(executed_key)
                    except Exception:
                        pass
                    continue

                per_slot = cash / max(slots, 1)
                shares = int(per_slot / float(px) / 100) * 100
                if shares < 100 or shares * float(px) > cash:
                    intent["attempt_count"] = int(intent.get("attempt_count") or 0) + 1
                    intent["last_attempt_date"] = executed_key
                    intent["last_attempt_reason"] = "no_cash"
                    try:
                        intent["execute_date"] = self._lowfreq_next_trading_day(executed_key)
                    except Exception:
                        pass
                    continue

                cash -= shares * float(px)
                positions[code] = {
                    "code": code,
                    "name": str(intent.get("name") or ""),
                    "sector": str(intent.get("sector") or ""),
                    "buy_date": executed_key,
                    "buy_price": float(px),
                    "shares": int(shares),
                    "shares_sold": 0,
                    "buy_score": float(intent.get("buy_score") or 0.0),
                    "wave_phase": str(intent.get("wave_phase") or ""),
                    "peak_price": float(px),
                    "partial_taken": False,
                    "sell_reason": "",
                    "status": "open",
                    "role": str(intent.get("role") or ""),
                }
                intent["status"] = "executed"
                intent["executed_date"] = executed_key
                intent["executed_price"] = float(px)
                intent["executed_shares"] = int(shares)
                intent["executed_at"] = datetime.now(timezone.utc).isoformat()
                executed_buy += 1
                continue

            if code not in positions or not isinstance(positions.get(code), dict):
                intent["status"] = "cancelled"
                intent["cancel_reason"] = "position_missing"
                intent["cancelled_at"] = datetime.now(timezone.utc).isoformat()
                continue

            trade = self._lowfreq_trade_from_payload(positions[code])
            ratio = float(intent.get("partial_ratio") or 1.0)
            ratio = 0.5 if ratio < 1.0 else 1.0
            shares_to_sell = int(trade.shares // 2) if ratio < 1.0 else int(trade.shares)
            if shares_to_sell <= 0:
                intent["status"] = "cancelled"
                intent["cancel_reason"] = "no_shares"
                intent["cancelled_at"] = datetime.now(timezone.utc).isoformat()
                continue

            cash += float(px) * float(shares_to_sell)
            ret = (float(px) - trade.buy_price) / max(trade.buy_price, 1e-9) * 100.0
            closed = self._lowfreq_trade_from_payload(self._lowfreq_trade_to_payload(trade))
            closed.sell_date = executed_key
            closed.sell_price = float(px)
            closed.shares = shares_to_sell
            closed.return_pct = round(ret, 2)
            closed.hold_days = engine._count_trading_days(date.fromisoformat(trade.buy_date), execute_date)
            closed.sell_reason = str(intent.get("sell_reason") or "")
            closed.status = "closed"
            closed_trades.append(self._lowfreq_trade_to_payload(closed))

            if ratio < 1.0:
                trade.shares -= shares_to_sell
                trade.shares_sold += shares_to_sell
                trade.partial_taken = True
                positions[code] = self._lowfreq_trade_to_payload(trade)
            else:
                positions.pop(code, None)

            intent["status"] = "executed"
            intent["executed_date"] = executed_key
            intent["executed_price"] = float(px)
            intent["executed_shares"] = int(shares_to_sell)
            intent["executed_at"] = datetime.now(timezone.utc).isoformat()
            executed_sell += 1

        state["cash"] = round(cash, 2)
        state["positions"] = positions
        state["closed_trades"] = closed_trades
        state["manual"] = {"intents": intents}
        return {"executed_buy": executed_buy, "executed_sell": executed_sell}

    def _save_lowfreq_sim_state(self, state: dict[str, Any]) -> None:
        self._lowfreq_sim_state_file.parent.mkdir(parents=True, exist_ok=True)
        self._lowfreq_sim_state_file.write_text(
            json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def _lowfreq_trade_from_payload(self, payload: dict[str, Any]):
        from lowfreq_engine_v16_advanced import TradeRecord

        return TradeRecord(
            code=str(payload.get("code") or ""),
            name=str(payload.get("name") or ""),
            sector=str(payload.get("sector") or ""),
            buy_date=str(payload.get("buy_date") or ""),
            sell_date=str(payload.get("sell_date") or ""),
            buy_price=float(payload.get("buy_price") or 0.0),
            sell_price=float(payload.get("sell_price") or 0.0),
            shares=int(payload.get("shares") or 0),
            shares_sold=int(payload.get("shares_sold") or 0),
            hold_days=int(payload.get("hold_days") or 0),
            return_pct=float(payload.get("return_pct") or 0.0),
            buy_score=float(payload.get("buy_score") or 0.0),
            wave_phase=str(payload.get("wave_phase") or ""),
            peak_price=float(payload.get("peak_price") or 0.0),
            partial_taken=bool(payload.get("partial_taken") or False),
            sell_reason=str(payload.get("sell_reason") or ""),
            status=str(payload.get("status") or "open"),
            role=str(payload.get("role") or ""),
        )

    def _lowfreq_trade_to_payload(self, trade) -> dict[str, Any]:
        from dataclasses import asdict

        return asdict(trade)

    def _lowfreq_intents_for_requested_date(
        self, *, intents: list[dict[str, Any]], requested_date: str
    ) -> list[dict[str, Any]]:
        requested_date = str(requested_date or "").strip()
        out: list[dict[str, Any]] = []
        for it in intents:
            if not isinstance(it, dict):
                continue
            if str(it.get("requested_date") or "").strip() != requested_date:
                continue
            out.append(it)
        return out

    def _lowfreq_find_pending_intent(
        self,
        *,
        intents: list[dict[str, Any]],
        intent_type: str,
        code: str,
        requested_date: str,
    ) -> Optional[dict[str, Any]]:
        intent_type = str(intent_type or "").strip()
        code = str(code or "").strip()
        requested_date = str(requested_date or "").strip()
        for it in intents:
            if not isinstance(it, dict):
                continue
            if str(it.get("intent_type") or "").strip() != intent_type:
                continue
            if str(it.get("status") or "pending") != "pending":
                continue
            if str(it.get("code") or "").strip() != code:
                continue
            if str(it.get("requested_date") or "").strip() != requested_date:
                continue
            return it
        return None

    def _lowfreq_generate_execution_intents_for_date(
        self,
        *,
        state: dict[str, Any],
        engine,
        requested_date: date,
    ) -> dict[str, Any]:
        requested_key = requested_date.isoformat()
        execute_date = self._lowfreq_next_trading_day(requested_key)
        manual = state.get("manual") if isinstance(state.get("manual"), dict) else {"intents": []}
        intents = manual.get("intents") if isinstance(manual.get("intents"), list) else []

        abandon_codes: set[str] = set()
        for it in self._lowfreq_intents_for_requested_date(intents=intents, requested_date=requested_key):
            if str(it.get("intent_type") or "") == "abandon" and str(it.get("status") or "") == "recorded":
                c = str(it.get("code") or "").strip()
                if c:
                    abandon_codes.add(c)

        positions: dict[str, dict[str, Any]] = state.get("positions", {})
        created_buy = 0
        created_sell = 0

        for code, trade_payload in positions.items():
            if not isinstance(trade_payload, dict):
                continue
            trade = self._lowfreq_trade_from_payload(trade_payload)
            sell = engine.check_sell_signal_v2(trade, requested_date)
            positions[code] = self._lowfreq_trade_to_payload(trade)
            if not sell:
                continue
            code_s = str(code or "").strip()
            if not code_s or code_s in abandon_codes:
                continue
            if self._lowfreq_find_pending_intent(
                intents=intents,
                intent_type="sell_intent",
                code=code_s,
                requested_date=requested_key,
            ):
                continue
            intents.append(
                {
                    "intent_id": uuid.uuid4().hex,
                    "intent_type": "sell_intent",
                    "status": "pending",
                    "code": code_s,
                    "name": str(trade.name or ""),
                    "sector": str(trade.sector or ""),
                    "role": str(trade.role or ""),
                    "requested_date": requested_key,
                    "execute_date": execute_date,
                    "sell_reason": str(getattr(sell, "details", "") or ""),
                    "sell_signal": str(getattr(sell, "reason", "") or ""),
                    "partial_ratio": 0.5 if str(getattr(sell, "reason", "") or "") == "partial_profit" else 1.0,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            created_sell += 1

        try:
            signals = engine.generate_buy_signals(requested_date)
        except Exception:
            signals = {}
        raw = signals.get("buy_signals", []) if isinstance(signals, dict) else []
        for sig in raw:
            if not isinstance(sig, dict):
                continue
            code = str(sig.get("code") or "").strip()
            if not code or code in positions or code in abandon_codes:
                continue
            if self._lowfreq_find_pending_intent(
                intents=intents,
                intent_type="buy_intent",
                code=code,
                requested_date=requested_key,
            ):
                continue
            intents.append(
                {
                    "intent_id": uuid.uuid4().hex,
                    "intent_type": "buy_intent",
                    "status": "pending",
                    "code": code,
                    "name": str(sig.get("name") or ""),
                    "sector": str(sig.get("sector") or ""),
                    "role": str(sig.get("role") or ""),
                    "buy_score": float(sig.get("buy_score") or 0.0),
                    "wave_phase": str(sig.get("wave_phase") or ""),
                    "requested_date": requested_key,
                    "execute_date": execute_date,
                    "attempt_count": 0,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "source": "model",
                }
            )
            created_buy += 1

        state["positions"] = positions
        state["manual"] = {"intents": intents}
        return {
            "requested_date": requested_key,
            "execute_date": execute_date,
            "created_buy": created_buy,
            "created_sell": created_sell,
        }

    def _advance_lowfreq_sim_state(
        self, *, state: dict[str, Any], engine, target_date: date
    ) -> None:
        settings = state.get("settings") if isinstance(state.get("settings"), dict) else {}
        autopilot_enabled = bool(settings.get("autopilot_enabled"))
        last_date = state.get("last_date")
        if isinstance(last_date, str) and last_date.strip():
            start_date = date.fromisoformat(last_date)
        else:
            start_date = target_date

        trading_dates = engine._get_trading_dates(start_date, target_date)
        if trading_dates and trading_dates[0] == start_date and start_date != target_date:
            trading_dates = trading_dates[1:]

        for current_date in trading_dates or [target_date]:
            positions: dict[str, dict[str, Any]] = state.get("positions", {})
            cash = float(state.get("cash") or 0.0)
            closed_trades: list[dict[str, Any]] = state.get("closed_trades", [])
            day_index = int(state.get("day_index") or 0)
            manual = state.get("manual") if isinstance(state.get("manual"), dict) else {"intents": []}
            intents = manual.get("intents") if isinstance(manual.get("intents"), list) else []

            if not autopilot_enabled:
                self._lowfreq_generate_execution_intents_for_date(
                    state=state, engine=engine, requested_date=current_date
                )
                state["day_index"] = day_index + 1
                state["last_date"] = current_date.isoformat()
                continue
            self._lowfreq_execute_pending_intents_for_date(
                state=state,
                engine=engine,
                execute_date=current_date,
            )
            self._lowfreq_generate_execution_intents_for_date(
                state=state,
                engine=engine,
                requested_date=current_date,
            )
            state["day_index"] = day_index + 1
            state["last_date"] = current_date.isoformat()

    def _build_lowfreq_hot_sectors_snapshot(
        self,
        *,
        engine,
        state: dict[str, Any],
        target_date: date,
        include_portfolio: bool = True,
        include_sell_signal: bool = True,
        perf: Optional[dict[str, float]] = None,
    ) -> dict[str, Any]:
        positions: dict[str, dict[str, Any]] = state.get("positions", {})
        manual = state.get("manual") if isinstance(state.get("manual"), dict) else {"intents": []}
        intents = manual.get("intents") if isinstance(manual.get("intents"), list) else []
        target_key = target_date.isoformat()
        pending_buy_by_code: dict[str, dict[str, Any]] = {}
        abandoned_codes: set[str] = set()
        for intent in intents:
            if not isinstance(intent, dict):
                continue
            code = str(intent.get("code") or "").strip()
            requested_date = str(intent.get("requested_date") or "").strip()
            if not code or requested_date != target_key:
                continue
            if str(intent.get("intent_type") or "") == "abandon":
                abandoned_codes.add(code)
            elif str(intent.get("intent_type") or "") == "buy_intent" and str(intent.get("status") or "pending") == "pending":
                pending_buy_by_code[code] = intent

        sectors_payload: list[dict[str, Any]] = []
        t0 = time.perf_counter()
        hot_sectors = engine.get_hot_sectors(target_date, top_n=int(engine.HOT_SECTOR_COUNT))
        if perf is not None:
            perf["get_hot_sectors_ms"] = round((time.perf_counter() - t0) * 1000.0, 3)

        t_candidates_total = 0.0
        for sh in hot_sectors:
            try:
                t1 = time.perf_counter()
                candidates = engine.get_sector_candidates(sh.sector, target_date, top_n=15)
                t_candidates_total += time.perf_counter() - t1
            except Exception:
                candidates = []
            leaders: list[dict[str, Any]] = []
            middle: list[dict[str, Any]] = []
            followers: list[dict[str, Any]] = []
            for c in candidates:
                buy_signal = (
                    float(c.buy_score) >= float(engine.BUY_THRESHOLD)
                    and str(c.role) != "跟随"
                    and float(c.sector_resonance) >= float(engine.MIN_RESONANCE)
                )
                sell_signal = False
                sell_reason = None
                if (
                    include_sell_signal
                    and c.code in positions
                    and isinstance(positions[c.code], dict)
                ):
                    trade = self._lowfreq_trade_from_payload(positions[c.code])
                    sell = engine.check_sell_signal_v2(trade, target_date)
                    positions[c.code] = self._lowfreq_trade_to_payload(trade)
                    if sell:
                        sell_signal = True
                        sell_reason = sell.details

                stock_payload = {
                    "code": c.code,
                    "name": c.name,
                    "certainty": float(c.buy_score),
                    "buy_score": float(c.buy_score),
                    "sector": str(sh.name or sh.sector or getattr(c, "sector", "") or ""),
                    "role": str(getattr(c, "role", "") or ""),
                    "reasons": list(getattr(c, "buy_reasons", []) or []),
                    "cup_handle_ok": bool(getattr(c, "cup_handle_ok", False)),
                    "resonance": float(getattr(c, "sector_resonance", 0.0) or 0.0),
                    "wave_phase": str(getattr(c, "wave_phase", "") or ""),
                    "return_5d": float(c.ret_5d),
                    "buy_signal": bool(buy_signal),
                    "sell_signal": bool(sell_signal),
                    "sell_reason": sell_reason,
                    "suggested_entry": "今日" if buy_signal else None,
                    "manual": {
                        "abandoned": c.code in abandoned_codes,
                        "buy_intent_pending": c.code in pending_buy_by_code,
                        "buy_execute_date": (
                            str(pending_buy_by_code.get(c.code, {}).get("execute_date") or "")
                            if c.code in pending_buy_by_code
                            else None
                        ),
                        "intent_id": (
                            str(pending_buy_by_code.get(c.code, {}).get("intent_id") or "")
                            if c.code in pending_buy_by_code
                            else None
                        ),
                    },
                }
                if c.role == "龙头":
                    leaders.append(stock_payload)
                elif c.role == "中军":
                    middle.append(stock_payload)
                else:
                    followers.append(stock_payload)

            sectors_payload.append(
                {
                    "code": sh.sector,
                    "name": sh.name,
                    "heat_score": float(sh.heat_score),
                    "leaders": leaders[:3],
                    "middle": middle[:5],
                    "followers": followers[:7],
                }
            )

        if perf is not None:
            perf["get_sector_candidates_ms_total"] = round(t_candidates_total * 1000.0, 3)

        portfolio = None
        if include_portfolio:
            t2 = time.perf_counter()
            portfolio = self._lowfreq_portfolio_view(engine=engine, state=state, target_date=target_date)
            if perf is not None:
                perf["portfolio_ms"] = round((time.perf_counter() - t2) * 1000.0, 3)
        return {
            "date": target_date.isoformat(),
            "sectors": sectors_payload,
            "portfolio": portfolio,
            "manual": {
                "requested_date": target_key,
                "pending_buy_intents": len(pending_buy_by_code),
                "abandoned": len(abandoned_codes),
            },
        }

    def lowfreq_manual_buy_intent_view(
        self,
        *,
        code: str,
        requested_date: str,
        name: str = "",
        sector: str = "",
        role: str = "",
        buy_score: float = 0.0,
        requested_by: str = "api",
    ) -> dict[str, Any]:
        code = str(code or "").strip()
        requested_date = str(requested_date or "").strip()
        if not code:
            raise ApiError(
                status_code=HTTPStatus.BAD_REQUEST,
                code="invalid_code",
                message="code must be a non-empty string",
                details={"code": code},
            )
        try:
            date.fromisoformat(requested_date)
        except ValueError:
            raise ApiError(
                status_code=HTTPStatus.BAD_REQUEST,
                code="invalid_requested_date",
                message=f"invalid requested_date: {requested_date}",
                details={"requested_date": requested_date},
            )

        execute_date = self._lowfreq_next_trading_day(requested_date)
        state = self._load_lowfreq_sim_state()
        manual = state.get("manual") if isinstance(state.get("manual"), dict) else {"intents": []}
        intents = manual.get("intents") if isinstance(manual.get("intents"), list) else []

        for intent in intents:
            if not isinstance(intent, dict):
                continue
            if str(intent.get("intent_type") or "") != "buy_intent":
                continue
            if str(intent.get("status") or "pending") != "pending":
                continue
            if str(intent.get("code") or "").strip() == code and str(intent.get("requested_date") or "").strip() == requested_date:
                return {"_meta": {"status": "ok", "requested_by": requested_by}, "intent": intent}

        intent = {
            "intent_id": uuid.uuid4().hex,
            "intent_type": "buy_intent",
            "status": "pending",
            "code": code,
            "name": str(name or ""),
            "sector": str(sector or ""),
            "role": str(role or ""),
            "buy_score": float(buy_score or 0.0),
            "requested_date": requested_date,
            "execute_date": execute_date,
            "attempt_count": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        intents.append(intent)
        state["manual"] = {"intents": intents}
        self._save_lowfreq_sim_state(state)
        return {"_meta": {"status": "ok", "requested_by": requested_by}, "intent": intent}

    def lowfreq_manual_abandon_view(
        self, *, code: str, requested_date: str, requested_by: str = "api"
    ) -> dict[str, Any]:
        code = str(code or "").strip()
        requested_date = str(requested_date or "").strip()
        if not code:
            raise ApiError(
                status_code=HTTPStatus.BAD_REQUEST,
                code="invalid_code",
                message="code must be a non-empty string",
                details={"code": code},
            )
        try:
            date.fromisoformat(requested_date)
        except ValueError:
            raise ApiError(
                status_code=HTTPStatus.BAD_REQUEST,
                code="invalid_requested_date",
                message=f"invalid requested_date: {requested_date}",
                details={"requested_date": requested_date},
            )

        state = self._load_lowfreq_sim_state()
        manual = state.get("manual") if isinstance(state.get("manual"), dict) else {"intents": []}
        intents = manual.get("intents") if isinstance(manual.get("intents"), list) else []

        for intent in intents:
            if not isinstance(intent, dict):
                continue
            if str(intent.get("intent_type") or "") != "buy_intent":
                continue
            if str(intent.get("status") or "pending") != "pending":
                continue
            if str(intent.get("code") or "").strip() == code and str(intent.get("requested_date") or "").strip() == requested_date:
                intent["status"] = "cancelled"
                intent["cancel_reason"] = "abandoned"
                intent["cancelled_at"] = datetime.now(timezone.utc).isoformat()

        abandon_intent = {
            "intent_id": uuid.uuid4().hex,
            "intent_type": "abandon",
            "status": "recorded",
            "code": code,
            "requested_date": requested_date,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        intents.append(abandon_intent)
        state["manual"] = {"intents": intents}
        self._save_lowfreq_sim_state(state)
        return {"_meta": {"status": "ok", "requested_by": requested_by}, "intent": abandon_intent}

    def lowfreq_settings_set_autopilot_view(
        self,
        *,
        enabled: bool,
        requested_by: str = "api",
    ) -> dict[str, Any]:
        state = self._load_lowfreq_sim_state()
        settings = state.get("settings") if isinstance(state.get("settings"), dict) else {}
        settings["autopilot_enabled"] = bool(enabled)
        settings["updated_at"] = datetime.now(timezone.utc).isoformat()
        settings["updated_by"] = str(requested_by or "api")
        state["settings"] = settings
        self._save_lowfreq_sim_state(state)
        return {
            "_meta": {"status": "ok", "requested_by": requested_by},
            "autopilot_enabled": bool(settings.get("autopilot_enabled")),
        }

    def lowfreq_execution_queue_view(
        self,
        *,
        target_date: Optional[str] = None,
        requested_by: str = "api",
        ensure_generated: bool = True,
    ) -> dict[str, Any]:
        if target_date:
            target_dt = date.fromisoformat(str(target_date))
        else:
            target_dt = date.fromisoformat(self._lowfreq_latest_trade_date())

        engine = self._lowfreq_engine_v16()
        state = self._load_lowfreq_sim_state()
        settings = state.get("settings") if isinstance(state.get("settings"), dict) else {}
        autopilot_enabled = bool(settings.get("autopilot_enabled"))
        latest_trade_dt = date.fromisoformat(self._lowfreq_latest_trade_date())

        if ensure_generated and not autopilot_enabled:
            self._lowfreq_generate_execution_intents_for_date(
                state=state, engine=engine, requested_date=target_dt
            )
            self._save_lowfreq_sim_state(state)

        manual = state.get("manual") if isinstance(state.get("manual"), dict) else {"intents": []}
        intents = manual.get("intents") if isinstance(manual.get("intents"), list) else []
        req_key = target_dt.isoformat()
        items: list[dict[str, Any]] = []
        cooldown_cache: dict[str, dict[str, Any]] = {}
        market_regime = "unknown"
        calibration_map: dict[str, dict[str, Any]] = {}
        _calib_conn = None
        try:
            _calib_conn = engine._conn()
            calibration_map = self._confidence_load_calibration_map(conn=_calib_conn, as_of_date=req_key)
        except Exception:
            calibration_map = {}
        finally:
            if _calib_conn is not None:
                try:
                    _calib_conn.close()
                except Exception:
                    pass
        for it in intents:
            if not isinstance(it, dict):
                continue
            if str(it.get("requested_date") or "").strip() != req_key:
                continue
            if str(it.get("intent_type") or "") not in {"buy_intent", "sell_intent"}:
                continue
            item = dict(it)
            intent_type = str(item.get("intent_type") or "")
            sector_name = str(item.get("sector") or "").strip()

            can_execute = True
            blocked_reason: Optional[str] = None
            execute_date = str(item.get("execute_date") or "").strip()
            if execute_date:
                try:
                    exec_dt = date.fromisoformat(execute_date)
                except Exception:
                    can_execute = False
                    blocked_reason = "invalid_execute_date"
                else:
                    if exec_dt > latest_trade_dt:
                        can_execute = False
                        blocked_reason = "execute_date_not_reached"

            cooldown_info = cooldown_cache.get(sector_name)
            if cooldown_info is None:
                try:
                    raw = engine._sector_cooldown_confirmed(sector_name, target_dt) if sector_name else {}
                    cooldown_info = raw if isinstance(raw, dict) else {}
                except Exception:
                    cooldown_info = {}
                cooldown_cache[sector_name] = cooldown_info
            cooldown_confirmed = bool(cooldown_info.get("confirmed")) if isinstance(cooldown_info, dict) else False
            cooldown_hits = 0
            if isinstance(cooldown_info, dict):
                try:
                    cooldown_hits = int(cooldown_info.get("hits") or 0)
                except Exception:
                    cooldown_hits = 0
            risk_level = "exit" if (intent_type == "sell_intent" or cooldown_confirmed) else "warn" if cooldown_hits > 0 else "ok"
            risk_reason: Optional[str] = None
            if intent_type == "sell_intent":
                risk_reason = str(item.get("sell_reason") or item.get("sell_signal") or "卖出信号")
            elif cooldown_confirmed:
                risk_reason = "冷却确认成立"
            elif cooldown_hits > 0:
                risk_reason = "当日命中但未确认"
            item["risk_level"] = risk_level
            item["risk_reason"] = risk_reason

            raw_score = item.get("buy_score")
            bucket_key = self._confidence_bucket_key(
                raw_score=(float(raw_score) if isinstance(raw_score, (int, float)) else None),
                role=str(item.get("role") or ""),
                risk_level=risk_level,
                market_regime=market_regime,
            )
            bucket = calibration_map.get(bucket_key)
            item["confidence_prob"] = float(bucket.get("confidence_prob")) if isinstance(bucket, dict) else None
            item["confidence_samples"] = int(bucket.get("n")) if isinstance(bucket, dict) else 0

            item["can_execute"] = bool(can_execute)
            item["blocked_reason"] = blocked_reason
            items.append(item)
        items.sort(key=lambda x: (str(x.get("intent_type") or ""), str(x.get("code") or "")))

        regime_snapshot = {
            "target_date": req_key,
            "market_regime": market_regime,
            "source": "lowfreq_engine_v16",
        }

        if items:
            import sqlite3

            codes_in_items = sorted({str(x.get("code") or "").strip() for x in items if str(x.get("code") or "").strip()})
            execute_dates = sorted(
                {
                    str(x.get("execute_date") or "").strip()
                    for x in items
                    if str(x.get("execute_date") or "").strip()
                }
            )
            if not execute_dates:
                try:
                    execute_dates = [self._lowfreq_next_trading_day(req_key)]
                except Exception:
                    execute_dates = []

            by_code_today: dict[str, sqlite3.Row] = {}
            by_date_open: dict[str, dict[str, float]] = {}
            if codes_in_items:
                placeholders = ",".join("?" for _ in codes_in_items)
                conn = sqlite3.connect(str(self._stock_db_default_path))
                try:
                    conn.row_factory = sqlite3.Row
                    cur = conn.cursor()
                    cur.execute(
                        f"""
                        SELECT code, amount, volume
                        FROM daily_prices
                        WHERE trade_date = ?
                          AND code IN ({placeholders})
                        """,
                        (req_key, *codes_in_items),
                    )
                    by_code_today = {str(r["code"]): r for r in cur.fetchall()}

                    for dkey in execute_dates:
                        if not dkey:
                            continue
                        cur.execute(
                            f"""
                            SELECT code, open
                            FROM daily_prices
                            WHERE trade_date = ?
                              AND code IN ({placeholders})
                            """,
                            (dkey, *codes_in_items),
                        )
                        open_map: dict[str, float] = {}
                        for r in cur.fetchall():
                            code = str(r["code"])
                            open_px = r["open"]
                            if isinstance(open_px, (int, float)):
                                open_map[code] = float(open_px)
                        by_date_open[dkey] = open_map
                finally:
                    conn.close()

            for item in items:
                code = str(item.get("code") or "").strip()
                row = by_code_today.get(code)
                has_price_bar = row is not None
                amount_yuan = float(row["amount"]) if (row is not None and isinstance(row["amount"], (int, float))) else None
                volume_shares = float(row["volume"]) if (row is not None and isinstance(row["volume"], (int, float))) else None
                liquidity_ok = bool(
                    amount_yuan is not None
                    and volume_shares is not None
                    and amount_yuan > 0.0
                    and volume_shares > 0.0
                )
                execute_date = str(item.get("execute_date") or "").strip() or None
                execute_open = None
                execute_open_available = False
                if execute_date and code:
                    open_map = by_date_open.get(execute_date) or {}
                    if code in open_map:
                        execute_open = float(open_map[code])
                        execute_open_available = True

                item["constraint"] = {
                    "trade_mode": {
                        "settlement": "T+1_stock",
                        "execution_convention": "signal_day->next_trading_day_open",
                    },
                    "tradability": {
                        "requested_date": req_key,
                        "has_price_bar": has_price_bar,
                        "amount_yuan": amount_yuan,
                        "volume_shares": volume_shares,
                        "liquidity_ok": liquidity_ok,
                        "execute_date": execute_date,
                        "execute_open": execute_open,
                        "execute_open_available": execute_open_available,
                    },
                }
                item["regime_snapshot"] = regime_snapshot

        return {
            "_meta": {"status": "ok", "requested_by": requested_by},
            "date": req_key,
            "latest_trade_date": latest_trade_dt.isoformat(),
            "autopilot_enabled": autopilot_enabled,
            "regime_snapshot": regime_snapshot,
            "queue": items,
        }

    def lowfreq_execution_intent_processed_view(
        self,
        *,
        intent_id: str,
        requested_by: str = "api",
    ) -> dict[str, Any]:
        intent_id = str(intent_id or "").strip()
        if not intent_id:
            raise ApiError(
                status_code=HTTPStatus.BAD_REQUEST,
                code="invalid_intent_id",
                message="intent_id must be a non-empty string",
            )
        engine = self._lowfreq_engine_v16()
        state = self._load_lowfreq_sim_state()
        manual = state.get("manual") if isinstance(state.get("manual"), dict) else {"intents": []}
        intents = manual.get("intents") if isinstance(manual.get("intents"), list) else []
        target_intent: Optional[dict[str, Any]] = None
        for it in intents:
            if isinstance(it, dict) and str(it.get("intent_id") or "").strip() == intent_id:
                target_intent = it
                break
        if target_intent is None:
            raise ApiError(
                status_code=HTTPStatus.NOT_FOUND,
                code="intent_not_found",
                message="intent not found",
                details={"intent_id": intent_id},
            )
        if str(target_intent.get("status") or "pending") != "pending":
            return {"_meta": {"status": "ok", "requested_by": requested_by}, "intent": dict(target_intent)}

        intent_type = str(target_intent.get("intent_type") or "")
        execute_date = str(target_intent.get("execute_date") or "").strip()
        if not execute_date:
            requested_date = str(target_intent.get("requested_date") or "").strip()
            if requested_date:
                execute_date = self._lowfreq_next_trading_day(requested_date)
            else:
                raise ApiError(
                    status_code=HTTPStatus.CONFLICT,
                    code="execute_date_missing",
                    message="execute_date missing",
                )
        exec_dt = date.fromisoformat(execute_date)

        positions: dict[str, dict[str, Any]] = state.get("positions", {})
        cash = float(state.get("cash") or 0.0)
        closed_trades: list[dict[str, Any]] = state.get("closed_trades", [])

        if intent_type == "buy_intent":
            code = str(target_intent.get("code") or "").strip()
            if not code:
                raise ApiError(
                    status_code=HTTPStatus.CONFLICT,
                    code="invalid_code",
                    message="intent code invalid",
                )
            if code in positions:
                target_intent["status"] = "cancelled"
                target_intent["cancel_reason"] = "already_holding"
                target_intent["cancelled_at"] = datetime.now(timezone.utc).isoformat()
                state["manual"] = {"intents": intents}
                self._save_lowfreq_sim_state(state)
                return {"_meta": {"status": "ok", "requested_by": requested_by}, "intent": dict(target_intent)}

            price = self._lowfreq_get_open_price(engine=engine, code=code, trade_date=exec_dt)
            if not price or float(price) <= 0:
                raise ApiError(
                    status_code=HTTPStatus.CONFLICT,
                    code="no_price",
                    message="no price for execute_date",
                    details={"code": code, "execute_date": execute_date},
                )
            slots = int(engine.MAX_POSITIONS) - len(positions)
            if slots <= 0:
                raise ApiError(
                    status_code=HTTPStatus.CONFLICT,
                    code="no_slots",
                    message="no available slots",
                    details={"max_positions": int(engine.MAX_POSITIONS)},
                )
            per_slot = cash / max(slots, 1)
            shares = int(per_slot / float(price) / 100) * 100
            if shares < 100 or shares * float(price) > cash:
                raise ApiError(
                    status_code=HTTPStatus.CONFLICT,
                    code="insufficient_cash",
                    message="insufficient cash for buy",
                    details={"cash": cash, "price": float(price), "shares": shares},
                )
            cash -= shares * float(price)
            positions[code] = {
                "code": code,
                "name": str(target_intent.get("name") or ""),
                "sector": str(target_intent.get("sector") or ""),
                "buy_date": execute_date,
                "buy_price": float(price),
                "shares": int(shares),
                "shares_sold": 0,
                "buy_score": float(target_intent.get("buy_score") or 0.0),
                "wave_phase": str(target_intent.get("wave_phase") or ""),
                "peak_price": float(price),
                "partial_taken": False,
                "sell_reason": "",
                "status": "open",
                "role": str(target_intent.get("role") or ""),
            }
            target_intent["status"] = "executed"
            target_intent["executed_date"] = execute_date
            target_intent["executed_price"] = float(price)
            target_intent["executed_shares"] = int(shares)
            target_intent["executed_at"] = datetime.now(timezone.utc).isoformat()

        elif intent_type == "sell_intent":
            code = str(target_intent.get("code") or "").strip()
            if not code or code not in positions or not isinstance(positions.get(code), dict):
                raise ApiError(
                    status_code=HTTPStatus.CONFLICT,
                    code="position_missing",
                    message="position missing for sell",
                    details={"code": code},
                )
            trade = self._lowfreq_trade_from_payload(positions[code])
            price = self._lowfreq_get_open_price(engine=engine, code=code, trade_date=exec_dt)
            if not price or float(price) <= 0:
                raise ApiError(
                    status_code=HTTPStatus.CONFLICT,
                    code="no_price",
                    message="no price for execute_date",
                    details={"code": code, "execute_date": execute_date},
                )
            ratio = float(target_intent.get("partial_ratio") or 1.0)
            ratio = 0.5 if ratio < 1.0 else 1.0
            shares_to_sell = int(trade.shares // 2) if ratio < 1.0 else int(trade.shares)
            if shares_to_sell <= 0:
                target_intent["status"] = "cancelled"
                target_intent["cancel_reason"] = "no_shares"
                target_intent["cancelled_at"] = datetime.now(timezone.utc).isoformat()
            else:
                cash += float(price) * float(shares_to_sell)
                ret = (float(price) - trade.buy_price) / max(trade.buy_price, 1e-9) * 100.0
                closed = self._lowfreq_trade_from_payload(self._lowfreq_trade_to_payload(trade))
                closed.sell_date = execute_date
                closed.sell_price = float(price)
                closed.shares = shares_to_sell
                closed.return_pct = round(ret, 2)
                closed.hold_days = engine._count_trading_days(
                    date.fromisoformat(trade.buy_date), exec_dt
                )
                closed.sell_reason = str(target_intent.get("sell_reason") or "")
                closed.status = "closed"
                closed_trades.append(self._lowfreq_trade_to_payload(closed))
                if ratio < 1.0:
                    trade.shares -= shares_to_sell
                    trade.shares_sold += shares_to_sell
                    trade.partial_taken = True
                    positions[code] = self._lowfreq_trade_to_payload(trade)
                else:
                    positions.pop(code, None)
                target_intent["status"] = "executed"
                target_intent["executed_date"] = execute_date
                target_intent["executed_price"] = float(price)
                target_intent["executed_shares"] = int(shares_to_sell)
                target_intent["executed_at"] = datetime.now(timezone.utc).isoformat()
        else:
            raise ApiError(
                status_code=HTTPStatus.BAD_REQUEST,
                code="invalid_intent_type",
                message="unsupported intent_type",
                details={"intent_type": intent_type},
            )

        state["cash"] = round(cash, 2)
        state["positions"] = positions
        state["closed_trades"] = closed_trades
        state["manual"] = {"intents": intents}
        self._save_lowfreq_sim_state(state)
        return {"_meta": {"status": "ok", "requested_by": requested_by}, "intent": dict(target_intent)}

    def lowfreq_execution_intent_abandon_view(
        self,
        *,
        intent_id: str,
        reason: str = "abandoned",
        requested_by: str = "api",
    ) -> dict[str, Any]:
        intent_id = str(intent_id or "").strip()
        if not intent_id:
            raise ApiError(
                status_code=HTTPStatus.BAD_REQUEST,
                code="invalid_intent_id",
                message="intent_id must be a non-empty string",
            )
        state = self._load_lowfreq_sim_state()
        manual = state.get("manual") if isinstance(state.get("manual"), dict) else {"intents": []}
        intents = manual.get("intents") if isinstance(manual.get("intents"), list) else []
        target_intent: Optional[dict[str, Any]] = None
        for it in intents:
            if isinstance(it, dict) and str(it.get("intent_id") or "").strip() == intent_id:
                target_intent = it
                break
        if target_intent is None:
            raise ApiError(
                status_code=HTTPStatus.NOT_FOUND,
                code="intent_not_found",
                message="intent not found",
                details={"intent_id": intent_id},
            )
        if str(target_intent.get("status") or "pending") == "pending":
            target_intent["status"] = "cancelled"
            target_intent["cancel_reason"] = str(reason or "abandoned")
            target_intent["cancelled_at"] = datetime.now(timezone.utc).isoformat()
        state["manual"] = {"intents": intents}
        self._save_lowfreq_sim_state(state)
        return {"_meta": {"status": "ok", "requested_by": requested_by}, "intent": dict(target_intent)}

    def _lowfreq_portfolio_view(self, *, engine, state: dict[str, Any], target_date: date) -> dict[str, Any]:
        cash = float(state.get("cash") or 0.0)
        initial_capital = float(state.get("initial_capital") or 1_000_000.0)
        positions: dict[str, dict[str, Any]] = state.get("positions", {})
        open_positions: list[dict[str, Any]] = []
        positions_value = 0.0
        sector_name_by_code: dict[str, str] = {}
        codes = [str(code) for code in positions.keys() if str(code).strip()]
        if codes:
            conn = None
            try:
                conn = engine._conn()
                cursor = conn.cursor()
                placeholders = ",".join(["?"] * len(codes))
                cursor.execute(
                    f"SELECT code, sector_lv2 FROM stocks WHERE code IN ({placeholders})",
                    tuple(codes),
                )
                for code, sector_lv2 in cursor.fetchall():
                    code_s = str(code or "").strip()
                    sec_name = str(sector_lv2 or "").strip()
                    if code_s and sec_name:
                        sector_name_by_code[code_s] = sec_name
            except Exception:
                sector_name_by_code = {}
            finally:
                if conn is not None:
                    try:
                        conn.close()
                    except Exception:
                        pass

        for code, trade_payload in positions.items():
            if not isinstance(trade_payload, dict):
                continue
            trade = self._lowfreq_trade_from_payload(trade_payload)
            price = engine._get_price(code, target_date) or trade.buy_price
            price = float(price or 0.0)
            mv = price * trade.shares
            positions_value += mv
            pnl = (price - trade.buy_price) * trade.shares
            pnl_pct = (price - trade.buy_price) / max(trade.buy_price, 1e-9) * 100
            sell = engine.check_sell_signal_v2(trade, target_date)
            trade_payload = self._lowfreq_trade_to_payload(trade)
            positions[code] = trade_payload
            open_positions.append(
                {
                    "code": trade.code,
                    "name": trade.name,
                    "sector": sector_name_by_code.get(str(trade.code)) or trade.sector,
                    "role": trade.role,
                    "buy_date": trade.buy_date,
                    "buy_price": trade.buy_price,
                    "shares": trade.shares,
                    "current_price": round(price, 3),
                    "market_value": round(mv, 2),
                    "unrealized_pnl": round(pnl, 2),
                    "unrealized_pnl_pct": round(pnl_pct, 2),
                    "buy_score": trade.buy_score,
                    "partial_taken": bool(trade.partial_taken),
                    "sell_signal": bool(sell is not None),
                    "sell_reason": (sell.details if sell else None),
                }
            )

        closed_trades_payload: list[dict[str, Any]] = []
        realized_pnl_total = 0.0
        raw_closed_trades = state.get("closed_trades") or []
        if isinstance(raw_closed_trades, list):
            for t in raw_closed_trades:
                if not isinstance(t, dict):
                    continue
                trade = self._lowfreq_trade_from_payload(t)
                shares = int(trade.shares or 0)
                buy_amount = float(trade.buy_price) * float(shares)
                sell_amount = float(trade.sell_price) * float(shares)
                realized_pnl = (float(trade.sell_price) - float(trade.buy_price)) * float(shares)
                realized_pnl_total += realized_pnl
                closed_trades_payload.append(
                    {
                        "code": str(trade.code),
                        "name": str(trade.name),
                        "sector": str(trade.sector),
                        "role": str(trade.role),
                        "buy_date": str(trade.buy_date),
                        "buy_price": float(trade.buy_price),
                        "buy_amount": round(buy_amount, 2),
                        "sell_date": str(trade.sell_date),
                        "sell_price": float(trade.sell_price),
                        "sell_amount": round(sell_amount, 2),
                        "shares": shares,
                        "hold_days": int(trade.hold_days or 0),
                        "return_pct": float(trade.return_pct),
                        "realized_pnl": round(realized_pnl, 2),
                        "sell_reason": str(trade.sell_reason or ""),
                        "status": str(trade.status or ""),
                    }
                )
        closed_trades_payload.sort(key=lambda x: (str(x.get("sell_date") or ""), str(x.get("buy_date") or "")), reverse=True)

        manual_intents_payload: list[dict[str, Any]] = []
        manual = state.get("manual") if isinstance(state.get("manual"), dict) else {"intents": []}
        intents = manual.get("intents") if isinstance(manual.get("intents"), list) else []
        for it in intents[-50:]:
            if isinstance(it, dict):
                manual_intents_payload.append(dict(it))

        total_value = cash + positions_value
        total_return_pct = (total_value - initial_capital) / max(initial_capital, 1e-9) * 100
        return {
            "as_of": target_date.isoformat(),
            "strategy": str(state.get("strategy") or "low_freq_v16_advanced"),
            "initial_capital": round(initial_capital, 2),
            "cash": round(cash, 2),
            "positions_value": round(positions_value, 2),
            "total_value": round(total_value, 2),
            "total_return_pct": round(total_return_pct, 2),
            "open_positions": sorted(open_positions, key=lambda x: x["market_value"], reverse=True),
            "closed_trades_count": len(state.get("closed_trades") or []),
            "closed_trades": closed_trades_payload[:200],
            "realized_pnl_total": round(realized_pnl_total, 2),
            "manual_intents": manual_intents_payload,
            "last_date": state.get("last_date"),
        }

    def lowfreq_hot_sectors_view(
        self,
        *,
        target_date: Optional[str] = None,
        mode: str = "ths_concept",
        include_portfolio: bool = False,
        include_sell_signal: bool = False,
        debug_perf: bool = False,
    ) -> dict[str, Any]:
        if target_date:
            target_dt = date.fromisoformat(str(target_date))
        else:
            target_dt = date.fromisoformat(self._lowfreq_latest_trade_date())

        if mode not in {"ths_concept", "team_theme", "industry"}:
            raise ApiError(
                status_code=HTTPStatus.BAD_REQUEST,
                code="invalid_mode",
                message="mode must be ths_concept, team_theme or industry",
                details={"mode": mode, "supported": ["ths_concept", "team_theme", "industry"]},
            )

        engine = self._lowfreq_engine_v16()
        perf: Optional[dict[str, float]] = {} if debug_perf else None
        t0 = time.perf_counter()
        if mode == "ths_concept":
            payload = self._build_ths_concepts_hot_snapshot(
                engine=engine,
                target_date=target_dt,
                include_portfolio=include_portfolio,
                include_sell_signal=include_sell_signal,
                perf=perf,
            )
        elif mode == "team_theme":
            payload = self._build_team_themes_hot_snapshot(
                engine=engine,
                target_date=target_dt,
                include_portfolio=include_portfolio,
                include_sell_signal=include_sell_signal,
                perf=perf,
            )
        else:
            state = self._load_lowfreq_sim_state()
            payload = self._build_lowfreq_hot_sectors_snapshot(
                engine=engine,
                state=state,
                target_date=target_dt,
                include_portfolio=include_portfolio,
                include_sell_signal=include_sell_signal,
                perf=perf,
            )
            if include_portfolio or include_sell_signal:
                t1 = time.perf_counter()
                self._save_lowfreq_sim_state(state)
                if perf is not None:
                    perf["state_io_ms"] = round((time.perf_counter() - t1) * 1000.0, 3)

        if perf is not None:
            perf["total_ms"] = round((time.perf_counter() - t0) * 1000.0, 3)
            meta = payload.get("_meta") if isinstance(payload, dict) else None
            if not isinstance(meta, dict):
                meta = {"status": "ok"}
            meta = dict(meta)
            meta["perf_ms"] = perf
            meta["include_portfolio"] = bool(include_portfolio)
            meta["include_sell_signal"] = bool(include_sell_signal)
            meta["mode"] = mode
            payload["_meta"] = meta
        return payload

    def _confidence_market_regime(self, *, target_date: date) -> str:
        return "unknown"

    def _confidence_load_calibration_map(
        self, *, conn: sqlite3.Connection, as_of_date: str
    ) -> dict[str, dict[str, Any]]:
        self._ensure_confidence_tables(conn=conn)
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT bucket_key, n, hits, confidence_prob
                FROM confidence_calibration_buckets
                WHERE as_of_date = ?
                """,
                (str(as_of_date),),
            )
        except Exception:
            return {}
        out: dict[str, dict[str, Any]] = {}
        for bucket_key, n, hits, prob in cursor.fetchall():
            key = str(bucket_key or "").strip()
            if not key:
                continue
            out[key] = {
                "bucket_key": key,
                "n": int(n or 0),
                "hits": int(hits or 0),
                "confidence_prob": float(prob or 0.0),
            }
        return out

    def lowfreq_confidence_daily_run_view(
        self,
        *,
        target_date: Optional[str] = None,
        requested_by: str = "api",
        max_label_updates: int = 200,
    ) -> dict[str, Any]:
        if target_date:
            target_dt = date.fromisoformat(str(target_date))
        else:
            target_dt = date.fromisoformat(self._lowfreq_latest_trade_date())

        engine = self._lowfreq_engine_v16()
        market_regime = self._confidence_market_regime(target_date=target_dt)

        snapshot = self.lowfreq_hot_sectors_view(
            target_date=target_dt.isoformat(),
            mode="team_theme",
            include_portfolio=False,
            include_sell_signal=False,
            debug_perf=False,
        )
        sectors = snapshot.get("sectors") if isinstance(snapshot, dict) else None
        sectors = sectors if isinstance(sectors, list) else []

        state = self._load_lowfreq_sim_state()
        positions = state.get("positions") if isinstance(state.get("positions"), dict) else {}

        db_path = Path(
            os.environ.get("NEOTRADE3_STOCK_DB_PATH") or str(self._stock_db_default_path)
        ).expanduser()
        conn = sqlite3.connect(str(db_path))
        try:
            conn.row_factory = sqlite3.Row
            self._ensure_confidence_tables(conn=conn)
            cursor = conn.cursor()
            now_iso = datetime.now(timezone.utc).isoformat()

            obs_rows_written = 0
            obs_codes: set[str] = set()

            def upsert_obs(row: dict[str, Any]) -> None:
                nonlocal obs_rows_written
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO stock_daily_observations (
                      obs_date, code, name, sector, role,
                      raw_score, buy_signal,
                      risk_level, risk_reason,
                      state_label, why,
                      close, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row["obs_date"],
                        row["code"],
                        row["name"],
                        row["sector"],
                        row["role"],
                        row.get("raw_score"),
                        int(bool(row.get("buy_signal"))),
                        row["risk_level"],
                        row.get("risk_reason"),
                        row["state_label"],
                        row.get("why"),
                        row.get("close"),
                        now_iso,
                    ),
                )
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO stock_forward_labels_60d (
                      obs_date, code, label_status, updated_at
                    ) VALUES (?, ?, 'pending', ?)
                    """,
                    (row["obs_date"], row["code"], now_iso),
                )
                obs_rows_written += 1

            for sec in sectors:
                if not isinstance(sec, dict):
                    continue
                sector_name = str(sec.get("sector_lv2") or sec.get("sector_lv1") or "").strip() or "未知板块"
                items = []
                items.extend(sec.get("leaders") or [])
                items.extend(sec.get("middle") or [])
                items.extend(sec.get("followers") or [])
                for s in items:
                    if not isinstance(s, dict):
                        continue
                    code = str(s.get("code") or "").strip()
                    if not code or code in obs_codes:
                        continue
                    obs_codes.add(code)
                    role = str(s.get("role") or "").strip() or "未知"
                    raw_score = s.get("buy_score")
                    buy_signal = bool(s.get("buy_signal"))
                    risk_level = str(s.get("risk_level") or "ok").strip() or "ok"
                    risk_reason = s.get("risk_reason")
                    if risk_level == "exit":
                        state_label = "离场预警"
                        why = str(risk_reason or "").strip() or "离场信号"
                    elif buy_signal:
                        state_label = "接近买点"
                        why = "出现入场信号"
                    else:
                        state_label = "观察"
                        why = None
                    upsert_obs(
                        {
                            "obs_date": target_dt.isoformat(),
                            "code": code,
                            "name": str(s.get("name") or ""),
                            "sector": sector_name,
                            "role": role,
                            "raw_score": float(raw_score) if isinstance(raw_score, (int, float)) else None,
                            "buy_signal": buy_signal,
                            "risk_level": risk_level,
                            "risk_reason": str(risk_reason) if isinstance(risk_reason, str) else None,
                            "state_label": state_label,
                            "why": why,
                            "close": None,
                        }
                    )

            cooldown_cache: dict[str, dict[str, Any]] = {}
            for code, trade_payload in positions.items():
                if not isinstance(trade_payload, dict):
                    continue
                code_s = str(code or "").strip()
                if not code_s or code_s in obs_codes:
                    continue
                obs_codes.add(code_s)
                trade = self._lowfreq_trade_from_payload(trade_payload)
                sell = None
                try:
                    sell = engine.check_sell_signal_v2(trade, target_dt)
                except Exception:
                    sell = None
                sector_name = str(trade.sector or "").strip() or "持仓"
                cooldown_info = cooldown_cache.get(sector_name)
                if cooldown_info is None:
                    try:
                        raw = engine._sector_cooldown_confirmed(sector_name, target_dt)
                        cooldown_info = raw if isinstance(raw, dict) else {}
                    except Exception:
                        cooldown_info = {}
                    cooldown_cache[sector_name] = cooldown_info
                cooldown_confirmed = bool(cooldown_info.get("confirmed")) if isinstance(cooldown_info, dict) else False
                cooldown_hits = 0
                if isinstance(cooldown_info, dict):
                    try:
                        cooldown_hits = int(cooldown_info.get("hits") or 0)
                    except Exception:
                        cooldown_hits = 0
                risk_level = "exit" if (sell is not None or cooldown_confirmed) else "warn" if cooldown_hits > 0 else "ok"
                risk_reason = (sell.details if sell is not None else "冷却确认成立") if (sell is not None or cooldown_confirmed) else "当日命中但未确认" if cooldown_hits > 0 else None
                state_label = "离场预警" if risk_level == "exit" else "持仓"
                why = str(risk_reason or "持仓跟踪")
                upsert_obs(
                    {
                        "obs_date": target_dt.isoformat(),
                        "code": code_s,
                        "name": str(trade.name or ""),
                        "sector": sector_name,
                        "role": str(trade.role or "持仓"),
                        "raw_score": float(trade.buy_score or 0.0),
                        "buy_signal": False,
                        "risk_level": risk_level,
                        "risk_reason": str(risk_reason) if isinstance(risk_reason, str) else None,
                        "state_label": state_label,
                        "why": why,
                        "close": None,
                    }
                )

            conn.commit()

            labels_updated = 0
            cursor.execute(
                """
                SELECT l.obs_date, l.code
                FROM stock_forward_labels_60d l
                WHERE l.label_status = 'pending'
                ORDER BY l.obs_date ASC
                LIMIT ?
                """,
                (int(max_label_updates),),
            )
            pending = [(str(r[0]), str(r[1])) for r in cursor.fetchall() if r and r[0] and r[1]]
            for obs_date, code in pending:
                try:
                    entry_date = self._lowfreq_next_trading_day(obs_date)
                except Exception:
                    continue
                try:
                    entry_dt = date.fromisoformat(entry_date)
                except Exception:
                    continue
                cursor.execute(
                    "SELECT open FROM daily_prices WHERE code = ? AND trade_date = ?",
                    (code, entry_date),
                )
                row = cursor.fetchone()
                if not row or row[0] is None:
                    continue
                entry_price = float(row[0])
                if entry_price <= 0:
                    continue
                cursor.execute(
                    """
                    SELECT high
                    FROM daily_prices
                    WHERE code = ? AND trade_date >= ?
                    ORDER BY trade_date ASC
                    LIMIT 60
                    """,
                    (code, entry_date),
                )
                highs = [float(r[0]) for r in cursor.fetchall() if r and r[0] is not None and float(r[0]) > 0]
                if len(highs) < 60:
                    continue
                max_high = max(highs)
                max_return = (max_high - entry_price) / max(entry_price, 1e-9)
                hit = 1 if max_return >= 0.50 else 0
                cursor.execute(
                    """
                    UPDATE stock_forward_labels_60d
                    SET entry_date = ?, entry_price = ?, max_high_60d = ?, max_return_60d = ?,
                        hit_50pct = ?, label_status = 'ready', label_ready_at = ?, updated_at = ?
                    WHERE obs_date = ? AND code = ?
                    """,
                    (
                        entry_date,
                        float(entry_price),
                        float(max_high),
                        float(max_return),
                        int(hit),
                        now_iso,
                        now_iso,
                        obs_date,
                        code,
                    ),
                )
                labels_updated += 1

            conn.commit()

            cursor.execute("DELETE FROM confidence_calibration_buckets WHERE as_of_date = ?", (target_dt.isoformat(),))
            cursor.execute(
                """
                SELECT o.raw_score, o.role, o.risk_level, l.hit_50pct
                FROM stock_daily_observations o
                JOIN stock_forward_labels_60d l
                  ON o.obs_date = l.obs_date AND o.code = l.code
                WHERE l.label_status = 'ready'
                """,
            )
            bucket_stats: dict[str, dict[str, int]] = {}
            for raw_score, role, risk_level, hit in cursor.fetchall():
                key = self._confidence_bucket_key(
                    raw_score=(float(raw_score) if raw_score is not None else None),
                    role=str(role or ""),
                    risk_level=str(risk_level or ""),
                    market_regime=market_regime,
                )
                stat = bucket_stats.get(key)
                if stat is None:
                    stat = {"n": 0, "hits": 0}
                    bucket_stats[key] = stat
                stat["n"] += 1
                stat["hits"] += int(hit or 0)

            for bucket_key, stat in bucket_stats.items():
                n = int(stat.get("n") or 0)
                hits = int(stat.get("hits") or 0)
                prob = (hits + 1.0) / (n + 2.0) if n > 0 else 0.5
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO confidence_calibration_buckets (
                      as_of_date, bucket_key, n, hits, confidence_prob, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (target_dt.isoformat(), bucket_key, n, hits, float(prob), now_iso),
                )

            conn.commit()

        finally:
            try:
                conn.close()
            except Exception:
                pass

        return {
            "_meta": {"status": "ok", "requested_by": requested_by},
            "date": target_dt.isoformat(),
            "market_regime": market_regime,
            "observations_written": int(obs_rows_written),
            "labels_updated": int(labels_updated),
            "buckets_written": int(len(bucket_stats)),
        }

    def lowfreq_confidence_calibration_overview_view(
        self,
        *,
        target_date: Optional[str] = None,
        requested_by: str = "api",
        limit: int = 50,
    ) -> dict[str, Any]:
        if target_date:
            target_dt = date.fromisoformat(str(target_date))
        else:
            target_dt = date.fromisoformat(self._lowfreq_latest_trade_date())

        db_path = Path(
            os.environ.get("NEOTRADE3_STOCK_DB_PATH") or str(self._stock_db_default_path)
        ).expanduser()
        conn = sqlite3.connect(str(db_path))
        try:
            self._ensure_confidence_tables(conn=conn)
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT bucket_key, n, hits, confidence_prob
                FROM confidence_calibration_buckets
                WHERE as_of_date = ?
                ORDER BY confidence_prob DESC, n DESC
                LIMIT ?
                """,
                (target_dt.isoformat(), int(limit)),
            )
            rows = []
            for r in cursor.fetchall():
                rows.append(
                    {
                        "bucket_key": str(r[0]),
                        "n": int(r[1] or 0),
                        "hits": int(r[2] or 0),
                        "confidence_prob": float(r[3] or 0.0),
                    }
                )
        finally:
            try:
                conn.close()
            except Exception:
                pass

        return {"_meta": {"status": "ok", "requested_by": requested_by}, "date": target_dt.isoformat(), "buckets": rows}

    def lowfreq_confidence_overview_view(
        self,
        *,
        target_date: Optional[str] = None,
        requested_by: str = "api",
        ensure_generated: bool = True,
        lookback_days: int = 7,
    ) -> dict[str, Any]:
        if target_date:
            target_dt = date.fromisoformat(str(target_date))
        else:
            target_dt = date.fromisoformat(self._lowfreq_latest_trade_date())

        if ensure_generated:
            self.lowfreq_confidence_daily_run_view(target_date=target_dt.isoformat(), requested_by=requested_by)

        db_path = Path(
            os.environ.get("NEOTRADE3_STOCK_DB_PATH") or str(self._stock_db_default_path)
        ).expanduser()
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        try:
            self._ensure_confidence_tables(conn=conn)
            calib = self._confidence_load_calibration_map(conn=conn, as_of_date=target_dt.isoformat())
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT obs_date, code, name, sector, role, raw_score, buy_signal, risk_level, risk_reason, state_label, why
                FROM stock_daily_observations
                WHERE obs_date = ?
                ORDER BY sector ASC, role ASC, raw_score DESC
                """,
                (target_dt.isoformat(),),
            )
            rows = cursor.fetchall()

            hist_days = max(1, min(30, int(lookback_days)))
            cursor.execute(
                """
                SELECT DISTINCT obs_date
                FROM stock_daily_observations
                WHERE obs_date <= ?
                ORDER BY obs_date DESC
                LIMIT ?
                """,
                (target_dt.isoformat(), hist_days),
            )
            hist_dates = [str(r[0]) for r in cursor.fetchall() if r and r[0]]
            hist_dates.sort()

            hist_calib: dict[str, dict[str, dict[str, Any]]] = {}
            for d in hist_dates:
                hist_calib[d] = self._confidence_load_calibration_map(conn=conn, as_of_date=d)

            items: list[dict[str, Any]] = []
            for r in rows:
                raw_score = float(r["raw_score"]) if r["raw_score"] is not None else None
                role = str(r["role"] or "")
                risk_level = str(r["risk_level"] or "ok")
                key = self._confidence_bucket_key(
                    raw_score=raw_score,
                    role=role,
                    risk_level=risk_level,
                    market_regime="unknown",
                )
                c = calib.get(key)
                confidence_prob = float(c.get("confidence_prob")) if isinstance(c, dict) else None
                confidence_samples = int(c.get("n")) if isinstance(c, dict) else 0
                history: list[dict[str, Any]] = []
                for d in hist_dates:
                    c2 = hist_calib.get(d, {}).get(key)
                    p2 = float(c2.get("confidence_prob")) if isinstance(c2, dict) else None
                    history.append({"date": d, "confidence_prob": p2})

                items.append(
                    {
                        "obs_date": str(r["obs_date"]),
                        "code": str(r["code"]),
                        "name": str(r["name"] or ""),
                        "sector": str(r["sector"] or ""),
                        "role": role,
                        "confidence_prob": confidence_prob,
                        "confidence_samples": confidence_samples,
                        "state_label": str(r["state_label"] or ""),
                        "why": (str(r["why"]) if r["why"] is not None else None),
                        "risk_level": risk_level,
                        "risk_reason": (str(r["risk_reason"]) if r["risk_reason"] is not None else None),
                        "raw_score": raw_score,
                        "buy_signal": bool(r["buy_signal"] or 0),
                        "history": history,
                    }
                )
        finally:
            try:
                conn.close()
            except Exception:
                pass

        return {
            "_meta": {"status": "ok", "requested_by": requested_by},
            "date": target_dt.isoformat(),
            "items": items,
        }

    def _ensure_ths_concept_daily_tables(self, *, conn: sqlite3.Connection) -> None:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS ths_concept_daily (
              trade_date TEXT NOT NULL,
              concept_code TEXT NOT NULL,
              concept_name TEXT NOT NULL,
              provider TEXT NOT NULL,
              member_count INTEGER NOT NULL,
              valid_count INTEGER NOT NULL,
              avg_pct_change REAL NOT NULL,
              adv_ratio REAL NOT NULL,
              total_amount REAL NOT NULL,
              leader_avg_pct REAL NOT NULL,
              follower_weakness REAL NOT NULL,
              trend_state TEXT NOT NULL,
              risk_level TEXT NOT NULL,
              heat_score REAL NOT NULL,
              heat_rank INTEGER NOT NULL,
              heat_ma20 REAL NOT NULL,
              heat_ma60 REAL NOT NULL,
              heat_ma90 REAL NOT NULL,
              mainline_score REAL NOT NULL,
              mainline_rank INTEGER NOT NULL,
              mainline_streak INTEGER NOT NULL,
              updated_at TEXT NOT NULL,
              PRIMARY KEY (trade_date, concept_code)
            )
            """
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_ths_concept_daily_date_rank ON ths_concept_daily (trade_date, mainline_rank)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_ths_concept_daily_code_date ON ths_concept_daily (concept_code, trade_date)"
        )

    def _ensure_rsi_tables(self, *, conn: sqlite3.Connection) -> None:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS rsi_weekly_operating_points (
              week_end_date TEXT NOT NULL,
              label_return_threshold REAL NOT NULL,
              score_threshold REAL NOT NULL,
              precision REAL NOT NULL,
              coverage REAL NOT NULL,
              n_pred INTEGER NOT NULL,
              n_hit INTEGER NOT NULL,
              n_total INTEGER NOT NULL,
              start_date TEXT NOT NULL,
              end_date TEXT NOT NULL,
              created_at TEXT NOT NULL,
              PRIMARY KEY (week_end_date, label_return_threshold)
            )
            """
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_rsi_weekly_operating_points_date ON rsi_weekly_operating_points (week_end_date)"
        )

    def _ensure_confidence_tables(self, *, conn: sqlite3.Connection) -> None:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS stock_daily_observations (
              obs_date TEXT NOT NULL,
              code TEXT NOT NULL,
              name TEXT NOT NULL,
              sector TEXT NOT NULL,
              role TEXT NOT NULL,
              raw_score REAL,
              buy_signal INTEGER NOT NULL,
              risk_level TEXT NOT NULL,
              risk_reason TEXT,
              state_label TEXT NOT NULL,
              why TEXT,
              close REAL,
              updated_at TEXT NOT NULL,
              PRIMARY KEY (obs_date, code)
            )
            """
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_stock_daily_observations_date_sector ON stock_daily_observations (obs_date, sector)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_stock_daily_observations_date_role ON stock_daily_observations (obs_date, role)"
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS stock_forward_labels_60d (
              obs_date TEXT NOT NULL,
              code TEXT NOT NULL,
              entry_date TEXT,
              entry_price REAL,
              max_high_60d REAL,
              max_return_60d REAL,
              hit_50pct INTEGER,
              label_status TEXT NOT NULL,
              label_ready_at TEXT,
              updated_at TEXT NOT NULL,
              PRIMARY KEY (obs_date, code)
            )
            """
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_stock_forward_labels_60d_status_date ON stock_forward_labels_60d (label_status, obs_date)"
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS confidence_calibration_buckets (
              as_of_date TEXT NOT NULL,
              bucket_key TEXT NOT NULL,
              n INTEGER NOT NULL,
              hits INTEGER NOT NULL,
              confidence_prob REAL NOT NULL,
              updated_at TEXT NOT NULL,
              PRIMARY KEY (as_of_date, bucket_key)
            )
            """
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_confidence_calibration_buckets_date_prob ON confidence_calibration_buckets (as_of_date, confidence_prob)"
        )

    def _confidence_score_bucket(self, raw_score: Optional[float]) -> str:
        if raw_score is None:
            return "score_na"
        try:
            s = float(raw_score)
        except Exception:
            return "score_na"
        b = int(max(0.0, min(200.0, s)) // 10) * 10
        return f"score_{b:03d}_{b+9:03d}"

    def _confidence_bucket_key(self, *, raw_score: Optional[float], role: str, risk_level: str, market_regime: str) -> str:
        role = str(role or "未知").strip() or "未知"
        risk_level = str(risk_level or "ok").strip() or "ok"
        market_regime = str(market_regime or "unknown").strip() or "unknown"
        score_bucket = self._confidence_score_bucket(raw_score)
        return f"{score_bucket}|role:{role}|risk:{risk_level}|regime:{market_regime}"

    def _load_ths_concept_caches(self) -> tuple[dict[str, str], dict[str, list[str]]]:
        concepts_cache_path = self._themes_snapshot_dir / "_tushare_concepts_cache.json"
        members_cache_path = self._themes_snapshot_dir / "_tushare_concept_members_cache.json"

        concept_name_by_code: dict[str, str] = {}
        concept_members: dict[str, list[str]] = {}

        try:
            if concepts_cache_path.exists() and concepts_cache_path.is_file():
                cache_doc = json.loads(concepts_cache_path.read_text(encoding="utf-8"))
            else:
                cache_doc = None
        except (OSError, json.JSONDecodeError):
            cache_doc = None

        provider = cache_doc.get("provider") if isinstance(cache_doc, dict) else None
        if provider not in (None, "ths"):
            cache_doc = None

        items = cache_doc.get("items") if isinstance(cache_doc, dict) else None
        if isinstance(items, list):
            for item in items:
                if not isinstance(item, dict):
                    continue
                code = str(item.get("code") or "").strip()
                name = str(item.get("name") or "").strip()
                if code and name:
                    concept_name_by_code[code] = name

        try:
            if members_cache_path.exists() and members_cache_path.is_file():
                members_doc = json.loads(members_cache_path.read_text(encoding="utf-8"))
            else:
                members_doc = None
        except (OSError, json.JSONDecodeError):
            members_doc = None

        members_provider = members_doc.get("provider") if isinstance(members_doc, dict) else None
        if members_provider not in (None, "ths"):
            members_doc = None

        concepts_map = members_doc.get("concepts") if isinstance(members_doc, dict) else None
        if isinstance(concepts_map, dict):
            for concept_code, entry in concepts_map.items():
                if not isinstance(entry, dict):
                    continue
                stocks = entry.get("stocks")
                if not isinstance(stocks, list):
                    continue
                codes: list[str] = []
                for st in stocks:
                    if not isinstance(st, dict):
                        continue
                    c = str(st.get("code") or "").strip()
                    if c:
                        codes.append(c)
                if codes:
                    concept_members[str(concept_code)] = codes

        return concept_name_by_code, concept_members

    def _recent_trading_dates_from_daily_prices(
        self, *, conn: sqlite3.Connection, end_date: str, limit: int
    ) -> list[str]:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT DISTINCT trade_date FROM daily_prices WHERE trade_date <= ? ORDER BY trade_date DESC LIMIT ?",
            (end_date, int(limit)),
        )
        return [str(r[0]) for r in cursor.fetchall() if r and r[0]]

    def ths_concept_mainline_compute_view(
        self,
        *,
        trade_date: str,
        requested_by: str = "api",
        top_n: int = 10,
        leader_k: int = 5,
    ) -> dict[str, Any]:
        trade_date = str(trade_date or "").strip()
        if not trade_date:
            raise ApiError(
                status_code=HTTPStatus.BAD_REQUEST,
                code="invalid_trade_date",
                message="trade_date must be a non-empty string",
            )

        concept_name_by_code, concept_members = self._load_ths_concept_caches()
        if not concept_members:
            return {
                "_meta": {"status": "ok", "requested_by": requested_by},
                "status": "skipped",
                "reason": "concept_members_cache_empty",
                "trade_date": trade_date,
                "rows_upserted": 0,
            }

        db_path = Path(
            os.environ.get("NEOTRADE3_STOCK_DB_PATH") or str(self._stock_db_default_path)
        ).expanduser()
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        try:
            self._ensure_ths_concept_daily_tables(conn=conn)
            trading_dates_90 = self._recent_trading_dates_from_daily_prices(
                conn=conn, end_date=trade_date, limit=90
            )
            prev_trade_date = trading_dates_90[1] if len(trading_dates_90) >= 2 else None

            base_rows: list[dict[str, Any]] = []
            total_amounts: list[float] = []

            for concept_code, codes in concept_members.items():
                concept_code = str(concept_code or "").strip()
                if not concept_code:
                    continue
                if not isinstance(codes, list) or len(codes) < 3:
                    continue
                placeholders = ",".join(["?"] * len(codes))
                params: list[object] = [trade_date]
                params.extend([str(c) for c in codes])
                try:
                    cursor = conn.cursor()
                    cursor.execute(
                        f"SELECT code, pct_change, amount, close FROM daily_prices WHERE trade_date = ? AND code IN ({placeholders})",
                        tuple(params),
                    )
                    rows = cursor.fetchall()
                except sqlite3.Error:
                    continue

                vals: list[tuple[str, float, float]] = []
                for r in rows:
                    try:
                        close = float(r["close"] or 0.0)
                        if close <= 0:
                            continue
                        pct = float(r["pct_change"] or 0.0)
                        amt = float(r["amount"] or 0.0)
                        vals.append((str(r["code"]), pct, amt))
                    except Exception:
                        continue
                if len(vals) < 3:
                    continue

                pct_list = [v[1] for v in vals]
                avg_pct = float(statistics.mean(pct_list)) if pct_list else 0.0
                adv_ratio = float(sum(1 for p in pct_list if p > 0.0)) / float(len(pct_list))
                total_amount = float(sum(v[2] for v in vals))
                total_amounts.append(total_amount)

                leaders = sorted(pct_list, reverse=True)[: max(1, int(leader_k))]
                leader_avg_1d = float(statistics.mean(leaders)) if leaders else 0.0
                follower_pcts = sorted(pct_list, reverse=True)[max(1, int(leader_k)) :]
                if follower_pcts:
                    follower_weakness_1d = float(
                        sum(1 for p in follower_pcts if p <= 0.0)
                    ) / float(len(follower_pcts))
                else:
                    follower_weakness_1d = 0.0

                base = 50.0
                base += max(-5.0, min(5.0, avg_pct)) * 6.0
                base += max(0.0, min(1.0, adv_ratio)) * 20.0
                base += max(-5.0, min(5.0, leader_avg_1d)) * 4.0
                base -= max(0.0, min(1.0, follower_weakness_1d)) * 20.0
                heat_score = float(max(0.0, min(100.0, base)))

                base_rows.append(
                    {
                        "trade_date": trade_date,
                        "concept_code": concept_code,
                        "concept_name": concept_name_by_code.get(concept_code) or concept_code,
                        "provider": "ths",
                        "member_count": int(len(codes)),
                        "valid_count": int(len(vals)),
                        "avg_pct_change": float(round(avg_pct, 4)),
                        "adv_ratio": float(round(adv_ratio, 6)),
                        "total_amount": float(total_amount),
                        "leader_avg_pct": 0.0,
                        "follower_weakness": 0.0,
                        "trend_state": "unknown",
                        "risk_level": "ok",
                        "heat_score": float(round(heat_score, 4)),
                        "_member_codes": [str(c) for c in codes],
                    }
                )

            if not base_rows:
                return {
                    "_meta": {"status": "ok", "requested_by": requested_by},
                    "status": "skipped",
                    "reason": "no_concepts_with_valid_prices",
                    "trade_date": trade_date,
                    "rows_upserted": 0,
                }

            amount_sorted = sorted(total_amounts)
            amount_min = float(amount_sorted[0])
            amount_max = float(amount_sorted[-1])
            amount_span = max(1e-9, amount_max - amount_min)
            for row in base_rows:
                amt = float(row.get("total_amount") or 0.0)
                pct = (amt - amount_min) / amount_span
                amount_score = float(max(0.0, min(1.0, pct)) * 20.0)
                row["heat_score"] = float(max(0.0, min(100.0, float(row["heat_score"]) + amount_score)))

            by_heat = sorted(base_rows, key=lambda r: float(r.get("heat_score") or 0.0), reverse=True)
            for idx, row in enumerate(by_heat, start=1):
                row["heat_rank"] = int(idx)

            previous_heat_by_code: dict[str, list[tuple[str, float]]] = {}
            if trading_dates_90:
                placeholders = ",".join(["?"] * len(trading_dates_90))
                cursor = conn.cursor()
                cursor.execute(
                    f"SELECT concept_code, trade_date, heat_score FROM ths_concept_daily WHERE trade_date IN ({placeholders}) AND provider = 'ths'",
                    tuple(trading_dates_90),
                )
                for concept_code, d, hs in cursor.fetchall():
                    cc = str(concept_code or "").strip()
                    dd = str(d or "").strip()
                    try:
                        hsf = float(hs or 0.0)
                    except Exception:
                        hsf = 0.0
                    previous_heat_by_code.setdefault(cc, []).append((dd, hsf))

            idx_by_date = {d: i for i, d in enumerate(trading_dates_90)}
            for cc, items in previous_heat_by_code.items():
                items.sort(key=lambda x: idx_by_date.get(x[0], 10_000))
                previous_heat_by_code[cc] = items

            def _ma_for(cc: str, window: int, include_today: float) -> float:
                arr = [x[1] for x in previous_heat_by_code.get(cc, [])[: max(0, int(window) - 1)]]
                arr.insert(0, float(include_today))
                if not arr:
                    return 0.0
                return float(statistics.mean(arr))

            for row in base_rows:
                cc = str(row.get("concept_code") or "")
                hs = float(row.get("heat_score") or 0.0)
                row["heat_ma20"] = float(round(_ma_for(cc, 20, hs), 4))
                row["heat_ma60"] = float(round(_ma_for(cc, 60, hs), 4))
                row["heat_ma90"] = float(round(_ma_for(cc, 90, hs), 4))
                row["mainline_score"] = float(
                    round(
                        hs
                        + 0.6 * float(row["heat_ma20"])
                        + 0.3 * float(row["heat_ma60"])
                        + 0.1 * float(row["heat_ma90"]),
                        4,
                    )
                )

            by_mainline = sorted(
                base_rows, key=lambda r: float(r.get("mainline_score") or 0.0), reverse=True
            )
            for idx, row in enumerate(by_mainline, start=1):
                row["mainline_rank"] = int(idx)

            engine = self._lowfreq_engine_v16()
            confirm_window = int(getattr(engine, "SECTOR_COOLDOWN_CONFIRM_WINDOW", 3) or 3)
            confirm_hits = int(getattr(engine, "SECTOR_COOLDOWN_CONFIRM_HITS", 2) or 2)
            tail_dates = trading_dates_90[: max(0, confirm_window)]
            if not tail_dates or tail_dates[0] != trade_date:
                tail_dates = [trade_date]

            all_codes: list[str] = []
            for row in base_rows:
                codes = row.get("_member_codes")
                if isinstance(codes, list):
                    for c in codes:
                        cs = str(c or "").strip()
                        if cs:
                            all_codes.append(cs)
            uniq_codes = sorted(set(all_codes))

            def _fetch_ret5_by_code(*, as_of: str) -> dict[str, float]:
                if not uniq_codes:
                    return {}
                out: dict[str, float] = {}
                cursor = conn.cursor()
                step = 800
                for i in range(0, len(uniq_codes), step):
                    chunk = uniq_codes[i : i + step]
                    placeholders = ",".join(["?"] * len(chunk))
                    cursor.execute(
                        f"""
                        SELECT code, close, rn FROM (
                          SELECT code, close,
                                 row_number() OVER (PARTITION BY code ORDER BY trade_date DESC) as rn
                          FROM daily_prices
                          WHERE trade_date <= ?
                            AND code IN ({placeholders})
                        )
                        WHERE rn <= 5
                        ORDER BY code, rn
                        """,
                        tuple([as_of] + chunk),
                    )
                    closes_by_code: dict[str, list[float]] = {}
                    for r in cursor.fetchall():
                        code = str(r[0] or "").strip()
                        if not code:
                            continue
                        close = r[1]
                        if close is None:
                            continue
                        lst = closes_by_code.get(code)
                        if lst is None:
                            lst = []
                            closes_by_code[code] = lst
                        if len(lst) >= 5:
                            continue
                        lst.append(float(close))
                    for code, closes in closes_by_code.items():
                        if len(closes) < 5:
                            continue
                        close_0 = float(closes[0])
                        close_5 = float(closes[4])
                        if close_5 <= 0:
                            continue
                        out[code] = (close_0 - close_5) / close_5 * 100.0
                return out

            ret5_by_date: dict[str, dict[str, float]] = {}
            for d in tail_dates:
                ret5_by_date[d] = _fetch_ret5_by_code(as_of=d)

            def _cooldown_info(*, member_codes: list[str], as_of: str) -> dict[str, Any]:
                ret5_map = ret5_by_date.get(as_of) or {}
                returns: list[float] = []
                for c in member_codes:
                    v = ret5_map.get(str(c))
                    if v is None:
                        continue
                    returns.append(float(v))
                if len(returns) < 10:
                    return {
                        "cooldown_detected": False,
                        "follower_weakness": 0.0,
                        "leader_strength": 0.5,
                        "trend_state": "unknown",
                        "leader_avg": 0.0,
                        "follower_avg": 0.0,
                    }
                returns.sort(reverse=True)
                n = len(returns)
                leaders = returns[: max(1, n // 5)]
                followers = returns[max(1, n // 2) :]
                leader_avg = float(statistics.mean(leaders)) if leaders else 0.0
                follower_avg = float(statistics.mean(followers)) if followers else 0.0
                leader_strength = min(1.0, max(0.0, (leader_avg + 10.0) / 30.0))
                follower_weakness = min(1.0, max(0.0, (5.0 - follower_avg) / 15.0))
                if leader_avg > 15.0 and follower_avg > 5.0:
                    trend_state = "rising"
                elif leader_avg < 5.0 and follower_avg < -5.0:
                    trend_state = "falling"
                elif follower_avg < -3.0 and leader_avg > 10.0:
                    trend_state = "diverging"
                else:
                    trend_state = "consolidating"
                cooldown_detected = bool(follower_weakness > 0.6 and leader_strength > 0.5)
                return {
                    "cooldown_detected": cooldown_detected,
                    "follower_weakness": float(follower_weakness),
                    "leader_strength": float(leader_strength),
                    "trend_state": str(trend_state),
                    "leader_avg": float(leader_avg),
                    "follower_avg": float(follower_avg),
                }

            def _is_hit(info: dict[str, Any]) -> bool:
                return bool(
                    info.get("cooldown_detected")
                    and float(info.get("follower_weakness") or 0.0) > 0.6
                    and str(info.get("trend_state") or "") in {"diverging", "falling"}
                )

            for row in base_rows:
                member_codes = row.get("_member_codes") if isinstance(row.get("_member_codes"), list) else []
                hits = 0
                checked = 0
                latest_info: dict[str, Any] = {}
                for d in tail_dates:
                    info = _cooldown_info(member_codes=member_codes, as_of=d)
                    latest_info = info
                    checked += 1
                    if _is_hit(info):
                        hits += 1
                confirmed = bool(checked > 0 and hits >= confirm_hits)
                today_info = _cooldown_info(member_codes=member_codes, as_of=trade_date)
                today_hit = _is_hit(today_info)
                if confirmed:
                    risk_level = "exit"
                elif today_hit:
                    risk_level = "warn"
                else:
                    risk_level = "ok"
                row["risk_level"] = risk_level
                row["trend_state"] = str(today_info.get("trend_state") or "unknown")
                row["follower_weakness"] = float(round(float(today_info.get("follower_weakness") or 0.0), 6))
                row["leader_avg_pct"] = float(round(float(today_info.get("leader_avg") or 0.0), 4))

            prev_streak_by_code: dict[str, int] = {}
            if prev_trade_date:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT concept_code, mainline_streak FROM ths_concept_daily WHERE trade_date = ? AND provider = 'ths'",
                    (prev_trade_date,),
                )
                for cc, st in cursor.fetchall():
                    try:
                        prev_streak_by_code[str(cc)] = int(st or 0)
                    except Exception:
                        prev_streak_by_code[str(cc)] = 0

            for row in base_rows:
                cc = str(row.get("concept_code") or "")
                rank = int(row.get("mainline_rank") or 10_000)
                if rank <= int(top_n):
                    row["mainline_streak"] = int(prev_streak_by_code.get(cc, 0) + 1)
                else:
                    row["mainline_streak"] = 0

            now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            cursor = conn.cursor()
            cursor.execute("BEGIN")
            cursor.execute(
                "DELETE FROM ths_concept_daily WHERE trade_date = ? AND provider = 'ths'",
                (trade_date,),
            )
            for row in base_rows:
                cursor.execute(
                    """
                    INSERT INTO ths_concept_daily (
                      trade_date, concept_code, concept_name, provider,
                      member_count, valid_count, avg_pct_change, adv_ratio, total_amount,
                      leader_avg_pct, follower_weakness, trend_state, risk_level,
                      heat_score, heat_rank, heat_ma20, heat_ma60, heat_ma90,
                      mainline_score, mainline_rank, mainline_streak, updated_at
                    ) VALUES (
                      ?, ?, ?, ?,
                      ?, ?, ?, ?, ?,
                      ?, ?, ?, ?,
                      ?, ?, ?, ?, ?,
                      ?, ?, ?, ?
                    )
                    """,
                    (
                        row["trade_date"],
                        row["concept_code"],
                        row["concept_name"],
                        row["provider"],
                        int(row["member_count"]),
                        int(row["valid_count"]),
                        float(row["avg_pct_change"]),
                        float(row["adv_ratio"]),
                        float(row["total_amount"]),
                        float(row["leader_avg_pct"]),
                        float(row["follower_weakness"]),
                        str(row["trend_state"]),
                        str(row["risk_level"]),
                        float(row["heat_score"]),
                        int(row["heat_rank"]),
                        float(row["heat_ma20"]),
                        float(row["heat_ma60"]),
                        float(row["heat_ma90"]),
                        float(row["mainline_score"]),
                        int(row["mainline_rank"]),
                        int(row["mainline_streak"]),
                        now,
                    ),
                )
            cursor.execute("COMMIT")

            return {
                "_meta": {"status": "ok", "requested_by": requested_by},
                "status": "ok",
                "trade_date": trade_date,
                "concept_count": len(base_rows),
                "top_mainline": [
                    {
                        "concept_code": r["concept_code"],
                        "concept_name": r["concept_name"],
                        "mainline_rank": r["mainline_rank"],
                        "mainline_score": r["mainline_score"],
                        "risk_level": r["risk_level"],
                    }
                    for r in sorted(base_rows, key=lambda x: int(x["mainline_rank"]))[: int(top_n)]
                ],
            }
        finally:
            conn.close()

    def ths_concept_mainline_view(
        self,
        *,
        trade_date: Optional[str],
        limit: int = 10,
        requested_by: str = "api",
    ) -> dict[str, Any]:
        d = str(trade_date or "").strip()
        if not d:
            d = self._lowfreq_latest_trade_date()
        limit = max(1, int(limit))

        db_path = Path(
            os.environ.get("NEOTRADE3_STOCK_DB_PATH") or str(self._stock_db_default_path)
        ).expanduser()
        with sqlite3.connect(str(db_path)) as conn:
            self._ensure_ths_concept_daily_tables(conn=conn)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM ths_concept_daily WHERE trade_date = ? AND provider = 'ths'",
                (d,),
            )
            total = int(cursor.fetchone()[0] or 0)
            cursor.execute(
                """
                SELECT COUNT(*) FROM ths_concept_daily
                WHERE trade_date = ? AND provider = 'ths'
                  AND risk_level IN ('ok', 'warn', 'exit')
                  AND trend_state IN ('rising', 'falling', 'diverging', 'consolidating', 'unknown')
                """,
                (d,),
            )
            compatible = int(cursor.fetchone()[0] or 0)
            exists = total > 0
            needs_recompute = bool(exists and compatible != total)
        if (not exists) or needs_recompute:
            self.ths_concept_mainline_compute_view(
                trade_date=d, requested_by=requested_by, top_n=10
            )

        with sqlite3.connect(str(db_path)) as conn:
            conn.row_factory = sqlite3.Row
            self._ensure_ths_concept_daily_tables(conn=conn)
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                  trade_date, concept_code, concept_name,
                  mainline_rank, mainline_score, mainline_streak,
                  heat_score, heat_rank, heat_ma20, heat_ma60, heat_ma90,
                  risk_level, trend_state, follower_weakness, leader_avg_pct,
                  member_count, valid_count
                FROM ths_concept_daily
                WHERE trade_date = ? AND provider = 'ths'
                ORDER BY mainline_rank ASC
                LIMIT ?
                """,
                (d, int(limit)),
            )
            rows = cursor.fetchall()
        out = []
        for r in rows:
            out.append({k: r[k] for k in r.keys()})
        return {"_meta": {"status": "ok", "requested_by": requested_by}, "date": d, "concepts": out}

    def ths_concept_mainline_detail_view(
        self,
        *,
        trade_date: Optional[str],
        concept_code: str,
        requested_by: str = "api",
        leaders: int = 3,
        middle: int = 5,
        followers: int = 7,
    ) -> dict[str, Any]:
        d = str(trade_date or "").strip()
        if not d:
            d = self._lowfreq_latest_trade_date()
        concept_code = str(concept_code or "").strip()
        if not concept_code:
            raise ApiError(
                status_code=HTTPStatus.BAD_REQUEST,
                code="invalid_concept_code",
                message="concept_code must be a non-empty string",
            )

        concept_name_by_code, concept_members = self._load_ths_concept_caches()
        members = concept_members.get(concept_code) or []
        if not members:
            raise ApiError(
                status_code=HTTPStatus.NOT_FOUND,
                code="concept_members_missing",
                message="concept members not cached",
                details={"concept_code": concept_code},
            )

        db_path = Path(
            os.environ.get("NEOTRADE3_STOCK_DB_PATH") or str(self._stock_db_default_path)
        ).expanduser()
        with sqlite3.connect(str(db_path)) as conn:
            conn.row_factory = sqlite3.Row
            self._ensure_ths_concept_daily_tables(conn=conn)
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                  trade_date, concept_code, concept_name,
                  mainline_rank, mainline_score, mainline_streak,
                  heat_score, heat_rank, heat_ma20, heat_ma60, heat_ma90,
                  risk_level, trend_state, follower_weakness, leader_avg_pct,
                  member_count, valid_count, avg_pct_change, adv_ratio, total_amount
                FROM ths_concept_daily
                WHERE trade_date = ? AND concept_code = ? AND provider = 'ths'
                """,
                (d, concept_code),
            )
            row = cursor.fetchone()
            summary = {k: row[k] for k in row.keys()} if row else None

            placeholders = ",".join(["?"] * len(members))
            params: list[object] = [d]
            params.extend([str(c) for c in members])
            cursor.execute(
                f"SELECT code, close, pct_change, amount FROM daily_prices WHERE trade_date = ? AND code IN ({placeholders})",
                tuple(params),
            )
            pr = []
            for r in cursor.fetchall():
                try:
                    close = float(r["close"] or 0.0)
                    if close <= 0:
                        continue
                    pr.append(
                        {
                            "code": str(r["code"]),
                            "name": "",
                            "pct_change": float(r["pct_change"] or 0.0),
                            "amount": float(r["amount"] or 0.0),
                        }
                    )
                except Exception:
                    continue

            placeholders = ",".join(["?"] * len(pr)) if pr else ""
            if pr:
                codes = [p["code"] for p in pr]
                cursor.execute(
                    f"SELECT code, name FROM stocks WHERE code IN ({','.join(['?']*len(codes))})",
                    tuple(codes),
                )
                name_map = {str(c): str(n or "") for c, n in cursor.fetchall()}
                for p in pr:
                    p["name"] = name_map.get(p["code"], "")

        pr.sort(key=lambda x: float(x.get("pct_change") or 0.0), reverse=True)
        leaders_list = [dict(x, role="龙头") for x in pr[: max(0, int(leaders))]]
        middle_list = [
            dict(x, role="中军")
            for x in pr[max(0, int(leaders)) : max(0, int(leaders)) + max(0, int(middle))]
        ]
        followers_list = [
            dict(x, role="跟随")
            for x in pr[
                max(0, int(leaders)) + max(0, int(middle)) : max(0, int(leaders))
                + max(0, int(middle))
                + max(0, int(followers))
            ]
        ]
        return {
            "_meta": {"status": "ok", "requested_by": requested_by},
            "date": d,
            "concept": {
                "concept_code": concept_code,
                "concept_name": concept_name_by_code.get(concept_code) or concept_code,
                "summary": summary,
            },
            "leaders": leaders_list,
            "middle": middle_list,
            "followers": followers_list,
        }

    def lowfreq_rsi_regression_view(
        self,
        *,
        target_date: Optional[str] = None,
        weeks: int = 12,
        label_return_threshold: float = 0.30,
        precision_floor: float = 0.85,
    ) -> dict[str, Any]:
        if target_date:
            end_date = str(target_date).strip()
        else:
            end_date = self._lowfreq_latest_trade_date()
        try:
            date.fromisoformat(end_date)
        except ValueError:
            raise ApiError(
                status_code=HTTPStatus.BAD_REQUEST,
                code="invalid_date",
                message=f"invalid date: {end_date}",
                details={"date": end_date},
            )

        weeks = max(1, int(weeks))
        label_return_threshold = float(label_return_threshold)
        precision_floor = float(precision_floor)

        window_len = max(20, weeks * 5)
        start_date = self._rolling_window_start_date(end_date=end_date, window_len=int(window_len))

        db_path = Path(
            os.environ.get("NEOTRADE3_STOCK_DB_PATH") or str(self._stock_db_default_path)
        ).expanduser()

        def compute_for_thresholds(conn: sqlite3.Connection, thresholds: list[float]) -> list[dict[str, Any]]:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM stock_daily_observations o
                JOIN stock_forward_labels_60d l
                  ON o.obs_date = l.obs_date AND o.code = l.code
                WHERE o.obs_date BETWEEN ? AND ?
                  AND l.label_status = 'ready'
                  AND l.max_return_60d IS NOT NULL
                  AND o.raw_score IS NOT NULL
                  AND o.role IN ('龙头', '中军')
                  AND o.risk_level != 'exit'
                """,
                (start_date, end_date),
            )
            n_total = int(cursor.fetchone()[0] or 0)

            out: list[dict[str, Any]] = []
            if n_total <= 0:
                for t in thresholds:
                    out.append(
                        {
                            "score_threshold": float(t),
                            "precision": None,
                            "coverage": 0.0,
                            "n_pred": 0,
                            "n_hit": 0,
                            "n_total": 0,
                        }
                    )
                return out

            for t in thresholds:
                cursor.execute(
                    """
                    SELECT
                      SUM(CASE WHEN o.raw_score >= ? THEN 1 ELSE 0 END) AS n_pred,
                      SUM(CASE WHEN o.raw_score >= ? AND l.max_return_60d >= ? THEN 1 ELSE 0 END) AS n_hit
                    FROM stock_daily_observations o
                    JOIN stock_forward_labels_60d l
                      ON o.obs_date = l.obs_date AND o.code = l.code
                    WHERE o.obs_date BETWEEN ? AND ?
                      AND l.label_status = 'ready'
                      AND l.max_return_60d IS NOT NULL
                      AND o.raw_score IS NOT NULL
                      AND o.role IN ('龙头', '中军')
                      AND o.risk_level != 'exit'
                    """,
                    (float(t), float(t), float(label_return_threshold), start_date, end_date),
                )
                row = cursor.fetchone()
                n_pred = int(row[0] or 0) if row else 0
                n_hit = int(row[1] or 0) if row else 0
                precision = (float(n_hit) / float(n_pred)) if n_pred > 0 else None
                coverage = float(n_pred) / float(max(1, n_total))
                out.append(
                    {
                        "score_threshold": float(t),
                        "precision": float(round(precision, 6)) if precision is not None else None,
                        "coverage": float(round(coverage, 6)),
                        "n_pred": int(n_pred),
                        "n_hit": int(n_hit),
                        "n_total": int(n_total),
                    }
                )
            return out

        thresholds = [float(x) for x in range(60, 131, 5)]
        engine = self._lowfreq_engine_v16()
        engine_threshold = float(getattr(engine, "BUY_THRESHOLD", 0.0) or 0.0)
        if engine_threshold not in thresholds:
            thresholds.append(engine_threshold)
            thresholds = sorted(set(thresholds))

        with sqlite3.connect(str(db_path)) as conn:
            self._ensure_confidence_tables(conn=conn)
            self._ensure_rsi_tables(conn=conn)
            curve = compute_for_thresholds(conn, thresholds)

            operating = None
            for row in curve:
                p = row.get("precision")
                if not isinstance(p, (int, float)) or float(p) < precision_floor:
                    continue
                if operating is None or float(row.get("coverage") or 0.0) > float(operating.get("coverage") or 0.0):
                    operating = row

            engine_row = None
            for row in curve:
                if float(row.get("score_threshold") or 0.0) == float(engine_threshold):
                    engine_row = row
                    break

            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT week_end_date, score_threshold, precision, coverage, n_pred, n_hit, n_total
                FROM rsi_weekly_operating_points
                WHERE label_return_threshold = ?
                  AND week_end_date <= ?
                ORDER BY week_end_date DESC
                LIMIT ?
                """,
                (float(label_return_threshold), end_date, int(weeks)),
            )
            baseline_rows = [
                {
                    "week_end_date": str(r[0]),
                    "score_threshold": float(r[1]),
                    "precision": float(r[2]),
                    "coverage": float(r[3]),
                    "n_pred": int(r[4]),
                    "n_hit": int(r[5]),
                    "n_total": int(r[6]),
                }
                for r in cursor.fetchall()
                if r and r[0]
            ]

        covs = [float(r["coverage"]) for r in baseline_rows if isinstance(r.get("coverage"), (int, float))]
        covs_sorted = sorted(covs)
        p25 = None
        if covs_sorted:
            idx = int((len(covs_sorted) - 1) * 0.25)
            p25 = float(covs_sorted[max(0, min(idx, len(covs_sorted) - 1))])

        regression_flag = None
        if p25 is not None and operating is not None:
            regression_flag = bool(float(operating.get("coverage") or 0.0) < float(p25))

        return {
            "_meta": {"status": "ok"},
            "window": {
                "weeks": int(weeks),
                "start_date": str(start_date),
                "end_date": str(end_date),
                "label_return_threshold": float(label_return_threshold),
                "precision_floor": float(precision_floor),
            },
            "engine_threshold": float(engine_threshold),
            "engine_point": engine_row,
            "operating_point": operating,
            "baseline": {
                "weeks": int(weeks),
                "points": baseline_rows[::-1],
                "coverage_p25": float(p25) if p25 is not None else None,
                "coverage_regressed": regression_flag,
            },
            "curve": curve,
        }

    def lowfreq_rsi_weekly_record_view(
        self,
        *,
        target_date: Optional[str] = None,
        weeks: int = 12,
        label_return_threshold: float = 0.30,
        precision_floor: float = 0.85,
        requested_by: str = "api",
    ) -> dict[str, Any]:
        out = self.lowfreq_rsi_regression_view(
            target_date=target_date,
            weeks=weeks,
            label_return_threshold=label_return_threshold,
            precision_floor=precision_floor,
        )
        week_end_date = str(out.get("window", {}).get("end_date") or "").strip()
        operating = out.get("operating_point")
        if not isinstance(operating, dict):
            raise ApiError(
                status_code=HTTPStatus.SERVICE_UNAVAILABLE,
                code="operating_point_unavailable",
                message="no operating point found under precision_floor",
                details={"precision_floor": precision_floor, "label_return_threshold": label_return_threshold},
            )

        created_at = datetime.now(timezone.utc).isoformat()
        db_path = Path(
            os.environ.get("NEOTRADE3_STOCK_DB_PATH") or str(self._stock_db_default_path)
        ).expanduser()
        with sqlite3.connect(str(db_path)) as conn:
            self._ensure_rsi_tables(conn=conn)
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO rsi_weekly_operating_points (
                  week_end_date, label_return_threshold,
                  score_threshold, precision, coverage,
                  n_pred, n_hit, n_total,
                  start_date, end_date, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    week_end_date,
                    float(label_return_threshold),
                    float(operating.get("score_threshold") or 0.0),
                    float(operating.get("precision") or 0.0),
                    float(operating.get("coverage") or 0.0),
                    int(operating.get("n_pred") or 0),
                    int(operating.get("n_hit") or 0),
                    int(operating.get("n_total") or 0),
                    str(out.get("window", {}).get("start_date") or ""),
                    str(out.get("window", {}).get("end_date") or ""),
                    created_at,
                ),
            )
            conn.commit()

        return {
            "_meta": {"status": "ok"},
            "requested_by": str(requested_by or "api"),
            "recorded": {
                "week_end_date": week_end_date,
                "label_return_threshold": float(label_return_threshold),
                "operating_point": operating,
                "created_at": created_at,
            },
            "regression": out,
        }

    def lowfreq_portfolio_view(
        self,
        *,
        target_date: Optional[str] = None,
        requested_by: str = "api",
    ) -> dict[str, Any]:
        if target_date:
            target_dt = date.fromisoformat(str(target_date))
        else:
            target_dt = date.fromisoformat(self._lowfreq_latest_trade_date())

        engine = self._lowfreq_engine_v16()
        state = self._load_lowfreq_sim_state()
        portfolio = self._lowfreq_portfolio_view(engine=engine, state=state, target_date=target_dt)
        self._save_lowfreq_sim_state(state)
        return {"_meta": {"status": "ok", "requested_by": requested_by}, "portfolio": portfolio}

    def lowfreq_sim_run_view(
        self, *, target_date: Optional[str] = None, requested_by: str = "api"
    ) -> dict[str, Any]:
        if target_date:
            target_dt = date.fromisoformat(str(target_date))
        else:
            target_dt = date.fromisoformat(self._lowfreq_latest_trade_date())

        engine = self._lowfreq_engine_v16()
        state = self._load_lowfreq_sim_state()
        self._advance_lowfreq_sim_state(state=state, engine=engine, target_date=target_dt)
        payload = self._build_lowfreq_hot_sectors_snapshot(
            engine=engine, state=state, target_date=target_dt
        )
        payload["_meta"] = {
            "status": "ok",
            "requested_by": requested_by,
            "model": "lowfreq_engine_v16_advanced",
        }
        self._save_lowfreq_sim_state(state)
        return payload

    def _lowfreq_backtest_with_trades(
        self,
        *,
        engine,
        start_date: date,
        end_date: date,
        initial_capital: float = 1_000_000.0,
    ) -> tuple[dict[str, Any], list[Any]]:
        from lowfreq_engine_v16_advanced import TradeRecord

        trading_dates = engine._get_trading_dates(start_date, end_date)
        capital = float(initial_capital)
        positions: dict[str, TradeRecord] = {}
        all_trades: list[TradeRecord] = []
        daily_values: list[dict[str, Any]] = []

        pending_buy_attempts: dict[str, dict[str, Any]] = {}
        pending_sell_signals: dict[str, dict[str, Any]] = {}

        conn = None
        try:
            conn = engine._conn()
            cursor = conn.cursor()
            name_cache: dict[str, str] = {}
            limit_cache: dict[str, float] = {}
            pct_cache: dict[tuple[str, str], float] = {}

            def _stock_name(code: str) -> str:
                code = str(code or "").strip()
                if code in name_cache:
                    return name_cache[code]
                try:
                    cursor.execute("SELECT name FROM stocks WHERE code = ?", (code,))
                    row = cursor.fetchone()
                    name = str(row[0]) if row and row[0] else ""
                except Exception:
                    name = ""
                name_cache[code] = name
                return name

            def _limit_pct(code: str) -> float:
                code = str(code or "").strip()
                if code in limit_cache:
                    return limit_cache[code]
                name = _stock_name(code)
                if "ST" in name.upper():
                    limit = 4.8
                elif code.startswith("688") or code.startswith("300"):
                    limit = 19.8
                else:
                    limit = 9.8
                limit_cache[code] = float(limit)
                return float(limit)

            def _pct_change(code: str, d: date) -> Optional[float]:
                key = (str(code or "").strip(), d.isoformat())
                if key in pct_cache:
                    return pct_cache[key]
                try:
                    cursor.execute(
                        "SELECT pct_change FROM daily_prices WHERE code = ? AND trade_date = ?",
                        (key[0], key[1]),
                    )
                    row = cursor.fetchone()
                    if row and row[0] is not None:
                        val = float(row[0])
                        pct_cache[key] = val
                        return val
                except Exception:
                    return None
                return None

            def _is_limit_up(code: str, d: date) -> bool:
                pct = _pct_change(code, d)
                if pct is None:
                    return False
                return float(pct) >= float(_limit_pct(code))

            def _is_limit_down(code: str, d: date) -> bool:
                pct = _pct_change(code, d)
                if pct is None:
                    return False
                return float(pct) <= -float(_limit_pct(code))

            def _close_trade(*, code: str, trade: TradeRecord, d: date, sell_reason: str) -> None:
                nonlocal capital
                sell_price = engine._get_price(code, d)
                if not sell_price:
                    return
                ret = (float(sell_price) - trade.buy_price) / max(trade.buy_price, 1e-9) * 100.0
                capital += float(sell_price) * trade.shares
                trade.sell_date = d.isoformat()
                trade.sell_price = float(sell_price)
                trade.return_pct = round(ret, 2)
                trade.hold_days = engine._count_trading_days(date.fromisoformat(trade.buy_date), d)
                trade.sell_reason = sell_reason
                trade.status = "closed"
                all_trades.append(trade)
                positions.pop(code, None)

            for i, current_date in enumerate(trading_dates):
                # 1) 先处理待卖出（跌停卖不出则继续等待）
                for code, payload in list(pending_sell_signals.items()):
                    if code not in positions:
                        pending_sell_signals.pop(code, None)
                        continue
                    if _is_limit_down(code, current_date):
                        continue
                    trade = positions.get(code)
                    if trade is None:
                        pending_sell_signals.pop(code, None)
                        continue
                    first_date = str(payload.get("first_date") or "")
                    details = str(payload.get("details") or "离场信号")
                    reason = f"{details}（跌停顺延，自{first_date}）" if first_date else f"{details}（跌停顺延）"
                    _close_trade(code=code, trade=trade, d=current_date, sell_reason=reason)
                    pending_sell_signals.pop(code, None)

                # 2) 评估当日离场信号（若跌停则挂起到待卖出）
                for code, trade in list(positions.items()):
                    if code in pending_sell_signals:
                        continue
                    sell = engine.check_sell_signal_v2(trade, current_date)
                    if not sell:
                        continue
                    if _is_limit_down(code, current_date):
                        pending_sell_signals[code] = {
                            "first_date": current_date.isoformat(),
                            "details": str(sell.details or "离场信号"),
                        }
                        continue
                    _close_trade(code=code, trade=trade, d=current_date, sell_reason=str(sell.details))

                # 3) 处理待买入（涨停买不进则继续等待；最多尝试 3 个交易日）
                for code, payload in list(pending_buy_attempts.items()):
                    if code in positions:
                        pending_buy_attempts.pop(code, None)
                        continue
                    slots = int(engine.MAX_POSITIONS) - len(positions)
                    if slots <= 0:
                        continue

                    remaining = int(payload.get("remaining") or 0)
                    if remaining <= 0:
                        pending_buy_attempts.pop(code, None)
                        continue
                    if _is_limit_up(code, current_date):
                        payload["remaining"] = remaining - 1
                        if int(payload.get("remaining") or 0) <= 0:
                            pending_buy_attempts.pop(code, None)
                        continue

                    sig = payload.get("sig") if isinstance(payload.get("sig"), dict) else {}
                    price = engine._get_price(code, current_date)
                    if not price or float(price) <= 0:
                        payload["remaining"] = remaining - 1
                        if int(payload.get("remaining") or 0) <= 0:
                            pending_buy_attempts.pop(code, None)
                        continue

                    per_slot = capital / max(slots, 1)
                    shares = int(per_slot / float(price) / 100) * 100
                    if shares >= 100 and shares * float(price) <= capital:
                        capital -= shares * float(price)
                        positions[code] = TradeRecord(
                            code=code,
                            name=str(sig.get("name") or ""),
                            sector=str(sig.get("sector") or ""),
                            buy_date=current_date.isoformat(),
                            buy_price=float(price),
                            shares=shares,
                            buy_score=float(sig.get("buy_score") or 0.0),
                            wave_phase=str(sig.get("wave_phase") or ""),
                            peak_price=float(price),
                            role=str(sig.get("role") or ""),
                            status="open",
                        )
                        pending_buy_attempts.pop(code, None)
                    else:
                        payload["remaining"] = remaining - 1
                        if int(payload.get("remaining") or 0) <= 0:
                            pending_buy_attempts.pop(code, None)

                # 4) 调仓日生成买入信号（涨停则进入待买入队列）
                if i % int(engine.REBALANCE_DAYS) == 0 and len(positions) < int(engine.MAX_POSITIONS):
                    signals = engine.generate_buy_signals(current_date)
                    for sig in signals.get("buy_signals", []):
                        if not isinstance(sig, dict):
                            continue
                        code = str(sig.get("code") or "").strip()
                        if not code or code in positions or code in pending_buy_attempts:
                            continue
                        slots = int(engine.MAX_POSITIONS) - len(positions)
                        if slots <= 0:
                            break
                        if _is_limit_up(code, current_date):
                            pending_buy_attempts[code] = {
                                "sig": sig,
                                "first_date": current_date.isoformat(),
                                "remaining": 3,
                            }
                            continue
                        price = engine._get_price(code, current_date)
                        if not price or float(price) <= 0:
                            continue
                        per_slot = capital / max(slots, 1)
                        shares = int(per_slot / float(price) / 100) * 100
                        if shares >= 100 and shares * float(price) <= capital:
                            capital -= shares * float(price)
                            positions[code] = TradeRecord(
                                code=code,
                                name=str(sig.get("name") or ""),
                                sector=str(sig.get("sector") or ""),
                                buy_date=current_date.isoformat(),
                                buy_price=float(price),
                                shares=shares,
                                buy_score=float(sig.get("buy_score") or 0.0),
                                wave_phase=str(sig.get("wave_phase") or ""),
                                peak_price=float(price),
                                role=str(sig.get("role") or ""),
                                status="open",
                            )
                pos_value = sum(
                    (engine._get_price(code, current_date) or pos.buy_price) * pos.shares
                    for code, pos in positions.items()
                )
                total = capital + float(pos_value)
                daily_values.append(
                    {
                        "date": current_date.isoformat(),
                        "total_value": round(total, 2),
                        "positions": len(positions),
                    }
                )
        finally:
            try:
                if conn is not None:
                    conn.close()
            except Exception:
                pass

        for code, trade in positions.items():
            sell_price = engine._get_price(code, trading_dates[-1]) if trading_dates else None
            if sell_price:
                ret = (
                    (float(sell_price) - trade.buy_price) / max(trade.buy_price, 1e-9) * 100
                )
                capital += float(sell_price) * trade.shares
                trade.sell_date = (trading_dates[-1].isoformat() if trading_dates else end_date.isoformat())
                trade.sell_price = float(sell_price)
                trade.return_pct = round(ret, 2)
                trade.hold_days = engine._count_trading_days(
                    date.fromisoformat(trade.buy_date), (trading_dates[-1] if trading_dates else end_date)
                )
                trade.sell_reason = "回测结束平仓"
                trade.status = "closed"
                all_trades.append(trade)

        metrics = engine._calc_metrics(daily_values, all_trades, float(initial_capital))
        return metrics, all_trades

    def lowfreq_backtest_run_view(
        self,
        *,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        async_run: bool = True,
        requested_by: str = "api",
        report_id: Optional[str] = None,
        overrides: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        start_key, end_key = self._lowfreq_trade_date_range()
        start_key = start_date or start_key
        end_key = end_date or end_key
        start_dt = date.fromisoformat(start_key)
        end_dt = date.fromisoformat(end_key)
        if start_dt > end_dt:
            raise ApiError(
                status_code=HTTPStatus.BAD_REQUEST,
                code="invalid_range",
                message="start_date must be <= end_date",
                details={"start_date": start_key, "end_date": end_key},
            )

        if report_id is not None and str(report_id).strip():
            effective_report_id = str(report_id).strip()
        else:
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            effective_report_id = f"lowfreq_v16_{start_key}_{end_key}__{stamp}_{uuid.uuid4().hex[:8]}"
        report_dir = self._lowfreq_backtest_artifacts_dir / effective_report_id
        report_dir.mkdir(parents=True, exist_ok=True)
        started_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        status_path = report_dir / "status.json"
        pdf_path = report_dir / "trades.pdf"
        json_path = report_dir / "trades.json"

        if pdf_path.exists() and json_path.exists():
            try:
                payload = json.loads(json_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                payload = None
            if isinstance(payload, dict):
                return {
                    "_meta": {"status": "ok", "requested_by": requested_by},
                    "report_id": effective_report_id,
                    "start_date": start_key,
                    "end_date": end_key,
                    "summary": payload.get("summary") or {},
                    "buy_dates": payload.get("buy_dates") or [],
                    "next_session": payload.get("next_session") or {},
                    "overrides": overrides or {},
                    "pdf_url": f"/api/lowfreq/backtest/reports/{effective_report_id}.pdf",
                    "json_url": f"/api/lowfreq/backtest/reports/{effective_report_id}.json",
                }

        if async_run:
            existing_status: Optional[dict[str, Any]] = None
            if status_path.exists():
                try:
                    existing_status = json.loads(status_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    existing_status = None

            if isinstance(existing_status, dict) and existing_status.get("status") == "running":
                return {
                    "_meta": {"status": "accepted", "requested_by": requested_by},
                    "message": "回测已在后台运行中，请稍后再查看/下载报告",
                    "report_id": effective_report_id,
                    "start_date": start_key,
                    "end_date": end_key,
                    "pdf_url": f"/api/lowfreq/backtest/reports/{effective_report_id}.pdf",
                    "json_url": f"/api/lowfreq/backtest/reports/{effective_report_id}.json",
                    "job": existing_status,
                }

            requested_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            job_id = uuid.uuid4().hex
            status_path.write_text(
                json.dumps(
                    {
                        "status": "running",
                        "job_id": job_id,
                        "requested_at": requested_at,
                        "requested_by": requested_by,
                        "report_id": effective_report_id,
                        "start_date": start_key,
                        "end_date": end_key,
                        "pid": None,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            ctx = multiprocessing.get_context("spawn")
            proc = ctx.Process(
                target=_lowfreq_backtest_worker,
                kwargs={
                    "project_root": str(self.project_root),
                    "start_date": start_key,
                    "end_date": end_key,
                    "requested_by": requested_by,
                    "report_id": effective_report_id,
                    "overrides": overrides or {},
                    "job_id": job_id,
                },
                daemon=True,
            )
            proc.start()

            status_path.write_text(
                json.dumps(
                    {
                        "status": "running",
                        "job_id": job_id,
                        "requested_at": requested_at,
                        "requested_by": requested_by,
                        "report_id": effective_report_id,
                        "start_date": start_key,
                        "end_date": end_key,
                        "pid": proc.pid,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            return {
                "_meta": {"status": "accepted", "requested_by": requested_by},
                "message": "已提交后台运行，报告生成中",
                "report_id": effective_report_id,
                "start_date": start_key,
                "end_date": end_key,
                "overrides": overrides or {},
                "pdf_url": f"/api/lowfreq/backtest/reports/{effective_report_id}.pdf",
                "json_url": f"/api/lowfreq/backtest/reports/{effective_report_id}.json",
                "job": {"job_id": job_id, "pid": proc.pid, "status": "running"},
            }

        engine = self._lowfreq_engine_v16()
        if overrides:
            for k, v in overrides.items():
                setattr(engine, str(k), v)
        metrics, trades = self._lowfreq_backtest_with_trades(
            engine=engine, start_date=start_dt, end_date=end_dt, initial_capital=1_000_000.0
        )

        buy_dates: dict[str, int] = {}
        for t in trades:
            buy_dates[t.buy_date] = buy_dates.get(t.buy_date, 0) + 1
        buy_dates_summary = [
            {"buy_date": k, "count": buy_dates[k]} for k in sorted(buy_dates.keys())
        ]

        from dataclasses import asdict

        next_trading_day: Optional[str] = None
        next_candidates: list[dict[str, Any]] = []
        try:
            db_path = Path(
                os.environ.get("NEOTRADE3_STOCK_DB_PATH") or str(self._stock_db_default_path)
            ).expanduser()
            conn = sqlite3.connect(str(db_path))
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT MIN(trade_date) FROM trading_calendar_cache WHERE trade_date > ?",
                    (end_key,),
                )
                row = cursor.fetchone()
                next_trading_day = str(row[0]) if row and row[0] else None
            finally:
                conn.close()
        except Exception:
            next_trading_day = None

        try:
            signals = engine.generate_buy_signals(end_dt)
            raw = signals.get("buy_signals", []) if isinstance(signals, dict) else []
            for item in raw:
                if not isinstance(item, dict):
                    continue
                next_candidates.append(
                    {
                        "code": str(item.get("code") or ""),
                        "name": str(item.get("name") or ""),
                        "sector": str(item.get("sector") or ""),
                        "role": str(item.get("role") or ""),
                        "buy_score": float(item.get("buy_score") or 0.0),
                        "wave_phase": str(item.get("wave_phase") or ""),
                        "resonance": float(item.get("resonance") or 0.0),
                        "reasons": list(item.get("reasons") or []),
                    }
                )
            next_candidates.sort(key=lambda x: float(x.get("buy_score") or 0.0), reverse=True)
            next_candidates = next_candidates[:10]
        except Exception:
            next_candidates = []

        json_payload = {
            "_meta": {
                "status": "ok",
                "requested_by": requested_by,
                "model": "lowfreq_engine_v16_advanced",
                "report_id": effective_report_id,
                "overrides": overrides or {},
            },
            "summary": metrics,
            "buy_dates": buy_dates_summary,
            "next_session": {
                "next_trading_day": next_trading_day,
                "candidates": next_candidates,
                "generated_from_trade_date": end_key,
            },
            "trades": [asdict(t) for t in trades],
        }
        (report_dir / "trades.json").write_text(
            json.dumps(json_payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        pdf_path = report_dir / "trades.pdf"
        self._render_lowfreq_backtest_pdf(
            pdf_path=pdf_path,
            summary=metrics,
            buy_dates=buy_dates_summary,
            trades=trades,
            next_session=json_payload["next_session"],
        )

        finished_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        status_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "status": "done",
                    "requested_by": requested_by,
                    "report_id": effective_report_id,
                    "start_date": start_key,
                    "end_date": end_key,
                    "started_at": started_at,
                    "finished_at": finished_at,
                    "pid": None,
                    "overrides": overrides or {},
                    "pdf_path": str(pdf_path),
                    "json_path": str(json_path),
                    "summary": metrics,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        return {
            "_meta": {"status": "ok", "requested_by": requested_by},
            "report_id": effective_report_id,
            "start_date": start_key,
            "end_date": end_key,
            "summary": metrics,
            "buy_dates": buy_dates_summary,
            "next_session": json_payload["next_session"],
            "overrides": overrides or {},
            "pdf_url": f"/api/lowfreq/backtest/reports/{effective_report_id}.pdf",
            "json_url": f"/api/lowfreq/backtest/reports/{effective_report_id}.json",
        }

    def lowfreq_backtest_status_view(self, *, report_id: str) -> dict[str, Any]:
        report_id = str(report_id or "").strip()
        if not report_id:
            raise ApiError(
                status_code=HTTPStatus.BAD_REQUEST,
                code="invalid_report_id",
                message="report_id is required",
            )

        report_dir = self._lowfreq_backtest_artifacts_dir / report_id
        if not report_dir.exists() or not report_dir.is_dir():
            raise ApiError(
                status_code=HTTPStatus.NOT_FOUND,
                code="report_not_found",
                message="report not found",
                details={"report_id": report_id},
            )

        status_path = report_dir / "status.json"
        json_path = report_dir / "trades.json"
        pdf_path = report_dir / "trades.pdf"

        status_payload: Optional[dict[str, Any]] = None
        if status_path.exists():
            try:
                raw = json.loads(status_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                raw = None
            status_payload = raw if isinstance(raw, dict) else None

        job = status_payload or {"status": "unknown", "reason": "status_file_missing"}

        return {
            "_meta": {"status": "ok"},
            "report_id": report_id,
            "job": job,
            "has_pdf": pdf_path.exists(),
            "has_json": json_path.exists(),
            "pdf_url": f"/api/lowfreq/backtest/reports/{report_id}.pdf" if pdf_path.exists() else None,
            "json_url": f"/api/lowfreq/backtest/reports/{report_id}.json" if json_path.exists() else None,
        }

    def _team_theme_defs(self) -> list[dict[str, Any]]:
        return [
            {"theme_id": "aidc", "name": "AiDC", "keywords": ["AIDC", "AiDC", "数据中心", "东数西算", "算力", "液冷", "服务器"]},
            {"theme_id": "new_energy", "name": "新能源", "keywords": ["新能源", "新能源车", "光伏", "风电", "锂电"]},
            {"theme_id": "domestic_substitution", "name": "国产替代", "keywords": ["国产替代", "信创", "自主可控", "国产软件", "国产操作系统"]},
            {"theme_id": "green_energy", "name": "绿能", "keywords": ["绿能", "绿色电力", "绿电", "碳中和", "碳交易"]},
            {"theme_id": "energy_storage", "name": "储能", "keywords": ["储能"]},
            {"theme_id": "chips", "name": "芯片", "keywords": ["芯片", "半导体", "存储芯片", "AI芯片", "国产芯片"]},
            {"theme_id": "power_compute", "name": "算电结合", "keywords": ["算电结合", "算电协同", "算电融合", "电力设备", "特高压"]},
        ]

    def _read_tushare_status(self) -> dict[str, Any]:
        try:
            if self._tushare_status_file.exists() and self._tushare_status_file.is_file():
                raw = json.loads(self._tushare_status_file.read_text(encoding="utf-8"))
            else:
                raw = None
        except (OSError, json.JSONDecodeError):
            raw = None
        return raw if isinstance(raw, dict) else {"version": 1}

    def _write_tushare_status(self, payload: dict[str, Any]) -> None:
        self._themes_snapshot_dir.mkdir(parents=True, exist_ok=True)
        self._tushare_status_file.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _note_tushare_ok(self, *, api_name: str) -> None:
        status = self._read_tushare_status()
        status["version"] = 1
        status["last_tushare_ok_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        status["last_tushare_ok_api"] = str(api_name)
        self._write_tushare_status(status)

    def _note_tushare_credit_insufficient(self, *, api_name: str, code: Any, msg: str) -> None:
        status = self._read_tushare_status()
        status["version"] = 1
        status["last_credit_insufficient_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        status["last_credit_insufficient_api"] = str(api_name)
        status["last_credit_insufficient_code"] = code
        status["last_credit_insufficient_msg"] = str(msg)
        self._write_tushare_status(status)

    def tushare_status_view(self) -> dict[str, Any]:
        status = self._read_tushare_status()

        def _parse_ts(value: Any) -> Optional[datetime]:
            if not isinstance(value, str) or not value.strip():
                return None
            raw = value.strip()
            try:
                return datetime.strptime(raw, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            except ValueError:
                return None

        last_insufficient = _parse_ts(status.get("last_credit_insufficient_at"))
        last_ok = _parse_ts(status.get("last_tushare_ok_at"))
        credit_insufficient = bool(last_insufficient and (last_ok is None or last_insufficient > last_ok))

        return {
            "_meta": {"status": "ok"},
            "credit_insufficient": bool(credit_insufficient),
            "last_credit_insufficient_at": status.get("last_credit_insufficient_at"),
            "last_credit_insufficient_api": status.get("last_credit_insufficient_api"),
            "last_credit_insufficient_code": status.get("last_credit_insufficient_code"),
            "last_credit_insufficient_msg": status.get("last_credit_insufficient_msg"),
            "last_tushare_ok_at": status.get("last_tushare_ok_at"),
            "last_tushare_ok_api": status.get("last_tushare_ok_api"),
        }

    def tushare_concept_health_view(self, *, requested_by: str = "api") -> dict[str, Any]:
        from neotrade3.data_sources.tushare_concept_adapter import TushareConceptAdapter

        self._load_env_file()
        t0 = time.perf_counter()
        ts = TushareConceptAdapter()
        if not ts.configured:
            return {
                "_meta": {"status": "ok"},
                "provider": "tushare",
                "requested_by": requested_by,
                "ok": False,
                "elapsed_ms": float((time.perf_counter() - t0) * 1000.0),
                "checks": {"token_configured": False},
                "errors": ["tushare_token_not_configured"],
            }

        concepts = ts.fetch_all_concepts()
        probe_concept_code = str(concepts[0].code).strip() if concepts else ""
        stocks = ts.fetch_concept_stocks(concept_code=probe_concept_code, limit=5) if probe_concept_code else []
        errors = ts.errors
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        concepts_ok = bool(concepts) and all(bool(c.code) and bool(str(c.name).strip()) for c in concepts[:5])
        stocks_ok = bool(stocks) and all(bool(s.code) and bool(str(s.name).strip()) for s in stocks)
        ok = bool(concepts_ok and stocks_ok and not errors)
        return {
            "_meta": {"status": "ok"},
            "provider": "tushare",
            "requested_by": requested_by,
            "ok": bool(ok),
            "elapsed_ms": float(elapsed_ms),
            "checks": {
                "token_configured": True,
                "concepts_ok": bool(concepts_ok),
                "concepts_count": len(concepts),
                "probe_concept_code": probe_concept_code or None,
                "concept_stocks_ok": bool(stocks_ok),
                "stocks_count": len(stocks),
                "error_count": len(errors),
            },
            "errors": errors[: min(5, len(errors))],
            "sample": {
                "concepts": [{"code": c.code, "name": c.name} for c in concepts[: min(5, len(concepts))]],
                "concept_stocks": [{"code": s.code, "name": s.name} for s in stocks[: min(5, len(stocks))]],
            },
        }

    def _theme_snapshot_path(self, target_date: str) -> Path:
        return self._themes_snapshot_dir / f"{target_date}.json"

    def _read_theme_snapshot_within_days(
        self, *, target_date: str, max_stale_days: int = 3
    ) -> tuple[Optional[dict[str, Any]], Optional[int], Optional[str]]:
        try:
            dt = date.fromisoformat(str(target_date))
        except ValueError:
            return None, None, "invalid_date"

        for delta in range(0, int(max_stale_days) + 1):
            candidate = (dt - timedelta(days=delta)).isoformat()
            path = self._theme_snapshot_path(candidate)
            if not path.exists():
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(payload, dict):
                return payload, int(delta), None
        return None, None, "not_found"

    def refresh_team_theme_snapshot_view(
        self, *, target_date: str, requested_by: str = "api"
    ) -> dict[str, Any]:
        from neotrade3.data_sources.tushare_concept_adapter import (
            ConceptSector as TushareConceptSector,
            TushareConceptAdapter,
        )

        self._load_env_file()
        self._themes_snapshot_dir.mkdir(parents=True, exist_ok=True)

        defs = self._team_theme_defs()
        t0 = time.perf_counter()
        provider_name = "tushare"
        provider_errors: list[str] = []
        ts = TushareConceptAdapter()
        if not ts.configured:
            provider_errors = ["tushare_token_not_configured"]
            concepts = []
        else:
            concepts_cache_path = self._themes_snapshot_dir / "_tushare_concepts_cache.json"
            cached: list[TushareConceptSector] = []
            try:
                if concepts_cache_path.exists() and concepts_cache_path.is_file():
                    cache_doc = json.loads(concepts_cache_path.read_text(encoding="utf-8"))
                else:
                    cache_doc = None
            except (OSError, json.JSONDecodeError):
                cache_doc = None

            cache_age_days: Optional[int] = None
            if isinstance(cache_doc, dict):
                fetched_at_ts = cache_doc.get("fetched_at_ts")
                items = cache_doc.get("items")
                cached_provider = cache_doc.get("provider")
                try:
                    fetched_at_ts = float(fetched_at_ts) if fetched_at_ts is not None else None
                except Exception:
                    fetched_at_ts = None
                if fetched_at_ts is not None:
                    cache_age_days = int((time.time() - fetched_at_ts) // 86400)
                if isinstance(items, list):
                    if cached_provider in (None, ts.concept_provider):
                        for item in items:
                            if not isinstance(item, dict):
                                continue
                            code = str(item.get("code") or "").strip()
                            name = str(item.get("name") or "").strip()
                            if not code or not name:
                                continue
                            cached.append(TushareConceptSector(code=code, name=name))

            max_cache_age_days = 30
            if cached and cache_age_days is not None and cache_age_days <= max_cache_age_days:
                concepts = cached
                provider_errors = [f"used_cache: age_days={cache_age_days}"]
            else:
                concepts = ts.fetch_all_concepts()
                provider_errors = ts.errors
                if not concepts and isinstance(ts.last_msg, str) and "积分不足" in ts.last_msg:
                    self._note_tushare_credit_insufficient(
                        api_name=str(ts.last_api_name or "concept"),
                        code=ts.last_code,
                        msg=ts.last_msg,
                    )
                if concepts:
                    self._note_tushare_ok(api_name=str(ts.last_api_name or "concept"))
                    try:
                        concepts_cache_path.write_text(
                            json.dumps(
                                {
                                    "version": 1,
                                    "fetched_at_ts": time.time(),
                                    "provider": ts.concept_provider,
                                    "token_fingerprint": ts.token_fingerprint,
                                    "items": [{"code": c.code, "name": c.name} for c in concepts],
                                },
                                ensure_ascii=False,
                                indent=2,
                            )
                            + "\n",
                            encoding="utf-8",
                        )
                    except OSError:
                        pass
                elif cached:
                    concepts = cached
                    provider_errors = [
                        *provider_errors[: min(3, len(provider_errors))],
                        f"fallback_cache: age_days={cache_age_days}",
                    ]
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        if not concepts:
            snap, stale_days, _ = self._read_theme_snapshot_within_days(
                target_date=target_date, max_stale_days=3
            )
            if snap is not None and stale_days is not None:
                dt = date.fromisoformat(str(target_date))
                used_date = (dt - timedelta(days=int(stale_days))).isoformat()
                used_path = self._theme_snapshot_path(used_date)
                return {
                    "_meta": {"status": "ok"},
                    "snapshot_path": str(used_path),
                    "snapshot_meta": {
                        "target_date": target_date,
                        "used_snapshot_date": used_date,
                        "stale_days": int(stale_days),
                        "provider": {
                            "name": provider_name,
                            "errors": provider_errors[: min(5, len(provider_errors))],
                            "fallback": "existing_snapshot",
                        },
                    },
                }
            raise ApiError(
                status_code=HTTPStatus.SERVICE_UNAVAILABLE,
                code="tushare_unavailable",
                message="concept provider fetch failed",
                details={"provider": provider_name, "errors": provider_errors[: min(5, len(provider_errors))]},
            )

        by_theme: dict[str, list[dict[str, Any]]] = {d["theme_id"]: [] for d in defs}
        for c in concepts:
            name = str(c.name or "")
            for d in defs:
                if any(str(kw) and str(kw) in name for kw in (d.get("keywords") or [])):
                    by_theme[d["theme_id"]].append(
                        {"code": c.code, "name": c.name, "change_pct": c.change_pct}
                    )

        members_by_theme: dict[str, list[str]] = {}
        concept_members: dict[str, list[dict[str, Any]]] = {}
        tushare_members_cache_path = self._themes_snapshot_dir / "_tushare_concept_members_cache.json"
        tushare_members_cache: dict[str, Any] = {}
        try:
            if tushare_members_cache_path.exists() and tushare_members_cache_path.is_file():
                tushare_members_cache = json.loads(
                    tushare_members_cache_path.read_text(encoding="utf-8")
                )
        except (OSError, json.JSONDecodeError):
            tushare_members_cache = {}
        cache_concepts = (
            tushare_members_cache.get("concepts")
            if isinstance(tushare_members_cache, dict)
            else None
        )
        if not isinstance(cache_concepts, dict):
            cache_concepts = {}
            tushare_members_cache = {"version": 1, "concepts": cache_concepts}

        max_member_fetch_calls = 3
        member_fetch_calls = 0
        ts_members_adapter = TushareConceptAdapter()
        for d in defs:
            theme_id = str(d["theme_id"])
            codes: list[str] = []
            for c in by_theme.get(theme_id) or []:
                concept_code = str(c.get("code") or "").strip()
                if not concept_code:
                    continue
                cached_members = cache_concepts.get(concept_code)
                cached_stocks = (
                    cached_members.get("stocks")
                    if isinstance(cached_members, dict)
                    else None
                )
                if isinstance(cached_stocks, list) and cached_stocks:
                    stocks = [
                        {"code": str(x.get("code") or ""), "name": str(x.get("name") or "")}
                        for x in cached_stocks
                        if isinstance(x, dict) and str(x.get("code") or "").strip()
                    ]
                    concept_members[concept_code] = [
                        {"code": s["code"], "name": s["name"], "change_pct": 0.0}
                        for s in stocks
                    ]
                    for s in stocks:
                        codes.append(str(s["code"]))
                    continue

                if member_fetch_calls >= max_member_fetch_calls:
                    concept_members[concept_code] = []
                    continue

                member_fetch_calls += 1
                ts_stocks = ts_members_adapter.fetch_concept_stocks(concept_code=concept_code, limit=50)
                if ts_members_adapter.last_code in (0, "0"):
                    self._note_tushare_ok(
                        api_name=str(ts_members_adapter.last_api_name or "concept_detail")
                    )
                elif isinstance(ts_members_adapter.last_msg, str) and "积分不足" in ts_members_adapter.last_msg:
                    self._note_tushare_credit_insufficient(
                        api_name=str(ts_members_adapter.last_api_name or "concept_detail"),
                        code=ts_members_adapter.last_code,
                        msg=ts_members_adapter.last_msg,
                    )
                concept_members[concept_code] = [
                    {"code": s.code, "name": s.name, "change_pct": s.change_pct} for s in ts_stocks
                ]
                cache_concepts[concept_code] = {
                    "fetched_at_ts": time.time(),
                    "stocks": [{"code": s.code, "name": s.name} for s in ts_stocks],
                }
                for s in ts_stocks:
                    if s.code:
                        codes.append(str(s.code))
            uniq = sorted(set(codes))
            members_by_theme[theme_id] = uniq

        try:
            tushare_members_cache_path.write_text(
                json.dumps(tushare_members_cache, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        except OSError:
            pass

        snapshot = {
            "version": 1,
            "target_date": target_date,
            "requested_by": requested_by,
            "provider": {"name": provider_name, "elapsed_ms": float(elapsed_ms), "errors": provider_errors[: min(5, len(provider_errors))]},
            "themes": [
                {
                    "theme_id": d["theme_id"],
                    "name": d["name"],
                    "keywords": d.get("keywords") or [],
                    "concepts": by_theme.get(d["theme_id"]) or [],
                    "members": members_by_theme.get(d["theme_id"]) or [],
                }
                for d in defs
            ],
            "concept_members": concept_members,
            "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        path = self._theme_snapshot_path(target_date)
        path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return {"_meta": {"status": "ok"}, "snapshot_path": str(path), "snapshot_meta": {"target_date": target_date}}

    def warm_tushare_theme_cache_view(
        self,
        *,
        requested_by: str = "api",
        max_member_calls: int = 1,
    ) -> dict[str, Any]:
        from neotrade3.data_sources.tushare_concept_adapter import (
            ConceptSector as TushareConceptSector,
            TushareConceptAdapter,
        )

        ts = TushareConceptAdapter()
        if not ts.configured:
            return {
                "_meta": {"status": "ok"},
                "status": "skipped",
                "reason": "tushare_token_not_configured",
            }

        self._themes_snapshot_dir.mkdir(parents=True, exist_ok=True)
        concepts_cache_path = self._themes_snapshot_dir / "_tushare_concepts_cache.json"
        members_cache_path = self._themes_snapshot_dir / "_tushare_concept_members_cache.json"

        concepts: list[TushareConceptSector] = []
        concepts_source = "cache"
        try:
            if concepts_cache_path.exists() and concepts_cache_path.is_file():
                cache_doc = json.loads(concepts_cache_path.read_text(encoding="utf-8"))
            else:
                cache_doc = None
        except (OSError, json.JSONDecodeError):
            cache_doc = None

        cache_age_days: Optional[int] = None
        last_attempt_ts: Optional[float] = None
        last_error: Optional[str] = None
        cached_token_fingerprint: Optional[str] = None
        cached_provider: Optional[str] = None
        if isinstance(cache_doc, dict):
            fetched_at_ts = cache_doc.get("fetched_at_ts")
            last_attempt_ts = cache_doc.get("last_attempt_ts")
            last_error = cache_doc.get("last_error")
            cached_token_fingerprint = cache_doc.get("token_fingerprint")
            cached_provider = cache_doc.get("provider")
            items = cache_doc.get("items")
            try:
                fetched_at_ts = float(fetched_at_ts) if fetched_at_ts is not None else None
            except Exception:
                fetched_at_ts = None
            try:
                last_attempt_ts = float(last_attempt_ts) if last_attempt_ts is not None else None
            except Exception:
                last_attempt_ts = None
            if fetched_at_ts is not None:
                cache_age_days = int((time.time() - fetched_at_ts) // 86400)
            if isinstance(items, list):
                if cached_provider == ts.concept_provider:
                    for item in items:
                        if not isinstance(item, dict):
                            continue
                        code = str(item.get("code") or "").strip()
                        name = str(item.get("name") or "").strip()
                        if not code or not name:
                            continue
                        concepts.append(TushareConceptSector(code=code, name=name))

        if not concepts:
            cooldown_seconds = 55
            if isinstance(last_error, str) and "1次/小时" in last_error:
                cooldown_seconds = 3500
            if (
                last_attempt_ts is not None
                and (time.time() - last_attempt_ts) < cooldown_seconds
                and cached_token_fingerprint == ts.token_fingerprint
            ):
                return {
                    "_meta": {"status": "ok"},
                    "status": "skipped",
                    "reason": "concept_list_cooldown",
                    "cooldown_seconds": cooldown_seconds,
                    "last_attempt_ts": last_attempt_ts,
                    "last_error": last_error,
                }

            concepts_source = "api"
            concepts = ts.fetch_all_concepts()
            if concepts:
                if ts.last_code in (0, "0"):
                    self._note_tushare_ok(api_name=str(ts.last_api_name or "concept"))
                try:
                    concepts_cache_path.write_text(
                        json.dumps(
                            {
                                "version": 1,
                                "fetched_at_ts": time.time(),
                                "provider": ts.concept_provider,
                                "token_fingerprint": ts.token_fingerprint,
                                "items": [{"code": c.code, "name": c.name} for c in concepts],
                            },
                            ensure_ascii=False,
                            indent=2,
                        )
                        + "\n",
                        encoding="utf-8",
                    )
                except OSError:
                    pass
            else:
                if isinstance(ts.last_msg, str) and "积分不足" in ts.last_msg:
                    self._note_tushare_credit_insufficient(
                        api_name=str(ts.last_api_name or "concept"),
                        code=ts.last_code,
                        msg=ts.last_msg,
                    )
                try:
                    concepts_cache_path.write_text(
                        json.dumps(
                            {
                                "version": 1,
                                "last_attempt_ts": time.time(),
                                "provider": ts.concept_provider,
                                "token_fingerprint": ts.token_fingerprint,
                                "last_error": (ts.errors[0] if ts.errors else "unknown_error"),
                                "items": [],
                            },
                            ensure_ascii=False,
                            indent=2,
                        )
                        + "\n",
                        encoding="utf-8",
                    )
                except OSError:
                    pass
                return {
                    "_meta": {"status": "ok"},
                    "status": "failed",
                    "reason": "concept_list_unavailable",
                    "errors": ts.errors[: min(5, len(ts.errors))],
                }

        defs = self._team_theme_defs()
        concept_codes: list[str] = []
        for c in concepts:
            name = str(c.name or "")
            if not name:
                continue
            for d in defs:
                if any(str(kw) and str(kw) in name for kw in (d.get("keywords") or [])):
                    code = str(c.code or "").strip()
                    if code:
                        concept_codes.append(code)
                    break
        concept_codes = sorted(set(concept_codes))

        try:
            if members_cache_path.exists() and members_cache_path.is_file():
                members_doc = json.loads(members_cache_path.read_text(encoding="utf-8"))
            else:
                members_doc = None
        except (OSError, json.JSONDecodeError):
            members_doc = None

        concepts_map = members_doc.get("concepts") if isinstance(members_doc, dict) else None
        members_provider = members_doc.get("provider") if isinstance(members_doc, dict) else None
        if not isinstance(concepts_map, dict) or members_provider != ts.concept_provider:
            concepts_map = {}
            members_doc = {"version": 1, "provider": ts.concept_provider, "concepts": concepts_map}

        missing = [code for code in concept_codes if code not in concepts_map]
        calls = 0
        warmed: list[str] = []
        for code in missing:
            if calls >= int(max_member_calls):
                break
            stocks = ts.fetch_concept_stocks(concept_code=code, limit=50)
            if ts.last_code in (0, "0"):
                self._note_tushare_ok(api_name=str(ts.last_api_name or "concept_detail"))
            elif isinstance(ts.last_msg, str) and "积分不足" in ts.last_msg:
                self._note_tushare_credit_insufficient(
                    api_name=str(ts.last_api_name or "concept_detail"),
                    code=ts.last_code,
                    msg=ts.last_msg,
                )
            concepts_map[code] = {
                "fetched_at_ts": time.time(),
                "stocks": [{"code": s.code, "name": s.name} for s in stocks],
            }
            warmed.append(code)
            calls += 1

        try:
            members_cache_path.write_text(
                json.dumps(members_doc, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        except OSError:
            pass

        return {
            "_meta": {"status": "ok"},
            "status": "ok",
            "requested_by": requested_by,
            "concepts_source": concepts_source,
            "concepts_cache_age_days": cache_age_days,
            "theme_concept_count": len(concept_codes),
            "members_cached_count": len(concepts_map),
            "members_missing_count": len(missing),
            "members_warmed": warmed,
            "member_calls": calls,
            "errors": ts.errors[: min(5, len(ts.errors))],
        }

    def _build_ths_concepts_hot_snapshot(
        self,
        *,
        engine,
        target_date: date,
        include_portfolio: bool,
        include_sell_signal: bool,
        perf: Optional[dict[str, float]] = None,
    ) -> dict[str, Any]:
        from neotrade3.data_sources.tushare_concept_adapter import (
            ConceptSector as TushareConceptSector,
            TushareConceptAdapter,
        )

        self._load_env_file()
        self._themes_snapshot_dir.mkdir(parents=True, exist_ok=True)

        t0 = time.perf_counter()
        ts = TushareConceptAdapter()
        concepts_cache_path = self._themes_snapshot_dir / "_tushare_concepts_cache.json"
        members_cache_path = self._themes_snapshot_dir / "_tushare_concept_members_cache.json"

        concepts: list[TushareConceptSector] = []
        concepts_source = "cache"
        try:
            cache_doc = (
                json.loads(concepts_cache_path.read_text(encoding="utf-8"))
                if concepts_cache_path.exists() and concepts_cache_path.is_file()
                else None
            )
        except (OSError, json.JSONDecodeError):
            cache_doc = None
        items = cache_doc.get("items") if isinstance(cache_doc, dict) else None
        cached_provider = cache_doc.get("provider") if isinstance(cache_doc, dict) else None
        if isinstance(items, list) and cached_provider in (None, ts.concept_provider):
            for item in items:
                if not isinstance(item, dict):
                    continue
                code = str(item.get("code") or "").strip()
                name = str(item.get("name") or "").strip()
                if not code or not name:
                    continue
                stock_count = 0
                raw_count = item.get("stock_count")
                if raw_count is not None:
                    try:
                        stock_count = int(raw_count)
                    except Exception:
                        stock_count = 0
                concepts.append(TushareConceptSector(code=code, name=name, stock_count=stock_count))

        provider_errors: list[str] = []
        if not concepts:
            if not ts.configured:
                provider_errors = ["tushare_token_not_configured"]
            else:
                concepts_source = "api"
                concepts = ts.fetch_all_concepts()
                provider_errors = ts.errors
                if concepts:
                    if ts.last_code in (0, "0"):
                        self._note_tushare_ok(api_name=str(ts.last_api_name or "concept"))
                    try:
                        concepts_cache_path.write_text(
                            json.dumps(
                                {
                                    "version": 1,
                                    "fetched_at_ts": time.time(),
                                    "provider": ts.concept_provider,
                                    "token_fingerprint": ts.token_fingerprint,
                                    "items": [
                                        {"code": c.code, "name": c.name, "stock_count": int(c.stock_count or 0)}
                                        for c in concepts
                                    ],
                                },
                                ensure_ascii=False,
                                indent=2,
                            )
                            + "\n",
                            encoding="utf-8",
                        )
                    except OSError:
                        pass
                elif isinstance(ts.last_msg, str) and "积分不足" in ts.last_msg:
                    self._note_tushare_credit_insufficient(
                        api_name=str(ts.last_api_name or "concept"),
                        code=ts.last_code,
                        msg=ts.last_msg,
                    )

        if not concepts:
            return {
                "_meta": {
                    "status": "error",
                    "code": "ths_concept_unavailable",
                    "message": "同花顺概念数据不可用（未配置 token 或无法拉取概念列表）",
                    "provider_errors": provider_errors[: min(5, len(provider_errors))],
                },
                "date": target_date.isoformat(),
                "sectors": [],
            }

        concepts_sorted = sorted(concepts, key=lambda c: int(getattr(c, "stock_count", 0) or 0), reverse=True)
        warm_concepts = concepts_sorted[:30]
        warm_codes = [str(c.code) for c in warm_concepts if getattr(c, "code", None)]

        try:
            members_doc = (
                json.loads(members_cache_path.read_text(encoding="utf-8"))
                if members_cache_path.exists() and members_cache_path.is_file()
                else None
            )
        except (OSError, json.JSONDecodeError):
            members_doc = None
        members_provider = members_doc.get("provider") if isinstance(members_doc, dict) else None
        concepts_map = members_doc.get("concepts") if isinstance(members_doc, dict) else None
        if members_provider != ts.concept_provider or not isinstance(concepts_map, dict):
            concepts_map = {}
            members_doc = {"version": 1, "provider": ts.concept_provider, "concepts": concepts_map}

        missing = [code for code in warm_codes if code not in concepts_map]
        warmed: list[str] = []
        member_calls = 0
        max_member_calls = 10
        if ts.configured:
            for code in missing:
                if member_calls >= int(max_member_calls):
                    break
                stocks = ts.fetch_concept_stocks(concept_code=code, limit=80)
                member_calls += 1
                if ts.last_code in (0, "0"):
                    self._note_tushare_ok(api_name=str(ts.last_api_name or "concept_detail"))
                elif isinstance(ts.last_msg, str) and "积分不足" in ts.last_msg:
                    self._note_tushare_credit_insufficient(
                        api_name=str(ts.last_api_name or "concept_detail"),
                        code=ts.last_code,
                        msg=ts.last_msg,
                    )
                concepts_map[code] = {
                    "fetched_at_ts": time.time(),
                    "stocks": [{"code": s.code, "name": s.name} for s in stocks],
                }
                warmed.append(code)
            try:
                members_cache_path.write_text(
                    json.dumps(members_doc, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
            except OSError:
                pass

        concept_name_by_code, concept_members = self._load_ths_concept_caches()
        try:
            self.ths_concept_mainline_compute_view(
                trade_date=target_date.isoformat(), requested_by="api", top_n=10
            )
        except Exception:
            pass
        mainline = self.ths_concept_mainline_view(
            trade_date=target_date.isoformat(),
            limit=10,
            requested_by="api",
        )
        concepts_rows = mainline.get("concepts") if isinstance(mainline, dict) else None
        concepts_rows = concepts_rows if isinstance(concepts_rows, list) else []

        candidate_by_code: dict[str, Any] = {}
        t_candidates = time.perf_counter()
        candidates = engine.get_global_candidates(target_date=target_date, top_n=200)
        for c in candidates:
            code = str(getattr(c, "code", "") or "").strip()
            if code:
                candidate_by_code[code] = c
        if perf is not None:
            perf["global_candidates_ms"] = (time.perf_counter() - t_candidates) * 1000.0

        union_codes: set[str] = set()
        for row in concepts_rows:
            if not isinstance(row, dict):
                continue
            cc = str(row.get("concept_code") or "").strip()
            members = concept_members.get(cc) or []
            for x in members:
                code = str(x or "").strip()
                if code:
                    union_codes.add(code)

        metrics_map = self._load_stock_metrics_for_codes(
            codes=sorted(union_codes),
            target_date=target_date.isoformat(),
            amount_window_len=20,
            return_offsets=(5, 20),
        )

        market_phase_payload: Optional[dict[str, Any]] = None
        market_upwave_ok = False
        try:
            from neotrade3.analysis.market_phase import detect_market_phase, MarketPhase

            mp = detect_market_phase(
                db_path=str(
                    Path(os.environ.get("NEOTRADE3_STOCK_DB_PATH") or str(self._stock_db_default_path)).expanduser()
                ),
                target_date=target_date.isoformat(),
                lookback_days=60,
            )
            market_phase_payload = {
                "phase": str(mp.phase.value),
                "confidence": float(mp.confidence),
                "market_breadth": float(mp.market_breadth),
                "amount_trend": str(mp.amount_trend),
            }
            market_upwave_ok = bool(mp.phase == MarketPhase.BULL and float(mp.confidence) >= 0.55)
        except Exception:
            market_phase_payload = None
            market_upwave_ok = False

        def _rank01(values_by_code: dict[str, float]) -> dict[str, float]:
            items = [(k, float(v)) for k, v in values_by_code.items() if k and isinstance(v, (int, float))]
            items.sort(key=lambda x: x[1])
            n = len(items)
            if n <= 1:
                return {k: 1.0 for k, _ in items}
            out: dict[str, float] = {}
            for i, (k, _v) in enumerate(items):
                out[k] = float(i) / float(n - 1)
            return out

        def _median(values: list[float]) -> float:
            vals = sorted([float(v) for v in values if isinstance(v, (int, float))])
            n = len(vals)
            if n == 0:
                return 0.0
            mid = n // 2
            if n % 2 == 1:
                return float(vals[mid])
            return float((vals[mid - 1] + vals[mid]) / 2.0)

        state = self._load_lowfreq_sim_state()
        positions = state.get("positions") if isinstance(state.get("positions"), dict) else {}
        manual_intents = state.get("manual_intents") if isinstance(state.get("manual_intents"), list) else []
        abandoned_codes = {
            str(item.get("code") or "")
            for item in manual_intents
            if isinstance(item, dict) and str(item.get("action") or "") == "abandon"
        }
        pending_buy_by_code = {
            str(item.get("code") or ""): item
            for item in manual_intents
            if isinstance(item, dict) and str(item.get("action") or "") == "buy_intent"
        }
        cooldown_cache: dict[str, dict[str, Any]] = {}
        market_regime = "unknown"
        calibration_map: dict[str, dict[str, Any]] = {}
        _calib_conn = None
        try:
            _calib_conn = engine._conn()
            calibration_map = self._confidence_load_calibration_map(
                conn=_calib_conn, as_of_date=target_date.isoformat()
            )
        except Exception:
            calibration_map = {}
        finally:
            if _calib_conn is not None:
                try:
                    _calib_conn.close()
                except Exception:
                    pass

        assigned_codes: set[str] = set()
        sectors: list[dict[str, Any]] = []
        for row in concepts_rows:
            if not isinstance(row, dict):
                continue
            concept_code = str(row.get("concept_code") or "").strip()
            if not concept_code:
                continue
            concept_name = str(row.get("concept_name") or concept_name_by_code.get(concept_code) or concept_code)
            members = concept_members.get(concept_code) or []
            member_codes = [str(x).strip() for x in members if str(x).strip()]
            member_metrics = [metrics_map.get(code) for code in member_codes if code in metrics_map]
            member_metrics = [m for m in member_metrics if isinstance(m, dict)]
            if not member_metrics:
                continue

            money_ratio_by_code: dict[str, float] = {}
            ret5_by_code: dict[str, float] = {}
            ret20_by_code: dict[str, float] = {}
            cap_by_code: dict[str, float] = {}
            for m in member_metrics:
                code = str(m.get("code") or "").strip()
                if not code:
                    continue
                amount_today = float(m.get("amount_today") or 0.0)
                avg_amount = float(m.get("avg_amount_window") or 0.0)
                ratio = amount_today / max(avg_amount, 1e-9)
                money_ratio_by_code[code] = float(ratio)
                r5 = m.get("return_d1")
                r20 = m.get("return_d2")
                ret5_by_code[code] = float(r5) if isinstance(r5, (int, float)) else 0.0
                ret20_by_code[code] = float(r20) if isinstance(r20, (int, float)) else 0.0
                mcap = m.get("circulating_market_cap")
                if not isinstance(mcap, (int, float)) or float(mcap) <= 0:
                    mcap = m.get("total_market_cap")
                cap_by_code[code] = float(mcap) if isinstance(mcap, (int, float)) else 0.0

            money_rank = _rank01(money_ratio_by_code)
            ret5_rank = _rank01(ret5_by_code)
            ret20_rank = _rank01(ret20_by_code)
            cap_rank = _rank01(cap_by_code)

            positive_ret5 = [code for code, v in ret5_by_code.items() if isinstance(v, (int, float)) and float(v) > 0]
            diffusion = float(len(positive_ret5)) / float(max(1, len(ret5_by_code)))
            cap_median = _median(list(cap_by_code.values()))

            leader_potential: list[tuple[str, float]] = []
            core_potential: list[tuple[str, float]] = []
            for code in ret5_by_code.keys():
                lp = float(0.45 * money_rank.get(code, 0.0) + 0.35 * ret5_rank.get(code, 0.0) + 0.20 * ret20_rank.get(code, 0.0))
                cp = float(0.35 * cap_rank.get(code, 0.0) + 0.35 * money_rank.get(code, 0.0) + 0.30 * ret20_rank.get(code, 0.0))
                leader_potential.append((code, lp))
                core_potential.append((code, cp))
            leader_potential.sort(key=lambda x: x[1], reverse=True)
            core_potential.sort(key=lambda x: x[1], reverse=True)

            leader_codes: list[str] = []
            for c, _ in leader_potential:
                if c and c not in assigned_codes:
                    leader_codes.append(c)
                if len(leader_codes) >= 2:
                    break

            core_codes: list[str] = []
            for c, _ in core_potential:
                if not c or c in assigned_codes or c in leader_codes:
                    continue
                if cap_median > 0 and float(cap_by_code.get(c) or 0.0) < cap_median:
                    continue
                core_codes.append(c)
                if len(core_codes) >= 5:
                    break
            if len(core_codes) < 5:
                for c, _ in core_potential:
                    if not c or c in assigned_codes or c in leader_codes or c in core_codes:
                        continue
                    core_codes.append(c)
                    if len(core_codes) >= 5:
                        break

            follower_codes: list[str] = []
            for c, _ in leader_potential:
                if not c or c in assigned_codes or c in leader_codes or c in core_codes:
                    continue
                follower_codes.append(c)
                if len(follower_codes) >= 7:
                    break

            top3_ret5 = sorted([float(ret5_by_code.get(c) or 0.0) for c in leader_codes + core_codes], reverse=True)[:3]
            top3_ratio = sorted([float(money_ratio_by_code.get(c) or 0.0) for c in leader_codes + core_codes], reverse=True)[:3]
            avg_top3_ret5 = float(sum(top3_ret5) / float(max(1, len(top3_ret5))))
            avg_top3_ratio = float(sum(top3_ratio) / float(max(1, len(top3_ratio))))
            concept_upwave_ok = bool(diffusion >= 0.6 and avg_top3_ret5 >= 2.0 and avg_top3_ratio >= 1.1)
            concept_upwave_payload = {
                "status": ("upwave" if concept_upwave_ok else "not_upwave"),
                "diffusion": float(round(diffusion, 4)),
                "avg_top3_return_5d": float(round(avg_top3_ret5, 4)),
                "avg_top3_money_ratio": float(round(avg_top3_ratio, 4)),
            }

            def build_stock_payload(code: str, role_label: str) -> dict[str, Any]:
                m = metrics_map.get(code) if isinstance(metrics_map, dict) else None
                c = candidate_by_code.get(code)
                name = str(getattr(c, "name", "") or "") if c is not None else str(m.get("name") or "") if isinstance(m, dict) else ""
                buy_score = float(getattr(c, "buy_score", 0.0) or 0.0) if c is not None else None
                resonance = float(getattr(c, "sector_resonance", 0.0) or 0.0) if c is not None else 0.0
                ret5 = float(getattr(c, "ret_5d", 0.0) or 0.0) if c is not None else float(m.get("return_d1") or 0.0) if isinstance(m, dict) else 0.0
                ret20 = float(m.get("return_d2") or 0.0) if isinstance(m, dict) else 0.0
                amount_today = float(m.get("amount_today") or 0.0) if isinstance(m, dict) else 0.0
                avg_amount = float(m.get("avg_amount_window") or 0.0) if isinstance(m, dict) else 0.0
                money_ratio = float(amount_today / max(avg_amount, 1e-9))
                mcap = m.get("circulating_market_cap") if isinstance(m, dict) else None
                if not isinstance(mcap, (int, float)) or float(mcap) <= 0:
                    mcap = m.get("total_market_cap") if isinstance(m, dict) else None
                mcap_f = float(mcap) if isinstance(mcap, (int, float)) else None

                sell_signal = False
                sell_reason = None
                if include_sell_signal and code in positions and isinstance(positions.get(code), dict):
                    trade = self._lowfreq_trade_from_payload(positions[code])
                    sell = engine.check_sell_signal_v2(trade, target_date)
                    positions[code] = self._lowfreq_trade_to_payload(trade)
                    if sell:
                        sell_signal = True
                        sell_reason = sell.details

                sector_name = concept_name
                cooldown_info = cooldown_cache.get(sector_name)
                if cooldown_info is None:
                    try:
                        raw = engine._sector_cooldown_confirmed(sector_name, target_date)
                        cooldown_info = raw if isinstance(raw, dict) else {}
                    except Exception:
                        cooldown_info = {}
                    cooldown_cache[sector_name] = cooldown_info
                cooldown_confirmed = bool(cooldown_info.get("confirmed")) if isinstance(cooldown_info, dict) else False
                cooldown_hits = 0
                if isinstance(cooldown_info, dict):
                    try:
                        cooldown_hits = int(cooldown_info.get("hits") or 0)
                    except Exception:
                        cooldown_hits = 0
                risk_level = "exit" if (sell_signal or cooldown_confirmed) else "warn" if cooldown_hits > 0 else "ok"
                risk_reason: Optional[str] = None
                if sell_signal:
                    risk_reason = str(sell_reason or "个股卖出信号")
                elif cooldown_confirmed:
                    risk_reason = "冷却确认成立"
                elif cooldown_hits > 0:
                    risk_reason = "当日命中但未确认"

                stock_upwave_ok = bool(ret20 > 0 and ret5 > 0 and money_ratio >= 1.05)
                buy_signal = False
                if isinstance(buy_score, (int, float)):
                    buy_signal = bool(
                        float(buy_score) >= float(engine.BUY_THRESHOLD)
                        and role_label in {"龙头", "中军"}
                        and float(resonance) >= float(engine.MIN_RESONANCE)
                        and market_upwave_ok
                        and concept_upwave_ok
                        and stock_upwave_ok
                    )

                confidence_prob = None
                confidence_samples = 0
                if isinstance(buy_score, (int, float)):
                    bucket_key = self._confidence_bucket_key(
                        raw_score=float(buy_score),
                        role=str(role_label),
                        risk_level=risk_level,
                        market_regime=market_regime,
                    )
                    bucket = calibration_map.get(bucket_key)
                    confidence_prob = float(bucket.get("confidence_prob")) if isinstance(bucket, dict) else None
                    confidence_samples = int(bucket.get("n")) if isinstance(bucket, dict) else 0

                return {
                    "code": code,
                    "name": name,
                    "certainty": float(buy_score) if isinstance(buy_score, (int, float)) else None,
                    "buy_score": float(buy_score) if isinstance(buy_score, (int, float)) else None,
                    "sector": concept_name,
                    "role": role_label,
                    "reasons": list(getattr(c, "buy_reasons", []) or []) if c is not None else [],
                    "cup_handle_ok": bool(getattr(c, "cup_handle_ok", False)) if c is not None else False,
                    "resonance": float(resonance),
                    "wave_phase": str(getattr(c, "wave_phase", "") or "") if c is not None else "",
                    "return_5d": float(ret5),
                    "buy_signal": bool(buy_signal),
                    "sell_signal": bool(sell_signal),
                    "sell_reason": sell_reason,
                    "risk_level": risk_level,
                    "risk_reason": risk_reason,
                    "confidence_prob": confidence_prob,
                    "confidence_samples": confidence_samples,
                    "suggested_entry": "今日" if buy_signal else None,
                    "role_scores": {
                        "money_ratio": float(round(money_ratio, 4)),
                        "money_rank": float(round(money_rank.get(code, 0.0), 4)),
                        "cap": mcap_f,
                        "cap_rank": float(round(cap_rank.get(code, 0.0), 4)),
                        "return_5d_rank": float(round(ret5_rank.get(code, 0.0), 4)),
                        "return_20d_rank": float(round(ret20_rank.get(code, 0.0), 4)),
                    },
                    "upwave_gate": {
                        "market_ok": bool(market_upwave_ok),
                        "concept_ok": bool(concept_upwave_ok),
                        "stock_ok": bool(stock_upwave_ok),
                    },
                    "manual": {
                        "abandoned": code in abandoned_codes,
                        "buy_intent_pending": code in pending_buy_by_code,
                        "buy_execute_date": (
                            str(pending_buy_by_code.get(code, {}).get("execute_date") or "")
                            if code in pending_buy_by_code
                            else None
                        ),
                        "intent_id": (
                            str(pending_buy_by_code.get(code, {}).get("intent_id") or "")
                            if code in pending_buy_by_code
                            else None
                        ),
                    },
                }

            leaders_payload = [build_stock_payload(c, "龙头") for c in leader_codes if c]
            middle_payload = [build_stock_payload(c, "中军") for c in core_codes if c]
            followers_payload = [build_stock_payload(c, "跟随") for c in follower_codes if c]

            for c in leader_codes + core_codes:
                if c:
                    assigned_codes.add(c)

            heat_score = float(row.get("heat_score") or 0.0) if isinstance(row.get("heat_score"), (int, float)) else 0.0
            sectors.append(
                {
                    "code": concept_code,
                    "name": concept_name,
                    "sector_lv1": concept_name,
                    "sector_lv2": concept_name,
                    "heat_score": float(round(heat_score, 4)),
                    "leaders": leaders_payload[:3],
                    "middle": middle_payload[:5],
                    "followers": followers_payload[:7],
                    "upwave": concept_upwave_payload,
                    "meta": {
                        "concept_code": concept_code,
                        "mainline_rank": row.get("mainline_rank"),
                        "mainline_score": row.get("mainline_score"),
                        "mainline_streak": row.get("mainline_streak"),
                        "trend_state": row.get("trend_state"),
                        "risk_level": row.get("risk_level"),
                        "heat_rank": row.get("heat_rank"),
                        "member_count": row.get("member_count"),
                        "valid_count": row.get("valid_count"),
                        "stale_days": None,
                    },
                }
            )

        sectors.sort(key=lambda x: float(x.get("heat_score") or 0.0), reverse=True)

        base: dict[str, Any] = {
            "_meta": {
                "status": "ok",
                "mode": "ths_concept",
                "market_phase": market_phase_payload,
                "concepts_source": concepts_source,
                "concept_count": len(concepts_rows),
                "members_warmed": warmed,
                "member_calls": int(member_calls),
                "provider_errors": provider_errors[: min(5, len(provider_errors))],
                "elapsed_ms": float((time.perf_counter() - t0) * 1000.0),
            },
            "date": target_date.isoformat(),
            "sectors": sectors,
        }

        if include_portfolio or include_sell_signal:
            state2 = self._load_lowfreq_sim_state()
            base["portfolio"] = self._lowfreq_portfolio_view(
                engine=engine,
                state=state2,
                target_date=target_date,
            )
            self._save_lowfreq_sim_state(state2)
        return base

    def _build_team_themes_hot_snapshot(
        self,
        *,
        engine,
        target_date: date,
        include_portfolio: bool,
        include_sell_signal: bool,
        perf: Optional[dict[str, float]] = None,
    ) -> dict[str, Any]:
        snapshot, stale_days, err = self._read_theme_snapshot_within_days(
            target_date=target_date.isoformat(), max_stale_days=3
        )
        if snapshot is None:
            return {
                "_meta": {
                    "status": "error",
                    "code": "team_theme_unavailable",
                    "message": "团队主题数据不可用（超过 3 天或未生成快照）",
                    "reason": err,
                },
                "date": target_date.isoformat(),
                "sectors": [],
            }

        themes = snapshot.get("themes")
        if not isinstance(themes, list):
            return {
                "_meta": {
                    "status": "error",
                    "code": "team_theme_unavailable",
                    "message": "团队主题数据不可用（快照格式异常）",
                },
                "date": target_date.isoformat(),
                "sectors": [],
            }

        t0 = time.perf_counter()
        candidates = engine.get_global_candidates(target_date=target_date, top_n=120)
        if perf is not None:
            perf["theme_candidates_ms"] = (time.perf_counter() - t0) * 1000.0

        state = self._load_lowfreq_sim_state()
        positions = state.get("positions") if isinstance(state.get("positions"), dict) else {}
        manual_intents = state.get("manual_intents") if isinstance(state.get("manual_intents"), list) else []
        abandoned_codes = {
            str(item.get("code") or "")
            for item in manual_intents
            if isinstance(item, dict) and str(item.get("action") or "") == "abandon"
        }
        pending_buy_by_code = {
            str(item.get("code") or ""): item
            for item in manual_intents
            if isinstance(item, dict) and str(item.get("action") or "") == "buy_intent"
        }

        cooldown_cache: dict[str, dict[str, Any]] = {}
        market_regime = "unknown"
        calibration_map: dict[str, dict[str, Any]] = {}
        _calib_conn = None
        try:
            _calib_conn = engine._conn()
            calibration_map = self._confidence_load_calibration_map(
                conn=_calib_conn, as_of_date=target_date.isoformat()
            )
        except Exception:
            calibration_map = {}
        finally:
            if _calib_conn is not None:
                try:
                    _calib_conn.close()
                except Exception:
                    pass

        candidate_by_code: dict[str, Any] = {}
        for c in candidates:
            code = str(getattr(c, "code", "") or "").strip()
            if code:
                candidate_by_code[code] = c

        union_codes: set[str] = set()
        for t in themes:
            if not isinstance(t, dict):
                continue
            members = t.get("members")
            if isinstance(members, list):
                for x in members:
                    code = str(x or "").strip()
                    if code:
                        union_codes.add(code)

        metrics_map = self._load_stock_metrics_for_codes(
            codes=sorted(union_codes),
            target_date=target_date.isoformat(),
            amount_window_len=20,
            return_offsets=(5, 20),
        )

        market_phase_payload: Optional[dict[str, Any]] = None
        market_upwave_ok = False
        try:
            from neotrade3.analysis.market_phase import detect_market_phase, MarketPhase

            mp = detect_market_phase(
                db_path=str(
                    Path(os.environ.get("NEOTRADE3_STOCK_DB_PATH") or str(self._stock_db_default_path)).expanduser()
                ),
                target_date=target_date.isoformat(),
                lookback_days=60,
            )
            market_phase_payload = {
                "phase": str(mp.phase.value),
                "confidence": float(mp.confidence),
                "market_breadth": float(mp.market_breadth),
                "amount_trend": str(mp.amount_trend),
            }
            market_upwave_ok = bool(mp.phase == MarketPhase.BULL and float(mp.confidence) >= 0.55)
        except Exception:
            market_phase_payload = None
            market_upwave_ok = False

        def _rank01(values_by_code: dict[str, float]) -> dict[str, float]:
            items = [(k, float(v)) for k, v in values_by_code.items() if k and isinstance(v, (int, float))]
            items.sort(key=lambda x: x[1])
            n = len(items)
            if n <= 1:
                return {k: 1.0 for k, _ in items}
            out: dict[str, float] = {}
            for i, (k, _v) in enumerate(items):
                out[k] = float(i) / float(n - 1)
            return out

        sectors: list[dict[str, Any]] = []
        for t in themes:
            if not isinstance(t, dict):
                continue
            theme_id = str(t.get("theme_id") or "")
            theme_name = str(t.get("name") or theme_id)
            members = t.get("members")
            member_set = {str(x) for x in members} if isinstance(members, list) else set()

            member_codes = [str(x).strip() for x in member_set if str(x).strip()]
            member_metrics = [metrics_map.get(code) for code in member_codes if code in metrics_map]
            member_metrics = [m for m in member_metrics if isinstance(m, dict)]
            if not member_metrics:
                continue

            money_ratio_by_code: dict[str, float] = {}
            ret5_by_code: dict[str, float] = {}
            ret20_by_code: dict[str, float] = {}
            cap_by_code: dict[str, float] = {}
            for m in member_metrics:
                code = str(m.get("code") or "").strip()
                if not code:
                    continue
                amount_today = float(m.get("amount_today") or 0.0)
                avg_amount = float(m.get("avg_amount_window") or 0.0)
                ratio = amount_today / max(avg_amount, 1e-9)
                money_ratio_by_code[code] = float(ratio)
                r5 = m.get("return_d1")
                r20 = m.get("return_d2")
                ret5_by_code[code] = float(r5) if isinstance(r5, (int, float)) else 0.0
                ret20_by_code[code] = float(r20) if isinstance(r20, (int, float)) else 0.0
                mcap = m.get("circulating_market_cap")
                if not isinstance(mcap, (int, float)) or float(mcap) <= 0:
                    mcap = m.get("total_market_cap")
                cap_by_code[code] = float(mcap) if isinstance(mcap, (int, float)) else 0.0

            money_rank = _rank01(money_ratio_by_code)
            ret5_rank = _rank01(ret5_by_code)
            ret20_rank = _rank01(ret20_by_code)
            cap_rank = _rank01(cap_by_code)

            positive_ret5 = [code for code, v in ret5_by_code.items() if isinstance(v, (int, float)) and float(v) > 0]
            diffusion = float(len(positive_ret5)) / float(max(1, len(ret5_by_code)))

            def _median(values: list[float]) -> float:
                vals = sorted([float(v) for v in values if isinstance(v, (int, float))])
                n = len(vals)
                if n == 0:
                    return 0.0
                mid = n // 2
                if n % 2 == 1:
                    return float(vals[mid])
                return float((vals[mid - 1] + vals[mid]) / 2.0)

            cap_median = _median(list(cap_by_code.values()))

            leader_potential: list[tuple[str, float]] = []
            core_potential: list[tuple[str, float]] = []
            for code in ret5_by_code.keys():
                lp = float(0.45 * money_rank.get(code, 0.0) + 0.35 * ret5_rank.get(code, 0.0) + 0.20 * ret20_rank.get(code, 0.0))
                cp = float(0.35 * cap_rank.get(code, 0.0) + 0.35 * money_rank.get(code, 0.0) + 0.30 * ret20_rank.get(code, 0.0))
                leader_potential.append((code, lp))
                core_potential.append((code, cp))
            leader_potential.sort(key=lambda x: x[1], reverse=True)
            core_potential.sort(key=lambda x: x[1], reverse=True)

            leader_codes = [c for c, _ in leader_potential[:2] if c]
            core_codes: list[str] = []
            for c, _ in core_potential:
                if c in leader_codes:
                    continue
                if cap_median > 0 and float(cap_by_code.get(c) or 0.0) < cap_median:
                    continue
                core_codes.append(c)
                if len(core_codes) >= 5:
                    break
            if len(core_codes) < 5:
                for c, _ in core_potential:
                    if c in leader_codes or c in core_codes:
                        continue
                    core_codes.append(c)
                    if len(core_codes) >= 5:
                        break

            follower_codes: list[str] = []
            for c, _ in leader_potential:
                if c in leader_codes or c in core_codes:
                    continue
                follower_codes.append(c)
                if len(follower_codes) >= 7:
                    break

            top3_ret5 = sorted([float(ret5_by_code.get(c) or 0.0) for c in leader_codes + core_codes], reverse=True)[:3]
            top3_ratio = sorted([float(money_ratio_by_code.get(c) or 0.0) for c in leader_codes + core_codes], reverse=True)[:3]
            avg_top3_ret5 = float(sum(top3_ret5) / float(max(1, len(top3_ret5))))
            avg_top3_ratio = float(sum(top3_ratio) / float(max(1, len(top3_ratio))))
            concept_upwave_ok = bool(diffusion >= 0.6 and avg_top3_ret5 >= 2.0 and avg_top3_ratio >= 1.1)

            concept_upwave_payload = {
                "status": ("upwave" if concept_upwave_ok else "not_upwave"),
                "diffusion": float(round(diffusion, 4)),
                "avg_top3_return_5d": float(round(avg_top3_ret5, 4)),
                "avg_top3_money_ratio": float(round(avg_top3_ratio, 4)),
            }

            def build_stock_payload(code: str, role_label: str) -> dict[str, Any]:
                m = metrics_map.get(code) if isinstance(metrics_map, dict) else None
                c = candidate_by_code.get(code)
                name = str(getattr(c, "name", "") or "") if c is not None else str(m.get("name") or "") if isinstance(m, dict) else ""
                buy_score = float(getattr(c, "buy_score", 0.0) or 0.0) if c is not None else None
                resonance = float(getattr(c, "sector_resonance", 0.0) or 0.0) if c is not None else 0.0
                ret5 = float(getattr(c, "ret_5d", 0.0) or 0.0) if c is not None else float(m.get("return_d1") or 0.0) if isinstance(m, dict) else 0.0
                ret20 = float(m.get("return_d2") or 0.0) if isinstance(m, dict) else 0.0
                amount_today = float(m.get("amount_today") or 0.0) if isinstance(m, dict) else 0.0
                avg_amount = float(m.get("avg_amount_window") or 0.0) if isinstance(m, dict) else 0.0
                money_ratio = float(amount_today / max(avg_amount, 1e-9))
                mcap = m.get("circulating_market_cap") if isinstance(m, dict) else None
                if not isinstance(mcap, (int, float)) or float(mcap) <= 0:
                    mcap = m.get("total_market_cap") if isinstance(m, dict) else None
                mcap_f = float(mcap) if isinstance(mcap, (int, float)) else None

                sell_signal = False
                sell_reason = None
                if include_sell_signal and code in positions and isinstance(positions.get(code), dict):
                    trade = self._lowfreq_trade_from_payload(positions[code])
                    sell = engine.check_sell_signal_v2(trade, target_date)
                    positions[code] = self._lowfreq_trade_to_payload(trade)
                    if sell:
                        sell_signal = True
                        sell_reason = sell.details

                sector_name = theme_name
                cooldown_info = cooldown_cache.get(sector_name)
                if cooldown_info is None:
                    try:
                        raw = engine._sector_cooldown_confirmed(sector_name, target_date)
                        cooldown_info = raw if isinstance(raw, dict) else {}
                    except Exception:
                        cooldown_info = {}
                    cooldown_cache[sector_name] = cooldown_info
                cooldown_confirmed = bool(cooldown_info.get("confirmed")) if isinstance(cooldown_info, dict) else False
                cooldown_hits = 0
                if isinstance(cooldown_info, dict):
                    try:
                        cooldown_hits = int(cooldown_info.get("hits") or 0)
                    except Exception:
                        cooldown_hits = 0
                risk_level = "exit" if (sell_signal or cooldown_confirmed) else "warn" if cooldown_hits > 0 else "ok"
                risk_reason: Optional[str] = None
                if sell_signal:
                    risk_reason = str(sell_reason or "个股卖出信号")
                elif cooldown_confirmed:
                    risk_reason = "冷却确认成立"
                elif cooldown_hits > 0:
                    risk_reason = "当日命中但未确认"

                stock_upwave_ok = bool(ret20 > 0 and ret5 > 0 and money_ratio >= 1.05)
                buy_signal = False
                if isinstance(buy_score, (int, float)):
                    buy_signal = bool(
                        float(buy_score) >= float(engine.BUY_THRESHOLD)
                        and role_label in {"龙头", "中军"}
                        and float(resonance) >= float(engine.MIN_RESONANCE)
                        and market_upwave_ok
                        and concept_upwave_ok
                        and stock_upwave_ok
                    )

                confidence_prob = None
                confidence_samples = 0
                if isinstance(buy_score, (int, float)):
                    bucket_key = self._confidence_bucket_key(
                        raw_score=float(buy_score),
                        role=str(role_label),
                        risk_level=risk_level,
                        market_regime=market_regime,
                    )
                    bucket = calibration_map.get(bucket_key)
                    confidence_prob = float(bucket.get("confidence_prob")) if isinstance(bucket, dict) else None
                    confidence_samples = int(bucket.get("n")) if isinstance(bucket, dict) else 0

                return {
                    "code": code,
                    "name": name,
                    "certainty": float(buy_score) if isinstance(buy_score, (int, float)) else None,
                    "buy_score": float(buy_score) if isinstance(buy_score, (int, float)) else None,
                    "sector": sector_name,
                    "role": role_label,
                    "reasons": list(getattr(c, "buy_reasons", []) or []) if c is not None else [],
                    "cup_handle_ok": bool(getattr(c, "cup_handle_ok", False)) if c is not None else False,
                    "resonance": float(resonance),
                    "wave_phase": str(getattr(c, "wave_phase", "") or "") if c is not None else "",
                    "return_5d": float(ret5),
                    "buy_signal": bool(buy_signal),
                    "sell_signal": bool(sell_signal),
                    "sell_reason": sell_reason,
                    "risk_level": risk_level,
                    "risk_reason": risk_reason,
                    "confidence_prob": confidence_prob,
                    "confidence_samples": confidence_samples,
                    "suggested_entry": "今日" if buy_signal else None,
                    "role_scores": {
                        "money_ratio": float(round(money_ratio, 4)),
                        "money_rank": float(round(money_rank.get(code, 0.0), 4)),
                        "cap": mcap_f,
                        "cap_rank": float(round(cap_rank.get(code, 0.0), 4)),
                        "return_5d_rank": float(round(ret5_rank.get(code, 0.0), 4)),
                        "return_20d_rank": float(round(ret20_rank.get(code, 0.0), 4)),
                    },
                    "upwave_gate": {
                        "market_ok": bool(market_upwave_ok),
                        "concept_ok": bool(concept_upwave_ok),
                        "stock_ok": bool(stock_upwave_ok),
                    },
                    "manual": {
                        "abandoned": code in abandoned_codes,
                        "buy_intent_pending": code in pending_buy_by_code,
                        "buy_execute_date": (
                            str(pending_buy_by_code.get(code, {}).get("execute_date") or "")
                            if code in pending_buy_by_code
                            else None
                        ),
                        "intent_id": (
                            str(pending_buy_by_code.get(code, {}).get("intent_id") or "")
                            if code in pending_buy_by_code
                            else None
                        ),
                    },
                }

            leaders_payload = [build_stock_payload(c, "龙头") for c in leader_codes if c]
            middle_payload = [build_stock_payload(c, "中军") for c in core_codes if c]
            followers_payload = [build_stock_payload(c, "跟随") for c in follower_codes if c]

            heat_candidates = [*leaders_payload, *middle_payload]
            heat_scores = [float(x.get("buy_score")) for x in heat_candidates if isinstance(x, dict) and isinstance(x.get("buy_score"), (int, float))]
            heat_scores.sort(reverse=True)
            if heat_scores:
                avg_top5_buy = float(sum(heat_scores[:5]) / float(max(1, min(5, len(heat_scores)))))
            else:
                ret_list = [float(x.get("return_5d") or 0.0) for x in heat_candidates if isinstance(x, dict)]
                ret_list.sort(reverse=True)
                avg_top5_buy = float(sum(ret_list[:5]) / float(max(1, min(5, len(ret_list)))))
            heat_score = float(max(0.0, min(100.0, float(avg_top5_buy) + float(diffusion) * 10.0)))

            sectors.append(
                {
                    "code": theme_id,
                    "name": theme_name,
                    "sector_lv1": theme_name,
                    "sector_lv2": theme_name,
                    "heat_score": float(round(heat_score, 4)),
                    "leaders": leaders_payload[:3],
                    "middle": middle_payload[:5],
                    "followers": followers_payload[:7],
                    "upwave": concept_upwave_payload,
                    "meta": {
                        "theme_id": theme_id,
                        "stale_days": stale_days,
                        "member_count": len(member_set),
                        "diffusion": float(round(diffusion, 4)),
                    },
                }
            )

        sectors.sort(key=lambda x: float(x.get("heat_score") or 0.0), reverse=True)

        base: dict[str, Any] = {
            "_meta": {
                "status": "ok",
                "mode": "team_theme",
                "stale_days": stale_days,
                "snapshot_date": str(snapshot.get("target_date") or ""),
                "market_phase": market_phase_payload,
            },
            "date": target_date.isoformat(),
            "sectors": sectors,
        }

        if include_portfolio or include_sell_signal:
            state = self._load_lowfreq_sim_state()
            base["portfolio"] = self._lowfreq_portfolio_view(
                engine=engine,
                state=state,
                target_date=target_date,
            )
            self._save_lowfreq_sim_state(state)
        return base

    def _rolling_window_start_date(self, *, end_date: str, window_len: int) -> str:
        db_path = Path(
            os.environ.get("NEOTRADE3_STOCK_DB_PATH") or str(self._stock_db_default_path)
        ).expanduser()
        conn = sqlite3.connect(str(db_path))
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT trade_date FROM trading_calendar_cache WHERE trade_date <= ? ORDER BY trade_date DESC LIMIT ?",
                (end_date, int(window_len)),
            )
            rows = cursor.fetchall()
        finally:
            conn.close()
        dates = [str(r[0]) for r in rows if r and r[0]]
        if len(dates) < int(window_len):
            raise ApiError(
                status_code=HTTPStatus.SERVICE_UNAVAILABLE,
                code="insufficient_trading_days",
                message="insufficient trading days in trading_calendar_cache",
                details={"end_date": end_date, "got": len(dates), "need": int(window_len)},
            )
        return dates[-1]

    def _trading_day_at_offset(self, *, end_date: str, offset: int) -> Optional[str]:
        db_path = Path(
            os.environ.get("NEOTRADE3_STOCK_DB_PATH") or str(self._stock_db_default_path)
        ).expanduser()
        conn = sqlite3.connect(str(db_path))
        try:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "SELECT trade_date FROM trading_calendar_cache WHERE trade_date <= ? ORDER BY trade_date DESC LIMIT 1 OFFSET ?",
                    (end_date, int(offset)),
                )
                row = cursor.fetchone()
                if row and row[0]:
                    return str(row[0])
            except Exception:
                row = None
            cursor.execute(
                "SELECT trade_date FROM (SELECT DISTINCT trade_date FROM daily_prices WHERE trade_date <= ?) ORDER BY trade_date DESC LIMIT 1 OFFSET ?",
                (end_date, int(offset)),
            )
            row = cursor.fetchone()
            return str(row[0]) if row and row[0] else None
        finally:
            conn.close()

    def _load_stock_metrics_for_codes(
        self,
        *,
        codes: list[str],
        target_date: str,
        amount_window_len: int = 20,
        return_offsets: tuple[int, int] = (5, 20),
    ) -> dict[str, dict[str, Any]]:
        codes_norm = [str(c).strip() for c in (codes or []) if str(c).strip()]
        codes_norm = sorted(set(codes_norm))
        if not codes_norm:
            return {}

        close_offset_1, close_offset_2 = int(return_offsets[0]), int(return_offsets[1])
        date_1 = self._trading_day_at_offset(end_date=target_date, offset=close_offset_1)
        date_2 = self._trading_day_at_offset(end_date=target_date, offset=close_offset_2)
        try:
            amount_start = self._rolling_window_start_date(end_date=target_date, window_len=int(amount_window_len))
        except Exception:
            amount_start = target_date

        db_path = Path(
            os.environ.get("NEOTRADE3_STOCK_DB_PATH") or str(self._stock_db_default_path)
        ).expanduser()
        conn = sqlite3.connect(str(db_path))
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            placeholders = ",".join("?" * len(codes_norm))

            basics: dict[str, dict[str, Any]] = {}
            cursor.execute(
                f"""
                SELECT code, name, total_market_cap, circulating_market_cap, sector_lv1
                FROM stocks
                WHERE code IN ({placeholders})
                """,
                tuple(codes_norm),
            )
            for row in cursor.fetchall():
                code = str(row["code"] or "").strip()
                if not code:
                    continue
                basics[code] = {
                    "code": code,
                    "name": str(row["name"] or ""),
                    "total_market_cap": (float(row["total_market_cap"]) if row["total_market_cap"] is not None else None),
                    "circulating_market_cap": (float(row["circulating_market_cap"]) if row["circulating_market_cap"] is not None else None),
                    "sector_lv1": str(row["sector_lv1"] or ""),
                }

            date_1_s = str(date_1) if date_1 else None
            date_2_s = str(date_2) if date_2 else None
            if date_1_s is None:
                date_1_s = target_date
            if date_2_s is None:
                date_2_s = target_date

            cursor.execute(
                f"""
                SELECT
                  code,
                  AVG(CASE WHEN trade_date BETWEEN ? AND ? THEN amount END) AS avg_amount_window,
                  MAX(CASE WHEN trade_date = ? THEN amount END) AS amount_today,
                  MAX(CASE WHEN trade_date = ? THEN close END) AS close_today,
                  MAX(CASE WHEN trade_date = ? THEN close END) AS close_d1,
                  MAX(CASE WHEN trade_date = ? THEN close END) AS close_d2
                FROM daily_prices
                WHERE code IN ({placeholders})
                  AND trade_date BETWEEN ? AND ?
                GROUP BY code
                """,
                (
                    str(amount_start),
                    str(target_date),
                    str(target_date),
                    str(target_date),
                    date_1_s,
                    date_2_s,
                    *codes_norm,
                    str(amount_start),
                    str(target_date),
                ),
            )
            out: dict[str, dict[str, Any]] = {}
            for row in cursor.fetchall():
                code = str(row["code"] or "").strip()
                if not code:
                    continue
                base = basics.get(code, {"code": code, "name": ""})
                close_today = float(row["close_today"]) if row["close_today"] is not None else None
                close_d1 = float(row["close_d1"]) if row["close_d1"] is not None else None
                close_d2 = float(row["close_d2"]) if row["close_d2"] is not None else None
                ret_1 = None
                if close_today is not None and close_d1 is not None and close_d1 > 0:
                    ret_1 = (close_today - close_d1) / close_d1 * 100.0
                ret_2 = None
                if close_today is not None and close_d2 is not None and close_d2 > 0:
                    ret_2 = (close_today - close_d2) / close_d2 * 100.0
                out[code] = {
                    **base,
                    "avg_amount_window": (float(row["avg_amount_window"]) if row["avg_amount_window"] is not None else None),
                    "amount_today": (float(row["amount_today"]) if row["amount_today"] is not None else None),
                    "close_today": close_today,
                    "close_d1": close_d1,
                    "close_d2": close_d2,
                    "return_d1": ret_1,
                    "return_d2": ret_2,
                    "return_d1_offset": close_offset_1,
                    "return_d2_offset": close_offset_2,
                    "amount_window_start": str(amount_start),
                }
            return out
        finally:
            conn.close()

    def _write_daily_run_ledger(self, *, target_date: str, payload: dict[str, Any]) -> str:
        self._daily_runs_dir.mkdir(parents=True, exist_ok=True)
        path = self._daily_runs_dir / f"{target_date}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return str(path)

    def daily_pipeline_run_view(self, *, target_date: str, requested_by: str) -> dict[str, Any]:
        started_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        steps: list[dict[str, Any]] = []
        ledger: dict[str, Any] = {
            "version": 1,
            "target_date": target_date,
            "requested_by": requested_by,
            "started_at": started_at,
            "steps": steps,
        }

        def add_step(
            step_id: str,
            status: str,
            *,
            outputs: Optional[dict[str, Any]] = None,
            error: Optional[str] = None,
            elapsed_ms: Optional[float] = None,
        ) -> None:
            steps.append(
                {
                    "step_id": step_id,
                    "status": status,
                    "elapsed_ms": float(elapsed_ms) if elapsed_ms is not None else None,
                    "outputs": outputs or {},
                    "error": error,
                }
            )

        trade_date: Optional[str] = None
        calendar_is_trading_day = False
        publish_ok = False
        t0 = time.perf_counter()
        try:
            out = self.update_daily_prices_tencent_view(
                target_date=target_date,
                requested_by=requested_by,
                dry_run=False,
            )
            tencent_update = out.get("tencent_update") or {}
            trade_date = tencent_update.get("trade_date")
            calendar_is_trading_day = bool(tencent_update.get("calendar_is_trading_day"))
            publish_ok = bool((tencent_update.get("quality_gate") or {}).get("passed"))
            add_step(
                "tencent_update",
                "ok",
                outputs={
                    "trade_date": trade_date,
                    "calendar_is_trading_day": calendar_is_trading_day,
                    "publish_ok": publish_ok,
                    "capture_batch_id": tencent_update.get("capture_batch_id"),
                    "publish_batch_id": tencent_update.get("publish_batch_id"),
                },
                elapsed_ms=(time.perf_counter() - t0) * 1000.0,
            )
        except ApiError as exc:
            add_step(
                "tencent_update",
                "failed",
                outputs={"error_code": exc.code, "error_details": exc.details},
                error=exc.message,
                elapsed_ms=(time.perf_counter() - t0) * 1000.0,
            )
        except Exception as exc:
            add_step(
                "tencent_update",
                "failed",
                outputs={"error_type": type(exc).__name__},
                error=str(exc),
                elapsed_ms=(time.perf_counter() - t0) * 1000.0,
            )

        end_date: Optional[str] = None
        if trade_date and calendar_is_trading_day and publish_ok:
            if str(trade_date) == str(target_date):
                end_date = str(target_date)
            else:
                db_path = Path(
                    os.environ.get("NEOTRADE3_STOCK_DB_PATH") or str(self._stock_db_default_path)
                ).expanduser()
                try:
                    conn = sqlite3.connect(str(db_path))
                    try:
                        row = conn.execute(
                            "SELECT COUNT(1) FROM daily_prices WHERE trade_date = ?",
                            (str(target_date),),
                        ).fetchone()
                        target_rows = int(row[0] or 0) if row else 0
                    finally:
                        conn.close()
                except Exception:
                    target_rows = 0
                if target_rows > 0:
                    end_date = str(target_date)
                else:
                    add_step(
                        "tencent_update",
                        "failed",
                        outputs={
                            "trade_date": trade_date,
                            "target_date": target_date,
                            "reason": "target_date_missing_after_mismatch_backfill",
                        },
                        error="target_date data missing after tencent trade_date mismatch backfill",
                    )

        if not end_date:
            ledger["finished_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            path = self._write_daily_run_ledger(target_date=target_date, payload=ledger)
            return {"_meta": {"status": "ok"}, "ledger_path": path, "ledger": ledger}

        t1 = time.perf_counter()
        try:
            health = self.tushare_concept_health_view(requested_by=requested_by)
            add_step(
                "tushare_health",
                "ok" if bool(health.get("ok")) else "failed",
                outputs={
                    "ok": health.get("ok"),
                    "elapsed_ms": health.get("elapsed_ms"),
                    "checks": health.get("checks"),
                    "errors": health.get("errors"),
                },
                elapsed_ms=(time.perf_counter() - t1) * 1000.0,
            )
        except Exception as exc:
            add_step(
                "tushare_health",
                "failed",
                error=str(exc),
                elapsed_ms=(time.perf_counter() - t1) * 1000.0,
            )

        t2 = time.perf_counter()
        try:
            snap = self.refresh_team_theme_snapshot_view(
                target_date=end_date,
                requested_by=requested_by,
            )
            add_step(
                "team_theme_snapshot",
                "ok",
                outputs={"snapshot_path": snap.get("snapshot_path")},
                elapsed_ms=(time.perf_counter() - t2) * 1000.0,
            )
        except Exception as exc:
            add_step(
                "team_theme_snapshot",
                "failed",
                error=str(exc),
                elapsed_ms=(time.perf_counter() - t2) * 1000.0,
            )

        t2b = time.perf_counter()
        try:
            out = self.ths_concept_mainline_compute_view(
                trade_date=end_date,
                requested_by=requested_by,
                top_n=10,
            )
            add_step(
                "ths_concept_mainline",
                "ok" if str(out.get("status")) == "ok" else "failed",
                outputs={
                    "status": out.get("status"),
                    "trade_date": out.get("trade_date"),
                    "concept_count": out.get("concept_count"),
                    "top_mainline": out.get("top_mainline"),
                    "reason": out.get("reason"),
                },
                elapsed_ms=(time.perf_counter() - t2b) * 1000.0,
            )
        except Exception as exc:
            add_step(
                "ths_concept_mainline",
                "failed",
                error=str(exc),
                elapsed_ms=(time.perf_counter() - t2b) * 1000.0,
            )

        t3 = time.perf_counter()
        try:
            bulk = self.screeners_bulk_run_view(
                target_date=end_date,
                screener_ids=None,
                requested_by=requested_by,
                parameters=None,
                dry_run=False,
                async_run=False,
            )
            add_step(
                "screeners_bulk_run",
                "ok",
                outputs={"status": (bulk.get("_meta") or {}).get("status")},
                elapsed_ms=(time.perf_counter() - t3) * 1000.0,
            )
        except Exception as exc:
            add_step(
                "screeners_bulk_run",
                "failed",
                error=str(exc),
                elapsed_ms=(time.perf_counter() - t3) * 1000.0,
            )

        t4 = time.perf_counter()
        try:
            engine = self._lowfreq_engine_v16()
            state = self._load_lowfreq_sim_state()
            before_last = state.get("last_date")
            before_positions = len(state.get("positions") or {})
            before_closed = len(state.get("closed_trades") or [])
            before_pending = 0
            manual0 = state.get("manual") if isinstance(state.get("manual"), dict) else {"intents": []}
            intents0 = manual0.get("intents") if isinstance(manual0.get("intents"), list) else []
            for it in intents0:
                if not isinstance(it, dict):
                    continue
                if str(it.get("status") or "pending") != "pending":
                    continue
                if str(it.get("requested_date") or "").strip() != end_date:
                    continue
                if str(it.get("intent_type") or "") not in {"buy_intent", "sell_intent"}:
                    continue
                before_pending += 1
            self._advance_lowfreq_sim_state(
                state=state,
                engine=engine,
                target_date=date.fromisoformat(end_date),
            )
            self._save_lowfreq_sim_state(state)
            settings = state.get("settings") if isinstance(state.get("settings"), dict) else {}
            autopilot_enabled = bool(settings.get("autopilot_enabled"))
            after_pending = 0
            manual1 = state.get("manual") if isinstance(state.get("manual"), dict) else {"intents": []}
            intents1 = manual1.get("intents") if isinstance(manual1.get("intents"), list) else []
            for it in intents1:
                if not isinstance(it, dict):
                    continue
                if str(it.get("status") or "pending") != "pending":
                    continue
                if str(it.get("requested_date") or "").strip() != end_date:
                    continue
                if str(it.get("intent_type") or "") not in {"buy_intent", "sell_intent"}:
                    continue
                after_pending += 1
            add_step(
                "lowfreq_sim_daily",
                "ok",
                outputs={
                    "before_last_date": before_last,
                    "after_last_date": state.get("last_date"),
                    "positions_before": before_positions,
                    "positions_after": len(state.get("positions") or {}),
                    "closed_trades_before": before_closed,
                    "closed_trades_after": len(state.get("closed_trades") or []),
                    "autopilot_enabled": autopilot_enabled,
                    "pending_intents_before": before_pending,
                    "pending_intents_after": after_pending,
                },
                elapsed_ms=(time.perf_counter() - t4) * 1000.0,
            )
        except Exception as exc:
            add_step(
                "lowfreq_sim_daily",
                "failed",
                error=str(exc),
                elapsed_ms=(time.perf_counter() - t4) * 1000.0,
            )

        t5_conf = time.perf_counter()
        try:
            out = self.lowfreq_confidence_daily_run_view(
                target_date=end_date,
                requested_by=requested_by,
                max_label_updates=200,
            )
            add_step(
                "confidence_daily",
                "ok",
                outputs={
                    "date": out.get("date"),
                    "market_regime": out.get("market_regime"),
                    "observations_written": out.get("observations_written"),
                    "labels_updated": out.get("labels_updated"),
                    "buckets_written": out.get("buckets_written"),
                },
                elapsed_ms=(time.perf_counter() - t5_conf) * 1000.0,
            )
        except Exception as exc:
            add_step(
                "confidence_daily",
                "failed",
                error=str(exc),
                elapsed_ms=(time.perf_counter() - t5_conf) * 1000.0,
            )

        t5 = time.perf_counter()
        report_id: Optional[str] = None
        backtest_summary: Optional[dict[str, Any]] = None
        start_date: Optional[str] = None
        try:
            start_date = self._rolling_window_start_date(end_date=end_date, window_len=60)
            report_id = f"lowfreq_v16_roll60_{start_date}_{end_date}__{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
            backtest = self.lowfreq_backtest_run_view(
                requested_by=requested_by,
                report_id=report_id,
                start_date=start_date,
                end_date=end_date,
                async_run=False,
                overrides=None,
            )
            backtest_summary = backtest.get("summary") if isinstance(backtest, dict) else None
            add_step(
                "lowfreq_backtest_roll60",
                "ok",
                outputs={
                    "report_id": report_id,
                    "start_date": start_date,
                    "end_date": end_date,
                    "pdf_url": backtest.get("pdf_url"),
                },
                elapsed_ms=(time.perf_counter() - t5) * 1000.0,
            )
        except Exception as exc:
            add_step(
                "lowfreq_backtest_roll60",
                "failed",
                error=str(exc),
                elapsed_ms=(time.perf_counter() - t5) * 1000.0,
            )

        t6 = time.perf_counter()
        try:
            opt = self.lowfreq_daily_auto_optimize_view(
                requested_by=requested_by,
                end_date=end_date,
                window_len=60,
                dd_limit_pct=10.0,
            )
            add_step(
                "auto_optimize",
                "ok",
                outputs={
                    "run_id": opt.get("run_id"),
                    "selected_overrides": opt.get("selected_overrides"),
                    "effective_from": opt.get("effective_from"),
                },
                elapsed_ms=(time.perf_counter() - t6) * 1000.0,
            )
        except Exception as exc:
            add_step(
                "auto_optimize",
                "failed",
                error=str(exc),
                elapsed_ms=(time.perf_counter() - t6) * 1000.0,
            )

        ledger["finished_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        ledger["trade_date"] = end_date
        ledger["backtest"] = {
            "report_id": report_id,
            "start_date": start_date,
            "end_date": end_date,
            "summary": backtest_summary,
        }
        path = self._write_daily_run_ledger(target_date=end_date, payload=ledger)
        return {"_meta": {"status": "ok"}, "ledger_path": path, "ledger": ledger}

    def lowfreq_daily_auto_optimize_view(
        self,
        *,
        requested_by: str,
        end_date: str,
        window_len: int = 60,
        dd_limit_pct: float = 10.0,
    ) -> dict[str, Any]:
        self._auto_opt_dir.mkdir(parents=True, exist_ok=True)

        end_date = str(end_date).strip()
        start_date = self._rolling_window_start_date(end_date=end_date, window_len=int(window_len))
        start_dt = date.fromisoformat(start_date)
        end_dt = date.fromisoformat(end_date)

        run_id = f"autoopt_{end_date}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}"
        grid: list[dict[str, Any]] = []
        for buy_threshold in (85.0, 90.0, 95.0):
            for max_pos in (2, 3):
                for reb_days in (15, 20):
                    grid.append(
                        {
                            "BUY_THRESHOLD": float(buy_threshold),
                            "MAX_POSITIONS": int(max_pos),
                            "REBALANCE_DAYS": int(reb_days),
                        }
                    )

        results: list[dict[str, Any]] = []
        best: Optional[dict[str, Any]] = None
        for params in grid:
            engine = self._lowfreq_engine_v16()
            for k, v in params.items():
                setattr(engine, str(k), v)
            metrics, _trades = self._lowfreq_backtest_with_trades(
                engine=engine,
                start_date=start_dt,
                end_date=end_dt,
                initial_capital=1_000_000.0,
            )
            dd = float(metrics.get("max_drawdown_pct") or 0.0)
            tr = float(metrics.get("total_return_pct") or 0.0)
            feasible = dd <= float(dd_limit_pct)
            rec = {
                "feasible": bool(feasible),
                "total_return_pct": tr,
                "max_drawdown_pct": dd,
                "params": params,
            }
            results.append(rec)
            if feasible:
                if best is None:
                    best = rec
                else:
                    if float(rec.get("total_return_pct") or 0.0) > float(best.get("total_return_pct") or 0.0):
                        best = rec

        effective_from: Optional[str] = None
        try:
            conn = sqlite3.connect(str(self._stock_db_default_path))
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT MIN(trade_date) FROM trading_calendar_cache WHERE trade_date > ?",
                    (end_date,),
                )
                row = cursor.fetchone()
                effective_from = str(row[0]) if row and row[0] else None
            finally:
                conn.close()
        except Exception:
            effective_from = None

        selected_overrides = best.get("params") if isinstance(best, dict) else None
        if isinstance(selected_overrides, dict):
            self._lowfreq_sim_overrides_file.parent.mkdir(parents=True, exist_ok=True)
            self._lowfreq_sim_overrides_file.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "run_id": run_id,
                        "requested_by": requested_by,
                        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "window": {"start_date": start_date, "end_date": end_date, "trading_days": int(window_len)},
                        "dd_limit_pct": float(dd_limit_pct),
                        "effective_from": effective_from,
                        "overrides": selected_overrides,
                        "selected_metrics": {
                            "total_return_pct": float(best.get("total_return_pct") or 0.0),
                            "max_drawdown_pct": float(best.get("max_drawdown_pct") or 0.0),
                        },
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

        ledger_path = self._auto_opt_dir / f"{end_date}.json"
        ledger_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "run_id": run_id,
                    "requested_by": requested_by,
                    "target_end_date": end_date,
                    "window": {"start_date": start_date, "end_date": end_date, "trading_days": int(window_len)},
                    "dd_limit_pct": float(dd_limit_pct),
                    "results": results,
                    "selected": best,
                    "effective_from": effective_from,
                    "overrides_path": str(self._lowfreq_sim_overrides_file)
                    if isinstance(selected_overrides, dict)
                    else None,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        return {
            "_meta": {"status": "ok"},
            "run_id": run_id,
            "start_date": start_date,
            "end_date": end_date,
            "dd_limit_pct": float(dd_limit_pct),
            "selected_overrides": selected_overrides,
            "effective_from": effective_from,
            "ledger_path": str(ledger_path),
        }

    def lowfreq_optimize_thresholds_view(
        self,
        *,
        requested_by: str = "api",
        dd_limits: Optional[list[float]] = None,
        max_trades: Optional[int] = None,
        coarse_trials: int = 30,
        fine_trials: int = 10,
        seed: int = 20260528,
        window_len: int = 60,
        top_n: int = 3,
        b2_threshold_pct: float = 5.0,
        capture_window_trading_days: int = 5,
        opportunity_max_return_cap_pct: float = 300.0,
    ) -> dict[str, Any]:
        import hashlib
        import random

        if dd_limits is None:
            dd_limits = [15.0, 18.0, 20.0]
        dd_limits = [float(x) for x in dd_limits]

        if max_trades is not None and int(max_trades) <= 0:
            raise ApiError(
                status_code=HTTPStatus.BAD_REQUEST,
                code="invalid_max_trades",
                message="max_trades must be > 0 when provided",
            )

        if coarse_trials <= 0 or fine_trials < 0:
            raise ApiError(
                status_code=HTTPStatus.BAD_REQUEST,
                code="invalid_trials",
                message="coarse_trials must be > 0 and fine_trials must be >= 0",
            )

        start_key, end_key = self._lowfreq_trade_date_range()
        start_dt = date.fromisoformat(start_key)
        end_dt = date.fromisoformat(end_key)

        run_id = f"opt_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}"
        optimize_dir = self.project_root / "var/artifacts/lowfreq_optimize" / run_id
        optimize_dir.mkdir(parents=True, exist_ok=True)

        grid = []
        buy_thresholds = (85.0, 90.0, 95.0)
        max_positions = (2, 3)
        rebalance_days = (15, 20)
        sector_accel_enabled = (False, True)
        relative_strength_bonus_caps = (0.0, 4.0, 8.0)
        for rotation_delta in (8.0, 10.0, 12.0, 14.0, 16.0):
            for rotation_min_ret in (0.0, 5.0, 10.0):
                for stop_confirm in (1, 2, 3):
                    for cooldown_win, cooldown_hits in ((3, 2), (4, 2), (5, 3)):
                        for buy_threshold in buy_thresholds:
                            for max_pos in max_positions:
                                for reb_days in rebalance_days:
                                    for accel_enabled in sector_accel_enabled:
                                        for bonus_cap in relative_strength_bonus_caps:
                                            grid.append(
                                                {
                                                    "ROTATION_SCORE_DELTA": float(rotation_delta),
                                                    "ROTATION_MIN_RETURN_PCT": float(rotation_min_ret),
                                                    "STOP_LOSS_CONFIRM_DAYS": int(stop_confirm),
                                                    "SECTOR_COOLDOWN_CONFIRM_WINDOW": int(cooldown_win),
                                                    "SECTOR_COOLDOWN_CONFIRM_HITS": int(cooldown_hits),
                                                    "BUY_THRESHOLD": float(buy_threshold),
                                                    "MAX_POSITIONS": int(max_pos),
                                                    "REBALANCE_DAYS": int(reb_days),
                                                    "SECTOR_ACCEL_BONUS_ENABLED": bool(accel_enabled),
                                                    "RELATIVE_STRENGTH_BONUS_CAP": float(bonus_cap),
                                                }
                                            )

        rng = random.Random(int(seed))
        rng.shuffle(grid)

        def report_id_for(dd_limit: float, params: dict[str, object]) -> str:
            payload = json.dumps({"dd": dd_limit, "params": params}, sort_keys=True).encode("utf-8")
            h = hashlib.sha1(payload).hexdigest()[:10]
            return f"lowfreq_v16_{start_key}_{end_key}__{run_id}__dd{int(dd_limit)}__{h}"

        def run_one(dd_limit: float, params: dict[str, object]) -> dict[str, Any]:
            rid = report_id_for(dd_limit, params)

            engine = self._lowfreq_engine_v16()
            for k, v in params.items():
                setattr(engine, str(k), v)
            metrics, _trades = self._lowfreq_backtest_with_trades(
                engine=engine,
                start_date=start_dt,
                end_date=end_dt,
                initial_capital=1_000_000.0,
            )
            dd = float(metrics.get("max_drawdown_pct") or 0.0)
            tr = float(metrics.get("total_return_pct") or 0.0)
            trades_n = int(metrics.get("total_trades") or 0)
            feasible = dd <= float(dd_limit) and (max_trades is None or trades_n <= int(max_trades))
            return {
                "report_id": rid,
                "dd_limit": float(dd_limit),
                "feasible": bool(feasible),
                "total_return_pct": tr,
                "max_drawdown_pct": dd,
                "total_trades": trades_n,
                "params": params,
            }

        def local_neighbors(best_params: dict[str, object]) -> list[dict[str, object]]:
            neighbors: list[dict[str, object]] = []
            base_delta = float(best_params.get("ROTATION_SCORE_DELTA") or 0.0)
            base_min_ret = float(best_params.get("ROTATION_MIN_RETURN_PCT") or 0.0)
            base_stop = int(best_params.get("STOP_LOSS_CONFIRM_DAYS") or 1)
            base_win = int(best_params.get("SECTOR_COOLDOWN_CONFIRM_WINDOW") or 3)
            base_hits = int(best_params.get("SECTOR_COOLDOWN_CONFIRM_HITS") or 2)
            base_buy_threshold = float(best_params.get("BUY_THRESHOLD") or 0.0)
            base_max_positions = int(best_params.get("MAX_POSITIONS") or 0)
            base_rebalance_days = int(best_params.get("REBALANCE_DAYS") or 0)
            base_sector_accel = bool(best_params.get("SECTOR_ACCEL_BONUS_ENABLED") or False)
            base_rel_bonus_cap = float(best_params.get("RELATIVE_STRENGTH_BONUS_CAP") or 0.0)

            if base_buy_threshold <= 0:
                base_buy_threshold = 85.0
            if base_max_positions <= 0:
                base_max_positions = 3
            if base_rebalance_days <= 0:
                base_rebalance_days = 15

            for d in (-2.0, 0.0, 2.0):
                for m in (-2.0, 0.0, 2.0):
                    for s in (-1, 0, 1):
                        base_cand = {
                            "ROTATION_SCORE_DELTA": float(max(6.0, base_delta + d)),
                            "ROTATION_MIN_RETURN_PCT": float(max(0.0, base_min_ret + m)),
                            "STOP_LOSS_CONFIRM_DAYS": int(min(5, max(1, base_stop + s))),
                            "SECTOR_COOLDOWN_CONFIRM_WINDOW": int(base_win),
                            "SECTOR_COOLDOWN_CONFIRM_HITS": int(base_hits),
                            "BUY_THRESHOLD": float(base_buy_threshold),
                            "MAX_POSITIONS": int(base_max_positions),
                            "REBALANCE_DAYS": int(base_rebalance_days),
                        }
                        for accel_enabled in (base_sector_accel, (not base_sector_accel)):
                            for cap_delta in (-4.0, 0.0, 4.0):
                                cap = float(max(0.0, min(12.0, base_rel_bonus_cap + cap_delta)))
                                cand = dict(base_cand)
                                cand["SECTOR_ACCEL_BONUS_ENABLED"] = bool(accel_enabled)
                                cand["RELATIVE_STRENGTH_BONUS_CAP"] = float(cap)
                                neighbors.append(cand)
            rng.shuffle(neighbors)
            return neighbors

        all_results: list[dict[str, Any]] = []
        chosen_best: Optional[dict[str, Any]] = None
        chosen_dd_limit: Optional[float] = None

        for dd_limit in dd_limits:
            results: list[dict[str, Any]] = []
            tried: set[str] = set()
            for params in grid[: int(coarse_trials)]:
                key = json.dumps({"dd": dd_limit, "p": params}, sort_keys=True)
                if key in tried:
                    continue
                tried.add(key)
                results.append(run_one(dd_limit, params))

            feasible = [r for r in results if r.get("feasible")]
            feasible.sort(
                key=lambda r: (
                    -float(r.get("total_return_pct") or 0.0),
                    int(r.get("total_trades") or 0),
                )
            )
            best = feasible[0] if feasible else None

            if best is not None and int(fine_trials) > 0:
                for params in local_neighbors(best.get("params") or {})[: int(fine_trials)]:
                    key = json.dumps({"dd": dd_limit, "p": params}, sort_keys=True)
                    if key in tried:
                        continue
                    tried.add(key)
                    results.append(run_one(dd_limit, params))
                feasible = [r for r in results if r.get("feasible")]
                feasible.sort(
                    key=lambda r: (
                        -float(r.get("total_return_pct") or 0.0),
                        int(r.get("total_trades") or 0),
                    )
                )
                best = feasible[0] if feasible else None

            all_results.extend(results)
            if best is not None:
                chosen_best = best
                chosen_dd_limit = float(dd_limit)
                break

        if chosen_best is None:
            chosen_dd_limit = float(dd_limits[-1])
            all_results.sort(
                key=lambda r: (
                    float(r.get("max_drawdown_pct") or 1e9),
                    -float(r.get("total_return_pct") or 0.0),
                )
            )
            chosen_best = all_results[0] if all_results else None

        if chosen_best is None:
            raise ApiError(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                code="optimize_failed",
                message="no optimization results produced",
            )

        best_report_id = str(chosen_best.get("report_id") or "")
        best_params = chosen_best.get("params") or {}
        persisted: Optional[dict[str, Any]] = None
        try:
            persisted = self._save_lowfreq_model_params(
                model_id="lowfreq_engine_v16_advanced",
                params={str(k): v for k, v in best_params.items()},
                source=f"optimize:{run_id}",
                requested_by=requested_by,
            )
        except Exception:
            persisted = None
        self.lowfreq_backtest_run_view(
            start_date=start_key,
            end_date=end_key,
            requested_by=f"{requested_by}.optimize.{run_id}.best",
            report_id=best_report_id,
            overrides={k: v for k, v in best_params.items()},
        )

        best_report_path = self._lowfreq_backtest_artifacts_dir / best_report_id / "trades.json"
        best_payload: Optional[dict[str, Any]] = None
        try:
            best_payload = json.loads(best_report_path.read_text(encoding="utf-8"))
        except Exception:
            best_payload = None

        opportunity_eval: Optional[dict[str, Any]] = None
        opportunity_miss_analysis: Optional[dict[str, Any]] = None
        opportunity_top_missed_features: Optional[dict[str, Any]] = None
        if best_payload is not None:
            opportunity_eval = self._lowfreq_opportunity_coverage_view(
                start_date=start_key,
                end_date=end_key,
                trades_payload=best_payload,
                window_len=int(window_len),
                top_n=int(top_n),
                b2_threshold_pct=float(b2_threshold_pct),
                capture_window_trading_days=int(capture_window_trading_days),
                max_return_cap_pct=float(opportunity_max_return_cap_pct),
            )
            if isinstance(opportunity_eval, dict) and opportunity_eval.get("status") == "ok":
                opportunity_miss_analysis = self._lowfreq_opportunity_miss_analysis_view(
                    start_date=start_key,
                    end_date=end_key,
                    trades_payload=best_payload,
                    top_missed=(opportunity_eval.get("top_missed") or [])[:50],
                    capture_window_trading_days=int(capture_window_trading_days),
                    engine_overrides={str(k): v for k, v in (best_params or {}).items()},
                )
                opportunity_top_missed_features = self._lowfreq_opportunity_top_missed_features_view(
                    start_date=start_key,
                    end_date=end_key,
                    top_missed=(opportunity_eval.get("top_missed") or [])[:50],
                    max_items=50,
                )

        ledger = {
            "_meta": {
                "status": "ok",
                "run_id": run_id,
                "requested_by": requested_by,
                "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            },
            "constraints": {
                "objective": "maximize_total_return_pct",
                "dd_limits": dd_limits,
                "chosen_dd_limit": chosen_dd_limit,
                "max_trades": int(max_trades) if max_trades is not None else None,
                "tie_breaker": "min_total_trades",
            },
            "search": {
                "seed": int(seed),
                "coarse_trials": int(coarse_trials),
                "fine_trials": int(fine_trials),
                "grid_size": int(len(grid)),
            },
            "best": chosen_best,
            "results": all_results,
            "opportunity_coverage": opportunity_eval,
            "opportunity_miss_analysis": opportunity_miss_analysis,
            "opportunity_top_missed_features": opportunity_top_missed_features,
        }
        (optimize_dir / "results.json").write_text(
            json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

        return {
            "_meta": {"status": "ok"},
            "run_id": run_id,
            "best": chosen_best,
            "model_persisted": persisted,
            "best_report": {
                "report_id": best_report_id,
                "pdf_url": f"/api/lowfreq/backtest/reports/{best_report_id}.pdf",
                "json_url": f"/api/lowfreq/backtest/reports/{best_report_id}.json",
            },
            "artifact_path": _safe_ref_path(str(optimize_dir / "results.json")),
            "opportunity_coverage": opportunity_eval,
            "opportunity_miss_analysis": opportunity_miss_analysis,
            "opportunity_top_missed_features": opportunity_top_missed_features,
        }

    def _lowfreq_opportunity_coverage_view(
        self,
        *,
        start_date: str,
        end_date: str,
        trades_payload: dict[str, Any],
        window_len: int,
        top_n: int,
        b2_threshold_pct: float,
        capture_window_trading_days: int,
        max_return_cap_pct: float = 300.0,
    ) -> dict[str, Any]:
        engine = self._lowfreq_engine_v16()
        start_dt = date.fromisoformat(start_date)
        end_dt = date.fromisoformat(end_date)
        trading_dates = engine._get_trading_dates(start_dt, end_dt)
        date_keys = [d.isoformat() for d in trading_dates]
        date_index = {k: i for i, k in enumerate(date_keys)}
        if len(date_keys) <= window_len + 1:
            return {"status": "skipped", "reason": "insufficient_trading_days"}

        db_path = Path(os.environ.get("NEOTRADE3_STOCK_DB_PATH") or str(self._stock_db_default_path)).expanduser()
        conn = sqlite3.connect(str(db_path))
        try:
            cursor = conn.cursor()
            market_cap_min = float(getattr(engine, "MARKET_CAP_MIN", 0.0) or 0.0)
            market_cap_max = float(getattr(engine, "MARKET_CAP_MAX", 1e18) or 1e18)
            cursor.execute(
                """
                SELECT dp.code, dp.trade_date, dp.close
                FROM daily_prices AS dp
                JOIN stocks AS s
                  ON s.code = dp.code
                WHERE dp.trade_date BETWEEN ? AND ?
                  AND dp.close IS NOT NULL
                  AND s.total_market_cap > ? AND s.total_market_cap < ?
                  AND (s.is_delisted IS NULL OR s.is_delisted = 0)
                  AND (s.asset_type IS NULL OR s.asset_type = 'stock')
                ORDER BY dp.code ASC, dp.trade_date ASC
                """,
                (start_date, end_date, market_cap_min, market_cap_max),
            )
            rows = cursor.fetchall()
        finally:
            conn.close()

        n_days = len(date_keys)
        closes_by_code: dict[str, list[Optional[float]]] = {}
        for code, d, close in rows:
            code = str(code)
            idx = date_index.get(str(d))
            if idx is None:
                continue
            bucket = closes_by_code.get(code)
            if bucket is None:
                bucket = [None] * n_days
                closes_by_code[code] = bucket
            bucket[int(idx)] = float(close)

        w = int(window_len)
        future_max_ret: dict[str, list[float]] = {}
        for code, closes in closes_by_code.items():
            from collections import deque

            values = [(-1e18 if v is None else float(v)) for v in closes]
            dq: deque[int] = deque()
            max_close: list[float] = [0.0] * n_days
            for i in range(n_days - 1, -1, -1):
                while dq and dq[0] > i + w:
                    dq.popleft()
                while dq and values[dq[-1]] <= values[i]:
                    dq.pop()
                dq.append(i)
                max_close[i] = values[dq[0]]

            ret_arr = [0.0] * n_days
            for i in range(n_days):
                base_raw = closes[i]
                if base_raw is None or float(base_raw) <= 0:
                    ret_arr[i] = 0.0
                else:
                    best_close = float(max_close[i])
                    if best_close <= 0:
                        ret_arr[i] = 0.0
                    else:
                        base = float(base_raw)
                        ret_arr[i] = (best_close / base - 1.0) * 100.0
            future_max_ret[code] = ret_arr

        trades = trades_payload.get("trades") or []
        buy_indices_by_code: dict[str, list[int]] = {}
        hold_ranges_by_code: dict[str, list[tuple[int, int]]] = {}
        for t in trades:
            if not isinstance(t, dict):
                continue
            code = str(t.get("code") or "").strip()
            bd = str(t.get("buy_date") or "").strip()
            if not code or not bd:
                continue
            idx = date_index.get(bd)
            if idx is None:
                continue
            buy_indices_by_code.setdefault(code, []).append(int(idx))
            sd = str(t.get("sell_date") or "").strip()
            if sd:
                sell_idx = date_index.get(sd)
            else:
                sell_idx = None
            if sell_idx is None:
                sell_idx = n_days - 1
            hold_ranges_by_code.setdefault(code, []).append((int(idx), int(sell_idx)))

        opportunities: list[dict[str, Any]] = []
        for i in range(0, n_days - w - 1):
            best: list[tuple[float, str]] = []
            for code, arr in future_max_ret.items():
                r = float(arr[i])
                if len(best) < int(top_n):
                    best.append((r, code))
                    best.sort(reverse=True)
                else:
                    if r > best[-1][0]:
                        best[-1] = (r, code)
                        best.sort(reverse=True)
            for r, code in best:
                if r <= 0 or r > float(max_return_cap_pct):
                    continue
                opportunities.append(
                    {
                        "window_start": date_keys[i],
                        "code": code,
                        "window_max_return_pct": float(r),
                    }
                )

        missed: list[dict[str, Any]] = []
        captured = 0
        for op in opportunities:
            code = str(op["code"])
            start_idx = date_index[str(op["window_start"])]
            closes = closes_by_code.get(code)
            if not closes:
                continue
            base_raw = closes[start_idx]
            if base_raw is None or float(base_raw) <= 0:
                continue
            base = float(base_raw)
            b2_idx = None
            threshold = base * (1.0 + float(b2_threshold_pct) / 100.0)
            for j in range(start_idx + 1, min(n_days, start_idx + w + 1)):
                cj = closes[j]
                if cj is not None and float(cj) >= threshold:
                    b2_idx = j
                    break
            if b2_idx is None:
                continue
            op["b2_date"] = date_keys[b2_idx]

            buy_idxs = buy_indices_by_code.get(code, [])
            hold_ranges = hold_ranges_by_code.get(code, [])
            hit = False
            for bi in buy_idxs:
                if abs(int(bi) - int(b2_idx)) <= int(capture_window_trading_days):
                    hit = True
                    break
            if not hit:
                for bi, si in hold_ranges:
                    if int(bi) <= int(b2_idx) <= int(si):
                        hit = True
                        break
            if hit:
                captured += 1
            else:
                missed.append(op)

        opportunities_count = len([o for o in opportunities if "b2_date" in o])
        missed.sort(key=lambda x: float(x.get("window_max_return_pct") or 0.0), reverse=True)
        top_missed = missed[:50]

        return {
            "status": "ok",
            "window_len": int(window_len),
            "top_n": int(top_n),
            "b2_threshold_pct": float(b2_threshold_pct),
            "capture_window_trading_days": int(capture_window_trading_days),
            "max_return_cap_pct": float(max_return_cap_pct),
            "opportunities_count": int(opportunities_count),
            "captured_count": int(captured),
            "captured_ratio": (float(captured) / float(opportunities_count) if opportunities_count else 0.0),
            "top_missed": top_missed,
        }

    def _lowfreq_opportunity_miss_analysis_view(
        self,
        *,
        start_date: str,
        end_date: str,
        trades_payload: dict[str, Any],
        top_missed: list[dict[str, Any]],
        capture_window_trading_days: int,
        engine_overrides: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        engine = self._lowfreq_engine_v16()
        if isinstance(engine_overrides, dict):
            for k, v in engine_overrides.items():
                try:
                    setattr(engine, str(k), v)
                except Exception:
                    continue
        start_dt = date.fromisoformat(start_date)
        end_dt = date.fromisoformat(end_date)
        trading_dates = engine._get_trading_dates(start_dt, end_dt)
        date_keys = [d.isoformat() for d in trading_dates]
        date_index = {k: i for i, k in enumerate(date_keys)}

        db_path = Path(os.environ.get("NEOTRADE3_STOCK_DB_PATH") or str(self._stock_db_default_path)).expanduser()
        conn = sqlite3.connect(str(db_path))
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT code, sector_lv1 FROM stocks WHERE sector_lv1 IS NOT NULL",
            )
            sector_by_code = {str(c): str(s) for c, s in cursor.fetchall() if c and s}
        finally:
            conn.close()

        market_filter_enabled = bool(getattr(engine, "MARKET_FILTER_ENABLED", False))
        min_market_score = float(getattr(engine, "MIN_MARKET_SCORE", 0.0) or 0.0)
        rebalance_days = int(getattr(engine, "REBALANCE_DAYS", 15) or 15)

        reason_counts: dict[str, int] = {}
        samples: list[dict[str, Any]] = []
        rebalance_window_hits = 0

        for op in top_missed:
            code = str(op.get("code") or "").strip()
            b2_date = str(op.get("b2_date") or "").strip()
            if not code or not b2_date:
                continue
            b2_idx = date_index.get(b2_date)
            if b2_idx is None:
                continue

            within_rebalance = False
            for d in range(-int(capture_window_trading_days), int(capture_window_trading_days) + 1):
                j = b2_idx + d
                if j < 0 or j >= len(date_keys):
                    continue
                if j % rebalance_days == 0:
                    within_rebalance = True
                    break
            if within_rebalance:
                rebalance_window_hits += 1

            primary = "unknown"
            details: dict[str, Any] = {"within_rebalance_window": within_rebalance}

            if market_filter_enabled:
                sentiment, score = engine.get_market_sentiment(date.fromisoformat(b2_date))
                details["market_score"] = float(score)
                if float(score) < min_market_score:
                    primary = "market_filter_blocked"
            if primary == "unknown":
                sector = sector_by_code.get(code)
                details["sector"] = sector
                hot_sectors = [s.sector for s in engine.get_hot_sectors(date.fromisoformat(b2_date), engine.HOT_SECTOR_COUNT)]
                details["hot_sectors"] = hot_sectors[:10]
                if not sector or sector not in set(hot_sectors):
                    primary = "sector_not_hot"

            if primary == "unknown":
                sector = details.get("sector")
                try:
                    candidates = engine.get_sector_candidates(str(sector), date.fromisoformat(b2_date), 20)
                except Exception:
                    candidates = []
                hit = None
                for c in candidates:
                    if str(getattr(c, "code", "")).strip() == code:
                        hit = c
                        break
                if hit is None:
                    primary = "not_in_sector_candidates"
                else:
                    details["buy_score"] = float(getattr(hit, "buy_score", 0.0) or 0.0)
                    details["role"] = str(getattr(hit, "role", "") or "")
                    details["resonance"] = float(getattr(hit, "sector_resonance", 0.0) or 0.0)
                    if details["role"] == "跟随":
                        primary = "role_follower_filtered"
                    elif details["resonance"] < float(getattr(engine, "MIN_RESONANCE", 0.0) or 0.0):
                        primary = "resonance_below_threshold"
                    elif details["buy_score"] < float(getattr(engine, "BUY_THRESHOLD", 0.0) or 0.0):
                        primary = "buy_score_below_threshold"
                    else:
                        primary = "signal_possible_but_not_captured"

            reason_counts[primary] = int(reason_counts.get(primary, 0)) + 1
            if len(samples) < 15:
                samples.append(
                    {
                        "code": code,
                        "window_start": op.get("window_start"),
                        "b2_date": b2_date,
                        "window_max_return_pct": op.get("window_max_return_pct"),
                        "reason": primary,
                        "details": details,
                    }
                )

        total = sum(reason_counts.values())
        return {
            "status": "ok",
            "top_missed_analyzed": int(total),
            "rebalance_days": int(rebalance_days),
            "within_rebalance_window_count": int(rebalance_window_hits),
            "within_rebalance_window_ratio": (float(rebalance_window_hits) / float(total) if total else 0.0),
            "reason_counts": reason_counts,
            "samples": samples,
        }

    def _lowfreq_opportunity_top_missed_features_view(
        self,
        *,
        start_date: str,
        end_date: str,
        top_missed: list[dict[str, Any]],
        max_items: int = 50,
    ) -> dict[str, Any]:
        engine = self._lowfreq_engine_v16()
        start_dt = date.fromisoformat(start_date)
        end_dt = date.fromisoformat(end_date)
        trading_dates = engine._get_trading_dates(start_dt, end_dt)
        date_keys = [d.isoformat() for d in trading_dates]
        date_index = {k: i for i, k in enumerate(date_keys)}

        db_path = Path(os.environ.get("NEOTRADE3_STOCK_DB_PATH") or str(self._stock_db_default_path)).expanduser()
        conn = sqlite3.connect(str(db_path))
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT code, name, sector_lv1, sector_lv2, industry, total_market_cap
                FROM stocks
                WHERE (is_delisted IS NULL OR is_delisted = 0)
                """,
            )
            meta_by_code = {
                str(r[0]): {
                    "name": str(r[1] or ""),
                    "sector_lv1": str(r[2] or ""),
                    "sector_lv2": str(r[3] or ""),
                    "industry": str(r[4] or ""),
                    "total_market_cap": float(r[5] or 0.0),
                }
                for r in cursor.fetchall()
                if r and r[0]
            }
        finally:
            conn.close()

        def sector_rank_map(target_date: str) -> dict[str, dict[str, Any]]:
            conn2 = sqlite3.connect(str(db_path))
            try:
                cur = conn2.cursor()
                cur.execute(
                    """
                    SELECT s.sector_lv1,
                           COUNT(*) AS stock_count,
                           AVG(dp.pct_change) AS avg_change,
                           SUM(dp.amount) AS total_amount
                    FROM stocks s
                    JOIN daily_prices dp ON s.code = dp.code
                    WHERE dp.trade_date = ?
                      AND s.total_market_cap > ? AND s.total_market_cap < ?
                      AND (s.is_delisted IS NULL OR s.is_delisted = 0)
                    GROUP BY s.sector_lv1
                    HAVING COUNT(*) >= 3
                    ORDER BY avg_change DESC
                    """,
                    (
                        target_date,
                        float(getattr(engine, "MARKET_CAP_MIN", 0.0) or 0.0),
                        float(getattr(engine, "MARKET_CAP_MAX", 1e18) or 1e18),
                    ),
                )
                rows = cur.fetchall()
            finally:
                conn2.close()
            out: dict[str, dict[str, Any]] = {}
            for i, (sec, cnt, avg_chg, amt) in enumerate(rows, start=1):
                out[str(sec)] = {
                    "rank_by_avg_change": int(i),
                    "sector_stock_count": int(cnt or 0),
                    "sector_avg_change": float(avg_chg or 0.0),
                    "sector_total_amount": float(amt or 0.0),
                }
            return out

        per_item: list[dict[str, Any]] = []
        by_sector: dict[str, dict[str, Any]] = {}
        by_industry: dict[str, dict[str, Any]] = {}

        items = [x for x in top_missed if isinstance(x, dict)][: int(max_items)]
        for op in items:
            code = str(op.get("code") or "").strip()
            b2_date = str(op.get("b2_date") or "").strip()
            if not code or not b2_date:
                continue
            if b2_date not in date_index:
                continue

            meta = meta_by_code.get(code, {})
            sector_lv1 = str(meta.get("sector_lv1") or "")
            industry = str(meta.get("industry") or "")
            sector_ranks = sector_rank_map(b2_date)
            sec_rank = sector_ranks.get(sector_lv1) or {}
            hot_sectors = [s.sector for s in engine.get_hot_sectors(date.fromisoformat(b2_date), engine.HOT_SECTOR_COUNT)]

            resonance = 0.0
            wave_phase = ""
            buy_score = None
            role = None
            try:
                resonance = float(engine.check_resonance(code, sector_lv1, date.fromisoformat(b2_date)) or 0.0)
            except Exception:
                resonance = 0.0
            try:
                wave_phase, _ = engine.detect_wave_phase(code, date.fromisoformat(b2_date))
            except Exception:
                wave_phase = ""
            try:
                candidates = engine.get_sector_candidates(sector_lv1, date.fromisoformat(b2_date), top_n=15)
                hit = None
                for c in candidates:
                    if str(getattr(c, "code", "")).strip() == code:
                        hit = c
                        break
                if hit is not None:
                    buy_score = float(getattr(hit, "buy_score", 0.0) or 0.0)
                    role = str(getattr(hit, "role", "") or "")
            except Exception:
                buy_score = None
                role = None

            mkt_cap_yi = float(meta.get("total_market_cap") or 0.0) / 1e8
            row = {
                "code": code,
                "name": str(meta.get("name") or ""),
                "window_start": str(op.get("window_start") or ""),
                "b2_date": b2_date,
                "window_max_return_pct": float(op.get("window_max_return_pct") or 0.0),
                "sector_lv1": sector_lv1,
                "industry": industry,
                "market_cap_yi": round(mkt_cap_yi, 1),
                "sector_in_hot": bool(sector_lv1 and sector_lv1 in set(hot_sectors)),
                "sector_hot_list": hot_sectors[:10],
                "sector_rank_by_avg_change": sec_rank.get("rank_by_avg_change"),
                "sector_avg_change": sec_rank.get("sector_avg_change"),
                "resonance": round(resonance, 3),
                "wave_phase": wave_phase,
                "candidate_buy_score": buy_score,
                "candidate_role": role,
            }
            per_item.append(row)

            if sector_lv1:
                agg = by_sector.get(sector_lv1)
                if agg is None:
                    agg = {"count": 0, "avg_window_max_return_pct": 0.0, "max_window_max_return_pct": 0.0}
                    by_sector[sector_lv1] = agg
                cnt = int(agg["count"]) + 1
                prev_avg = float(agg["avg_window_max_return_pct"])
                val = float(row["window_max_return_pct"])
                agg["count"] = cnt
                agg["avg_window_max_return_pct"] = prev_avg + (val - prev_avg) / float(cnt)
                agg["max_window_max_return_pct"] = max(float(agg["max_window_max_return_pct"]), val)

            if industry:
                agg2 = by_industry.get(industry)
                if agg2 is None:
                    agg2 = {"count": 0, "avg_window_max_return_pct": 0.0, "max_window_max_return_pct": 0.0}
                    by_industry[industry] = agg2
                cnt2 = int(agg2["count"]) + 1
                prev_avg2 = float(agg2["avg_window_max_return_pct"])
                val2 = float(row["window_max_return_pct"])
                agg2["count"] = cnt2
                agg2["avg_window_max_return_pct"] = prev_avg2 + (val2 - prev_avg2) / float(cnt2)
                agg2["max_window_max_return_pct"] = max(float(agg2["max_window_max_return_pct"]), val2)

        sector_top = sorted(
            [{"sector_lv1": k, **v} for k, v in by_sector.items()],
            key=lambda x: (-int(x["count"]), -float(x["avg_window_max_return_pct"])),
        )[:15]
        industry_top = sorted(
            [{"industry": k, **v} for k, v in by_industry.items()],
            key=lambda x: (-int(x["count"]), -float(x["avg_window_max_return_pct"])),
        )[:15]

        return {
            "status": "ok",
            "items": per_item,
            "by_sector_lv1_top": sector_top,
            "by_industry_top": industry_top,
        }

    def _render_lowfreq_backtest_pdf(
        self,
        *,
        pdf_path: Path,
        summary: dict[str, Any],
        buy_dates: list[dict[str, Any]],
        trades: list[Any],
        next_session: Optional[dict[str, Any]] = None,
    ) -> None:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
        styles = getSampleStyleSheet()
        base = ParagraphStyle(
            "base",
            parent=styles["Normal"],
            fontName="STSong-Light",
            fontSize=9,
            leading=12,
        )
        title_style = ParagraphStyle(
            "title",
            parent=styles["Title"],
            fontName="STSong-Light",
            fontSize=16,
            leading=20,
        )

        doc = SimpleDocTemplate(
            str(pdf_path),
            pagesize=A4,
            leftMargin=12 * mm,
            rightMargin=12 * mm,
            topMargin=12 * mm,
            bottomMargin=12 * mm,
        )

        story: list[Any] = []
        story.append(Paragraph("低频量化交易回测报告（v16）", title_style))
        story.append(Spacer(1, 6 * mm))

        summary_rows = [
            ["回测区间", f"{summary.get('start_date','')} → {summary.get('end_date','')}"],
            ["初始资本", f"{summary.get('initial_capital', 0):,.0f}"],
            ["最终资产", f"{summary.get('final_value', 0):,.0f}"],
            ["总收益率", f"{summary.get('total_return_pct', 0)}%"],
            ["最大回撤", f"{summary.get('max_drawdown_pct', 0)}%"],
            ["交易次数", str(summary.get("total_trades", 0))],
            ["30%+ 达成率", f"{summary.get('target_hit_rate_30_pct', 0)}%"],
        ]
        summary_table = Table(summary_rows, colWidths=[32 * mm, 150 * mm])
        summary_table.setStyle(
            TableStyle(
                [
                    ("FONT", (0, 0), (-1, -1), "STSong-Light", 9),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.grey),
                    ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.whitesmoke, colors.white]),
                ]
            )
        )
        story.append(summary_table)
        story.append(Spacer(1, 6 * mm))

        story.append(Paragraph("执行约束（成交假设）", ParagraphStyle("h2", parent=base, fontSize=12, leading=14)))
        story.append(Spacer(1, 2 * mm))
        story.append(
            Paragraph(
                "1) 数据与价格：仅使用日线收盘价 close 作为成交价。<br/>"
                "2) 前视校验：NO_LOOKAHEAD_ENFORCED=True，信号计算均使用 trade_date &lt;= 当前交易日的数据窗口。<br/>"
                "3) 涨跌停判定：使用 pct_change 与保守阈值（ST=±4.8%，300/688=±19.8%，其他=±9.8%）。<br/>"
                "4) 执行顺序：待卖出 → 当日新离场 → 待买入 → 调仓日新买入。<br/>"
                "5) 跌停卖不出：离场信号当日跌停则顺延到首个非跌停日成交，卖出原因中标记“跌停顺延”。<br/>"
                "6) 涨停买不进：买入信号当日涨停则进入待买队列，最多尝试 3 个交易日；遇涨停/无有效价格/资金不足会消耗一次尝试，耗尽则取消。",
                base,
            )
        )
        story.append(Spacer(1, 6 * mm))

        if buy_dates:
            story.append(Paragraph("买入日期汇总", ParagraphStyle("h2", parent=base, fontSize=12, leading=14)))
            story.append(Spacer(1, 2 * mm))
            rows = [["买入日期", "次数"]] + [[d["buy_date"], str(d["count"])] for d in buy_dates]
            t = Table(rows, colWidths=[50 * mm, 30 * mm])
            t.setStyle(
                TableStyle(
                    [
                        ("FONT", (0, 0), (-1, -1), "STSong-Light", 9),
                        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                    ]
                )
            )
            story.append(t)
            story.append(Spacer(1, 6 * mm))

        if next_session and (next_session.get("candidates") or next_session.get("next_trading_day")):
            next_day = str(next_session.get("next_trading_day") or "")
            title = "明日建仓候选" + (f"（{next_day}）" if next_day else "")
            story.append(Paragraph(title, ParagraphStyle("h2", parent=base, fontSize=12, leading=14)))
            story.append(Spacer(1, 2 * mm))
            candidates = next_session.get("candidates") or []
            if isinstance(candidates, list) and candidates:
                rows = [["代码", "名称", "板块", "角色", "评分", "浪型", "共振"]]
                for c in candidates:
                    if not isinstance(c, dict):
                        continue
                    rows.append(
                        [
                            str(c.get("code") or ""),
                            str(c.get("name") or ""),
                            str(c.get("sector") or ""),
                            str(c.get("role") or ""),
                            f"{float(c.get('buy_score') or 0.0):.0f}",
                            str(c.get("wave_phase") or ""),
                            f"{float(c.get('resonance') or 0.0):.0%}",
                        ]
                    )
                t = Table(rows, colWidths=[16*mm, 28*mm, 20*mm, 12*mm, 10*mm, 14*mm, 12*mm])
                t.setStyle(
                    TableStyle(
                        [
                            ("FONT", (0, 0), (-1, -1), "STSong-Light", 8),
                            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ]
                    )
                )
                story.append(t)
            else:
                story.append(Paragraph("无可用候选（可能因数据/条件不足）。", base))
            story.append(Spacer(1, 6 * mm))

        story.append(Paragraph("交易明细", ParagraphStyle("h2", parent=base, fontSize=12, leading=14)))
        story.append(Spacer(1, 2 * mm))

        header = ["代码", "名称", "板块", "角色", "买入日", "评分", "买入价", "卖出日", "收益%"]
        rows = [header]
        for t in trades:
            rows.append(
                [
                    getattr(t, "code", ""),
                    getattr(t, "name", ""),
                    getattr(t, "sector", ""),
                    getattr(t, "role", ""),
                    getattr(t, "buy_date", ""),
                    f"{getattr(t, 'buy_score', 0):.0f}",
                    f"{getattr(t, 'buy_price', 0):.3f}",
                    getattr(t, "sell_date", ""),
                    f"{getattr(t, 'return_pct', 0):.2f}",
                ]
            )

        table = Table(rows, repeatRows=1, colWidths=[16*mm, 24*mm, 22*mm, 12*mm, 22*mm, 10*mm, 16*mm, 22*mm, 14*mm])
        table.setStyle(
            TableStyle(
                [
                    ("FONT", (0, 0), (-1, -1), "STSong-Light", 8),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )
        story.append(table)
        doc.build(story)

    def lowfreq_backtest_report_download_view(
        self, *, report_id: str, format: str
    ) -> Any:
        report_dir = self._lowfreq_backtest_artifacts_dir / str(report_id)
        if format == "pdf":
            pdf_path = report_dir / "trades.pdf"
            if not pdf_path.exists():
                raise ApiError(
                    status_code=HTTPStatus.NOT_FOUND,
                    code="report_not_found",
                    message="report not found",
                    details={"report_id": report_id},
                )
            content = pdf_path.read_bytes()
            return ApiBinaryResponse(
                content=content,
                content_type="application/pdf",
                filename=f"{report_id}.pdf",
            )
        if format == "json":
            json_path = report_dir / "trades.json"
            if not json_path.exists():
                raise ApiError(
                    status_code=HTTPStatus.NOT_FOUND,
                    code="report_not_found",
                    message="report not found",
                    details={"report_id": report_id},
                )
            try:
                return json.loads(json_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                raise ApiError(
                    status_code=HTTPStatus.CONFLICT,
                    code="report_corrupted",
                    message="report corrupted",
                    details={"report_id": report_id},
                )
        raise ApiError(
            status_code=HTTPStatus.BAD_REQUEST,
            code="invalid_format",
            message="format must be pdf or json",
            details={"format": format},
        )

    def lowfreq_backtest_reports_view(self, *, limit: int = 10) -> dict[str, Any]:
        if int(limit) <= 0:
            raise ApiError(
                status_code=HTTPStatus.BAD_REQUEST,
                code="invalid_limit",
                message="limit must be a positive integer",
                details={"limit": limit},
            )
        limit = min(int(limit), 100)

        import re

        base_dir = self._lowfreq_backtest_artifacts_dir
        if not base_dir.exists():
            return {"_meta": {"returned_count": 0, "limit": limit}, "reports": []}

        rx = re.compile(r"^lowfreq_v16_(\\d{4}-\\d{2}-\\d{2})_(\\d{4}-\\d{2}-\\d{2})")
        items: list[dict[str, Any]] = []
        for d in base_dir.iterdir():
            if not d.is_dir():
                continue
            report_id = d.name
            pdf_path = d / "trades.pdf"
            json_path = d / "trades.json"
            if not pdf_path.exists():
                continue

            start_date: Optional[str] = None
            end_date: Optional[str] = None
            m = rx.match(report_id)
            if m:
                start_date, end_date = m.group(1), m.group(2)

            requested_at: Optional[str] = None
            finished_at: Optional[str] = None
            status_path = d / "status.json"
            if status_path.exists():
                try:
                    status_payload = json.loads(status_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    status_payload = None
                if isinstance(status_payload, dict):
                    ra = status_payload.get("requested_at")
                    fa = status_payload.get("finished_at")
                    requested_at = str(ra) if isinstance(ra, str) and ra.strip() else None
                    finished_at = str(fa) if isinstance(fa, str) and fa.strip() else None
                    sd = status_payload.get("start_date")
                    ed = status_payload.get("end_date")
                    if isinstance(sd, str) and sd.strip():
                        start_date = start_date or sd.strip()
                    if isinstance(ed, str) and ed.strip():
                        end_date = end_date or ed.strip()

            total_return_pct: Optional[float] = None
            if json_path.exists():
                try:
                    payload = json.loads(json_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    payload = None
                if isinstance(payload, dict):
                    summary = payload.get("summary")
                    if isinstance(summary, dict):
                        tr = summary.get("total_return_pct")
                        if isinstance(tr, (int, float)):
                            total_return_pct = float(tr)

            mtime = None
            try:
                mtime = float(pdf_path.stat().st_mtime)
            except OSError:
                mtime = None

            items.append(
                {
                    "report_id": report_id,
                    "start_date": start_date,
                    "end_date": end_date,
                    "requested_at": requested_at,
                    "finished_at": finished_at,
                    "summary": {"total_return_pct": total_return_pct},
                    "pdf_url": f"/api/lowfreq/backtest/reports/{report_id}.pdf",
                    "json_url": f"/api/lowfreq/backtest/reports/{report_id}.json",
                    "_sort": {"finished_at": finished_at, "requested_at": requested_at, "mtime": mtime},
                }
            )

        def _sort_key(entry: dict[str, Any]) -> tuple[float, float]:
            raw = entry.get("_sort") if isinstance(entry.get("_sort"), dict) else {}
            mtime = raw.get("mtime")
            if isinstance(mtime, (int, float)):
                return (1.0, float(mtime))
            return (0.0, 0.0)

        items.sort(key=_sort_key, reverse=True)
        for entry in items:
            entry.pop("_sort", None)
        returned = items[:limit]
        return {"_meta": {"returned_count": len(returned), "limit": limit}, "reports": returned}

    def lowfreq_backtest_window_summary_view(
        self, *, end_date: str, window_trading_days: int = 60
    ) -> dict[str, Any]:
        if not isinstance(end_date, str) or not end_date.strip():
            raise ApiError(
                status_code=HTTPStatus.BAD_REQUEST,
                code="invalid_end_date",
                message="end_date must be a non-empty string in YYYY-MM-DD format",
                details={"end_date": end_date},
            )
        try:
            date.fromisoformat(end_date)
        except ValueError:
            raise ApiError(
                status_code=HTTPStatus.BAD_REQUEST,
                code="invalid_end_date",
                message=f"invalid end_date: {end_date}",
                details={"end_date": end_date},
            )
        if int(window_trading_days) <= 0:
            raise ApiError(
                status_code=HTTPStatus.BAD_REQUEST,
                code="invalid_window",
                message="window_trading_days must be a positive integer",
                details={"window_trading_days": window_trading_days},
            )

        db_path = Path(
            os.environ.get("NEOTRADE3_STOCK_DB_PATH") or str(self._stock_db_default_path)
        ).expanduser()
        if not db_path.exists():
            raise ApiError(
                status_code=HTTPStatus.SERVICE_UNAVAILABLE,
                code="stock_db_not_ready",
                message="NeoTrade3 行情库未初始化（stock_data.db 不存在）",
                details={"expected_path": _safe_ref_path(str(db_path))},
            )

        actual_end: Optional[str] = None
        dates: list[str] = []
        conn = sqlite3.connect(str(db_path))
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT MAX(trade_date) FROM trading_calendar_cache WHERE trade_date <= ?",
                (end_date.strip(),),
            )
            row = cur.fetchone()
            actual_end = str(row[0]) if row and row[0] else None
            if not actual_end:
                raise ApiError(
                    status_code=HTTPStatus.CONFLICT,
                    code="trading_calendar_unavailable",
                    message="trading calendar unavailable for the requested end_date",
                    details={"end_date": end_date},
                )
            cur.execute(
                "SELECT trade_date FROM trading_calendar_cache WHERE trade_date <= ? ORDER BY trade_date DESC LIMIT ?",
                (actual_end, int(window_trading_days)),
            )
            rows = cur.fetchall()
            dates = [str(r[0]) for r in rows if r and r[0]]
        finally:
            conn.close()

        if len(dates) < int(window_trading_days):
            raise ApiError(
                status_code=HTTPStatus.CONFLICT,
                code="insufficient_trading_days",
                message="insufficient trading days for the requested window",
                details={"end_date": actual_end, "need": int(window_trading_days), "got": len(dates)},
            )

        actual_start = dates[-1]
        reports_payload = self.lowfreq_backtest_reports_view(limit=100)
        reports = reports_payload.get("reports") if isinstance(reports_payload, dict) else None
        matched: list[dict[str, Any]] = []
        if isinstance(reports, list):
            for r in reports:
                if not isinstance(r, dict):
                    continue
                if r.get("start_date") == actual_start and r.get("end_date") == actual_end:
                    matched.append(r)

        if not matched:
            return {
                "_meta": {"status": "missing"},
                "start_date": actual_start,
                "end_date": actual_end,
                "window_trading_days": int(window_trading_days),
                "message": "未生成该窗口回测报告",
            }

        latest = matched[0]
        return {
            "_meta": {"status": "ok"},
            "start_date": actual_start,
            "end_date": actual_end,
            "window_trading_days": int(window_trading_days),
            "report": latest,
        }


def _lowfreq_backtest_worker(
    *,
    project_root: str,
    start_date: str,
    end_date: str,
    requested_by: str,
    report_id: str,
    overrides: dict[str, Any],
    job_id: str,
) -> None:
    root = Path(project_root)
    report_dir = root / "var/artifacts/lowfreq_backtest" / str(report_id)
    report_dir.mkdir(parents=True, exist_ok=True)
    status_path = report_dir / "status.json"
    pdf_path = report_dir / "trades.pdf"
    json_path = report_dir / "trades.json"

    def write_status(payload: dict[str, Any]) -> None:
        status_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    started_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    write_status(
        {
            "status": "running",
            "job_id": job_id,
            "pid": os.getpid(),
            "requested_at": started_at,
            "requested_by": requested_by,
            "report_id": report_id,
            "start_date": start_date,
            "end_date": end_date,
        }
    )

    service = BootstrapApiService(project_root=root, api_key="worker")
    try:
        service.lowfreq_backtest_run_view(
            start_date=start_date,
            end_date=end_date,
            async_run=False,
            requested_by=requested_by,
            report_id=report_id,
            overrides=overrides or {},
        )
        finished_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        write_status(
            {
                "version": 1,
                "status": "done",
                "job_id": job_id,
                "pid": os.getpid(),
                "requested_at": started_at,
                "finished_at": finished_at,
                "requested_by": requested_by,
                "report_id": report_id,
                "start_date": start_date,
                "end_date": end_date,
                "pdf_path": str(pdf_path) if pdf_path.exists() else None,
                "json_path": str(json_path) if json_path.exists() else None,
            }
        )
    except Exception as exc:
        failed_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        write_status(
            {
                "version": 1,
                "status": "failed",
                "job_id": job_id,
                "pid": os.getpid(),
                "requested_at": started_at,
                "failed_at": failed_at,
                "requested_by": requested_by,
                "report_id": report_id,
                "start_date": start_date,
                "end_date": end_date,
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
        )


def _screeners_bulk_run_worker(
    *,
    project_root: str,
    target_date: str,
    screener_ids: list[str],
    requested_by: str,
    parameters: dict[str, Any],
    job_id: str,
) -> None:
    root = Path(project_root)
    service = BootstrapApiService(project_root=root, api_key="worker")
    try:
        result = service.screeners_bulk_run_view(
            target_date=target_date,
            screener_ids=screener_ids,
            requested_by=requested_by,
            parameters=parameters,
            dry_run=False,
            async_run=False,
        )
        ledger = result.get("bulk_run") if isinstance(result, dict) else None
        if isinstance(ledger, dict):
            ledger["job_id"] = job_id
            ledgers_dir = root / "var/ledgers/screener_runs" / target_date
            bulk_ledger_path = ledgers_dir / "bulk_run_ledger.json"
            ledgers_dir.mkdir(parents=True, exist_ok=True)
            bulk_ledger_path.write_text(
                json.dumps(ledger, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
                encoding="utf-8",
            )
    except Exception:
        failed_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        ledgers_dir = root / "var/ledgers/screener_runs" / target_date
        artifacts_dir = root / "var/artifacts/screener_runs" / target_date
        bulk_ledger_path = ledgers_dir / "bulk_run_ledger.json"
        bulk_artifact_path = artifacts_dir / "bulk_run_result.json"
        payload = {
            "version": 1,
            "job_id": job_id,
            "target_date": target_date,
            "requested_by": requested_by,
            "requested_at": failed_at,
            "status": "failed",
            "screener_ids": screener_ids,
            "run_count": 0,
            "run_ledgers": [],
        }
        artifact = {
            "version": 1,
            "job_id": job_id,
            "target_date": target_date,
            "requested_by": requested_by,
            "requested_at": failed_at,
            "status": "failed",
            "summary": {"run_count": 0, "picks_count_total": 0},
            "runs": [],
        }
        ledgers_dir.mkdir(parents=True, exist_ok=True)
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        bulk_ledger_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        bulk_artifact_path.write_text(
            json.dumps(artifact, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def build_handler(service: BootstrapApiService) -> type[BaseHTTPRequestHandler]:
    from apps.api.http import build_handler as _build_handler

    return _build_handler(service)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the NeoTrade3 bootstrap API.")
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Bind host for the API server (use 0.0.0.0 for LAN access).",
    )
    parser.add_argument(
        "--port", type=int, default=18030, help="Bind port for the API server."
    )
    parser.add_argument(
        "--api-key", default=None, help="API key required for POST endpoints."
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[2]
    api_key = args.api_key or os.environ.get("NEOTRADE3_API_KEY")
    service = BootstrapApiService(project_root=project_root, api_key=api_key)
    handler = build_handler(service)
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(
        json.dumps(
            {
                "service": "neotrade3-bootstrap-api",
                "host": args.host,
                "port": args.port,
                "healthz": f"http://{args.host}:{args.port}/healthz",
            },
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
