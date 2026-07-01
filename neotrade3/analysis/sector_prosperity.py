from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Optional


@dataclass(frozen=True)
class SectorProsperityScore:
    sector_lv1: str
    scores: dict[str, Optional[float]]
    coverage: dict[str, float]
    evidence: dict[str, Any]


class SectorProsperityBuilder:
    def __init__(self, db_path: str | Path, project_root: str | Path | None = None) -> None:
        self.db_path = Path(db_path)
        self.project_root = Path(project_root) if project_root else None

    def build(
        self,
        *,
        target_date: str,
        lookback_trading_days: int = 120,
        min_coverage_core: float = 0.6,
        weights: Optional[dict[str, float]] = None,
    ) -> dict[str, Any]:
        date.fromisoformat(target_date)
        if lookback_trading_days <= 0:
            raise ValueError("lookback_trading_days must be a positive integer")

        w = dict(weights or {})
        w.setdefault("policy", 0.25)
        w.setdefault("capital", 0.25)
        w.setdefault("us_mapping", 0.15)
        w.setdefault("financial", 0.20)
        w.setdefault("supply_demand", 0.10)
        w.setdefault("tech_cycle", 0.05)

        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            trading_days: list[str] = []
            try:
                cursor.execute(
                    "SELECT trade_date FROM trading_calendar_cache WHERE trade_date <= ? ORDER BY trade_date DESC LIMIT ?",
                    (target_date, int(lookback_trading_days)),
                )
                rows = cursor.fetchall() or []
                trading_days = [str(r[0]) for r in rows if r and r[0]]
            except sqlite3.Error:
                trading_days = []
            if not trading_days:
                cursor.execute(
                    "SELECT DISTINCT trade_date FROM daily_prices WHERE trade_date <= ? ORDER BY trade_date DESC LIMIT ?",
                    (target_date, int(lookback_trading_days)),
                )
                rows = cursor.fetchall() or []
                trading_days = [str(r[0]) for r in rows if r and r[0]]
            if not trading_days:
                return self._empty_payload(target_date=target_date, weights=w)

            used_date = trading_days[0]
            window_days = list(reversed(trading_days))

            cursor.execute(
                """
                SELECT s.sector_lv1 AS sector, dp.trade_date, SUM(dp.amount) AS total_amount, AVG(dp.pct_change) AS avg_pct
                FROM daily_prices dp
                JOIN stocks s ON dp.code = s.code
                WHERE dp.trade_date IN ({})
                  AND s.sector_lv1 IS NOT NULL
                  AND (s.is_delisted IS NULL OR s.is_delisted = 0)
                GROUP BY s.sector_lv1, dp.trade_date
                """.format(
                    ",".join(["?"] * len(window_days))
                ),
                tuple(window_days),
            )
            sector_day_rows = cursor.fetchall() or []

            by_sector: dict[str, dict[str, dict[str, float]]] = {}
            for r in sector_day_rows:
                sec = str(r["sector"] or "").strip()
                d = str(r["trade_date"] or "").strip()
                if not sec or not d:
                    continue
                by_sector.setdefault(sec, {})
                by_sector[sec][d] = {
                    "total_amount": float(r["total_amount"] or 0.0),
                    "avg_pct": float(r["avg_pct"] or 0.0),
                }

            sectors: list[SectorProsperityScore] = []
            capital_scores_raw: dict[str, float] = {}
            for sec, series in by_sector.items():
                amounts = [float(series.get(d, {}).get("total_amount") or 0.0) for d in window_days]
                if not any(a > 0 for a in amounts):
                    continue
                today_amount = float(series.get(used_date, {}).get("total_amount") or 0.0)

                tail_20 = [a for a in amounts[-20:] if isinstance(a, (int, float))]
                tail_60 = [a for a in amounts[-60:] if isinstance(a, (int, float))]
                avg20 = float(sum(tail_20) / float(max(1, len(tail_20))))
                avg60 = float(sum(tail_60) / float(max(1, len(tail_60))))
                ratio20 = today_amount / max(avg20, 1e-9)
                accel = avg20 / max(avg60, 1e-9)
                capital_scores_raw[sec] = float(ratio20 * 0.6 + accel * 0.4)

            def _rank_to_100(values_by_key: dict[str, float]) -> dict[str, float]:
                items = [(k, float(v)) for k, v in values_by_key.items() if k and isinstance(v, (int, float))]
                items.sort(key=lambda x: x[1])
                n = len(items)
                if n == 0:
                    return {}
                if n == 1:
                    return {items[0][0]: 100.0}
                out: dict[str, float] = {}
                for i, (k, _v) in enumerate(items):
                    out[k] = float(i) / float(n - 1) * 100.0
                return out

            capital_rank = _rank_to_100(capital_scores_raw)

            for sec, series in by_sector.items():
                if sec not in capital_rank:
                    continue
                amounts = [float(series.get(d, {}).get("total_amount") or 0.0) for d in window_days]
                avgs = [float(series.get(d, {}).get("avg_pct") or 0.0) for d in window_days]
                today_amount = float(series.get(used_date, {}).get("total_amount") or 0.0)
                today_avg_pct = float(series.get(used_date, {}).get("avg_pct") or 0.0)
                tail_20 = [a for a in amounts[-20:] if isinstance(a, (int, float))]
                tail_60 = [a for a in amounts[-60:] if isinstance(a, (int, float))]
                avg20 = float(sum(tail_20) / float(max(1, len(tail_20))))
                avg60 = float(sum(tail_60) / float(max(1, len(tail_60))))
                ratio20 = today_amount / max(avg20, 1e-9)
                accel = avg20 / max(avg60, 1e-9)
                tail_20_ret = [v for v in avgs[-20:] if isinstance(v, (int, float))]
                avg_ret_20 = float(sum(tail_20_ret) / float(max(1, len(tail_20_ret))))

                score_policy = None
                score_us = None
                score_fin = None
                score_sd = None
                score_tech = None
                score_capital = float(round(float(capital_rank.get(sec) or 0.0), 6))

                coverage = {
                    "policy": 0.0,
                    "capital": 1.0,
                    "us_mapping": 0.0,
                    "financial": 0.0,
                    "supply_demand": 0.0,
                    "tech_cycle": 0.0,
                }

                total_weight = 0.0
                weighted_sum = 0.0
                for key, weight in w.items():
                    cov = float(coverage.get(key, 0.0))
                    if cov <= 0:
                        continue
                    s = {"capital": score_capital}.get(key)
                    if isinstance(s, (int, float)):
                        weighted_sum += float(weight) * float(s)
                        total_weight += float(weight)

                total_score = None
                if total_weight > 0:
                    total_score = float(round(weighted_sum / total_weight, 6))

                core_coverage = float(
                    (coverage.get("policy", 0.0) + coverage.get("capital", 0.0) + coverage.get("financial", 0.0))
                    / 3.0
                )
                label = "insufficient_data"
                if core_coverage >= float(min_coverage_core) and isinstance(total_score, (int, float)):
                    label = "high_prosperity" if float(total_score) >= 70.0 else "watch"

                sectors.append(
                    SectorProsperityScore(
                        sector_lv1=sec,
                        scores={
                            "total": total_score,
                            "policy": score_policy,
                            "capital": score_capital,
                            "us_mapping": score_us,
                            "financial": score_fin,
                            "supply_demand": score_sd,
                            "tech_cycle": score_tech,
                        },
                        coverage=coverage,
                        evidence={
                            "as_of_date": used_date,
                            "window_trading_days": int(len(window_days)),
                            "capital_proxy": {
                                "amount_today": float(round(today_amount, 6)),
                                "amount_avg_20d": float(round(avg20, 6)),
                                "amount_avg_60d": float(round(avg60, 6)),
                                "ratio_today_over_avg20": float(round(ratio20, 6)),
                                "accel_avg20_over_avg60": float(round(accel, 6)),
                            },
                            "market_proxy": {
                                "sector_avg_pct_today": float(round(today_avg_pct, 6)),
                                "sector_avg_pct_20d": float(round(avg_ret_20, 6)),
                            },
                            "label": label,
                        },
                    )
                )

            sectors.sort(
                key=lambda s: float(s.scores["total"])
                if isinstance(s.scores.get("total"), (int, float))
                else -1e18,
                reverse=True,
            )
            return {
                "_meta": {
                    "status": "ok",
                    "data_coverage_note": "policy/us_mapping/financial/supply_demand/tech_cycle require external datasets; current build uses capital proxy only when those datasets are absent.",
                },
                "target_date": str(used_date),
                "requested_date": str(target_date),
                "weights": {k: float(v) for k, v in w.items()},
                "min_coverage_core": float(min_coverage_core),
                "sectors": [
                    {
                        "sector_lv1": s.sector_lv1,
                        "scores": s.scores,
                        "coverage": s.coverage,
                        "evidence": s.evidence,
                    }
                    for s in sectors
                ],
            }
        finally:
            conn.close()

    def _empty_payload(self, *, target_date: str, weights: dict[str, float]) -> dict[str, Any]:
        return {
            "_meta": {"status": "empty"},
            "target_date": target_date,
            "requested_date": target_date,
            "weights": {k: float(v) for k, v in weights.items()},
            "min_coverage_core": 0.0,
            "sectors": [],
        }

    @staticmethod
    def save(payload: dict[str, Any], *, project_root: str | Path, target_date: str) -> Path:
        root = Path(project_root)
        ledgers_dir = root / "var" / "ledgers" / "sector_prosperity" / target_date
        artifacts_dir = root / "var" / "artifacts" / "sector_prosperity" / target_date
        ledgers_dir.mkdir(parents=True, exist_ok=True)
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        ledger_path = ledgers_dir / "sector_prosperity_run.json"
        artifact_path = artifacts_dir / "sector_prosperity_daily.json"
        ledger_payload = {
            "status": payload.get("_meta", {}).get("status", "unknown"),
            "target_date": target_date,
            "artifact_path": f"var/artifacts/sector_prosperity/{target_date}/sector_prosperity_daily.json",
        }
        ledger_path.write_text(
            json.dumps(ledger_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        artifact_payload = dict(payload)
        meta = artifact_payload.get("_meta")
        if isinstance(meta, dict):
            meta["source"] = "stored"
        artifact_path.write_text(
            json.dumps(artifact_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return artifact_path

    @staticmethod
    def load(*, project_root: str | Path, target_date: str) -> Optional[dict[str, Any]]:
        root = Path(project_root)
        artifact_path = (
            root
            / "var"
            / "artifacts"
            / "sector_prosperity"
            / target_date
            / "sector_prosperity_daily.json"
        )
        if not artifact_path.exists():
            return None
        try:
            data = json.loads(artifact_path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else None
        except Exception:
            return None
