from __future__ import annotations

import importlib.util
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _load_module(module_name: str, relative_path: str):
    module_path = PROJECT_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


run_module = _load_module(
    "run_chaos_midterm_validation_module",
    "scripts/run_chaos_midterm_validation.py",
)
cleanup_module = _load_module(
    "cleanup_runtime_outputs_module",
    "scripts/cleanup_runtime_outputs.py",
)


def test_resolve_output_roots_accepts_paths_under_runtime_root(tmp_path: Path) -> None:
    runtime_root = tmp_path / ".runtime_outputs" / "chaos_midterm_validation"
    ledger_root, artifact_root, meta = run_module._resolve_output_roots(
        project_root=tmp_path,
        output_root=str(runtime_root),
    )

    assert ledger_root == runtime_root / "ledgers"
    assert artifact_root == runtime_root / "artifacts"
    assert meta["output_mode"] == "override_local"
    assert meta["temporary_output"] is True


def test_resolve_output_roots_rejects_paths_outside_runtime_root(tmp_path: Path) -> None:
    outside_root = tmp_path / "other_runtime_area"
    with pytest.raises(SystemExit, match="output_root must stay under dedicated runtime root"):
        run_module._resolve_output_roots(
            project_root=tmp_path,
            output_root=str(outside_root),
        )


def test_iter_stale_files_uses_expires_after_and_temporary_flag(tmp_path: Path) -> None:
    runtime_root = tmp_path / ".runtime_outputs"
    target_dir = runtime_root / "artifacts" / "chaos_midterm_validation" / "2026-04-22"
    target_dir.mkdir(parents=True)

    expired_file = target_dir / "expired.json"
    expired_file.write_text(
        json.dumps(
            {
                "_meta": {
                    "temporary_output": True,
                    "expires_after": "2026-07-01T00:00:00Z",
                }
            }
        ),
        encoding="utf-8",
    )

    persistent_file = target_dir / "persistent.json"
    persistent_file.write_text(
        json.dumps(
            {
                "_meta": {
                    "temporary_output": False,
                    "expires_after": "2026-07-01T00:00:00Z",
                }
            }
        ),
        encoding="utf-8",
    )

    stale_files = cleanup_module._iter_stale_files(
        root=runtime_root,
        now=datetime(2026, 7, 23, tzinfo=timezone.utc),
        fallback_cutoff=datetime(2026, 7, 9, tzinfo=timezone.utc),
    )

    assert stale_files == [expired_file]


def test_iter_stale_files_falls_back_to_mtime_when_expiry_missing(tmp_path: Path) -> None:
    runtime_root = tmp_path / ".runtime_outputs"
    target_dir = runtime_root / "ledgers" / "chaos_midterm_validation" / "2026-04-22"
    target_dir.mkdir(parents=True)

    candidate = target_dir / "fallback.json"
    candidate.write_text(
        json.dumps({"_meta": {"temporary_output": True, "retention_days": 14}}),
        encoding="utf-8",
    )
    old_ts = datetime(2026, 7, 1, tzinfo=timezone.utc).timestamp()
    candidate.touch()
    os.utime(candidate, (old_ts, old_ts))

    stale_files = cleanup_module._iter_stale_files(
        root=runtime_root,
        now=datetime(2026, 7, 23, tzinfo=timezone.utc),
        fallback_cutoff=datetime(2026, 7, 9, tzinfo=timezone.utc),
    )

    assert stale_files == [candidate]
