from __future__ import annotations

from neotrade3.analysis.attribution_daily_audit_payload import build_simple_stage_audit


def test_build_simple_stage_audit_projects_current_envelope() -> None:
    out = build_simple_stage_audit(
        audit_date="2025-06-18",
        stage="global_wave_filtered",
        reason="跨板块分支波段不符（2浪）",
    )

    assert out == {
        "date": "2025-06-18",
        "stage": "global_wave_filtered",
        "reason": "跨板块分支波段不符（2浪）",
    }


def test_build_simple_stage_audit_keeps_empty_string_fallbacks() -> None:
    out = build_simple_stage_audit(
        audit_date="",
        stage="",
        reason="",
    )

    assert out == {
        "date": "",
        "stage": "",
        "reason": "",
    }
