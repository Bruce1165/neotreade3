from __future__ import annotations

import json
import sqlite3
from datetime import date, timedelta
from pathlib import Path
from typing import Any


def ts_code_for_stock_code(code: str) -> str:
    current = str(code or "").strip()
    if not current:
        return ""
    if "." in current and len(current.split(".", 1)[0]) == 6:
        return current
    suffix = "SH" if current.startswith("6") else "SZ"
    return f"{current}.{suffix}"


def match_market_keywords(*, texts: list[str], keywords: tuple[str, ...]) -> list[str]:
    hits: list[str] = []
    seen: set[str] = set()
    normalized_texts = [
        str(text or "").strip().lower()
        for text in texts
        if str(text or "").strip()
    ]
    for keyword in keywords:
        raw_keyword = str(keyword or "").strip()
        if not raw_keyword:
            continue
        key = raw_keyword.lower()
        if key in seen:
            continue
        if any(key in text for text in normalized_texts):
            hits.append(raw_keyword)
            seen.add(key)
    return hits


def market_ai_keywords() -> tuple[str, ...]:
    return (
        "AI",
        "人工智能",
        "算力",
        "国产算力",
        "AIDC",
        "数据中心",
        "东数西算",
        "液冷",
        "服务器",
        "光模块",
        "CPO",
        "铜缆",
        "GPU",
        "芯片",
        "半导体",
        "存储",
        "HBM",
        "先进封装",
        "机器人",
        "人形机器人",
        "减速器",
        "伺服",
        "传感器",
        "控制器",
        "自动驾驶",
        "智驾",
    )


def market_kshape_up_keywords() -> tuple[str, ...]:
    return market_ai_keywords() + (
        "商业航天",
        "低空经济",
        "卫星",
        "火箭",
        "创新药",
        "医疗器械",
        "高端医疗器械",
        "新材料",
        "电子特气",
        "靶材",
        "光刻",
        "晶圆",
        "算力底座",
    )


def market_kshape_down_keywords() -> tuple[str, ...]:
    return (
        "高股息",
        "电力",
        "公用事业",
        "银行",
        "煤炭",
        "有色",
        "港口",
        "高速",
        "铁路",
        "基建",
        "消费",
        "物流",
        "文创",
        "互联网",
        "保险",
        "券商",
        "财富管理",
        "公募",
        "资管",
        "ESG",
        "信披",
        "数据服务",
    )


def market_head_broker_names() -> tuple[str, ...]:
    return (
        "中信证券",
        "华泰证券",
        "国泰海通",
        "东方财富",
        "中金公司",
    )


def table_exists(cursor: sqlite3.Cursor, table: str) -> bool:
    row = cursor.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
        (table,),
    ).fetchone()
    return row is not None


def table_has_rows(cursor: sqlite3.Cursor, table: str, *, nonempty_table_cache: dict[str, bool]) -> bool:
    cached = nonempty_table_cache.get(str(table))
    if cached is not None:
        return bool(cached)
    if not table_exists(cursor, table):
        nonempty_table_cache[str(table)] = False
        return False
    row = cursor.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone()
    has_rows = row is not None
    nonempty_table_cache[str(table)] = bool(has_rows)
    return bool(has_rows)


def load_stock_concepts_cache(
    *,
    themes_snapshot_dir: Path,
    stock_concepts_cache: dict[str, list[dict[str, str]]] | None,
) -> dict[str, list[dict[str, str]]]:
    if stock_concepts_cache is not None:
        return stock_concepts_cache

    concepts_cache_path = themes_snapshot_dir / "_tushare_concepts_cache.json"
    members_cache_path = themes_snapshot_dir / "_tushare_concept_members_cache.json"
    concept_name_by_code: dict[str, str] = {}
    stock_concepts: dict[str, list[dict[str, str]]] = {}

    try:
        cache_doc = json.loads(concepts_cache_path.read_text(encoding="utf-8")) if concepts_cache_path.exists() else None
    except (OSError, json.JSONDecodeError):
        cache_doc = None
    items = cache_doc.get("items") if isinstance(cache_doc, dict) else None
    if isinstance(items, list):
        for item in items:
            if not isinstance(item, dict):
                continue
            code = str(item.get("code") or "").strip()
            name = str(item.get("name") or "").strip()
            if code and name:
                concept_name_by_code[code] = name

    try:
        members_doc = json.loads(members_cache_path.read_text(encoding="utf-8")) if members_cache_path.exists() else None
    except (OSError, json.JSONDecodeError):
        members_doc = None
    concepts_map = members_doc.get("concepts") if isinstance(members_doc, dict) else None
    if isinstance(concepts_map, dict):
        for concept_code, entry in concepts_map.items():
            if not isinstance(entry, dict):
                continue
            concept_name = str(concept_name_by_code.get(str(concept_code)) or entry.get("name") or "").strip()
            stocks = entry.get("stocks")
            if not concept_name or not isinstance(stocks, list):
                continue
            for stock in stocks:
                if not isinstance(stock, dict):
                    continue
                code = str(stock.get("code") or "").strip()
                if not code:
                    continue
                stock_concepts.setdefault(code, []).append(
                    {
                        "concept_code": str(concept_code),
                        "concept_name": concept_name,
                    }
                )

    return {
        str(code): [dict(item) for item in items]
        for code, items in stock_concepts.items()
    }


