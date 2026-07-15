from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def prepare_screeners_config_root(
    *,
    tmp_path: Path,
    screener_ids: list[str],
) -> tuple[Path, Path]:
    screeners_dir = tmp_path / "config" / "screeners"
    screeners_dir.mkdir(parents=True, exist_ok=True)

    registry_source = PROJECT_ROOT / "config/screeners/screeners_registry.json"
    registry_path = screeners_dir / "screeners_registry.json"
    registry_path.write_text(registry_source.read_text(encoding="utf-8"), encoding="utf-8")

    for screener_id in screener_ids:
        source = PROJECT_ROOT / f"config/screeners/{screener_id}.json"
        target = screeners_dir / f"{screener_id}.json"
        target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    return screeners_dir, registry_path
