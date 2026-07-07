from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _load_script_module(relative_path: str, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, PROJECT_ROOT / relative_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PROCESS_MODULE = _load_script_module(
    "scripts/generate_lowfreq_top200_process_research_report.py",
    "lowfreq_process_research_inputs_test",
)


def test_process_research_requires_explicit_input_paths() -> None:
    with pytest.raises(ValueError, match="explicit input artifacts are required"):
        PROCESS_MODULE._resolve_process_research_inputs(
            base_backtest_json=None,
            variant_backtest_json=None,
            base_attribution_json=None,
            variant_attribution_json=None,
        )


def test_process_research_validates_input_paths(tmp_path: Path) -> None:
    base_backtest = tmp_path / "base_payload.json"
    variant_backtest = tmp_path / "variant_payload.json"
    base_attr = tmp_path / "base_attr.json"
    variant_attr = tmp_path / "variant_attr.json"
    for path in (base_backtest, variant_backtest, base_attr, variant_attr):
        path.write_text("{}", encoding="utf-8")

    resolved = PROCESS_MODULE._resolve_process_research_inputs(
        base_backtest_json=base_backtest,
        variant_backtest_json=variant_backtest,
        base_attribution_json=base_attr,
        variant_attribution_json=variant_attr,
    )

    assert resolved == {
        "base_backtest_json": base_backtest,
        "variant_backtest_json": variant_backtest,
        "base_attribution_json": base_attr,
        "variant_attribution_json": variant_attr,
    }
