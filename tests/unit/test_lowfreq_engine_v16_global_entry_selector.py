from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from types import SimpleNamespace

from neotrade3.cycle_intelligence import global_entry_selector


def _make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE stocks (
            code TEXT PRIMARY KEY,
            name TEXT,
            sector_lv1 TEXT,
            total_market_cap REAL,
            is_delisted INTEGER
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE daily_prices (
            code TEXT,
            trade_date TEXT,
            close REAL,
            pct_change REAL,
            amount REAL,
            volume REAL,
            high REAL,
            low REAL
        )
        """
    )
    return conn


def _seed_stock(
    conn: sqlite3.Connection,
    *,
    code: str,
    sector: str,
    target_date: date,
    days: int,
    base_close: float,
    step: float,
    pct_change: float,
    market_cap: float = 25_000_000_000.0,
) -> None:
    conn.execute(
        """
        INSERT INTO stocks(code, name, sector_lv1, total_market_cap, is_delisted)
        VALUES (?, ?, ?, ?, 0)
        """,
        (code, f"{code}-name", sector, market_cap),
    )
    for offset in range(days):
        trade_date = target_date - timedelta(days=offset)
        close = base_close + step * float(days - offset)
        volume = 1_000_000.0 + (days - offset) * 10_000.0
        amount = close * volume
        conn.execute(
            """
            INSERT INTO daily_prices(code, trade_date, close, pct_change, amount, volume, high, low)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                code,
                trade_date.isoformat(),
                close,
                pct_change if offset == 0 else 0.5,
                amount,
                volume,
                close * 1.02,
                close * 0.98,
            ),
        )
    conn.commit()


def _history_batch_loader(cursor, codes, target_date, limit=60):
    out = {}
    for code in codes:
        cursor.execute(
            """
            SELECT trade_date, close, volume, amount, high, low
            FROM daily_prices
            WHERE code = ? AND trade_date <= ?
            ORDER BY trade_date DESC
            LIMIT ?
            """,
            (code, target_date.isoformat(), int(limit)),
        )
        out[code] = [
            {
                "trade_date": trade_date,
                "close": float(close) if close is not None else None,
                "volume": float(volume) if volume is not None else None,
                "amount": float(amount) if amount is not None else None,
                "high": float(high) if high is not None else None,
                "low": float(low) if low is not None else None,
            }
            for trade_date, close, volume, amount, high, low in cursor.fetchall()
        ]
    return out


def _identity_release(*, score, role, wave_phase, soft_flags, reasons, release_enabled, release_min_score):
    return score, soft_flags, reasons


def test_build_global_candidates_applies_filters_penalties_and_roles() -> None:
    target = date(2024, 6, 28)
    conn = _make_conn()
    _seed_stock(conn, code="AAA", sector="BK1", target_date=target, days=30, base_close=10.0, step=0.25, pct_change=8.0)
    _seed_stock(conn, code="BBB", sector="BK1", target_date=target, days=10, base_close=8.0, step=0.12, pct_change=7.0)
    _seed_stock(conn, code="CCC", sector="BK1", target_date=target, days=30, base_close=7.0, step=0.08, pct_change=6.0)
    _seed_stock(conn, code="DDD", sector="BK2", target_date=target, days=30, base_close=9.0, step=0.22, pct_change=5.0)
    _seed_stock(conn, code="EEE", sector="BKX", target_date=target, days=30, base_close=11.0, step=0.2, pct_change=9.0)

    def _fundamentals_loader(cursor, codes, target_date):
        return {
            "AAA": {"code": "AAA", "pe_ttm": 12.0, "profit_growth": 24.0, "revenue_growth": 18.0, "roe": 15.0},
            "BBB": {"code": "BBB", "pe_ttm": 15.0, "profit_growth": 20.0, "revenue_growth": 16.0, "roe": 13.0},
            "CCC": {"code": "CCC", "pe_ttm": 0.0, "profit_growth": -5.0, "revenue_growth": -2.0, "roe": 4.0},
            "DDD": {"code": "DDD", "pe_ttm": 11.0, "profit_growth": 18.0, "revenue_growth": 14.0, "roe": 11.0},
        }

    def _check_fundamentals(fundamentals):
        if fundamentals.get("code") == "CCC":
            return False, 0.0, ["基本面弱"]
        return True, 40.0, ["基本面通过"]

    out = global_entry_selector.build_global_candidates(
        conn.cursor(),
        target_date=target,
        top_n=10,
        market_cap_min=1_000_000.0,
        market_cap_max=100_000_000_000.0,
        cross_sector_scan_limit=50,
        exclude_sectors={"BKX"},
        exclude_codes={"DDD"},
        cup_handle_enabled=True,
        cup_handle_bonus=8.0,
        relative_strength_bonus_cap=6.0,
        release_enabled=False,
        release_min_score=80.0,
        cup_handle_loader=lambda current_date: {"AAA"},
        structure_confirm_loader=lambda *, code, target_date: (
            {"passed": False, "reasons": ["结构弱"]} if code == "BBB" else {"passed": True, "reasons": ["结构通过"]}
        ),
        fundamentals_loader=_fundamentals_loader,
        check_fundamentals=_check_fundamentals,
        history_batch_loader=_history_batch_loader,
        weekly_returns_loader=lambda code, target_date: {
            "AAA": {"status": "ok", "ret_1w": 12.0, "ret_4w": 20.0, "ret_12w": 28.0},
            "BBB": {"status": "ok", "ret_1w": 8.0, "ret_4w": 12.0, "ret_12w": 16.0},
            "CCC": {"status": "ok", "ret_1w": 5.0, "ret_4w": 8.0, "ret_12w": 10.0},
        }[code],
        wave_phase_detector=lambda *, closes, highs, lows: ("3浪", 0.8),
        focus_gate_checker=lambda cursor, code, stock_name, role, target_date, market_focus_snapshot_loader: (
            True,
            ["focus-ok"],
            {"focus_bonus": 2.0},
        ),
        strong_leader_release=_identity_release,
        market_focus_snapshot_loader=lambda cursor, *, code, stock_name, target_date: {},
        stock_candidate_factory=lambda **kwargs: SimpleNamespace(**kwargs),
    )

    assert [item.code for item in out] == ["AAA", "BBB", "CCC"]
    assert all(item.signal_source == "cross_sector" for item in out)
    assert out[0].role == "龙头"
    assert out[1].role == "龙头"
    assert out[2].role == "中军"
    assert "板块龙头（多因子）" in out[0].buy_reasons
    assert any(reason.startswith("相对板块强度+") for reason in out[0].buy_reasons)

    by_code = {item.code: item for item in out}
    assert "DDD" not in by_code
    assert "EEE" not in by_code
    assert by_code["BBB"].soft_flags.count("structure_soft_fail") == 1
    assert by_code["BBB"].soft_flags.count("history_short") == 1
    assert by_code["CCC"].soft_flags.count("fundamentals_soft_fail") == 1


