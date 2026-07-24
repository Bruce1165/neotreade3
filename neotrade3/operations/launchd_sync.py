from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import plistlib
import re
import shutil
import subprocess
import sys
from typing import Callable, Optional, Sequence

HOME_TOKEN = "{{HOME}}"
PROJECT_ROOT_TOKEN = "{{PROJECT_ROOT}}"
PYTHON_BIN_TOKEN = "{{PYTHON_BIN}}"
NODE_BIN_TOKEN = "{{NODE_BIN}}"
DASHBOARD_PASSWORD_TOKEN = "{{DASHBOARD_PASSWORD}}"
DEFAULT_AGENT_TARGET_DIR = Path.home() / "Library" / "LaunchAgents"
DEFAULT_DAEMON_TARGET_DIR = Path("/Library/LaunchDaemons")
DEFAULT_TARGET_DIR = DEFAULT_AGENT_TARGET_DIR
EXPECTED_WEEKDAYS = (1, 2, 3, 4, 5)

_WEEKDAY_RE = re.compile(r'"Weekday"\s*=>\s*(\d+)')
_HOUR_RE = re.compile(r'"Hour"\s*=>\s*(\d+)')
_MINUTE_RE = re.compile(r'"Minute"\s*=>\s*(\d+)')
_PATH_RE = re.compile(r"^\s*path = (.+)$", re.MULTILINE)
_PROGRAM_RE = re.compile(r"^\s*program = (.+)$", re.MULTILINE)
_STDOUT_PATH_RE = re.compile(r"^\s*stdout path = (.+)$", re.MULTILINE)
_STDERR_PATH_RE = re.compile(r"^\s*stderr path = (.+)$", re.MULTILINE)

EnvironmentFactory = Callable[[Path, Path, str], dict[str, str]]
ProgramArgumentsFactory = Callable[[Path, str, str], list[str]]
WorkingDirectoryFactory = Callable[[Path], Path]


@dataclass(frozen=True)
class ScheduleExpectation:
    weekdays: tuple[int, ...]
    hour: int
    minute: int


@dataclass(frozen=True)
class LaunchAgentSpec:
    label: str
    template_path: Path
    log_stem: str
    build_program_arguments: ProgramArgumentsFactory
    working_directory_factory: WorkingDirectoryFactory
    schedule: Optional[ScheduleExpectation] = None
    process_type: str = "Background"
    run_at_load: bool = False
    keep_alive: bool = False
    build_environment_variables: Optional[EnvironmentFactory] = None
    logs_under_home: bool = False

    @property
    def target_file_name(self) -> str:
        return f"{self.label}.plist"


@dataclass(frozen=True)
class RenderedLaunchAgent:
    spec: LaunchAgentSpec
    project_root: Path
    target_path: Path
    document: dict
    content: bytes
    python_bin: str
    node_bin: str
    dashboard_password: str


@dataclass(frozen=True)
class LaunchctlState:
    label: str
    output: str
    weekdays: tuple[int, ...]
    hours: tuple[int, ...]
    minutes: tuple[int, ...]
    path: Optional[str] = None
    program: Optional[str] = None
    stdout_path: Optional[str] = None
    stderr_path: Optional[str] = None


RunCommand = Callable[[Sequence[str]], subprocess.CompletedProcess]


def _build_scheduler_environment(
    project_root: Path, home_dir: Path, dashboard_password: str
) -> dict[str, str]:
    del dashboard_password
    return {
        "PYTHONUNBUFFERED": "1",
        "NEOTRADE3_ENV_FILE": str(
            home_dir / "Library" / "Application Support" / "NeoTrade3" / "env.secrets"
        ),
    }


def _build_gateway_environment(
    project_root: Path, home_dir: Path, dashboard_password: str
) -> dict[str, str]:
    del project_root, home_dir
    return {
        "DASHBOARD_PASSWORD": dashboard_password,
    }


def _project_root_directory(project_root: Path) -> Path:
    return project_root


def _dashboard_directory(project_root: Path) -> Path:
    return project_root / "neotrade3-dashboard"


def _scheduler_program_arguments(job_id: str) -> ProgramArgumentsFactory:
    def _build(project_root: Path, python_bin: str, node_bin: str) -> list[str]:
        del project_root, node_bin
        return [
            python_bin,
            "-m",
            "neotrade3.scheduler.task_scheduler",
            "--run-once",
            job_id,
        ]

    return _build


