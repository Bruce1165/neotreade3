from __future__ import annotations

import shutil
from pathlib import Path


def cleanup_var_paths(*, project_root: Path, relative_paths: list[str]) -> None:
    var_root = project_root / "var"
    var_root_resolved = var_root.resolve()

    for relative_path in relative_paths:
        relative = Path(relative_path)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"invalid relative var path: {relative_path}")
        if not relative.parts or relative.parts[0] != "var":
            raise ValueError(f"expected var relative path: {relative_path}")

        target = (project_root / relative).resolve()
        try:
            target.relative_to(var_root_resolved)
        except ValueError as exc:
            raise ValueError(f"path escapes var root: {relative_path}") from exc

        if target.is_dir():
            shutil.rmtree(target, ignore_errors=True)
            continue

        try:
            target.unlink()
        except FileNotFoundError:
            pass
        except IsADirectoryError:
            shutil.rmtree(target, ignore_errors=True)
