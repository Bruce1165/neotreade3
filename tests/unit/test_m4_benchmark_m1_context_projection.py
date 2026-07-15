from __future__ import annotations

from pathlib import Path

from neotrade3.benchmark import (
    BenchmarkM1ContextProjection,
    build_benchmark_m1_context_projection_record_id,
    materialize_benchmark_m1_context_projection,
    read_benchmark_m1_context_projection,
    read_benchmark_m1_context_projection_artifact,
    read_benchmark_m1_context_projection_ledger,
)


def test_materialize_benchmark_m1_context_projection(tmp_path: Path) -> None:
    projection = BenchmarkM1ContextProjection(source="benchmark_local_projection")
    record_id = build_benchmark_m1_context_projection_record_id(
        stock_code="600000",
        trade_date="2026-07-07",
    )

    ledger_record = materialize_benchmark_m1_context_projection(
        project_root=tmp_path,
        record_id=record_id,
        projection=projection,
    )
    artifact_payload = read_benchmark_m1_context_projection_artifact(
        project_root=tmp_path,
        record_id=record_id,
    )
    reconstructed = read_benchmark_m1_context_projection(
        project_root=tmp_path,
        record_id=record_id,
    )
    reconstructed_ledger = read_benchmark_m1_context_projection_ledger(
        project_root=tmp_path,
        record_id=record_id,
    )

    assert ledger_record.record_id == record_id
    assert artifact_payload is not None
    assert artifact_payload["source"] == "benchmark_local_projection"
    assert reconstructed == projection
    assert reconstructed_ledger == ledger_record
