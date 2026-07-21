from __future__ import annotations

import os
import sqlite3
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

from apps.api.main import BootstrapApiService


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _seed_daily_prices_100d(*, db_path: Path, code: str, obs_date: str) -> None:
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE daily_prices (
              code TEXT NOT NULL,
              trade_date TEXT NOT NULL,
              open REAL,
              high REAL
            )
            """
        )
        conn.commit()

        entry_dt = date.fromisoformat(obs_date) + timedelta(days=1)
        for i in range(100):
            dt = entry_dt + timedelta(days=i)
            trade_date = dt.isoformat()
            open_price = 10.0 if i == 0 else None
            high_price = 10.0 + (6.0 * (i / 99.0))
            conn.execute(
                "INSERT INTO daily_prices(code, trade_date, open, high) VALUES(?,?,?,?)",
                (code, trade_date, open_price, high_price),
            )
        conn.commit()
    finally:
        conn.close()


def test_lowfreq_confidence_daily_run_generates_100d_labels(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "stock_data.db"
    target_date = "2026-01-01"
    code = "600001"
    _seed_daily_prices_100d(db_path=db_path, code=code, obs_date=target_date)
    monkeypatch.setenv("NEOTRADE3_STOCK_DB_PATH", str(db_path))

    service = BootstrapApiService(project_root=PROJECT_ROOT)
    monkeypatch.setattr(service, "_lowfreq_latest_trade_date", lambda: target_date)
    monkeypatch.setattr(
        service,
        "_lowfreq_next_trading_day",
        lambda obs_date: (date.fromisoformat(str(obs_date)) + timedelta(days=1)).isoformat(),
    )
    monkeypatch.setattr(service, "_load_lowfreq_sim_state", lambda: {"positions": {}})
    monkeypatch.setattr(service, "_save_lowfreq_sim_state", lambda state: None)
    monkeypatch.setattr(
        service,
        "_lowfreq_engine_v16",
        lambda: SimpleNamespace(),
    )
    monkeypatch.setattr(
        service,
        "lowfreq_hot_sectors_view",
        lambda **kwargs: {
            "sectors": [
                {
                    "sector_lv2": "测试板块",
                    "leaders": [
                        {
                            "code": code,
                            "name": "测试股票",
                            "role": "龙头",
                            "buy_score": 120.0,
                            "buy_signal": True,
                            "risk_level": "ok",
                            "risk_reason": None,
                        }
                    ],
                    "middle": [],
                    "followers": [],
                }
            ]
        },
    )

    payload = service.lowfreq_confidence_daily_run_view(
        target_date=target_date,
        requested_by="test",
        max_label_updates=50,
    )
    assert payload["labels_updated"] >= 1

    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute(
            "SELECT label_status, max_return_100d, hit_50pct FROM stock_forward_labels_100d WHERE obs_date = ? AND code = ?",
            (target_date, code),
        ).fetchone()
        assert row is not None
        assert str(row[0]) == "ready"
        assert float(row[1]) >= 0.50
        assert int(row[2]) == 1

        bucket_row = conn.execute(
            "SELECT COUNT(*) FROM confidence_calibration_buckets_100d WHERE as_of_date = ?",
            (target_date,),
        ).fetchone()
        assert bucket_row is not None
        assert int(bucket_row[0] or 0) >= 1
    finally:
        conn.close()

