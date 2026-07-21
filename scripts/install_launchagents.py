from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import sys

from neotrade3.operations.launchd_sync import (
    DEFAULT_TARGET_DIR,
    format_check_report,
    inspect_launchctl_state,
    install_launch_agents,
    render_launch_agents,
    validate_launchctl_state,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROJECT_PYTHON = PROJECT_ROOT / ".venv" / "bin" / "python"
DEFAULT_NODE_BIN = shutil.which("node") or "/opt/homebrew/bin/node"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Render, validate, and install NeoTrade3 launchd agents."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    render_parser = subparsers.add_parser("render", help="Render plist files into a directory.")
    render_parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory that receives rendered plist files.",
    )
    render_parser.add_argument(
        "--python-bin",
        default=str(DEFAULT_PROJECT_PYTHON),
        help=(
            "Python executable path written into ProgramArguments. "
            f"Default: {DEFAULT_PROJECT_PYTHON}"
        ),
    )
    render_parser.add_argument(
        "--node-bin",
        default=str(DEFAULT_NODE_BIN),
        help=f"Node executable path written into ProgramArguments. Default: {DEFAULT_NODE_BIN}",
    )
    render_parser.add_argument(
        "--home-dir",
        default=str(Path.home()),
        help="Home directory used to render {{HOME}} token. Default: current user's home",
    )
    render_parser.add_argument(
        "--labels",
        default="",
        help="Comma-separated labels to render (empty means all). Example: com.neotrade3.scheduler",
    )
    render_parser.add_argument(
        "--daemon-user",
        default="",
        help="When rendering LaunchDaemons, write UserName into plist. Empty means omit.",
    )

    check_parser = subparsers.add_parser(
        "check",
        help="Validate templates and compare them with installed plist files.",
    )
    check_parser.add_argument(
        "--target-dir",
        default=str(DEFAULT_TARGET_DIR),
        help=f"Installed plist directory to compare against. Default: {DEFAULT_TARGET_DIR}",
    )
    check_parser.add_argument(
        "--launchctl",
        action="store_true",
        help="Also inspect current launchctl state for the managed labels.",
    )
    check_parser.add_argument(
        "--domain",
        default="gui",
        choices=("gui", "system"),
        help="launchctl domain to inspect (gui or system). Default: gui",
    )
    check_parser.add_argument(
        "--python-bin",
        default=str(DEFAULT_PROJECT_PYTHON),
        help=(
            "Python executable path expected in ProgramArguments. "
            f"Default: {DEFAULT_PROJECT_PYTHON}"
        ),
    )
    check_parser.add_argument(
        "--node-bin",
        default=str(DEFAULT_NODE_BIN),
        help=f"Node executable path expected in ProgramArguments. Default: {DEFAULT_NODE_BIN}",
    )
    check_parser.add_argument(
        "--home-dir",
        default=str(Path.home()),
        help="Home directory used to render {{HOME}} token. Default: current user's home",
    )
    check_parser.add_argument(
        "--labels",
        default="",
        help="Comma-separated labels to check (empty means all). Example: com.neotrade3.scheduler",
    )
    check_parser.add_argument(
        "--daemon-user",
        default="",
        help="When checking LaunchDaemons, render with the same UserName. Empty means omit.",
    )

    install_parser = subparsers.add_parser(
        "install",
        help="Install rendered plist files into LaunchAgents and reload them.",
    )
    install_parser.add_argument(
        "--target-dir",
        default=str(DEFAULT_TARGET_DIR),
        help=f"LaunchAgents target directory. Default: {DEFAULT_TARGET_DIR}",
    )
    install_parser.add_argument(
        "--domain",
        default="gui",
        choices=("gui", "system"),
        help="launchctl domain to bootstrap (gui or system). Default: gui",
    )
    install_parser.add_argument(
        "--python-bin",
        default=str(DEFAULT_PROJECT_PYTHON),
        help=(
            "Python executable path written into ProgramArguments. "
            f"Default: {DEFAULT_PROJECT_PYTHON}"
        ),
    )
    install_parser.add_argument(
        "--node-bin",
        default=str(DEFAULT_NODE_BIN),
        help=f"Node executable path written into ProgramArguments. Default: {DEFAULT_NODE_BIN}",
    )
    install_parser.add_argument(
        "--home-dir",
        default=str(Path.home()),
        help="Home directory used to render {{HOME}} token. Default: current user's home",
    )
    install_parser.add_argument(
        "--labels",
        default="",
        help="Comma-separated labels to install (empty means all). Example: com.neotrade3.scheduler",
    )
    install_parser.add_argument(
        "--daemon-user",
        default="",
        help="When installing LaunchDaemons, write UserName into plist. Required for --domain system.",
    )

    return parser


