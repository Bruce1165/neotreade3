from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from types import SimpleNamespace

from neotrade3.cycle_intelligence import sector_entry_selector


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
) -> None:
    conn.execute(
        """
        INSERT INTO stocks(code, name, sector_lv1, total_market_cap, is_delisted)
        VALUES (?, ?, ?, ?, 0)
        """,
        (code, f"{code}-name", sector, 25_000_000_000.0),
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
                pct_change if offset == 0 else 0.6,
                amount,
                volume,
                close * 1.02,
                close * 0.98,
            ),
        )
    conn.commit()


def _identity_release(*, score, role, wave_phase, soft_flags, reasons, release_enabled, release_min_score):
    return score, soft_flags, reasons


def test_check_weekly_duck_head_confirms_pattern() -> None:
    target = date(2024, 6, 28)
    closes = [
        8.0,
        8.2,
        8.4,
        8.6,
        8.8,
        9.0,
        9.2,
        9.4,
        9.6,
        9.8,
        10.0,
        10.2,
        10.4,
        10.6,
        10.8,
        11.0,
    ]
    series = []
    for idx, close in enumerate(closes):
        min_close = close
        if idx == len(closes) - 3:
            min_close = 10.0
        series.append(
            {
                "close": close,
                "min_close": min_close,
                "last_date": (target - timedelta(weeks=len(closes) - idx - 1)).isoformat(),
            }
        )
    series[-3]["min_close"] = 9.4

    out = sector_entry_selector.check_weekly_duck_head(
        "AAA",
        target,
        weekly_duck_head_enabled=True,
        weekly_duck_head_min_weeks=15,
        weekly_duck_head_ma_short=5,
        weekly_duck_head_ma_mid=10,
        weekly_duck_head_ma_long=15,
        weekly_duck_head_pullback_weeks=6,
        weekly_duck_head_breakout_lookback_weeks=4,
        weekly_duck_head_overextend_pct=20.0,
        weekly_series_loader=lambda code, current_date: {"status": "ok", "series": series},
    )

    assert out["passed"] is True
    assert out["reason"] == "weekly_duck_head_confirmed"


def test_build_sector_candidates_applies_soft_penalties_and_role_bonus(monkeypatch) -> None:
    target = date(2024, 6, 28)
    conn = _make_conn()
    _seed_stock(conn, code="AAA", sector="BK1", target_date=target, days=30, base_close=10.0, step=0.25, pct_change=6.0)
    _seed_stock(conn, code="BBB", sector="BK1", target_date=target, days=10, base_close=8.0, step=0.12, pct_change=5.0)
    _seed_stock(conn, code="CCC", sector="BK1", target_date=target, days=30, base_close=7.5, step=0.08, pct_change=4.0)

    monkeypatch.setattr(
        sector_entry_selector,
        "passes_core_focus_gate",
        lambda cursor, code, stock_name, role, target_date, market_focus_snapshot_loader: (True, ["focus-ok"], {"focus_bonus": 2.0}),
    )
    monkeypatch.setattr(sector_entry_selector, "apply_strong_leader_soft_release", _identity_release)

    weekly_views = {
        "AAA": {"status": "ok", "series": [{"close": 8.0 + i * 0.4, "min_close": 8.0 + i * 0.4} for i in range(16)]},
        "BBB": {"status": "insufficient", "series": [{"close": 10.0 + i * 0.1, "min_close": 10.0 + i * 0.1} for i in range(4)]},
        "CCC": {"status": "ok", "series": [{"close": 9.0 + i * 0.12, "min_close": 9.0 + i * 0.12} for i in range(16)]},
    }

    def _fundamentals_loader(cursor, codes, target_date):
        return {
            "AAA": {"code": "AAA", "pe_ttm": 12.0, "profit_growth": 24.0, "revenue_growth": 18.0, "roe": 15.0},
            "BBB": {"code": "BBB", "pe_ttm": 15.0, "profit_growth": 20.0, "revenue_growth": 16.0, "roe": 13.0},
            "CCC": {"code": "CCC", "pe_ttm": 0.0, "profit_growth": -5.0, "revenue_growth": -2.0, "roe": 4.0},
        }

    def _check_fundamentals(fundamentals):
        if fundamentals.get("code") == "CCC":
            return False, 0.0, ["基本面弱"]
        return True, 40.0, ["基本面通过"]

    out = sector_entry_selector.build_sector_candidates(
        conn.cursor(),
        sector="BK1",
        target_date=target,
        top_n=3,
        market_cap_min=1_000_000.0,
        market_cap_max=100_000_000_000.0,
        cup_handle_enabled=True,
        cup_handle_bonus=8.0,
        relative_strength_bonus_cap=6.0,
        release_enabled=False,
        release_min_score=80.0,
        structure_confirm_mode="cup_only",
        weekly_duck_head_enabled=True,
        weekly_duck_head_min_weeks=15,
        weekly_duck_head_ma_short=5,
        weekly_duck_head_ma_mid=10,
        weekly_duck_head_ma_long=15,
        weekly_duck_head_pullback_weeks=6,
        weekly_duck_head_breakout_lookback_weeks=4,
        weekly_duck_head_overextend_pct=20.0,
        fundamentals_loader=_fundamentals_loader,
        check_fundamentals=_check_fundamentals,
        weekly_series_loader=lambda code, current_date: weekly_views[code],
        cup_handle_loader=lambda current_date: {"AAA"},
        ensure_no_lookahead_guard=lambda rows, target_date, trade_date_index, context: None,
        market_focus_snapshot_loader=lambda code, current_date: {},
        stock_candidate_factory=lambda **kwargs: SimpleNamespace(**kwargs),
    )

    assert out[0].code == "AAA"
    assert out[0].role == "龙头"
    assert "板块龙头（多因子）" in out[0].buy_reasons
    assert any(reason.startswith("相对板块强度+") for reason in out[0].buy_reasons)

    by_code = {item.code: item for item in out}
    assert by_code["BBB"].soft_flags.count("structure_soft_fail") == 1
    assert by_code["BBB"].soft_flags.count("history_short") == 1
    assert by_code["CCC"].soft_flags.count("fundamentals_soft_fail") == 1


