from __future__ import annotations

import json
import platform
import sys
from typing import Any

REQUIRED_PYTHON_MAJOR = 3
REQUIRED_PYTHON_MINOR = 10
REQUIRED_PYTHON_SERIES = "3.10.x"


def build_python_runtime_payload(*, entrypoint: str) -> dict[str, Any]:
    return {
        "entrypoint": str(entrypoint),
        "python_executable": sys.executable,
        "python_version": platform.python_version(),
        "python_prefix": sys.prefix,
        "python_base_prefix": sys.base_prefix,
        "venv_active": bool(sys.prefix != sys.base_prefix),
    }


def is_supported_python_310() -> bool:
    return (
        int(sys.version_info.major) == REQUIRED_PYTHON_MAJOR
        and int(sys.version_info.minor) == REQUIRED_PYTHON_MINOR
    )


def format_python_310_error(*, entrypoint: str) -> str:
    return (
        f"{entrypoint} requires Python {REQUIRED_PYTHON_SERIES}; "
        f"got {platform.python_version()} via {sys.executable}. "
        "Use PROJECT_ROOT/.venv/bin/python."
    )


def log_python_runtime(*, entrypoint: str, logger: Any | None = None) -> dict[str, Any]:
    payload = build_python_runtime_payload(entrypoint=entrypoint)
    line = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    if logger is not None:
        logger.info("python_runtime %s", line)
    else:
        print(line)
    return payload


def require_python_310(*, entrypoint: str) -> None:
    if not is_supported_python_310():
        raise RuntimeError(format_python_310_error(entrypoint=entrypoint))
