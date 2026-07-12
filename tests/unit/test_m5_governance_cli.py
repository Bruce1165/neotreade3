from __future__ import annotations

import json
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from neotrade3.governance.cli import build_parser, main
from neotrade3.governance.run_ledger import (
    read_governance_handoff_artifact,
    read_governance_run_ledger,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BENCHMARK_CONFIG_DIR = PROJECT_ROOT / "config" / "benchmark"


def _prepare_project_root(tmp_path: Path) -> Path:
    benchmark_dir = tmp_path / "config" / "benchmark"
    benchmark_dir.mkdir(parents=True, exist_ok=True)
    for file_name in (
        "validation_seed_manifest.json",
        "validation_seed_v2_manifest.json",
        "validation_seed_samples.json",
    ):
        source = BENCHMARK_CONFIG_DIR / file_name
        (benchmark_dir / file_name).write_text(
            source.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
    return tmp_path


def test_governance_cli_parser_uses_default_manifest() -> None:
    parser = build_parser()
    args = parser.parse_args([])

    assert args.project_root is None
    assert args.manifest == "config/benchmark/validation_seed_manifest.json"
    assert args.dry_run is False


def test_governance_cli_parser_accepts_explicit_arguments() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "--project-root",
            "/tmp/neotrade3",
            "--manifest",
            "config/benchmark/validation_seed_v2_manifest.json",
            "--dry-run",
        ]
    )

    assert args.project_root == "/tmp/neotrade3"
    assert args.manifest == "config/benchmark/validation_seed_v2_manifest.json"
    assert args.dry_run is True


def test_governance_cli_main_dry_run_does_not_write_outputs(tmp_path: Path) -> None:
    project_root = _prepare_project_root(tmp_path)
    buffer = StringIO()

    with redirect_stdout(buffer):
        exit_code = main(["--project-root", str(project_root), "--dry-run"])

    payload = json.loads(buffer.getvalue())
    assert exit_code == 0
    assert payload["source_run_id"] == "validation_seed_v1_batch"
    assert payload["status"] == "completed"
    assert payload["source_layer"] == "M4"
    assert payload["projected_assessment_count"] == 2
    assert payload["dry_run"] is True
    assert not (project_root / payload["artifact_path"]).exists()
    assert not (project_root / payload["ledger_path"]).exists()
    assert (
        read_governance_run_ledger(
            project_root=project_root,
            source_run_id=payload["source_run_id"],
        )
        is None
    )
    assert (
        read_governance_handoff_artifact(
            project_root=project_root,
            source_run_id=payload["source_run_id"],
        )
        is None
    )


def test_governance_cli_main_materializes_outputs(tmp_path: Path) -> None:
    project_root = _prepare_project_root(tmp_path)
    buffer = StringIO()

    with redirect_stdout(buffer):
        exit_code = main(
            [
                "--project-root",
                str(project_root),
                "--manifest",
                "config/benchmark/validation_seed_v2_manifest.json",
            ]
        )

    payload = json.loads(buffer.getvalue())
    artifact_path = project_root / payload["artifact_path"]
    ledger_path = project_root / payload["ledger_path"]
    ledger_record = read_governance_run_ledger(
        project_root=project_root,
        source_run_id=payload["source_run_id"],
    )
    artifact_payload = read_governance_handoff_artifact(
        project_root=project_root,
        source_run_id=payload["source_run_id"],
    )

    assert exit_code == 0
    assert payload["source_run_id"] == "validation_seed_v2_batch"
    assert payload["status"] == "completed"
    assert payload["source_layer"] == "M4"
    assert payload["projected_assessment_count"] == 2
    assert payload["dry_run"] is False
    assert artifact_path.exists()
    assert ledger_path.exists()
    assert ledger_record is not None
    assert artifact_payload is not None
    assert ledger_record.source_run_id == payload["source_run_id"]
    assert ledger_record.artifact_path == payload["artifact_path"]
    assert ledger_record.ledger_path == payload["ledger_path"]
    assert ledger_record.diagnostic_count == payload["diagnostic_count"]
    assert ledger_record.change_request_count == payload["change_request_count"]
    assert ledger_record.experiment_request_count == payload["experiment_request_count"]
    assert (
        ledger_record.promotion_blocker_count
        == payload["promotion_blocker_count"]
    )
    assert artifact_payload["source_run_id"] == payload["source_run_id"]
    assert artifact_payload["projected_assessment_count"] == payload[
        "projected_assessment_count"
    ]
