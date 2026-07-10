from __future__ import annotations

from neotrade3.cycle_intelligence.weekly_returns import weekly_returns_from_series


def test_weekly_returns_from_series_returns_insufficient_for_short_series() -> None:
    out = weekly_returns_from_series(
        {
            "series": [{"close": float(idx + 1)} for idx in range(15)],
        }
    )

    assert out == {"status": "insufficient", "weeks": 15}


def test_weekly_returns_from_series_computes_expected_windows() -> None:
    closes = [float(idx + 1) for idx in range(16)]

    out = weekly_returns_from_series(
        {
            "series": [{"close": close} for close in closes],
        }
    )

    assert out["status"] == "ok"
    assert out["ret_1w"] == 100.0 * (16.0 / 15.0 - 1.0)
    assert out["ret_4w"] == 100.0 * (16.0 / 12.0 - 1.0)
    assert out["ret_12w"] == 100.0 * (16.0 / 4.0 - 1.0)


def test_weekly_returns_from_series_ignores_non_dict_and_null_close_entries() -> None:
    out = weekly_returns_from_series(
        {
            "series": [
                None,
                {"close": 1.0},
                {"close": None},
                "bad-row",
                {"close": 2.0},
                {"close": 3.0},
                {"close": 4.0},
                {"close": 5.0},
                {"close": 6.0},
                {"close": 7.0},
                {"close": 8.0},
                {"close": 9.0},
                {"close": 10.0},
                {"close": 11.0},
                {"close": 12.0},
                {"close": 13.0},
                {"close": 14.0},
                {"close": 15.0},
                {"close": 16.0},
            ]
        }
    )

    assert out["status"] == "ok"
    assert out["ret_1w"] == 100.0 * (16.0 / 15.0 - 1.0)
    assert out["ret_4w"] == 100.0 * (16.0 / 12.0 - 1.0)
    assert out["ret_12w"] == 100.0 * (16.0 / 4.0 - 1.0)


def test_weekly_returns_from_series_returns_zero_for_non_positive_base_close() -> None:
    closes = [1.0, 2.0, 3.0, 0.0, 5.0, 6.0, -1.0, 8.0, 9.0, 10.0, 11.0, 0.0, 13.0, 14.0, 15.0, 16.0]

    out = weekly_returns_from_series(
        {
            "series": [{"close": close} for close in closes],
        }
    )

    assert out == {
        "status": "ok",
        "ret_1w": 100.0 * (16.0 / 15.0 - 1.0),
        "ret_4w": 0.0,
        "ret_12w": 0.0,
    }
