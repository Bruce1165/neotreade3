"""NeoTrade3 scheduler entrypoints.

This module serves three distinct purposes:
1. Defines the task functions that can be executed by id.
2. Provides `--run-once` manual entrypoints used by production LaunchAgents.
3. Provides APScheduler registrations for local development and debugging.

Current production enablement is defined by `config/launchd/` templates and the
installed LaunchAgents, not by the APScheduler registrations in this file.
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import os
import subprocess
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from neotrade3.common.python_runtime import log_python_runtime, require_python_310

logger = logging.getLogger(__name__)

# Project root: two levels up from this file
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS_DIR = _PROJECT_ROOT / "scripts"
_DEFAULT_ENV_FILE = Path.home() / "Library/Application Support/NeoTrade3/env.secrets"
_ENV_FILE_LOADED_FROM: Path | None = None


def _fingerprint_secret(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def _load_env_file() -> None:
    global _ENV_FILE_LOADED_FROM
    raw_path = os.environ.get("NEOTRADE3_ENV_FILE") or str(_DEFAULT_ENV_FILE)
    env_path = Path(str(raw_path or "")).expanduser() if raw_path else None
    if env_path is None or not env_path.exists() or not env_path.is_file():
        return
    try:
        text = env_path.read_text(encoding="utf-8")
    except OSError:
        return
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        key = k.strip()
        val = v.strip().strip('"').strip("'")
        if not key:
            continue
        os.environ[key] = val
    _ENV_FILE_LOADED_FROM = env_path


_load_env_file()


def _require_scheduler_python() -> None:
    require_python_310(entrypoint="neotrade3.scheduler.task_scheduler")

# ---------------------------------------------------------------------------
# Job functions (called by the scheduler)
# ---------------------------------------------------------------------------


def _run_update_daily_prices_authoritative() -> bool:
    try:
        from apps.api.main import BootstrapApiService

        _require_scheduler_python()
        service = BootstrapApiService(project_root=_PROJECT_ROOT)
        service._ensure_no_proxy(hosts=["api.waditu.com", "api.tushare.pro"])
        # #region debug-point B:scheduler-run-start
        service._dbg_emit(
            run_id="pre-fix",
            hypothesis_id="B",
            location="neotrade3/scheduler/task_scheduler.py:_run_update_daily_prices_authoritative",
            msg="[DEBUG] scheduler run_once start",
            data={
                "env_file": str(_ENV_FILE_LOADED_FROM) if _ENV_FILE_LOADED_FROM else None,
                "project_root": str(_PROJECT_ROOT),
            },
        )
        # #endregion
        now_cn = datetime.now(ZoneInfo("Asia/Shanghai"))
        cutoff = now_cn.date()
        if now_cn.time() < datetime.strptime("15:10:00", "%H:%M:%S").time():
            cutoff = cutoff - timedelta(days=1)
        cutoff_iso = cutoff.isoformat()

        db_path = _PROJECT_ROOT / "var" / "db" / "stock_data.db"
        latest_in_db: str | None = None
        try:
            import sqlite3

            with sqlite3.connect(str(db_path)) as conn:
                row = conn.execute("SELECT MAX(trade_date) FROM daily_prices").fetchone()
                latest_in_db = str(row[0]) if row and row[0] else None
        except Exception:
            latest_in_db = None
        if latest_in_db and latest_in_db > cutoff_iso:
            latest_in_db = cutoff_iso

        run_dates: list[str] = []
        try:
            import sqlite3

            with sqlite3.connect(str(db_path)) as conn:
                if latest_in_db:
                    rows = conn.execute(
                        """
                        SELECT trade_date
                        FROM trading_calendar_cache
                        WHERE trade_date > ? AND trade_date <= ?
                        ORDER BY trade_date ASC
                        """,
                        (latest_in_db, cutoff_iso),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        """
                        SELECT trade_date
                        FROM trading_calendar_cache
                        WHERE trade_date <= ?
                        ORDER BY trade_date DESC
                        LIMIT 1
                        """,
                        (cutoff_iso,),
                    ).fetchall()
                run_dates = [str(r[0]) for r in rows if r and r[0]]
                if latest_in_db is None:
                    run_dates = sorted(run_dates)
        except Exception:
            run_dates = [cutoff_iso]

        if not run_dates:
            logger.info(
                "update_daily_prices_authoritative: up-to-date (latest=%s cutoff=%s)",
                latest_in_db,
                cutoff_iso,
            )
            return True

        for d in run_dates:
            payload = service.daily_pipeline_run_view(
                target_date=str(d),
                requested_by="scheduler.update_daily_prices_authoritative",
            )
            ledger = payload.get("ledger") or {}
            steps = ledger.get("steps") or []
            step_status = {
                str(s.get("step_id") or ""): str(s.get("status") or "")
                for s in steps
                if isinstance(s, dict)
            }
            # #region debug-point C:scheduler-run-result
            service._dbg_emit(
                run_id="pre-fix",
                hypothesis_id="C",
                location="neotrade3/scheduler/task_scheduler.py:_run_update_daily_prices_authoritative",
                msg="[DEBUG] scheduler run_once done",
                data={
                    "cutoff_iso": str(cutoff_iso),
                    "ledger_path": payload.get("ledger_path"),
                    "target_date": ledger.get("target_date"),
                    "trade_date": ledger.get("trade_date"),
                    "steps": step_status,
                },
            )
            # #endregion
            logger.info(
                "daily_pipeline done: target_date=%s trade_date=%s ledger=%s steps=%s",
                ledger.get("target_date"),
                ledger.get("trade_date"),
                payload.get("ledger_path"),
                step_status,
            )
        return True
    except Exception as exc:
        logger.error("update_daily_prices_authoritative failed: %s", exc)
        return False


def _run_trade_execution_rt_0935() -> bool:
    try:
        from apps.api.main import BootstrapApiService

        _require_scheduler_python()
        service = BootstrapApiService(project_root=_PROJECT_ROOT)
        service._ensure_no_proxy(hosts=["qt.gtimg.cn", "api.waditu.com", "api.tushare.pro"])

        now_cn = datetime.now(ZoneInfo("Asia/Shanghai"))
        allow_offwindow = str(os.environ.get("NEOTRADE3_ALLOW_OFFWINDOW") or "").strip() in {"1", "true", "True", "yes", "Y"}
        window_start = now_cn.replace(hour=9, minute=33, second=0, microsecond=0)
        window_end = now_cn.replace(hour=9, minute=37, second=59, microsecond=0)
        if not allow_offwindow and not (window_start <= now_cn <= window_end):
            logger.info(
                "trade_execution_rt_0935 skipped: outside time window (now=%s window=%s~%s)",
                now_cn.strftime("%H:%M:%S"),
                window_start.strftime("%H:%M:%S"),
                window_end.strftime("%H:%M:%S"),
            )
            return True

        target_date = now_cn.date().isoformat()
        out = service.trade_execution_rt_run_view(
            target_date=target_date,
            requested_by="scheduler.trade_execution_rt_0935",
            timeout_seconds=10,
        )
        ledger = out.get("ledger") or {}
        summary = ledger.get("summary") or {}
        logger.info(
            "trade_execution_rt done: date=%s ledger=%s summary=%s",
            target_date,
            out.get("ledger_path"),
            summary,
        )
        return True
    except Exception as exc:
        logger.error("trade_execution_rt_0935 failed: %s", exc)
        return False


def _run_update_financial_data() -> bool:
    """Run scripts/update_financial_data.py."""
    script = _SCRIPTS_DIR / "update_financial_data.py"
    if not script.exists():
        logger.error("脚本不存在: %s", script)
        return False
    logger.info("开始执行 update_financial_data ...")
    try:
        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            timeout=300,
            cwd=str(_PROJECT_ROOT),
        )
        if result.returncode == 0:
            logger.info("update_financial_data 执行成功")
            return True
        else:
            logger.error(
                "update_financial_data 执行失败 (rc=%d): %s",
                result.returncode,
                result.stderr.strip()[-500:],
            )
            return False
    except subprocess.TimeoutExpired:
        logger.error("update_financial_data 执行超时")
        return False
    except Exception as exc:
        logger.error("update_financial_data 异常: %s", exc)
        return False


def _run_fetch_news() -> bool:
    """Fetch latest news from Cailianpress."""
    try:
        from apps.api.main import BootstrapApiService
        from neotrade3.data_sources.cls_adapter import ClsNewsAdapter

        service = BootstrapApiService(project_root=_PROJECT_ROOT)
        target_date = date.today().isoformat()
        trading_day = service.trading_day_view(target_date=target_date)
        if not bool(trading_day.get("is_trading_day")):
            logger.info(
                "fetch_news skipped: non-trading day (target_date=%s nearest_trading_day=%s)",
                target_date,
                trading_day.get("nearest_trading_day"),
            )
            return True

        adapter = ClsNewsAdapter()
        items = adapter.fetch_telegraph(limit=20)
        logger.info("财联社快讯抓取完成, 共 %d 条", len(items))
        return True
    except Exception as exc:
        logger.error("抓取财联社快讯失败: %s", exc)
        return False


def _run_warm_tushare_theme_cache() -> bool:
    try:
        from apps.api.main import BootstrapApiService

        raw_token = str(os.environ.get("TUSHARE_TOKEN") or "").strip()
        tushare_configured = bool(raw_token)
        token_fp = _fingerprint_secret(raw_token) if raw_token else None
        service = BootstrapApiService(project_root=_PROJECT_ROOT)
        out = service.warm_tushare_theme_cache_view(
            requested_by="scheduler.warm_tushare_theme_cache",
            max_member_calls=1,
        )
        logger.info(
            "warm_tushare_theme_cache done: env_file=%s tushare_configured=%s token_fp=%s status=%s warmed=%s missing=%s errors=%s",
            str(_ENV_FILE_LOADED_FROM) if _ENV_FILE_LOADED_FROM else None,
            tushare_configured,
            token_fp,
            out.get("status"),
            out.get("members_warmed"),
            out.get("members_missing_count"),
            (out.get("errors") or [])[:1],
        )
        return True
    except Exception as exc:
        logger.error("warm_tushare_theme_cache failed: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Scheduler wrapper
# ---------------------------------------------------------------------------


class NeoTradeScheduler:
    """Wraps APScheduler BackgroundScheduler for local/dev NeoTrade3 jobs.

    This wrapper is for code-level scheduling and debugging only. Current
    production automation is enabled via launchd LaunchAgents.

    Usage:
        scheduler = NeoTradeScheduler()
        scheduler.start()
        # ...
        scheduler.stop()
    """

    def __init__(self) -> None:
        self._scheduler = None
        self._apscheduler = None
        self._init_scheduler()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the scheduler."""
        if self._scheduler is None:
            logger.warning("APScheduler 未安装, 调度器无法启动")
            return
        if self._scheduler.running:
            logger.info("调度器已在运行中")
            return
        self._scheduler.start()
        logger.info("NeoTrade 调度器已启动")

    def stop(self) -> None:
        """Gracefully stop the scheduler."""
        if self._scheduler is not None and self._scheduler.running:
            self._scheduler.shutdown(wait=True)
            logger.info("NeoTrade 调度器已停止")

    def list_jobs(self) -> list[dict]:
        """List all scheduled jobs.

        Returns:
            List of dicts with job id, name, next_run_time, trigger info.
        """
        if self._scheduler is None:
            return []
        jobs: list[dict] = []
        for job in self._scheduler.get_jobs():
            nrt = getattr(job, "next_run_time", None)
            jobs.append(
                {
                    "id": job.id,
                    "name": job.name,
                    "next_run_time": str(nrt) if nrt else "not scheduled",
                    "trigger": str(job.trigger),
                }
            )
        return jobs

    def run_now(self, job_id: str) -> bool:
        """Trigger a job immediately by its id.

        Args:
            job_id: The job identifier, e.g. "update_financial_data".

        Returns:
            True if the job was found and triggered, False otherwise.
        """
        if self._scheduler is None:
            logger.warning("调度器不可用, 无法触发任务: %s", job_id)
            return False
        job = self._scheduler.get_job(job_id)
        if job is None:
            logger.warning("未找到任务: %s", job_id)
            return False
        job.modify(next_run_time=datetime.now(ZoneInfo("Asia/Shanghai")))
        logger.info("已触发任务: %s", job_id)
        return True

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _init_scheduler(self) -> None:
        """Initialize APScheduler jobs for local development/debugging."""
        try:
            from apscheduler.schedulers.background import BackgroundScheduler
            from apscheduler.triggers.cron import CronTrigger
            from apscheduler.triggers.interval import IntervalTrigger
        except ImportError:
            logger.warning(
                "APScheduler 未安装, 定时任务不可用. "
                "请执行: pip install APScheduler"
            )
            return

        self._apscheduler = True
        self._scheduler = BackgroundScheduler(
            timezone="Asia/Shanghai",
            job_defaults={"coalesce": True, "max_instances": 1},
        )

        # APScheduler local/dev definition only.
        # Production enablement and schedule are controlled by launchd templates.
        # Keep the local/dev cron aligned with the production launchd schedule.
        # Job 0: update_daily_prices_authoritative - 工作日 15:45 尝试同步当日行情
        self._scheduler.add_job(
            _run_update_daily_prices_authoritative,
            trigger=CronTrigger(
                day_of_week="mon-fri",
                hour=15,
                minute=45,
            ),
            id="update_daily_prices_authoritative",
            name="权威源同步日线行情",
            replace_existing=True,
        )

        # Local/dev APScheduler definition. No production LaunchAgent is enabled.
        # Job 1: update_financial_data - 每天 18:00 执行
        self._scheduler.add_job(
            _run_update_financial_data,
            trigger=CronTrigger(hour=18, minute=0),
            id="update_financial_data",
            name="更新财务数据",
            replace_existing=True,
        )

        # Local/dev APScheduler definition. No production LaunchAgent is enabled.
        # Job 2: fetch_news - 交易时段每 30 分钟
        self._scheduler.add_job(
            _run_fetch_news,
            trigger=CronTrigger(
                day_of_week="mon-fri",
                hour="9-14",
                minute="0,30",
            ),
            id="fetch_news",
            name="抓取财联社快讯",
            replace_existing=True,
        )

        # Local/dev APScheduler definition. No production LaunchAgent is enabled.
        # Job 3: warm_tushare_theme_cache - 每 2 分钟增量预热一次（避免刷新时触发频控）
        self._scheduler.add_job(
            _run_warm_tushare_theme_cache,
            trigger=IntervalTrigger(minutes=2),
            id="warm_tushare_theme_cache",
            name="预热Tushare概念缓存",
            replace_existing=True,
        )

        logger.info("已注册 %d 个定时任务", len(self._scheduler.get_jobs()))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run NeoTrade3 scheduler.")
    parser.add_argument(
        "--list-jobs",
        action="store_true",
        help="List APScheduler local/dev job registrations, not production launchd jobs.",
    )
    parser.add_argument(
        "--run-now",
        default=None,
        help="Trigger an APScheduler local/dev job id immediately then exit.",
    )
    parser.add_argument(
        "--run-once",
        default=None,
        help="Run a job id in foreground once then exit; used by production launchd run-once entrypoints.",
    )
    parser.add_argument(
        "--run-forever",
        action="store_true",
        help="Run APScheduler local/dev loop in foreground until interrupted; does not define production scheduling.",
    )
    return parser


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = build_parser()
    args = parser.parse_args()
    log_python_runtime(entrypoint="neotrade3.scheduler.task_scheduler", logger=logger)
    try:
        _require_scheduler_python()
    except RuntimeError as exc:
        logger.error(str(exc))
        return 2

    run_once_map = {
        "update_daily_prices_authoritative": _run_update_daily_prices_authoritative,
        "trade_execution_rt_0935": _run_trade_execution_rt_0935,
        "update_financial_data": _run_update_financial_data,
        "fetch_news": _run_fetch_news,
        "warm_tushare_theme_cache": _run_warm_tushare_theme_cache,
    }

    if args.run_once:
        job_id = str(args.run_once).strip()
        fn = run_once_map.get(job_id)
        if fn is None:
            raise SystemExit(f"unknown job_id: {job_id}")
        return 0 if fn() else 1

    scheduler = NeoTradeScheduler()

    if args.list_jobs:
        for job in scheduler.list_jobs():
            print(job)
        return 0

    if args.run_now:
        scheduler.start()
        triggered = scheduler.run_now(str(args.run_now))
        time.sleep(2.0)
        return 0 if triggered else 1

    scheduler.start()
    if args.run_forever:
        try:
            while True:
                time.sleep(1.0)
        except KeyboardInterrupt:
            pass
        finally:
            scheduler.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