def load_penetration_keywords(
    *,
    market_intelligence_config_dir: Path,
    penetration_keywords_cache: tuple[str, ...] | None,
) -> tuple[str, ...]:
    if penetration_keywords_cache is not None:
        return tuple(penetration_keywords_cache)
    config_path = market_intelligence_config_dir / "penetration_stages.json"
    keywords: list[str] = []
    try:
        doc = json.loads(config_path.read_text(encoding="utf-8")) if config_path.exists() else None
    except (OSError, json.JSONDecodeError):
        doc = None
    items = doc.get("items") if isinstance(doc, dict) else None
    if isinstance(items, list):
        for item in items:
            if not isinstance(item, dict):
                continue
            if str(item.get("match_type") or "").strip() != "keyword":
                continue
            keyword = str(item.get("match_value") or "").strip()
            if keyword:
                keywords.append(keyword)
    return tuple(dict.fromkeys(keywords))


def build_market_focus_snapshot(
    cursor: sqlite3.Cursor,
    *,
    code: str,
    stock_name: str,
    target_date: date,
    market_focus_cache: dict[tuple[str, str], dict[str, Any]],
    nonempty_table_cache: dict[str, bool],
    stock_concepts_cache: dict[str, list[dict[str, str]]],
    penetration_keywords: tuple[str, ...],
) -> dict[str, Any]:
    cache_key = (str(code), target_date.isoformat())
    if cache_key in market_focus_cache:
        return dict(market_focus_cache[cache_key])

    stock_concepts = stock_concepts_cache.get(str(code), [])
    concept_names = [
        str(item.get("concept_name") or "").strip()
        for item in stock_concepts
        if isinstance(item, dict)
    ]
    texts = [str(stock_name or "").strip(), str(code or "").strip(), *concept_names]
    ai_hits = match_market_keywords(texts=texts, keywords=market_ai_keywords())
    hardtech_hits = match_market_keywords(texts=texts, keywords=market_kshape_up_keywords())
    down_hits = match_market_keywords(texts=texts, keywords=market_kshape_down_keywords())
    penetration_hits = match_market_keywords(texts=texts, keywords=penetration_keywords)

    target_key = target_date.isoformat()
    ts_code = ts_code_for_stock_code(code)
    holder_etf_count = 0
    holder_fund_count = 0
    total_mkv = None
    avg_ratio = None
    index_count = 0

    fund_portfolios_ready = table_has_rows(cursor, "fund_portfolios", nonempty_table_cache=nonempty_table_cache)
    etf_basic_ready = table_has_rows(cursor, "etf_basic_info", nonempty_table_cache=nonempty_table_cache)
    index_weights_ready = table_has_rows(cursor, "index_weights", nonempty_table_cache=nonempty_table_cache)

    if fund_portfolios_ready:
        symbol_candidates = tuple(dict.fromkeys([str(code), ts_code]))
        symbol_placeholders = ",".join(["?"] * len(symbol_candidates))
        latest_ann_row = cursor.execute(
            f"SELECT MAX(ann_date) FROM fund_portfolios WHERE symbol IN ({symbol_placeholders}) AND ann_date <= ?",
            (*symbol_candidates, target_key),
        ).fetchone()
        latest_ann_date = str(latest_ann_row[0]) if latest_ann_row and latest_ann_row[0] is not None else None
        if latest_ann_date:
            agg = cursor.execute(
                f"""
                SELECT
                    COUNT(DISTINCT fp.ts_code),
                    COUNT(DISTINCT CASE WHEN eb.ts_code IS NOT NULL THEN fp.ts_code END),
                    SUM(fp.mkv),
                    AVG(fp.stk_mkv_ratio)
                FROM fund_portfolios fp
                LEFT JOIN etf_basic_info eb ON eb.ts_code = fp.ts_code
                WHERE fp.symbol IN ({symbol_placeholders})
                  AND fp.ann_date = ?
                """,
                (*symbol_candidates, latest_ann_date),
            ).fetchone()
            holder_fund_count = int((agg[0] if agg else 0) or 0)
            holder_etf_count = int((agg[1] if agg else 0) or 0)
            total_mkv = float(agg[2]) if agg and isinstance(agg[2], (int, float)) else None
            avg_ratio = float(agg[3]) if agg and isinstance(agg[3], (int, float)) else None

    if index_weights_ready and ts_code:
        latest_index_row = cursor.execute(
            "SELECT MAX(trade_date) FROM index_weights WHERE con_code = ? AND trade_date <= ?",
            (ts_code, target_key),
        ).fetchone()
        latest_index_date = str(latest_index_row[0]) if latest_index_row and latest_index_row[0] is not None else None
        if latest_index_date:
            count_row = cursor.execute(
                "SELECT COUNT(DISTINCT index_code) FROM index_weights WHERE con_code = ? AND trade_date = ?",
                (ts_code, latest_index_date),
            ).fetchone()
            index_count = int((count_row[0] if count_row else 0) or 0)

    config_score = 0
    if holder_etf_count > 0:
        config_score += 1
    if holder_fund_count >= 3:
        config_score += 1
    if isinstance(total_mkv, (int, float)) and float(total_mkv) > 0:
        config_score += 1
    if isinstance(avg_ratio, (int, float)) and float(avg_ratio) >= 3.0:
        config_score += 1
    if index_count > 0:
        config_score += 1

    start_90 = (target_date - timedelta(days=90)).isoformat()
    start_180 = (target_date - timedelta(days=180)).isoformat()
    research_inst = 0
    consensus_orgs = 0
    survey_orgs = 0
    survey_count = 0

    if table_has_rows(cursor, "research_reports", nonempty_table_cache=nonempty_table_cache) and ts_code:
        row = cursor.execute(
            """
            SELECT COUNT(DISTINCT inst_csname)
            FROM research_reports
            WHERE ts_code = ?
              AND trade_date >= ?
              AND trade_date <= ?
            """,
            (ts_code, start_90, target_key),
        ).fetchone()
        research_inst = int((row[0] if row else 0) or 0)

    if table_has_rows(cursor, "report_consensus", nonempty_table_cache=nonempty_table_cache) and ts_code:
        row = cursor.execute(
            """
            SELECT COUNT(DISTINCT org_name)
            FROM report_consensus
            WHERE ts_code = ?
              AND report_date <= ?
            """,
            (ts_code, target_key),
        ).fetchone()
        consensus_orgs = int((row[0] if row else 0) or 0)

    if table_has_rows(cursor, "institutional_surveys", nonempty_table_cache=nonempty_table_cache) and ts_code:
        row = cursor.execute(
            """
            SELECT COUNT(1), COUNT(DISTINCT rece_org)
            FROM institutional_surveys
            WHERE ts_code = ?
              AND surv_date >= ?
              AND surv_date <= ?
            """,
            (ts_code, start_180, target_key),
        ).fetchone()
        survey_count = int((row[0] if row else 0) or 0)
        survey_orgs = int((row[1] if row else 0) or 0)

    attention_score = 0
    if research_inst >= 1:
        attention_score += 1
    if consensus_orgs >= 1:
        attention_score += 1
    if survey_orgs >= 1:
        attention_score += 1
    if survey_count >= 1:
        attention_score += 1

    is_ai_metal_exception = "小金属" in "".join(texts) and bool(ai_hits)
    is_head_broker_exception = str(stock_name or "").strip() in market_head_broker_names()
    second_category_focus = bool(ai_hits or hardtech_hits or penetration_hits)
    allowed_exception = bool(is_ai_metal_exception or is_head_broker_exception)
    etf_index_data_ready = bool(etf_basic_ready or index_weights_ready)
    etf_index_evidence = bool(holder_etf_count > 0 or index_count > 0)
    fund_config_evidence = bool(
        holder_fund_count >= 3
        or (isinstance(avg_ratio, (int, float)) and float(avg_ratio) >= 3.0)
        or (isinstance(total_mkv, (int, float)) and float(total_mkv) > 0)
    )
    focus_pass = (
        (second_category_focus or allowed_exception)
        and config_score >= 2
        and (etf_index_evidence if etf_index_data_ready else fund_config_evidence)
    )
    focus_bonus = 12.0 if ai_hits else 8.0 if second_category_focus else 4.0 if allowed_exception else 0.0

    snapshot = {
        "focus_pass": bool(focus_pass),
        "focus_bonus": float(focus_bonus),
        "second_category_focus": bool(second_category_focus),
        "allowed_exception": bool(allowed_exception),
        "ai_hits": list(ai_hits),
        "hardtech_hits": list(hardtech_hits),
        "down_hits": list(down_hits),
        "penetration_hits": list(penetration_hits),
        "holder_etf_count": int(holder_etf_count),
        "holder_fund_count": int(holder_fund_count),
        "index_count": int(index_count),
        "config_score": int(config_score),
        "attention_score": int(attention_score),
        "research_inst": int(research_inst),
        "consensus_orgs": int(consensus_orgs),
        "survey_orgs": int(survey_orgs),
        "survey_count": int(survey_count),
        "etf_index_data_ready": bool(etf_index_data_ready),
        "etf_index_evidence": bool(etf_index_evidence),
        "fund_config_evidence": bool(fund_config_evidence),
    }
    market_focus_cache[cache_key] = dict(snapshot)
    return snapshot
