from __future__ import annotations

from typing import Any

from neotrade3.analysis.attribution_markdown_report import build_attribution_markdown_report


def _build_row(
    code: str,
    *,
    name: str = "样本",
    annual_return_pct: float = 12.3,
    segment_start_date: str = "2025-01-06",
    segment_top_date: str = "2025-05-20",
    first_candidate_date: str = "2025-02-10",
    first_buy_date: str = "2025-03-03",
    first_sell_date: str = "2025-04-01",
    primary_reason: str = "原因",
    reason_bucket: str = "bucket",
    candidate_picked: bool = False,
    entry_picked: bool = False,
    bought: bool = False,
    held_to_top: bool = False,
) -> dict[str, Any]:
    return {
        "code": code,
        "name": name,
        "annual_return_pct": annual_return_pct,
        "segment_start_date": segment_start_date,
        "segment_top_date": segment_top_date,
        "first_candidate_date": first_candidate_date,
        "first_buy_date": first_buy_date,
        "first_sell_date": first_sell_date,
        "primary_reason": primary_reason,
        "reason_bucket": reason_bucket,
        "candidate_picked": candidate_picked,
        "entry_picked": entry_picked,
        "bought": bought,
        "held_to_top": held_to_top,
    }


def _section(markdown: str, title: str) -> str:
    section = markdown.split(f"## {title}\n\n", maxsplit=1)[1]
    return section.split("\n## ", maxsplit=1)[0]


def _bullet_count(section: str) -> int:
    return sum(1 for line in section.splitlines() if line.startswith("- "))


def test_build_attribution_markdown_report_renders_current_headings_and_summary() -> None:
    rows = [
        _build_row(
            "000001",
            name="平安银行",
            candidate_picked=True,
            entry_picked=False,
            primary_reason="进入候选池但未进入正式建仓池",
            reason_bucket="candidate_not_entry",
        ),
        _build_row(
            "000002",
            name="万科A",
            candidate_picked=False,
            primary_reason="所属板块未进热点",
            reason_bucket="not_candidate",
        ),
        _build_row(
            "000003",
            name="国农科技",
            bought=True,
            held_to_top=False,
            primary_reason="过早止盈",
            reason_bucket="early_exit",
        ),
        _build_row(
            "000004",
            name="国华网安",
            bought=True,
            held_to_top=True,
            primary_reason="实际持仓延续到市场事实见顶",
            reason_bucket="held_to_top",
        ),
        _build_row(
            "000005",
            name="世纪星源",
            bought=True,
            held_to_top=True,
            primary_reason="实际持仓延续到市场事实见顶",
            reason_bucket="held_to_top",
        ),
        _build_row(
            "000006",
            name="深振业A",
            bought=True,
            held_to_top=True,
            primary_reason="实际持仓延续到市场事实见顶",
            reason_bucket="held_to_top",
        ),
    ]

    out = build_attribution_markdown_report(
        year=2025,
        limit=200,
        ranking=[{"code": "000001"}, {"code": "000002"}],
        aggregate={
            "candidate_picked_count": 1,
            "entry_picked_count": 0,
            "bought_count": 4,
            "held_to_top_count": 3,
        },
        attribution_rows=rows,
        backtest_payload={
            "summary": {
                "total_return_pct": 18.5,
                "max_drawdown_pct": -7.2,
                "total_trades": 12,
            }
        },
    )

    assert out.startswith("# Lowfreq Model 2025 Top200 Scorecard Report\n")
    assert "## 口径说明\n\n" in out
    assert "## 总体摘要\n\n" in out
    assert "## 原因分布\n\n" in out
    assert "## 典型候选未转建仓样本\n\n" in out
    assert "## 典型未进候选样本\n\n" in out
    assert "## 典型提前离场样本\n\n" in out
    assert "- Top200 count: 2" in out
    assert "- 进入候选池：1" in out
    assert "- 进入正式建仓池：0" in out
    assert "- 实际买入：4" in out
    assert "- 持有到市场事实见顶：3" in out
    assert "- 当前18个月回测摘要：总收益 18.5%，最大回撤 -7.2%，交易数 12" in out
    assert "- held_to_top: 3" in out
    assert "- candidate_not_entry: 1" in out
    assert "- not_candidate: 1" in out
    assert "- early_exit: 1" in out
    assert out.endswith("\n")


def test_build_attribution_markdown_report_omits_backtest_summary_when_missing() -> None:
    out = build_attribution_markdown_report(
        year=2025,
        limit=5,
        ranking=[],
        aggregate={},
        attribution_rows=[],
        backtest_payload={},
    )

    assert "- 当前18个月回测摘要：" not in out


def test_build_attribution_markdown_report_truncates_each_sample_section_to_top20() -> None:
    candidate_rows = [
        _build_row(
            f"C{i:03d}",
            candidate_picked=True,
            entry_picked=False,
            primary_reason=f"候选未转建仓-{i}",
        )
        for i in range(25)
    ]
    not_picked_rows = [
        _build_row(
            f"N{i:03d}",
            candidate_picked=False,
            primary_reason=f"未进候选-{i}",
        )
        for i in range(25)
    ]
    early_exit_rows = [
        _build_row(
            f"E{i:03d}",
            candidate_picked=True,
            entry_picked=True,
            bought=True,
            held_to_top=False,
            primary_reason=f"提前离场-{i}",
        )
        for i in range(25)
    ]

    out = build_attribution_markdown_report(
        year=2025,
        limit=200,
        ranking=[],
        aggregate={},
        attribution_rows=candidate_rows + not_picked_rows + early_exit_rows,
        backtest_payload={},
    )

    candidate_section = _section(out, "典型候选未转建仓样本")
    not_picked_section = _section(out, "典型未进候选样本")
    early_exit_section = _section(out, "典型提前离场样本")

    assert _bullet_count(candidate_section) == 20
    assert "C019" in candidate_section
    assert "C020" not in candidate_section

    assert _bullet_count(not_picked_section) == 20
    assert "N019" in not_picked_section
    assert "N020" not in not_picked_section

    assert _bullet_count(early_exit_section) == 20
    assert "E019" in early_exit_section
    assert "E020" not in early_exit_section
