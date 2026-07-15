from __future__ import annotations

import json
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from neotrade3.benchmark import (
    load_benchmark_run_manifest,
    materialize_benchmark_batch_run,
    run_benchmark_manifest,
)
from neotrade3.governance.assembler import build_validation_result
from neotrade3.governance.cli import build_parser, main
from neotrade3.governance.run_ledger import (
    read_governance_candidate_validation_artifact,
    read_governance_candidate_validation_record,
    read_governance_final_validation_artifact,
    read_governance_final_validation_record,
    read_governance_handoff_artifact,
    read_governance_reject_execution_artifact,
    read_governance_reject_execution_ledger,
    read_governance_run_ledger,
    read_governance_status_transition_artifact,
    read_governance_status_transition_ledger,
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


def _materialize_benchmark_run(project_root: Path, manifest_name: str) -> str:
    manifest = load_benchmark_run_manifest(
        project_root / "config" / "benchmark" / manifest_name
    )
    batch_result = run_benchmark_manifest(
        project_root=project_root,
        manifest=manifest,
    )
    materialize_benchmark_batch_run(
        project_root=project_root,
        batch_result=batch_result,
    )
    return batch_result.run_id


def _inject_rejected_validation(
    *,
    project_root: Path,
    source_run_id: str,
    validation_id: str,
) -> None:
    artifact_path = (
        project_root
        / "var/artifacts/governance_handoffs"
        / source_run_id
        / "governance_handoff_bundle.json"
    )
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    experiment_id = payload["experiment_requests"][0]["experiment_id"]
    payload["validation_results"].append(
        build_validation_result(
            validation_id=validation_id,
            experiment_id=experiment_id,
            baseline_run_id=source_run_id,
            candidate_run_id="candidate-run-1",
            outcome="rejected",
            introduced_risk_count=1,
            cleared_guardrail_codes=[],
            remaining_guardrail_codes=["interaction.local_global"],
            evidence_refs=[{"kind": "validation_result"}],
        ).to_payload()
    )
    artifact_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _build_candidate_validation_result_payload(
    *,
    project_root: Path,
    source_run_id: str,
    outcome: str = "rejected",
    candidate_run_id: str = "candidate-run-1",
) -> dict[str, object]:
    handoff_payload = read_governance_handoff_artifact(
        project_root=project_root,
        source_run_id=source_run_id,
    )
    assert handoff_payload is not None
    baseline_validation = handoff_payload["validation_results"][0]
    introduced_risk_count = 0 if outcome == "passed" else 1
    cleared_guardrail_codes = (
        ["interaction.local_global"] if outcome == "passed" else []
    )
    remaining_guardrail_codes = (
        [] if outcome == "passed" else ["interaction.local_global"]
    )
    return build_validation_result(
        validation_id=baseline_validation["validation_id"],
        experiment_id=baseline_validation["experiment_id"],
        baseline_run_id=source_run_id,
        candidate_run_id=candidate_run_id,
        outcome=outcome,
        introduced_risk_count=introduced_risk_count,
        cleared_guardrail_codes=cleared_guardrail_codes,
        remaining_guardrail_codes=remaining_guardrail_codes,
        evidence_refs=[{"kind": "candidate_validation"}],
    ).to_payload()


def test_governance_cli_parser_requires_subcommand() -> None:
    parser = build_parser()
    try:
        parser.parse_args([])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("parser should require a subcommand")


def test_governance_cli_parser_accepts_handoff_arguments() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "handoff",
            "--project-root",
            "/tmp/neotrade3",
            "--benchmark-run-id",
            "validation_seed_v2_batch",
            "--dry-run",
        ]
    )

    assert args.command == "handoff"
    assert args.project_root == "/tmp/neotrade3"
    assert args.benchmark_run_id == "validation_seed_v2_batch"
    assert args.dry_run is True


