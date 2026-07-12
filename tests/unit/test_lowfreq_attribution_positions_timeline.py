from __future__ import annotations

from neotrade3.analysis.attribution_positions_timeline import build_positions_timeline


def test_build_positions_timeline_keeps_all_trading_dates_initialized() -> None:
    timeline = build_positions_timeline([], ["2025-09-01", "2025-09-02"])

    assert timeline == {
        "2025-09-01": set(),
        "2025-09-02": set(),
    }


def test_build_positions_timeline_expands_holding_window_until_before_sell_date() -> None:
    timeline = build_positions_timeline(
        [
            {
                "code": "300308",
                "buy_date": "2025-09-02",
                "sell_date": "2025-09-04",
            }
        ],
        ["2025-09-01", "2025-09-02", "2025-09-03", "2025-09-04", "2025-09-05"],
    )

    assert timeline["2025-09-01"] == set()
    assert timeline["2025-09-02"] == {"300308"}
    assert timeline["2025-09-03"] == {"300308"}
    assert timeline["2025-09-04"] == set()
    assert timeline["2025-09-05"] == set()


def test_build_positions_timeline_ignores_invalid_and_out_of_range_trades() -> None:
    timeline = build_positions_timeline(
        [
            {"code": "", "buy_date": "2025-09-02", "sell_date": "2025-09-04"},
            {"code": "300308", "buy_date": "", "sell_date": "2025-09-04"},
            {"code": "600460", "buy_date": "2025-08-31", "sell_date": "2025-09-03"},
            {"code": "601606", "buy_date": "2025-09-02"},
        ],
        ["2025-09-01", "2025-09-02", "2025-09-03"],
    )

    assert timeline["2025-09-01"] == set()
    assert timeline["2025-09-02"] == {"601606"}
    assert timeline["2025-09-03"] == {"601606"}
