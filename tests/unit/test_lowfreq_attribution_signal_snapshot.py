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


ATTR_MODULE = _load_script_module(
    "scripts/generate_lowfreq_top200_attribution_report.py",
    "lowfreq_top200_attribution_signal_snapshot_test",
)


def test_signal_layer_snapshot_preserves_candidate_entry_split() -> None:
    snapshot = ATTR_MODULE._signal_layer_snapshot(
        {
            "candidate_signals": [
                {"code": "300308", "candidate_tier": "soft_retained", "buy_score": 91.0},
                {"code": "600460", "candidate_tier": "entry_ready", "buy_score": 95.0},
            ],
            "entry_signals": [
                {"code": "600460", "candidate_tier": "entry_ready", "buy_score": 95.0},
            ],
            "signal_summary": {"candidate_count": 2, "entry_count": 1, "soft_retained_count": 1},
        }
    )

    assert sorted(snapshot["candidate_signals"].keys()) == ["300308", "600460"]
    assert sorted(snapshot["entry_signals"].keys()) == ["600460"]
    assert snapshot["signal_summary"]["candidate_count"] == 2
    assert snapshot["signal_summary"]["entry_count"] == 1
    assert snapshot["signal_summary"]["soft_retained_count"] == 1


def test_signal_layer_snapshot_prefers_formal_front_when_available() -> None:
    snapshot = ATTR_MODULE._signal_layer_snapshot(
        {
            "candidate_signals": [
                {
                    "code": "300308",
                    "candidate_tier": "soft_retained",
                    "entry_ready": False,
                    "buy_score": 91.0,
                    "formal": {
                        "status": "ok",
                        "identify_state": {"status": "identified", "reason": "watch_scope"},
                        "tracking_state": {
                            "status": "tracking",
                            "maturity": "ready_for_entry",
                            "transition_reason": "supports_action",
                        },
                        "entry_state": {
                            "status": "ready",
                            "decision": "enter",
                            "actionable": True,
                            "blocking_reasons": [],
                        },
                        "small_cycle": {
                            "cycle_state": "S2 Advancing",
                            "state_stability_level": "stable",
                        },
                        "m1_constraints_ref": {
                            "blocked": False,
                            "blocking_reasons": [],
                            "profile_window_ready": True,
                        },
                    },
                }
            ],
            "entry_signals": [],
        }
    )

    candidate = snapshot["candidate_signals"]["300308"]
    assert candidate["entry_ready"] is True
    assert candidate["candidate_tier"] == "entry_ready"
    assert candidate["formal_front"]["entry_state"]["status"] == "ready"


def test_signal_layer_snapshot_ignores_legacy_buy_signals_without_entry_signals() -> None:
    snapshot = ATTR_MODULE._signal_layer_snapshot(
        {
            "buy_signals": [{"code": "600460", "candidate_tier": "entry_ready", "buy_score": 95.0}],
        }
    )

    assert snapshot["candidate_signals"] == {}
    assert snapshot["entry_signals"] == {}
    assert snapshot["signal_summary"]["candidate_count"] == 0
    assert snapshot["signal_summary"]["entry_count"] == 0
