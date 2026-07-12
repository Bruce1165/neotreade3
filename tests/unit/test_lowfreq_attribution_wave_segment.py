from __future__ import annotations

from datetime import date

from neotrade3.analysis.attribution_wave_segment import (
    build_insufficient_history_wave_segment,
    build_missing_wave_segment,
    build_ok_wave_segment,
)


def test_build_missing_wave_segment_projects_current_failure_payload() -> None:
    out = build_missing_wave_segment(code="300750")

    assert out == {
        "status": "missing_2025_prices",
        "code": "300750",
    }


def test_build_insufficient_history_wave_segment_projects_current_payload() -> None:
    out = build_insufficient_history_wave_segment(
        code="300750",
        top_date=date(2025, 6, 18),
        top_close=188.123456,
    )

    assert out == {
        "status": "insufficient_history",
        "code": "300750",
        "top_date": "2025-06-18",
        "top_close": 188.1235,
    }


def test_build_ok_wave_segment_projects_current_success_payload() -> None:
    out = build_ok_wave_segment(
        code="300750",
        lookback_trading_days="180",
        start_date="2025-01-06",
        start_close=102.34567,
        top_date=date(2025, 6, 18),
        top_close=188.123456,
        segment_return_pct=83.775,
    )

    assert out == {
        "status": "ok",
        "code": "300750",
        "segment_window_trading_days": 180,
        "start_date": "2025-01-06",
        "start_close": 102.3457,
        "top_date": "2025-06-18",
        "top_close": 188.1235,
        "segment_return_pct": 83.78,
        "segment_basis": "见顶日前180交易日窗口内最低收盘价 -> 2025年最高收盘价",
    }