def _api_program_arguments(project_root: Path, python_bin: str, node_bin: str) -> list[str]:
    del project_root, node_bin
    return [
        python_bin,
        "-m",
        "apps.api.main",
        "--host",
        "127.0.0.1",
        "--port",
        "18031",
    ]


def _gateway_program_arguments(project_root: Path, python_bin: str, node_bin: str) -> list[str]:
    del python_bin
    return [
        node_bin,
        str(project_root / "neotrade3-dashboard" / "server" / "gateway.js"),
        "--host",
        "127.0.0.1",
        "--port",
        "5174",
        "--api-base",
        "http://127.0.0.1:18031",
        "--dist-dir",
        str(project_root / "neotrade3-dashboard" / "dist"),
    ]


def build_launch_agent_specs(project_root: Path) -> list[LaunchAgentSpec]:
    template_dir = project_root / "config" / "launchd"
    return [
        LaunchAgentSpec(
            label="com.neotrade3.scheduler",
            template_path=template_dir / "com.neotrade3.scheduler.plist.template",
            log_stem="neotrade3_scheduler",
            build_program_arguments=_scheduler_program_arguments("update_daily_prices_authoritative"),
            working_directory_factory=_project_root_directory,
            schedule=ScheduleExpectation(
                weekdays=EXPECTED_WEEKDAYS,
                hour=15,
                minute=45,
            ),
            build_environment_variables=_build_scheduler_environment,
            logs_under_home=True,
        ),
        LaunchAgentSpec(
            label="com.neotrade3.trade_execution_rt",
            template_path=template_dir / "com.neotrade3.trade_execution_rt.plist.template",
            log_stem="neotrade3_trade_execution_rt",
            build_program_arguments=_scheduler_program_arguments("trade_execution_rt_0935"),
            working_directory_factory=_project_root_directory,
            schedule=ScheduleExpectation(
                weekdays=EXPECTED_WEEKDAYS,
                hour=9,
                minute=35,
            ),
            build_environment_variables=_build_scheduler_environment,
        ),
        LaunchAgentSpec(
            label="com.neotrade3.api",
            template_path=template_dir / "com.neotrade3.api.plist.template",
            log_stem="neotrade3_api",
            build_program_arguments=_api_program_arguments,
            working_directory_factory=_project_root_directory,
            run_at_load=True,
            keep_alive=True,
            build_environment_variables=_build_scheduler_environment,
        ),
        LaunchAgentSpec(
            label="com.neotrade3.frontend_gateway",
            template_path=template_dir / "com.neotrade3.frontend_gateway.plist.template",
            log_stem="neotrade3_frontend_gateway",
            build_program_arguments=_gateway_program_arguments,
            working_directory_factory=_dashboard_directory,
            run_at_load=True,
            keep_alive=True,
            build_environment_variables=_build_gateway_environment,
        ),
    ]


def resolve_python_bin(python_bin: str | Path | None = None) -> str:
    candidate = Path(str(python_bin if python_bin is not None else sys.executable))
    return str(candidate.expanduser())


def resolve_node_bin(node_bin: str | Path | None = None) -> str:
    if node_bin is not None:
        return str(Path(str(node_bin)).expanduser())
    detected = shutil.which("node")
    if detected:
        return detected
    return "/opt/homebrew/bin/node"


def resolve_dashboard_password(dashboard_password: str | None = None) -> str:
    value = dashboard_password if dashboard_password is not None else os.environ.get("DASHBOARD_PASSWORD")
    if not value:
        raise ValueError("缺少 DASHBOARD_PASSWORD，无法渲染 frontend_gateway 模板")
    return value


