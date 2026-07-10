from __future__ import annotations

import sqlite3
from datetime import date
from typing import Any, Callable

WAVE_1 = "1浪"
WAVE_3 = "3浪"
WAVE_5 = "5浪"
WAVE_B = "B浪"
WAVE_UNKNOWN = "未知"


def detect_wave_phase_from_series(
    *,
    closes: list[float],
    highs: list[float],
    lows: list[float],
) -> tuple[str, float]:
    if len(closes) < 30:
        return WAVE_UNKNOWN, 0.0

    recent_high = max(highs[:20])
    recent_low = min(lows[:20])
    prev_high = max(highs[20:40]) if len(highs) >= 40 else recent_high * 0.9

    current_price = closes[0]
    price_change_20d = (current_price - closes[19]) / closes[19] * 100 if closes[19] > 0 else 0

    if current_price > prev_high * 1.02 and price_change_20d > 10:
        return WAVE_3, 0.8
    if current_price > prev_high * 1.05 and price_change_20d > 20:
        return WAVE_5, 0.7
    if current_price < recent_low * 1.05 and price_change_20d < -10:
        return WAVE_B, 0.6
    if price_change_20d > 5:
        return WAVE_1, 0.5
    return WAVE_UNKNOWN, 0.3


def passes_core_focus_gate(
    cursor: sqlite3.Cursor,
    *,
    code: str,
    stock_name: str,
    role: str,
    target_date: date,
    market_focus_snapshot_loader: Callable[..., dict[str, Any]],
) -> tuple[bool, list[str], dict[str, Any]]:
    if str(role or "").strip() != "龙头":
        return False, ["仅允许细分赛道龙头进入正式买入主链"], {
            "focus_pass": False,
            "focus_bonus": 0.0,
        }

    snapshot = dict(
        market_focus_snapshot_loader(
            cursor,
            code=code,
            stock_name=stock_name,
            target_date=target_date,
        )
        or {}
    )
    if not bool(snapshot.get("focus_pass")):
        return False, ["未同时满足核心范围、配置高配与细分赛道龙头闸门"], snapshot

    reasons: list[str] = []
    if snapshot.get("ai_hits"):
        reasons.append(f"AI 主线命中：{', '.join(list(snapshot.get('ai_hits') or [])[:3])}")
    elif snapshot.get("hardtech_hits"):
        reasons.append(f"硬科技主线命中：{', '.join(list(snapshot.get('hardtech_hits') or [])[:3])}")
    if snapshot.get("penetration_hits"):
        reasons.append(
            f"命中渗透率重点赛道：{', '.join(list(snapshot.get('penetration_hits') or [])[:3])}"
        )
    if bool(snapshot.get("etf_index_data_ready")):
        reasons.append(
            f"ETF/指数证据通过：ETF持有人{int(snapshot.get('holder_etf_count') or 0)}，指数成分{int(snapshot.get('index_count') or 0)}，配置分{int(snapshot.get('config_score') or 0)}"
        )
    else:
        reasons.append(
            f"基金配置证据通过：基金数{int(snapshot.get('holder_fund_count') or 0)}，配置分{int(snapshot.get('config_score') or 0)}"
        )
    attention_score = int(snapshot.get("attention_score") or 0)
    if attention_score > 0:
        reasons.append(f"机构关注增强：关注分{attention_score}")
    else:
        reasons.append("机构关注未命中，本次按参考项处理")
    return True, reasons, snapshot


def apply_strong_leader_soft_release(
    *,
    score: float,
    role: str,
    wave_phase: str,
    soft_flags: list[str],
    reasons: list[str],
    release_enabled: bool = False,
    release_min_score: float = 80.0,
) -> tuple[float, list[str], list[str]]:
    if not bool(release_enabled):
        return float(score), _normalize_flags(soft_flags), list(reasons or [])

    normalized_role = str(role or "").strip()
    normalized_wave = str(wave_phase or "").strip()
    normalized_flags = _normalize_flags(soft_flags)
    if normalized_role != "龙头":
        return float(score), normalized_flags, list(reasons or [])
    if normalized_wave not in {WAVE_1, WAVE_3}:
        return float(score), normalized_flags, list(reasons or [])
    if float(score) < float(release_min_score):
        return float(score), normalized_flags, list(reasons or [])

    allowed_flags = {"focus_soft_fail", "structure_soft_fail"}
    flag_set = set(normalized_flags)
    if not flag_set or not flag_set.issubset(allowed_flags):
        return float(score), normalized_flags, list(reasons or [])

    released_flags = [flag for flag in ("structure_soft_fail", "focus_soft_fail") if flag in flag_set]
    score_delta = 0.0
    if "structure_soft_fail" in flag_set:
        score_delta += 10.0
    if "focus_soft_fail" in flag_set:
        score_delta += 8.0

    filtered_reasons: list[str] = []
    for reason in list(reasons or []):
        text = str(reason or "")
        if text == "capture-first: 结构未确认，降权保留" and "structure_soft_fail" in flag_set:
            continue
        if text == "capture-first: focus gate 未过，降权保留" and "focus_soft_fail" in flag_set:
            continue
        if text.startswith("soft:") and flag_set:
            continue
        filtered_reasons.append(text)

    release_note = f"capture-first: 高分龙头窄例外放行({'+'.join(released_flags)})"
    filtered_reasons.append(release_note)
    return float(score) + float(score_delta), [], filtered_reasons


def _normalize_flags(soft_flags: list[str]) -> list[str]:
    return [str(flag or "").strip() for flag in list(soft_flags or []) if str(flag or "").strip()]
