"""
因子矩阵生成模块 (Factor Matrix Builder)

核心模块：整合市场阶段、板块轮动、个股分层、筛选器命中、实验室信号等多维因子，
为每只股票生成综合评分（technical / sentiment / composite / overall），
并按 certainty 分层输出。

输出格式与已有 var/artifacts/factor_matrix/{date}/factor_matrix_daily.json 完全兼容。
"""

from __future__ import annotations

import json
import sqlite3
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from neotrade3.analysis.market_phase import (
    MarketPhase,
    MarketPhaseResult,
    detect_market_phase,
)
from neotrade3.analysis.stock_tiering import (
    StockTieringAnalyzer,
    StockTieringResult,
)
from neotrade3.analysis.sector_rotation import (
    SectorRotationAnalyzer,
    SectorRotationResult,
)
from neotrade3.analysis.resonance_scorer import (
    ResonanceScorer,
    MarketPhase as ResonanceMarketPhase,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 市场阶段中文映射
# ---------------------------------------------------------------------------
_MARKET_PHASE_DISPLAY: dict[str, str] = {
    "bull": "牛市",
    "bear": "熊市",
    "range": "震荡市",
    "transition": "过渡期",
}


def _clamp(value: float, lo: float, hi: float) -> float:
    """将数值限制在 [lo, hi] 区间内。"""
    return max(lo, min(hi, value))


def _market_phase_code(mp: MarketPhaseResult) -> str:
    """从 MarketPhaseResult 提取阶段代码字符串。"""
    return mp.phase.value if hasattr(mp.phase, "value") else str(mp.phase)


def _market_phase_display(mp: MarketPhaseResult) -> str:
    """从 MarketPhaseResult 提取中文显示名。"""
    code = _market_phase_code(mp)
    return _MARKET_PHASE_DISPLAY.get(code, "未知")


def _resonance_market_phase(mp: MarketPhaseResult) -> ResonanceMarketPhase:
    """将 market_phase 模块的 MarketPhase 映射到 resonance_scorer 模块的 MarketPhase。"""
    mapping = {
        MarketPhase.BULL: ResonanceMarketPhase.BULL,
        MarketPhase.BEAR: ResonanceMarketPhase.BEAR,
        MarketPhase.RANGE: ResonanceMarketPhase.RANGE,
        MarketPhase.TRANSITION: ResonanceMarketPhase.TRANSITION,
    }
    return mapping.get(mp.phase, ResonanceMarketPhase.TRANSITION)


class FactorMatrixBuilder:
    """因子矩阵构建器。

    Parameters
    ----------
    db_path : str | Path
        SQLite 数据库路径（包含 daily_prices、stocks 表）。
    project_root : str | Path | None
        项目根目录，用于定位 var/ 下的 artifacts / ledgers。
        若为 None，则在 save/load 时必须显式传入。
    """

    def __init__(
        self,
        db_path: str | Path,
        project_root: str | Path | None = None,
    ) -> None:
        self.db_path = Path(db_path)
        self.project_root = Path(project_root) if project_root else None

        # 缓存：在一次 build() 调用中复用
        self._market_phase: MarketPhaseResult | None = None
        self._sector_rotation: SectorRotationResult | None = None
        self._stock_tiering: StockTieringResult | None = None
        self._screener_hits: dict[str, list[dict[str, Any]]] | None = None
        self._lab_hits: dict[str, list[dict[str, Any]]] | None = None

        # 预计算的辅助映射
        self._sector_rank: dict[str, int] = {}
        self._stock_sector_rps: dict[str, dict[str, Any]] = {}
        self._stock_tier_map: dict[str, dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # 主入口
    # ------------------------------------------------------------------
    def build(
        self,
        target_date: str,
        universe_limit: int = 300,
        debug: bool = False,
    ) -> dict[str, Any]:
        """构建因子矩阵。

        Parameters
        ----------
        target_date : str
            目标交易日期，格式 YYYY-MM-DD。
        universe_limit : int
            股票池上限（按成交额降序取前 N 只）。
        debug : bool
            是否在 payload 中保留调试信息。

        Returns
        -------
        dict[str, Any]
            与已有 artifact 格式完全兼容的 payload 字典。
        """
        # 1. 选股 universe
        universe = self._select_universe(target_date, universe_limit)
        if not universe:
            logger.warning("universe 为空，target_date=%s", target_date)
            return self._empty_payload(target_date, debug)

        # 2. 市场阶段
        mp_result = self._detect_market_phase(target_date)

        # 3. 板块轮动
        sr_result = self._compute_sector_rotation(target_date)

        # 4. 个股分层
        st_result = self._compute_stock_tiering(target_date)

        # 5. 筛选器命中
        screener_data = self._load_screener_hits(target_date)

        # 6. 实验室命中
        lab_data = self._load_lab_hits(target_date)

        # 7. 构建上下文
        context = {
            "market_phase": mp_result,
            "sector_rotation": sr_result,
            "stock_tiering": st_result,
            "screener_hits": screener_data,
            "lab_hits": lab_data,
            "sector_rank": self._sector_rank,
            "stock_sector_rps": self._stock_sector_rps,
            "stock_tier_map": self._stock_tier_map,
            "universe_size": len(universe),
            "resonance_scorer": None,
            "debug": debug,
        }

        # 初始化共振评分器
        try:
            rmp = _resonance_market_phase(mp_result)
            context["resonance_scorer"] = ResonanceScorer(market_phase=rmp)
        except Exception as exc:
            logger.warning("初始化 ResonanceScorer 失败: %s", exc)

        # 8. 逐股计算
        candidates: list[dict[str, Any]] = []
        for row in universe:
            try:
                candidate = self._compute_candidate(row, context)
                candidates.append(candidate)
            except Exception as exc:
                logger.debug("计算 candidate 失败 %s: %s", row["stock_code"], exc)

        # 9. 按 certainty 降序排序，分层
        candidates.sort(key=lambda c: c.get("certainty", 0), reverse=True)
        ge_80 = [c for c in candidates if c["certainty"] >= 80]
        ge_70 = [c for c in candidates if 70 <= c["certainty"] < 80]
        ge_60 = [c for c in candidates if 60 <= c["certainty"] < 70]

        # 10. 组装 payload
        payload = self._assemble_payload(
            target_date=target_date,
            universe_limit=universe_limit,
            mp_result=mp_result,
            sr_result=sr_result,
            screener_data=screener_data,
            lab_data=lab_data,
            ge_80=ge_80,
            ge_70=ge_70,
            ge_60=ge_60,
            candidates=candidates,
            debug=debug,
        )
        return payload

    # ------------------------------------------------------------------
    # 1. 选股 universe
    # ------------------------------------------------------------------
    def _select_universe(
        self,
        target_date: str,
        limit: int | None,
    ) -> list[dict[str, Any]]:
        """按成交额降序选取股票 universe。

        若 target_date 无数据，自动回退到最近一个有数据的交易日。
        limit 为 None 时表示全量（无限制）。
        """
        # 动态构建 SQL：limit 为 None 时不加 LIMIT 子句
        limit_clause = "LIMIT ?" if limit is not None else ""
        params = (target_date, limit) if limit is not None else (target_date,)

        sql = f"""
        SELECT dp.code as stock_code, s.name as stock_name, s.sector_lv1, s.sector_lv2,
               dp.amount, dp.pct_change, dp.close, dp.volume, 0.0 as turnover,
               NULL as pe_ratio, NULL as pb_ratio, NULL as roe, NULL as total_market_cap, NULL as circulating_market_cap
        FROM daily_prices dp
        JOIN stocks s ON dp.code = s.code
        WHERE dp.trade_date = ? AND (s.is_delisted IS NULL OR s.is_delisted = 0)
          AND dp.code NOT LIKE '399%' AND dp.code NOT LIKE '43%'
          AND dp.code NOT LIKE '83%' AND dp.code NOT LIKE '87%' AND dp.code NOT LIKE '88%'
          AND s.name NOT LIKE '%ST%' AND s.name NOT LIKE '%PT%'
        ORDER BY dp.amount DESC
        {limit_clause}
        """
        rows = self._query_with_fallback(sql, target_date, params)
        if not rows:
            return []
        # sqlite3.Row -> dict
        return [dict(r) for r in rows]

    def _query_with_fallback(
        self,
        sql: str,
        target_date: str,
        params: tuple,
        max_fallback_days: int = 10,
    ) -> list[sqlite3.Row]:
        """执行查询，若 target_date 无数据则回退到最近有数据的交易日。"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql, params).fetchall()
            if rows:
                conn.close()
                return rows

            # 回退：查找最近的交易日
            fallback_sql = """
            SELECT DISTINCT trade_date FROM daily_prices
            WHERE trade_date < ?
            ORDER BY trade_date DESC
            LIMIT ?
            """
            fallback_rows = conn.execute(
                fallback_sql, (target_date, max_fallback_days)
            ).fetchall()
            conn.close()

            for fr in fallback_rows:
                fb_date = fr["trade_date"]
                conn2 = sqlite3.connect(str(self.db_path))
                conn2.row_factory = sqlite3.Row
                fb_params = (fb_date,) + params[1:]
                fb_rows = conn2.execute(sql, fb_params).fetchall()
                conn2.close()
                if fb_rows:
                    logger.info(
                        "target_date=%s 无数据，回退到 %s", target_date, fb_date
                    )
                    return fb_rows
            return []
        except Exception as exc:
            logger.error("查询数据库失败: %s", exc)
            return []

    # ------------------------------------------------------------------
    # 2. 市场阶段检测
    # ------------------------------------------------------------------
    def _detect_market_phase(self, target_date: str) -> MarketPhaseResult:
        """调用 market_phase.detect_market_phase，失败时返回默认值。"""
        if self._market_phase is not None:
            return self._market_phase
        try:
            result = detect_market_phase(
                db_path=str(self.db_path), target_date=target_date
            )
        except Exception as exc:
            logger.warning("市场阶段检测失败: %s", exc)
            result = MarketPhaseResult(
                phase=MarketPhase.TRANSITION,
                confidence=0.0,
                market_return_20d=0.0,
                market_return_60d=0.0,
                market_breadth=0.5,
                ma20_slope=0.0,
                ma60_slope=0.0,
                total_amount=0.0,
                amount_trend="unknown",
            )
        self._market_phase = result
        return result

    # ------------------------------------------------------------------
    # 3. 板块轮动
    # ------------------------------------------------------------------
    def _compute_sector_rotation(
        self, target_date: str
    ) -> SectorRotationResult:
        """调用 SectorRotationAnalyzer，构建板块排名映射和个股 RPS 映射。"""
        if self._sector_rotation is not None:
            return self._sector_rotation
        try:
            analyzer = SectorRotationAnalyzer(db_path=str(self.db_path))
            result = analyzer.analyze(target_date=target_date)

            # 构建 sector_rank: sector_name -> rank (1-5)
            self._sector_rank = {}
            for idx, sr in enumerate(result.top_sectors[:5], start=1):
                self._sector_rank[sr.sector_name] = idx

            # 构建 stock_sector_rps: code -> {rps_120, is_mainline}
            self._stock_sector_rps = {}
            for sr in result.top_sectors:
                # 从板块轮动结果中提取板块 RPS 信息
                # 注：板块级 RPS，个股级映射需要额外查询
                pass

        except Exception as exc:
            logger.warning("板块轮动分析失败: %s", exc)
            result = SectorRotationResult(
                analysis_date=target_date,
                top_sectors=[],
                weakening_sectors=[],
                mainline_sectors=[],
                emerging_sectors=[],
                rotation_signal="unknown",
                market_context={},
            )
        self._sector_rotation = result
        return result

    # ------------------------------------------------------------------
    # 4. 个股分层
    # ------------------------------------------------------------------
    def _compute_stock_tiering(
        self, target_date: str
    ) -> StockTieringResult:
        """调用 StockTieringAnalyzer，构建 stock_tier_map。"""
        if self._stock_tiering is not None:
            return self._stock_tiering
        try:
            analyzer = StockTieringAnalyzer(db_path=str(self.db_path))
            result = analyzer.analyze(target_date=target_date)

            # 构建 stock_tier_map: code -> {tier, leadership_score}
            self._stock_tier_map = {}
            for sector_tier in result.sectors:
                for ts in sector_tier.leaders:
                    self._stock_tier_map[ts.code] = {
                        "tier": "leader",
                        "leadership_score": round(ts.metrics.leadership_score, 2),
                    }
                for ts in sector_tier.cores:
                    self._stock_tier_map[ts.code] = {
                        "tier": "core",
                        "leadership_score": round(ts.metrics.leadership_score, 2),
                    }
                for ts in sector_tier.followers:
                    self._stock_tier_map[ts.code] = {
                        "tier": "follower",
                        "leadership_score": round(ts.metrics.leadership_score, 2),
                    }
        except Exception as exc:
            logger.warning("个股分层分析失败: %s", exc)
            result = StockTieringResult(
                target_date=target_date,
                sectors=[],
                all_tiered_stocks=[],
            )
        self._stock_tiering = result
        return result

    # ------------------------------------------------------------------
    # 5. 筛选器命中加载
    # ------------------------------------------------------------------
    def _load_screener_hits(
        self, target_date: str
    ) -> dict[str, list[dict[str, Any]]]:
        """从 var/artifacts/screener_runs/{date}/ 读取筛选器命中结果。

        Returns
        -------
        dict[str, list[dict]]
            {screener_name: [stock_code, ...]} 或 {screener_name: [detail_dict, ...]}
        """
        if self._screener_hits is not None:
            return self._screener_hits

        hits: dict[str, list[dict[str, Any]]] = {}
        if not self.project_root:
            self._screener_hits = hits
            return hits

        artifacts_dir = (
            self.project_root / "var" / "artifacts" / "screener_runs" / target_date
        )
        ledgers_dir = (
            self.project_root / "var" / "ledgers" / "screener_runs" / target_date
        )

        for search_dir in [artifacts_dir, ledgers_dir]:
            if not search_dir.is_dir():
                continue
            for fp in sorted(search_dir.glob("*.json")):
                try:
                    data = json.loads(fp.read_text(encoding="utf-8"))
                    name = fp.stem  # e.g. "screener_daily_hot_cold_result"
                    # 提取股票列表
                    stock_list = self._extract_stock_codes_from_screener(data, name)
                    if stock_list:
                        hits[name] = stock_list
                except Exception as exc:
                    logger.debug("读取筛选器文件 %s 失败: %s", fp, exc)

        self._screener_hits = hits
        return hits

    @staticmethod
    def _extract_stock_codes_from_screener(
        data: Any, name: str
    ) -> list[dict[str, Any]]:
        """从筛选器结果中提取股票代码列表。

        支持多种格式：
        - {"picked": [{"code": "000725", ...}, ...]}
        - {"hits": ["000725", ...]}
        - {"pool": ["000725", ...]}
        - 扁平列表 ["000725", ...]
        """
        if isinstance(data, list):
            return [{"code": str(c)} for c in data]
        if not isinstance(data, dict):
            return []

        # picked 列表（常见于 screener result）
        for key in ("picked", "picked_examples", "hits", "pool", "stocks"):
            if key in data and isinstance(data[key], list):
                items = data[key]
                result: list[dict[str, Any]] = []
                for item in items:
                    if isinstance(item, dict):
                        code = item.get("code") or item.get("stock_code")
                        if code:
                            entry: dict[str, Any] = {"code": str(code)}
                            if "name" in item:
                                entry["name"] = item["name"]
                            result.append(entry)
                    elif isinstance(item, str):
                        result.append({"code": item})
                if result:
                    return result
        return []

    # ------------------------------------------------------------------
    # 6. 实验室命中加载
    # ------------------------------------------------------------------
    def _load_lab_hits(
        self, target_date: str
    ) -> dict[str, list[dict[str, Any]]]:
        """从 var/artifacts/lab_runs/{date}/ 读取实验室命中结果。

        Returns
        -------
        dict[str, list[dict]]
            {lab_name: [{"code": ..., "name": ...}, ...]}
        """
        if self._lab_hits is not None:
            return self._lab_hits

        hits: dict[str, list[dict[str, Any]]] = {}
        if not self.project_root:
            self._lab_hits = hits
            return hits

        lab_dir = self.project_root / "var" / "artifacts" / "lab_runs" / target_date
        if not lab_dir.is_dir():
            self._lab_hits = hits
            return hits

        for fp in sorted(lab_dir.glob("*.json")):
            try:
                data = json.loads(fp.read_text(encoding="utf-8"))
                name = fp.stem  # e.g. "lab_five_flags_lab_result"
                lab_info = self._extract_lab_info(data, name)
                if lab_info:
                    hits[name] = lab_info
            except Exception as exc:
                logger.debug("读取实验室文件 %s 失败: %s", fp, exc)

        self._lab_hits = hits
        return hits

    @staticmethod
    def _extract_lab_info(
        data: Any, name: str
    ) -> list[dict[str, Any]]:
        """从实验室结果中提取股票列表和实验室元信息。"""
        if not isinstance(data, dict):
            return []

        lab_name = data.get("lab_name", name.replace("lab_", "").replace("_result", ""))
        lab_id = data.get("lab_id", name)

        # 查找 artifacts 下的 pool / hits / stocks 列表
        artifacts = data.get("artifacts", data)
        if isinstance(artifacts, dict):
            for _key, value in artifacts.items():
                if isinstance(value, dict):
                    for sub_key in ("pool", "hits", "stocks", "candidates", "positions"):
                        if sub_key in value and isinstance(value[sub_key], list):
                            codes = value[sub_key]
                            return [
                                {
                                    "code": str(c) if isinstance(c, (str, int)) else str(c.get("code", "")),
                                    "lab_name": lab_name,
                                    "lab_id": lab_id,
                                }
                                for c in codes
                                if c
                            ]
                    trades = value.get("trades")
                    if isinstance(trades, dict):
                        for trade_key in ("entry_trades", "exit_trades"):
                            trade_items = trades.get(trade_key)
                            if isinstance(trade_items, list):
                                return [
                                    {
                                        "code": str(c) if isinstance(c, (str, int)) else str(c.get("code", "")),
                                        "lab_name": lab_name,
                                        "lab_id": lab_id,
                                    }
                                    for c in trade_items
                                    if c
                                ]

        # 直接在顶层查找
        for key in ("pool", "hits", "stocks", "candidates", "positions"):
            if key in data and isinstance(data[key], list):
                codes = data[key]
                return [
                    {
                        "code": str(c) if isinstance(c, (str, int)) else str(c.get("code", "")),
                        "lab_name": lab_name,
                        "lab_id": lab_id,
                    }
                    for c in codes
                    if c
                ]
        trades = data.get("trades")
        if isinstance(trades, dict):
            for trade_key in ("entry_trades", "exit_trades"):
                trade_items = trades.get(trade_key)
                if isinstance(trade_items, list):
                    return [
                        {
                            "code": str(c) if isinstance(c, (str, int)) else str(c.get("code", "")),
                            "lab_name": lab_name,
                            "lab_id": lab_id,
                        }
                        for c in trade_items
                        if c
                    ]
        return []

    # ------------------------------------------------------------------
    # 7. 单股因子计算
    # ------------------------------------------------------------------
    def _compute_candidate(
        self,
        row: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """为单只股票计算全部因子，返回 candidate 字典。"""
        code = row["stock_code"]
        name = row["stock_name"]
        sector_lv1 = row.get("sector_lv1") or ""
        sector_lv2 = row.get("sector_lv2") or ""
        amount = row.get("amount") or 0.0
        pct_change = row.get("pct_change") or 0.0
        close = row.get("close") or 0.0
        volume = row.get("volume") or 0.0
        turnover = row.get("turnover") or 0.0
        pe_ratio = row.get("pe_ratio") or 0.0
        pb_ratio = row.get("pb_ratio") or 0.0
        roe = row.get("roe") or 0.0
        total_market_cap = row.get("total_market_cap") or 0.0
        circulating_market_cap = row.get("circulating_market_cap") or 0.0

        signals: list[dict[str, Any]] = []
        technical_evidence: list[str] = []
        sentiment_evidence: list[str] = []
        composite_evidence: list[str] = []
        notes: list[str] = []

        # ---- 筛选器命中 ----
        screener_hits = context.get("screener_hits", {})
        hit_count = 0
        hit_names: list[str] = []
        for sname, stock_list in screener_hits.items():
            for item in stock_list:
                if str(item.get("code", "")) == str(code):
                    hit_count += 1
                    display_name = sname
                    # 尝试从筛选器名提取可读名称
                    if "screener_" in sname:
                        display_name = sname.replace("screener_", "").replace("_result", "").replace("_run", "")
                    hit_names.append(display_name)
                    break

        if hit_count > 0:
            signals.append({
                "source": "screeners",
                "name": "internal_formula_hits",
                "value": float(hit_count),
                "direction": "positive",
                "confidence_hint": None,
                "evidence": [f"命中筛选器：{'、'.join(hit_names)}"],
            })
            for hn in hit_names:
                signals.append({
                    "source": "screener",
                    "name": hn,
                    "value": 1.0,
                    "direction": "positive",
                    "confidence_hint": None,
                    "evidence": [f"命中：{hn}"],
                })
            technical_evidence.append(f"筛选器命中数：{hit_count}")
            technical_evidence.append(f"命中筛选器：{'、'.join(hit_names)}")

        # ---- 涨跌幅信号 ----
        signals.append({
            "source": "market",
            "name": "pct_change",
            "value": round(pct_change, 4),
            "direction": "positive" if pct_change > 0 else ("negative" if pct_change < 0 else "neutral"),
            "confidence_hint": None,
            "evidence": [f"pct_change={pct_change:.4f}（单位：%）"],
        })
        technical_evidence.append(f"当日涨跌幅：{pct_change:.2f}%")

        # ---- 成交额信号 ----
        signals.append({
            "source": "market",
            "name": "amount",
            "value": float(amount),
            "direction": "positive" if amount > 0 else "neutral",
            "confidence_hint": None,
            "evidence": [f"amount={amount}（单位：元）"],
        })

        # ---- 板块聚焦信号 ----
        sector_rank_map = context.get("sector_rank", {})
        sector_rank = sector_rank_map.get(sector_lv1, 0)
        if sector_rank > 0:
            signals.append({
                "source": "sector",
                "name": "sector_lv1_top5_by_amount",
                "value": 1.0,
                "direction": "positive",
                "confidence_hint": None,
                "evidence": [f"sector_lv1={sector_lv1} rank={sector_rank}/5"],
            })

        # ---- 实验室命中 ----
        lab_hits = context.get("lab_hits", {})
        lab_hit_count = 0
        lab_hit_names: list[str] = []
        for lname, stock_list in lab_hits.items():
            for item in stock_list:
                if str(item.get("code", "")) == str(code):
                    lab_hit_count += 1
                    ln = item.get("lab_name", lname)
                    lab_hit_names.append(ln)
                    signals.append({
                        "source": "lab",
                        "name": ln,
                        "value": 1.0,
                        "direction": "positive",
                        "confidence_hint": None,
                        "evidence": [f"实验室命中：{ln}"],
                    })
                    break

        if lab_hit_count > 0:
            signals.append({
                "source": "labs",
                "name": "lab_hits",
                "value": float(lab_hit_count),
                "direction": "positive",
                "confidence_hint": None,
                "evidence": [f"命中实验室：{'、'.join(lab_hit_names)}"],
            })

        # ---- 涨停原因信号（占位，当前无外部数据源） ----
        signals.append({
            "source": "limit_up_reasons",
            "name": "limit_up_reason_hits",
            "value": 0.0,
            "direction": "positive",
            "confidence_hint": None,
            "evidence": ["涨停原因：无记录（或当日未涨停）。"],
        })

        # ---- 公告信号（占位） ----
        signals.append({
            "source": "announcements",
            "name": "announcement_hits",
            "value": 0.0,
            "direction": "neutral",
            "confidence_hint": None,
            "evidence": [],
        })

        # ---- 估值因子信号 ----
        # PE: 市盈率，越低越好（负值表示亏损，不参与评分）
        if pe_ratio and pe_ratio > 0:
            pe_direction = "positive" if pe_ratio < 30 else ("neutral" if pe_ratio < 60 else "negative")
            signals.append({
                "source": "fundamental",
                "name": "pe_ratio",
                "value": round(pe_ratio, 2),
                "direction": pe_direction,
                "confidence_hint": None,
                "evidence": [f"PE={pe_ratio:.1f}（{'低估' if pe_ratio < 30 else '合理' if pe_ratio < 60 else '高估'}）"],
            })
            composite_evidence.append(f"市盈率：{pe_ratio:.1f}")

        # PB: 市净率，越低越好
        if pb_ratio and pb_ratio > 0:
            pb_direction = "positive" if pb_ratio < 2 else ("neutral" if pb_ratio < 5 else "negative")
            signals.append({
                "source": "fundamental",
                "name": "pb_ratio",
                "value": round(pb_ratio, 2),
                "direction": pb_direction,
                "confidence_hint": None,
                "evidence": [f"PB={pb_ratio:.2f}（{'破净/低估' if pb_ratio < 1 else '合理' if pb_ratio < 3 else '高估'}）"],
            })
            composite_evidence.append(f"市净率：{pb_ratio:.2f}")

        # ROE: 净资产收益率（数据覆盖率低，仅在有数据时使用）
        if roe and roe > 0:
            roe_direction = "positive" if roe > 15 else ("neutral" if roe > 8 else "negative")
            signals.append({
                "source": "fundamental",
                "name": "roe",
                "value": round(roe, 2),
                "direction": roe_direction,
                "confidence_hint": None,
                "evidence": [f"ROE={roe:.1f}%（{'优秀' if roe > 15 else '一般' if roe > 8 else '较差'}）"],
            })
            composite_evidence.append(f"ROE：{roe:.1f}%")

        # 市值信号
        if total_market_cap and total_market_cap > 0:
            cap_yi = total_market_cap / 1e8  # 转换为亿元
            cap_label = "大盘" if cap_yi > 500 else ("中盘" if cap_yi > 100 else "小盘")
            signals.append({
                "source": "fundamental",
                "name": "market_cap",
                "value": round(cap_yi, 2),
                "direction": "neutral",
                "confidence_hint": None,
                "evidence": [f"总市值：{cap_yi:.0f}亿（{cap_label}）"],
            })

        # ============================================================
        # 评分计算
        # ============================================================

        # ---- technical_score ----
        # 基础技术分 = 50 + 8*hit_count + 3*clamp(pct_change, -10, 10) + lab_tech_bonus
        pct_clamped = _clamp(pct_change, -10.0, 10.0)
        lab_tech_bonus = min(lab_hit_count * 5, 15)
        base_technical = 50.0 + 8.0 * hit_count + 3.0 * pct_clamped + lab_tech_bonus

        # 共振技术分加成
        resonance_technical_bonus = 0.0
        resonance_score = 0.0
        scorer = context.get("resonance_scorer")
        stock_sector_rps = context.get("stock_sector_rps", {})
        rps_info = stock_sector_rps.get(code, {})
        rps_120 = rps_info.get("rps_120", 50.0)
        rps_250 = rps_info.get("rps_250", 50.0)

        if scorer is not None:
            try:
                # 价格趋势 proxy：用 pct_change 归一化到 0-1
                price_trend = _clamp((pct_change + 10) / 20, 0.0, 1.0)
                # 成交量趋势 proxy：用 turnover 归一化
                volume_trend = _clamp(turnover / 20.0, 0.0, 1.0) if turnover else 0.5
                # 均线排列和突破信号暂用默认值
                ma_alignment = pct_change > 0 and amount > 0
                breakout_signal = abs(pct_change) >= 9.5

                res_score = scorer.calculate_technical_score(
                    rps_120=rps_120,
                    rps_250=rps_250,
                    price_trend=price_trend,
                    volume_trend=volume_trend,
                    ma_alignment=ma_alignment,
                    breakout_signal=breakout_signal,
                )
                resonance_score = res_score
                # 共振加成 = (res_score - 50) * 0.2，范围约 [-10, +10]
                resonance_technical_bonus = (res_score - 50.0) * 0.2
            except Exception as exc:
                logger.debug("共振技术评分失败 %s: %s", code, exc)

        technical_score = _clamp(base_technical + resonance_technical_bonus, 0.0, 100.0)

        # ---- sentiment_score ----
        # amount_score: 基于成交额排名
        universe_size = context.get("universe_size", 300)
        amount_rank = row.get("_amount_rank", 0)
        if amount_rank == 0:
            # 用 amount 在 universe 中的相对位置估算
            amount_score = 50.0
        else:
            amount_score = max(0, 100.0 - (amount_rank / universe_size) * 100.0)

        # rank_bonus: 板块排名加成
        rank_bonus = (6 - sector_rank) * 5 if sector_rank > 0 else 0.0

        # lab_sentiment_bonus
        lab_sentiment_bonus = min(lab_hit_count * 5, 20.0)

        # tier_bonus: 个股分层加成
        tier_map = context.get("stock_tier_map", {})
        tier_info = tier_map.get(code, {})
        stock_tier = tier_info.get("tier", "follower")
        tier_bonus_map = {"leader": 10.0, "core": 5.0, "follower": 0.0}
        tier_bonus = tier_bonus_map.get(stock_tier, 0.0)

        # sector_rps_bonus
        sector_rps_bonus = 0.0
        if sector_rank > 0:
            sector_rps_bonus = (6 - sector_rank) * 3

        sentiment_score = _clamp(
            amount_score + rank_bonus + lab_sentiment_bonus + tier_bonus + sector_rps_bonus,
            0.0,
            100.0,
        )

        # ---- composite_score (估值基本面) ----
        # 基于 PE/PB 估值因子计算综合面得分
        composite_score = 0.0
        composite_evidence_items: list[str] = []

        if pe_ratio and pe_ratio > 0:
            # PE 越低越好：<15 得满分，15-30 得 70%，30-60 得 40%，>60 得 10%
            if pe_ratio < 15:
                pe_score = 100.0
            elif pe_ratio < 30:
                pe_score = 70.0
            elif pe_ratio < 60:
                pe_score = 40.0
            else:
                pe_score = 10.0
            composite_score += pe_score * 0.5  # PE 权重 50%
            composite_evidence_items.append(f"PE={pe_ratio:.1f} → 估值分{pe_score:.0f}")

        if pb_ratio and pb_ratio > 0:
            # PB 越低越好：<1 得满分，1-2 得 80%，2-5 得 50%，>5 得 20%
            if pb_ratio < 1:
                pb_score = 100.0
            elif pb_ratio < 2:
                pb_score = 80.0
            elif pb_ratio < 5:
                pb_score = 50.0
            else:
                pb_score = 20.0
            composite_score += pb_score * 0.3  # PB 权重 30%
            composite_evidence_items.append(f"PB={pb_ratio:.2f} → 估值分{pb_score:.0f}")

        if roe and roe > 0:
            # ROE 越高越好：>15 得满分，8-15 得 60%，<8 得 20%
            if roe > 15:
                roe_score = 100.0
            elif roe > 8:
                roe_score = 60.0
            else:
                roe_score = 20.0
            composite_score += roe_score * 0.2  # ROE 权重 20%
            composite_evidence_items.append(f"ROE={roe:.1f}% → 质量分{roe_score:.0f}")

        # 如果有估值数据，归一化到 0-100
        has_fundamental = (pe_ratio and pe_ratio > 0) or (pb_ratio and pb_ratio > 0)
        if has_fundamental:
            composite_score = _clamp(composite_score, 0.0, 100.0)
            if composite_evidence_items:
                composite_evidence.append("估值评估：" + "；".join(composite_evidence_items))

        # ---- overall（动态权重） ----
        # 根据市场阶段动态调整权重
        mp_result = context.get("market_phase")
        phase_code = _market_phase_code(mp_result) if mp_result else "range"

        # 动态权重表
        _DYNAMIC_WEIGHTS: dict[str, tuple[float, float, float]] = {
            "bull": (0.60, 0.30, 0.10),       # 牛市重技术
            "transition": (0.50, 0.40, 0.10),  # 过渡期均衡偏技术
            "range": (0.45, 0.45, 0.10),       # 震荡市均衡
            "bear": (0.35, 0.55, 0.10),        # 熊市重资金情绪
        }
        w_tech, w_sent, w_comp = _DYNAMIC_WEIGHTS.get(phase_code, (0.45, 0.45, 0.10))

        # 如果 composite 无数据，将权重重新分配给 tech 和 sent
        if not has_fundamental:
            total_active = w_tech + w_sent
            w_tech = w_tech / total_active
            w_sent = w_sent / total_active
            w_comp = 0.0

        overall = w_tech * technical_score + w_sent * sentiment_score + w_comp * composite_score

        # ---- evidence 汇总 ----
        sentiment_evidence.append(f"当日成交额：{amount:,.0f} 元")
        if sector_rank > 0:
            sentiment_evidence.append(f"板块聚焦：{sector_lv1}（Top5 by 成交额）")
        sentiment_evidence.append("涨停原因：无记录（或当日未涨停）。")
        if lab_hit_names:
            for ln in lab_hit_names:
                sentiment_evidence.append(f"实验室信号：{ln}（在池）")
        if amount_rank > 0:
            sentiment_evidence.append(f"成交额排名：{amount_rank}/{universe_size}")

        composite_evidence.append("公告：无记录（或未在当日发布）。")
        composite_evidence.append(
            "综合面（行业/财报/新闻/政策/国际政治）尚未接入腾讯等外部数据源，"
            "当前仅能基于本地公告表做弱提示，暂不计分。"
        )

        if lab_hit_names:
            notes.append(
                f"实验室信号：{lab_hit_names[0]}（输入快照已生成，策略待迁移）"
            )
        notes.append(
            "v2 动态权重：按市场阶段调整 tech/sent/comp 比例（牛市重技术，熊市重资金情绪）"
        )
        notes.append(
            "composite 面纳入 PE/PB/ROE 估值因子（PE 50% + PB 30% + ROE 20%）"
        )

        # ---- factor_summary (新增字段) ----
        resonance_grade = "N/A"
        if resonance_score >= 80:
            resonance_grade = "A"
        elif resonance_score >= 60:
            resonance_grade = "B"
        elif resonance_score >= 40:
            resonance_grade = "C"
        else:
            resonance_grade = "D"

        mp_result = context.get("market_phase")
        mp_display = _market_phase_display(mp_result) if mp_result else "未知"

        factor_summary = {
            "resonance_score": round(resonance_score, 2),
            "resonance_grade": resonance_grade,
            "stock_tier": stock_tier,
            "tier_leadership_score": tier_info.get("leadership_score", 0.0),
            "sector_rps_120": round(rps_120, 2),
            "market_phase": mp_display,
            "dynamic_weights": {
                "phase": phase_code,
                "technical": round(w_tech, 2),
                "sentiment": round(w_sent, 2),
                "composite": round(w_comp, 2),
            },
            "valuation": {
                "pe_ratio": round(pe_ratio, 2) if pe_ratio else None,
                "pb_ratio": round(pb_ratio, 2) if pb_ratio else None,
                "roe": round(roe, 2) if roe else None,
                "composite_score": round(composite_score, 2) if has_fundamental else None,
            },
        }

        if context.get("debug") is True:
            for signal in signals:
                if isinstance(signal, dict):
                    signal.setdefault("raw_refs", {})

        return {
            "stock_code": code,
            "stock_name": name,
            "sector_lv1": sector_lv1,
            "sector_lv2": sector_lv2,
            "certainty": round(overall, 2),
            "subscores": {
                "technical": round(technical_score, 2),
                "sentiment": round(sentiment_score, 2),
                "composite": round(composite_score, 2),
                "overall": round(overall, 2),
            },
            "evidence": {
                "technical_evidence": technical_evidence,
                "sentiment_evidence": sentiment_evidence,
                "composite_evidence": composite_evidence,
                "notes": notes,
            },
            "signals": signals,
            "factor_summary": factor_summary,
        }

    # ------------------------------------------------------------------
    # 组装最终 payload
    # ------------------------------------------------------------------
    def _assemble_payload(
        self,
        target_date: str,
        universe_limit: int,
        mp_result: MarketPhaseResult,
        sr_result: SectorRotationResult,
        screener_data: dict[str, list[dict[str, Any]]],
        lab_data: dict[str, list[dict[str, Any]]],
        ge_80: list[dict[str, Any]],
        ge_70: list[dict[str, Any]],
        ge_60: list[dict[str, Any]],
        candidates: list[dict[str, Any]],
        debug: bool,
    ) -> dict[str, Any]:
        """组装与已有 artifact 格式完全兼容的 payload。"""

        # ---- market_context ----
        mp_code = _market_phase_code(mp_result)
        mp_display = _market_phase_display(mp_result)

        # 聚焦主题：取 top_sectors 的前5板块名
        focus_themes = [sr.sector_name for sr in sr_result.top_sectors[:5]]
        focus_themes_source = "top5_sectors_by_amount_proxy"

        # 板块成交额 evidence
        evidence_items: list[dict[str, Any]] = []
        for sr in sr_result.top_sectors[:5]:
            evidence_items.append({
                "sector_lv1": sr.sector_name,
                "rps_120": round(sr.rps_120, 2),
                "is_mainline": sr.is_mainline,
            })

        market_context: dict[str, Any] = {
            "market_phase": {
                "code": mp_code,
                "display": mp_display,
                "confidence": round(mp_result.confidence, 4),
            },
            "focus_themes": focus_themes,
            "focus_themes_source": focus_themes_source,
            "evidence": evidence_items,
            "notes": [
                "聚焦主题由板块成交额 proxy 的 Top5 驱动。"
            ],
        }

        # ---- model_state ----
        # 实验室集成信息
        lab_integrations: list[dict[str, Any]] = []
        for lname, stock_list in lab_data.items():
            lab_info = {
                "lab_id": lname,
                "lab_name": lname.replace("lab_", "").replace("_result", ""),
                "status": "ok",
                "target_date": target_date,
                "extracted_stock_count": len(stock_list),
            }
            if self.project_root:
                lab_info["artifact_path"] = (
                    f"var/artifacts/lab_runs/{target_date}/{lname}.json"
                )
            lab_integrations.append(lab_info)

        model_state: dict[str, Any] = {
            "version": 2,
            "updated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "learning_modes": ["historical_backtest", "live_tracking"],
            "feedback_policy": [
                "primary: certainty score outcomes + user feedback",
                "secondary: realized return over 20-50 trading days",
            ],
            "integrations": {
                "labs": lab_integrations,
                "composite_sources": [
                    {"source": "announcements", "status": "weak_hint_only"},
                    {"source": "tencent_external", "status": "pending_integration"},
                ],
                "strategies": [
                    {"strategy_id": "triple_screen", "display_name": "三重滤网", "status": "pending_implementation"},
                    {"strategy_id": "neil_turtle", "display_name": "海龟", "status": "pending_implementation"},
                ],
            },
        }

        if debug:
            model_state["_debug_screener_hits"] = {
                k: len(v) for k, v in screener_data.items()
            }
            model_state["_debug_lab_hits"] = {
                k: len(v) for k, v in lab_data.items()
            }

        payload: dict[str, Any] = {
            "_meta": {
                "status": "ok",
                "source": "live",
                "debug": debug,
            },
            "target_date": target_date,
            "universe": {
                "selection": "top_by_amount",
                "limit": universe_limit,
                "filters": [
                    "exclude is_delisted=1",
                    "exclude index prefixes (399xxx)",
                    "exclude BSE prefixes (43/83/87/88)",
                    "exclude ST/PT by name keyword if available",
                ],
            },
            "market_context": market_context,
            "tiers": {
                "ge_80": ge_80,
                "ge_70": ge_70,
                "ge_60": ge_60,
            },
            "candidates_summary": {
                "candidate_count": len(candidates),
                "ge_80_count": len(ge_80),
                "ge_70_count": len(ge_70),
                "ge_60_count": len(ge_60),
                "dedupe_policy": "deduped by certainty tier bands",
            },
            "model_state": model_state,
        }
        return payload

    # ------------------------------------------------------------------
    # 空 payload
    # ------------------------------------------------------------------
    @staticmethod
    def _empty_payload(target_date: str, debug: bool) -> dict[str, Any]:
        """当 universe 为空时返回的空 payload。"""
        return {
            "_meta": {"status": "empty", "source": "live", "debug": debug},
            "target_date": target_date,
            "universe": {"selection": "top_by_amount", "limit": 0, "filters": []},
            "market_context": {
                "market_phase": {"code": "unknown", "display": "未知（无数据）", "confidence": 0.0},
                "focus_themes": [],
                "focus_themes_source": "none",
                "evidence": [],
                "notes": ["universe 为空，可能是非交易日或数据库无数据。"],
            },
            "tiers": {"ge_80": [], "ge_70": [], "ge_60": []},
            "candidates_summary": {
                "candidate_count": 0,
                "ge_80_count": 0,
                "ge_70_count": 0,
                "ge_60_count": 0,
                "dedupe_policy": "deduped by certainty tier bands",
            },
            "model_state": {
                "version": 2,
                "updated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
        }

    # ------------------------------------------------------------------
    # 静态方法：save / load
    # ------------------------------------------------------------------
    @staticmethod
    def save(
        payload: dict[str, Any],
        project_root: str | Path,
        target_date: str,
    ) -> Path:
        """将 payload 写入 ledger 和 artifact。

        Parameters
        ----------
        payload : dict
            build() 返回的完整 payload。
        project_root : str | Path
            项目根目录。
        target_date : str
            目标日期 YYYY-MM-DD。

        Returns
        -------
        Path
            artifact 文件路径。
        """
        root = Path(project_root)

        # Ledger
        ledger_dir = root / "var" / "ledgers" / "factor_matrix" / target_date
        ledger_dir.mkdir(parents=True, exist_ok=True)
        ledger_path = ledger_dir / "factor_matrix_run.json"

        ledger = {
            "status": payload.get("_meta", {}).get("status", "unknown"),
            "target_date": target_date,
            "version": payload.get("model_state", {}).get("version", 2),
            "artifact_path": f"var/artifacts/factor_matrix/{target_date}/factor_matrix_daily.json",
            "inputs": {
                "stock_db_path": "var/db/stock_data.db",
            },
            "requested_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "requested_by": "factor_matrix_builder",
        }
        ledger_path.write_text(
            json.dumps(ledger, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        # Artifact
        artifact_dir = root / "var" / "artifacts" / "factor_matrix" / target_date
        artifact_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = artifact_dir / "factor_matrix_daily.json"

        artifact_payload = dict(payload)
        artifact_payload["_meta"]["source"] = "stored"
        artifact_path.write_text(
            json.dumps(artifact_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        logger.info(
            "因子矩阵已保存: ledger=%s, artifact=%s",
            ledger_path,
            artifact_path,
        )
        return artifact_path

    @staticmethod
    def load(
        project_root: str | Path,
        target_date: str,
    ) -> dict[str, Any] | None:
        """从 artifact 目录加载已保存的因子矩阵。

        Parameters
        ----------
        project_root : str | Path
            项目根目录。
        target_date : str
            目标日期 YYYY-MM-DD。

        Returns
        -------
        dict[str, Any] | None
            已保存的 payload，若文件不存在则返回 None。
        """
        root = Path(project_root)
        artifact_path = (
            root / "var" / "artifacts" / "factor_matrix" / target_date / "factor_matrix_daily.json"
        )
        if not artifact_path.is_file():
            return None
        try:
            data = json.loads(artifact_path.read_text(encoding="utf-8"))
            return data
        except Exception as exc:
            logger.error("加载因子矩阵失败: %s", exc)
            return None
