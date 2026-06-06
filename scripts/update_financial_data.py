#!/usr/bin/env python3
"""Update financial data (ROE, EPS, etc.) in stocks table from mootdx."""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from neotrade3.data_sources import MootdxAdapter


def update_stocks_financial_data(
    db_path: str | Path,
    report_period: str | None = None,
    dry_run: bool = False,
) -> dict[str, int]:
    """Update stocks table with financial data from mootdx.

    Args:
        db_path: Path to SQLite database
        report_period: Report period in YYYYMMDD format, or None for latest
        dry_run: If True, don't actually update database

    Returns:
        Statistics dict with counts
    """
    db_path = Path(db_path)
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    # Fetch financial data from mootdx
    print(f"Fetching financial data from mootdx (period: {report_period or 'latest'})...")
    adapter = MootdxAdapter(cache_dir=project_root / "var" / "cache" / "mootdx")

    try:
        records = adapter.fetch_financial_data(report_period=report_period)
    except ImportError as exc:
        print(f"Error: {exc}")
        print("Please install mootdx: pip install mootdx")
        sys.exit(1)
    except Exception as exc:
        print(f"Error fetching data: {exc}")
        sys.exit(1)

    print(f"Fetched {len(records)} financial records")

    if not records:
        return {"fetched": 0, "updated": 0, "skipped": 0}

    # Build lookup dict by code
    financial_data: dict[str, dict] = {}
    for r in records:
        financial_data[r.code] = {
            "roe": r.roe,
            "eps": r.eps,
            "debt_ratio": r.debt_ratio,
            "revenue_growth": r.revenue_growth,
            "profit_growth": r.profit_growth,
            "report_period": r.report_period,
        }

    # Update database
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Check current ROE coverage
    cursor.execute("SELECT COUNT(*) FROM stocks WHERE roe IS NOT NULL AND roe > 0")
    roe_before = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM stocks")
    total_stocks = cursor.fetchone()[0]

    print(f"Current ROE coverage: {roe_before}/{total_stocks} ({roe_before/total_stocks*100:.1f}%)")

    # Update stocks
    updated = 0
    skipped = 0

    for code, data in financial_data.items():
        # Check if stock exists
        cursor.execute("SELECT code FROM stocks WHERE code = ?", (code,))
        if not cursor.fetchone():
            skipped += 1
            continue

        if dry_run:
            updated += 1
            continue

        # Update financial fields
        cursor.execute(
            """
            UPDATE stocks SET
                roe = ?,
                eps = ?,
                debt_ratio = ?,
                revenue_growth = ?,
                profit_growth = ?,
                updated_at = datetime('now')
            WHERE code = ?
            """,
            (
                data["roe"],
                data["eps"],
                data["debt_ratio"],
                data["revenue_growth"],
                data["profit_growth"],
                code,
            ),
        )
        if cursor.rowcount > 0:
            updated += 1

    if not dry_run:
        conn.commit()

    # Check new ROE coverage
    cursor.execute("SELECT COUNT(*) FROM stocks WHERE roe IS NOT NULL AND roe > 0")
    roe_after = cursor.fetchone()[0]
    conn.close()

    print(f"New ROE coverage: {roe_after}/{total_stocks} ({roe_after/total_stocks*100:.1f}%)")
    print(f"Updated: {updated}, Skipped (not in DB): {skipped}")

    return {
        "fetched": len(records),
        "updated": updated,
        "skipped": skipped,
        "roe_before": roe_before,
        "roe_after": roe_after,
        "total_stocks": total_stocks,
    }


def main():
    parser = argparse.ArgumentParser(description="Update financial data from mootdx")
    parser.add_argument(
        "--db-path",
        default=project_root / "var" / "db" / "stock_data.db",
        help="Path to SQLite database",
    )
    parser.add_argument(
        "--period",
        help="Report period in YYYYMMDD format (e.g., 20250331 for Q1 2025)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be updated without making changes",
    )
    parser.add_argument(
        "--list-periods",
        action="store_true",
        help="List available report periods from mootdx",
    )

    args = parser.parse_args()

    if args.list_periods:
        adapter = MootdxAdapter()
        periods = adapter.get_available_periods()
        print("Available report periods:")
        for p in periods[:10]:  # Show first 10
            print(f"  {p}")
        return

    stats = update_stocks_financial_data(
        db_path=args.db_path,
        report_period=args.period,
        dry_run=args.dry_run,
    )

    if args.dry_run:
        print("\n(Dry run - no changes made)")


if __name__ == "__main__":
    main()
