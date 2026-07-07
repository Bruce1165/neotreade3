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


RESEARCH_MODULE = _load_script_module(
    "scripts/generate_lowfreq_research_report_assets.py",
    "lowfreq_research_entry_signal_rows_test",
)


def test_entry_signal_rows_prefers_entry_signals_over_legacy_buy_signals() -> None:
    rows = RESEARCH_MODULE._entry_signal_rows(
        {
            "buy_signals": [{"code": "600460"}],
            "entry_signals": [{"code": "300308"}],
        }
    )

    assert rows == [{"code": "300308"}]


def test_entry_signal_rows_ignores_legacy_buy_signals_without_entry_signals() -> None:
    rows = RESEARCH_MODULE._entry_signal_rows(
        {
            "buy_signals": [{"code": "600460"}],
        }
    )

    assert rows == []
