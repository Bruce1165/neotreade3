"""Formal front assembly helpers for low-frequency engine payloads."""

from __future__ import annotations

import sqlite3
from datetime import date
from typing import Any

from neotrade3.cycle_intelligence import build_small_cycle_from_m1
from neotrade3.data_control import project_pf1_trading_profile
from neotrade3.data_control.formal_input_adapter import load_formal_m1_inputs

from .assembler import (
    build_entry_state_from_formal_inputs,
    build_identify_state_from_formal_inputs,
    build_m1_constraints_ref,
    build_tracking_state_from_formal_inputs,
)


def _candidate_codes(candidate_signals: list[dict[str, Any]]) -> list[str]:
    return [
        str(sig.get("code") or "").strip()
        for sig in candidate_signals
        if isinstance(sig, dict) and str(sig.get("code") or "").strip()
    ]


def attach_lowfreq_formal_front_payloads(
    signals: list[dict[str, Any]],
    *,
    formal_by_code: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    attached: list[dict[str, Any]] = []
    for raw_sig in signals:
        sig = dict(raw_sig)
        code = str(sig.get("code") or "").strip()
        sig["formal"] = dict(formal_by_code.get(code) or {"status": "unavailable"})
        attached.append(sig)
    return attached


def finalize_lowfreq_formal_front_payload(
    signal_payload: dict[str, Any],
    *,
    formal_payload: dict[str, Any],
) -> dict[str, Any]:
    finalized = dict(signal_payload)
    candidate_signals = attach_lowfreq_formal_front_payloads(
        list(finalized.get("candidate_signals") or []),
        formal_by_code=dict(formal_payload.get("items_by_code") or {}),
    )
    entry_signals = [dict(sig) for sig in candidate_signals if bool(sig.get("entry_ready"))]
    finalized["candidate_signals"] = candidate_signals
    finalized["entry_signals"] = entry_signals
    finalized["buy_signals"] = list(entry_signals)
    finalized["formal"] = formal_payload
    return finalized


def build_lowfreq_formal_front_payload(
    cursor: sqlite3.Cursor,
    *,
    target_date: date,
    candidate_signals: list[dict[str, Any]],
    history_limit: int = 20,
) -> dict[str, Any]:
    codes = _candidate_codes(candidate_signals)
    if not codes:
        return {"status": "ok", "items_by_code": {}, "summary": {"total": 0, "ok": 0, "error": 0}}

    try:
        formal_inputs = load_formal_m1_inputs(
            cursor,
            codes,
            target_date=target_date,
            history_limit=history_limit,
        )
        d1_by_code = dict(formal_inputs.get("d1_by_code") or {})
        security_by_code = dict(formal_inputs.get("security_by_code") or {})
        trading_day_status = formal_inputs.get("trading_day_status")
        history_by_code = dict(formal_inputs.get("history_by_code") or {})
    except Exception as exc:
        message = str(exc) or exc.__class__.__name__
        return {
            "status": "error",
            "items_by_code": {
                code: {
                    "status": "error",
                    "error_type": "formal_projection_failed",
                    "message": message,
                }
                for code in codes
            },
            "summary": {"total": len(codes), "ok": 0, "error": len(codes)},
        }

    items_by_code: dict[str, dict[str, Any]] = {}
    ok_count = 0
    error_count = 0
    for code in codes:
        d1_fact = d1_by_code.get(code)
        security_master = security_by_code.get(code)
        price_rows = history_by_code.get(code) or []
        try:
            if d1_fact is None:
                raise ValueError("d1_fact_missing")
            if security_master is None:
                raise ValueError("security_master_missing")
            trading_profile = project_pf1_trading_profile(
                stock_code=code,
                price_rows=price_rows,
            )
            constraints = build_m1_constraints_ref(
                d1_fact=d1_fact,
                security_master=security_master,
                trading_day_status=trading_day_status,
                trading_profile=trading_profile,
            )
            small_cycle = build_small_cycle_from_m1(
                d1_fact=d1_fact,
                security_master=security_master,
                trading_day_status=trading_day_status,
                trading_profile=trading_profile,
            )
            identify_state = build_identify_state_from_formal_inputs(
                cycle=small_cycle,
                m1_constraints_ref=constraints,
            )
            tracking_state = build_tracking_state_from_formal_inputs(
                cycle=small_cycle,
                m1_constraints_ref=constraints,
            )
            entry_state = build_entry_state_from_formal_inputs(
                cycle=small_cycle,
                m1_constraints_ref=constraints,
            )
            items_by_code[code] = {
                "status": "ok",
                "small_cycle": small_cycle.to_payload(),
                "identify_state": identify_state.to_payload(),
                "tracking_state": tracking_state.to_payload(),
                "entry_state": entry_state.to_payload(),
                "m1_constraints_ref": dict(constraints),
            }
            ok_count += 1
        except Exception as exc:
            items_by_code[code] = {
                "status": "error",
                "error_type": "formal_projection_failed",
                "message": str(exc) or exc.__class__.__name__,
            }
            error_count += 1

    return {
        "status": "ok" if error_count == 0 else "partial",
        "items_by_code": items_by_code,
        "summary": {
            "total": len(codes),
            "ok": ok_count,
            "error": error_count,
        },
    }
