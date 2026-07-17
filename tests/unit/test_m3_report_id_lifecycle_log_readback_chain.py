from __future__ import annotations

from datetime import date, datetime, timezone
from http import HTTPStatus
from pathlib import Path

from apps.api.main import BootstrapApiService
from apps.api.router import BootstrapApiRouter
from neotrade3.decision_engine.contracts import DecisionLifecycleLog
from neotrade3.decision_engine.decision_lifecycle_log import build_decision_lifecycle_logs
from neotrade3.decision_engine.lifecycle_log_store import (
    build_decision_m3_lifecycle_log_record_id,
    materialize_decision_m3_lifecycle_log,
)
from neotrade3.orchestration.report_runner_backtest_source import (
    load_lowfreq_report_backtest_payload,
)


class _FakeEngine:
    def __init__(self) -> None:
        self.MAX_POSITIONS = 5
        self.EXEC_BLOCK_ONLY_ONE_PRICE_LIMIT = False

    def run_backtest(
        self,
        *,
        start_date: date,
        end_date: date,
        initial_capital: float,
        include_trades: bool,
        project_root: Path,
        run_id: str,
        source_run_id: str,
    ) -> dict[str, object]:
        return {"trades": [], "total_return_pct": 0.0}


class _FakeService:
    def __init__(self, *, project_root: Path) -> None:
        self.project_root = project_root
        self._engine = _FakeEngine()

    def _lowfreq_engine_v16(self) -> _FakeEngine:
        return self._engine


def test_report_id_can_be_used_to_readback_m3_lifecycle_log_via_api(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import neotrade3.orchestration.report_runner_backtest_source as backtest_source

    class _FixedDatetime:
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 7, 17, 0, 0, 0, tzinfo=timezone.utc)

    class _FixedUuid:
        hex = "a" * 32

    monkeypatch.setattr(backtest_source, "datetime", _FixedDatetime)
    monkeypatch.setattr(backtest_source.uuid, "uuid4", lambda: _FixedUuid())

    report_payload = load_lowfreq_report_backtest_payload(
        service=_FakeService(project_root=tmp_path),
        backtest_json=None,
        start_date=date(2024, 12, 18),
        end_date=date(2026, 6, 18),
        initial_capital=1_000_000.0,
        max_positions_override=None,
        execution_one_price_limit_only=False,
        generated_at="2026-07-17T00:00:00Z",
    )
    report_id = report_payload["_meta"]["report_id"]

    stock_code = "300001"
    audit_rows = [
        {"code": stock_code, "date": "2026-07-17", "event": "market_exit_confirmed"}
    ]
    lifecycle_payloads = build_decision_lifecycle_logs(
        audit_rows,
        run_id=report_id,
        source_run_id=report_id,
    )
    lifecycle_log = DecisionLifecycleLog.from_dict(lifecycle_payloads[0])

    record_id = build_decision_m3_lifecycle_log_record_id(
        stock_code=stock_code,
        run_id=report_id,
    )
    materialize_decision_m3_lifecycle_log(
        project_root=tmp_path,
        record_id=record_id,
        lifecycle_log=lifecycle_log,
    )

    service = BootstrapApiService(project_root=tmp_path)
    router = BootstrapApiRouter(service)

    status, payload = router.dispatch(f"/api/m3/lifecycle-logs/{record_id}")
    assert status == HTTPStatus.OK
    assert payload["lifecycle_log"]["record_id"] == record_id
    assert payload["lifecycle_log_payload"]["run_id"] == report_id

