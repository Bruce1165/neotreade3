from __future__ import annotations

import re
from pathlib import Path


def _parse_rulebook_registry(text: str) -> dict[str, dict[str, str]]:
    entries: dict[str, dict[str, str]] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line.startswith("- RB."):
            continue
        payload = line.lstrip("-").strip()
        parts = payload.split()
        if not parts:
            continue
        entry_id = str(parts[0]).strip()
        fields: dict[str, str] = {}
        for item in parts[1:]:
            if "=" not in item:
                continue
            k, v = item.split("=", 1)
            fields[str(k).strip()] = str(v).strip()
        entries[entry_id] = fields
    return entries


def _parse_task_registry(text: str) -> dict[str, dict[str, str]]:
    entries: dict[str, dict[str, str]] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line.startswith("- TASK."):
            continue
        payload = line.lstrip("-").strip()
        parts = payload.split()
        if not parts:
            continue
        task_id = str(parts[0]).strip()
        fields: dict[str, str] = {}
        for item in parts[1:]:
            if "=" not in item:
                continue
            k, v = item.split("=", 1)
            fields[str(k).strip()] = str(v).strip()
        entries[task_id] = fields
    return entries


def test_task_registry_gate() -> None:
    rulebook_text = Path("docs/architecture/lowfreq_v16_model_rulebook.md").read_text(encoding="utf-8")
    rb_registry = _parse_rulebook_registry(rulebook_text)
    assert rb_registry

    task_text = Path("docs/superpowers/specs/lowfreq_v16_task_registry.md").read_text(encoding="utf-8")
    tasks = _parse_task_registry(task_text)
    assert tasks

    allowed_status = {"todo", "doing", "done"}
    repo_root = Path(".").resolve()

    for task_id, fields in tasks.items():
        status = str(fields.get("status") or "").strip()
        assert status in allowed_status
        evidence_raw = str(fields.get("evidence") or "").strip()
        assert evidence_raw
        evidence_items = [x.strip() for x in evidence_raw.split(",") if x.strip()]
        assert evidence_items
        for rel in evidence_items:
            p = (repo_root / rel).resolve()
            assert p.exists()

        rb_ids_raw = str(fields.get("rb_ids") or "").strip()
        assert rb_ids_raw
        rb_ids = [x.strip() for x in rb_ids_raw.split(",") if x.strip()]
        assert rb_ids
        for rid in rb_ids:
            assert rid in rb_registry

        if status == "done":
            has_implemented = False
            for rid in rb_ids:
                if str(rb_registry[rid].get("status") or "").strip() == "implemented":
                    has_implemented = True
                    break
            assert has_implemented

