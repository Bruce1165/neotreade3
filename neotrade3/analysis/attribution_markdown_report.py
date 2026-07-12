"""Markdown formatter helpers for lowfreq attribution report consumers."""

from __future__ import annotations

from collections import Counter
from typing import Any


def build_attribution_markdown_report(
    *,
    year: int,
    limit: int,
    ranking: list[dict[str, Any]],
    aggregate: dict[str, Any],
    attribution_rows: list[dict[str, Any]],
    backtest_payload: dict[str, Any],
) -> str:
    top_reasons = Counter(str(x.get("reason_bucket") or "") for x in attribution_rows)
    candidate_only_rows = [x for x in attribution_rows if x.get("candidate_picked") and not x.get("entry_picked")]
    not_picked_rows = [x for x in attribution_rows if not x.get("candidate_picked")]
    early_exits = [x for x in attribution_rows if x.get("bought") and not x.get("held_to_top")]

    lines: list[str] = []
    lines.append(f"# Lowfreq Model {int(year)} Top{int(limit)} Scorecard Report")
    lines.append("")
    lines.append("## 口径说明")
    lines.append("")
    lines.append("- 年度涨幅口径：未复权收盘价，使用年内首个有效交易日与最后一个有效交易日。")
    lines.append("- 主升段起点：见顶日前 180 个交易日窗口内最低收盘价。")
    lines.append("- 见顶日期：2025 年内最高收盘价所在交易日。")
    lines.append("- 分层信号口径：`candidate_signals` 表示进入候选池，`entry_signals` 表示进入正式建仓池；active 归因不再读取旧 `buy_signals` 别名。")
    lines.append("- 模型行为口径：当前引擎主动离场归因为 `market_top_confirmed`、`sector_top_confirmed`、`thesis_invalidated`。")
    lines.append("")
    lines.append("## 总体摘要")
    lines.append("")
    lines.append(f"- Top{int(limit)} count: {len(ranking)}")
    lines.append(f"- 进入候选池：{aggregate.get('candidate_picked_count', 0)}")
    lines.append(f"- 进入正式建仓池：{aggregate.get('entry_picked_count', 0)}")
    lines.append(f"- 实际买入：{aggregate.get('bought_count', 0)}")
    lines.append(f"- 持有到市场事实见顶：{aggregate.get('held_to_top_count', 0)}")

    summary = backtest_payload.get("summary") if isinstance(backtest_payload, dict) else {}
    if isinstance(summary, dict) and summary:
        lines.append(
            f"- 当前18个月回测摘要：总收益 {summary.get('total_return_pct', 0)}%，最大回撤 {summary.get('max_drawdown_pct', 0)}%，交易数 {summary.get('total_trades', 0)}"
        )

    lines.append("")
    lines.append("## 原因分布")
    lines.append("")
    for reason, count in top_reasons.most_common():
        lines.append(f"- {reason}: {count}")

    lines.append("")
    lines.append("## 典型候选未转建仓样本")
    lines.append("")
    for row in candidate_only_rows[:20]:
        lines.append(
            f"- {row['code']} {row['name']} | 年涨幅 {row['annual_return_pct']:.2f}% | 起涨 {row['segment_start_date']} | 首次候选 {row['first_candidate_date']} | 原因：{row['primary_reason']}"
        )

    lines.append("")
    lines.append("## 典型未进候选样本")
    lines.append("")
    for row in not_picked_rows[:20]:
        lines.append(
            f"- {row['code']} {row['name']} | 年涨幅 {row['annual_return_pct']:.2f}% | 起涨 {row['segment_start_date']} | 见顶 {row['segment_top_date']} | 原因：{row['primary_reason']}"
        )

    lines.append("")
    lines.append("## 典型提前离场样本")
    lines.append("")
    for row in early_exits[:20]:
        lines.append(
            f"- {row['code']} {row['name']} | 买入 {row['first_buy_date']} | 卖出 {row['first_sell_date']} | 见顶 {row['segment_top_date']} | 原因：{row['primary_reason']}"
        )

    return "\n".join(lines) + "\n"