def render_launch_agent(
    spec: LaunchAgentSpec,
    *,
    project_root: Path,
    home_dir: Optional[Path] = None,
    target_dir: Optional[Path] = None,
    python_bin: str | Path | None = None,
    node_bin: str | Path | None = None,
    dashboard_password: str | None = None,
    daemon_user: str | None = None,
) -> RenderedLaunchAgent:
    home = (home_dir or Path.home()).expanduser()
    target_root = target_dir or DEFAULT_TARGET_DIR
    resolved_python_bin = resolve_python_bin(python_bin)
    resolved_node_bin = resolve_node_bin(node_bin)
    text = spec.template_path.read_text(encoding="utf-8")
    if DASHBOARD_PASSWORD_TOKEN in text:
        resolved_dashboard_password = resolve_dashboard_password(dashboard_password)
    else:
        resolved_dashboard_password = dashboard_password or ""
    rendered_text = (
        text.replace(HOME_TOKEN, str(home))
        .replace(PROJECT_ROOT_TOKEN, str(project_root))
        .replace(PYTHON_BIN_TOKEN, resolved_python_bin)
        .replace(NODE_BIN_TOKEN, resolved_node_bin)
        .replace(DASHBOARD_PASSWORD_TOKEN, resolved_dashboard_password)
    )
    document = plistlib.loads(rendered_text.encode("utf-8"))
    if daemon_user:
        document["UserName"] = str(daemon_user)
    errors = validate_launch_agent_document(
        document,
        spec=spec,
        project_root=project_root,
        home_dir=home,
        expected_python_bin=resolved_python_bin,
        expected_node_bin=resolved_node_bin,
        expected_dashboard_password=resolved_dashboard_password,
    )
    if errors:
        raise ValueError(f"{spec.label} 模板校验失败: {'; '.join(errors)}")
    content = plistlib.dumps(
        document,
        fmt=plistlib.FMT_XML,
        sort_keys=False,
        skipkeys=False,
    )
    return RenderedLaunchAgent(
        spec=spec,
        project_root=project_root,
        target_path=target_root / spec.target_file_name,
        document=document,
        content=content,
        python_bin=resolved_python_bin,
        node_bin=resolved_node_bin,
        dashboard_password=resolved_dashboard_password,
    )


def render_launch_agents(
    *,
    project_root: Path,
    home_dir: Optional[Path] = None,
    target_dir: Optional[Path] = None,
    python_bin: str | Path | None = None,
    node_bin: str | Path | None = None,
    dashboard_password: str | None = None,
    labels: Optional[Sequence[str]] = None,
    daemon_user: str | None = None,
) -> list[RenderedLaunchAgent]:
    specs = build_launch_agent_specs(project_root)
    if labels is not None:
        normalized = [str(item).strip() for item in labels if str(item).strip()]
        if not normalized:
            raise ValueError("labels 不能为空")
        available = {spec.label for spec in specs}
        unknown = [label for label in normalized if label not in available]
        if unknown:
            raise ValueError(f"未知 label: {unknown}")
        selected = set(normalized)
        specs = [spec for spec in specs if spec.label in selected]
    return [
        render_launch_agent(
            spec,
            project_root=project_root,
            home_dir=home_dir,
            target_dir=target_dir,
            python_bin=python_bin,
            node_bin=node_bin,
            dashboard_password=dashboard_password,
            daemon_user=daemon_user,
        )
        for spec in specs
    ]


def validate_launch_agent_document(
    document: dict,
    *,
    spec: LaunchAgentSpec,
    project_root: Path,
    home_dir: Path,
    expected_python_bin: str | Path,
    expected_node_bin: str | Path,
    expected_dashboard_password: str,
) -> list[str]:
    errors: list[str] = []
    if str(document.get("Label") or "") != spec.label:
        errors.append("Label 不匹配")
    expected_working_directory = spec.working_directory_factory(project_root)
    if str(document.get("WorkingDirectory") or "") != str(expected_working_directory):
        errors.append("WorkingDirectory 不匹配")
    if document.get("RunAtLoad") is not spec.run_at_load:
        errors.append(f"RunAtLoad 必须为 {str(spec.run_at_load).lower()}")
    if str(document.get("ProcessType") or "") != spec.process_type:
        errors.append(f"ProcessType 必须为 {spec.process_type}")
    if bool(document.get("KeepAlive")) is not spec.keep_alive:
        errors.append(f"KeepAlive 必须为 {str(spec.keep_alive).lower()}")

    args = [str(item) for item in (document.get("ProgramArguments") or [])]
    resolved_python_bin = resolve_python_bin(expected_python_bin)
    resolved_node_bin = resolve_node_bin(expected_node_bin)
    expected_args = spec.build_program_arguments(
        project_root,
        resolved_python_bin,
        resolved_node_bin,
    )
    if args != expected_args:
        errors.append("ProgramArguments 不匹配")

    expected_env = (
        spec.build_environment_variables(
            project_root,
            home_dir,
            expected_dashboard_password,
        )
        if spec.build_environment_variables is not None
        else None
    )
    env = document.get("EnvironmentVariables")
    if expected_env is None:
        if env not in (None, {}):
            errors.append("EnvironmentVariables 应为空")
    elif not isinstance(env, dict):
        errors.append("EnvironmentVariables 不是 dict")
    else:
        for key, value in expected_env.items():
            if str(env.get(key) or "") != str(value):
                errors.append(f"{key} 不匹配")

    if spec.logs_under_home:
        expected_log_dir = home_dir / "Library" / "Logs" / "NeoTrade3"
    else:
        expected_log_dir = project_root / "var" / "log"
    expected_stdout = expected_log_dir / f"{spec.log_stem}.out.log"
    expected_stderr = expected_log_dir / f"{spec.log_stem}.err.log"
    if str(document.get("StandardOutPath") or "") != str(expected_stdout):
        errors.append("StandardOutPath 不匹配")
    if str(document.get("StandardErrorPath") or "") != str(expected_stderr):
        errors.append("StandardErrorPath 不匹配")

    calendar_entries = extract_calendar_entries(document)
    if spec.schedule is None:
        if calendar_entries:
            errors.append("StartCalendarInterval 应为空")
    else:
        weekdays = tuple(entry.get("Weekday") for entry in calendar_entries if "Weekday" in entry)
        hours = {int(entry.get("Hour")) for entry in calendar_entries if "Hour" in entry}
        minutes = {int(entry.get("Minute")) for entry in calendar_entries if "Minute" in entry}
        if weekdays != spec.schedule.weekdays:
            errors.append(f"Weekday 必须为 {list(spec.schedule.weekdays)}")
        if hours != {spec.schedule.hour}:
            errors.append(f"Hour 必须为 {spec.schedule.hour}")
        if minutes != {spec.schedule.minute}:
            errors.append(f"Minute 必须为 {spec.schedule.minute}")

    return errors


