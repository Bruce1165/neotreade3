import pytest

from neotrade3.analysis.m6_backtest_eval import (
    compute_equity_peak,
    evaluate_capture_rate,
    evaluate_hold_to_peak_with_drawdown_tolerance,
)


def test_compute_equity_peak_picks_max_value() -> None:
    peak = compute_equity_peak(
        daily_values_net=[
            {"date": "2026-01-01", "total_value": 100.0},
            {"date": "2026-01-02", "total_value": 150.0},
            {"date": "2026-01-03", "total_value": 120.0},
        ]
    )
    assert peak.peak_date == "2026-01-02"
    assert peak.peak_value == 150.0


def test_evaluate_capture_rate_reports_missed_and_captured() -> None:
    result = evaluate_capture_rate(
        top_codes=["600001", "600002", "688001"],
        trades=[{"code": "600001"}, {"code": "688001"}],
    )
    assert sorted(result.captured_codes) == ["600001", "688001"]
    assert result.missed_codes == ["600002"]


def test_evaluate_hold_to_peak_with_drawdown_tolerance() -> None:
    daily_values_net = [
        {"date": "2026-01-01", "total_value": 100.0},
        {"date": "2026-01-02", "total_value": 200.0},
        {"date": "2026-01-03", "total_value": 180.0},
    ]
    peak = compute_equity_peak(daily_values_net=daily_values_net)
    out = evaluate_hold_to_peak_with_drawdown_tolerance(
        captured_codes=["600001"],
        trades=[{"code": "600001", "sell_date": "2026-01-03", "status": "closed"}],
        daily_values_net=daily_values_net,
        peak=peak,
        end_date="2026-01-03",
        threshold_pct=15.0,
    )
    assert out.held_codes == ["600001"]
    assert out.missed_codes == []


def test_evaluate_hold_to_peak_fail_closed_when_equity_missing() -> None:
    daily_values_net = [
        {"date": "2026-01-01", "total_value": 100.0},
        {"date": "2026-01-02", "total_value": 200.0},
    ]
    peak = compute_equity_peak(daily_values_net=daily_values_net)
    with pytest.raises(ValueError):
        _ = evaluate_hold_to_peak_with_drawdown_tolerance(
            captured_codes=["600001"],
            trades=[{"code": "600001", "sell_date": "2026-01-03", "status": "closed"}],
            daily_values_net=daily_values_net,
            peak=peak,
            end_date="2026-01-03",
            threshold_pct=5.0,
        )

