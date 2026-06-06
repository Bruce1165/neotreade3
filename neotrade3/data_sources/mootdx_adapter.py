"""Mootdx data source adapter for fetching financial data."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class FinancialRecord:
    """A single financial record for a stock."""

    code: str
    name: str
    # Profitability
    roe: float | None  # 净资产收益率 (%)
    roe_diluted: float | None  # 摊薄 ROE (%)
    eps: float | None  # 每股收益
    # Valuation
    pe_ratio: float | None  # 市盈率
    pb_ratio: float | None  # 市净率
    # Financial health
    debt_ratio: float | None  # 资产负债率 (%)
    current_ratio: float | None  # 流动比率
    # Growth
    revenue_growth: float | None  # 营收增长率 (%)
    profit_growth: float | None  # 净利润增长率 (%)
    # Report period
    report_period: str  # YYYYMMDD format


class MootdxAdapter:
    """Adapter for fetching financial data from mootdx (通达信) data source.

    Usage:
        adapter = MootdxAdapter()
        records = adapter.fetch_financial_data()
        for r in records:
            print(f"{r.code}: ROE={r.roe}%")
    """

    def __init__(self, cache_dir: str | Path | None = None) -> None:
        """Initialize the adapter.

        Args:
            cache_dir: Directory to cache downloaded financial files.
                      If None, uses a temporary directory.
        """
        self.cache_dir = Path(cache_dir) if cache_dir else Path(tempfile.gettempdir()) / "mootdx_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._client: Any | None = None

    def _get_affair(self) -> Any:
        """Lazy import and return mootdx Affair class."""
        try:
            from mootdx.affair import Affair
            return Affair
        except ImportError as exc:
            raise ImportError(
                "mootdx is required. Install with: pip install mootdx"
            ) from exc

    def fetch_financial_data(
        self,
        report_period: str | None = None,
    ) -> list[FinancialRecord]:
        """Fetch financial data for all stocks.

        Args:
            report_period: Report period in YYYYMMDD format (e.g., '20250331' for Q1 2025).
                          If None, fetches the latest available period.

        Returns:
            List of FinancialRecord objects.
        """
        Affair = self._get_affair()

        # Get available files
        try:
            files = Affair.files()
        except Exception as exc:
            raise RuntimeError(f"Failed to list mootdx files: {exc}") from exc

        if not files:
            return []

        # Select target file
        # files is a list of dicts, extract filenames
        filenames = [f.get("filename", "") if isinstance(f, dict) else str(f) for f in files]
        
        if report_period:
            target_file = f"gpcw{report_period}.zip"
            if target_file not in filenames:
                raise ValueError(f"Report period {report_period} not available. Available: {filenames[:5]}...")
        else:
            # Get latest file (sorted by name, gpcwYYYYMMDD.zip)
            target_file = sorted([f for f in filenames if f.startswith("gpcw")])[-1]

        # Download if not cached
        cache_path = self.cache_dir / target_file
        if not cache_path.exists():
            try:
                Affair.fetch(downdir=str(self.cache_dir), filename=target_file)
            except Exception as exc:
                raise RuntimeError(f"Failed to download {target_file}: {exc}") from exc

        # Parse financial data
        try:
            df = Affair.parse(downdir=str(self.cache_dir), filename=target_file)
        except Exception as exc:
            raise RuntimeError(f"Failed to parse financial data: {exc}") from exc

        return self._parse_dataframe(df)

    def _parse_dataframe(self, df: Any) -> list[FinancialRecord]:
        """Parse mootdx DataFrame into FinancialRecord objects."""
        records: list[FinancialRecord] = []

        # Column mapping based on mootdx documentation
        # DataFrame index is 'code', columns are Chinese financial terms
        # Handle duplicate columns by using .iloc[0] if Series is returned
        def get_value(row: Any, col: str) -> Any:
            val = row.get(col)
            if hasattr(val, 'iloc'):  # It's a Series (duplicate column)
                return val.iloc[0] if len(val) > 0 else None
            return val

        for code, row in df.iterrows():
            code = str(code).zfill(6)
            if not code or code == "000000":
                continue

            record = FinancialRecord(
                code=code,
                name="",  # Name not in financial data, will be filled from stocks table
                # ROE - 净资产收益率 (原始为单季度值，此处年化处理 ×4)
                roe=self._annualize_roe(self._safe_float(get_value(row, "净资产收益率"))),
                roe_diluted=self._annualize_roe(self._safe_float(get_value(row, "摊薄净资产收益率"))),
                eps=self._safe_float(get_value(row, "基本每股收益")),
                # Valuation - not in financial report, will be from stocks table
                pe_ratio=None,
                pb_ratio=None,
                # Financial health
                debt_ratio=self._safe_float(get_value(row, "资产负债率(%)")),
                current_ratio=self._safe_float(get_value(row, "流动比率(非金融类指标)")),
                # Growth
                revenue_growth=self._safe_float(get_value(row, "营业收入增长率(%)")),
                profit_growth=self._safe_float(get_value(row, "净利润增长率(%)")),
                # Report period
                report_period=str(get_value(row, "report_date") or ""),
            )
            records.append(record)

        return records

    @staticmethod
    def _safe_float(value: Any) -> float | None:
        """Safely convert value to float, returning None on failure."""
        if value is None:
            return None
        try:
            f = float(value)
            # Filter out invalid values
            if f == 0.0 or abs(f) > 1e6:
                return None
            return f
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _annualize_roe(roe: float | None) -> float | None:
        """Annualize quarterly ROE by multiplying by 4.

        mootdx returns single-quarter ROE. We annualize it for consistency
        with publicly reported annual ROE figures.
        Caps at ±200% to avoid extreme values from loss-making quarters.
        """
        if roe is None:
            return None
        annualized = roe * 4
        if annualized > 200:
            return 200.0
        if annualized < -200:
            return -200.0
        return round(annualized, 2)

    def get_available_periods(self) -> list[str]:
        """Get list of available report periods from mootdx.

        Returns:
            List of period strings in YYYYMMDD format.
        """
        Affair = self._get_affair()

        try:
            files = Affair.files()
        except Exception:
            return []

        # Extract periods from filenames like "gpcw20250331.zip"
        # files is a list of dicts with 'filename' key
        periods = []
        for f in files:
            filename = f.get("filename", "") if isinstance(f, dict) else str(f)
            if filename.startswith("gpcw") and filename.endswith(".zip"):
                period = filename[4:12]  # Extract YYYYMMDD
                if period.isdigit():
                    periods.append(period)

        return sorted(periods, reverse=True)
