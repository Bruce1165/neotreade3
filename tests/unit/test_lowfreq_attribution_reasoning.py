from __future__ import annotations

import importlib.util
from datetime import date
from pathlib import Path
from types import SimpleNamespace

from neotrade3.analysis.attribution_reasoning import resolve_sell_reason_bucket


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _load_script_module(relative_path: str, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, PROJECT_ROOT / relative_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ATTR_MODULE = _load_script_module(
    "scripts/generate_lowfreq_top200_attribution_report.py",
    "lowfreq_top200_attribution_reasoning_test",
)


def test_sell_reason_bucket_uses_engine_canonical_exit_taxonomy() -> None:
    assert resolve_sell_reason_bucket("创业板见顶确认候选：趋势转弱=是 | 广度转弱=是 | 代理回撤-10.5%") == (
        "market_top_confirmed"
    )
    assert resolve_sell_reason_bucket("板块见顶确认：AI退潮") == "sector_top_confirmed"
    assert resolve_sell_reason_bucket("早窗硬证伪退出：跌破买入价-5.2%（阈值-5.0%）") == "thesis_invalidated"
    assert resolve_sell_reason_bucket("回测结束平仓") == "回测结束平仓"


def test_audit_daily_reason_distinguishes_entry_from_candidate() -> None:
    class _Ctx:
        def buy_signal_audit_entry(self, *, code: str, target_date: date):
            return None

        def market_filter_state(self, _target_date):
            return {"filtered": False, "sentiment": "normal", "score": 72.0}

        def entry_signals(self, _target_date):
            return {
                "600460": {
                    "code": "600460",
                    "buy_score": 95.0,
                    "role": "龙头",
                    "wave_phase": "3浪",
                    "candidate_tier": "entry_ready",
                    "reasons": ["正式建仓"],
                }
            }

        def candidate_signals(self, _target_date):
            return {
                "300308": {
                    "code": "300308",
                    "buy_score": 90.0,
                    "role": "龙头",
                    "wave_phase": "1浪",
                    "candidate_tier": "soft_retained",
                    "entry_ready": False,
                    "reasons": ["soft retained"],
                }
            }

        def hot_sectors(self, _target_date):
            return []

    entry_audit = ATTR_MODULE._audit_daily_reason(
        engine=SimpleNamespace(),
        ctx=_Ctx(),
        code="600460",
        name="士兰微",
        sector="半导体",
        target_date=date(2025, 6, 18),
    )
    candidate_audit = ATTR_MODULE._audit_daily_reason(
        engine=SimpleNamespace(),
        ctx=_Ctx(),
        code="300308",
        name="中际旭创",
        sector="光模块",
        target_date=date(2025, 6, 18),
    )

    assert entry_audit["stage"] == "entry_signal_selected"
    assert entry_audit["reason"] == "进入正式建仓池"
    assert candidate_audit["stage"] == "candidate_signal_selected"
    assert candidate_audit["signal"]["candidate_tier"] == "soft_retained"


def test_audit_daily_reason_keeps_formal_tracking_in_candidate_bucket() -> None:
    class _Ctx:
        def buy_signal_audit_entry(self, *, code: str, target_date: date):
            return None

        def market_filter_state(self, _target_date):
            return {"filtered": False, "sentiment": "normal", "score": 72.0}

        def entry_signals(self, _target_date):
            return {}

        def candidate_signals(self, _target_date):
            return {
                "300308": {
                    "code": "300308",
                    "buy_score": 90.0,
                    "role": "龙头",
                    "wave_phase": "1浪",
                    "candidate_tier": "soft_retained",
                    "entry_ready": False,
                    "formal_front": {
                        "status": "ok",
                        "identify_state": {"status": "identified", "reason": "watch_scope"},
                        "tracking_state": {
                            "status": "tracking",
                            "maturity": "observe",
                            "transition_reason": "await_more_confirmation",
                        },
                        "entry_state": {
                            "status": "not_ready",
                            "decision": "wait",
                            "actionable": False,
                            "blocking_reasons": ["tracking_not_mature"],
                        },
                    },
                    "reasons": ["formal tracking"],
                }
            }

        def hot_sectors(self, _target_date):
            return []

    candidate_audit = ATTR_MODULE._audit_daily_reason(
        engine=SimpleNamespace(),
        ctx=_Ctx(),
        code="300308",
        name="中际旭创",
        sector="光模块",
        target_date=date(2025, 6, 18),
    )

    assert candidate_audit["stage"] == "candidate_signal_selected"
    assert candidate_audit["signal"]["entry_ready"] is False
    assert candidate_audit["signal"]["candidate_tier"] == "soft_retained"


def test_audit_daily_reason_marks_cross_sector_wave_filter_stage() -> None:
    class _Ctx:
        def buy_signal_audit_entry(self, *, code: str, target_date: date):
            return None

        def market_filter_state(self, _target_date):
            return {"filtered": False, "sentiment": "normal", "score": 72.0}

        def entry_signals(self, _target_date):
            return {}

        def candidate_signals(self, _target_date):
            return {}

        def hot_sectors(self, _target_date):
            return []

        def global_seed_codes(self, _target_date):
            return {"300308"}

        def global_candidates(self, _target_date):
            return {
                "300308": SimpleNamespace(
                    code="300308",
                    wave_phase="2浪",
                    role="龙头",
                    sector_resonance=0.85,
                    buy_score=98.0,
                    cup_handle_ok=True,
                )
            }

    audit = ATTR_MODULE._audit_daily_reason(
        engine=SimpleNamespace(
            MIN_RESONANCE=0.7,
            CROSS_SECTOR_WAVE3_ONLY=True,
            CROSS_SECTOR_ALLOW_WAVE1=True,
            BUY_THRESHOLD=85.0,
            CROSS_SECTOR_SCORE_MARGIN=8.0,
            CUP_HANDLE_NONCONFIRM_THRESHOLD_BONUS=0.0,
        ),
        ctx=_Ctx(),
        code="300308",
        name="中际旭创",
        sector="光模块",
        target_date=date(2025, 6, 18),
        analysis_mode="full",
    )

    assert audit["stage"] == "global_wave_filtered"
    assert audit["reason"] == "跨板块分支波段不符（2浪）"


def test_analyze_topk_aggregates_candidate_without_entry(monkeypatch) -> None:
    ranking = [
        {
            "rank": 1,
            "code": "300308",
            "name": "中际旭创",
            "sector": "光模块",
            "annual_return_pct": 168.0,
        }
    ]

    monkeypatch.setattr(
        ATTR_MODULE,
        "_compute_wave_segment",
        lambda conn, *, code, year: {
            "status": "ok",
            "code": code,
            "start_date": "2025-01-02",
            "top_date": "2025-01-03",
            "segment_return_pct": 65.0,
        },
    )
    monkeypatch.setattr(
        ATTR_MODULE,
        "_load_trading_dates",
        lambda conn, *, start_date, end_date: ["2025-01-02", "2025-01-03"],
    )

    class _DummyCtx:
        def __init__(self, *, engine, conn, buy_signal_audit_entries=None) -> None:
            self.engine = engine
            self.conn = conn

    monkeypatch.setattr(ATTR_MODULE, "AuditContext", _DummyCtx)
    monkeypatch.setattr(
        ATTR_MODULE,
        "_audit_daily_reason",
        lambda **kwargs: (
            {
                "date": "2025-01-02",
                "stage": "candidate_signal_selected",
                "reason": "进入候选池，但未进入正式建仓池",
                "signal": {"candidate_tier": "soft_retained"},
            }
            if kwargs["target_date"].isoformat() == "2025-01-02"
            else {
                "date": "2025-01-03",
                "stage": "global_seed_miss",
                "reason": "所属板块未进热点，且个股未进入跨板块扫描种子",
            }
        ),
    )

    _segments, rows, aggregate = ATTR_MODULE._analyze_topk(
        engine=SimpleNamespace(MAX_POSITIONS=3),
        conn=SimpleNamespace(),
        ranking=ranking,
        backtest_payload={"trades": []},
        year=2025,
    )

    assert aggregate["candidate_picked_count"] == 1
    assert aggregate["entry_picked_count"] == 0
    assert aggregate["reason_buckets"]["candidate_not_entry"] == 1
    assert rows[0]["candidate_picked"] is True
    assert rows[0]["entry_picked"] is False
    assert rows[0]["reason_bucket"] == "candidate_not_entry"
    assert rows[0]["primary_reason"] == "进入候选池但被软保留，未进入正式建仓池"


def test_extract_execution_reason_skips_full_book_in_unbounded_mode() -> None:
    class _Result:
        def __init__(self, rows):
            self._rows = rows

        def fetchall(self):
            return list(self._rows)

        def fetchone(self):
            return self._rows[0] if self._rows else None

    class _Conn:
        def execute(self, sql, params):
            if "LIMIT 3" in sql:
                return _Result([("2025-12-30", 3.0, 10.0, 9.5, 9.8)])
            if "SELECT close" in sql:
                return _Result([(9.8,)])
            raise AssertionError(f"unexpected sql: {sql}")

    class _Ctx:
        def signals(self, _target_date):
            return {}

    reason = ATTR_MODULE._extract_execution_reason(
        code="301123",
        signal_dates=["2025-12-30"],
        positions_timeline={"2025-12-30": {"000001", "000002", "000003"}},
        conn=_Conn(),
        engine=SimpleNamespace(),
        ctx=_Ctx(),
        max_positions=3,
        segment_top_date="2025-12-30",
        buy_signal_audits=[],
        code_trades=[],
        execution_mode="unbounded_opportunity",
    )

    assert reason == "信号存在但未形成实际成交，需复核执行窗口"


def test_extract_execution_reason_uses_buy_signal_audit_before_fallback() -> None:
    class _Result:
        def __init__(self, rows):
            self._rows = rows

        def fetchall(self):
            return list(self._rows)

        def fetchone(self):
            return self._rows[0] if self._rows else None

    class _Conn:
        def execute(self, sql, params):
            if "LIMIT 3" in sql:
                return _Result([("2025-09-01", 10.0, 10.0, 10.0, 10.0)])
            if "SELECT close" in sql:
                return _Result([(10.0,)])
            raise AssertionError(f"unexpected sql: {sql}")

    class _Ctx:
        def signals(self, _target_date):
            return {}

    reason = ATTR_MODULE._extract_execution_reason(
        code="601606",
        signal_dates=["2025-08-29"],
        positions_timeline={},
        conn=_Conn(),
        engine=SimpleNamespace(),
        ctx=_Ctx(),
        max_positions=3,
        segment_top_date="2025-09-02",
        buy_signal_audits=[
            {
                "date": "2025-09-01",
                "action_type": "block",
                "blocked_reason": "chase_entry_blocked",
                "execution_block_reason": "execution_rule_blocked",
            }
        ],
        code_trades=[{"buy_date": "2025-09-03", "sell_date": "2025-09-05"}],
        execution_mode="unbounded_opportunity",
    )

    assert reason == "信号存在但因追高型买点被硬禁，见顶后才成交"


def test_extract_execution_reason_marks_late_buy_after_top() -> None:
    class _Result:
        def __init__(self, rows):
            self._rows = rows

        def fetchall(self):
            return list(self._rows)

        def fetchone(self):
            return self._rows[0] if self._rows else None

    class _Conn:
        def execute(self, sql, params):
            if "LIMIT 3" in sql:
                return _Result([("2025-12-30", 3.0, 10.0, 9.5, 9.8)])
            if "SELECT close" in sql:
                return _Result([(9.8,)])
            raise AssertionError(f"unexpected sql: {sql}")

    class _Ctx:
        def signals(self, _target_date):
            return {}

    reason = ATTR_MODULE._extract_execution_reason(
        code="301123",
        signal_dates=["2025-12-30"],
        positions_timeline={},
        conn=_Conn(),
        engine=SimpleNamespace(),
        ctx=_Ctx(),
        max_positions=3,
        segment_top_date="2025-12-30",
        buy_signal_audits=[],
        code_trades=[{"buy_date": "2025-12-31", "sell_date": "2025-12-31"}],
        execution_mode="unbounded_opportunity",
    )

    assert reason == "信号存在但见顶后才成交"
