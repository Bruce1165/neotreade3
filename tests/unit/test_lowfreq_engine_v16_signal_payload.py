from __future__ import annotations

from datetime import date

from neotrade3.decision_engine.signal_payload import build_signal_structure_payload


def test_build_signal_structure_payload_sorts_by_buy_score_then_resonance() -> None:
    out = build_signal_structure_payload(
        deduped_signals={
            "AAA": {"code": "AAA", "buy_score": 90.0, "resonance": 0.70, "entry_ready": False},
            "BBB": {"code": "BBB", "buy_score": 95.0, "resonance": 0.60, "entry_ready": True},
            "CCC": {"code": "CCC", "buy_score": 95.0, "resonance": 0.80, "entry_ready": False},
        },
        target_date=date(2026, 7, 10),
        market_filter_note=None,
    )

    assert [row["code"] for row in out["candidate_signals"]] == ["CCC", "BBB", "AAA"]
    assert out["tracking_pool_candidate_order"] == ["CCC", "BBB", "AAA"]
    assert list(out["tracking_pool_candidates"].keys()) == ["CCC", "BBB", "AAA"]


def test_build_signal_structure_payload_keeps_only_entry_ready_rows() -> None:
    out = build_signal_structure_payload(
        deduped_signals={
            "AAA": {"code": "AAA", "buy_score": 90.0, "resonance": 0.70, "entry_ready": False},
            "BBB": {"code": "BBB", "buy_score": 95.0, "resonance": 0.60, "entry_ready": True},
        },
        target_date=date(2026, 7, 10),
        market_filter_note=None,
    )

    assert [row["code"] for row in out["entry_signals"]] == ["BBB"]
    assert [row["code"] for row in out["buy_signals"]] == ["BBB"]


def test_build_signal_structure_payload_clones_entry_rows() -> None:
    out = build_signal_structure_payload(
        deduped_signals={
            "AAA": {"code": "AAA", "buy_score": 95.0, "resonance": 0.70, "entry_ready": True},
        },
        target_date=date(2026, 7, 10),
        market_filter_note=None,
    )

    assert out["entry_signals"][0] is not out["candidate_signals"][0]
    assert out["buy_signals"][0] is not out["candidate_signals"][0]
    assert out["buy_signals"][0] is out["entry_signals"][0]


def test_build_signal_structure_payload_emits_summary_and_passthrough_fields() -> None:
    out = build_signal_structure_payload(
        deduped_signals={
            "AAA": {
                "code": "AAA",
                "buy_score": 95.0,
                "resonance": 0.70,
                "entry_ready": True,
                "candidate_tier": "soft_retained",
            },
            "BBB": {
                "code": "BBB",
                "buy_score": 96.0,
                "resonance": 0.80,
                "entry_ready": False,
                "candidate_tier": "core",
            },
        },
        target_date=date(2026, 7, 10),
        market_filter_note="capture-first: 市场偏弱，降权保留",
    )

    assert out["signal_summary"] == {
        "candidate_count": 2,
        "entry_count": 1,
        "soft_retained_count": 1,
    }
    assert sorted(out["tracking_pool_candidates"].keys()) == ["AAA", "BBB"]
    assert isinstance(out["tracking_pool_candidate_fields"], dict)
    assert "code" in out["tracking_pool_candidate_fields"]
    assert "formal_front" in out["tracking_pool_candidate_fields"]
    assert "certainty_score" in out["tracking_pool_candidate_fields"]
    assert "pattern_evidence" in out["tracking_pool_candidate_fields"]
    assert out["date"] == "2026-07-10"
    assert out["capture_first_mode"] is True
    assert out["market_filter_note"] == "capture-first: 市场偏弱，降权保留"
