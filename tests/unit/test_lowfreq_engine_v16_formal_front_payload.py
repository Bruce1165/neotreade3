from __future__ import annotations

from neotrade3.decision_engine.formal_front import finalize_lowfreq_formal_front_payload


def test_finalize_lowfreq_formal_front_payload_attaches_formal_items_by_code() -> None:
    signal_payload = {
        "candidate_signals": [
            {"code": "AAA", "entry_ready": True},
            {"code": "BBB", "entry_ready": False},
        ],
        "tracking_pool_candidates": {
            "AAA": {"code": "AAA", "entry_ready": True},
            "BBB": {"code": "BBB", "entry_ready": False},
        },
        "tracking_pool_candidate_order": ["AAA", "BBB"],
    }
    formal_payload = {
        "status": "partial",
        "items_by_code": {
            "AAA": {"status": "ok", "entry_state": {"status": "ready"}},
        },
        "summary": {"total": 2, "ok": 1, "error": 1},
    }

    out = finalize_lowfreq_formal_front_payload(
        signal_payload,
        formal_payload=formal_payload,
    )

    assert out["candidate_signals"][0]["formal"] == {"status": "ok", "entry_state": {"status": "ready"}}
    assert out["candidate_signals"][1]["formal"] == {"status": "unavailable"}
    assert out["tracking_pool_candidates"]["AAA"]["formal"] == {"status": "ok", "entry_state": {"status": "ready"}}
    assert out["tracking_pool_candidates"]["BBB"]["formal"] == {"status": "unavailable"}
    assert out["formal"] is formal_payload


def test_finalize_lowfreq_formal_front_payload_rebuilds_entry_and_buy_signals() -> None:
    signal_payload = {
        "candidate_signals": [
            {"code": "AAA", "entry_ready": True, "buy_score": 95.0},
            {"code": "BBB", "entry_ready": False, "buy_score": 90.0},
        ],
        "entry_signals": [{"code": "stale"}],
        "buy_signals": [{"code": "stale"}],
    }

    out = finalize_lowfreq_formal_front_payload(
        signal_payload,
        formal_payload={"status": "ok", "items_by_code": {}},
    )

    assert [row["code"] for row in out["entry_signals"]] == ["AAA"]
    assert [row["code"] for row in out["buy_signals"]] == ["AAA"]


def test_finalize_lowfreq_formal_front_payload_clones_entry_rows() -> None:
    signal_payload = {
        "candidate_signals": [
            {"code": "AAA", "entry_ready": True, "buy_score": 95.0},
        ]
    }

    out = finalize_lowfreq_formal_front_payload(
        signal_payload,
        formal_payload={"status": "ok", "items_by_code": {"AAA": {"status": "ok"}}},
    )

    assert out["entry_signals"][0] is not out["candidate_signals"][0]
    assert out["buy_signals"][0] is out["entry_signals"][0]
