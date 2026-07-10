from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from pathlib import Path

import neotrade3.cycle_intelligence.sector_cooldown as sector_cooldown


def _seed_sector_cooldown_db(db_path: Path) -> date:
    target = date(2026, 7, 10)
    conn = sqlite3.connect(str(db_path))
    try:
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
                code TEXT NOT NULL,
                trade_date TEXT NOT NULL,
                close REAL
            )
            """
        )

        returns_by_code = {
            "000001": 20.0,
            "000002": 18.0,
            "000003": 7.0,
            "000004": 6.0,
            "000005": 5.0,
            "000006": -6.0,
            "000007": -7.0,
            "000008": -8.0,
            "000009": -9.0,
            "000010": -10.0,
        }
        for idx, (code, ret) in enumerate(returns_by_code.items(), start=1):
            conn.execute(
                """
                INSERT INTO stocks(code, name, sector_lv1, total_market_cap, is_delisted)
                VALUES (?, ?, ?, ?, 0)
                """,
                (code, f"样本{idx}", "AI算力", 5_000_000_000.0 + idx),
            )
            close_5 = 100.0
            close_0 = close_5 * (1 + ret / 100)
            step = (close_0 - close_5) / 4
            for offset in range(5):
                trade_date = (target - timedelta(days=offset)).isoformat()
                close = close_0 - step * offset
                conn.execute(
                    "INSERT INTO daily_prices(code, trade_date, close) VALUES (?, ?, ?)",
                    (code, trade_date, close),
                )
        conn.commit()
    finally:
        conn.close()
    return target


def test_detect_sector_cooldown_returns_unknown_shape_when_sector_has_too_few_members(tmp_path: Path) -> None:
    db_path = tmp_path / "stock_data.db"
    target = date(2026, 7, 10)
    conn = sqlite3.connect(str(db_path))
    try:
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
                code TEXT NOT NULL,
                trade_date TEXT NOT NULL,
                close REAL
            )
            """
        )
        for idx in range(3):
            conn.execute(
                """
                INSERT INTO stocks(code, name, sector_lv1, total_market_cap, is_delisted)
                VALUES (?, ?, ?, ?, 0)
                """,
                (f"30000{idx}", f"少量样本{idx}", "小板块", 3_000_000_000.0),
            )
        conn.commit()

        out = sector_cooldown.detect_sector_cooldown(
            conn.cursor(),
            sector="小板块",
            target_date=target,
            market_cap_min=1_000_000.0,
            market_cap_max=100_000_000_000.0,
            sector_members_cache={},
            sector_cooldown_cache={},
        )
    finally:
        conn.close()

    assert out == {
        "cooldown_detected": False,
        "follower_weakness": 0,
        "leader_strength": 0.5,
        "trend_state": "unknown",
    }


def test_detect_sector_cooldown_calculates_diverging_cooldown_signal(tmp_path: Path) -> None:
    db_path = tmp_path / "stock_data.db"
    target = _seed_sector_cooldown_db(db_path)
    conn = sqlite3.connect(str(db_path))
    try:
        out = sector_cooldown.detect_sector_cooldown(
            conn.cursor(),
            sector="AI算力",
            target_date=target,
            market_cap_min=1_000_000.0,
            market_cap_max=100_000_000_000.0,
            sector_members_cache={},
            sector_cooldown_cache={},
        )
    finally:
        conn.close()

    assert out["cooldown_detected"] is True
    assert out["trend_state"] == "diverging"
    assert out["leader_strength"] > 0.9
    assert out["follower_weakness"] > 0.8
    assert out["leader_avg"] > 15
    assert out["follower_avg"] < -5


def test_confirm_sector_cooldown_uses_window_hits_and_latest_payload() -> None:
    seen_ranges: list[tuple[date, date]] = []
    target = date(2026, 7, 10)
    dates = [date(2026, 7, 8), date(2026, 7, 9), date(2026, 7, 10)]
    payload_by_date = {
        dates[0]: {
            "cooldown_detected": True,
            "follower_weakness": 0.72,
            "trend_state": "diverging",
        },
        dates[1]: {
            "cooldown_detected": False,
            "follower_weakness": 0.31,
            "trend_state": "consolidating",
        },
        dates[2]: {
            "cooldown_detected": True,
            "follower_weakness": 0.81,
            "trend_state": "falling",
            "leader_strength": 0.42,
        },
    }

    def _trading_dates_loader(start: date, end: date) -> list[date]:
        seen_ranges.append((start, end))
        return dates

    def _cooldown_loader(sector: str, current_date: date) -> dict:
        assert sector == "AI算力"
        return dict(payload_by_date[current_date])

    out = sector_cooldown.confirm_sector_cooldown(
        "AI算力",
        target,
        window=3,
        required=2,
        trading_dates_loader=_trading_dates_loader,
        cooldown_loader=_cooldown_loader,
    )

    assert seen_ranges == [(date(2026, 5, 31), target)]
    assert out["confirmed"] is True
    assert out["hits"] == 2
    assert out["checked"] == 3
    assert out["latest"]["trend_state"] == "falling"
