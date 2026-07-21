from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Optional


@dataclass(frozen=True)
class EquityPeak:
    peak_date: str
    peak_value: float


@dataclass(frozen=True)
class CaptureResult:
    captured_codes: list[str]
    missed_codes: list[str]

    @property
    def captured_count(self) -> int:
        return int(len(self.captured_codes))

    @property
    def missed_count(self) -> int:
        return int(len(self.missed_codes))


@dataclass(frozen=True)
class PeakHoldResult:
    threshold_pct: float
    held_codes: list[str]
    missed_codes: list[str]
    by_code_drawdown_pct: dict[str, float]

    @property
    def held_count(self) -> int:
        return int(len(self.held_codes))


def compute_equity_peak(*, daily_values_net: list[dict[str, Any]]) -> EquityPeak:
    if not daily_values_net:
        raise ValueError("daily_values_net is empty")
    best_date = None
    best_value: Optional[float] = None
    for row in daily_values_net:
        if not isinstance(row, dict):
            raise ValueError("daily_values_net row must be a dict")
        d = str(row.get("date") or "").strip()
        if not d:
            raise ValueError("daily_values_net row missing date")
        v = row.get("total_value")
        if v is None:
            raise ValueError("daily_values_net row missing total_value")
        fv = float(v)
        if best_value is None or fv > best_value:
            best_value = fv
            best_date = d
    if best_value is None or best_date is None:
        raise ValueError("failed to compute equity peak")
    return EquityPeak(peak_date=str(best_date), peak_value=float(best_value))


def _normalize_code(value: object) -> str:
    return str(value or "").strip()


def extract_trade_codes(trades: Iterable[dict[str, Any]]) -> set[str]:
    out: set[str] = set()
    for t in trades:
        if not isinstance(t, dict):
            raise ValueError("trade must be a dict")
        code = _normalize_code(t.get("code"))
        if code:
            out.add(code)
    return out


def evaluate_capture_rate(
    *,
    top_codes: list[str],
    trades: list[dict[str, Any]],
) -> CaptureResult:
    normalized_top = [_normalize_code(x) for x in top_codes if _normalize_code(x)]
    if not normalized_top:
        raise ValueError("top_codes is empty")
    top_set = set(normalized_top)
    traded_codes = extract_trade_codes(trades)
    captured = sorted([c for c in top_set if c in traded_codes])
    missed = sorted([c for c in top_set if c not in traded_codes])
    return CaptureResult(captured_codes=captured, missed_codes=missed)


def build_equity_index(*, daily_values_net: list[dict[str, Any]]) -> dict[str, float]:
    index: dict[str, float] = {}
    for row in daily_values_net:
        if not isinstance(row, dict):
            raise ValueError("daily_values_net row must be a dict")
        d = str(row.get("date") or "").strip()
        if not d:
            raise ValueError("daily_values_net row missing date")
        v = row.get("total_value")
        if v is None:
            raise ValueError("daily_values_net row missing total_value")
        index[d] = float(v)
    if not index:
        raise ValueError("equity index is empty")
    return index


def _resolve_trade_exit_date(*, trade: dict[str, Any], fallback_end_date: str) -> str:
    raw = str(trade.get("sell_date") or "").strip()
    if raw:
        return raw
    status = str(trade.get("status") or "").strip().lower()
    if status in ("open", ""):
        return str(fallback_end_date)
    raise ValueError("trade missing sell_date")


def evaluate_hold_to_peak_with_drawdown_tolerance(
    *,
    captured_codes: list[str],
    trades: list[dict[str, Any]],
    daily_values_net: list[dict[str, Any]],
    peak: EquityPeak,
    end_date: str,
    threshold_pct: float = 5.0,
) -> PeakHoldResult:
    if threshold_pct < 0:
        raise ValueError("threshold_pct must be >= 0")
    equity_index = build_equity_index(daily_values_net=daily_values_net)
    by_code_last_exit: dict[str, str] = {}
    for t in trades:
        if not isinstance(t, dict):
            raise ValueError("trade must be a dict")
        code = _normalize_code(t.get("code"))
        if not code:
            raise ValueError("trade missing code")
        if code not in set(captured_codes):
            continue
        exit_date = _resolve_trade_exit_date(trade=t, fallback_end_date=str(end_date))
        prev = by_code_last_exit.get(code)
        if prev is None or exit_date > prev:
            by_code_last_exit[code] = exit_date

    held: list[str] = []
    missed: list[str] = []
    dd_by_code: dict[str, float] = {}
    for code in sorted(set(captured_codes)):
        exit_date = by_code_last_exit.get(code)
        if not exit_date:
            missed.append(code)
            continue
        equity_at_exit = equity_index.get(exit_date)
        if equity_at_exit is None:
            raise ValueError(f"equity missing for exit_date={exit_date}")
        dd = (float(peak.peak_value) - float(equity_at_exit)) / float(peak.peak_value) * 100.0
        dd_by_code[code] = float(dd)
        if float(dd) <= float(threshold_pct):
            held.append(code)
        else:
            missed.append(code)

    return PeakHoldResult(
        threshold_pct=float(threshold_pct),
        held_codes=held,
        missed_codes=missed,
        by_code_drawdown_pct=dd_by_code,
    )