def test_governance_cli_parser_accepts_reject_arguments() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "reject",
            "--project-root",
            "/tmp/neotrade3",
            "--source-run-id",
            "benchmark-run-1",
            "--validation-id",
            "validation-1",
            "--dry-run",
        ]
    )

    assert args.command == "reject"
    assert args.project_root == "/tmp/neotrade3"
    assert args.source_run_id == "benchmark-run-1"
    assert args.validation_id == "validation-1"
    assert args.dry_run is True


def test_governance_cli_parser_accepts_status_transition_arguments() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "status-transition",
            "--project-root",
            "/tmp/neotrade3",
            "--source-run-id",
            "benchmark-run-1",
            "--validation-id",
            "validation-1",
            "--dry-run",
        ]
    )

    assert args.command == "status-transition"
    assert args.project_root == "/tmp/neotrade3"
    assert args.source_run_id == "benchmark-run-1"
    assert args.validation_id == "validation-1"
    assert args.dry_run is True


def test_governance_cli_parser_accepts_candidate_validation_outcome_arguments() -> None:
    parser = build_parser()
    validation_result = json.dumps(
        {
            "validation_id": "validation-1",
            "experiment_id": "experiment-1",
            "baseline_run_id": "benchmark-run-1",
            "candidate_run_id": "candidate-run-1",
            "outcome": "rejected",
            "introduced_risk_count": 1,
            "cleared_guardrail_codes": [],
            "remaining_guardrail_codes": ["interaction.local_global"],
            "evidence_refs": [{"kind": "candidate_validation"}],
        },
        ensure_ascii=False,
    )
    args = parser.parse_args(
        [
            "candidate-validation-outcome",
            "--project-root",
            "/tmp/neotrade3",
            "--source-run-id",
            "benchmark-run-1",
            "--validation-result",
            validation_result,
            "--dry-run",
        ]
    )

    assert args.command == "candidate-validation-outcome"
    assert args.project_root == "/tmp/neotrade3"
    assert args.source_run_id == "benchmark-run-1"
    assert args.validation_result.validation_id == "validation-1"
    assert args.validation_result.outcome == "rejected"
    assert args.dry_run is True


def test_governance_cli_parser_accepts_final_validation_selection_arguments() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "final-validation-selection",
            "--project-root",
            "/tmp/neotrade3",
            "--source-run-id",
            "benchmark-run-1",
            "--dry-run",
        ]
    )

    assert args.command == "final-validation-selection"
    assert args.project_root == "/tmp/neotrade3"
    assert args.source_run_id == "benchmark-run-1"
    assert args.dry_run is True


def test_governance_cli_main_dry_run_does_not_write_outputs(tmp_path: Path) -> None:
    project_root = _prepare_project_root(tmp_path)
    run_id = _materialize_benchmark_run(project_root, "validation_seed_manifest.json")
    buffer = StringIO()

    with redirect_stdout(buffer):
        exit_code = main(
            [
                "handoff",
                "--project-root",
                str(project_root),
                "--benchmark-run-id",
                run_id,
                "--dry-run",
            ]
        )

    payload = json.loads(buffer.getvalue())
    assert exit_code == 0
    assert payload["source_run_id"] == run_id
    assert payload["status"] == "completed"
    assert payload["source_layer"] == "M4"
    assert payload["projected_assessment_count"] == 2
    assert payload["attention_item_count"] == 1
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


