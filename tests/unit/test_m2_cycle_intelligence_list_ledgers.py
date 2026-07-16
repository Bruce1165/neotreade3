from __future__ import annotations

import json
from pathlib import Path

import pytest

from neotrade3.cycle_intelligence import (
    list_shadow_cycle_intelligence_bundle_ledgers,
    list_small_cycle_ledgers,
    read_shadow_cycle_intelligence_bundle_ledger,
    read_small_cycle_ledger,
)


def _write_small_cycle_ledger(
    *,
    project_root: Path,
    record_id: str,
    written_at: str,
) -> None:
    ledger_file = (
        project_root
        / "var/ledgers/m2_small_cycles"
        / record_id
        / "small_cycle.json"
    )
    ledger_file.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "record_id": record_id,
        "written_at": written_at,
        "stock_code": record_id.split("-", 1)[0],
        "trade_date": record_id.split("-", 1)[1] if "-" in record_id else "",
        "cycle_state": "S2 Advancing",
        "artifact_path": f"var/artifacts/m2_small_cycles/{record_id}/small_cycle.json",
        "ledger_path": f"var/ledgers/m2_small_cycles/{record_id}/small_cycle.json",
    }
    ledger_file.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_shadow_bundle_ledger(
    *,
    project_root: Path,
    record_id: str,
    written_at: str,
) -> None:
    ledger_file = (
        project_root
        / "var/ledgers/m2_shadow_bundles"
        / record_id
        / "shadow_bundle.json"
    )
    ledger_file.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "record_id": record_id,
        "written_at": written_at,
        "stock_code": record_id.split("-", 1)[0],
        "trade_date": record_id.split("-", 1)[1] if "-" in record_id else "",
        "artifact_path": f"var/artifacts/m2_shadow_bundles/{record_id}/shadow_bundle.json",
        "ledger_path": f"var/ledgers/m2_shadow_bundles/{record_id}/shadow_bundle.json",
    }
    ledger_file.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def test_list_small_cycle_ledgers_sorts_by_written_at_desc_and_honors_limit(
    tmp_path: Path,
) -> None:
    _write_small_cycle_ledger(
        project_root=tmp_path,
        record_id="600000-2026-07-07",
        written_at="2026-07-07T00:00:00Z",
    )
    _write_small_cycle_ledger(
        project_root=tmp_path,
        record_id="600000-2026-07-08",
        written_at="2026-07-08T00:00:00Z",
    )

    records = list_small_cycle_ledgers(project_root=tmp_path, limit=1)

    assert len(records) == 1
    assert records[0].record_id == "600000-2026-07-08"


def test_list_shadow_bundle_ledgers_sorts_by_written_at_desc_and_honors_limit(
    tmp_path: Path,
) -> None:
    _write_shadow_bundle_ledger(
        project_root=tmp_path,
        record_id="600000-2026-07-07",
        written_at="2026-07-07T00:00:00Z",
    )
    _write_shadow_bundle_ledger(
        project_root=tmp_path,
        record_id="600000-2026-07-09",
        written_at="2026-07-09T00:00:00Z",
    )

    records = list_shadow_cycle_intelligence_bundle_ledgers(project_root=tmp_path, limit=2)

    assert len(records) == 2
    assert records[0].record_id == "600000-2026-07-09"
    assert records[1].record_id == "600000-2026-07-07"


def test_list_small_cycle_ledgers_fails_closed_on_invalid_json(tmp_path: Path) -> None:
    ledger_file = (
        tmp_path / "var/ledgers/m2_small_cycles/600000-2026-07-07/small_cycle.json"
    )
    ledger_file.parent.mkdir(parents=True, exist_ok=True)
    ledger_file.write_text("{", encoding="utf-8")

    with pytest.raises(ValueError):
        list_small_cycle_ledgers(project_root=tmp_path, limit=10)


def test_list_small_cycle_ledgers_fails_closed_on_non_object_json(tmp_path: Path) -> None:
    ledger_file = (
        tmp_path / "var/ledgers/m2_small_cycles/600000-2026-07-07/small_cycle.json"
    )
    ledger_file.parent.mkdir(parents=True, exist_ok=True)
    ledger_file.write_text("[]", encoding="utf-8")

    with pytest.raises(TypeError, match="JSON object"):
        list_small_cycle_ledgers(project_root=tmp_path, limit=10)


def test_list_shadow_bundle_ledgers_fails_closed_on_non_object_json(tmp_path: Path) -> None:
    ledger_file = (
        tmp_path
        / "var/ledgers/m2_shadow_bundles/600000-2026-07-07/shadow_bundle.json"
    )
    ledger_file.parent.mkdir(parents=True, exist_ok=True)
    ledger_file.write_text("[]", encoding="utf-8")

    with pytest.raises(TypeError, match="JSON object"):
        list_shadow_cycle_intelligence_bundle_ledgers(project_root=tmp_path, limit=10)


def test_read_small_cycle_ledger_fails_closed_on_non_object_json(tmp_path: Path) -> None:
    ledger_file = (
        tmp_path / "var/ledgers/m2_small_cycles/600000-2026-07-07/small_cycle.json"
    )
    ledger_file.parent.mkdir(parents=True, exist_ok=True)
    ledger_file.write_text("[]", encoding="utf-8")

    with pytest.raises(TypeError, match="JSON object"):
        read_small_cycle_ledger(project_root=tmp_path, record_id="600000-2026-07-07")


def test_read_shadow_bundle_ledger_fails_closed_on_non_object_json(tmp_path: Path) -> None:
    ledger_file = (
        tmp_path
        / "var/ledgers/m2_shadow_bundles/600000-2026-07-07/shadow_bundle.json"
    )
    ledger_file.parent.mkdir(parents=True, exist_ok=True)
    ledger_file.write_text("[]", encoding="utf-8")

    with pytest.raises(TypeError, match="JSON object"):
        read_shadow_cycle_intelligence_bundle_ledger(
            project_root=tmp_path,
            record_id="600000-2026-07-07",
        )
