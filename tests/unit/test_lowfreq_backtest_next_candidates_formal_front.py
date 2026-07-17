from __future__ import annotations

import sqlite3
from pathlib import Path
from types import SimpleNamespace

from apps.api.main import BootstrapApiService


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _make_service() -> BootstrapApiService:
    return BootstrapApiService(project_root=PROJECT_ROOT)


def test_lowfreq_backtest_run_view_projects_formal_front_into_next_candidates(tmp_path: Path) -> None:
    service = _make_service()
    db_path = tmp_path / "backtest_next_candidates.db"
    service._stock_db_default_path = db_path

    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            """
            CREATE TABLE trading_calendar_cache (
              trade_date TEXT PRIMARY KEY
            )
            """
        )
        conn.executemany(
            "INSERT INTO trading_calendar_cache(trade_date) VALUES (?)",
            [("2026-06-10",), ("2026-06-11",), ("2026-06-12",)],
        )
        conn.execute(
            """
            CREATE TABLE daily_prices (
              code TEXT,
              trade_date TEXT,
              close REAL
            )
            """
        )
        conn.commit()

    class _BacktestEngine:
        EXECUTION_MODE = "unbounded_opportunity"

        def run_backtest(
            self,
            start_date,
            end_date,
            initial_capital=1_000_000.0,
            *,
            include_trades=False,
            include_daily_values=False,
        ):
            return {
                "total_return_pct": 12.34,
                "annual_return_pct": 18.9,
                "max_drawdown_pct": -5.1,
                "win_rate_pct": 55.0,
                "sharpe": 1.2,
                "trades": [
                    SimpleNamespace(
                        code="600001",
                        buy_date="2026-06-10",
                        sell_date="2026-06-11",
                        buy_price=10.0,
                        sell_price=11.0,
                        return_pct=10.0,
                        hold_days=1,
                        role="龙头",
                        sell_reason="测试卖出",
                    )
                ],
                "config_snapshot": {"execution_mode": "unbounded_opportunity"},
                "trade_blocks": {},
                "execution_action_summary": {"buy": 1},
                "coverage_gaps": {},
                "buy_signal_audit": [],
            }

        def generate_buy_signals(self, _target_date):
            return {
                "signal_summary": {"candidate_count": 1, "entry_count": 1},
                "entry_signals": [
                    {
                        "code": "600001",
                        "name": "下一交易日候选",
                        "sector": "机器人",
                        "role": "龙头",
                        "buy_score": 92.0,
                        "wave_phase": "3浪",
                        "resonance": 0.9,
                        "reasons": ["正式买点成立"],
                        "formal": {
                            "status": "ok",
                            "small_cycle": {
                                "cycle_state": "S2 Advancing",
                                "state_stability_level": "stable",
                            },
                            "identify_state": {
                                "status": "identified",
                                "reason": "small_cycle_enters_formal_watch_scope",
                            },
                            "tracking_state": {
                                "status": "tracking",
                                "maturity": "ready_for_entry",
                                "transition_reason": "small_cycle_supports_formal_action",
                            },
                            "entry_state": {
                                "status": "ready",
                                "decision": "enter",
                                "actionable": True,
                                "blocking_reasons": [],
                            },
                            "m1_constraints_ref": {
                                "blocked": False,
                                "blocking_reasons": [],
                                "profile_window_ready": True,
                            },
                        },
                    }
                ],
            }

        def _get_price(self, code, target_date):
            return 11.0

        def check_sell_signal_v2(self, trade, target_date):
            return None

    service._lowfreq_engine_v16 = lambda: _BacktestEngine()

    payload = service.lowfreq_backtest_run_view(
        start_date="2026-06-10",
        end_date="2026-06-10",
        async_run=False,
        requested_by="pytest",
    )

    assert payload["next_session"]["next_trading_day"] == "2026-06-11"
    assert payload["next_session"]["candidates"][0]["code"] == "600001"
    assert payload["next_session"]["candidates"][0]["formal_front"]["status"] == "ok"
    assert (
        payload["next_session"]["candidates"][0]["formal_front"]["entry_state"]["actionable"]
        is True
    )
    assert payload["next_session"]["signal_summary"]["candidate_count"] == 1