def test_governance_cli_final_validation_selection_materializes_outputs(
    tmp_path: Path,
) -> None:
    project_root = _prepare_project_root(tmp_path)
    run_id = _materialize_benchmark_run(project_root, "validation_seed_manifest.json")
    main(["handoff", "--project-root", str(project_root), "--benchmark-run-id", run_id])
    validation_result_payload = _build_candidate_validation_result_payload(
        project_root=project_root,
        source_run_id=run_id,
        outcome="passed",
        candidate_run_id="candidate-run-1",
    )
    validation_result = json.dumps(validation_result_payload, ensure_ascii=False)
    main(
        [
            "candidate-validation-outcome",
            "--project-root",
            str(project_root),
            "--source-run-id",
            run_id,
            "--validation-result",
            validation_result,
        ]
    )
    buffer = StringIO()

    with redirect_stdout(buffer):
        exit_code = main(
            [
                "final-validation-selection",
                "--project-root",
                str(project_root),
                "--source-run-id",
                run_id,
            ]
        )

    payload = json.loads(buffer.getvalue())
    artifact = read_governance_final_validation_artifact(
        project_root=project_root,
        source_run_id=run_id,
    )
    ledger = read_governance_final_validation_record(
        project_root=project_root,
        source_run_id=run_id,
    )

    assert exit_code == 0
    assert payload["source_run_id"] == run_id
    assert payload["selected_validation_id"] == validation_result_payload["validation_id"]
    assert payload["outcome"] == "passed"
    assert payload["dry_run"] is False
    assert artifact is not None
    assert artifact["source_run_id"] == run_id
    assert (
        artifact["selected_validation_id"] == validation_result_payload["validation_id"]
    )
    assert ledger is not None
    assert ledger.source_run_id == run_id
    assert (
        ledger.selected_validation_id == validation_result_payload["validation_id"]
    )