def cmd_render(
    output_dir: Path,
    *,
    home_dir: Path,
    labels: list[str] | None,
    daemon_user: str | None,
    python_bin: str,
    node_bin: str,
) -> int:
    rendered_agents = render_launch_agents(
        project_root=PROJECT_ROOT,
        home_dir=home_dir,
        target_dir=output_dir,
        python_bin=python_bin,
        node_bin=node_bin,
        labels=labels,
        daemon_user=daemon_user,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    for rendered in rendered_agents:
        rendered.target_path.parent.mkdir(parents=True, exist_ok=True)
        rendered.target_path.write_bytes(rendered.content)
        print(f"[rendered] {rendered.spec.label} -> {rendered.target_path}")
    return 0


def cmd_check(
    target_dir: Path,
    *,
    inspect_launchctl: bool,
    domain: str,
    home_dir: Path,
    labels: list[str] | None,
    daemon_user: str | None,
    python_bin: str,
    node_bin: str,
) -> int:
    rendered_agents = render_launch_agents(
        project_root=PROJECT_ROOT,
        home_dir=home_dir,
        target_dir=target_dir,
        python_bin=python_bin,
        node_bin=node_bin,
        labels=labels,
        daemon_user=daemon_user,
    )
    report = format_check_report(
        rendered_agents,
        home_dir=Path.home(),
        target_dir=target_dir,
    )
    has_error = False
    for line in report:
        print(line)
        if ": missing" in line or (": " in line and not line.endswith(": ok")):
            has_error = True

    if inspect_launchctl:
        for rendered in rendered_agents:
            try:
                state = inspect_launchctl_state(rendered.spec.label, domain=domain)
            except RuntimeError as exc:
                print(f"[launchctl] {rendered.spec.label}: {exc}")
                has_error = True
                continue
            try:
                validate_launchctl_state(state, rendered.spec, rendered=rendered)
            except RuntimeError as exc:
                print(f"[launchctl] {rendered.spec.label}: {exc}")
                has_error = True
                continue
            print(f"[launchctl] {rendered.spec.label}: ok")
    return 1 if has_error else 0


def cmd_install(
    target_dir: Path,
    *,
    domain: str,
    home_dir: Path,
    labels: list[str] | None,
    daemon_user: str | None,
    python_bin: str,
    node_bin: str,
) -> int:
    rendered_agents = render_launch_agents(
        project_root=PROJECT_ROOT,
        home_dir=home_dir,
        target_dir=target_dir,
        python_bin=python_bin,
        node_bin=node_bin,
        labels=labels,
        daemon_user=daemon_user,
    )
    states = install_launch_agents(rendered_agents, domain=domain)
    for state in states:
        print(
            f"[installed] {state.label}: weekdays={list(state.weekdays)} "
            f"hours={list(state.hours)} minutes={list(state.minutes)}"
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    labels = None
    if str(getattr(args, "labels", "") or "").strip():
        labels = [item.strip() for item in str(args.labels).split(",") if item.strip()]
    daemon_user = str(getattr(args, "daemon_user", "") or "").strip() or None
    if args.command == "render":
        return cmd_render(
            Path(args.output_dir).expanduser(),
            home_dir=Path(args.home_dir).expanduser(),
            labels=labels,
            daemon_user=daemon_user,
            python_bin=str(args.python_bin),
            node_bin=str(args.node_bin),
        )
    if args.command == "check":
        return cmd_check(
            Path(args.target_dir).expanduser(),
            inspect_launchctl=bool(args.launchctl),
            domain=str(args.domain),
            home_dir=Path(args.home_dir).expanduser(),
            labels=labels,
            daemon_user=daemon_user,
            python_bin=str(args.python_bin),
            node_bin=str(args.node_bin),
        )
    if args.command == "install":
        if str(args.domain) == "system":
            if Path(args.home_dir).expanduser() == Path("/var/root"):
                raise SystemExit("--domain system 必须显式指定 --home-dir=/Users/<your_user>")
            if not daemon_user:
                raise SystemExit("--domain system 必须显式指定 --daemon-user=<your_user>")
        return cmd_install(
            Path(args.target_dir).expanduser(),
            domain=str(args.domain),
            home_dir=Path(args.home_dir).expanduser(),
            labels=labels,
            daemon_user=daemon_user,
            python_bin=str(args.python_bin),
            node_bin=str(args.node_bin),
        )
    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
