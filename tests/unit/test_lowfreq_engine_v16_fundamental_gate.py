from __future__ import annotations

from neotrade3.cycle_intelligence.fundamental_gate import score_fundamentals


def test_score_fundamentals_skips_when_table_is_unavailable() -> None:
    passed, score, reasons = score_fundamentals(
        {"table_exists": False},
        max_pe=80.0,
        min_profit_growth=15.0,
        min_roe=8.0,
    )

    assert passed is True
    assert score == 50
    assert reasons == ["基本面数据不可用，跳过筛选"]


def test_score_fundamentals_scores_healthy_case() -> None:
    passed, score, reasons = score_fundamentals(
        {
            "table_exists": True,
            "pe_ttm": 18.0,
            "profit_growth": 28.0,
            "revenue_growth": 16.0,
            "roe": 14.0,
        },
        max_pe=80.0,
        min_profit_growth=15.0,
        min_roe=8.0,
    )

    assert passed is True
    assert score == 100
    assert reasons == [
        "PE18.0合理",
        "净利增28.0%",
        "营收增16.0%",
        "ROE14.0%",
    ]


def test_score_fundamentals_allows_loss_when_growth_is_strong() -> None:
    passed, score, reasons = score_fundamentals(
        {
            "table_exists": True,
            "pe_ttm": 0.0,
            "profit_growth": 35.0,
            "revenue_growth": 12.0,
            "roe": 10.0,
        },
        max_pe=80.0,
        min_profit_growth=15.0,
        min_roe=8.0,
    )

    assert passed is True
    assert score == 90
    assert reasons == [
        "亏损但高增长",
        "净利增35.0%",
        "营收增12.0%",
        "ROE10.0%",
    ]


def test_score_fundamentals_fails_invalid_pe_without_growth_exception() -> None:
    passed, score, reasons = score_fundamentals(
        {
            "table_exists": True,
            "pe_ttm": 0.0,
            "profit_growth": -5.0,
            "revenue_growth": -2.0,
            "roe": 4.0,
        },
        max_pe=80.0,
        min_profit_growth=15.0,
        min_roe=8.0,
    )

    assert passed is False
    assert score == 20
    assert reasons == [
        "PE无效且无高增长",
        "净利下滑-5.0%",
    ]


def test_score_fundamentals_preserves_soft_score_composition() -> None:
    passed, score, reasons = score_fundamentals(
        {
            "table_exists": True,
            "pe_ttm": 120.0,
            "profit_growth": 8.0,
            "revenue_growth": 5.0,
            "roe": 6.0,
        },
        max_pe=80.0,
        min_profit_growth=15.0,
        min_roe=8.0,
    )

    assert passed is True
    assert score == 45
    assert reasons == [
        "PE120.0偏高",
        "净利增8.0%（偏低）",
    ]
