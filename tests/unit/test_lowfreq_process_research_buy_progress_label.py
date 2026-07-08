from __future__ import annotations

import importlib.util
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _load_script_module(relative_path: str, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, PROJECT_ROOT / relative_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PROCESS_MODULE = _load_script_module(
    "scripts/generate_lowfreq_top200_process_research_report.py",
    "lowfreq_process_research_buy_progress_label_test",
)


def _make_row(*, trade_label: str = "") -> dict[str, object]:
    return {
        "name": "Sample",
        "sector": "AI",
        "rank": 1,
        "annual_return_pct": 12.3,
        "segment_start_date": "2026-01-01",
        "segment_top_date": "2026-01-10",
        "segment_return_pct": 20.0,
        "first_signal_date": "2026-01-02",
        "first_buy_date": "2026-01-03",
        "first_sell_date": "",
        "picked": True,
        "bought": True,
        "held_to_top": False,
        "reason_bucket": "momentum",
        "primary_reason": "breakout",
        "relevant_trades": [
            {
                "buy_price_ref": 12.0,
                "buy_progress_label": trade_label,
            }
        ],
    }


def test_full_light_row_prefers_stored_buy_progress_label() -> None:
    row = _make_row(trade_label="晚窗")

    payload = PROCESS_MODULE._full_light_row(
        code="000001",
        base_row=row,
        variant_row=row,
        process_metrics={
            "segment_start_close": 10.0,
            "segment_top_close": 20.0,
        },
        series_map={
            "2026-01-02": 11.0,
            "2026-01-03": 12.0,
        },
    )

    assert payload["base"]["buy_progress_pct"] == 20.0
    assert payload["base"]["buy_progress_label"] == "晚窗"


def test_full_light_row_falls_back_to_computed_buy_progress_label() -> None:
    row = _make_row(trade_label="")

    payload = PROCESS_MODULE._full_light_row(
        code="000001",
        base_row=row,
        variant_row=row,
        process_metrics={
            "segment_start_close": 10.0,
            "segment_top_close": 20.0,
        },
        series_map={
            "2026-01-02": 11.0,
            "2026-01-03": 12.0,
        },
    )

    assert payload["base"]["buy_progress_pct"] == 20.0
    assert payload["base"]["buy_progress_label"] == "早窗"
