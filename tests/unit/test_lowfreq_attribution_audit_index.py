from __future__ import annotations

from neotrade3.analysis.attribution_audit_index import build_buy_signal_audit_index


def test_build_buy_signal_audit_index_filters_invalid_entries() -> None:
    out = build_buy_signal_audit_index(
        [
            {"code": "300308", "date": "2025-09-02", "event": "z_event"},
            "not-a-dict",
            {"code": "", "date": "2025-09-01", "event": "a_event"},
            {"date": "2025-09-01", "event": "a_event"},
        ]
    )

    assert list(out.keys()) == ["300308"]
    assert out["300308"] == [{"code": "300308", "date": "2025-09-02", "event": "z_event"}]


def test_build_buy_signal_audit_index_sorts_each_bucket_by_date_then_event() -> None:
    out = build_buy_signal_audit_index(
        [
            {"code": "300308", "date": "2025-09-02", "event": "z_event"},
            {"code": "300308", "date": "2025-09-01", "event": "z_event"},
            {"code": "300308", "date": "2025-09-01", "event": "a_event"},
        ]
    )

    assert [item["event"] for item in out["300308"]] == ["a_event", "z_event", "z_event"]
    assert [item["date"] for item in out["300308"]] == ["2025-09-01", "2025-09-01", "2025-09-02"]


def test_build_buy_signal_audit_index_keeps_code_buckets_separate() -> None:
    out = build_buy_signal_audit_index(
        [
            {"code": "300308", "date": "2025-09-02", "event": "b_event"},
            {"code": "600460", "date": "2025-09-01", "event": "a_event"},
        ]
    )

    assert sorted(out.keys()) == ["300308", "600460"]
    assert out["300308"][0]["event"] == "b_event"
    assert out["600460"][0]["event"] == "a_event"
