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

    return parser


def cmd_render(output_dir: Path, *, python_bin: str, node_bin: str) -> int:
    rendered_agents = render_launch_agents(
        project_root=PROJECT_ROOT,
        target_dir=output_dir,
        python_bin=python_bin,
        node_bin=node_bin,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    for rendered in rendered_agents:
        rendered.target_path.parent.mkdir(parents=True, exist_ok=True)
        rendered.target_path.write_bytes(rendered.content)
        print(f"[rendered] {rendered.spec.label} -> {rendered.target_path}")
    return 0


def cmd_check(target_dir: Path, *, inspect_launchctl: bool, python_bin: str, node_bin: str) -> int:
    rendered_agents = render_launch_agents(
        project_root=PROJECT_ROOT,
        target_dir=target_dir,
        python_bin=python_bin,
        node_bin=node_bin,
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
                state = inspect_launchctl_state(rendered.spec.label)
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


def cmd_install(target_dir: Path, *, python_bin: str, node_bin: str) -> int:
    rendered_agents = render_launch_agents(
        project_root=PROJECT_ROOT,
        target_dir=target_dir,
        python_bin=python_bin,
        node_bin=node_bin,
    )
    states = install_launch_agents(rendered_agents)
    for state in states:
        print(
            f"[installed] {state.label}: weekdays={list(state.weekdays)} "
            f"hours={list(state.hours)} minutes={list(state.minutes)}"
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "render":
        return cmd_render(
            Path(args.output_dir).expanduser(),
            python_bin=str(args.python_bin),
            node_bin=str(args.node_bin),
        )
    if args.command == "check":
        return cmd_check(
            Path(args.target_dir).expanduser(),
            inspect_launchctl=bool(args.launchctl),
            python_bin=str(args.python_bin),
            node_bin=str(args.node_bin),
        )
    if args.command == "install":
        return cmd_install(
            Path(args.target_dir).expanduser(),
            python_bin=str(args.python_bin),
            node_bin=str(args.node_bin),
        )
    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
