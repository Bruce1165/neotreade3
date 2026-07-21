from __future__ import annotations

import re
from pathlib import Path


def _parse_registry_entries(text: str) -> dict[str, dict[str, str]]:
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


def test_rulebook_contract_registry_gate() -> None:
    rulebook_path = Path("docs/architecture/lowfreq_v16_model_rulebook.md")
    text = rulebook_path.read_text(encoding="utf-8")
    assert "Contract Registry（契约注册表）" in text

    registry = _parse_registry_entries(text)
    assert registry

    referenced = set(re.findall(r"RB\.[A-Z0-9_.-]+", text))
    missing = sorted([x for x in referenced if x not in registry])
    assert not missing

    allowed_status = {"implemented", "planned", "deferred"}
    repo_root = Path(".").resolve()
    for entry_id, fields in registry.items():
        status = str(fields.get("status") or "").strip()
        assert status in allowed_status
        evidence_raw = str(fields.get("evidence") or "").strip()
        assert evidence_raw
        evidence_items = [x.strip() for x in evidence_raw.split(",") if x.strip()]
        assert evidence_items
        for rel in evidence_items:
            p = (repo_root / rel).resolve()
            assert p.exists()