def test_build_sector_candidates_supports_stock_candidate_like_factory_and_top_n(monkeypatch) -> None:
    target = date(2024, 6, 28)
    conn = _make_conn()
    _seed_stock(conn, code="AAA", sector="BK2", target_date=target, days=30, base_close=9.0, step=0.2, pct_change=7.0)
    _seed_stock(conn, code="BBB", sector="BK2", target_date=target, days=30, base_close=8.5, step=0.15, pct_change=5.5)

    monkeypatch.setattr(
        sector_entry_selector,
        "passes_core_focus_gate",
        lambda cursor, code, stock_name, role, target_date, market_focus_snapshot_loader: (True, [], {"focus_bonus": 0.0}),
    )
    monkeypatch.setattr(sector_entry_selector, "apply_strong_leader_soft_release", _identity_release)

    weekly_views = {
        "AAA": {"status": "ok", "series": [{"close": 7.0 + i * 0.35, "min_close": 7.0 + i * 0.35} for i in range(16)]},
        "BBB": {"status": "ok", "series": [{"close": 7.5 + i * 0.18, "min_close": 7.5 + i * 0.18} for i in range(16)]},
    }

    out = sector_entry_selector.build_sector_candidates(
        conn.cursor(),
        sector="BK2",
        target_date=target,
        top_n=1,
        market_cap_min=1_000_000.0,
        market_cap_max=100_000_000_000.0,
        cup_handle_enabled=True,
        cup_handle_bonus=10.0,
        relative_strength_bonus_cap=6.0,
        release_enabled=False,
        release_min_score=80.0,
        structure_confirm_mode="cup_only",
        weekly_duck_head_enabled=True,
        weekly_duck_head_min_weeks=15,
        weekly_duck_head_ma_short=5,
        weekly_duck_head_ma_mid=10,
        weekly_duck_head_ma_long=15,
        weekly_duck_head_pullback_weeks=6,
        weekly_duck_head_breakout_lookback_weeks=4,
        weekly_duck_head_overextend_pct=20.0,
        fundamentals_loader=lambda cursor, codes, target_date: {
            code: {"code": code, "pe_ttm": 10.0, "profit_growth": 20.0, "revenue_growth": 15.0, "roe": 12.0}
            for code in codes
        },
        check_fundamentals=lambda fundamentals: (True, 40.0, ["基本面通过"]),
        weekly_series_loader=lambda code, current_date: weekly_views[code],
        cup_handle_loader=lambda current_date: {"AAA", "BBB"},
        ensure_no_lookahead_guard=lambda rows, target_date, trade_date_index, context: None,
        market_focus_snapshot_loader=lambda code, current_date: {},
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