def extract_calendar_entries(document: dict) -> list[dict]:
    raw_entries = document.get("StartCalendarInterval")
    if isinstance(raw_entries, dict):
        return [raw_entries]
    if isinstance(raw_entries, list):
        return [entry for entry in raw_entries if isinstance(entry, dict)]
    return []


def compare_installed_document(
    rendered: RenderedLaunchAgent,
    installed_document: dict,
    *,
    home_dir: Optional[Path] = None,
) -> list[str]:
    errors = validate_launch_agent_document(
        installed_document,
        spec=rendered.spec,
        project_root=rendered.project_root,
        home_dir=(home_dir or Path.home()).expanduser(),
        expected_python_bin=rendered.python_bin,
        expected_node_bin=rendered.node_bin,
        expected_dashboard_password=rendered.dashboard_password,
    )
    if errors:
        return errors
    if installed_document != rendered.document:
        return ["已安装 plist 与仓库模板渲染结果不一致"]
    return []


def write_rendered_launch_agent(rendered: RenderedLaunchAgent) -> bool:
    rendered.target_path.parent.mkdir(parents=True, exist_ok=True)
    before = rendered.target_path.read_bytes() if rendered.target_path.exists() else None
    if before == rendered.content:
        return False
    rendered.target_path.write_bytes(rendered.content)
    return True


def load_installed_document(path: Path) -> dict:
    return plistlib.loads(path.read_bytes())


