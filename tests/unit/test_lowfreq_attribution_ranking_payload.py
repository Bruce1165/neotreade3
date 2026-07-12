from __future__ import annotations

from neotrade3.analysis.attribution_ranking_payload import build_attribution_ranking_row


def test_build_attribution_ranking_row_projects_current_payload() -> None:
    out = build_attribution_ranking_row(
        rank="7",
        code="300308",
        name="中际旭创",
        sector="光模块",
        first_trade_date="2025-01-02",
        last_trade_date="2025-12-31",
        first_close="88.123456",
        last_close="231.987654",
        annual_return_pct="163.286",
    )

    assert out == {
        "rank": 7,
        "code": "300308",
        "name": "中际旭创",
        "sector": "光模块",
        "first_trade_date": "2025-01-02",
        "last_trade_date": "2025-12-31",
        "first_close": 88.1235,
        "last_close": 231.9877,
        "annual_return_pct": 163.29,
        "price_basis": "未复权收盘价",
    }


def test_build_attribution_ranking_row_keeps_empty_string_fallbacks() -> None:
    out = build_attribution_ranking_row(
        rank=1,
        code="000001",
        name="",
        sector="",
        first_trade_date="2025-01-02",
        last_trade_date="2025-12-31",
        first_close=10.0,
        last_close=12.0,
        annual_return_pct=20.0,
    )

    assert out["name"] == ""
    assert out["sector"] == ""


def test_build_attribution_ranking_row_rounds_prices_and_return_with_current_precision() -> None:
    out = build_attribution_ranking_row(
        rank=1,
        code="000001",
        name="平安银行",
        sector="银行",
        first_trade_date="2025-01-02",
        last_trade_date="2025-12-31",
        first_close=10.12344,
        last_close=12.98765,
        annual_return_pct=28.456,
    )

    assert out["first_close"] == 10.1234
    assert out["last_close"] == 12.9877
    assert out["annual_return_pct"] == 28.46
