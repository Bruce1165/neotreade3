from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from apps.api.main import BootstrapApiService
from neotrade3.analysis.m6_backtest_eval import (
    compute_equity_peak,
    evaluate_capture_rate,
    evaluate_hold_to_peak_with_drawdown_tolerance,
)
from neotrade3.analysis.top200_bullstocks import extract_codes, load_global_top_bullstocks


def _resolve_project_root() -> Path:
    return _PROJECT_ROOT


def _resolve_stock_db_path(project_root: Path) -> Path:
    raw = os.environ.get("NEOTRADE3_STOCK_DB_PATH")
    if isinstance(raw, str) and raw.strip():
        p = Path(raw).expanduser()
    else:
        p = project_root / "var/db/stock_data.db"
    if not p.exists() or not p.is_file():
        raise RuntimeError(f"stock db missing: {p}")
    return p


def _load_trade_date_bounds(conn: sqlite3.Connection) -> tuple[str, str]:
    row = conn.execute("SELECT MIN(trade_date), MAX(trade_date) FROM daily_prices").fetchone()
    if not row or not row[0] or not row[1]:
        raise RuntimeError("daily_prices is empty; cannot infer backtest range")
    return str(row[0]), str(row[1])


def _fail_closed_on_backfill_result(result: dict[str, Any]) -> None:
    status = str(result.get("status") or "").strip().lower()
    if status != "ok":
        raise RuntimeError(f"tushare backfill failed: status={status} reason={result.get('reason')}")
    if int(result.get("failed_days") or 0) != 0:
        raise RuntimeError(f"tushare backfill failed_days={int(result.get('failed_days') or 0)}")
    if int(result.get("skipped_days") or 0) != 0:
        raise RuntimeError(f"tushare backfill skipped_days={int(result.get('skipped_days') or 0)}")
    if int(result.get("ok_days") or 0) != int(result.get("trading_days") or 0):
        raise RuntimeError(
            f"tushare backfill ok_days={int(result.get('ok_days') or 0)} trading_days={int(result.get('trading_days') or 0)}"
        )


