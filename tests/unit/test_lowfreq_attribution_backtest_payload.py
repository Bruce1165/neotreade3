from __future__ import annotations

from neotrade3.analysis.attribution_backtest_payload import build_attribution_backtest_payload


def test_build_attribution_backtest_payload_projects_current_payload() -> None:
    trade_blocks = {"buy_limit_up": 2}
    config_snapshot = {"execution_mode": "bounded"}
    coverage_gaps = {"missing_bars": 1}
    summary = {
        "total_return_pct": 32.5,
        "trade_blocks": trade_blocks,
        "config_snapshot": config_snapshot,
        "coverage_gaps": coverage_gaps,
    }
    trades = [{"code": "300750"}]

    out = build_attribution_backtest_payload(
        requested_by="script",
        generated_at="2026-07-12T16:30:00Z",
        summary=summary,
        trades=trades,
    )

    assert out == {
        "_meta": {
            "status": "ok",
            "requested_by": "script",
            "model": "lowfreq_engine_v16_advanced",
            "generated_at": "2026-07-12T16:30:00Z",
        },
        "summary": summary,
        "trade_blocks": trade_blocks,
        "config_snapshot": config_snapshot,
        "coverage_gaps": coverage_gaps,
        "trades": trades,
    }


def test_build_attribution_backtest_payload_preserves_summary_children_by_reference() -> None:
    trade_blocks = {"buy_reserved_due_to_full_book": 1}
    config_snapshot = {"execution_mode": "unbounded_opportunity"}
    coverage_gaps = {"daily_prices": []}
    summary = {
        "trade_blocks": trade_blocks,
        "config_snapshot": config_snapshot,
        "coverage_gaps": coverage_gaps,
    }
    trades = [{"code": "600000"}]

    out = build_attribution_backtest_payload(
        requested_by="script",
        generated_at="2026-07-12T16:30:00Z",
        summary=summary,
        trades=trades,
    )

    assert out["summary"] is summary
    assert out["trade_blocks"] is trade_blocks
    assert out["config_snapshot"] is config_snapshot
    assert out["coverage_gaps"] is coverage_gaps
    assert out["trades"] is trades


def test_build_attribution_backtest_payload_keeps_invalid_input_fallbacks() -> None:
    out = build_attribution_backtest_payload(
        requested_by="",
        generated_at="",
        summary=None,
        trades=None,
    )

    assert out["_meta"]["requested_by"] == ""
    assert out["_meta"]["generated_at"] == ""
    assert out["summary"] == {}
    assert out["trade_blocks"] == {}
    assert out["config_snapshot"] == {}
    assert out["coverage_gaps"] == {}
    assert out["trades"] == []
