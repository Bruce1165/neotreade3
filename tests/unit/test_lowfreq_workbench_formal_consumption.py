from __future__ import annotations

from datetime import date
from pathlib import Path
from types import SimpleNamespace

from apps.api.main import BootstrapApiService
from lowfreq_engine_v16_advanced import StockCandidate, SectorHeat


class _DummyLowfreqEngine:
    HOT_SECTOR_COUNT = 3
    BUY_THRESHOLD = 90.0
    MIN_RESONANCE = 0.5

    def get_hot_sectors(self, target_date, top_n=3):
        return [SectorHeat("BK001", "机器人", 88.5)]

    def get_sector_candidates(self, sector, target_date, top_n=15):
        return [
            StockCandidate(
                code="600001",
                name="领涨一号",
                sector="机器人",
                market_cap_yi=120.0,
                role="龙头",
                buy_score=96.0,
                buy_reasons=["突破确认"],
                wave_phase="3",
                sector_resonance=0.9,
                ret_5d=7.2,
            )
        ]

    def generate_buy_signals(self, target_date):
        return {
            "candidate_signals": [
                {
                    "code": "600001",
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
            ]
        }


def test_build_lowfreq_hot_sectors_snapshot_attaches_formal_front() -> None:
    service = BootstrapApiService(project_root=str(Path(__file__).resolve().parents[2]))
    payload = service._build_lowfreq_hot_sectors_snapshot(
        engine=_DummyLowfreqEngine(),
        state={},
        target_date=date(2026, 7, 7),
        include_portfolio=False,
        include_sell_signal=False,
        perf={},
    )

    leader = payload["sectors"][0]["leaders"][0]
    assert leader["buy_signal"] is True
    assert leader["formal_front"]["status"] == "ok"
    assert leader["formal_front"]["entry_state"]["actionable"] is True
