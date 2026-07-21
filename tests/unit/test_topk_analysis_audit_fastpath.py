from __future__ import annotations

import sqlite3
from datetime import date

from scripts.generate_lowfreq_top200_attribution_report import _audit_daily_reason, _extract_execution_reason, AuditContext


class _StubEngine:
    MARKET_FILTER_ENABLED = False
    MIN_MARKET_SCORE = 0

    BUY_THRESHOLD = 85.0
    CUP_HANDLE_NONCONFIRM_THRESHOLD_BONUS = 0.0
    MIN_RESONANCE = 0.7
    CROSS_SECTOR_WAVE3_ONLY = True
    CROSS_SECTOR_ALLOW_WAVE1 = True
    CROSS_SECTOR_SCORE_MARGIN = 0.0

    MARKET_CAP_MIN = 0
    MARKET_CAP_MAX = 10**18
    HOT_SECTOR_COUNT = 12

    def get_market_sentiment(self, target_date: date):
        return ("ok", 100.0)

    def generate_buy_signals(self, target_date: date):
        raise RuntimeError("generate_buy_signals should not be called in analysis fastpath")


def test_audit_daily_reason_uses_buy_signal_audit_fastpath_without_generate_buy_signals() -> None:
    engine = _StubEngine()
    conn = sqlite3.connect(":memory:")
    try:
        audit_entries = [
            {
                "code": "000001",
                "date": "2026-06-10",
                "event": "tracking_started",
                "funnel_stage": "candidate_detected",
                "execution_status": "tracking",
                "buy_score": 91.0,
                "role": "龙头",
                "wave_phase": "3浪",
                "tracking_ready": False,
                "tracking_evidence_bundle": ["e1", "e2"],
            }
        ]
        ctx = AuditContext(engine=engine, conn=conn, buy_signal_audit_entries=audit_entries)
        out = _audit_daily_reason(
            engine=engine,
            ctx=ctx,
            code="000001",
            name="x",
            sector="E49",
            target_date=date.fromisoformat("2026-06-10"),
        )
        assert out["stage"] == "candidate_signal_selected"
        sig = out.get("signal") if isinstance(out.get("signal"), dict) else {}
        assert sig.get("buy_score") == 91.0
        assert sig.get("role") == "龙头"
        assert sig.get("wave_phase") == "3浪"
    finally:
        conn.close()


def test_extract_execution_reason_infers_chase_blocked_from_buy_signal_audit() -> None:
    engine = _StubEngine()
    conn = sqlite3.connect(":memory:")
    try:
        conn.execute(
            """
            CREATE TABLE daily_prices(
                code TEXT,
                trade_date TEXT,
                pct_change REAL,
                high REAL,
                low REAL,
                close REAL
            )
            """
        )
        conn.executemany(
            "INSERT INTO daily_prices(code, trade_date, pct_change, high, low, close) VALUES (?,?,?,?,?,?)",
            [
                ("000001", "2026-06-10", 0.0, 10.0, 9.0, 9.5),
                ("000001", "2026-06-11", 0.0, 10.0, 9.0, 9.5),
                ("000001", "2026-06-12", 0.0, 10.0, 9.0, 9.5),
            ],
        )
        ctx = AuditContext(engine=engine, conn=conn, buy_signal_audit_entries=[])
        reason = _extract_execution_reason(
            code="000001",
            signal_dates=["2026-06-10"],
            positions_timeline={},
            conn=conn,
            engine=engine,
            ctx=ctx,
            max_positions=3,
            segment_top_date="2026-12-31",
            buy_signal_audits=[{"code": "000001", "date": "2026-06-10", "event": "chase_entry_blocked"}],
            code_trades=[],
            execution_mode="bounded",
            execution_one_price_limit_only=False,
            limit_up_pct=9.8,
        )
        assert "追高型买点" in reason
    finally:
        conn.close()