def _render_pdf(
    *,
    pdf_path: Path,
    meta: dict[str, Any],
    summary: dict[str, Any],
    top200_rows: list[dict[str, Any]],
    capture_payload: dict[str, Any],
    peak_payload: dict[str, Any],
) -> None:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    styles = getSampleStyleSheet()
    base = ParagraphStyle(
        "base",
        parent=styles["Normal"],
        fontName="STSong-Light",
        fontSize=9,
        leading=12,
    )
    title_style = ParagraphStyle(
        "title",
        parent=styles["Title"],
        fontName="STSong-Light",
        fontSize=16,
        leading=20,
    )

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
    )

    story: list[Any] = []
    story.append(Paragraph("M6（LowFreq V16）全量回测 Top200 评估报告", title_style))
    story.append(Spacer(1, 6 * mm))

    summary_rows = [
        ["回测区间", f"{summary.get('start_date','')} → {summary.get('end_date','')}"],
        ["初始资本", f"{summary.get('initial_capital', 0):,.0f}"],
        ["期末净值", f"{summary.get('final_value_net', 0):,.2f}"],
        ["净收益额", f"{summary.get('net_gain', 0):,.2f}"],
        ["净收益率", f"{summary.get('net_return_pct', 0):.2f}%"],
        ["净值最大回撤", f"{summary.get('max_drawdown_pct_net', 0):.2f}%"],
        ["Top200 捕获率", f"{capture_payload.get('captured_count', 0)}/200 ({capture_payload.get('capture_rate_pct', 0):.2f}%)"],
        ["峰顶守住率", f"{peak_payload.get('held_count', 0)}/{capture_payload.get('captured_count', 0)} ({peak_payload.get('held_rate_pct', 0):.2f}%)"],
    ]
    summary_table = Table(summary_rows, colWidths=[36 * mm, 146 * mm])
    summary_table.setStyle(
        TableStyle(
            [
                ("FONT", (0, 0), (-1, -1), "STSong-Light", 9),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.grey),
                ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.whitesmoke, colors.white]),
            ]
        )
    )
    story.append(summary_table)
    story.append(Spacer(1, 6 * mm))

    story.append(Paragraph("执行口径（关键）", ParagraphStyle("h2", parent=base, fontSize=12, leading=14)))
    story.append(Spacer(1, 2 * mm))
    story.append(
        Paragraph(
            "1) 数据：使用日线 close；并在回测前对 DB 覆盖区间缺口做 Tushare 回补。<br/>"
            "2) no-look-ahead：启用引擎内置 guard（未来数据引用 fail-closed）。<br/>"
            "3) Top200：全样本期 max_runup_pct（最大 run-up）倒序取前 200。<br/>"
            f"4) 峰顶守住：以策略净值峰顶为峰顶，允许峰顶后回撤不超过 {float(peak_payload.get('threshold_pct', 0.0)):.2f}% 退出也算守住。",
            base,
        )
    )
    story.append(Spacer(1, 6 * mm))

    if isinstance(top200_rows, list) and top200_rows:
        story.append(Paragraph("Top200 样本（Top10）", ParagraphStyle("h2", parent=base, fontSize=12, leading=14)))
        story.append(Spacer(1, 2 * mm))
        rows = [["rank", "code", "name", "max_runup%"]] + [
            [str(r.get("rank")), str(r.get("code")), str(r.get("name")), f"{float(r.get('max_runup_pct') or 0.0):.2f}"]
            for r in top200_rows[:10]
        ]
        t = Table(rows, colWidths=[14 * mm, 22 * mm, 48 * mm, 24 * mm])
        t.setStyle(
            TableStyle(
                [
                    ("FONT", (0, 0), (-1, -1), "STSong-Light", 9),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ]
            )
        )
        story.append(t)
        story.append(Spacer(1, 6 * mm))

    story.append(Paragraph("审计信息", ParagraphStyle("h2", parent=base, fontSize=12, leading=14)))
    story.append(Spacer(1, 2 * mm))
    audit_rows = [
        ["生成时间", str(meta.get("generated_at") or "")],
        ["DB 路径", str(meta.get("stock_db_path") or "")],
        ["策略", str(meta.get("strategy_id") or "")],
        ["策略版本", str(meta.get("strategy_version") or "")],
        ["no-look-ahead", str(meta.get("no_lookahead_enforced") or "")],
    ]
    audit_table = Table(audit_rows, colWidths=[28 * mm, 154 * mm])
    audit_table.setStyle(
        TableStyle(
            [
                ("FONT", (0, 0), (-1, -1), "STSong-Light", 9),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.grey),
                ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.whitesmoke, colors.white]),
            ]
        )
    )
    story.append(audit_table)
    doc.build(story)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--peak-drawdown-tolerance-pct", type=float, default=5.0)
    parser.add_argument("--requested-by", type=str, default="m6_full_backtest")
    args = parser.parse_args()

    project_root = _resolve_project_root()
    service = BootstrapApiService(project_root=project_root)
    stock_db_path = _resolve_stock_db_path(project_root)

    conn = sqlite3.connect(str(stock_db_path))
    try:
        start_date, end_date = _load_trade_date_bounds(conn)
        top200 = load_global_top_bullstocks(conn, limit=int(args.limit))
    finally:
        conn.close()

    raw_token = str(os.environ.get("TUSHARE_TOKEN") or "").strip()
    if not raw_token:
        raise RuntimeError(
            "TUSHARE_TOKEN not configured; set it in env or env.secrets and re-run"
        )

    backfill = service.backfill_daily_prices_tushare_range_view(
        start_date=str(start_date),
        end_date=str(end_date),
        requested_by=str(args.requested_by),
        min_close_coverage=0.99,
        min_amount_coverage=0.99,
        dry_run=False,
    )
    if not isinstance(backfill, dict):
        raise RuntimeError("unexpected backfill response")
    _fail_closed_on_backfill_result(backfill)

    engine = service._lowfreq_engine_v16()
    if not bool(getattr(engine, "NO_LOOKAHEAD_ENFORCED", False)):
        raise RuntimeError("NO_LOOKAHEAD_ENFORCED is not enabled")

    start_dt = date.fromisoformat(str(start_date))
    end_dt = date.fromisoformat(str(end_date))
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"m6_full_{start_date}_{end_date}__{stamp}"
    source_run_id = "m6_full_backtest_top200"

    result = engine.run_backtest(
        start_dt,
        end_dt,
        initial_capital=1_000_000.0,
        include_trades=True,
        include_daily_values=True,
        project_root=project_root,
        run_id=run_id,
        source_run_id=source_run_id,
    )
    if not isinstance(result, dict):
        raise RuntimeError("backtest result not a dict")

    daily_values_net = result.get("daily_values_net")
    trades = result.get("trades")
    net_metrics = result.get("net_metrics")
    if not isinstance(daily_values_net, list):
        raise RuntimeError("missing daily_values_net")
    if not isinstance(trades, list):
        raise RuntimeError("missing trades")
    if not isinstance(net_metrics, dict):
        raise RuntimeError("missing net_metrics")

    peak = compute_equity_peak(daily_values_net=daily_values_net)
    top_codes = extract_codes(top200)
    capture = evaluate_capture_rate(top_codes=top_codes, trades=trades)
    peak_hold = evaluate_hold_to_peak_with_drawdown_tolerance(
        captured_codes=capture.captured_codes,
        trades=trades,
        daily_values_net=daily_values_net,
        peak=peak,
        end_date=str(end_date),
        threshold_pct=float(args.peak_drawdown_tolerance_pct),
    )

    initial_capital = float(result.get("initial_capital") or 1_000_000.0)
    final_value_net = float(net_metrics.get("final_value") or 0.0)
    net_gain = float(final_value_net) - float(initial_capital)
    net_return_pct = float(net_metrics.get("total_return_pct") or 0.0)
    max_drawdown_pct_net = float(net_metrics.get("max_drawdown_pct") or 0.0)

    capture_rate_pct = float(capture.captured_count) / float(len(top_codes)) * 100.0
    held_rate_pct = (
        float(peak_hold.held_count) / float(max(capture.captured_count, 1)) * 100.0
    )

    meta = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "stock_db_path": str(stock_db_path),
        "strategy_id": str((result.get("config_snapshot") or {}).get("strategy_id") or ""),
        "strategy_version": str((result.get("config_snapshot") or {}).get("strategy_version") or ""),
        "no_lookahead_enforced": bool(getattr(engine, "NO_LOOKAHEAD_ENFORCED", False)),
        "run_id": run_id,
        "source_run_id": source_run_id,
    }
    summary = {
        "start_date": str(start_date),
        "end_date": str(end_date),
        "initial_capital": float(initial_capital),
        "final_value_net": float(final_value_net),
        "net_gain": float(net_gain),
        "net_return_pct": float(net_return_pct),
        "max_drawdown_pct_net": float(max_drawdown_pct_net),
        "equity_peak_date": str(peak.peak_date),
        "equity_peak_value": float(peak.peak_value),
    }
    capture_payload = {
        "captured_count": int(capture.captured_count),
        "capture_rate_pct": float(capture_rate_pct),
        "captured_codes": list(capture.captured_codes),
        "missed_codes": list(capture.missed_codes),
    }
    peak_payload = {
        "threshold_pct": float(peak_hold.threshold_pct),
        "held_count": int(peak_hold.held_count),
        "held_rate_pct": float(held_rate_pct),
        "held_codes": list(peak_hold.held_codes),
        "missed_codes": list(peak_hold.missed_codes),
        "by_code_drawdown_pct": dict(peak_hold.by_code_drawdown_pct),
    }

    reports_dir = project_root / "var/reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    base_name = f"m6_full_backtest_{start_date}_{end_date}__{stamp}"
    pdf_path = reports_dir / f"{base_name}.pdf"
    payload_path = reports_dir / f"{base_name}.json"
    top200_path = reports_dir / f"top200_bullstocks_{start_date}_{end_date}__{stamp}.json"

    payload_path.write_text(
        json.dumps(
            {
                "_meta": meta,
                "summary": summary,
                "top200": [r.to_payload() for r in top200],
                "capture": capture_payload,
                "peak_hold": peak_payload,
                "backfill": backfill,
                "engine_result": result,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    top200_path.write_text(
        json.dumps([r.to_payload() for r in top200], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    _render_pdf(
        pdf_path=pdf_path,
        meta=meta,
        summary=summary,
        top200_rows=[r.to_payload() for r in top200],
        capture_payload=capture_payload,
        peak_payload=peak_payload,
    )

    print(str(pdf_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
