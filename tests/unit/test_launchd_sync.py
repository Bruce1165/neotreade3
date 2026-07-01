from __future__ import annotations

from pathlib import Path
import plistlib

import pytest

from neotrade3.operations.launchd_sync import (
    LaunchctlState,
    build_launch_agent_specs,
    compare_installed_document,
    render_launch_agents,
    validate_launchctl_state,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_render_launch_agents_uses_monday_to_friday_and_existing_log_paths(tmp_path: Path) -> None:
    home_dir = tmp_path / "home"
    python_bin = "/tmp/neotrade3-venv/bin/python"
    node_bin = "/opt/homebrew/bin/node"
    dashboard_password = "test-dashboard-password"
    rendered_agents = render_launch_agents(
        project_root=PROJECT_ROOT,
        home_dir=home_dir,
        target_dir=tmp_path / "LaunchAgents",
        python_bin=python_bin,
        node_bin=node_bin,
        dashboard_password=dashboard_password,
    )

    assert [agent.spec.label for agent in rendered_agents] == [
        "com.neotrade3.scheduler",
        "com.neotrade3.trade_execution_rt",
        "com.neotrade3.api",
        "com.neotrade3.frontend_gateway",
    ]

    scheduler = rendered_agents[0]
    trade_execution = rendered_agents[1]
    api = rendered_agents[2]
    gateway = rendered_agents[3]

    assert [entry["Weekday"] for entry in scheduler.document["StartCalendarInterval"]] == [
        1,
        2,
        3,
        4,
        5,
    ]
    assert [entry["Minute"] for entry in scheduler.document["StartCalendarInterval"]] == [
        45,
        45,
        45,
        45,
        45,
    ]
    assert scheduler.document["ProgramArguments"][0] == python_bin
    assert scheduler.document["ProgramArguments"][-1] == "update_daily_prices_authoritative"
    assert trade_execution.document["ProgramArguments"][0] == python_bin
    assert scheduler.document["StandardErrorPath"] == str(
        PROJECT_ROOT / "var" / "log" / "neotrade3_scheduler.err.log"
    )
    assert trade_execution.document["StandardErrorPath"] == str(
        PROJECT_ROOT / "var" / "log" / "neotrade3_trade_execution_rt.err.log"
    )
    assert trade_execution.document["EnvironmentVariables"]["NEOTRADE3_ENV_FILE"] == str(
        home_dir / "Library" / "Application Support" / "NeoTrade3" / "env.secrets"
    )
    assert api.document["ProgramArguments"] == [
        python_bin,
        "-m",
        "apps.api.main",
        "--host",
        "127.0.0.1",
        "--port",
        "18030",
    ]
    assert api.document["KeepAlive"] is True
    assert gateway.document["ProgramArguments"][0] == node_bin
    assert gateway.document["ProgramArguments"][1] == str(
        PROJECT_ROOT / "neotrade3-dashboard" / "server" / "gateway.js"
    )
    assert gateway.document["WorkingDirectory"] == str(
        PROJECT_ROOT / "neotrade3-dashboard"
    )
    assert gateway.document["KeepAlive"] is True
    assert gateway.document["EnvironmentVariables"]["DASHBOARD_PASSWORD"] == dashboard_password


def test_compare_installed_document_detects_weekday_drift(tmp_path: Path) -> None:
    rendered_agents = render_launch_agents(
        project_root=PROJECT_ROOT,
        home_dir=tmp_path / "home",
        target_dir=tmp_path / "LaunchAgents",
        python_bin="/tmp/neotrade3-venv/bin/python",
        node_bin="/opt/homebrew/bin/node",
        dashboard_password="test-dashboard-password",
    )
    rendered = rendered_agents[0]
    installed = plistlib.loads(rendered.content)
    installed["StartCalendarInterval"][0]["Weekday"] = 2
    installed["StartCalendarInterval"][-1]["Weekday"] = 6

    errors = compare_installed_document(
        rendered,
        installed,
        home_dir=tmp_path / "home",
    )

    assert errors == ["Weekday 必须为 [1, 2, 3, 4, 5]"]


def test_validate_launchctl_state_rejects_non_weekday_schedule() -> None:
    spec = build_launch_agent_specs(PROJECT_ROOT)[0]
    state = LaunchctlState(
        label=spec.label,
        output="",
        weekdays=(2, 3, 4, 5, 6),
        hours=(15,),
        minutes=(45,),
    )

    with pytest.raises(RuntimeError, match="Weekday"):
        validate_launchctl_state(state, spec)


def test_validate_launchctl_state_allows_daemon_specs_with_matching_runtime_binding(
    tmp_path: Path,
) -> None:
    rendered = render_launch_agents(
        project_root=PROJECT_ROOT,
        home_dir=tmp_path / "home",
        target_dir=tmp_path / "LaunchAgents",
        python_bin="/tmp/neotrade3-venv/bin/python",
        node_bin="/opt/homebrew/bin/node",
        dashboard_password="test-dashboard-password",
    )[2]
    spec = rendered.spec
    state = LaunchctlState(
        label=spec.label,
        output="",
        weekdays=(),
        hours=(),
        minutes=(),
        path=str(rendered.target_path),
        program=rendered.document["ProgramArguments"][0],
        stdout_path=rendered.document["StandardOutPath"],
        stderr_path=rendered.document["StandardErrorPath"],
    )

    validate_launchctl_state(state, spec, rendered=rendered)


def test_validate_launchctl_state_rejects_daemon_path_drift(tmp_path: Path) -> None:
    rendered = render_launch_agents(
        project_root=PROJECT_ROOT,
        home_dir=tmp_path / "home",
        target_dir=tmp_path / "LaunchAgents",
        python_bin="/tmp/neotrade3-venv/bin/python",
        node_bin="/opt/homebrew/bin/node",
        dashboard_password="test-dashboard-password",
    )[2]
    state = LaunchctlState(
        label=rendered.spec.label,
        output="",
        weekdays=(),
        hours=(),
        minutes=(),
        path=str(tmp_path / "LaunchAgents" / "com.neotrade3.api.recover.plist"),
        program=rendered.document["ProgramArguments"][0],
        stdout_path=rendered.document["StandardOutPath"],
        stderr_path=rendered.document["StandardErrorPath"],
    )

    with pytest.raises(RuntimeError, match="path="):
        validate_launchctl_state(state, rendered.spec, rendered=rendered)
