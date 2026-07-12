from __future__ import annotations

from neotrade3.analysis.attribution_report_row import (
    build_attribution_report_row,
    build_attribution_segment_failed_row,
)


def test_build_attribution_segment_failed_row_projects_current_failure_payload() -> None:
    out = build_attribution_segment_failed_row(
        rank="9",
        code="300750",
        name="宁德时代",
        annual_return_pct="102.3",
        segment_status="missing_2025_prices",
    )

    assert out == {
        "rank": 9,
        "code": "300750",
        "name": "宁德时代",
        "annual_return_pct": 102.3,
        "segment_status": "missing_2025_prices",
        "candidate_picked": False,
        "entry_picked": False,
        "picked": False,
        "bought": False,
        "held_to_top": False,
        "primary_reason": "主升段识别失败",
    }


def test_build_attribution_segment_failed_row_keeps_unknown_status_fallback() -> None:
    out = build_attribution_segment_failed_row(
        rank=1,
        code="000001",
        name="平安银行",
        annual_return_pct=12.5,
        segment_status="",
    )

    assert out["segment_status"] == "unknown"


def test_build_attribution_report_row_projects_full_payload_with_current_coercions() -> None:
    daily_audits = [{"stage": "candidate_signal_selected", "reason": "进入候选池"}]
    relevant_trades = [{"buy_date": "2025-03-03", "sell_date": "2025-04-01"}]

    out = build_attribution_report_row(
        rank="7",
        code="000001",
        name="平安银行",
        sector="银行",
        annual_return_pct="88.5",
        segment_start_date="2025-01-06",
        segment_top_date="2025-05-20",
        segment_return_pct="41.2",
        candidate_picked=1,
        entry_picked=0,
        picked=True,
        first_candidate_date="2025-02-10",
        candidate_signal_count_in_segment="3",
        first_entry_date="",
        first_signal_date="2025-02-10",
        entry_signal_count_in_segment="0",
        signal_count_in_segment="3",
        bought=0,
        first_buy_date="",
        first_sell_date="",
        held_to_top=0,
        primary_reason="进入候选池但未进入正式建仓池",
        reason_bucket="candidate_not_entry",
        daily_audits=daily_audits,
        relevant_trades=relevant_trades,
    )

    assert out == {
        "rank": 7,
        "code": "000001",
        "name": "平安银行",
        "sector": "银行",
        "annual_return_pct": 88.5,
        "segment_start_date": "2025-01-06",
        "segment_top_date": "2025-05-20",
        "segment_return_pct": 41.2,
        "candidate_picked": True,
        "entry_picked": False,
        "picked": True,
        "first_candidate_date": "2025-02-10",
        "candidate_signal_count_in_segment": 3,
        "first_entry_date": "",
        "first_signal_date": "2025-02-10",
        "entry_signal_count_in_segment": 0,
        "signal_count_in_segment": 3,
        "bought": False,
        "first_buy_date": "",
        "first_sell_date": "",
        "held_to_top": False,
        "primary_reason": "进入候选池但未进入正式建仓池",
        "reason_bucket": "candidate_not_entry",
        "daily_audits": daily_audits,
        "relevant_trades": relevant_trades,
    }


def test_build_attribution_report_row_keeps_picked_independent_from_entry_picked() -> None:
    out = build_attribution_report_row(
        rank=1,
        code="000001",
        name="平安银行",
        sector="银行",
        annual_return_pct=1.0,
        segment_start_date="2025-01-01",
        segment_top_date="2025-02-01",
        segment_return_pct=2.0,
        candidate_picked=True,
        entry_picked=False,
        picked=True,
        first_candidate_date="",
        candidate_signal_count_in_segment=1,
        first_entry_date="",
        first_signal_date="",
        entry_signal_count_in_segment=0,
        signal_count_in_segment=1,
        bought=False,
        first_buy_date="",
        first_sell_date="",
        held_to_top=False,
        primary_reason="x",
        reason_bucket="y",
        daily_audits=[],
        relevant_trades=[],
    )

    assert out["entry_picked"] is False
    assert out["picked"] is True


def test_build_attribution_report_row_passes_through_daily_audits_and_relevant_trades() -> None:
    daily_audits = [{"stage": "entry_signal_selected"}]
    relevant_trades = [{"buy_date": "2025-03-03"}]

    out = build_attribution_report_row(
        rank=1,
        code="000001",
        name="平安银行",
        sector="银行",
        annual_return_pct=1.0,
        segment_start_date="2025-01-01",
        segment_top_date="2025-02-01",
        segment_return_pct=2.0,
        candidate_picked=True,
        entry_picked=True,
        picked=True,
        first_candidate_date="",
        candidate_signal_count_in_segment=1,
        first_entry_date="",
        first_signal_date="",
        entry_signal_count_in_segment=1,
        signal_count_in_segment=1,
        bought=True,
        first_buy_date="2025-01-10",
        first_sell_date="",
        held_to_top=True,
        primary_reason="实际持仓延续到市场事实见顶",
        reason_bucket="held_to_top",
        daily_audits=daily_audits,
        relevant_trades=relevant_trades,
    )

    assert out["daily_audits"] is daily_audits
    assert out["relevant_trades"] is relevant_trades
