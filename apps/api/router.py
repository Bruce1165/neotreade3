"""HTTP router for the NeoTrade3 bootstrap API."""

from __future__ import annotations

import os
from datetime import date
from http import HTTPStatus
from pathlib import Path
from typing import Any, Optional, Union
from urllib.parse import parse_qs, urlparse

from neotrade3.governance.contracts import ValidationResult

from apps.api.shared import ApiBinaryResponse, ApiError


class BootstrapApiRouter:
    """Pure router used by the HTTP handler and tests."""

    def __init__(self, service: Any) -> None:
        self.service = service

    @staticmethod
    def _parse_codes_csv(raw_codes: object) -> list[str]:
        if raw_codes is None:
            return []
        out: list[str] = []
        seen: set[str] = set()
        for part in str(raw_codes).split(","):
            code = part.strip().split(".", 1)[0].strip()
            if not code or code in seen:
                continue
            seen.add(code)
            out.append(code)
        return out

    @staticmethod
    def _parse_positive_limit(raw_limit: object, *, default: int = 100, max_limit: int = 500) -> int:
        if raw_limit is None:
            return int(default)
        try:
            limit = int(str(raw_limit))
        except ValueError as exc:
            raise ApiError(
                status_code=HTTPStatus.BAD_REQUEST,
                code="invalid_limit",
                message="limit must be an integer",
                details={"limit": raw_limit},
            ) from exc
        if limit <= 0:
            raise ApiError(
                status_code=HTTPStatus.BAD_REQUEST,
                code="invalid_limit",
                message="limit must be a positive integer",
                details={"limit": limit},
            )
        return min(limit, int(max_limit))

    def _normalize_path(self, raw_path: str) -> str:
        """Normalize path: support both /api/... and /api/v1/..."""
        parsed = urlparse(raw_path)
        path = parsed.path
        if path.startswith("/api/v1/"):
            return "/api" + path[7:]
        return path

    def dispatch(self, raw_path: str) -> tuple[int, Union[dict[str, Any], ApiBinaryResponse]]:
        parsed = urlparse(raw_path)
        query = parse_qs(parsed.query)

        if parsed.path == "/healthz":
            return HTTPStatus.OK, self.service.health()

        if parsed.path == "/api" or parsed.path == "/api/v1":
            return HTTPStatus.OK, {
                "name": "NeoTrade3 API",
                "version": "1.0.0",
                "description": "量化选股系统 API",
                "error_format": {
                    "structure": '{"error": {"code": "<string>", "message": "<string>", "details": {...}}}',
                    "note": "所有错误响应统一使用此格式，内部异常不会暴露给客户端",
                },
                "endpoints": {
                    "GET": [
                        "/healthz — 健康检查",
                        "/api — API 文档（本页面）",
                        "/api/trading-day?date=YYYY-MM-DD — 交易日查询",
                        "/api/factor-matrix/daily?date=YYYY-MM-DD — 因子矩阵",
                        "/api/sector-prosperity/daily?date=YYYY-MM-DD — 高景气板块评分",
                        "/api/market-phase?date=YYYY-MM-DD — 市场阶段",
                        "/api/resonance-score?codes=xxx&date=YYYY-MM-DD — 共振评分",
                        "/api/sector-rotation?date=YYYY-MM-DD — 板块轮动",
                        "/api/stock-tiering?date=YYYY-MM-DD — 个股分层",
                        "/api/signals?codes=xxx&date=YYYY-MM-DD — 交易信号",
                        "/api/lowfreq/workbench?date=YYYY-MM-DD — 低频自动操盘工作台",
                        "/api/ops-center/summary?date=YYYY-MM-DD — 运维中心摘要",
                        "/api/lowfreq-score/pool?state=跟踪 — 低频交易得分系统股票池",
                        "/api/lowfreq-score/pool/<code> — 低频交易得分系统单股详情",
                        "/api/lowfreq-score/events?code=xxx — 低频交易得分系统事件流",
                        "/api/lowfreq-score/summary?period_type=month — 低频交易得分系统阶段汇总",
                        "/api/screeners — 筛选器列表",
                        "/api/screeners/runs?date=YYYY-MM-DD — 筛选器运行记录",
                        "/api/screeners/config/<id> — 筛选器配置",
                        "/api/labs/runs/<date>/<lab_id> — 实验室结果",
                        "/api/orchestration/runs — 编排运行记录",
                        "/api/governance/final-validations/<source_run_id> — 治理终审选择结果",
                        "/api/governance/final-validations?limit=... — 治理终审选择列表",
                        "/api/governance/final-validations/<source_run_id>/download — 下载终审选择 artifact",
                        "/api/governance/final-validations/<source_run_id>/download-ledger — 下载终审选择 ledger",
                        "/api/data-control — 数据控制状态",
                        "/api/data-control/m1/d1/daily-price-facts?date=YYYY-MM-DD — M1 D1 正式对象投影",
                        "/api/data-control/m1/d7/security-master?codes=xxx — M1 D7 证券主数据投影",
                        "/api/data-control/m1/d7/trading-day-status?date=YYYY-MM-DD — M1 D7 交易日状态投影",
                        "/api/data-control/m1/d8/trading-profiles?date=YYYY-MM-DD — M1 D8 交易画像投影",
                        "/api/issue-center?date=YYYY-MM-DD — 问题中心",
                        "/api/stocks/lookup?code=xxx — 股票查询",
                        "/api/stocks/coverage — 数据覆盖统计",
                        "/api/backtest?codes=xxx&date=YYYY-MM-DD — 回测",
                    ],
                    "POST": [
                        "/api/factor-matrix/daily/run — 运行因子矩阵",
                        "/api/sector-prosperity/daily/run — 运行高景气板块评分",
                        "/api/labs/run — 运行实验室",
                        "/api/orchestration/run — 运行编排",
                        "/api/screeners/run — 运行筛选器",
                        "/api/lowfreq-score/manual/buy-intent — 低频交易得分系统手工买入意图",
                        "/api/lowfreq-score/manual/abandon — 低频交易得分系统手工放弃记录",
                        "/api/screeners/config/<id> — 更新筛选器配置",
                        "/api/data-control/seed-stock-db — 初始化数据库",
                        "/api/data-control/sync-daily-prices — 同步行情",
                        "/api/data/update — authoritative 日线更新",
                    ],
                },
            }

        if parsed.path == "/api/data/status" or parsed.path == "/api/v1/data/status":
            return HTTPStatus.OK, self._data_status(query)

        if parsed.path == "/api/sectors/hot" or parsed.path == "/api/v1/sectors/hot":
            return HTTPStatus.OK, self._hot_sectors(query)

        if (
            parsed.path == "/api/data/sources/assessment"
            or parsed.path == "/api/v1/data/sources/assessment"
        ):
            raw_date = query.get("date", [None])[0]
            raw_lookback = query.get("lookback_days", ["30"])[0]
            try:
                lookback_days = int(str(raw_lookback))
            except ValueError:
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_lookback_days",
                    message="lookback_days must be an integer",
                    details={"lookback_days": raw_lookback},
                )
            return HTTPStatus.OK, self.service.data_sources_assessment_view(
                target_date=str(raw_date).strip() if isinstance(raw_date, str) and raw_date.strip() else None,
                lookback_days=lookback_days,
            )

        if (
            parsed.path == "/api/data/history/gaps"
            or parsed.path == "/api/v1/data/history/gaps"
        ):
            raw_start = query.get("start_date", [None])[0]
            raw_end = query.get("end_date", [None])[0]
            raw_required = query.get("required_history_days", [None])[0]
            required_history_days: Optional[int] = None
            if raw_required is not None:
                try:
                    required_history_days = int(str(raw_required))
                except ValueError:
                    raise ApiError(
                        status_code=HTTPStatus.BAD_REQUEST,
                        code="invalid_required_history_days",
                        message="required_history_days must be an integer",
                        details={"required_history_days": raw_required},
                    )
            return HTTPStatus.OK, self.service.historical_data_gaps_view(
                start_date=str(raw_start).strip() if isinstance(raw_start, str) and raw_start.strip() else None,
                end_date=str(raw_end).strip() if isinstance(raw_end, str) and raw_end.strip() else None,
                required_history_days=required_history_days,
            )

        if (
            parsed.path == "/api/model/validate/quickstart"
            or parsed.path == "/api/v1/model/validate/quickstart"
        ):
            raw_end = query.get("end_date", [None])[0]
            raw_window = query.get("window_trading_days", ["60"])[0]
            try:
                window_trading_days = int(str(raw_window))
            except ValueError:
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_window_trading_days",
                    message="window_trading_days must be an integer",
                    details={"window_trading_days": raw_window},
                )
            return HTTPStatus.OK, self.service.model_validation_quickstart_view(
                end_date=str(raw_end).strip() if isinstance(raw_end, str) and raw_end.strip() else None,
                window_trading_days=window_trading_days,
            )

        if (
            parsed.path == "/api/ashare/midcap/audit"
            or parsed.path == "/api/v1/ashare/midcap/audit"
        ):
            raw_date = query.get("date", [None])[0]
            return HTTPStatus.OK, self.service.ashare_midcap_audit_view(
                target_date=str(raw_date).strip() if isinstance(raw_date, str) and raw_date.strip() else None
            )

        if parsed.path == "/api/lowfreq/rsi/regression":
            return HTTPStatus.OK, self._lowfreq_rsi_regression(query)

        if parsed.path == "/api/concepts/mainline" or parsed.path == "/api/v1/concepts/mainline":
            return HTTPStatus.OK, self._concepts_mainline(query)

        if (
            parsed.path == "/api/concepts/mainline/detail"
            or parsed.path == "/api/v1/concepts/mainline/detail"
        ):
            return HTTPStatus.OK, self._concepts_mainline_detail(query)

        report_path = parsed.path
        if report_path.startswith("/api/v1/"):
            report_path = "/api" + report_path[7:]
        if report_path == "/api/lowfreq/backtest/reports":
            raw_limit = query.get("limit", ["10"])[0]
            try:
                limit = int(str(raw_limit))
            except ValueError:
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_limit",
                    message="limit must be an integer",
                    details={"limit": raw_limit},
                )
            if limit <= 0:
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_limit",
                    message="limit must be a positive integer",
                    details={"limit": limit},
                )
            return HTTPStatus.OK, self.service.lowfreq_backtest_reports_view(limit=limit)

        if report_path == "/api/lowfreq/backtest/window-summary":
            raw_end_date = query.get("end_date", [None])[0]
            if raw_end_date is None:
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="missing_end_date",
                    message="end_date query parameter is required",
                )
            raw_window = query.get("window_trading_days", ["60"])[0]
            try:
                window_trading_days = int(str(raw_window))
            except ValueError:
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_window",
                    message="window_trading_days must be an integer",
                    details={"window_trading_days": raw_window},
                )
            return (
                HTTPStatus.OK,
                self.service.lowfreq_backtest_window_summary_view(
                    end_date=str(raw_end_date), window_trading_days=window_trading_days
                ),
            )

        if report_path == "/api/lowfreq/backtest/status":
            raw_report_id = query.get("report_id", [None])[0]
            if raw_report_id is None:
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="missing_report_id",
                    message="report_id query parameter is required",
                )
            return (
                HTTPStatus.OK,
                self.service.lowfreq_backtest_status_view(report_id=str(raw_report_id)),
            )

        if report_path == "/api/lowfreq/backtest/report-detail":
            raw_report_id = query.get("report_id", [None])[0]
            if raw_report_id is None:
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="missing_report_id",
                    message="report_id query parameter is required",
                )
            return (
                HTTPStatus.OK,
                self.service.lowfreq_backtest_report_detail_view(
                    report_id=str(raw_report_id)
                ),
            )

        if report_path.startswith("/api/lowfreq/backtest/reports/"):
            tail = report_path.split("/api/lowfreq/backtest/reports/", 1)[-1]
            if not tail or "/" in tail:
                raise ApiError(
                    status_code=HTTPStatus.NOT_FOUND,
                    code="not_found",
                    message="report not found",
                    details={"path": parsed.path},
                )
            if tail.endswith(".pdf"):
                report_id = tail[: -len(".pdf")]
                return (
                    HTTPStatus.OK,
                    self.service.lowfreq_backtest_report_download_view(
                        report_id=report_id, format="pdf"
                    ),
                )
            if tail.endswith(".json"):
                report_id = tail[: -len(".json")]
                return (
                    HTTPStatus.OK,
                    self.service.lowfreq_backtest_report_download_view(
                        report_id=report_id, format="json"
                    ),
                )
            raise ApiError(
                status_code=HTTPStatus.NOT_FOUND,
                code="not_found",
                message="report not found",
                details={"path": parsed.path},
            )

        if report_path == "/api/lowfreq/portfolio":
            target_date = query.get("date", [None])[0]
            return HTTPStatus.OK, self.service.lowfreq_portfolio_view(target_date=target_date)

        if report_path == "/api/lowfreq/workbench":
            target_date = query.get("date", [None])[0]
            raw_ensure = query.get("ensure_generated", ["true"])[0]
            ensure_generated = self._parse_bool(raw_ensure)
            return HTTPStatus.OK, self.service.lowfreq_workbench_view(
                target_date=target_date,
                requested_by="api",
                ensure_generated=ensure_generated,
            )

        if report_path == "/api/ops-center/summary":
            target_date = query.get("date", [None])[0]
            return HTTPStatus.OK, self.service.ops_center_summary_view(target_date=target_date)

        if report_path == "/api/lowfreq-score/pool":
            state = query.get("state", [None])[0]
            target_date = query.get("date", [None])[0]
            raw_limit = query.get("limit", ["500"])[0]
            try:
                limit = int(str(raw_limit))
            except ValueError:
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_limit",
                    message="limit must be an integer",
                    details={"limit": raw_limit},
                )
            return HTTPStatus.OK, self.service.lowfreq_score_pool_view(
                state=state,
                limit=limit,
                target_date=target_date,
                requested_by="api",
            )

        if report_path.startswith("/api/lowfreq-score/pool/"):
            code = report_path.removeprefix("/api/lowfreq-score/pool/")
            target_date = query.get("date", [None])[0]
            raw_limit = query.get("event_limit", ["100"])[0]
            try:
                event_limit = int(str(raw_limit))
            except ValueError:
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_event_limit",
                    message="event_limit must be an integer",
                    details={"event_limit": raw_limit},
                )
            return HTTPStatus.OK, self.service.lowfreq_score_pool_item_view(
                code=code,
                event_limit=event_limit,
                target_date=target_date,
                requested_by="api",
            )

        if report_path == "/api/lowfreq-score/events":
            code = query.get("code", [None])[0]
            target_date = query.get("date", [None])[0]
            raw_limit = query.get("limit", ["200"])[0]
            try:
                limit = int(str(raw_limit))
            except ValueError:
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_limit",
                    message="limit must be an integer",
                    details={"limit": raw_limit},
                )
            return HTTPStatus.OK, self.service.lowfreq_score_events_view(
                code=code,
                limit=limit,
                target_date=target_date,
                requested_by="api",
            )

        if report_path == "/api/lowfreq-score/summary":
            period_type = query.get("period_type", [None])[0]
            target_date = query.get("date", [None])[0]
            raw_limit = query.get("limit", ["120"])[0]
            try:
                limit = int(str(raw_limit))
            except ValueError:
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_limit",
                    message="limit must be an integer",
                    details={"limit": raw_limit},
                )
            return HTTPStatus.OK, self.service.lowfreq_score_summary_view(
                period_type=period_type,
                limit=limit,
                target_date=target_date,
                requested_by="api",
            )

        if report_path == "/api/lowfreq/confidence/overview":
            target_date = query.get("date", [None])[0]
            raw_ensure = query.get("ensure_generated", ["true"])[0]
            ensure_generated = self._parse_bool(raw_ensure)
            raw_lookback = query.get("lookback_days", ["7"])[0]
            try:
                lookback_days = int(str(raw_lookback))
            except ValueError:
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_lookback_days",
                    message="lookback_days must be an integer",
                    details={"lookback_days": raw_lookback},
                )
            return HTTPStatus.OK, self.service.lowfreq_confidence_overview_view(
                target_date=target_date,
                requested_by="api",
                ensure_generated=ensure_generated,
                lookback_days=lookback_days,
            )

        if report_path == "/api/lowfreq/confidence/calibration":
            target_date = query.get("date", [None])[0]
            raw_limit = query.get("limit", ["50"])[0]
            try:
                limit = int(str(raw_limit))
            except ValueError:
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_limit",
                    message="limit must be an integer",
                    details={"limit": raw_limit},
                )
            return HTTPStatus.OK, self.service.lowfreq_confidence_calibration_overview_view(
                target_date=target_date,
                requested_by="api",
                limit=limit,
            )

        if report_path == "/api/lowfreq/execution/queue":
            target_date = query.get("date", [None])[0]
            raw_ensure = query.get("ensure_generated", ["true"])[0]
            ensure_generated = self._parse_bool(raw_ensure)
            return HTTPStatus.OK, self.service.lowfreq_execution_queue_view(
                target_date=target_date,
                requested_by="api",
                ensure_generated=ensure_generated,
            )

        if parsed.path == "/api/screeners" or parsed.path == "/api/v1/screeners":
            filter_date = query.get("date", [None])[0]
            if filter_date:
                try:
                    date.fromisoformat(filter_date)
                except ValueError:
                    raise ApiError(
                        status_code=HTTPStatus.BAD_REQUEST,
                        code="invalid_date",
                        message=f"invalid date: {filter_date}",
                        details={"date": filter_date},
                    )
            return HTTPStatus.OK, self.service.screeners_view(target_date=filter_date or None)

        if parsed.path == "/api/screeners/runs":
            filter_date = query.get("date", [None])[0]
            if filter_date:
                try:
                    date.fromisoformat(filter_date)
                except ValueError:
                    raise ApiError(
                        status_code=HTTPStatus.BAD_REQUEST,
                        code="invalid_date",
                        message=f"invalid date: {filter_date}",
                        details={"date": filter_date},
                    )

            filter_screener_id = query.get("screener_id", [None])[0]
            if filter_screener_id is not None:
                filter_screener_id = str(filter_screener_id).strip()
                if not filter_screener_id:
                    raise ApiError(
                        status_code=HTTPStatus.BAD_REQUEST,
                        code="invalid_screener_id",
                        message="screener_id must be a non-empty string",
                        details={"screener_id": filter_screener_id},
                    )

            raw_limit = query.get("limit", [None])[0]
            runs_limit: Optional[int] = None
            if raw_limit is not None:
                try:
                    runs_limit = int(str(raw_limit))
                except ValueError:
                    raise ApiError(
                        status_code=HTTPStatus.BAD_REQUEST,
                        code="invalid_limit",
                        message="limit must be an integer",
                        details={"limit": raw_limit},
                    )
                if runs_limit <= 0:
                    raise ApiError(
                        status_code=HTTPStatus.BAD_REQUEST,
                        code="invalid_limit",
                        message="limit must be a positive integer",
                        details={"limit": runs_limit},
                    )

            return HTTPStatus.OK, self.service.screener_runs_view(
                target_date=filter_date or None,
                screener_id=filter_screener_id or None,
                limit=runs_limit,
            )

        if parsed.path == "/api/screeners/bulk-runs":
            filter_date = query.get("date", [None])[0]
            if filter_date:
                try:
                    date.fromisoformat(filter_date)
                except ValueError:
                    raise ApiError(
                        status_code=HTTPStatus.BAD_REQUEST,
                        code="invalid_date",
                        message=f"invalid date: {filter_date}",
                        details={"date": filter_date},
                    )

            raw_limit = query.get("limit", [None])[0]
            bulk_runs_limit: Optional[int] = None
            if raw_limit is not None:
                try:
                    bulk_runs_limit = int(str(raw_limit))
                except ValueError:
                    raise ApiError(
                        status_code=HTTPStatus.BAD_REQUEST,
                        code="invalid_limit",
                        message="limit must be an integer",
                        details={"limit": raw_limit},
                    )
                if bulk_runs_limit <= 0:
                    raise ApiError(
                        status_code=HTTPStatus.BAD_REQUEST,
                        code="invalid_limit",
                        message="limit must be a positive integer",
                        details={"limit": bulk_runs_limit},
                    )

            return HTTPStatus.OK, self.service.screener_bulk_runs_view(
                target_date=filter_date or None,
                limit=bulk_runs_limit,
            )

        if parsed.path.startswith("/api/screeners/config/") or parsed.path.startswith(
            "/api/v1/screeners/"
        ):
            parts = [part for part in parsed.path.split("/") if part]
            if len(parts) >= 4:
                if parts[0] == "api" and parts[1] == "v1":
                    if parts[2] == "screeners" and len(parts) >= 4:
                        screener_id = parts[3]
                        if len(parts) >= 5 and parts[4] == "config":
                            if not screener_id.strip():
                                raise ApiError(
                                    status_code=HTTPStatus.BAD_REQUEST,
                                    code="invalid_screener_id",
                                    message="screener_id must be a non-empty string",
                                    details={"screener_id": screener_id},
                                )
                            return HTTPStatus.OK, self.service.screener_config_view(
                                screener_id=screener_id
                            )
                        if len(parts) >= 5 and parts[4] == "results":
                            return HTTPStatus.OK, self._get_screener_results(screener_id)
                if (
                    parts[0] == "api"
                    and parts[1] == "screeners"
                    and parts[2] == "config"
                ):
                    screener_id = parts[3]
                    if not screener_id.strip():
                        raise ApiError(
                            status_code=HTTPStatus.BAD_REQUEST,
                            code="invalid_screener_id",
                            message="screener_id must be a non-empty string",
                            details={"screener_id": screener_id},
                        )
                    return HTTPStatus.OK, self.service.screener_config_view(
                        screener_id=screener_id
                    )

        if parsed.path == "/api/trading-day":
            raw_date = query.get("date", [None])[0]
            if raw_date is None:
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_date",
                    message="date query parameter is required",
                )
            raw_date = str(raw_date)
            try:
                date.fromisoformat(raw_date)
            except ValueError:
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_date",
                    message=f"invalid date: {raw_date}",
                    details={"date": raw_date},
                )
            return HTTPStatus.OK, self.service.trading_day_view(target_date=raw_date)

        if parsed.path == "/api/trading-calendar/meta":
            return HTTPStatus.OK, self.service.trading_calendar_meta_view()

        if parsed.path == "/api/factor-matrix/daily":
            raw_date = query.get("date", [date.today().isoformat()])[0]
            raw_date = str(raw_date)
            try:
                date.fromisoformat(raw_date)
            except ValueError:
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_date",
                    message=f"invalid date: {raw_date}",
                    details={"date": raw_date},
                )
            raw_debug = query.get("debug", ["false"])[0]
            debug = str(raw_debug).strip().lower() in {"1", "true", "yes", "y"}
            return HTTPStatus.OK, self.service.factor_matrix_daily_view(
                target_date=raw_date,
                debug=debug,
            )

        if parsed.path == "/api/sector-prosperity/daily":
            raw_date = query.get("date", [date.today().isoformat()])[0]
            raw_date = str(raw_date)
            try:
                date.fromisoformat(raw_date)
            except ValueError:
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_date",
                    message=f"invalid date: {raw_date}",
                    details={"date": raw_date},
                )
            return HTTPStatus.OK, self.service.sector_prosperity_daily_view(
                target_date=raw_date
            )

        if parsed.path.startswith("/api/factor-matrix/daily/"):
            parts = [part for part in parsed.path.split("/") if part]
            if len(parts) not in {4, 5}:
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_path",
                    message="expected /api/factor-matrix/daily/<date>",
                    details={"path": parsed.path},
                )
            _, _, _, raw_date, *rest = parts
            try:
                date.fromisoformat(raw_date)
            except ValueError:
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_date",
                    message=f"invalid date: {raw_date}",
                    details={"date": raw_date},
                )
            if rest:
                if rest[0] != "download":
                    raise ApiError(
                        status_code=HTTPStatus.BAD_REQUEST,
                        code="invalid_path",
                        message="expected /api/factor-matrix/daily/<date>/download",
                        details={"path": parsed.path},
                    )
                return HTTPStatus.OK, self.service.factor_matrix_daily_download_view(
                    target_date=raw_date
                )
            return HTTPStatus.OK, self.service.factor_matrix_daily_detail_view(
                target_date=raw_date
            )

        if parsed.path.startswith("/api/sector-prosperity/daily/"):
            parts = [part for part in parsed.path.split("/") if part]
            if len(parts) not in {4, 5}:
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_path",
                    message="expected /api/sector-prosperity/daily/<date>",
                    details={"path": parsed.path},
                )
            _, _, _, raw_date, *rest = parts
            try:
                date.fromisoformat(raw_date)
            except ValueError:
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_date",
                    message=f"invalid date: {raw_date}",
                    details={"date": raw_date},
                )
            if rest:
                if rest[0] != "download":
                    raise ApiError(
                        status_code=HTTPStatus.BAD_REQUEST,
                        code="invalid_path",
                        message="expected /api/sector-prosperity/daily/<date>/download",
                        details={"path": parsed.path},
                    )
                return HTTPStatus.OK, self.service.sector_prosperity_daily_download_view(
                    target_date=raw_date
                )
            return HTTPStatus.OK, self.service.sector_prosperity_daily_detail_view(
                target_date=raw_date
            )

        if parsed.path == "/api/stocks/lookup":
            raw_codes = query.get("codes", [])
            codes: list[str] = []
            for raw in raw_codes:
                for part in str(raw).split(","):
                    part = part.strip()
                    if part:
                        codes.append(part)
            for raw in query.get("code", []):
                for part in str(raw).split(","):
                    part = part.strip()
                    if part:
                        codes.append(part)
            if not codes:
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_stock_codes",
                    message="codes query parameter is required",
                )
            return HTTPStatus.OK, self.service.stocks_lookup_view(stock_codes=codes)

        if parsed.path == "/api/stocks/coverage":
            target_date = self._parse_target_date(query)
            return HTTPStatus.OK, self.service.stocks_coverage_view(target_date=target_date)

        if parsed.path == "/api/market-intelligence/candidates":
            raw_top_n = query.get("top_n", ["20"])[0]
            try:
                top_n = int(str(raw_top_n).strip())
            except (TypeError, ValueError):
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_top_n",
                    message="top_n must be a positive integer",
                    details={"top_n": raw_top_n},
                )
            return HTTPStatus.OK, self.service.market_intelligence_candidates_view(
                top_n=top_n
            )

        if parsed.path == "/api/market-intelligence/unified-candidates":
            raw_top_n = query.get("top_n", ["20"])[0]
            try:
                top_n = int(str(raw_top_n).strip())
            except (TypeError, ValueError):
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_top_n",
                    message="top_n must be a positive integer",
                    details={"top_n": raw_top_n},
                )
            return HTTPStatus.OK, self.service.market_intelligence_unified_candidates_view(
                top_n=top_n
            )

        if parsed.path == "/api/market-intelligence/recommendations":
            raw_top_n = query.get("top_n", ["20"])[0]
            try:
                top_n = int(str(raw_top_n).strip())
            except (TypeError, ValueError):
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_top_n",
                    message="top_n must be a positive integer",
                    details={"top_n": raw_top_n},
                )
            return HTTPStatus.OK, self.service.market_intelligence_recommendations_view(
                top_n=top_n
            )

        if parsed.path == "/api/market-intelligence/review-board":
            raw_top_n = query.get("top_n", ["20"])[0]
            try:
                top_n = int(str(raw_top_n).strip())
            except (TypeError, ValueError):
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_top_n",
                    message="top_n must be a positive integer",
                    details={"top_n": raw_top_n},
                )
            trade_date = query.get("trade_date", [None])[0]
            if trade_date is not None and not isinstance(trade_date, str):
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_trade_date",
                    message="trade_date must be a string when provided",
                    details={"trade_date": trade_date},
                )
            return HTTPStatus.OK, self.service.market_intelligence_review_board_view(
                top_n=top_n,
                trade_date=trade_date,
            )

        if parsed.path == "/api/market-intelligence/decision-summary":
            raw_top_n = query.get("top_n", ["20"])[0]
            try:
                top_n = int(str(raw_top_n).strip())
            except (TypeError, ValueError):
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_top_n",
                    message="top_n must be a positive integer",
                    details={"top_n": raw_top_n},
                )
            trade_date = query.get("trade_date", [None])[0]
            if trade_date is not None and not isinstance(trade_date, str):
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_trade_date",
                    message="trade_date must be a string when provided",
                    details={"trade_date": trade_date},
                )
            return HTTPStatus.OK, self.service.market_intelligence_decision_summary_view(
                top_n=top_n,
                trade_date=trade_date,
            )

        if parsed.path == "/api/market-intelligence/themes":
            raw_top_n = query.get("top_n", ["20"])[0]
            try:
                top_n = int(str(raw_top_n).strip())
            except (TypeError, ValueError):
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_top_n",
                    message="top_n must be a positive integer",
                    details={"top_n": raw_top_n},
                )
            trade_date = query.get("trade_date", [None])[0]
            if trade_date is not None and not isinstance(trade_date, str):
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_trade_date",
                    message="trade_date must be a string when provided",
                    details={"trade_date": trade_date},
                )
            return HTTPStatus.OK, self.service.market_intelligence_theme_board_view(
                top_n=top_n,
                trade_date=trade_date,
            )

        if parsed.path == "/api/check-stock":
            raw_code = query.get("code", [None])[0]
            if raw_code is None:
                raw_code = query.get("stock_code", [None])[0]
            if raw_code is None:
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_stock_code",
                    message="stock code is required as code=... or stock_code=...",
                )
            stock_code = str(raw_code).strip()
            if not stock_code:
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_stock_code",
                    message="stock code must be a non-empty string",
                    details={"stock_code": raw_code},
                )

            raw_date = query.get("date", [date.today().isoformat()])[0]
            raw_date = str(raw_date)
            try:
                date.fromisoformat(raw_date)
            except ValueError:
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_date",
                    message=f"invalid date: {raw_date}",
                    details={"date": raw_date},
                )
            raw_debug = query.get("debug", ["false"])[0]
            debug = str(raw_debug).strip().lower() in {"1", "true", "yes", "y"}
            raw_screener_ids = query.get("screener_ids", [])
            screener_ids: list[str] = []
            for raw in raw_screener_ids:
                for part in str(raw).split(","):
                    part = part.strip()
                    if part:
                        screener_ids.append(part)
            return HTTPStatus.OK, self.service.check_stock_view(
                target_date=raw_date,
                stock_code=stock_code,
                screener_ids=screener_ids if screener_ids else None,
                debug=debug,
            )

        if parsed.path.startswith("/api/v1/stock/"):
            parts = [part for part in parsed.path.split("/") if part]
            if len(parts) >= 5 and parts[4] == "check":
                code = parts[3]
                if not code or len(code) < 4:
                    raise ApiError(
                        status_code=HTTPStatus.BAD_REQUEST,
                        code="invalid_stock_code",
                        message="stock code is required and must be at least 4 characters",
                        details={"stock_code": code},
                    )
                return HTTPStatus.OK, self._check_stock(code)

        if parsed.path.startswith("/api/screeners/run/"):
            parts = [part for part in parsed.path.split("/") if part]
            if len(parts) != 6 or parts[5] != "export.csv":
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_path",
                    message="expected /api/screeners/run/<screener_id>/<date>/export.csv",
                    details={"path": parsed.path},
                )
            screener_id = parts[3]
            raw_date = parts[4]
            if not screener_id.strip():
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_screener_id",
                    message="screener_id must be a non-empty string",
                    details={"screener_id": screener_id},
                )
            try:
                date.fromisoformat(raw_date)
            except ValueError:
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_date",
                    message=f"invalid date: {raw_date}",
                    details={"date": raw_date},
                )
            return HTTPStatus.OK, self.service.screener_run_export_csv_view(
                screener_id=screener_id,
                target_date=raw_date,
            )

        if parsed.path.startswith("/api/screeners/runs/"):
            parts = [part for part in parsed.path.split("/") if part]
            if len(parts) not in {5, 6}:
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_path",
                    message="expected /api/screeners/runs/<date>/<screener_id>",
                    details={"path": parsed.path},
                )
            _, _, _, raw_date, screener_id, *rest = parts
            try:
                date.fromisoformat(raw_date)
            except ValueError:
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_date",
                    message=f"invalid date: {raw_date}",
                    details={"date": raw_date},
                )
            if not screener_id.strip():
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_screener_id",
                    message="screener_id must be a non-empty string",
                    details={"screener_id": screener_id},
                )
            if rest:
                if rest[0] not in {"download", "download.csv"}:
                    raise ApiError(
                        status_code=HTTPStatus.BAD_REQUEST,
                        code="invalid_path",
                        message="expected /api/screeners/runs/<date>/<screener_id>/download(.csv)",
                        details={"path": parsed.path},
                    )
                if rest[0] == "download.csv":
                    return HTTPStatus.OK, self.service.screener_run_csv_download_view(
                        target_date=raw_date,
                        screener_id=screener_id,
                    )
                return HTTPStatus.OK, self.service.screener_run_artifact_download_view(
                    target_date=raw_date,
                    screener_id=screener_id,
                )
            return HTTPStatus.OK, self.service.screener_run_detail_view(
                target_date=raw_date,
                screener_id=screener_id,
            )

        if parsed.path.startswith("/api/screeners/bulk-runs/"):
            parts = [part for part in parsed.path.split("/") if part]
            if len(parts) not in {4, 5}:
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_path",
                    message="expected /api/screeners/bulk-runs/<date>",
                    details={"path": parsed.path},
                )
            _, _, raw_date, *rest = parts[1:]
            try:
                date.fromisoformat(raw_date)
            except ValueError:
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_date",
                    message=f"invalid date: {raw_date}",
                    details={"date": raw_date},
                )
            if rest:
                if rest[0] != "download":
                    raise ApiError(
                        status_code=HTTPStatus.BAD_REQUEST,
                        code="invalid_path",
                        message="expected /api/screeners/bulk-runs/<date>/download",
                        details={"path": parsed.path},
                    )
                return (
                    HTTPStatus.OK,
                    self.service.screener_bulk_run_artifact_download_view(
                        target_date=raw_date
                    ),
                )
            return HTTPStatus.OK, self.service.screener_bulk_run_detail_view(
                target_date=raw_date
            )

        target_date = self._parse_target_date(query)
        raw_publish = query.get("publish_succeeded", [None])[0]
        if raw_publish is None:
            publish_succeeded = False
        else:
            publish_succeeded = self._parse_bool(raw_publish)
        write_outputs = self._parse_bool(query.get("write_outputs", ["false"])[0])

        if parsed.path == "/api/bootstrap-summary":
            return HTTPStatus.OK, self.service.bootstrap_summary(
                target_date=target_date,
                publish_succeeded=publish_succeeded,
            )

        if parsed.path == "/api/bootstrap-snapshot":
            return HTTPStatus.OK, self.service.build_snapshot(
                target_date=target_date,
                publish_succeeded=publish_succeeded,
                write_outputs=write_outputs,
            )

        if parsed.path == "/api/data-control":
            return HTTPStatus.OK, self.service.data_control_view(
                target_date=target_date,
                publish_succeeded=publish_succeeded,
            )

        if parsed.path == "/api/data-control/m1/d1/daily-price-facts":
            raw_date = query.get("date", [None])[0]
            if raw_date is None:
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_date",
                    message="date query parameter is required",
                )
            raw_date = str(raw_date).strip()
            try:
                date.fromisoformat(raw_date)
            except ValueError:
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_date",
                    message=f"invalid date: {raw_date}",
                    details={"date": raw_date},
                )
            limit = self._parse_positive_limit(query.get("limit", [None])[0], default=100)
            codes = self._parse_codes_csv(query.get("codes", [None])[0])
            return HTTPStatus.OK, self.service.m1_d1_daily_price_facts_view(
                target_date=raw_date,
                stock_codes=codes or None,
                limit=limit,
            )

        if parsed.path == "/api/data-control/m1/d7/security-master":
            limit = self._parse_positive_limit(query.get("limit", [None])[0], default=100)
            codes = self._parse_codes_csv(query.get("codes", [None])[0])
            return HTTPStatus.OK, self.service.m1_d7_security_master_view(
                stock_codes=codes or None,
                limit=limit,
            )

        if parsed.path == "/api/data-control/m1/d7/trading-day-status":
            raw_date = query.get("date", [None])[0]
            if raw_date is None:
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_date",
                    message="date query parameter is required",
                )
            raw_date = str(raw_date).strip()
            try:
                date.fromisoformat(raw_date)
            except ValueError:
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_date",
                    message=f"invalid date: {raw_date}",
                    details={"date": raw_date},
                )
            return HTTPStatus.OK, self.service.m1_d7_trading_day_status_view(
                target_date=raw_date
            )

        if parsed.path == "/api/data-control/m1/d8/trading-profiles":
            raw_date = query.get("date", [None])[0]
            if raw_date is None:
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_date",
                    message="date query parameter is required",
                )
            raw_date = str(raw_date).strip()
            try:
                date.fromisoformat(raw_date)
            except ValueError:
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_date",
                    message=f"invalid date: {raw_date}",
                    details={"date": raw_date},
                )
            limit = self._parse_positive_limit(query.get("limit", [None])[0], default=100)
            codes = self._parse_codes_csv(query.get("codes", [None])[0])
            return HTTPStatus.OK, self.service.m1_d8_trading_profiles_view(
                target_date=raw_date,
                stock_codes=codes or None,
                limit=limit,
            )

        if parsed.path == "/api/data-control/runs":
            filter_date = query.get("date", [None])[0]
            if filter_date is not None:
                filter_date = str(filter_date)
                try:
                    date.fromisoformat(filter_date)
                except ValueError:
                    raise ApiError(
                        status_code=HTTPStatus.BAD_REQUEST,
                        code="invalid_date",
                        message=f"invalid date: {filter_date}",
                        details={"date": filter_date},
                    )

            raw_limit = query.get("limit", [None])[0]
            data_control_runs_limit: Optional[int] = None
            if raw_limit is not None:
                try:
                    data_control_runs_limit = int(str(raw_limit))
                except ValueError:
                    raise ApiError(
                        status_code=HTTPStatus.BAD_REQUEST,
                        code="invalid_limit",
                        message="limit must be an integer",
                        details={"limit": raw_limit},
                    )
                if data_control_runs_limit <= 0:
                    raise ApiError(
                        status_code=HTTPStatus.BAD_REQUEST,
                        code="invalid_limit",
                        message="limit must be a positive integer",
                        details={"limit": data_control_runs_limit},
                    )
            return HTTPStatus.OK, self.service.data_control_runs_view(
                target_date=filter_date or None, limit=data_control_runs_limit
            )

        if parsed.path.startswith("/api/data-control/runs/"):
            parts = [part for part in parsed.path.split("/") if part]
            if len(parts) not in {5, 6}:
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_path",
                    message="expected /api/data-control/runs/<date>/<stage>",
                    details={"path": parsed.path},
                )
            _, _, _, raw_date, stage, *rest = parts
            try:
                date.fromisoformat(raw_date)
            except ValueError:
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_date",
                    message=f"invalid date: {raw_date}",
                    details={"date": raw_date},
                )
            if rest:
                if rest[0] != "download":
                    raise ApiError(
                        status_code=HTTPStatus.BAD_REQUEST,
                        code="invalid_path",
                        message="expected /api/data-control/runs/<date>/<stage>/download",
                        details={"path": parsed.path},
                    )
                return HTTPStatus.OK, self.service.data_control_run_download_view(
                    target_date=raw_date, stage=stage
                )
            return HTTPStatus.OK, self.service.data_control_run_detail_view(
                target_date=raw_date, stage=stage
            )

        if parsed.path == "/api/orchestration/runs":
            filter_date = query.get("date", [None])[0]
            if filter_date is not None:
                filter_date = str(filter_date)
                try:
                    date.fromisoformat(filter_date)
                except ValueError:
                    raise ApiError(
                        status_code=HTTPStatus.BAD_REQUEST,
                        code="invalid_date",
                        message=f"invalid date: {filter_date}",
                        details={"date": filter_date},
                    )

            raw_limit = query.get("limit", [None])[0]
            orchestration_runs_limit: Optional[int] = None
            if raw_limit is not None:
                try:
                    orchestration_runs_limit = int(str(raw_limit))
                except ValueError:
                    raise ApiError(
                        status_code=HTTPStatus.BAD_REQUEST,
                        code="invalid_limit",
                        message="limit must be an integer",
                        details={"limit": raw_limit},
                    )
                if orchestration_runs_limit <= 0:
                    raise ApiError(
                        status_code=HTTPStatus.BAD_REQUEST,
                        code="invalid_limit",
                        message="limit must be a positive integer",
                        details={"limit": orchestration_runs_limit},
                    )

            return HTTPStatus.OK, self.service.orchestration_runs_view(
                target_date=filter_date or None,
                limit=orchestration_runs_limit,
            )

        if parsed.path.startswith("/api/orchestration/runs/"):
            parts = [part for part in parsed.path.split("/") if part]
            if len(parts) not in {4, 5}:
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_path",
                    message="expected /api/orchestration/runs/<date>",
                    details={"path": parsed.path},
                )
            _, _, raw_date, *rest = parts[1:]
            try:
                date.fromisoformat(raw_date)
            except ValueError:
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_date",
                    message=f"invalid date: {raw_date}",
                    details={"date": raw_date},
                )
            if rest:
                if rest[0] != "download":
                    raise ApiError(
                        status_code=HTTPStatus.BAD_REQUEST,
                        code="invalid_path",
                        message="expected /api/orchestration/runs/<date>/download",
                        details={"path": parsed.path},
                    )
                return HTTPStatus.OK, self.service.orchestration_run_download_view(
                    target_date=raw_date
                )
            return HTTPStatus.OK, self.service.orchestration_run_detail_view(
                target_date=raw_date
            )

        if parsed.path == "/api/orchestration":
            return HTTPStatus.OK, self.service.orchestration_view(
                target_date=target_date,
                publish_succeeded=publish_succeeded,
            )

        if (
            parsed.path == "/api/governance/final-validations"
            or parsed.path == "/api/v1/governance/final-validations"
        ):
            raw_limit = query.get("limit", [None])[0]
            limit = self._parse_positive_limit(raw_limit, default=20, max_limit=200)
            return HTTPStatus.OK, self.service.governance_final_validations_view(
                limit=limit
            )

        if parsed.path.startswith("/api/governance/final-validations/") or parsed.path.startswith(
            "/api/v1/governance/final-validations/"
        ):
            parts = [part for part in parsed.path.split("/") if part]
            if len(parts) not in {4, 5}:
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_path",
                    message="expected /api/governance/final-validations/<source_run_id>[/download|/download-ledger]",
                    details={"path": parsed.path},
                )
            _, _, _, source_run_id, *rest = parts
            if not source_run_id.strip():
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_source_run_id",
                    message="source_run_id must be a non-empty string",
                    details={"source_run_id": source_run_id},
                )
            if rest:
                if rest[0] == "download-ledger":
                    return HTTPStatus.OK, self.service.governance_final_validation_ledger_download_view(
                        source_run_id=source_run_id
                    )
                if rest[0] != "download":
                    raise ApiError(
                        status_code=HTTPStatus.BAD_REQUEST,
                        code="invalid_path",
                        message="expected /api/governance/final-validations/<source_run_id>/(download|download-ledger)",
                        details={"path": parsed.path},
                    )
                return HTTPStatus.OK, self.service.governance_final_validation_download_view(
                    source_run_id=source_run_id
                )
            return HTTPStatus.OK, self.service.governance_final_validation_view(
                source_run_id=source_run_id
            )

        if parsed.path == "/api/labs":
            return HTTPStatus.OK, self.service.labs_view()

        if parsed.path == "/api/labs/runs":
            filter_date = query.get("date", [None])[0]
            if filter_date is not None:
                filter_date = str(filter_date)
                try:
                    date.fromisoformat(filter_date)
                except ValueError:
                    raise ApiError(
                        status_code=HTTPStatus.BAD_REQUEST,
                        code="invalid_date",
                        message=f"invalid date: {filter_date}",
                        details={"date": filter_date},
                    )

            raw_limit = query.get("limit", [None])[0]
            lab_runs_limit: Optional[int] = None
            if raw_limit is not None:
                try:
                    lab_runs_limit = int(str(raw_limit))
                except ValueError:
                    raise ApiError(
                        status_code=HTTPStatus.BAD_REQUEST,
                        code="invalid_limit",
                        message="limit must be an integer",
                        details={"limit": raw_limit},
                    )
                if lab_runs_limit <= 0:
                    raise ApiError(
                        status_code=HTTPStatus.BAD_REQUEST,
                        code="invalid_limit",
                        message="limit must be a positive integer",
                        details={"limit": lab_runs_limit},
                    )

            return HTTPStatus.OK, self.service.lab_runs_view(
                target_date=filter_date or None, limit=lab_runs_limit
            )

        if parsed.path.startswith("/api/labs/runs/"):
            parts = [part for part in parsed.path.split("/") if part]
            if len(parts) not in {5, 6}:
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_path",
                    message="expected /api/labs/runs/<date>/<lab_id>",
                    details={"path": parsed.path},
                )
            _, _, _, raw_date, lab_id, *rest = parts
            try:
                date.fromisoformat(raw_date)
            except ValueError:
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_date",
                    message=f"invalid date: {raw_date}",
                    details={"date": raw_date},
                )
            if not lab_id.strip():
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_lab_id",
                    message="lab_id must be a non-empty string",
                    details={"lab_id": lab_id},
                )
            if rest:
                if rest[0] != "download":
                    raise ApiError(
                        status_code=HTTPStatus.BAD_REQUEST,
                        code="invalid_path",
                        message="expected /api/labs/runs/<date>/<lab_id>/download",
                        details={"path": parsed.path},
                    )
                return HTTPStatus.OK, self.service.lab_run_download_view(
                    target_date=raw_date, lab_id=lab_id
                )
            return HTTPStatus.OK, self.service.lab_run_detail_view(
                target_date=raw_date, lab_id=lab_id
            )

        if parsed.path == "/api/config-contracts":
            return HTTPStatus.OK, self.service.config_contracts_view()

        if parsed.path == "/api/migration/feature-manual":
            return HTTPStatus.OK, self.service.migration_feature_manual_view()

        if parsed.path == "/api/migration/feature-mapping":
            domain = query.get("domain", ["strategy_and_lab"])[0]
            filter_status = query.get("status", [None])[0]
            filter_strategy = query.get("strategy", [None])[0]
            return HTTPStatus.OK, self.service.migration_feature_mapping_view(
                str(domain),
                filter_status=str(filter_status) if filter_status else None,
                filter_strategy=str(filter_strategy) if filter_strategy else None,
            )

        if parsed.path == "/api/migration/feature-mapping-coverage":
            domain = query.get("domain", ["strategy_and_lab"])[0]
            return HTTPStatus.OK, self.service.migration_feature_mapping_coverage_view(
                str(domain)
            )

        if parsed.path == "/api/pools":
            return HTTPStatus.OK, self.service.pools_view(
                target_date=target_date,
                publish_succeeded=publish_succeeded,
            )

        if parsed.path.startswith("/api/pools/"):
            parts = [part for part in parsed.path.split("/") if part]
            if len(parts) not in {3, 4}:
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_path",
                    message="expected /api/pools/<pool_id> or /api/pools/<pool_id>/download.csv",
                    details={"path": parsed.path},
                )
            _, _, pool_id, *rest = parts
            if not pool_id.strip():
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_pool_id",
                    message="pool_id must be a non-empty string",
                    details={"pool_id": pool_id},
                )
            if rest:
                if rest[0] != "download.csv":
                    raise ApiError(
                        status_code=HTTPStatus.BAD_REQUEST,
                        code="invalid_path",
                        message="expected /api/pools/<pool_id>/download.csv",
                        details={"path": parsed.path},
                    )
                return HTTPStatus.OK, self.service.pool_csv_download_view(
                    target_date=target_date, pool_id=pool_id
                )
            return HTTPStatus.OK, self.service.pool_detail_view(
                target_date=target_date,
                pool_id=pool_id,
                publish_succeeded=publish_succeeded,
            )

        if parsed.path == "/api/issue-center":
            return HTTPStatus.OK, self.service.issue_center_view(
                target_date=target_date,
                publish_succeeded=publish_succeeded,
            )

        if parsed.path == "/api/learning":
            return HTTPStatus.OK, self.service.learning_view(
                target_date=target_date,
                publish_succeeded=publish_succeeded,
            )

        if parsed.path == "/api/market-phase":
            lookback_days = int(query.get("lookback_days", ["60"])[0])
            return HTTPStatus.OK, self.service.market_phase_view(
                target_date=target_date,
                lookback_days=lookback_days,
            )

        if parsed.path == "/api/resonance-score":
            codes_param = query.get("codes", [])
            if not codes_param:
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="missing_codes",
                    message="codes parameter is required (comma-separated)",
                )
            codes = [c.strip() for c in codes_param[0].split(",") if c.strip()]
            return HTTPStatus.OK, self.service.resonance_score_view(
                target_date=target_date,
                codes=codes,
            )

        if parsed.path == "/api/sector-rotation":
            lookback_days = int(query.get("lookback_days", ["20"])[0])
            return HTTPStatus.OK, self.service.sector_rotation_view(
                target_date=target_date,
                lookback_days=lookback_days,
            )

        if parsed.path == "/api/stock-tiering":
            lookback_days = int(query.get("lookback_days", ["20"])[0])
            codes_param = query.get("codes", [])
            codes = None
            if codes_param:
                codes = [c.strip() for c in codes_param[0].split(",") if c.strip()]
            return HTTPStatus.OK, self.service.stock_tiering_view(
                target_date=target_date,
                codes=codes,
                lookback_days=lookback_days,
            )

        if parsed.path == "/api/signals":
            min_grade = query.get("min_grade", ["C"])[0]
            codes_param = query.get("codes", [])
            codes = None
            if codes_param:
                codes = [c.strip() for c in codes_param[0].split(",") if c.strip()]
            return HTTPStatus.OK, self.service.signals_view(
                target_date=target_date,
                codes=codes,
                min_grade=min_grade,
            )

        if parsed.path == "/api/backtest":
            start_date_str = query.get("start_date", [None])[0]
            end_date_str = query.get("end_date", [None])[0]
            min_grade = query.get("min_grade", ["C"])[0]

            if not start_date_str or not end_date_str:
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="missing_dates",
                    message="start_date and end_date are required",
                )

            try:
                from datetime import datetime

                start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
                end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
            except ValueError:
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_date_format",
                    message="dates must be in YYYY-MM-DD format",
                )

            codes_param = query.get("codes", [])
            codes = None
            if codes_param:
                codes = [c.strip() for c in codes_param[0].split(",") if c.strip()]

            return HTTPStatus.OK, self.service.backtest_view(
                start_date=start_date,
                end_date=end_date,
                min_grade=min_grade,
                codes=codes,
            )

        if parsed.path == "/api/evolution":
            start_date_str = query.get("start_date", [None])[0]
            end_date_str = query.get("end_date", [None])[0]
            market_phase = query.get("market_phase", ["bull"])[0]

            if not start_date_str or not end_date_str:
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="missing_dates",
                    message="start_date and end_date are required",
                )

            try:
                from datetime import datetime

                start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
                end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
            except ValueError:
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_date_format",
                    message="dates must be in YYYY-MM-DD format",
                )

            return HTTPStatus.OK, self.service.evolution_view(
                start_date=start_date,
                end_date=end_date,
                market_phase=market_phase,
            )

        if parsed.path == "/api/prediction/signals":
            return HTTPStatus.OK, self.service.prediction_signals_view(query)

        if parsed.path == "/api/prediction/backtest":
            return HTTPStatus.OK, self.service.prediction_backtest_view(query)

        if parsed.path == "/api/sector-rotation/signals":
            return HTTPStatus.OK, self.service.sector_rotation_signals_view(query)

        if parsed.path == "/api/sector-rotation/ranking":
            return HTTPStatus.OK, self.service.sector_rotation_ranking_view(query)

        raise ApiError(
            status_code=HTTPStatus.NOT_FOUND,
            code="not_found",
            message=f"unsupported path: {parsed.path}",
            details={"path": parsed.path},
        )

    def dispatch_post(self, raw_path: str, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        parsed = urlparse(raw_path)
        path = parsed.path

        if path.startswith("/api/v1/"):
            path = "/api" + path[7:]

        if path == "/api/data/update":
            raw_date = body.get("date") or body.get("target_date") or date.today().isoformat()
            if not isinstance(raw_date, str) or not raw_date.strip():
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_date",
                    message="date must be a string in YYYY-MM-DD format",
                    details={"date": raw_date},
                )
            try:
                date.fromisoformat(raw_date)
            except ValueError:
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_date",
                    message=f"invalid date: {raw_date}",
                    details={"date": raw_date},
                )

            requested_by = body.get("requested_by", "api.data.update")
            if not isinstance(requested_by, str) or not requested_by.strip():
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_requested_by",
                    message="requested_by must be a non-empty string",
                    details={"requested_by": requested_by},
                )

            dry_run = body.get("dry_run", False)
            if not isinstance(dry_run, bool):
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_dry_run",
                    message="dry_run must be a boolean",
                    details={"dry_run": dry_run},
                )

            authoritative_result = self.service.update_daily_prices_authoritative_view(
                target_date=raw_date,
                requested_by=requested_by.strip(),
                dry_run=dry_run,
            )

            v2_sync: Optional[dict[str, Any]] = None
            if not dry_run:
                raw_v2_path = os.environ.get("NEOTRADE3_STOCK_DB_V2_PATH")
                v2_db_path = (
                    Path(raw_v2_path).expanduser()
                    if isinstance(raw_v2_path, str) and raw_v2_path.strip()
                    else None
                )
                if v2_db_path is not None and v2_db_path.exists() and v2_db_path.is_file():
                    try:
                        import sqlite3

                        with sqlite3.connect(str(self.service.project_root / "var/db/stock_data.db")) as conn:
                            row = conn.execute(
                                "SELECT COUNT(1) FROM daily_prices WHERE trade_date = ?",
                                (raw_date,),
                            ).fetchone()
                        missing_in_v3 = int(row[0] or 0) == 0 if row else True
                    except Exception:
                        missing_in_v3 = False
                    if missing_in_v3:
                        v2_sync = self.service.sync_daily_prices_view(
                            source_db_path=str(v2_db_path),
                            requested_by=requested_by.strip(),
                            dry_run=False,
                            rebuild_trading_calendar=True,
                            target_date=raw_date,
                        )

            return HTTPStatus.OK, {
                "_meta": {"status": "ok"},
                "target_date": raw_date,
                "authoritative_update": authoritative_result,
                "v2_sync": v2_sync,
            }

        if path == "/api/model/run":
            raw_date = body.get("date")
            if raw_date is not None and not isinstance(raw_date, str):
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_date",
                    message="date must be a string in YYYY-MM-DD format",
                    details={"date": raw_date},
                )
            if isinstance(raw_date, str) and raw_date.strip():
                try:
                    date.fromisoformat(raw_date)
                except ValueError:
                    raise ApiError(
                        status_code=HTTPStatus.BAD_REQUEST,
                        code="invalid_date",
                        message=f"invalid date: {raw_date}",
                        details={"date": raw_date},
                    )
                target_date = raw_date.strip()
            else:
                target_date = None

            requested_by = body.get("requested_by", "api")
            if not isinstance(requested_by, str) or not requested_by.strip():
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_requested_by",
                    message="requested_by must be a non-empty string",
                    details={"requested_by": requested_by},
                )

            return HTTPStatus.OK, self.service.lowfreq_sim_run_view(
                target_date=target_date,
                requested_by=requested_by.strip(),
            )

        if path == "/api/screeners/run-all":
            raw_date = body.get("date")
            if raw_date is not None and not isinstance(raw_date, str):
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_date",
                    message="date must be a string in YYYY-MM-DD format",
                    details={"date": raw_date},
                )
            if isinstance(raw_date, str) and raw_date.strip():
                try:
                    date.fromisoformat(raw_date)
                except ValueError:
                    raise ApiError(
                        status_code=HTTPStatus.BAD_REQUEST,
                        code="invalid_date",
                        message=f"invalid date: {raw_date}",
                        details={"date": raw_date},
                    )
                target_date = raw_date.strip()
            else:
                target_date = None

            bulk = self.service.screeners_bulk_run_view(
                target_date=target_date,
                enabled_only=True,
                requested_by=str(body.get("requested_by", "api")).strip() or "api",
                dry_run=False,
            )
            total_hits = 0
            if isinstance(bulk, dict):
                bulk_run = bulk.get("bulk_run")
                if isinstance(bulk_run, dict):
                    run_results = bulk_run.get("run_results")
                    if isinstance(run_results, list):
                        for entry in run_results:
                            if isinstance(entry, dict):
                                total_hits += int(entry.get("result_count") or 0)

            return HTTPStatus.OK, {
                "_meta": {"status": "ok"},
                "bulk": bulk,
                "total_hits": total_hits,
            }

        if path == "/api/lowfreq/backtest/run":
            requested_by = body.get("requested_by", "api")
            if not isinstance(requested_by, str) or not requested_by.strip():
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_requested_by",
                    message="requested_by must be a non-empty string",
                    details={"requested_by": requested_by},
                )

            async_run = body.get("async_run", True)
            if not isinstance(async_run, bool):
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_async_run",
                    message="async_run must be a boolean when provided",
                    details={"async_run": async_run},
                )

            start_date = body.get("start_date")
            end_date = body.get("end_date")
            if start_date is not None and not isinstance(start_date, str):
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_start_date",
                    message="start_date must be a string in YYYY-MM-DD format when provided",
                    details={"start_date": start_date},
                )
            if end_date is not None and not isinstance(end_date, str):
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_end_date",
                    message="end_date must be a string in YYYY-MM-DD format when provided",
                    details={"end_date": end_date},
                )
            if isinstance(start_date, str) and start_date.strip():
                try:
                    date.fromisoformat(start_date)
                except ValueError:
                    raise ApiError(
                        status_code=HTTPStatus.BAD_REQUEST,
                        code="invalid_start_date",
                        message=f"invalid start_date: {start_date}",
                        details={"start_date": start_date},
                    )
            else:
                start_date = None
            if isinstance(end_date, str) and end_date.strip():
                try:
                    date.fromisoformat(end_date)
                except ValueError:
                    raise ApiError(
                        status_code=HTTPStatus.BAD_REQUEST,
                        code="invalid_end_date",
                        message=f"invalid end_date: {end_date}",
                        details={"end_date": end_date},
                    )
            else:
                end_date = None

            payload = self.service.lowfreq_backtest_run_view(
                start_date=start_date,
                end_date=end_date,
                async_run=async_run,
                requested_by=requested_by.strip(),
            )
            if isinstance(payload, dict) and payload.get("_meta", {}).get("status") == "accepted":
                return HTTPStatus.ACCEPTED, payload
            return HTTPStatus.OK, payload

        if path in {"/api/lowfreq/manual/buy-intent", "/api/lowfreq-score/manual/buy-intent"}:
            requested_by = body.get("requested_by", "api")
            if not isinstance(requested_by, str) or not requested_by.strip():
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_requested_by",
                    message="requested_by must be a non-empty string",
                    details={"requested_by": requested_by},
                )

            code = body.get("code")
            if not isinstance(code, str) or not code.strip():
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_code",
                    message="code must be a non-empty string",
                    details={"code": code},
                )

            requested_date = body.get("requested_date")
            if not isinstance(requested_date, str) or not requested_date.strip():
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_requested_date",
                    message="requested_date must be a string in YYYY-MM-DD format",
                    details={"requested_date": requested_date},
                )
            try:
                date.fromisoformat(requested_date)
            except ValueError:
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_requested_date",
                    message=f"invalid requested_date: {requested_date}",
                    details={"requested_date": requested_date},
                )

            name = body.get("name")
            if name is not None and not isinstance(name, str):
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_name",
                    message="name must be a string when provided",
                    details={"name": name},
                )
            sector = body.get("sector")
            if sector is not None and not isinstance(sector, str):
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_sector",
                    message="sector must be a string when provided",
                    details={"sector": sector},
                )
            role = body.get("role")
            if role is not None and not isinstance(role, str):
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_role",
                    message="role must be a string when provided",
                    details={"role": role},
                )
            buy_score = body.get("buy_score")
            if buy_score is not None and not isinstance(buy_score, (int, float)):
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_buy_score",
                    message="buy_score must be a number when provided",
                    details={"buy_score": buy_score},
                )

            service_method = (
                self.service.lowfreq_score_manual_buy_intent_view
                if path == "/api/lowfreq-score/manual/buy-intent"
                else self.service.lowfreq_manual_buy_intent_view
            )
            return HTTPStatus.OK, service_method(
                code=code.strip(),
                requested_date=requested_date.strip(),
                name=(str(name) if isinstance(name, str) else ""),
                sector=(str(sector) if isinstance(sector, str) else ""),
                role=(str(role) if isinstance(role, str) else ""),
                buy_score=float(buy_score or 0.0),
                requested_by=requested_by.strip(),
            )

        if path in {"/api/lowfreq/manual/abandon", "/api/lowfreq-score/manual/abandon"}:
            requested_by = body.get("requested_by", "api")
            if not isinstance(requested_by, str) or not requested_by.strip():
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_requested_by",
                    message="requested_by must be a non-empty string",
                    details={"requested_by": requested_by},
                )

            code = body.get("code")
            if not isinstance(code, str) or not code.strip():
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_code",
                    message="code must be a non-empty string",
                    details={"code": code},
                )

            requested_date = body.get("requested_date")
            if not isinstance(requested_date, str) or not requested_date.strip():
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_requested_date",
                    message="requested_date must be a string in YYYY-MM-DD format",
                    details={"requested_date": requested_date},
                )
            try:
                date.fromisoformat(requested_date)
            except ValueError:
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_requested_date",
                    message=f"invalid requested_date: {requested_date}",
                    details={"requested_date": requested_date},
                )

            service_method = (
                self.service.lowfreq_score_manual_abandon_view
                if path == "/api/lowfreq-score/manual/abandon"
                else self.service.lowfreq_manual_abandon_view
            )
            return HTTPStatus.OK, service_method(
                code=code.strip(),
                requested_date=requested_date.strip(),
                requested_by=requested_by.strip(),
            )

        if path == "/api/lowfreq/settings/autopilot":
            requested_by = body.get("requested_by", "api")
            if not isinstance(requested_by, str) or not requested_by.strip():
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_requested_by",
                    message="requested_by must be a non-empty string",
                    details={"requested_by": requested_by},
                )
            enabled = body.get("enabled")
            if not isinstance(enabled, bool):
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_enabled",
                    message="enabled must be a boolean",
                    details={"enabled": enabled},
                )
            return HTTPStatus.OK, self.service.lowfreq_settings_set_autopilot_view(
                enabled=enabled,
                requested_by=requested_by.strip(),
            )

        if path == "/api/lowfreq/execution/processed":
            requested_by = body.get("requested_by", "api")
            if not isinstance(requested_by, str) or not requested_by.strip():
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_requested_by",
                    message="requested_by must be a non-empty string",
                    details={"requested_by": requested_by},
                )
            intent_id = body.get("intent_id")
            if not isinstance(intent_id, str) or not intent_id.strip():
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_intent_id",
                    message="intent_id must be a non-empty string",
                    details={"intent_id": intent_id},
                )
            return HTTPStatus.OK, self.service.lowfreq_execution_intent_processed_view(
                intent_id=intent_id.strip(),
                requested_by=requested_by.strip(),
            )

        if path == "/api/lowfreq/execution/abandon":
            requested_by = body.get("requested_by", "api")
            if not isinstance(requested_by, str) or not requested_by.strip():
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_requested_by",
                    message="requested_by must be a non-empty string",
                    details={"requested_by": requested_by},
                )
            intent_id = body.get("intent_id")
            if not isinstance(intent_id, str) or not intent_id.strip():
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_intent_id",
                    message="intent_id must be a non-empty string",
                    details={"intent_id": intent_id},
                )
            reason = body.get("reason", "abandoned")
            if reason is not None and not isinstance(reason, str):
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_reason",
                    message="reason must be a string when provided",
                    details={"reason": reason},
                )
            return HTTPStatus.OK, self.service.lowfreq_execution_intent_abandon_view(
                intent_id=intent_id.strip(),
                reason=str(reason or "abandoned"),
                requested_by=requested_by.strip(),
            )

        if path == "/api/lowfreq/confidence/run":
            requested_by = body.get("requested_by", "api")
            if not isinstance(requested_by, str) or not requested_by.strip():
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_requested_by",
                    message="requested_by must be a non-empty string",
                    details={"requested_by": requested_by},
                )
            raw_date = body.get("date")
            if raw_date is not None and not isinstance(raw_date, str):
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_date",
                    message="date must be a string in YYYY-MM-DD format when provided",
                    details={"date": raw_date},
                )
            if isinstance(raw_date, str) and raw_date.strip():
                try:
                    date.fromisoformat(raw_date.strip())
                except ValueError:
                    raise ApiError(
                        status_code=HTTPStatus.BAD_REQUEST,
                        code="invalid_date",
                        message=f"invalid date: {raw_date}",
                        details={"date": raw_date},
                    )
                target_date = raw_date.strip()
            else:
                target_date = None

            max_label_updates = body.get("max_label_updates", 200)
            if not isinstance(max_label_updates, int):
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_max_label_updates",
                    message="max_label_updates must be an integer",
                    details={"max_label_updates": max_label_updates},
                )
            return HTTPStatus.OK, self.service.lowfreq_confidence_daily_run_view(
                target_date=target_date,
                requested_by=requested_by.strip(),
                max_label_updates=int(max_label_updates),
            )

        if path == "/api/lowfreq/rsi/weekly-record":
            requested_by = body.get("requested_by", "api")
            if not isinstance(requested_by, str) or not requested_by.strip():
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_requested_by",
                    message="requested_by must be a non-empty string",
                    details={"requested_by": requested_by},
                )
            raw_date = body.get("date")
            if raw_date is not None and not isinstance(raw_date, str):
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_date",
                    message="date must be a string in YYYY-MM-DD format when provided",
                    details={"date": raw_date},
                )
            target_date = raw_date.strip() if isinstance(raw_date, str) and raw_date.strip() else None

            weeks = body.get("weeks", 12)
            if not isinstance(weeks, int):
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_weeks",
                    message="weeks must be an integer",
                    details={"weeks": weeks},
                )
            label_return_threshold = body.get("label_return_threshold", 0.30)
            if not isinstance(label_return_threshold, (int, float)):
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_label_return_threshold",
                    message="label_return_threshold must be a number",
                    details={"label_return_threshold": label_return_threshold},
                )
            precision_floor = body.get("precision_floor", 0.85)
            if not isinstance(precision_floor, (int, float)):
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_precision_floor",
                    message="precision_floor must be a number",
                    details={"precision_floor": precision_floor},
                )

            return HTTPStatus.OK, self.service.lowfreq_rsi_weekly_record_view(
                target_date=target_date,
                weeks=int(weeks),
                label_return_threshold=float(label_return_threshold),
                precision_floor=float(precision_floor),
                requested_by=requested_by.strip(),
            )

        if path == "/api/pools/manual/snapshot":
            raw_date = body.get("date") or date.today().isoformat()
            if not isinstance(raw_date, str):
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_date",
                    message="date must be a string in YYYY-MM-DD format",
                    details={"date": raw_date},
                )
            try:
                date.fromisoformat(raw_date)
            except ValueError:
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_date",
                    message=f"invalid date: {raw_date}",
                    details={"date": raw_date},
                )

            pool_id = body.get("pool_id")
            if not isinstance(pool_id, str) or not pool_id.strip():
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_pool_id",
                    message="pool_id must be a non-empty string",
                    details={"pool_id": pool_id},
                )

            members = body.get("members")
            if not isinstance(members, list) or not all(isinstance(item, str) for item in members):
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_members",
                    message="members must be a list of strings",
                    details={"members": members},
                )

            display_name = body.get("display_name")
            if display_name is not None and not isinstance(display_name, str):
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_display_name",
                    message="display_name must be a string when provided",
                    details={"display_name": display_name},
                )

            requested_by = body.get("requested_by", "api")
            if not isinstance(requested_by, str) or not requested_by.strip():
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_requested_by",
                    message="requested_by must be a non-empty string",
                    details={"requested_by": requested_by},
                )

            dry_run = body.get("dry_run", False)
            if not isinstance(dry_run, bool):
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_dry_run",
                    message="dry_run must be a boolean",
                    details={"dry_run": dry_run},
                )

            return HTTPStatus.OK, self.service.pool_manual_snapshot_view(
                target_date=raw_date,
                pool_id=pool_id.strip(),
                display_name=display_name,
                members=[str(item) for item in members],
                requested_by=requested_by.strip(),
                dry_run=dry_run,
            )

        if path == "/api/screeners/run":
            screener_id = body.get("screener_id")
            if not isinstance(screener_id, str) or not screener_id.strip():
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_screener_id",
                    message="screener_id must be a non-empty string",
                    details={"screener_id": screener_id},
                )

            raw_date = body.get("date") or date.today().isoformat()
            if not isinstance(raw_date, str):
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_date",
                    message="date must be a string in YYYY-MM-DD format",
                    details={"date": raw_date},
                )
            try:
                date.fromisoformat(raw_date)
            except ValueError:
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_date",
                    message=f"invalid date: {raw_date}",
                    details={"date": raw_date},
                )

            requested_by = body.get("requested_by", "api")
            if not isinstance(requested_by, str) or not requested_by.strip():
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_requested_by",
                    message="requested_by must be a non-empty string",
                    details={"requested_by": requested_by},
                )

            dry_run = body.get("dry_run", False)
            if not isinstance(dry_run, bool):
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_dry_run",
                    message="dry_run must be a boolean",
                    details={"dry_run": dry_run},
                )

            parameters = body.get("parameters")
            if parameters is not None and not isinstance(parameters, dict):
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_parameters",
                    message="parameters must be an object",
                    details={"parameters": parameters},
                )

            return HTTPStatus.OK, self.service.screeners_run_view(
                target_date=raw_date,
                screener_id=screener_id.strip(),
                requested_by=requested_by.strip(),
                parameters=parameters,
                dry_run=dry_run,
            )

        if path == "/api/screeners/bulk-run":
            raw_date = body.get("date") or date.today().isoformat()
            if not isinstance(raw_date, str):
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_date",
                    message="date must be a string in YYYY-MM-DD format",
                    details={"date": raw_date},
                )
            try:
                date.fromisoformat(raw_date)
            except ValueError:
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_date",
                    message=f"invalid date: {raw_date}",
                    details={"date": raw_date},
                )

            requested_by = body.get("requested_by", "api")
            if not isinstance(requested_by, str) or not requested_by.strip():
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_requested_by",
                    message="requested_by must be a non-empty string",
                    details={"requested_by": requested_by},
                )

            dry_run = body.get("dry_run", False)
            if not isinstance(dry_run, bool):
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_dry_run",
                    message="dry_run must be a boolean",
                    details={"dry_run": dry_run},
                )

            parameters = body.get("parameters")
            if parameters is not None and not isinstance(parameters, dict):
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_parameters",
                    message="parameters must be an object",
                    details={"parameters": parameters},
                )

            screener_ids = body.get("screener_ids")
            if screener_ids is not None and not isinstance(screener_ids, list):
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_screener_id",
                    message="screener_ids must be a list",
                    details={"screener_ids": screener_ids},
                )

            async_run = body.get("async_run", False)
            if not isinstance(async_run, bool):
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_async_run",
                    message="async_run must be a boolean",
                    details={"async_run": async_run},
                )

            payload = self.service.screeners_bulk_run_view(
                target_date=raw_date,
                screener_ids=(
                    [str(item) for item in screener_ids] if screener_ids is not None else None
                ),
                requested_by=requested_by.strip(),
                parameters=parameters,
                dry_run=dry_run,
                async_run=async_run,
            )
            return (HTTPStatus.ACCEPTED if payload.get("_meta", {}).get("status") == "accepted" else HTTPStatus.OK), payload

        if path.startswith("/api/screeners/config/"):
            parts = [part for part in path.split("/") if part]
            if len(parts) != 4:
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_path",
                    message="expected /api/screeners/config/<screener_id>",
                    details={"path": path},
                )
            screener_id = parts[-1].strip()
            if not screener_id:
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_screener_id",
                    message="screener_id must be a non-empty string",
                    details={"screener_id": screener_id},
                )

            current_parameters = body.get("current_parameters")
            if not isinstance(current_parameters, dict):
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_parameters",
                    message="current_parameters must be an object",
                    details={"current_parameters": current_parameters},
                )

            requested_by = body.get("requested_by", "api")
            if not isinstance(requested_by, str) or not requested_by.strip():
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_requested_by",
                    message="requested_by must be a non-empty string",
                    details={"requested_by": requested_by},
                )

            return HTTPStatus.OK, self.service.screener_config_update_view(
                screener_id=screener_id,
                current_parameters=current_parameters,
                requested_by=requested_by.strip(),
            )

        if path == "/api/factor-matrix/daily/run":
            raw_date = body.get("date") or date.today().isoformat()
            if not isinstance(raw_date, str):
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_date",
                    message="date must be a string in YYYY-MM-DD format",
                    details={"date": raw_date},
                )
            try:
                date.fromisoformat(raw_date)
            except ValueError:
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_date",
                    message=f"invalid date: {raw_date}",
                    details={"date": raw_date},
                )

            requested_by = body.get("requested_by", "api")
            if not isinstance(requested_by, str) or not requested_by.strip():
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_requested_by",
                    message="requested_by must be a non-empty string",
                    details={"requested_by": requested_by},
                )

            dry_run = body.get("dry_run", False)
            if not isinstance(dry_run, bool):
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_dry_run",
                    message="dry_run must be a boolean",
                    details={"dry_run": dry_run},
                )

            debug = body.get("debug", False)
            if not isinstance(debug, bool):
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_debug",
                    message="debug must be a boolean",
                    details={"debug": debug},
                )

            return HTTPStatus.OK, self.service.factor_matrix_daily_run_view(
                target_date=raw_date,
                requested_by=requested_by.strip(),
                dry_run=dry_run,
                debug=debug,
            )

        if path == "/api/sector-prosperity/daily/run":
            raw_date = body.get("date") or date.today().isoformat()
            if not isinstance(raw_date, str):
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_date",
                    message="date must be a string in YYYY-MM-DD format",
                    details={"date": raw_date},
                )
            try:
                date.fromisoformat(raw_date)
            except ValueError:
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_date",
                    message=f"invalid date: {raw_date}",
                    details={"date": raw_date},
                )
            requested_by = body.get("requested_by", "api")
            if not isinstance(requested_by, str) or not requested_by.strip():
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_requested_by",
                    message="requested_by must be a non-empty string",
                    details={"requested_by": requested_by},
                )
            dry_run = body.get("dry_run", False)
            if not isinstance(dry_run, bool):
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_dry_run",
                    message="dry_run must be a boolean",
                    details={"dry_run": dry_run},
                )
            return HTTPStatus.OK, self.service.sector_prosperity_daily_run_view(
                target_date=raw_date,
                requested_by=requested_by.strip(),
                dry_run=dry_run,
            )

        if path == "/api/labs/run":
            lab_id = body.get("lab_id")
            if not isinstance(lab_id, str) or not lab_id.strip():
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_lab_id",
                    message="lab_id must be a non-empty string",
                    details={"lab_id": lab_id},
                )

            raw_date = body.get("date") or date.today().isoformat()
            if not isinstance(raw_date, str):
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_date",
                    message="date must be a string in YYYY-MM-DD format",
                    details={"date": raw_date},
                )
            try:
                date.fromisoformat(raw_date)
            except ValueError:
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_date",
                    message=f"invalid date: {raw_date}",
                    details={"date": raw_date},
                )

            requested_by = body.get("requested_by", "api")
            if not isinstance(requested_by, str) or not requested_by.strip():
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_requested_by",
                    message="requested_by must be a non-empty string",
                    details={"requested_by": requested_by},
                )

            dry_run = body.get("dry_run", False)
            if not isinstance(dry_run, bool):
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_dry_run",
                    message="dry_run must be a boolean",
                    details={"dry_run": dry_run},
                )

            return HTTPStatus.OK, self.service.lab_run_view(
                target_date=raw_date,
                lab_id=lab_id.strip(),
                requested_by=requested_by.strip(),
                dry_run=dry_run,
            )

        if path == "/api/orchestration/run":
            raw_date = body.get("date") or date.today().isoformat()
            if not isinstance(raw_date, str):
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_date",
                    message="date must be a string in YYYY-MM-DD format",
                    details={"date": raw_date},
                )
            try:
                date.fromisoformat(raw_date)
            except ValueError:
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_date",
                    message=f"invalid date: {raw_date}",
                    details={"date": raw_date},
                )

            mode = body.get("mode", "daily")
            if not isinstance(mode, str) or not mode.strip():
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_mode",
                    message="mode must be a non-empty string",
                    details={"mode": mode},
                )
            normalized_mode = mode.strip().lower()
            if normalized_mode not in {
                "daily",
                "governance_reject",
                "governance_reject_transition_chain",
                "governance_status_transition",
                "governance_candidate_validation_outcome",
                "governance_final_validation_selection",
            }:
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_mode",
                    message=(
                        "mode must be one of: daily, governance_reject, "
                        "governance_reject_transition_chain, "
                        "governance_status_transition, "
                        "governance_candidate_validation_outcome, "
                        "governance_final_validation_selection"
                    ),
                    details={"mode": mode},
                )

            requested_by = body.get("requested_by", "api")
            if not isinstance(requested_by, str) or not requested_by.strip():
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_requested_by",
                    message="requested_by must be a non-empty string",
                    details={"requested_by": requested_by},
                )

            publish_succeeded = body.get("publish_succeeded", False)
            if not isinstance(publish_succeeded, bool):
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_publish_succeeded",
                    message="publish_succeeded must be a boolean",
                    details={"publish_succeeded": publish_succeeded},
                )

            dry_run = body.get("dry_run", False)
            if not isinstance(dry_run, bool):
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_dry_run",
                    message="dry_run must be a boolean",
                    details={"dry_run": dry_run},
                )

            source_run_id = body.get("source_run_id")
            validation_id = body.get("validation_id")
            validation_result = body.get("validation_result")
            resolved_validation_result: ValidationResult | None = None
            if normalized_mode in {
                "governance_reject",
                "governance_reject_transition_chain",
                "governance_status_transition",
                "governance_candidate_validation_outcome",
                "governance_final_validation_selection",
            }:
                if (
                    not isinstance(source_run_id, str)
                    or not source_run_id.strip()
                ):
                    raise ApiError(
                        status_code=HTTPStatus.BAD_REQUEST,
                        code="invalid_source_run_id",
                        message="source_run_id must be a non-empty string",
                        details={"source_run_id": source_run_id},
                    )
            if normalized_mode in {
                "governance_reject",
                "governance_status_transition",
            }:
                if (
                    not isinstance(validation_id, str)
                    or not validation_id.strip()
                ):
                    raise ApiError(
                        status_code=HTTPStatus.BAD_REQUEST,
                        code="invalid_validation_id",
                        message="validation_id must be a non-empty string",
                        details={"validation_id": validation_id},
                    )
            if normalized_mode == "governance_candidate_validation_outcome":
                try:
                    resolved_validation_result = ValidationResult.from_dict(
                        validation_result
                    )
                except (TypeError, ValueError) as exc:
                    raise ApiError(
                        status_code=HTTPStatus.BAD_REQUEST,
                        code="invalid_validation_result",
                        message=(
                            "validation_result must match ValidationResult contract"
                        ),
                        details={"reason": str(exc)},
                    ) from exc
            elif (
                normalized_mode == "governance_final_validation_selection"
                and validation_result is not None
            ):
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_validation_result",
                    message=(
                        "validation_result is not supported for "
                        "governance_final_validation_selection"
                    ),
                    details={"validation_result": validation_result},
                )

            return HTTPStatus.OK, self.service.orchestration_run_view(
                target_date=raw_date,
                mode=normalized_mode,
                publish_succeeded=publish_succeeded,
                requested_by=requested_by.strip(),
                dry_run=dry_run,
                source_run_id=(
                    source_run_id.strip()
                    if isinstance(source_run_id, str)
                    else None
                ),
                validation_id=(
                    validation_id.strip()
                    if isinstance(validation_id, str)
                    else None
                ),
                validation_result=resolved_validation_result,
            )

        if path == "/api/trading-calendar/rebuild":
            default_db_path = str(self.service.project_root / "var/db/stock_data.db")
            sqlite_db_path = (
                body.get("sqlite_db_path")
                or os.environ.get("NEOTRADE3_STOCK_DB_PATH")
                or default_db_path
            )
            table = body.get("table") or "daily_prices"
            date_column = body.get("date_column") or "trade_date"
            requested_by = body.get("requested_by", "api")

            if not isinstance(sqlite_db_path, str) or not sqlite_db_path.strip():
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_db_path",
                    message="sqlite_db_path must be a non-empty string",
                    details={"env_var": "NEOTRADE3_STOCK_DB_PATH"},
                )
            if not isinstance(table, str) or not table.strip():
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_table",
                    message="table must be a non-empty string",
                    details={"table": table},
                )
            if not isinstance(date_column, str) or not date_column.strip():
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_date_column",
                    message="date_column must be a non-empty string",
                    details={"date_column": date_column},
                )
            if str(table) != "daily_prices":
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_table",
                    message="unsupported table for trading calendar rebuild",
                    details={"expected": "daily_prices", "table": table},
                )
            if str(date_column) != "trade_date":
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_date_column",
                    message="unsupported date_column for trading calendar rebuild",
                    details={"expected": "trade_date", "date_column": date_column},
                )
            if not isinstance(requested_by, str) or not requested_by.strip():
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_requested_by",
                    message="requested_by must be a non-empty string",
                    details={"requested_by": requested_by},
                )

            return HTTPStatus.OK, self.service.rebuild_trading_calendar_view(
                sqlite_db_path=sqlite_db_path,
                table=table,
                date_column=date_column,
                requested_by=requested_by.strip(),
            )

        if path == "/api/data-control/seed-stock-db":
            source_db_path = body.get("source_db_path") or ""
            if not isinstance(source_db_path, str) or not source_db_path.strip():
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_source_db_path",
                    message="source_db_path must be a non-empty string",
                    details={"source_db_path": source_db_path},
                )

            requested_by = body.get("requested_by", "api")
            if not isinstance(requested_by, str) or not requested_by.strip():
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_requested_by",
                    message="requested_by must be a non-empty string",
                    details={"requested_by": requested_by},
                )

            force = body.get("force", False)
            if not isinstance(force, bool):
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_force",
                    message="force must be a boolean",
                    details={"force": force},
                )

            rebuild_trading_calendar = body.get("rebuild_trading_calendar", True)
            if not isinstance(rebuild_trading_calendar, bool):
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_rebuild_trading_calendar",
                    message="rebuild_trading_calendar must be a boolean",
                    details={"rebuild_trading_calendar": rebuild_trading_calendar},
                )

            strict = body.get("strict", True)
            if not isinstance(strict, bool):
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_strict",
                    message="strict must be a boolean",
                    details={"strict": strict},
                )

            normalize_volume_to = body.get("normalize_volume_to", "share")
            if not isinstance(normalize_volume_to, str) or not normalize_volume_to.strip():
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_normalize_volume_to",
                    message="normalize_volume_to must be a non-empty string",
                    details={"normalize_volume_to": normalize_volume_to},
                )

            return HTTPStatus.OK, self.service.seed_stock_db_view(
                source_db_path=source_db_path.strip(),
                force=force,
                requested_by=requested_by.strip(),
                rebuild_trading_calendar=rebuild_trading_calendar,
                strict=strict,
                normalize_volume_to=normalize_volume_to.strip(),
            )

        if path == "/api/data-control/sync-daily-prices":
            source_db_path = body.get("source_db_path")
            if source_db_path is None or (
                isinstance(source_db_path, str) and not source_db_path.strip()
            ):
                raw_env_path = os.environ.get("NEOTRADE3_STOCK_DB_V2_PATH")
                if isinstance(raw_env_path, str) and raw_env_path.strip():
                    source_db_path = raw_env_path.strip()
                else:
                    raise ApiError(
                        status_code=HTTPStatus.BAD_REQUEST,
                        code="invalid_source_db_path",
                        message="source_db_path is required (or configure NEOTRADE3_STOCK_DB_V2_PATH)",
                        details={
                            "hint": {
                                "source_db_path": "请通过 source_db_path 参数指定源数据库路径，或设置环境变量 NEOTRADE3_STOCK_DB_V2_PATH"
                            }
                        },
                    )
            if not isinstance(source_db_path, str) or not source_db_path.strip():
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_source_db_path",
                    message="source_db_path must be a non-empty string",
                    details={"source_db_path": source_db_path},
                )

            requested_by = body.get("requested_by", "api")
            if not isinstance(requested_by, str) or not requested_by.strip():
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_requested_by",
                    message="requested_by must be a non-empty string",
                    details={"requested_by": requested_by},
                )

            dry_run = body.get("dry_run", False)
            if not isinstance(dry_run, bool):
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_dry_run",
                    message="dry_run must be a boolean",
                    details={"dry_run": dry_run},
                )

            rebuild_trading_calendar = body.get("rebuild_trading_calendar", True)
            if not isinstance(rebuild_trading_calendar, bool):
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_rebuild_trading_calendar",
                    message="rebuild_trading_calendar must be a boolean",
                    details={"rebuild_trading_calendar": rebuild_trading_calendar},
                )

            target_date = body.get("target_date")
            if target_date is None:
                target_date = body.get("date")
            if target_date is not None:
                if not isinstance(target_date, str) or not target_date.strip():
                    raise ApiError(
                        status_code=HTTPStatus.BAD_REQUEST,
                        code="invalid_target_date",
                        message="target_date must be a non-empty string in YYYY-MM-DD format",
                        details={"target_date": target_date},
                    )
                try:
                    date.fromisoformat(target_date)
                except ValueError:
                    raise ApiError(
                        status_code=HTTPStatus.BAD_REQUEST,
                        code="invalid_target_date",
                        message=f"invalid target_date: {target_date}",
                        details={"target_date": target_date},
                    )

            return HTTPStatus.OK, self.service.sync_daily_prices_view(
                source_db_path=source_db_path.strip(),
                requested_by=requested_by.strip(),
                dry_run=dry_run,
                rebuild_trading_calendar=rebuild_trading_calendar,
                target_date=target_date,
            )

        if path == "/api/data-control/backfill/daily-prices/tushare":
            start_date = body.get("start_date") or ""
            end_date = body.get("end_date") or ""
            if not isinstance(start_date, str) or not start_date.strip():
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_start_date",
                    message="start_date is required (YYYY-MM-DD)",
                )
            if not isinstance(end_date, str) or not end_date.strip():
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_end_date",
                    message="end_date is required (YYYY-MM-DD)",
                )
            requested_by = body.get("requested_by", "api")
            if not isinstance(requested_by, str) or not requested_by.strip():
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_requested_by",
                    message="requested_by must be a non-empty string",
                    details={"requested_by": requested_by},
                )
            dry_run = body.get("dry_run", False)
            if not isinstance(dry_run, bool):
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_dry_run",
                    message="dry_run must be a boolean",
                    details={"dry_run": dry_run},
                )
            min_close_coverage = body.get("min_close_coverage", 0.99)
            if not isinstance(min_close_coverage, (int, float)):
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_min_close_coverage",
                    message="min_close_coverage must be a number",
                    details={"min_close_coverage": min_close_coverage},
                )
            min_amount_coverage = body.get("min_amount_coverage", 0.99)
            if not isinstance(min_amount_coverage, (int, float)):
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_min_amount_coverage",
                    message="min_amount_coverage must be a number",
                    details={"min_amount_coverage": min_amount_coverage},
                )
            min_turnover_coverage = body.get("min_turnover_coverage", 0.0)
            if not isinstance(min_turnover_coverage, (int, float)):
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_min_turnover_coverage",
                    message="min_turnover_coverage must be a number",
                    details={"min_turnover_coverage": min_turnover_coverage},
                )
            return HTTPStatus.OK, self.service.backfill_daily_prices_tushare_range_view(
                start_date=str(start_date).strip(),
                end_date=str(end_date).strip(),
                requested_by=requested_by.strip(),
                min_close_coverage=float(min_close_coverage),
                min_amount_coverage=float(min_amount_coverage),
                min_turnover_coverage=float(min_turnover_coverage),
                dry_run=dry_run,
            )

        if path == "/api/data-control/update-stock-fundamentals/tushare":
            raw_date = body.get("trade_date") or body.get("date") or date.today().isoformat()
            if not isinstance(raw_date, str):
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_trade_date",
                    message="trade_date must be a string in YYYY-MM-DD format",
                    details={"trade_date": raw_date},
                )
            try:
                date.fromisoformat(raw_date)
            except ValueError:
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_trade_date",
                    message=f"invalid trade_date: {raw_date}",
                    details={"trade_date": raw_date},
                )

            requested_by = body.get("requested_by", "api")
            if not isinstance(requested_by, str) or not requested_by.strip():
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_requested_by",
                    message="requested_by must be a non-empty string",
                    details={"requested_by": requested_by},
                )

            dry_run = body.get("dry_run", False)
            if not isinstance(dry_run, bool):
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_dry_run",
                    message="dry_run must be a boolean",
                    details={"dry_run": dry_run},
                )

            return HTTPStatus.OK, self.service.stock_fundamentals_update_tushare_view(
                trade_date=raw_date,
                requested_by=requested_by.strip(),
                dry_run=dry_run,
            )

        if path == "/api/data-control/update-financial-reports/tushare":
            start_period = body.get("start_period") or ""
            end_period = body.get("end_period") or ""
            if not isinstance(start_period, str) or not start_period.strip():
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_start_period",
                    message="start_period is required (YYYYMMDD)",
                )
            if not isinstance(end_period, str) or not end_period.strip():
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_end_period",
                    message="end_period is required (YYYYMMDD)",
                )
            requested_by = body.get("requested_by", "api")
            if not isinstance(requested_by, str) or not requested_by.strip():
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_requested_by",
                    message="requested_by must be a non-empty string",
                    details={"requested_by": requested_by},
                )
            max_codes = body.get("max_codes", 0)
            if max_codes is not None and not isinstance(max_codes, int):
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_max_codes",
                    message="max_codes must be an integer",
                    details={"max_codes": max_codes},
                )
            sleep_seconds = body.get("sleep_seconds", 0.12)
            if not isinstance(sleep_seconds, (int, float)) or float(sleep_seconds) < 0:
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_sleep_seconds",
                    message="sleep_seconds must be a non-negative number",
                    details={"sleep_seconds": sleep_seconds},
                )
            dry_run = body.get("dry_run", False)
            if not isinstance(dry_run, bool):
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_dry_run",
                    message="dry_run must be a boolean",
                    details={"dry_run": dry_run},
                )
            return HTTPStatus.OK, self.service.financial_reports_update_tushare_view(
                start_period=str(start_period).strip(),
                end_period=str(end_period).strip(),
                requested_by=requested_by.strip(),
                max_codes=int(max_codes) if isinstance(max_codes, int) else 0,
                sleep_seconds=float(sleep_seconds),
                dry_run=dry_run,
            )

        if path == "/api/data-control/sync-tushare-market-data":
            resource = body.get("resource") or ""
            if not isinstance(resource, str) or not resource.strip():
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_resource",
                    message="resource is required",
                )
            requested_by = body.get("requested_by", "api")
            if not isinstance(requested_by, str) or not requested_by.strip():
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_requested_by",
                    message="requested_by must be a non-empty string",
                    details={"requested_by": requested_by},
                )
            filters = body.get("filters", {})
            if not isinstance(filters, dict):
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_filters",
                    message="filters must be an object",
                    details={"filters_type": type(filters).__name__},
                )
            fields = body.get("fields")
            if fields is not None:
                if not isinstance(fields, list) or any(
                    not isinstance(item, str) or not item.strip() for item in fields
                ):
                    raise ApiError(
                        status_code=HTTPStatus.BAD_REQUEST,
                        code="invalid_fields",
                        message="fields must be a list of non-empty strings",
                    )
                fields = [str(item).strip() for item in fields]
            dry_run = body.get("dry_run", False)
            if not isinstance(dry_run, bool):
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_dry_run",
                    message="dry_run must be a boolean",
                    details={"dry_run": dry_run},
                )
            timeout_seconds = body.get("timeout_seconds", 20)
            if not isinstance(timeout_seconds, int) or timeout_seconds <= 0:
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_timeout_seconds",
                    message="timeout_seconds must be a positive integer",
                    details={"timeout_seconds": timeout_seconds},
                )
            return HTTPStatus.OK, self.service.sync_tushare_market_data_view(
                resource=str(resource).strip(),
                requested_by=requested_by.strip(),
                filters=filters,
                fields=fields,
                dry_run=dry_run,
                timeout_seconds=int(timeout_seconds),
            )

        if path == "/api/data-control/backfill/ths-concept-daily":
            start_date = body.get("start_date") or ""
            end_date = body.get("end_date") or ""
            if not isinstance(start_date, str) or not start_date.strip():
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_start_date",
                    message="start_date is required (YYYY-MM-DD)",
                )
            if not isinstance(end_date, str) or not end_date.strip():
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_end_date",
                    message="end_date is required (YYYY-MM-DD)",
                )
            requested_by = body.get("requested_by", "api")
            if not isinstance(requested_by, str) or not requested_by.strip():
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_requested_by",
                    message="requested_by must be a non-empty string",
                    details={"requested_by": requested_by},
                )
            top_n = body.get("top_n", 10)
            if not isinstance(top_n, int) or top_n <= 0:
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_top_n",
                    message="top_n must be a positive integer",
                    details={"top_n": top_n},
                )
            leader_k = body.get("leader_k", 5)
            if not isinstance(leader_k, int) or leader_k <= 0:
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_leader_k",
                    message="leader_k must be a positive integer",
                    details={"leader_k": leader_k},
                )
            limit_days = body.get("limit_days", 0)
            if limit_days is not None and (not isinstance(limit_days, int) or limit_days < 0):
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_limit_days",
                    message="limit_days must be a non-negative integer",
                    details={"limit_days": limit_days},
                )
            dry_run = body.get("dry_run", False)
            if not isinstance(dry_run, bool):
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_dry_run",
                    message="dry_run must be a boolean",
                    details={"dry_run": dry_run},
                )
            return HTTPStatus.OK, self.service.ths_concept_mainline_backfill_view(
                start_date=str(start_date).strip(),
                end_date=str(end_date).strip(),
                requested_by=requested_by.strip(),
                top_n=int(top_n),
                leader_k=int(leader_k),
                limit_days=int(limit_days) if isinstance(limit_days, int) else 0,
                dry_run=dry_run,
            )

        if path == "/api/data-control/validate-stock-db":
            sqlite_db_path = body.get("sqlite_db_path") or str(
                self.service.project_root / "var/db/stock_data.db"
            )
            if not isinstance(sqlite_db_path, str) or not sqlite_db_path.strip():
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_db_path",
                    message="sqlite_db_path must be a non-empty string",
                    details={"sqlite_db_path": "redacted"},
                )

            sample_limit = body.get("sample_limit", 200)
            if not isinstance(sample_limit, int) or sample_limit <= 0:
                raise ApiError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    code="invalid_sample_limit",
                    message="sample_limit must be a positive integer",
                    details={"sample_limit": sample_limit},
                )

            return HTTPStatus.OK, {
                "_meta": {"status": "ok"},
                "units_validation": self.service.validate_stock_db_view(
                    sqlite_db_path=sqlite_db_path.strip(),
                    sample_limit=sample_limit,
                ),
            }

        raise ApiError(
            status_code=HTTPStatus.NOT_FOUND,
            code="not_found",
            message=f"unsupported path: {path}",
            details={"path": path},
        )

    def _data_status(self, query: Optional[dict[str, list[str]]] = None) -> dict[str, Any]:
        import sqlite3

        include_tencent = False
        raw_tencent = None
        if query:
            raw_tencent = query.get("tencent", [None])[0]
            include_tencent = str(raw_tencent or "").strip().lower() in {"1", "true", "yes", "y", "on"}

        try:
            db_path = self.service.project_root / "var/db/stock_data.db"
            with sqlite3.connect(str(db_path)) as conn:
                cursor = conn.cursor()

                cursor.execute("SELECT COUNT(*) FROM stocks")
                stock_count = int(cursor.fetchone()[0] or 0)

                cursor.execute("SELECT MAX(trade_date) FROM daily_prices")
                latest_date = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM daily_prices")
                price_count = int(cursor.fetchone()[0] or 0)

            payload: dict[str, Any] = {
                "latest_trade_date": latest_date,
                "latest_available_date": latest_date,
                "stock_count": stock_count,
                "price_record_count": price_count,
                "status": "ok",
            }

            try:
                payload["tushare"] = self.service.tushare_status_view()
            except Exception:
                payload["tushare"] = {"_meta": {"status": "error"}, "credit_insufficient": False}

            if include_tencent:
                try:
                    payload["tencent"] = self.service.tencent_quote_meta_view(
                        symbol="sh000001",
                        timeout_seconds=10,
                    )
                except Exception:
                    payload["tencent"] = {"status": "error", "error": "tencent check failed"}

            return payload
        except Exception:
            return {
                "latest_trade_date": None,
                "latest_available_date": None,
                "stock_count": 0,
                "price_record_count": 0,
                "status": "error",
                "error": "stock db unavailable",
            }

    def _hot_sectors(self, query: dict) -> dict[str, Any]:
        target_date = query.get("date", [None])[0]
        mode = str(query.get("mode", ["ths_concept"])[0] or "ths_concept").strip()
        include_portfolio = self._parse_bool(query.get("include_portfolio", ["false"])[0])
        include_sell_signal = self._parse_bool(query.get("include_sell_signal", ["false"])[0])
        debug_perf = self._parse_bool(query.get("debug_perf", ["false"])[0])
        return self.service.lowfreq_hot_sectors_view(
            target_date=target_date,
            mode=mode,
            include_portfolio=include_portfolio,
            include_sell_signal=include_sell_signal,
            debug_perf=debug_perf,
        )

    def _concepts_mainline(self, query: dict) -> dict[str, Any]:
        target_date = query.get("date", [None])[0]
        raw_limit = query.get("limit", ["10"])[0]
        try:
            limit = int(str(raw_limit))
        except ValueError:
            raise ApiError(
                status_code=HTTPStatus.BAD_REQUEST,
                code="invalid_limit",
                message="limit must be an integer",
                details={"limit": raw_limit},
            )
        if limit <= 0:
            raise ApiError(
                status_code=HTTPStatus.BAD_REQUEST,
                code="invalid_limit",
                message="limit must be a positive integer",
                details={"limit": limit},
            )
        return self.service.ths_concept_mainline_view(
            trade_date=target_date,
            limit=limit,
            requested_by="api",
        )

    def _concepts_mainline_detail(self, query: dict) -> dict[str, Any]:
        target_date = query.get("date", [None])[0]
        concept_code = query.get("concept_code", [None])[0]
        if concept_code is None:
            raise ApiError(
                status_code=HTTPStatus.BAD_REQUEST,
                code="missing_concept_code",
                message="concept_code query parameter is required",
            )
        return self.service.ths_concept_mainline_detail_view(
            trade_date=target_date,
            concept_code=str(concept_code),
            requested_by="api",
        )

    def _lowfreq_rsi_regression(self, query: dict) -> dict[str, Any]:
        target_date = query.get("date", [None])[0]
        raw_weeks = query.get("weeks", ["12"])[0]
        try:
            weeks = int(str(raw_weeks))
        except ValueError:
            raise ApiError(
                status_code=HTTPStatus.BAD_REQUEST,
                code="invalid_weeks",
                message="weeks must be an integer",
                details={"weeks": raw_weeks},
            )
        raw_label = query.get("label_return_threshold", ["0.30"])[0]
        try:
            label_return_threshold = float(str(raw_label))
        except ValueError:
            raise ApiError(
                status_code=HTTPStatus.BAD_REQUEST,
                code="invalid_label_return_threshold",
                message="label_return_threshold must be a number",
                details={"label_return_threshold": raw_label},
            )
        raw_floor = query.get("precision_floor", ["0.85"])[0]
        try:
            precision_floor = float(str(raw_floor))
        except ValueError:
            raise ApiError(
                status_code=HTTPStatus.BAD_REQUEST,
                code="invalid_precision_floor",
                message="precision_floor must be a number",
                details={"precision_floor": raw_floor},
            )
        return self.service.lowfreq_rsi_regression_view(
            target_date=str(target_date).strip() if isinstance(target_date, str) and target_date.strip() else None,
            weeks=int(weeks),
            label_return_threshold=float(label_return_threshold),
            precision_floor=float(precision_floor),
        )

    def _generate_sample_stocks(self, count: int) -> list[dict]:
        import random

        sample_codes = ["600000", "600036", "600519", "000001", "000858", "300750", "300059"]
        sample_names = ["浦发银行", "招商银行", "贵州茅台", "平安银行", "五粮液", "宁德时代", "东方财富"]
        stocks = []
        for i in range(min(count, len(sample_codes))):
            stocks.append(
                {
                    "code": sample_codes[i],
                    "name": sample_names[i],
                    "certainty": 60 + random.randint(0, 40),
                    "return_5d": (random.random() - 0.3) * 20,
                    "buy_signal": random.random() > 0.6,
                    "suggested_entry": "今日" if random.random() > 0.7 else None,
                }
            )
        return stocks

    def _transform_sector_stocks(self, stocks: list) -> list[dict]:
        result = []
        for s in stocks:
            result.append(
                {
                    "code": s.get("code", ""),
                    "name": s.get("name", ""),
                    "certainty": s.get("certainty", s.get("score", 50)),
                    "return_5d": s.get("return_5d", 0),
                    "buy_signal": s.get("buy_signal", False),
                    "suggested_entry": s.get("suggested_entry"),
                }
            )
        return result

    def _get_screener_results(self, screener_id: str) -> dict:
        raise ApiError(
            status_code=HTTPStatus.NOT_IMPLEMENTED,
            code="screener_results_not_implemented",
            message="screener results endpoint is not implemented",
            details={
                "screener_id": str(screener_id),
                "endpoint": "/api/v1/screeners/<screener_id>/results",
            },
        )

    def _check_stock(self, code: str) -> dict:
        raise ApiError(
            status_code=HTTPStatus.NOT_IMPLEMENTED,
            code="stock_check_not_implemented",
            message="stock check endpoint is not implemented",
            details={
                "stock_code": str(code),
                "endpoint": "/api/v1/stock/<code>/check",
            },
        )

    @staticmethod
    def _parse_target_date(query: dict[str, list[str]]) -> date:
        raw_value = query.get("date", [date.today().isoformat()])[0]
        return date.fromisoformat(raw_value)

    @staticmethod
    def _parse_bool(raw_value: str) -> bool:
        return raw_value.lower() in {"1", "true", "yes", "on"}
