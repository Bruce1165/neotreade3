from __future__ import annotations

from types import SimpleNamespace

import pytest

from neotrade3.common import python_runtime


def test_require_python_310_accepts_python_310(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_sys = SimpleNamespace(
        version_info=SimpleNamespace(major=3, minor=10, micro=12),
        executable="/tmp/neotrade3/.venv/bin/python",
        prefix="/tmp/neotrade3/.venv",
        base_prefix="/Library/Developer/CommandLineTools/usr",
    )
    monkeypatch.setattr(python_runtime, "sys", fake_sys)
    monkeypatch.setattr(python_runtime.platform, "python_version", lambda: "3.10.12")

    python_runtime.require_python_310(entrypoint="tests.entrypoint")


def test_require_python_310_rejects_python_311(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_sys = SimpleNamespace(
        version_info=SimpleNamespace(major=3, minor=11, micro=9),
        executable="/usr/local/bin/python3.11",
        prefix="/usr/local",
        base_prefix="/usr/local",
    )
    monkeypatch.setattr(python_runtime, "sys", fake_sys)
    monkeypatch.setattr(python_runtime.platform, "python_version", lambda: "3.11.9")

    with pytest.raises(RuntimeError, match="requires Python 3.10.x"):
        python_runtime.require_python_310(entrypoint="tests.entrypoint")