def default_run_command(command: Sequence[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        list(command),
        text=True,
        capture_output=True,
        check=False,
    )


def _extract_launchctl_value(pattern: re.Pattern[str], output: str) -> Optional[str]:
    match = pattern.search(output)
    if match is None:
        return None
    return match.group(1).strip()


def install_launch_agents(
    rendered_agents: Sequence[RenderedLaunchAgent],
    *,
    uid: Optional[int] = None,
    domain: str = "gui",
    run_command: RunCommand = default_run_command,
) -> list[LaunchctlState]:
    launchd_uid = int(uid if uid is not None else os.getuid())
    states: list[LaunchctlState] = []
    if domain not in {"gui", "system"}:
        raise ValueError(f"unsupported launchctl domain: {domain}")
    for rendered in rendered_agents:
        write_rendered_launch_agent(rendered)
        if domain == "system":
            service_target = f"system/{rendered.spec.label}"
            bootstrap_domain = "system"
            inspect_uid: int | None = None
        else:
            service_target = f"gui/{launchd_uid}/{rendered.spec.label}"
            bootstrap_domain = f"gui/{launchd_uid}"
            inspect_uid = launchd_uid
        print_result = run_command(["launchctl", "print", service_target])
        if print_result.returncode == 0:
            bootout_result = run_command(["launchctl", "bootout", service_target])
            if bootout_result.returncode != 0:
                raise RuntimeError(
                    f"{rendered.spec.label} bootout 失败: {bootout_result.stderr.strip() or bootout_result.stdout.strip()}"
                )
        bootstrap_result = run_command(
            ["launchctl", "bootstrap", bootstrap_domain, str(rendered.target_path)]
        )
        if bootstrap_result.returncode != 0:
            raise RuntimeError(
                f"{rendered.spec.label} bootstrap 失败: {bootstrap_result.stderr.strip() or bootstrap_result.stdout.strip()}"
            )
        state = inspect_launchctl_state(
            rendered.spec.label,
            uid=inspect_uid,
            domain=domain,
            run_command=run_command,
        )
        validate_launchctl_state(state, rendered.spec, rendered=rendered)
        states.append(state)
    return states


def inspect_launchctl_state(
    label: str,
    *,
    uid: Optional[int] = None,
    domain: str = "gui",
    run_command: RunCommand = default_run_command,
) -> LaunchctlState:
    launchd_uid = int(uid if uid is not None else os.getuid())
    if domain not in {"gui", "system"}:
        raise ValueError(f"unsupported launchctl domain: {domain}")
    if domain == "system":
        target = f"system/{label}"
    else:
        target = f"gui/{launchd_uid}/{label}"
    result = run_command(["launchctl", "print", target])
    if result.returncode != 0:
        raise RuntimeError(
            f"{label} launchctl print 失败: {result.stderr.strip() or result.stdout.strip()}"
        )
    output = result.stdout
    weekdays = tuple(sorted({int(value) for value in _WEEKDAY_RE.findall(output)}))
    hours = tuple(sorted({int(value) for value in _HOUR_RE.findall(output)}))
    minutes = tuple(sorted({int(value) for value in _MINUTE_RE.findall(output)}))
    return LaunchctlState(
        label=label,
        output=output,
        weekdays=weekdays,
        hours=hours,
        minutes=minutes,
        path=_extract_launchctl_value(_PATH_RE, output),
        program=_extract_launchctl_value(_PROGRAM_RE, output),
        stdout_path=_extract_launchctl_value(_STDOUT_PATH_RE, output),
        stderr_path=_extract_launchctl_value(_STDERR_PATH_RE, output),
    )


def validate_launchctl_state(
    state: LaunchctlState,
    spec: LaunchAgentSpec,
    *,
    rendered: Optional[RenderedLaunchAgent] = None,
) -> None:
    errors: list[str] = []
    if spec.schedule is not None:
        if state.weekdays != spec.schedule.weekdays:
            errors.append(f"Weekday={state.weekdays}")
        if state.hours != (spec.schedule.hour,):
            errors.append(f"Hour={state.hours}")
        if state.minutes != (spec.schedule.minute,):
            errors.append(f"Minute={state.minutes}")
    if rendered is not None:
        expected_program = rendered.document["ProgramArguments"][0]
        expected_stdout = rendered.document["StandardOutPath"]
        expected_stderr = rendered.document["StandardErrorPath"]
        expected_path = str(rendered.target_path)
        if state.path != expected_path:
            errors.append(f"path={state.path!r}")
        if state.program != expected_program:
            errors.append(f"program={state.program!r}")
        if state.stdout_path != expected_stdout:
            errors.append(f"stdout path={state.stdout_path!r}")
        if state.stderr_path != expected_stderr:
            errors.append(f"stderr path={state.stderr_path!r}")
    if errors:
        raise RuntimeError(f"{spec.label} launchctl 校验失败: {', '.join(errors)}")


def format_check_report(
    rendered_agents: Sequence[RenderedLaunchAgent],
    *,
    home_dir: Optional[Path] = None,
    target_dir: Optional[Path] = None,
) -> list[str]:
    report: list[str] = []
    for rendered in rendered_agents:
        report.append(f"[template] {rendered.spec.label}: ok")
        installed_path = (target_dir or DEFAULT_TARGET_DIR) / rendered.spec.target_file_name
        if installed_path.exists():
            installed_document = load_installed_document(installed_path)
            errors = compare_installed_document(
                rendered,
                installed_document,
                home_dir=home_dir,
            )
            if errors:
                report.append(f"[installed] {rendered.spec.label}: {'; '.join(errors)}")
            else:
                report.append(f"[installed] {rendered.spec.label}: ok")
        else:
            report.append(f"[installed] {rendered.spec.label}: missing")
    return report
