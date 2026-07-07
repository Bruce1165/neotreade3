"""Bootstrap preflight definitions for NeoTrade3 orchestration."""

from __future__ import annotations

import json
import os
import time
from datetime import date
from pathlib import Path

from .models import PreflightCheck, PreflightReport, PreflightStatus

# 锁文件路径（相对于项目根目录）
_LOCK_RELATIVE_PATH = "var/run/.lock"
# 锁超时时间（秒）：超过此时间视为僵尸锁，可强制获取
_LOCK_TIMEOUT_SECONDS = 3600  # 1 小时


class PreflightRunner:
    """Builds lightweight preflight checks for the daily orchestrator."""

    @staticmethod
    def default_checks() -> list[PreflightCheck]:
        return [
            PreflightCheck(
                check_id="trading_day_check",
                description="Confirm the target date is eligible for a daily orchestrator run.",
            ),
            PreflightCheck(
                check_id="run_lock_check",
                description="Confirm no conflicting orchestrator run lock is active.",
            ),
            PreflightCheck(
                check_id="environment_check",
                description="Confirm required config, database, and filesystem dependencies are reachable.",
            ),
            PreflightCheck(
                check_id="duplicate_run_check",
                description="Confirm the target date has not already been fully processed.",
            ),
            PreflightCheck(
                check_id="m1_formal_contract_check",
                description="Confirm existing M1 formal object evidence is not degraded when same-day data-control artifacts already exist.",
            ),
        ]

    @staticmethod
    def _project_root() -> Path:
        return Path(__file__).resolve().parents[2]

    def _load_trading_days(self) -> tuple[set[str], str | None]:
        ledger_file = (
            self._project_root() / "var/ledgers/trading_calendar/trading_calendar.json"
        )
        if not ledger_file.exists():
            return set(), f"missing trading calendar ledger: {ledger_file}"
        try:
            payload = json.loads(ledger_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return set(), f"failed to read trading calendar ledger: {exc}"
        if not isinstance(payload, dict):
            return set(), "trading calendar ledger is not a JSON object"
        trading_days = payload.get("trading_days")
        if not isinstance(trading_days, list) or not all(
            isinstance(item, str) for item in trading_days
        ):
            return set(), "trading calendar ledger missing trading_days list[str]"
        return set(trading_days), None

    def build_report(self, target_date: date) -> PreflightReport:
        checks_by_id = {check.check_id: check for check in self.default_checks()}
        overall = PreflightStatus.PASSED

        trading_days, trading_days_error = self._load_trading_days()
        trading_day_check = checks_by_id.get("trading_day_check")
        if trading_day_check is not None:
            if trading_days_error is not None:
                trading_day_check.status = PreflightStatus.FAILED
                trading_day_check.details = trading_days_error
                overall = PreflightStatus.FAILED
            elif target_date.isoformat() not in trading_days:
                trading_day_check.status = PreflightStatus.FAILED
                trading_day_check.details = (
                    f"target_date not in trading calendar: {target_date.isoformat()}"
                )
                overall = PreflightStatus.FAILED
            else:
                trading_day_check.status = PreflightStatus.PASSED
                trading_day_check.details = "target_date is a trading day"

        environment_check = checks_by_id.get("environment_check")
        if environment_check is not None:
            project_root = self._project_root()
            required_paths = [
                project_root / "config/data_control/source_registry.json",
                project_root / "config/labs/labs_registry.json",
                project_root / "config/orchestrator/daily_master_orchestrator.json",
                project_root / "config/screeners/screeners_registry.json",
                project_root / "var/db/stock_data.db",
                project_root / "var/ledgers/trading_calendar/trading_calendar.json",
            ]
            missing = [str(path) for path in required_paths if not path.exists()]
            if missing:
                environment_check.status = PreflightStatus.FAILED
                environment_check.details = "missing required paths: " + ", ".join(
                    missing
                )
                overall = PreflightStatus.FAILED
            else:
                environment_check.status = PreflightStatus.PASSED
                environment_check.details = "required paths are present"

        run_lock_check = checks_by_id.get("run_lock_check")
        if run_lock_check is not None:
            project_root = self._project_root()
            lock_path = project_root / _LOCK_RELATIVE_PATH

            if lock_path.exists():
                # 检查锁文件内容
                try:
                    lock_info = json.loads(lock_path.read_text(encoding="utf-8"))
                    locked_at = lock_info.get("locked_at", "")
                    locked_by = lock_info.get("locked_by", "unknown")
                    locked_pid = lock_info.get("pid", None)
                except (OSError, json.JSONDecodeError):
                    locked_at = "unknown"
                    locked_by = "unknown"
                    locked_pid = None

                # 检查是否为僵尸锁（超时）
                is_stale = False
                if locked_at and locked_at != "unknown":
                    try:
                        from calendar import timegm
                        lock_time = timegm(time.strptime(locked_at, "%Y-%m-%dT%H:%M:%SZ"))
                        if time.time() - lock_time > _LOCK_TIMEOUT_SECONDS:
                            is_stale = True
                    except (ValueError, OSError):
                        pass

                # 检查持有锁的进程是否仍在运行
                is_pid_alive = False
                if locked_pid and not is_stale:
                    try:
                        os.kill(locked_pid, 0)  # 信号 0：检查进程是否存在
                        is_pid_alive = True
                    except (OSError, ProcessLookupError):
                        is_pid_alive = False

                if is_stale or not is_pid_alive:
                    # 僵尸锁或进程已退出，可以安全获取
                    run_lock_check.status = PreflightStatus.WARNING
                    reason = "stale lock" if is_stale else "lock owner process exited"
                    run_lock_check.details = (
                        f"existing lock is stale ({reason}): "
                        f"locked_by={locked_by}, pid={locked_pid}, locked_at={locked_at}. "
                        f"Lock will be overwritten."
                    )
                    if overall is PreflightStatus.PASSED:
                        overall = PreflightStatus.WARNING
                else:
                    # 活跃锁，阻止运行
                    run_lock_check.status = PreflightStatus.FAILED
                    run_lock_check.details = (
                        f"active run lock detected: locked_by={locked_by}, "
                        f"pid={locked_pid}, locked_at={locked_at}. "
                        f"Wait for the other run to finish, or remove {lock_path} if stale."
                    )
                    overall = PreflightStatus.FAILED
            else:
                run_lock_check.status = PreflightStatus.PASSED
                run_lock_check.details = "no active run lock detected"

        duplicate_run_check = checks_by_id.get("duplicate_run_check")
        if duplicate_run_check is not None:
            project_root = self._project_root()
            date_key = target_date.isoformat()
            summary_path = (
                project_root
                / "var/artifacts/bootstrap_runs"
                / date_key
                / "bootstrap_run_summary.json"
            )
            if summary_path.exists():
                duplicate_run_check.status = PreflightStatus.WARNING
                duplicate_run_check.details = (
                    "bootstrap summary already exists; re-run will overwrite outputs"
                )
                if overall is PreflightStatus.PASSED:
                    overall = PreflightStatus.WARNING
            else:
                duplicate_run_check.status = PreflightStatus.PASSED
                duplicate_run_check.details = "no prior bootstrap summary detected"

        m1_formal_contract_check = checks_by_id.get("m1_formal_contract_check")
        if m1_formal_contract_check is not None:
            stage_summary = self._load_data_control_stage_summary(target_date)
            stages = stage_summary.get("stages") if isinstance(stage_summary, dict) else None
            if not isinstance(stages, dict) or not stages:
                m1_formal_contract_check.status = PreflightStatus.PASSED
                m1_formal_contract_check.details = (
                    "no same-day data_control artifacts found; skip M1 formal readiness gating"
                )
            else:
                degraded: list[str] = []
                partials: list[str] = []
                for stage, stage_payload in stages.items():
                    if not isinstance(stage_payload, dict):
                        continue
                    formal_summary = stage_payload.get("m1_formal_artifacts")
                    if not isinstance(formal_summary, dict):
                        continue
                    for object_family, object_payload in formal_summary.items():
                        if not isinstance(object_payload, dict):
                            continue
                        verdict = str(
                            object_payload.get("freshness_verdict") or "unknown"
                        ).strip().lower()
                        if verdict in {"not_ready", "unknown"}:
                            degraded.append(f"{stage}.{object_family}={verdict}")
                        elif verdict == "partial":
                            partials.append(f"{stage}.{object_family}=partial")
                if degraded:
                    m1_formal_contract_check.status = PreflightStatus.FAILED
                    m1_formal_contract_check.details = (
                        "existing same-day M1 formal artifacts are not ready: "
                        + ", ".join(degraded)
                    )
                    overall = PreflightStatus.FAILED
                elif partials:
                    m1_formal_contract_check.status = PreflightStatus.WARNING
                    m1_formal_contract_check.details = (
                        "existing same-day M1 formal artifacts are partial: "
                        + ", ".join(partials)
                    )
                    if overall is PreflightStatus.PASSED:
                        overall = PreflightStatus.WARNING
                else:
                    m1_formal_contract_check.status = PreflightStatus.PASSED
                    m1_formal_contract_check.details = (
                        "existing same-day M1 formal artifacts are ready"
                    )

        return PreflightReport(
            target_date=target_date,
            checks=list(checks_by_id.values()),
            overall_status=overall,
        )

    def _load_data_control_stage_summary(self, target_date: date) -> dict[str, object]:
        date_key = target_date.isoformat()
        summary: dict[str, object] = {"target_date": date_key, "stages": {}}
        stages: dict[str, object] = {}
        for stage in ("capture", "compose", "publish"):
            ledger_path = (
                self._project_root()
                / "var/ledgers/data_control"
                / date_key
                / f"data_control_{stage}_ledger.json"
            )
            if not ledger_path.exists():
                continue
            try:
                payload = json.loads(ledger_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(payload, dict):
                continue
            item: dict[str, object] = {
                "status": str(payload.get("status", "")),
                "message": str(payload.get("message", "")),
            }
            m1_formal_artifacts = payload.get("m1_formal_artifacts")
            if isinstance(m1_formal_artifacts, dict):
                summary_payload = m1_formal_artifacts.get("summary")
                if isinstance(summary_payload, dict):
                    item["m1_formal_artifacts"] = summary_payload
            stages[stage] = item
        summary["stages"] = stages
        return summary

    # ------------------------------------------------------------------
    # 运行锁管理（供 Worker 调用）
    # ------------------------------------------------------------------
    @staticmethod
    def acquire_lock(
        project_root: Path,
        requested_by: str = "unknown",
    ) -> tuple[bool, str]:
        """尝试获取运行锁。

        Returns
        -------
        tuple[bool, str]
            (成功与否, 说明信息)
        """
        lock_path = project_root / _LOCK_RELATIVE_PATH
        lock_path.parent.mkdir(parents=True, exist_ok=True)

        def _is_stale(*, locked_at: str) -> bool:
            if not locked_at:
                return False
            try:
                from calendar import timegm

                lock_time = timegm(time.strptime(locked_at, "%Y-%m-%dT%H:%M:%SZ"))
                return time.time() - lock_time > _LOCK_TIMEOUT_SECONDS
            except (ValueError, OSError):
                return False

        def _is_pid_alive(*, pid: object) -> bool:
            if not isinstance(pid, int) or pid <= 0:
                return False
            try:
                os.kill(pid, 0)
                return True
            except (OSError, ProcessLookupError):
                return False

        def _try_create_exclusive() -> tuple[bool, str]:
            lock_data = {
                "locked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "locked_by": requested_by,
                "pid": os.getpid(),
            }
            payload = (json.dumps(lock_data, indent=2, ensure_ascii=False) + "\n").encode(
                "utf-8"
            )
            try:
                fd = os.open(
                    str(lock_path),
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                    0o644,
                )
            except FileExistsError:
                return False, "exists"
            except OSError as exc:
                return False, f"open_failed: {exc}"
            try:
                os.write(fd, payload)
            except OSError as exc:
                try:
                    os.close(fd)
                except OSError:
                    pass
                try:
                    lock_path.unlink()
                except OSError:
                    pass
                return False, f"write_failed: {exc}"
            try:
                os.close(fd)
            except OSError:
                pass
            return True, f"锁已获取: pid={os.getpid()}, by={requested_by}"

        created, message = _try_create_exclusive()
        if created:
            return True, message
        if message != "exists":
            return False, f"写入锁文件失败: {message}"

        try:
            lock_info = json.loads(lock_path.read_text(encoding="utf-8"))
            locked_at = str(lock_info.get("locked_at", "") or "")
            locked_pid = lock_info.get("pid", None)
            locked_by = str(lock_info.get("locked_by", "?") or "?")
        except (OSError, json.JSONDecodeError):
            locked_at = ""
            locked_pid = None
            locked_by = "unknown"

        stale = _is_stale(locked_at=locked_at)
        alive = _is_pid_alive(pid=locked_pid) if not stale else False
        if not stale and alive:
            return False, (
                f"无法获取锁：活跃锁存在 (pid={locked_pid}, "
                f"locked_by={locked_by}, locked_at={locked_at})"
            )

        try:
            lock_path.unlink()
        except OSError as exc:
            return False, f"无法清理旧锁文件: {exc}"

        created, message = _try_create_exclusive()
        if created:
            return True, message
        if message == "exists":
            return False, "无法获取锁：并发获取导致锁已被其他进程抢占"
        return False, f"写入锁文件失败: {message}"

    @staticmethod
    def release_lock(project_root: Path) -> bool:
        """释放运行锁。

        Returns
        -------
        bool
            是否成功释放
        """
        lock_path = project_root / _LOCK_RELATIVE_PATH
        if lock_path.exists():
            try:
                lock_path.unlink()
                return True
            except OSError:
                return False
        return True  # 锁不存在也视为成功