def test_build_global_candidates_supports_stock_candidate_like_factory_and_top_n() -> None:
    target = date(2024, 6, 28)
    conn = _make_conn()
    _seed_stock(conn, code="AAA", sector="BK2", target_date=target, days=30, base_close=9.0, step=0.2, pct_change=7.0)
    _seed_stock(conn, code="BBB", sector="BK2", target_date=target, days=30, base_close=8.5, step=0.15, pct_change=5.5)

    out = global_entry_selector.build_global_candidates(
        conn.cursor(),
        target_date=target,
        top_n=1,
        market_cap_min=1_000_000.0,
        market_cap_max=100_000_000_000.0,
        cross_sector_scan_limit=50,
        exclude_sectors=set(),
        exclude_codes=set(),
        cup_handle_enabled=True,
        cup_handle_bonus=10.0,
        relative_strength_bonus_cap=6.0,
        release_enabled=False,
        release_min_score=80.0,
        cup_handle_loader=lambda current_date: {"AAA", "BBB"},
        structure_confirm_loader=lambda *, code, target_date: {"passed": True, "reasons": ["结构通过"]},
        fundamentals_loader=lambda cursor, codes, target_date: {
            code: {"code": code, "pe_ttm": 10.0, "profit_growth": 20.0, "revenue_growth": 15.0, "roe": 12.0}
            for code in codes
        },
        check_fundamentals=lambda fundamentals: (True, 40.0, ["基本面通过"]),
        history_batch_loader=_history_batch_loader,
        weekly_returns_loader=lambda code, target_date: {
            "AAA": {"status": "ok", "ret_1w": 10.0, "ret_4w": 18.0, "ret_12w": 24.0},
            "BBB": {"status": "ok", "ret_1w": 7.0, "ret_4w": 10.0, "ret_12w": 14.0},
        }[code],
        wave_phase_detector=lambda *, closes, highs, lows: ("3浪", 0.8),
        focus_gate_checker=lambda cursor, code, stock_name, role, target_date, market_focus_snapshot_loader: (
            True,
            [],
            {"focus_bonus": 0.0},
        ),
        strong_leader_release=_identity_release,
        market_focus_snapshot_loader=lambda cursor, *, code, stock_name, target_date: {},
        stock_candidate_factory=lambda **kwargs: dict(kwargs),
    )

    assert len(out) == 1
    assert out[0]["code"] == "AAA"
    assert sorted(out[0].keys()) == [
        "buy_reasons",
        "buy_score",
        "code",
        "cup_handle_ok",
        "market_cap_yi",
        "name",
        "pe_ttm",
        "price_position",
        "profit_growth",
        "ret_5d",
        "revenue_growth",
        "roe",
        "role",
        "sector",
        "sector_resonance",
        "signal_source",
        "soft_flags",
        "vol_ratio",
        "wave_phase",
    ]
