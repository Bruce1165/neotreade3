#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from typing import Any
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNTIME_ROOT = PROJECT_ROOT / ".runtime_outputs"


def _parse_utc_timestamp(raw: Any) -> datetime | None:
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _load_runtime_meta(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(payload, dict):
        return {}
    meta = payload.get("_meta")
    return meta if isinstance(meta, dict) else {}


def _should_remove_file(*, path: Path, now: datetime, fallback_cutoff: datetime) -> bool:
    meta = _load_runtime_meta(path)
    if not bool(meta.get("temporary_output")):
        return False
    expires_after = _parse_utc_timestamp(meta.get("expires_after"))
    if expires_after is not None:
        return expires_after <= now
    modified_at = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return modified_at <= fallback_cutoff


def _iter_stale_files(*, root: Path, now: datetime, fallback_cutoff: datetime) -> list[Path]:
    stale_files: list[Path] = []
    if not root.exists():
        return stale_files
    for path in root.rglob("*.json"):
        if not path.is_file():
            continue
        if _should_remove_file(path=path, now=now, fallback_cutoff=fallback_cutoff):
            stale_files.append(path)
    return sorted(stale_files)


def _prune_empty_parents(*, path: Path, stop_at: Path) -> None:
    current = path.parent
    stop_at_resolved = stop_at.resolve()
    while True:
        current_resolved = current.resolve()
        if current_resolved == stop_at_resolved:
            break
        if any(current.iterdir()):
            break
        current.rmdir()
        current = current.parent


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(DEFAULT_RUNTIME_ROOT))
    parser.add_argument("--older-than-days", type=int, default=14)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    root = Path(str(args.root)).expanduser()
    if not root.is_absolute():
        root = (PROJECT_ROOT / root).resolve()
    else:
        root = root.resolve()
    runtime_root = DEFAULT_RUNTIME_ROOT.resolve()
    try:
        root.relative_to(runtime_root)
    except ValueError as exc:
        raise SystemExit(f"refuse cleanup outside dedicated runtime root: {root}")
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=max(1, int(args.older_than_days)))

    stale_files = _iter_stale_files(root=root, now=now, fallback_cutoff=cutoff)

    removed_files = 0
    for path in stale_files:
        if not args.dry_run:
            path.unlink(missing_ok=True)
            _prune_empty_parents(path=path, stop_at=root)
        removed_files += 1

    # Remove any empty top-level directories left behind.
    if root.exists() and not args.dry_run:
        for child in sorted(root.iterdir()):
            if child.is_dir() and not any(child.iterdir()):
                shutil.rmtree(child, ignore_errors=True)

    print(
        json.dumps(
            {
                "status": "ok",
                "root": str(root),
                "older_than_days": max(1, int(args.older_than_days)),
                "dry_run": bool(args.dry_run),
                "removed_files": removed_files,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
