from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

from neotrade3.cycle_intelligence.sector_heat import build_hot_sectors


def _seed_sector_heat_db(db_path: Path) -> date:
    target = date(2026, 7, 10)
    prev = target - timedelta(days=1)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE stocks (
                code TEXT PRIMARY KEY,
                name TEXT,
                sector_lv1 TEXT,
                sector_lv2 TEXT,
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
                pct_change REAL,
                volume REAL,
                amount REAL
            )
            """
        )

        sector_rows = {
            "BK_A": ("机器人", 1.5, 0.5),
            "BK_B": ("算力", 2.5, 2.3),
            "BK_C": ("医药", 0.8, 0.0),
        }
        code_index = 1
        for sector_code, (sector_name, target_pct, prev_pct) in sector_rows.items():
            for member in range(3):
                code = f"60{code_index:04d}"
                code_index += 1
                conn.execute(
                    """
                    INSERT INTO stocks(code, name, sector_lv1, sector_lv2, total_market_cap, is_delisted)
                    VALUES (?, ?, ?, ?, ?, 0)
                    """,
                    (code, f"{sector_name}{member}", sector_code, sector_name, 5_000_000_000.0),
                )
                conn.execute(
                    """
                    INSERT INTO daily_prices(code, trade_date, pct_change, volume, amount)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (code, target.isoformat(), target_pct, 1000 + member, 100000 + member),
                )
                conn.execute(
                    """
                    INSERT INTO daily_prices(code, trade_date, pct_change, volume, amount)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (code, prev.isoformat(), prev_pct, 900 + member, 90000 + member),
                )
        conn.commit()
    finally:
        conn.close()
    return target


def test_build_hot_sectors_skips_cooldown_sector_and_applies_bonuses(tmp_path: Path) -> None:
    db_path = tmp_path / "stock_data.db"
    target = _seed_sector_heat_db(db_path)
    conn = sqlite3.connect(str(db_path))
    skip_events: list[tuple[str, float]] = []

    def _cooldown_loader(sector: str, current_date: date, cursor=None) -> dict:
        assert cursor is not None
        assert current_date == target
        if sector == "BK_A":
            return {
                "cooldown_detected": False,
                "follower_weakness": 0.2,
                "leader_strength": 0.9,
                "trend_state": "rising",
            }
        if sector == "BK_B":
            return {
                "cooldown_detected": True,
                "follower_weakness": 0.81,
                "leader_strength": 0.7,
                "trend_state": "falling",
            }
        return {
            "cooldown_detected": False,
            "follower_weakness": 0.3,
            "leader_strength": 0.55,
            "trend_state": "consolidating",
        }

    try:
        out = build_hot_sectors(
            conn.cursor(),
            target_date=target,
            top_n=2,
            market_cap_min=1_000_000.0,
            market_cap_max=100_000_000_000.0,
            sector_accel_bonus_enabled=True,
            sector_accel_lookback_trading_days=1,
            sector_accel_bonus_high=12.0,
            sector_accel_bonus_low=5.0,
            recent_trading_dates_loader=lambda current_date, limit: [target - timedelta(days=1)],
            sector_cooldown_loader=_cooldown_loader,
            sector_heat_factory=lambda **kwargs: SimpleNamespace(**kwargs),
            skip_logger=lambda sector, cooldown_info: skip_events.append(
                (str(sector), float(cooldown_info.get("follower_weakness") or 0.0))
            ),
        )
    finally:
        conn.close()

    assert [item.sector for item in out] == ["BK_A", "BK_C"]
    assert [item.name for item in out] == ["机器人", "医药"]
    assert out[0].heat_score == 97.0
    assert out[1].heat_score == 72.0
    assert out[0].trend_state == "rising"
    assert out[0].leader_strength == 0.9
    assert out[0].follower_weakness == 0.2
    assert out[0].momentum_5d == 1.5
    assert out[0].stock_count == 3
    assert skip_events == [("BK_B", 0.81)]


def test_build_hot_sectors_returns_sector_heat_like_shape(tmp_path: Path) -> None:
    db_path = tmp_path / "stock_data.db"
    target = _seed_sector_heat_db(db_path)
    conn = sqlite3.connect(str(db_path))
    try:
        out = build_hot_sectors(
            conn.cursor(),
            target_date=target,
            top_n=1,
            market_cap_min=1_000_000.0,
            market_cap_max=100_000_000_000.0,
            sector_accel_bonus_enabled=False,
            sector_accel_lookback_trading_days=1,
            sector_accel_bonus_high=12.0,
            sector_accel_bonus_low=5.0,
            recent_trading_dates_loader=lambda current_date, limit: [],
            sector_cooldown_loader=lambda sector, current_date, cursor=None: {
                "cooldown_detected": False,
                "follower_weakness": 0.1,
                "leader_strength": 0.4,
                "trend_state": "consolidating",
            },
            sector_heat_factory=lambda **kwargs: dict(kwargs),
        )
    finally:
        conn.close()

    assert len(out) == 1
    item = out[0]
    assert sorted(item.keys()) == [
        "follower_weakness",
        "heat_score",
        "leader_strength",
        "momentum_5d",
        "name",
        "sector",
        "stock_count",
        "trend_state",
    ]
    assert item["sector"] == "BK_B"
    assert item["name"] == "算力"
