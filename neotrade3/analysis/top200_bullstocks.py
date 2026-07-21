from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any, Iterable


def _a_share_universe_sql(*, alias: str = "s") -> str:
    a = str(alias or "s").strip() or "s"
    return f"""
        length({a}.code) = 6
        AND ({a}.is_delisted IS NULL OR {a}.is_delisted = 0)
        AND (
            {a}.code GLOB '60[0-9][0-9][0-9][0-9]'
            OR {a}.code GLOB '688[0-9][0-9][0-9]'
            OR {a}.code GLOB '300[0-9][0-9][0-9]'
            OR {a}.code GLOB '301[0-9][0-9][0-9]'
            OR {a}.code GLOB '00[0-9][0-9][0-9][0-9]'
        )
    """


@dataclass(frozen=True)
class BullStockRankingRow:
    rank: int
    code: str
    name: str
    sector_lv1: str
    max_runup_pct: float
    first_trade_date: str
    last_trade_date: str

    def to_payload(self) -> dict[str, Any]:
        return {
            "rank": int(self.rank),
            "code": str(self.code),
            "name": str(self.name),
            "sector_lv1": str(self.sector_lv1),
            "max_runup_pct": float(self.max_runup_pct),
            "first_trade_date": str(self.first_trade_date),
            "last_trade_date": str(self.last_trade_date),
        }


def load_global_top_bullstocks(
    conn: sqlite3.Connection,
    *,
    limit: int = 200,
) -> list[BullStockRankingRow]:
    if int(limit) <= 0:
        raise ValueError("limit must be positive")

    sql = f"""
    WITH universe AS (
        SELECT s.code, COALESCE(s.name, '') AS name, COALESCE(s.sector_lv1, '') AS sector_lv1
        FROM stocks s
        WHERE {_a_share_universe_sql(alias="s")}
    ),
    base_prices AS (
        SELECT d.code, d.trade_date, d.close
        FROM daily_prices d
        JOIN universe u ON u.code = d.code
        WHERE d.trade_date IS NOT NULL AND d.close IS NOT NULL AND d.close > 0
    ),
    priced AS (
        SELECT
            bp.code AS code,
            bp.trade_date AS trade_date,
            bp.close AS close,
            MIN(bp.close) OVER (
                PARTITION BY bp.code
                ORDER BY bp.trade_date
                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
            ) AS min_close_so_far
        FROM base_prices bp
    ),
    runups AS (
        SELECT
            p.code AS code,
            MIN(p.trade_date) AS first_dt,
            MAX(p.trade_date) AS last_dt,
            MAX(((p.close / p.min_close_so_far) - 1.0) * 100.0) AS max_runup_pct
        FROM priced p
        GROUP BY p.code
    )
    SELECT
        r.code,
        u.name,
        u.sector_lv1,
        r.first_dt,
        r.last_dt,
        r.max_runup_pct
    FROM runups r
    JOIN universe u ON u.code = r.code
    WHERE r.first_dt IS NOT NULL
      AND r.last_dt IS NOT NULL
      AND r.max_runup_pct IS NOT NULL
    ORDER BY r.max_runup_pct DESC, r.code ASC
    LIMIT ?
    """
    rows = conn.execute(sql, (int(limit),)).fetchall()
    if len(rows) < int(limit):
        raise RuntimeError(
            f"global top bullstocks ranking size {len(rows)} < {int(limit)}"
        )
    out: list[BullStockRankingRow] = []
    for idx, row in enumerate(rows, start=1):
        out.append(
            BullStockRankingRow(
                rank=idx,
                code=str(row[0]),
                name=str(row[1] or "").strip() or str(row[0]),
                sector_lv1=str(row[2] or "").strip(),
                first_trade_date=str(row[3]),
                last_trade_date=str(row[4]),
                max_runup_pct=float(row[5]),
            )
        )
    return out


def extract_codes(rows: Iterable[BullStockRankingRow]) -> list[str]:
    out: list[str] = []
    for r in rows:
        c = str(getattr(r, "code", "") or "").strip()
        if c:
            out.append(c)
    return out

