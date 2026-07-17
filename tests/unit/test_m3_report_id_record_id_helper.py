from __future__ import annotations

import pytest

from neotrade3.decision_engine.lifecycle_log_store import (
    build_decision_m3_lifecycle_log_record_id_from_report_id,
)


def test_build_decision_m3_lifecycle_log_record_id_from_report_id_returns_expected_value() -> None:
    record_id = build_decision_m3_lifecycle_log_record_id_from_report_id(
        stock_code="300001",
        report_id="lowfreq_v16_2024-12-18_2026-06-18__20260717T000000Z_aaaaaaaa",
    )
    assert record_id == "300001-lowfreq_v16_2024-12-18_2026-06-18__20260717T000000Z_aaaaaaaa"


def test_build_decision_m3_lifecycle_log_record_id_from_report_id_fails_closed() -> None:
    with pytest.raises(ValueError):
        build_decision_m3_lifecycle_log_record_id_from_report_id(
            stock_code="",
            report_id="r",
        )
    with pytest.raises(ValueError):
        build_decision_m3_lifecycle_log_record_id_from_report_id(
            stock_code="300001",
            report_id="",
        )
    with pytest.raises(ValueError):
        build_decision_m3_lifecycle_log_record_id_from_report_id(
            stock_code="../300001",
            report_id="r",
        )

