from __future__ import annotations

import sqlite3
from pathlib import Path
from types import SimpleNamespace

from apps.api.main import BootstrapApiService


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _make_service() -> BootstrapApiService:
    return BootstrapApiService(project_root=PROJECT_ROOT)


def test_lowfreq_score_pool_view_carries_formal_front_for_tracked_candidate(tmp_path: Path) -> None:
    service = _make_service()
    db_path = tmp_path / "lowfreq_score_sync.db"
    service._stock_db_default_path = db_path
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            """
            CREATE TABLE stocks (
              code TEXT PRIMARY KEY,
              name TEXT,
              sector_lv1 TEXT,
              sector_lv2 TEXT
            )
            """
        )
        conn.executemany(
            "INSERT INTO stocks(code, name, sector_lv1, sector_lv2) VALUES (?, ?, ?, ?)",
            [
                ("600001", "跟踪股", "科技", "机器人"),
                ("600002", "持有股", "科技", "机器人"),
                ("600003", "已清仓股", "科技", "人工智能"),
            ],
        )
        conn.commit()

    service._lowfreq_latest_trade_date = lambda: "2026-06-10"
    service._load_lowfreq_sim_state = lambda: {
        "positions": {
            "600002": {
                "code": "600002",
                "name": "持有股",
                "sector": "I65",
                "buy_date": "2026-06-05",
                "buy_price": 10.0,
                "shares": 1000,
                "buy_score": 96.0,
                "wave_phase": "3浪",
                "status": "open",
                "role": "龙头",
            }
        },
        "closed_trades": [
            {
                "code": "600003",
                "name": "已清仓股",
                "sector": "C42",
                "buy_date": "2026-05-20",
                "buy_price": 8.0,
                "sell_date": "2026-06-07",
                "sell_price": 10.0,
                "shares": 1000,
                "return_pct": 25.0,
                "sell_reason": "板块见顶确认",
                "status": "closed",
                "role": "中军",
            }
        ],
    }

    class _ScoreEngine:
        def generate_buy_signals(self, _target_date):
            return {
                "candidate_signals": [
                    {
                        "code": "600001",
                        "name": "跟踪股",
                        "sector": "I88",
                        "entry_ready": False,
                        "buy_score": 88.0,
                        "reasons": ["候选识别成立"],
                        "formal": {
                            "status": "ok",
                            "small_cycle": {
                                "cycle_state": "S1 Emerging",
                                "state_stability_level": "watch",
                            },
                            "identify_state": {
                                "status": "identified",
                                "reason": "small_cycle_enters_formal_watch_scope",
                            },
                            "tracking_state": {
                                "status": "tracking",
                                "maturity": "observe",
                                "transition_reason": "small_cycle_requires_more_confirmation",
                            },
                            "entry_state": {
                                "status": "not_ready",
                                "decision": "wait",
                                "actionable": False,
                                "blocking_reasons": ["tracking_not_mature"],
                            },
                            "m1_constraints_ref": {
                                "blocked": False,
                                "blocking_reasons": [],
                                "profile_window_ready": True,
                            },
                        },
                    }
                ]
            }

        def _get_price(self, code, _target_date):
            return {"600001": 12.3, "600002": 10.8}.get(code)

        def check_sell_signal_v2(self, trade, _target_date):
            if str(getattr(trade, "code", "")) == "600002":
                return SimpleNamespace(reason="sector_top_confirmed", details="板块见顶确认")
            return None

    service._lowfreq_engine_v16 = lambda: _ScoreEngine()

    pool_payload = service.lowfreq_score_pool_view(limit=20)
    pool_by_code = {item["code"]: item for item in pool_payload["pool"]}

    assert pool_payload["meta"]["as_of_date"] == "2026-06-10"
    assert pool_by_code["600001"]["state"] == "跟踪"
    assert pool_by_code["600001"]["sector_name"] == "机器人"
    assert pool_by_code["600001"]["formal_front"]["status"] == "ok"
    assert pool_by_code["600001"]["formal_front"]["small_cycle"]["cycle_state"] == "S1 Emerging"
    assert pool_by_code["600001"]["formal_front"]["entry_state"]["status"] == "not_ready"
