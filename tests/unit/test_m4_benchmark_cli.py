from __future__ import annotations

import json
from io import StringIO
from pathlib import Path
from contextlib import redirect_stdout

from neotrade3.benchmark.cli import build_parser, main


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


def test_benchmark_cli_parser_uses_default_manifest() -> None:
    parser = build_parser()
    args = parser.parse_args([])

    assert args.project_root is None
    assert args.manifest == "config/benchmark/validation_seed_manifest.json"
    assert args.dry_run is False


def test_benchmark_cli_parser_accepts_explicit_arguments() -> None:
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


def test_benchmark_cli_main_dry_run_does_not_write_outputs(tmp_path) -> None:
    project_root = _prepare_project_root(tmp_path)
    buffer = StringIO()

    with redirect_stdout(buffer):
        exit_code = main(["--project-root", str(project_root), "--dry-run"])

    payload = json.loads(buffer.getvalue())
    assert exit_code == 0
    assert payload["run_id"] == "validation_seed_v1_batch"
    assert payload["status"] == "completed"
    assert payload["sample_count"] == 2
    assert payload["executed_sample_ids"] == [
        "b3_boundary_complex_advancing_seed",
        "b4_local_global_guardrail_seed",
    ]
    assert payload["dry_run"] is True
    assert not (project_root / payload["artifact_path"]).exists()
    assert not (project_root / payload["ledger_path"]).exists()


def test_benchmark_cli_main_materializes_outputs(tmp_path) -> None:
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

    assert exit_code == 0
    assert payload["run_id"] == "validation_seed_v2_batch"
    assert payload["status"] == "completed"
    assert payload["sample_count"] == 2
    assert payload["executed_sample_ids"] == [
        "b1_target_opportunity_seed",
        "b2_control_failure_seed",
    ]
    assert payload["dry_run"] is False
    assert artifact_path.exists()
    assert ledger_path.exists()

    artifact_payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    ledger_payload = json.loads(ledger_path.read_text(encoding="utf-8"))
    assert artifact_payload["run_id"] == "validation_seed_v2_batch"
    assert ledger_payload["run_id"] == "validation_seed_v2_batch"
