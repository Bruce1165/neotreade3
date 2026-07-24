from __future__ import annotations

from typing import Any


def score_fundamentals(
    fundamentals: dict[str, Any],
    *,
    max_pe: float,
    min_profit_growth: float,
    min_roe: float,
) -> tuple[bool, float, list[str]]:
    """Score the fundamentals gate while keeping the existing engine contract."""
    if not fundamentals.get("table_exists", False):
        return True, 50, ["基本面数据不可用，跳过筛选"]

    score = 0
    reasons: list[str] = []
    passed = True

    pe = fundamentals.get("pe_ttm", 0) or 0
    profit_growth = fundamentals.get("profit_growth", 0)
    revenue_growth = fundamentals.get("revenue_growth", 0)
    roe = fundamentals.get("roe", 0) or 0

    if 0 < pe < max_pe:
        score += 20
        reasons.append(f"PE{pe:.1f}合理")
    elif pe <= 0:
        if profit_growth is not None and profit_growth > 30:
            score += 10
            reasons.append("亏损但高增长")
        else:
            passed = False
            reasons.append("PE无效且无高增长")
    else:
        score += 5
        reasons.append(f"PE{pe:.1f}偏高")

    if profit_growth is None:
        reasons.append("净利增长数据缺失，未计分")
    elif profit_growth >= min_profit_growth:
        score += 30
        reasons.append(f"净利增{profit_growth:.1f}%")
    elif profit_growth > 0:
        score += 15
        reasons.append(f"净利增{profit_growth:.1f}%（偏低）")
    elif profit_growth == 0:
        score += 5
        reasons.append("净利同比持平")
    else:
        score += 5
        reasons.append(f"净利下滑{abs(profit_growth):.1f}%")

    if revenue_growth is not None:
        if revenue_growth >= 10:
            score += 20
            reasons.append(f"营收增{revenue_growth:.1f}%")
        elif revenue_growth > 0:
            score += 10

    if roe >= min_roe:
        score += 30
        reasons.append(f"ROE{roe:.1f}%")
    elif roe > 0:
        score += 15

    return passed, score, reasons
