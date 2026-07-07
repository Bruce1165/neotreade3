"""Data control bootstrap for NeoTrade3."""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import statistics
import time
from datetime import date
from pathlib import Path
from typing import Any, cast

from .ledger import DataControlLedgerBuilder, DataControlLedgerEntry
from .models import (
    DataControlPlan,
    DataControlStage,
    DataControlStepDefinition,
    DataControlStepResult,
)
from .source_registry import SourceRegistry

logger = logging.getLogger(__name__)


class DataControlPipeline:
    """Defines the minimal capture-compose-publish chain for bootstrap."""

    def __init__(self, source_registry: SourceRegistry | None = None) -> None:
        self.source_registry = source_registry
        self.ledger_builder = DataControlLedgerBuilder()

    @classmethod
    def from_registry_file(cls, file_path: str | Path) -> "DataControlPipeline":
        return cls(source_registry=SourceRegistry.from_file(file_path))

    @staticmethod
    def default_steps() -> list[DataControlStepDefinition]:
        return [
            DataControlStepDefinition(
                stage=DataControlStage.CAPTURE,
                entrypoint="neotrade3.data_control.pipeline:DataControlPipeline.capture",
                description="Collect raw source snapshots into the capture layer.",
                writes_to_official_store=False,
            ),
            DataControlStepDefinition(
                stage=DataControlStage.COMPOSE,
                entrypoint="neotrade3.data_control.pipeline:DataControlPipeline.compose",
                description="Compose validated candidates from captured inputs.",
                writes_to_official_store=False,
            ),
            DataControlStepDefinition(
                stage=DataControlStage.PUBLISH,
                entrypoint="neotrade3.data_control.pipeline:DataControlPipeline.publish",
                description="Publish approved outputs into the official daily dataset.",
                writes_to_official_store=True,
            ),
        ]

    def build_plan(self, target_date: date) -> DataControlPlan:
        return DataControlPlan(target_date=target_date, steps=self.default_steps())

    def describe_sources(self) -> dict[str, list[str]]:
        if self.source_registry is None:
            return {}

        return {
            stage.value: [
                source.source_id
                for source in self.source_registry.sources_for_stage(stage.value)
            ]
            for stage in DataControlStage
        }

    def build_plan_ledger(self, plan: DataControlPlan) -> list[DataControlLedgerEntry]:
        stage_sources = {
            stage: self.describe_sources().get(stage.value, [])
            for stage in DataControlStage
        }
        return self.ledger_builder.build_plan_entries(plan, stage_sources)

    @staticmethod
    def _normalize_formal_codes(codes: list[str] | None, *, limit: int) -> list[str]:
        out: list[str] = []
        seen: set[str] = set()
        for raw in list(codes or []):
            code = str(raw or "").strip().split(".", 1)[0].strip()
            if not code or code in seen:
                continue
            seen.add(code)
            out.append(code)
            if len(out) >= int(limit):
                break
        return out

    @staticmethod
    def _formal_object_summary(payload: object) -> dict[str, object]:
        if not isinstance(payload, dict):
            return {
                "status": "unavailable",
                "count": 0,
                "attention_count": 0,
                "freshness_verdict": "unknown",
            }
        attention_items = payload.get("attention_items")
        freshness_proof = payload.get("freshness_proof")
        return {
            "status": str(payload.get("_meta", {}).get("status", "ok"))
            if isinstance(payload.get("_meta"), dict)
            else "ok",
            "count": int(payload.get("count") or 0) if isinstance(payload.get("count"), int) else 0,
            "attention_count": len(attention_items) if isinstance(attention_items, list) else 0,
            "freshness_verdict": (
                str(freshness_proof.get("verdict", "unknown"))
                if isinstance(freshness_proof, dict)
                else "unknown"
            ),
        }

    def _build_m1_formal_artifacts(
        self,
        *,
        target_date: date,
        preferred_codes: list[str] | None = None,
        sample_limit: int = 5,
    ) -> dict[str, object]:
        try:
            from apps.api.main import BootstrapApiService

            service = BootstrapApiService(project_root=self._project_root())
            normalized_codes = self._normalize_formal_codes(
                preferred_codes, limit=int(sample_limit)
            )
            d1_payload = cast(
                dict[str, object],
                service.m1_d1_daily_price_facts_view(
                    target_date=target_date.isoformat(),
                    stock_codes=normalized_codes or None,
                    limit=sample_limit,
                ),
            )
            sample_codes = normalized_codes or self._normalize_formal_codes(
                [
                    str(item.get("stock_code") or "").strip()
                    for item in list(d1_payload.get("items") or [])
                    if isinstance(item, dict)
                ],
                limit=int(sample_limit),
            )
            d7_security_payload = cast(
                dict[str, object],
                service.m1_d7_security_master_view(
                    stock_codes=sample_codes or None,
                    limit=sample_limit,
                ),
            )
            d7_trading_day_payload = cast(
                dict[str, object],
                service.m1_d7_trading_day_status_view(
                    target_date=target_date.isoformat()
                ),
            )
            d8_payload = cast(
                dict[str, object],
                service.m1_d8_trading_profiles_view(
                    target_date=target_date.isoformat(),
                    stock_codes=sample_codes or None,
                    limit=sample_limit,
                ),
            )
            return {
                "status": "ok",
                "target_date": target_date.isoformat(),
                "sample_codes": sample_codes,
                "catalog": service._m1_formal_contract_catalog(),
                "objects": {
                    "d1_daily_price_fact": d1_payload,
                    "d7_security_master_minimal": d7_security_payload,
                    "d7_trading_day_status": d7_trading_day_payload,
                    "pf1_trading_profile": d8_payload,
                },
                "summary": {
                    "d1_daily_price_fact": self._formal_object_summary(d1_payload),
                    "d7_security_master_minimal": self._formal_object_summary(
                        d7_security_payload
                    ),
                    "d7_trading_day_status": self._formal_object_summary(
                        d7_trading_day_payload
                    ),
                    "pf1_trading_profile": self._formal_object_summary(d8_payload),
                },
            }
        except Exception as exc:
            return {
                "status": "failed",
                "target_date": target_date.isoformat(),
                "error": str(exc),
                "sample_codes": self._normalize_formal_codes(
                    preferred_codes, limit=int(sample_limit)
                ),
            }

    def capture(
        self,
        *,
        target_date: date,
        requested_by: str = "data_control.capture",
        dry_run: bool = False,
    ) -> DataControlStepResult:
        authoritative_update: dict[str, object] | None = None
        if not dry_run and os.environ.get("NEOTRADE3_ENABLE_TENCENT_UPDATE") == "1":
            try:
                from apps.api.main import BootstrapApiService

                service = BootstrapApiService(project_root=self._project_root())
                authoritative_update = cast(
                    dict[str, object],
                    service.update_daily_prices_authoritative_view(
                        target_date=target_date.isoformat(),
                        requested_by=requested_by,
                    ),
                )
            except Exception as exc:
                authoritative_update = {
                    "status": "failed",
                    "message": "authoritative_update_failed",
                    "error": str(exc),
                }

        self._maybe_rebuild_trading_calendar()
        db_path = self._stock_db_path()
        target_day_check: dict[str, object] | None = None
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(1) FROM daily_prices WHERE trade_date = ?",
                (target_date.isoformat(),),
            )
            target_rows = int(cursor.fetchone()[0] or 0)

            calendar_table: str | None = None
            calendar_is_trading_day: bool | None = None
            for table_name in ("trading_calendar_cache", "trading_calendar"):
                try:
                    row = cursor.execute(
                        f"SELECT 1 FROM {table_name} WHERE trade_date = ? LIMIT 1",
                        (target_date.isoformat(),),
                    ).fetchone()
                except sqlite3.Error:
                    continue
                calendar_table = table_name
                calendar_is_trading_day = bool(row)
                break
            target_day_check = {
                "trade_date": target_date.isoformat(),
                "target_rows": target_rows,
                "calendar_table": calendar_table or "unavailable",
                "calendar_is_trading_day": calendar_is_trading_day,
            }
        except Exception:
            target_day_check = None
        finally:
            try:
                conn.close()
            except Exception:
                pass

        validation_before = self._validate_units_in_stock_db(db_path=db_path, sample_limit=200)
        normalization: dict[str, object] | None = None

        validation = validation_before
        if (
            not dry_run
            and isinstance(validation_before, dict)
            and validation_before.get("status") != "ok"
            and isinstance(validation_before.get("detected"), dict)
            and validation_before.get("detected", {}).get("volume_unit") == "lot"
        ):
            latest_trade_date = self._latest_trade_date_in_stock_db(db_path=db_path)
            normalized_rows = (
                self._normalize_daily_prices_volume_to_shares_if_needed(
                    db_path=db_path, trade_date=latest_trade_date
                )
                if latest_trade_date
                else 0
            )
            validation = self._validate_units_in_stock_db(db_path=db_path, sample_limit=200)
            normalization = {
                "normalized_rows": int(normalized_rows),
                "trade_date": latest_trade_date,
            }

        status = "ok" if validation.get("status") == "ok" else "failed"
        if (
            target_day_check is not None
            and target_day_check.get("calendar_is_trading_day") is True
            and int(target_day_check.get("target_rows") or 0) == 0
        ):
            status = "failed"
        if status == "ok":
            message = "capture 已完成单位校验与交易日历生成。"
            if normalization is not None and int(normalization.get("normalized_rows") or 0) > 0:
                message = "capture 已自动修复 volume 单位并生成交易日历。"
        else:
            message = "capture 失败：行情未覆盖目标交易日或单位校验未通过，禁止进入 compose/publish。"
        payload = {
            "version": 1,
            "target_date": target_date.isoformat(),
            "requested_by": requested_by,
            "requested_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "status": status,
            "message": message,
                    "authoritative_update": authoritative_update,
            "target_day_check": target_day_check,
            "units_validation": validation,
            "units_validation_before": validation_before,
            "normalization": normalization,
            "outputs": {"trading_calendar_generated": True},
            "m1_formal_artifacts": self._build_m1_formal_artifacts(target_date=target_date),
        }
        if not dry_run:
            ledger_path, artifact_path = self._stage_paths(
                target_date=target_date, stage=DataControlStage.CAPTURE
            )
            ledger_path.parent.mkdir(parents=True, exist_ok=True)
            artifact_path.parent.mkdir(parents=True, exist_ok=True)
            ledger_path.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True)
                + "\n",
                encoding="utf-8",
            )
            artifact_path.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True)
                + "\n",
                encoding="utf-8",
            )
        return DataControlStepResult(
            stage=DataControlStage.CAPTURE,
            status=status,
            message=message,
        )

    @staticmethod
    def _latest_trade_date_in_stock_db(*, db_path: Path) -> str | None:
        if not db_path.exists() or not db_path.is_file():
            return None
        try:
            conn = sqlite3.connect(str(db_path))
        except Exception:
            return None
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(trade_date) FROM daily_prices")
            row = cursor.fetchone()
            return str(row[0]) if row and row[0] is not None else None
        except Exception:
            return None
        finally:
            try:
                conn.close()
            except Exception:
                pass

    @staticmethod
    def _normalize_daily_prices_volume_to_shares_if_needed(
        *, db_path: Path, trade_date: str | None = None
    ) -> int:
        if not db_path.exists() or not db_path.is_file():
            return 0
        try:
            conn = sqlite3.connect(str(db_path), timeout=30.0)
            conn.execute("PRAGMA busy_timeout = 30000")
        except Exception:
            return 0
        try:
            cursor = conn.cursor()
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
            last_exc: Exception | None = None
            for attempt in range(6):
                try:
                    cursor.execute(
                        f"UPDATE daily_prices SET volume = volume * 100 {where}", params
                    )
                    cursor.execute("SELECT changes()")
                    changed = int(cursor.fetchone()[0] or 0)
                    conn.commit()
                    return changed
                except sqlite3.OperationalError as exc:
                    last_exc = exc
                    msg = str(exc).lower()
                    if "database is locked" not in msg and "database is busy" not in msg:
                        raise
                    try:
                        conn.rollback()
                    except Exception:
                        pass
                    time.sleep(0.2 * (2**attempt))
            if last_exc is not None:
                raise last_exc
            return 0
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            return 0
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def compose(
        self,
        *,
        target_date: date,
        requested_by: str = "data_control.compose",
        dry_run: bool = False,
    ) -> DataControlStepResult:
        db_path = self._stock_db_path()
        candidates, sector_top5, warnings = self._compose_candidate_universe(
            db_path=db_path, target_date=target_date
        )
        status = "ok" if candidates else "failed"
        if status == "ok":
            message = "compose 已生成候选集合与板块聚合（资金/情绪 proxy）。"
        else:
            message = "compose 失败：无法从行情库生成候选集合。"
        payload = {
            "version": 1,
            "target_date": target_date.isoformat(),
            "requested_by": requested_by,
            "requested_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "status": status,
            "message": message,
            "candidate_universe": candidates,
            "sector_top5_by_amount": sector_top5,
            "warnings": warnings,
            "m1_formal_artifacts": self._build_m1_formal_artifacts(
                target_date=target_date,
                preferred_codes=[
                    str(item.get("stock_code") or "").strip()
                    for item in candidates[:5]
                    if isinstance(item, dict)
                ],
            ),
        }
        if not dry_run:
            ledger_path, artifact_path = self._stage_paths(
                target_date=target_date, stage=DataControlStage.COMPOSE
            )
            ledger_path.parent.mkdir(parents=True, exist_ok=True)
            artifact_path.parent.mkdir(parents=True, exist_ok=True)
            ledger_path.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True)
                + "\n",
                encoding="utf-8",
            )
            artifact_path.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True)
                + "\n",
                encoding="utf-8",
            )
        return DataControlStepResult(
            stage=DataControlStage.COMPOSE,
            status=status,
            message=message,
        )

    def publish(
        self,
        *,
        target_date: date,
        requested_by: str = "data_control.publish",
        dry_run: bool = False,
    ) -> DataControlStepResult:
        db_path = self._stock_db_path()
        calendar_path = (
            self._project_root() / "var/ledgers/trading_calendar/trading_calendar.json"
        )
        compose_ledger_path, compose_artifact_path = self._stage_paths(
            target_date=target_date, stage=DataControlStage.COMPOSE
        )
        validation: dict[str, object] | None = None
        prerequisites = {
            "has_trading_calendar": calendar_path.exists(),
            "has_compose_artifact": compose_artifact_path.exists(),
        }
        if not calendar_path.exists():
            status = "failed"
            message = "publish 失败：交易日历缺失。请先执行 capture。"
        elif not compose_artifact_path.exists():
            status = "failed"
            message = "publish 失败：compose 产物缺失。请先执行 compose。"
        else:
            validation = self._validate_units_in_stock_db(
                db_path=db_path, sample_limit=200
            )
            if validation.get("status") == "ok":
                status = "ok"
                message = "publish 通过：单位校验 ok（volume=股、pct_change=%），且 compose 产物存在，可进入 publish_gated_jobs。"
            else:
                status = "failed"
                message = "publish 失败：单位校验未通过（禁止发布）。"

        compose_sample_codes: list[str] = []
        if compose_artifact_path.exists():
            try:
                compose_payload = json.loads(
                    compose_artifact_path.read_text(encoding="utf-8")
                )
            except (OSError, json.JSONDecodeError):
                compose_payload = None
            if isinstance(compose_payload, dict):
                compose_sample_codes = [
                    str(item.get("stock_code") or "").strip()
                    for item in list(compose_payload.get("candidate_universe") or [])[:5]
                    if isinstance(item, dict)
                ]

        payload = {
            "version": 1,
            "target_date": target_date.isoformat(),
            "requested_by": requested_by,
            "requested_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "status": status,
            "message": message,
            "prerequisites": prerequisites,
            "units_validation": validation,
            "published_daily_data": {
                "target_date": target_date.isoformat(),
                "compose_artifact_available": compose_artifact_path.exists(),
            },
            "m1_formal_artifacts": self._build_m1_formal_artifacts(
                target_date=target_date,
                preferred_codes=compose_sample_codes,
            ),
        }
        if not dry_run:
            ledger_path, artifact_path = self._stage_paths(
                target_date=target_date, stage=DataControlStage.PUBLISH
            )
            ledger_path.parent.mkdir(parents=True, exist_ok=True)
            artifact_path.parent.mkdir(parents=True, exist_ok=True)
            ledger_path.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True)
                + "\n",
                encoding="utf-8",
            )
            artifact_path.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True)
                + "\n",
                encoding="utf-8",
            )
        return DataControlStepResult(
            stage=DataControlStage.PUBLISH,
            status=status,
            message=message,
        )

    @staticmethod
    def _project_root() -> Path:
        return Path(__file__).resolve().parents[2]

    def _maybe_rebuild_trading_calendar(self) -> None:
        project_root = self._project_root()
        sqlite_db_path = os.environ.get("NEOTRADE3_STOCK_DB_PATH") or str(
            project_root / "var/db/stock_data.db"
        )
        db_path = Path(sqlite_db_path).expanduser()
        if not db_path.exists() or not db_path.is_file():
            return
        ledger_file = (
            project_root / "var/ledgers/trading_calendar/trading_calendar.json"
        )

        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT trade_date FROM daily_prices")
            rows = cursor.fetchall()
        except Exception as exc:
            logger.warning("Failed to read trading calendar from stock db: %s", exc)
            return
        finally:
            try:
                conn.close()
            except Exception as exc:
                logger.debug("Failed to close sqlite connection: %s", exc)

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
            return

        payload = {
            "version": 1,
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "generated_by": "data_control.capture",
            "source": {
                "type": "sqlite",
                "table": "daily_prices",
                "date_column": "trade_date",
            },
            "trading_days": days,
            "trading_day_count": len(days),
        }
        ledger_file.parent.mkdir(parents=True, exist_ok=True)
        ledger_file.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def _stock_db_path() -> Path:
        project_root = DataControlPipeline._project_root()
        sqlite_db_path = os.environ.get("NEOTRADE3_STOCK_DB_PATH") or str(
            project_root / "var/db/stock_data.db"
        )
        return Path(sqlite_db_path).expanduser()

    @staticmethod
    def _validate_units_in_stock_db(
        *, db_path: Path, sample_limit: int
    ) -> dict[str, object]:
        if not db_path.exists() or not db_path.is_file():
            return {
                "status": "failed",
                "message": "stock db not found",
                "reasons": ["db_path missing"],
            }
        try:
            conn = sqlite3.connect(str(db_path))
        except Exception as exc:
            return {"status": "failed", "message": "invalid db", "reasons": [str(exc)]}
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
            return {
                "status": "failed",
                "message": "query failed",
                "reasons": [str(exc)],
            }
        finally:
            conn.close()

        if not rows:
            return {
                "status": "failed",
                "message": "no valid samples",
                "reasons": [
                    "daily_prices lacks required sample rows for unit validation."
                ],
            }

        pct_diffs_percent: list[float] = []
        pct_diffs_decimal: list[float] = []
        lot_rel_errors: list[float] = []
        share_rel_errors: list[float] = []
        for trade_date, code, close, preclose, pct_change, volume, amount in rows:
            try:
                close_f = float(close)
                preclose_f = float(preclose)
                pct_f = float(pct_change)
                vol_f = float(volume)
                amt_f = float(amount)
            except (TypeError, ValueError):
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

        if not pct_diffs_percent or not share_rel_errors:
            return {
                "status": "failed",
                "message": "insufficient parsable samples",
                "reasons": [],
            }

        pct_unit = (
            "percent"
            if statistics.median(pct_diffs_percent)
            <= statistics.median(pct_diffs_decimal)
            else "decimal"
        )
        volume_unit = (
            "share"
            if statistics.median(share_rel_errors) <= statistics.median(lot_rel_errors)
            else "lot"
        )

        ok = pct_unit == "percent" and volume_unit == "share"
        return {
            "status": "ok" if ok else "failed",
            "message": "ok" if ok else "unit mismatch",
            "detected": {"pct_change_unit": pct_unit, "volume_unit": volume_unit},
        }

    @staticmethod
    def _compose_candidate_universe(
        *,
        db_path: Path,
        target_date: date,
        limit: int = 300,
    ) -> tuple[list[dict[str, object]], list[dict[str, object]], list[str]]:
        if not db_path.exists() or not db_path.is_file():
            return [], [], ["stock db missing"]

        warnings: list[str] = []
        try:
            conn = sqlite3.connect(str(db_path))
        except Exception as exc:
            return [], [], [f"failed to open sqlite db: {exc}"]
        try:
            cursor = conn.cursor()
            query_attempts: list[tuple[str, bool, bool]] = [
                (
                    "SELECT dp.code, COALESCE(s.name,''), COALESCE(s.sector_lv1,''), COALESCE(s.sector_lv2,''), "
                    "dp.close, dp.preclose, dp.pct_change, dp.amount, dp.volume, s.circulating_market_cap "
                    "FROM daily_prices dp "
                    "JOIN stocks s ON s.code = dp.code "
                    "WHERE dp.trade_date = ? "
                    "AND COALESCE(s.asset_type, 'stock') = 'stock' "
                    "AND COALESCE(s.is_delisted, 0) = 0 "
                    "ORDER BY dp.amount DESC "
                    "LIMIT ?",
                    True,
                    True,
                ),
                (
                    "SELECT dp.code, COALESCE(s.name,''), COALESCE(s.sector_lv1,''), COALESCE(s.sector_lv2,''), "
                    "dp.close, dp.preclose, dp.pct_change, dp.amount, dp.volume, NULL "
                    "FROM daily_prices dp "
                    "JOIN stocks s ON s.code = dp.code "
                    "WHERE dp.trade_date = ? "
                    "AND COALESCE(s.asset_type, 'stock') = 'stock' "
                    "AND COALESCE(s.is_delisted, 0) = 0 "
                    "ORDER BY dp.amount DESC "
                    "LIMIT ?",
                    True,
                    False,
                ),
                (
                    "SELECT dp.code, COALESCE(s.name,''), COALESCE(s.sector_lv1,''), COALESCE(s.sector_lv2,''), "
                    "dp.close, dp.preclose, dp.pct_change, dp.amount, NULL "
                    "FROM daily_prices dp "
                    "JOIN stocks s ON s.code = dp.code "
                    "WHERE dp.trade_date = ? "
                    "AND COALESCE(s.asset_type, 'stock') = 'stock' "
                    "AND COALESCE(s.is_delisted, 0) = 0 "
                    "ORDER BY dp.amount DESC "
                    "LIMIT ?",
                    False,
                    False,
                ),
            ]
            rows = []
            has_volume = False
            has_cap = False
            last_exc: Exception | None = None
            for sql, attempt_has_volume, attempt_has_cap in query_attempts:
                try:
                    cursor.execute(sql, (target_date.isoformat(), int(limit)))
                    rows = cursor.fetchall()
                    has_volume = attempt_has_volume
                    has_cap = attempt_has_cap
                    break
                except Exception as exc:
                    last_exc = exc
                    continue
            if last_exc is not None and not rows:
                raise last_exc
            if not has_volume:
                warnings.append(
                    "daily_prices.volume 列缺失或不可用，本次 compose 不输出 volume 字段。"
                )
            if not has_cap:
                warnings.append(
                    "stocks.circulating_market_cap 列缺失或不可用，本次 compose 不输出流通市值字段。"
                )
        except Exception as exc:
            return [], [], [f"compose query failed: {exc}"]
        finally:
            conn.close()

        candidates: list[dict[str, object]] = []
        sector_amount: dict[str, float] = {}
        sector_counts: dict[str, int] = {}
        for row in rows:
            if has_volume:
                (
                    code,
                    name,
                    sector_lv1,
                    sector_lv2,
                    close,
                    preclose,
                    pct_change,
                    amount,
                    volume,
                    market_cap,
                ) = row
            else:
                (
                    code,
                    name,
                    sector_lv1,
                    sector_lv2,
                    close,
                    preclose,
                    pct_change,
                    amount,
                    market_cap,
                ) = row
                volume = None

            code_str = str(code)
            name_str = str(name or "")
            if code_str.startswith("399"):
                continue
            if code_str.startswith(("43", "83", "87", "88")):
                continue
            if any(keyword in name_str for keyword in ("*ST", "ST", "PT")):
                continue

            amount_f = float(amount) if amount is not None else 0.0
            sector_key = str(sector_lv1 or "").strip() or "unknown"
            sector_amount[sector_key] = sector_amount.get(sector_key, 0.0) + amount_f
            sector_counts[sector_key] = sector_counts.get(sector_key, 0) + 1

            item: dict[str, object] = {
                "stock_code": code_str,
                "stock_name": name_str,
                "sector_lv1": str(sector_lv1 or "").strip() or None,
                "sector_lv2": str(sector_lv2 or "").strip() or None,
                "close": float(close) if close is not None else None,
                "preclose": float(preclose) if preclose is not None else None,
                "pct_change": float(pct_change) if pct_change is not None else None,
                "amount": amount_f,
                "circulating_market_cap": (
                    float(market_cap) if (has_cap and market_cap is not None) else None
                ),
            }
            if volume is not None:
                try:
                    item["volume"] = float(volume)
                except (TypeError, ValueError):
                    item["volume"] = None
            candidates.append(item)

        candidates.sort(
            key=lambda x: float(cast(Any, x.get("amount") or 0.0)),
            reverse=True,
        )
        sector_items = [
            {
                "sector_lv1": sector,
                "amount_sum": round(amount_sum, 2),
                "stock_count": int(sector_counts.get(sector, 0)),
            }
            for sector, amount_sum in sector_amount.items()
        ]
        sector_items.sort(
            key=lambda x: float(cast(Any, x.get("amount_sum") or 0.0)),
            reverse=True,
        )
        return candidates, sector_items[:5], warnings

    def _stage_paths(
        self, *, target_date: date, stage: DataControlStage
    ) -> tuple[Path, Path]:
        date_key = target_date.isoformat()
        ledgers_dir = self._project_root() / "var/ledgers/data_control" / date_key
        artifacts_dir = self._project_root() / "var/artifacts/data_control" / date_key
        ledger_path = ledgers_dir / f"data_control_{stage.value}_ledger.json"
        artifact_path = artifacts_dir / f"data_control_{stage.value}_result.json"
        return ledger_path, artifact_path
