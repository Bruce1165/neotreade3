"""Lab runtime adapter for NeoTrade3.

Lab Design Decisions (V3):
- cup_handle_lab: 杯柄强化 - 成功归因 + 参数优化建议 + 个股分层过滤
- quant_trading_lab: 量化交易核心 - 整合三维共振评分 + 波浪识别 + 板块轮动
- five_flags_lab: 已整合到 quant_trading_lab，不再独立运行
- paper_simulation_lab: 忽略，不实现
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any

from neotrade3.analysis.resonance_scorer import ResonanceScorer
from neotrade3.analysis.stock_tiering import StockTieringAnalyzer, StockTier


class LabRuntimeAdapter:
    """Runtime adapter for lab jobs in NeoTrade3."""

    @staticmethod
    def run_job(
        task_id: str,
        target_date: str | date | None = None,
        lab_id: str | None = None,
        project_root: Path | str | None = None,
        **kwargs: object,
    ) -> dict[str, Any]:
        """Run a lab job and return results."""
        inferred_lab = lab_id is None
        if lab_id is None:
            lab_id = task_id.split(".", 1)[0].strip() if task_id else ""
        if target_date is None and inferred_lab:
            return {
                "task_id": task_id,
                "lab_id": lab_id,
                "status": "pending_implementation",
                "message": "LabRuntimeAdapter.run_job(task_id) is a compatibility entrypoint; pass target_date and lab_id for real execution.",
                "target_date": date.today().isoformat(),
            }
        if target_date is None:
            target_date_str = date.today().isoformat()
        elif isinstance(target_date, date):
            target_date_str = target_date.isoformat()
        else:
            target_date_str = str(target_date)

        if project_root is None:
            project_root = Path(__file__).resolve().parents[2]
        elif isinstance(project_root, str):
            project_root = Path(project_root)

        if lab_id == "cup_handle_lab":
            return LabRuntimeAdapter._run_cup_handle_lab(
                task_id=task_id,
                target_date=target_date_str,
                project_root=project_root,
                **kwargs,
            )
        elif lab_id == "quant_trading_lab":
            return LabRuntimeAdapter._run_quant_trading_lab(
                task_id=task_id,
                target_date=target_date_str,
                project_root=project_root,
                **kwargs,
            )
        elif lab_id == "five_flags_lab":
            return {
                "task_id": task_id,
                "lab_id": lab_id,
                "status": "skipped",
                "message": "五图筛选已整合到 quant_trading_lab，不再独立运行",
                "target_date": target_date_str,
            }
        elif lab_id == "paper_simulation_lab":
            return LabRuntimeAdapter._run_paper_simulation_lab(
                task_id=task_id,
                target_date=target_date_str,
                project_root=project_root,
                **kwargs,
            )
        else:
            return {
                "task_id": task_id,
                "lab_id": lab_id,
                "status": "pending_implementation",
                "message": f"Unknown lab: {lab_id}",
                "target_date": target_date_str,
            }

    @staticmethod
    def _run_cup_handle_lab(
        task_id: str,
        target_date: str,
        project_root: Path,
        include_followers: bool = False,
        min_resonance_score: float = 60.0,
        **kwargs: object,
    ) -> dict[str, Any]:
        """Run cup handle lab - 杯柄强化分析（V2 集成个股分层和共振评分）.

        Args:
            task_id: Task identifier
            target_date: Analysis date (YYYY-MM-DD)
            project_root: Project root path
            include_followers: Whether to include follower-tier stocks
            min_resonance_score: Minimum resonance score to include
            **kwargs: Additional arguments
        """
        screener_artifact_path = (
            project_root
            / f"var/artifacts/screener_runs/{target_date}/screener_cup_handle_v4_result.json"
        )

        # Step 1: Load cup handle candidates
        raw_candidates: list[dict[str, Any]] = []
        if screener_artifact_path.exists():
            try:
                payload = json.loads(screener_artifact_path.read_text(encoding="utf-8"))
                picks = payload.get("picks", [])
                if isinstance(picks, list):
                    for pick in picks:
                        if isinstance(pick, str):
                            raw_candidates.append({"stock_code": pick})
                        elif isinstance(pick, dict):
                            raw_candidates.append({
                                "stock_code": pick.get("code", ""),
                                "stock_name": pick.get("name", ""),
                                "cup_rim_price": pick.get("cup_rim_price"),
                                "cup_bottom_price": pick.get("cup_bottom_price"),
                                "entry_price": pick.get("close"),
                            })
            except (OSError, json.JSONDecodeError):
                pass

        if not raw_candidates:
            return {
                "task_id": task_id,
                "lab_id": "cup_handle_lab",
                "status": "ok",
                "message": "杯柄实验室完成，无候选股票",
                "target_date": target_date,
                "candidates_count": 0,
                "candidates": [],
                "analysis_version": "v2_enhanced",
                "filter_applied": {
                    "include_followers": include_followers,
                    "min_resonance_score": min_resonance_score,
                },
            }

        # Step 2: Enrich from DB
        raw_candidates = LabRuntimeAdapter._enrich_from_db(
            raw_candidates, target_date, project_root
        )

        codes = [c.get("stock_code", "") for c in raw_candidates if c.get("stock_code")]

        # Step 3: Apply stock tiering
        db_path = project_root / "var" / "db" / "stock_data.db"
        tiering_result = None
        tier_map: dict[str, str] = {}
        if db_path.exists() and codes:
            try:
                target_date_obj = datetime.strptime(target_date, "%Y-%m-%d").date()
                tiering_analyzer = StockTieringAnalyzer(db_path=str(db_path))
                tiering_result = tiering_analyzer.analyze(
                    codes=codes,
                    target_date=target_date_obj,
                    lookback_days=20,
                )
                for stock in tiering_result.all_tiered_stocks:
                    tier_map[stock.code] = stock.tier.value
            except Exception:
                pass  # Tiering is best-effort

        # Step 4: Apply resonance scoring
        resonance_results: dict[str, dict[str, Any]] = {}
        if db_path.exists() and codes:
            try:
                target_date_obj = datetime.strptime(target_date, "%Y-%m-%d").date()
                scorer = ResonanceScorer(db_path=str(db_path))
                scores = scorer.score_stocks(codes=codes, target_date=target_date_obj)
                for r in scores:
                    resonance_results[r.code] = {
                        "total_score": r.total_score,
                        "grade": r.grade,
                        "technical": r.sub_scores.technical,
                        "capital": r.sub_scores.capital,
                        "policy": r.sub_scores.policy,
                    }
            except Exception:
                pass  # Resonance scoring is best-effort

        # Step 5: Filter and enrich candidates
        filtered_candidates: list[dict[str, Any]] = []
        for cand in raw_candidates:
            code = cand.get("stock_code", "")
            tier = tier_map.get(code, "unknown")
            resonance = resonance_results.get(code, {})
            total_score = resonance.get("total_score", 0)

            # Apply tier filter
            if tier == StockTier.FOLLOWER.value and not include_followers:
                continue

            # Apply resonance score filter
            if total_score > 0 and total_score < min_resonance_score:
                continue

            # Enrich candidate
            enriched = {
                **cand,
                "tier": tier,
                "tier_display": {
                    "leader": "龙头",
                    "core": "中军",
                    "follower": "跟随",
                    "unknown": "未知",
                }.get(tier, tier),
                "resonance_score": total_score,
                "resonance_grade": resonance.get("grade", ""),
                "sub_scores": {
                    "technical": resonance.get("technical", 0),
                    "capital": resonance.get("capital", 0),
                    "policy": resonance.get("policy", 0),
                } if resonance else {},
            }
            filtered_candidates.append(enriched)

        # Step 6: Sort by resonance score (descending), then by tier priority
        tier_priority = {"leader": 0, "core": 1, "follower": 2, "unknown": 3}
        filtered_candidates.sort(
            key=lambda x: (-x.get("resonance_score", 0), tier_priority.get(x.get("tier", "unknown"), 3))
        )

        # Calculate statistics
        tier_counts = {"leader": 0, "core": 0, "follower": 0, "unknown": 0}
        for c in filtered_candidates:
            tier_counts[c.get("tier", "unknown")] = tier_counts.get(c.get("tier", "unknown"), 0) + 1

        return {
            "task_id": task_id,
            "lab_id": "cup_handle_lab",
            "status": "ok",
            "message": f"杯柄实验室完成，共 {len(filtered_candidates)} 只精选候选（原始 {len(raw_candidates)} 只）",
            "target_date": target_date,
            "candidates_count": len(filtered_candidates),
            "raw_candidates_count": len(raw_candidates),
            "candidates": filtered_candidates[:20],
            "tier_distribution": tier_counts,
            "analysis_version": "v2_enhanced",
            "filter_applied": {
                "include_followers": include_followers,
                "min_resonance_score": min_resonance_score,
            },
            "notes": [
                "V2 版本：集成个股分层 + 三维共振评分",
                "过滤：默认排除跟随股，可配置包含",
                "排序：按共振总分降序，同分按分层优先级",
                "后续版本将添加：成功归因分析、参数优化建议",
            ],
        }

    @staticmethod
    def _run_quant_trading_lab(
        task_id: str,
        target_date: str,
        project_root: Path,
        **kwargs: object,
    ) -> dict[str, Any]:
        """Run quant trading lab - 量化交易核心分析（V2 增强版）.

        V2 增强：集成 SignalGenerator 生成 A/B/C 等级交易信号
        """
        from neotrade3.analysis.signal_generator import SignalGenerator, SignalGrade
        from neotrade3.analysis.factor_matrix import FactorMatrixBuilder

        db_path = project_root / "var/db/stock_data.db"

        # Step 1: 获取高确定性候选（从因子矩阵或实时生成）
        factor_matrix_path = (
            project_root
            / f"var/artifacts/factor_matrix/{target_date}/factor_matrix_daily.json"
        )

        high_certainty_candidates: list[dict[str, Any]] = []
        market_context: dict[str, Any] = {}

        if factor_matrix_path.exists():
            try:
                payload = json.loads(factor_matrix_path.read_text(encoding="utf-8"))
                market_context = payload.get("market_context", {})
                tiers = payload.get("tiers", {})
                for tier_name in ["ge_80", "ge_70", "ge_60"]:
                    for c in tiers.get(tier_name, []):
                        if isinstance(c, dict):
                            high_certainty_candidates.append({
                                "stock_code": c.get("stock_code", ""),
                                "stock_name": c.get("stock_name", ""),
                                "certainty": c.get("certainty", 0),
                                "tier": tier_name,
                                "subscores": c.get("subscores", {}),
                                "factor_summary": c.get("factor_summary", {}),
                            })
            except (OSError, json.JSONDecodeError):
                pass

        # 如果没有缓存，实时生成因子矩阵
        if not high_certainty_candidates and db_path.exists():
            try:
                builder = FactorMatrixBuilder(
                    db_path=str(db_path),
                    project_root=project_root,
                )
                payload = builder.build(target_date=target_date, universe_limit=300)
                market_context = payload.get("market_context", {})
                for tier_name in ["ge_80", "ge_70", "ge_60"]:
                    for c in payload.get("tiers", {}).get(tier_name, []):
                        high_certainty_candidates.append({
                            "stock_code": c["stock_code"],
                            "stock_name": c["stock_name"],
                            "certainty": c["certainty"],
                            "tier": tier_name,
                            "subscores": c["subscores"],
                            "factor_summary": c.get("factor_summary", {}),
                        })
            except Exception:
                pass

        # Step 2: 使用 SignalGenerator 生成交易信号
        trading_signals: list[dict[str, Any]] = []
        wave_signals: list[dict[str, Any]] = []

        if db_path.exists() and high_certainty_candidates:
            try:
                # 取前 50 只最高确定性候选进行深度分析
                top_candidates = sorted(
                    high_certainty_candidates,
                    key=lambda x: x.get("certainty", 0),
                    reverse=True,
                )[:50]

                codes = [c["stock_code"] for c in top_candidates if c.get("stock_code")]

                if codes:
                    generator = SignalGenerator(db_path=str(db_path))
                    # Convert target_date string to date object
                    from datetime import date as dt_date
                    if isinstance(target_date, str):
                        target_date_obj = dt_date.fromisoformat(target_date)
                    else:
                        target_date_obj = target_date
                    result = generator.generate(
                        codes=codes,
                        target_date=target_date_obj,
                        min_grade=SignalGrade.C,  # 包含 C 级信号
                    )

                    market_context["signal_market_phase"] = result.market_phase
                    market_context["debug_total_analyzed"] = result.total_analyzed
                    market_context["debug_raw_signals_count"] = len(result.signals)

                    # 转换信号为可序列化格式
                    for sig in result.signals:
                        trading_signals.append({
                            "code": sig.code,
                            "name": sig.name,
                            "direction": sig.direction.value if hasattr(sig.direction, "value") else str(sig.direction),
                            "grade": sig.grade.value if hasattr(sig.grade, "value") else str(sig.grade),
                            "composite_score": sig.composite_score,
                            "dimension_scores": [
                                {
                                    "source": d.source.value if hasattr(d.source, "value") else str(d.source),
                                    "score": d.score,
                                    "is_bullish": d.is_bullish,
                                    "weight": d.weight,
                                    "detail": d.detail,
                                }
                                for d in (sig.dimension_scores or [])
                            ],
                            "entry_price": sig.entry_price,
                            "stop_loss": sig.stop_loss,
                            "take_profit": sig.take_profit_1 if hasattr(sig, "take_profit_1") else None,
                            "expected_return": {
                                "min": sig.expected_return.conservative_pct if sig.expected_return else None,
                                "max": sig.expected_return.optimistic_pct if sig.expected_return else None,
                                "confidence": sig.expected_return.confidence_pct if sig.expected_return else None,
                            } if sig.expected_return else {},
                            "time_horizon_days": sig.expected_return.holding_days_max if sig.expected_return and hasattr(sig.expected_return, "holding_days_max") else 20,
                            "evidence": [],
                        })

                    # 提取波浪信号 (从 dimension_scores 中找 ELLIOTT_WAVE 维度)
                    for sig in result.signals:
                        wave_dim = None
                        for d in (sig.dimension_scores or []):
                            if hasattr(d, "source") and "elliott" in str(d.source).lower():
                                wave_dim = d
                                break
                        if wave_dim:
                            wave_signals.append({
                                "code": sig.code,
                                "name": sig.name,
                                "wave_detail": wave_dim.detail if hasattr(wave_dim, "detail") else str(wave_dim),
                            })

            except Exception as e:
                # 信号生成失败不影响返回候选列表
                import traceback
                market_context["signal_generation_error"] = str(e)
                market_context["signal_generation_traceback"] = traceback.format_exc()

        # Step 3: 按等级统计
        grade_counts = {"A": 0, "B": 0, "C": 0}
        for sig in trading_signals:
            grade = sig.get("grade", "")
            if grade in grade_counts:
                grade_counts[grade] += 1

        # Step 4: 组装返回结果
        top_signals = sorted(
            trading_signals,
            key=lambda x: (x.get("composite_score", 0), {"A": 3, "B": 2, "C": 1}.get(x.get("grade", "C"), 0)),
            reverse=True,
        )[:20]

        return {
            "task_id": task_id,
            "lab_id": "quant_trading_lab",
            "status": "ok",
            "message": f"量化交易实验室 V2 完成，共 {len(high_certainty_candidates)} 只候选，生成 {len(trading_signals)} 个交易信号（A:{grade_counts['A']} B:{grade_counts['B']} C:{grade_counts['C']}）",
            "target_date": target_date,
            "market_context": market_context,
            "high_certainty_count": len(high_certainty_candidates),
            "candidates": high_certainty_candidates[:20],
            "trading_signals": top_signals,
            "wave_signals": wave_signals[:10],
            "grade_distribution": grade_counts,
            "analysis_version": "v2_enhanced",
            "notes": [
                "V2 增强版：集成 SignalGenerator 生成 A/B/C 等级交易信号",
                "包含：三维共振评分 + 艾略特波浪识别 + 板块轮动 + 个股分层",
                "信号包含：入场价、止损、止盈、预期收益、时间窗口",
            ],
        }

    @staticmethod
    def _run_paper_simulation_lab(
        task_id: str,
        target_date: str,
        project_root: Path,
        strategy_id: str = "default",
        **kwargs: object,
    ) -> dict[str, Any]:
        """Run paper simulation lab - 模拟交易实验室.

        Args:
            task_id: Task identifier
            target_date: Simulation date (YYYY-MM-DD)
            project_root: Project root path
            strategy_id: Strategy identifier
            **kwargs: Additional arguments
        """
        from neotrade3.labs.paper_trading import (
            AnalyticsCalculator,
            PaperTradingEngine,
            PortfolioManager,
            StrategyConfig,
        )

        # Setup paths
        db_path = project_root / "var" / "data" / "paper_trading.db"
        market_data_path = project_root / "var" / "db" / "stock_data.db"

        # Load or create strategy config
        config = StrategyConfig(
            strategy_id=strategy_id,
            strategy_name="NeoTrade3 Paper Trading",
            initial_capital=1_000_000.0,
            max_positions=10,
            max_position_pct=20.0,
            stop_loss_pct=8.0,
            take_profit_pct=20.0,
            min_resonance_score=60.0,
            preferred_tiers=["leader", "core"],
            max_holding_days=50,
            signal_sources=["cup_handle_lab", "quant_trading_lab"],
        )

        # Initialize portfolio manager
        portfolio = PortfolioManager(db_path=str(db_path), strategy_config=config)

        # Initialize trading engine
        engine = PaperTradingEngine(
            portfolio_manager=portfolio,
            market_data_source=market_data_path if market_data_path.exists() else None,
        )

        # Get lab candidates and generate signals
        all_signals: list[dict[str, Any]] = []

        # Try to get cup_handle_lab candidates
        cup_handle_result = LabRuntimeAdapter._run_cup_handle_lab(
            task_id=f"{task_id}_cup_handle",
            target_date=target_date,
            project_root=project_root,
            include_followers=False,
            min_resonance_score=60.0,
        )
        if cup_handle_result.get("status") == "ok":
            candidates = cup_handle_result.get("candidates", [])
            for c in candidates:
                c["source"] = "cup_handle_lab"
            signals = engine.generate_signals_from_candidates(candidates)
            all_signals.extend(signals)

        # Try to get quant_trading_lab candidates
        quant_result = LabRuntimeAdapter._run_quant_trading_lab(
            task_id=f"{task_id}_quant",
            target_date=target_date,
            project_root=project_root,
        )
        if quant_result.get("status") == "ok":
            candidates = quant_result.get("candidates", [])
            for c in candidates:
                c["source"] = "quant_trading_lab"
                c["resonance_score"] = c.get("certainty", 0)
            signals = engine.generate_signals_from_candidates(candidates)
            all_signals.extend(signals)

        # Execute trading day
        target_date_obj = datetime.strptime(target_date, "%Y-%m-%d").date()

        # Process entry signals
        entry_trades = engine.process_signals(all_signals, target_date_obj)

        # Check exit conditions for existing positions
        exit_trades = engine.check_exit_conditions(target_date_obj)

        # Save portfolio snapshot
        snapshot = portfolio.save_snapshot(target_date_obj)

        # Calculate analytics
        analytics_calculator = AnalyticsCalculator(
            db_path=str(db_path),
            strategy_id=strategy_id,
        )
        analytics = analytics_calculator.calculate(
            analysis_date=target_date_obj,
            lookback_days=365,
        )

        # Get current positions
        open_positions = portfolio.get_open_positions()

        return {
            "task_id": task_id,
            "lab_id": "paper_simulation_lab",
            "status": "ok",
            "message": f"模拟交易完成：{len(entry_trades)} 笔买入，{len(exit_trades)} 笔卖出，当前持仓 {len(open_positions)} 只",
            "target_date": target_date,
            "strategy_id": strategy_id,
            "trades": {
                "entry_count": len(entry_trades),
                "exit_count": len(exit_trades),
                "entry_trades": [
                    {
                        "code": t.code,
                        "name": t.name,
                        "side": t.side.value,
                        "quantity": t.quantity,
                        "price": t.price,
                        "amount": t.amount,
                        "signal_source": t.signal_source,
                        "signal_reason": t.signal_reason,
                    }
                    for t in entry_trades
                ],
                "exit_trades": [
                    {
                        "code": t.code,
                        "name": t.name,
                        "side": t.side.value,
                        "quantity": t.quantity,
                        "price": t.price,
                        "amount": t.amount,
                        "signal_reason": t.signal_reason,
                    }
                    for t in exit_trades
                ],
            },
            "portfolio": {
                "cash": round(snapshot["cash"], 2),
                "total_value": round(snapshot["total_value"], 2),
                "position_count": len(open_positions),
                "total_pnl": round(snapshot["total_pnl"], 2),
                "total_return_pct": round(snapshot["total_return_pct"], 2),
            },
            "positions": [
                {
                    "code": p.code,
                    "name": p.name,
                    "entry_date": p.entry_date.isoformat(),
                    "entry_price": p.entry_price,
                    "current_price": p.current_price,
                    "quantity": p.current_quantity,
                    "unrealized_pnl": round(p.unrealized_pnl, 2),
                    "unrealized_pnl_pct": round((p.current_price - p.entry_price) / p.entry_price * 100, 2) if p.entry_price else 0,
                    "holding_days": p.holding_days,
                }
                for p in open_positions
            ],
            "analytics": analytics.to_dict(),
            "analysis_version": "v1_paper_trading",
            "notes": [
                "V1 版本：模拟交易实验室",
                "支持 cup_handle_lab 和 quant_trading_lab 信号",
                "自动止损(8%)、止盈(20%)、时间退出(50天)",
                "包含绩效分析和持仓追踪",
            ],
        }

    @staticmethod
    def _enrich_from_db(
        candidates: list[dict[str, Any]],
        target_date: str,
        project_root: Path,
    ) -> list[dict[str, Any]]:
        """Enrich candidate list with stock names and prices from database."""
        db_path = project_root / "var" / "db" / "stock_data.db"
        if not db_path.exists():
            return candidates

        codes = [c.get("stock_code", "") for c in candidates if c.get("stock_code")]
        if not codes:
            return candidates

        conn = sqlite3.connect(str(db_path))
        try:
            placeholders = ",".join("?" * len(codes))
            cursor = conn.execute(
                f"""
                SELECT s.code, s.name, dp.close
                FROM stocks s
                LEFT JOIN daily_prices dp ON s.code = dp.code AND dp.trade_date = ?
                WHERE s.code IN ({placeholders})
                """,
                [target_date] + codes,
            )
            db_lookup: dict[str, dict[str, Any]] = {}
            for row in cursor.fetchall():
                db_lookup[row[0]] = {
                    "stock_name": row[1] or "",
                    "close": float(row[2]) if row[2] is not None else None,
                }

            for cand in candidates:
                code = cand.get("stock_code", "")
                info = db_lookup.get(code, {})
                if info:
                    if not cand.get("stock_name"):
                        cand["stock_name"] = info["stock_name"]
                    if not cand.get("entry_price") and info.get("close"):
                        cand["entry_price"] = info["close"]
        finally:
            conn.close()

        return candidates