def test_governance_cli_main_materializes_outputs(tmp_path: Path) -> None:
    project_root = _prepare_project_root(tmp_path)
    run_id = _materialize_benchmark_run(project_root, "validation_seed_v2_manifest.json")
    buffer = StringIO()

    with redirect_stdout(buffer):
        exit_code = main(
            [
                "handoff",
                "--project-root",
                str(project_root),
                "--benchmark-run-id",
                run_id,
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
    assert payload["source_run_id"] == run_id
    assert payload["status"] == "completed"
    assert payload["source_layer"] == "M4"
    assert payload["projected_assessment_count"] == 2
    assert payload["attention_item_count"] == 0
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
        ledger_record.validation_result_count
        == payload["validation_result_count"]
    )
    assert (
        ledger_record.promotion_blocker_count
        == payload["promotion_blocker_count"]
    )
    assert ledger_record.attention_item_count == payload["attention_item_count"]
    assert (
        ledger_record.decision_record_count
        == payload["decision_record_count"]
    )
    assert artifact_payload["source_run_id"] == payload["source_run_id"]
    assert artifact_payload["projected_assessment_count"] == payload[
        "projected_assessment_count"
    ]
    assert len(artifact_payload["validation_results"]) == payload["validation_result_count"]
    assert len(artifact_payload["attention_items"]) == payload["attention_item_count"]
    assert len(artifact_payload["decision_records"]) == payload["decision_record_count"]


def test_governance_cli_main_raises_for_missing_benchmark_artifact(
    tmp_path: Path,
) -> None:
    project_root = _prepare_project_root(tmp_path)

    try:
        main(
            [
                "handoff",
                "--project-root",
                str(project_root),
                "--benchmark-run-id",
                "missing_benchmark_run",
            ]
        )
    except FileNotFoundError as exc:
        assert "missing_benchmark_run" in str(exc)
    else:
        raise AssertionError("missing benchmark artifact should raise FileNotFoundError")


def test_governance_cli_reject_dry_run_does_not_write_outputs(tmp_path: Path) -> None:
    project_root = _prepare_project_root(tmp_path)
    run_id = _materialize_benchmark_run(project_root, "validation_seed_manifest.json")
    main(["handoff", "--project-root", str(project_root), "--benchmark-run-id", run_id])
    _inject_rejected_validation(
        project_root=project_root,
        source_run_id=run_id,
        validation_id="validation-final-reject",
    )
    buffer = StringIO()

    with redirect_stdout(buffer):
        exit_code = main(
            [
                "reject",
                "--project-root",
                str(project_root),
                "--source-run-id",
                run_id,
                "--validation-id",
                "validation-final-reject",
                "--dry-run",
            ]
        )

    payload = json.loads(buffer.getvalue())
    assert exit_code == 0
    assert payload["validation_id"] == "validation-final-reject"
    assert payload["source_run_id"] == run_id
    assert payload["decision"] == "reject"
    assert payload["dry_run"] is True
    assert not (project_root / payload["artifact_path"]).exists()
    assert not (project_root / payload["ledger_path"]).exists()
    assert (
        read_governance_reject_execution_artifact(
            project_root=project_root,
            validation_id=payload["validation_id"],
        )
        is None
    )
    assert (
        read_governance_reject_execution_ledger(
            project_root=project_root,
            validation_id=payload["validation_id"],
        )
        is None
    )


def test_governance_cli_reject_materializes_outputs(tmp_path: Path) -> None:
    project_root = _prepare_project_root(tmp_path)
    run_id = _materialize_benchmark_run(project_root, "validation_seed_manifest.json")
    main(["handoff", "--project-root", str(project_root), "--benchmark-run-id", run_id])
    _inject_rejected_validation(
        project_root=project_root,
        source_run_id=run_id,
        validation_id="validation-final-reject",
    )
    buffer = StringIO()

    with redirect_stdout(buffer):
        exit_code = main(
            [
                "reject",
                "--project-root",
                str(project_root),
                "--source-run-id",
                run_id,
                "--validation-id",
                "validation-final-reject",
            ]
        )

    payload = json.loads(buffer.getvalue())
    artifact_path = project_root / payload["artifact_path"]
    ledger_path = project_root / payload["ledger_path"]
    artifact_payload = read_governance_reject_execution_artifact(
        project_root=project_root,
        validation_id=payload["validation_id"],
    )
    ledger_record = read_governance_reject_execution_ledger(
        project_root=project_root,
        validation_id=payload["validation_id"],
    )

    assert exit_code == 0
    assert payload["validation_id"] == "validation-final-reject"
    assert payload["source_run_id"] == run_id
    assert payload["decision"] == "reject"
    assert payload["dry_run"] is False
    assert artifact_path.exists()
    assert ledger_path.exists()
    assert artifact_payload is not None
    assert ledger_record is not None
    assert artifact_payload["decision_record"]["decision"] == "reject"
    assert artifact_payload["validation_result"]["outcome"] == "rejected"
    assert ledger_record.validation_id == payload["validation_id"]
    assert ledger_record.decision == payload["decision"]


def test_governance_cli_reject_raises_for_missing_validation(tmp_path: Path) -> None:
    project_root = _prepare_project_root(tmp_path)
    run_id = _materialize_benchmark_run(project_root, "validation_seed_v2_manifest.json")
    main(["handoff", "--project-root", str(project_root), "--benchmark-run-id", run_id])

    try:
        main(
            [
                "reject",
                "--project-root",
                str(project_root),
                "--source-run-id",
                run_id,
                "--validation-id",
                "missing-validation",
            ]
        )
    except ValueError as exc:
        assert "validation_result not found" in str(exc)
    else:
        raise AssertionError("missing validation should raise ValueError")


def test_governance_cli_candidate_validation_outcome_dry_run_does_not_write_outputs(
    tmp_path: Path,
) -> None:
    project_root = _prepare_project_root(tmp_path)
    run_id = _materialize_benchmark_run(project_root, "validation_seed_manifest.json")
    main(["handoff", "--project-root", str(project_root), "--benchmark-run-id", run_id])
    validation_result = _build_candidate_validation_result_payload(
        project_root=project_root,
        source_run_id=run_id,
        outcome="rejected",
    )
    buffer = StringIO()

    with redirect_stdout(buffer):
        exit_code = main(
            [
                "candidate-validation-outcome",
                "--project-root",
                str(project_root),
                "--source-run-id",
                run_id,
                "--validation-result",
                json.dumps(validation_result, ensure_ascii=False, sort_keys=True),
                "--dry-run",
            ]
        )

    payload = json.loads(buffer.getvalue())
    assert exit_code == 0
    assert payload["validation_id"] == validation_result["validation_id"]
    assert payload["source_run_id"] == run_id
    assert payload["outcome"] == "rejected"
    assert payload["dry_run"] is True
    assert not (project_root / payload["artifact_path"]).exists()
    assert not (project_root / payload["ledger_path"]).exists()
    assert (
        read_governance_candidate_validation_artifact(
            project_root=project_root,
            validation_id=payload["validation_id"],
        )
        is None
    )
    assert (
        read_governance_candidate_validation_record(
            project_root=project_root,
            validation_id=payload["validation_id"],
        )
        is None
    )


def test_governance_cli_candidate_validation_outcome_materializes_outputs(
    tmp_path: Path,
) -> None:
    project_root = _prepare_project_root(tmp_path)
    run_id = _materialize_benchmark_run(project_root, "validation_seed_manifest.json")
    main(["handoff", "--project-root", str(project_root), "--benchmark-run-id", run_id])
    validation_result = _build_candidate_validation_result_payload(
        project_root=project_root,
        source_run_id=run_id,
        outcome="passed",
        candidate_run_id="candidate-run-pass",
    )
    buffer = StringIO()

    with redirect_stdout(buffer):
        exit_code = main(
            [
                "candidate-validation-outcome",
                "--project-root",
                str(project_root),
                "--source-run-id",
                run_id,
                "--validation-result",
                json.dumps(validation_result, ensure_ascii=False, sort_keys=True),
            ]
        )

    payload = json.loads(buffer.getvalue())
    artifact_path = project_root / payload["artifact_path"]
    ledger_path = project_root / payload["ledger_path"]
    artifact_payload = read_governance_candidate_validation_artifact(
        project_root=project_root,
        validation_id=payload["validation_id"],
    )
    ledger_record = read_governance_candidate_validation_record(
        project_root=project_root,
        validation_id=payload["validation_id"],
    )

    assert exit_code == 0
    assert payload["validation_id"] == validation_result["validation_id"]
    assert payload["source_run_id"] == run_id
    assert payload["outcome"] == "passed"
    assert payload["candidate_run_id"] == "candidate-run-pass"
    assert payload["dry_run"] is False
    assert artifact_path.exists()
    assert ledger_path.exists()
    assert artifact_payload is not None
    assert ledger_record is not None
    assert artifact_payload["outcome"] == "passed"
    assert (
        artifact_payload["validation_result"]["candidate_run_id"]
        == "candidate-run-pass"
    )
    assert ledger_record.validation_id == payload["validation_id"]
    assert ledger_record.outcome == payload["outcome"]


def test_governance_cli_status_transition_dry_run_does_not_write_outputs(
    tmp_path: Path,
) -> None:
    project_root = _prepare_project_root(tmp_path)
    run_id = _materialize_benchmark_run(project_root, "validation_seed_manifest.json")
    main(["handoff", "--project-root", str(project_root), "--benchmark-run-id", run_id])
    _inject_rejected_validation(
        project_root=project_root,
        source_run_id=run_id,
        validation_id="validation-final-reject",
    )
    main(
        [
            "reject",
            "--project-root",
            str(project_root),
            "--source-run-id",
            run_id,
            "--validation-id",
            "validation-final-reject",
        ]
    )
    buffer = StringIO()

    with redirect_stdout(buffer):
        exit_code = main(
            [
                "status-transition",
                "--project-root",
                str(project_root),
                "--source-run-id",
                run_id,
                "--validation-id",
                "validation-final-reject",
                "--dry-run",
            ]
        )

    payload = json.loads(buffer.getvalue())
    assert exit_code == 0
    assert payload["validation_id"] == "validation-final-reject"
    assert payload["source_run_id"] == run_id
    assert payload["effective_attention_status"] == "resolved"
    assert payload["effective_blocker_active"] is True
    assert payload["dry_run"] is True
    assert not (project_root / payload["artifact_path"]).exists()
    assert not (project_root / payload["ledger_path"]).exists()
    assert (
        read_governance_status_transition_artifact(
            project_root=project_root,
            validation_id=payload["validation_id"],
        )
        is None
    )
    assert (
        read_governance_status_transition_ledger(
            project_root=project_root,
            validation_id=payload["validation_id"],
        )
        is None
    )


def test_governance_cli_status_transition_materializes_outputs(tmp_path: Path) -> None:
    project_root = _prepare_project_root(tmp_path)
    run_id = _materialize_benchmark_run(project_root, "validation_seed_manifest.json")
    main(["handoff", "--project-root", str(project_root), "--benchmark-run-id", run_id])
    _inject_rejected_validation(
        project_root=project_root,
        source_run_id=run_id,
        validation_id="validation-final-reject",
    )
    main(
        [
            "reject",
            "--project-root",
            str(project_root),
            "--source-run-id",
            run_id,
            "--validation-id",
            "validation-final-reject",
        ]
    )
    buffer = StringIO()

    with redirect_stdout(buffer):
        exit_code = main(
            [
                "status-transition",
                "--project-root",
                str(project_root),
                "--source-run-id",
                run_id,
                "--validation-id",
                "validation-final-reject",
            ]
        )

    payload = json.loads(buffer.getvalue())
    artifact_path = project_root / payload["artifact_path"]
    ledger_path = project_root / payload["ledger_path"]
    artifact_payload = read_governance_status_transition_artifact(
        project_root=project_root,
        validation_id=payload["validation_id"],
    )
    ledger_record = read_governance_status_transition_ledger(
        project_root=project_root,
        validation_id=payload["validation_id"],
    )

    assert exit_code == 0
    assert payload["validation_id"] == "validation-final-reject"
    assert payload["source_run_id"] == run_id
    assert payload["status"] == "completed"
    assert payload["effective_attention_status"] == "resolved"
    assert payload["effective_blocker_active"] is True
    assert payload["dry_run"] is False
    assert artifact_path.exists()
    assert ledger_path.exists()
    assert artifact_payload is not None
    assert ledger_record is not None
    assert ledger_record.validation_id == payload["validation_id"]
    assert ledger_record.decision_id == payload["decision_id"]
    assert ledger_record.effective_attention_id == payload["effective_attention_id"]
    assert (
        ledger_record.effective_attention_status
        == payload["effective_attention_status"]
    )
    assert ledger_record.effective_blocker_id == payload["effective_blocker_id"]
    assert (
        ledger_record.effective_blocker_active
        == payload["effective_blocker_active"]
    )
    assert artifact_payload["effective_attention_item"]["status"] == "resolved"
    assert artifact_payload["effective_promotion_blocker"]["active"] is True


def test_governance_cli_status_transition_raises_for_missing_reject_proof(
    tmp_path: Path,
) -> None:
    project_root = _prepare_project_root(tmp_path)
    run_id = _materialize_benchmark_run(project_root, "validation_seed_manifest.json")
    main(["handoff", "--project-root", str(project_root), "--benchmark-run-id", run_id])
    _inject_rejected_validation(
        project_root=project_root,
        source_run_id=run_id,
        validation_id="validation-final-reject",
    )

    try:
        main(
            [
                "status-transition",
                "--project-root",
                str(project_root),
                "--source-run-id",
                run_id,
                "--validation-id",
                "validation-final-reject",
            ]
        )
    except ValueError as exc:
        assert "persisted governance reject execution not found" in str(exc)
    else:
        raise AssertionError("missing reject proof should raise ValueError")
