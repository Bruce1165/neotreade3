from __future__ import annotations

from datetime import date

import neotrade3.decision_engine.formal_front as formal_front
from neotrade3.decision_engine.formal_front import (
    build_lowfreq_formal_front_payload_from_connection,
)


class _FakeConn:
    def __init__(self, cursor_obj: object) -> None:
        self._cursor_obj = cursor_obj
        self.closed = False

    def cursor(self) -> object:
        return self._cursor_obj

    def close(self) -> None:
        self.closed = True


def test_build_lowfreq_formal_front_payload_from_connection_delegates_and_closes(monkeypatch) -> None:
    seen: dict[str, object] = {}
    cursor = object()
    conn = _FakeConn(cursor)

    def _fake_build(raw_cursor, *, target_date, candidate_signals, history_limit=20):
        seen["cursor"] = raw_cursor
        seen["target_date"] = target_date
        seen["candidate_signals"] = list(candidate_signals)
        seen["history_limit"] = history_limit
        return {"status": "ok"}

    monkeypatch.setattr(formal_front, "build_lowfreq_formal_front_payload", _fake_build)

    out = build_lowfreq_formal_front_payload_from_connection(
        lambda: conn,
        target_date=date(2026, 7, 7),
        candidate_signals=[{"code": "600460"}],
        history_limit=20,
    )

    assert out == {"status": "ok"}
    assert seen == {
        "cursor": cursor,
        "target_date": date(2026, 7, 7),
        "candidate_signals": [{"code": "600460"}],
        "history_limit": 20,
    }
    assert conn.closed is True


def test_build_lowfreq_formal_front_payload_from_connection_closes_on_build_error(monkeypatch) -> None:
    conn = _FakeConn(object())

    def _boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(formal_front, "build_lowfreq_formal_front_payload", _boom)

    try:
        build_lowfreq_formal_front_payload_from_connection(
            lambda: conn,
            target_date=date(2026, 7, 7),
            candidate_signals=[{"code": "600460"}],
        )
    except RuntimeError as exc:
        assert str(exc) == "boom"
    else:
        raise AssertionError("expected RuntimeError")

    assert conn.closed is True
