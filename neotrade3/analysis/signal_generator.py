"""Comprehensive signal generator for NeoTrade3.

综合信号生成器 - 整合多维分析，生成高确定性操作信号
多维度共振：技术面 + 资金面 + 政策面 + 波浪位置 + 板块轮动 + 个股分层
"""

from __future__ import annotations

import sqlite3
import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class SignalDirection(str, Enum):
    """Signal direction."""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


class SignalGrade(str, Enum):
    """Signal certainty grade - 信号确定性等级."""
    A = "A"  # 强共振：≥4 维度对齐，高确定性
    B = "B"  # 多维度：3 维度对齐，较高确定性
    C = "C"  # 单维度：1-2 维度触发，需谨慎


class SignalSource(str, Enum):
    """Which dimension contributed to the signal."""
    RESONANCE = "resonance"          # 三维共振评分
    ELLIOTT_WAVE = "elliott_wave"    # 艾略特波浪
    SECTOR_ROTATION = "sector"       # 板块轮动
    STOCK_TIERING = "tiering"        # 个股分层
    MARKET_PHASE = "market_phase"    # 市场相位
    CUP_HANDLE = "cup_handle"        # 杯柄形态


@dataclass
class DimensionScore:
    """Score from a single analysis dimension."""
    source: SignalSource
    score: float          # 0-100
    is_bullish: bool      # 是否看多
    weight: float         # 该维度在综合评分中的权重
    detail: str = ""      # 简要说明


@dataclass
class ExpectedReturn:
    """Expected return range for a signal."""
    conservative_pct: float   # 保守估计 (%)
    base_pct: float           # 基准估计 (%)
    optimistic_pct: float     # 乐观估计 (%)
    holding_days_min: int    # 最短持仓天数
    holding_days_max: int    # 最长持仓天数
    confidence_pct: float     # 预判置信度 (%)

    def to_dict(self) -> dict[str, Any]:
        return {
            "conservative_pct": round(self.conservative_pct, 1),
            "base_pct": round(self.base_pct, 1),
            "optimistic_pct": round(self.optimistic_pct, 1),
            "holding_days_range": [self.holding_days_min, self.holding_days_max],
            "confidence_pct": round(self.confidence_pct, 1),
        }


@dataclass
class TradingSignal:
    """A comprehensive trading signal."""
    signal_id: str
    code: str
    name: str
    direction: SignalDirection
    grade: SignalGrade

    # Price levels
    entry_price: float
    stop_loss: float
    take_profit_1: float     # 第一目标
    take_profit_2: float     # 第二目标
    take_profit_3: float     # 极端目标

    # Scoring
    composite_score: float   # 综合评分 0-100
    dimension_scores: list[DimensionScore]

    # Expected return
    expected_return: ExpectedReturn

    # Risk
    risk_reward_ratio: float
    max_loss_pct: float      # 最大亏损 (%)

    # Timing
    signal_date: date
    valid_until: date        # 信号有效期

    # Source tracking
    contributing_dimensions: list[SignalSource] = field(default_factory=list)
    reasoning: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "code": self.code,
            "name": self.name,
            "direction": self.direction.value,
            "grade": self.grade.value,
            "composite_score": round(self.composite_score, 1),
            "price_levels": {
                "entry": round(self.entry_price, 2),
                "stop_loss": round(self.stop_loss, 2),
                "take_profit_1": round(self.take_profit_1, 2),
                "take_profit_2": round(self.take_profit_2, 2),
                "take_profit_3": round(self.take_profit_3, 2),
            },
            "risk": {
                "risk_reward_ratio": round(self.risk_reward_ratio, 2),
                "max_loss_pct": round(self.max_loss_pct, 1),
            },
            "expected_return": self.expected_return.to_dict(),
            "dimensions": [
                {
                    "source": d.source.value,
                    "score": round(d.score, 1),
                    "is_bullish": d.is_bullish,
                    "weight": d.weight,
                    "detail": d.detail,
                }
                for d in self.dimension_scores
            ],
            "contributing_dimensions": [d.value for d in self.contributing_dimensions],
            "timing": {
                "signal_date": self.signal_date.isoformat(),
                "valid_until": self.valid_until.isoformat(),
            },
            "reasoning": self.reasoning,
        }


@dataclass
class SignalGenerationResult:
    """Result of signal generation for a batch of stocks."""
    target_date: date
    market_phase: str
    signals: list[TradingSignal] = field(default_factory=list)

    # Summary
    total_analyzed: int = 0
    buy_signals: int = 0
    sell_signals: int = 0
    grade_a_count: int = 0
    grade_b_count: int = 0
    grade_c_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_date": self.target_date.isoformat(),
            "market_phase": self.market_phase,
            "summary": {
                "total_analyzed": self.total_analyzed,
                "buy_signals": self.buy_signals,
                "sell_signals": self.sell_signals,
                "grade_distribution": {
                    "A": self.grade_a_count,
                    "B": self.grade_b_count,
                    "C": self.grade_c_count,
                },
            },
            "signals": [s.to_dict() for s in self.signals],
        }


class SignalGenerator:
    """Generate comprehensive trading signals by combining multiple analysis dimensions."""

    # Dimension weights for composite scoring
    DIMENSION_WEIGHTS: dict[SignalSource, float] = {
        SignalSource.RESONANCE: 0.30,       # 三维共振权重最高
        SignalSource.ELLIOTT_WAVE: 0.25,     # 波浪位置
        SignalSource.SECTOR_ROTATION: 0.15,  # 板块轮动
        SignalSource.STOCK_TIERING: 0.15,    # 个股分层
        SignalSource.MARKET_PHASE: 0.10,     # 市场相位
        SignalSource.CUP_HANDLE: 0.05,       # 杯柄形态
    }

    # Grade thresholds
    GRADE_A_MIN_DIMENSIONS = 4   # A级需要≥4个维度对齐
    GRADE_B_MIN_DIMENSIONS = 3   # B级需要≥3个维度对齐
    MIN_BULLISH_SCORE = 60.0     # 最低看多评分

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path

    def generate(
        self,
        codes: list[str] | None = None,
        target_date: date | None = None,
        min_grade: SignalGrade = SignalGrade.C,
    ) -> SignalGenerationResult:
        """Generate trading signals for a set of stocks.

        Args:
            codes: Stock codes to analyze. If None, analyze from candidate pools.
            target_date: Analysis date.
            min_grade: Minimum signal grade to include.

        Returns:
            SignalGenerationResult with all generated signals.
        """
        if target_date is None:
            target_date = date.today()

        result = SignalGenerationResult(
            target_date=target_date,
            market_phase="unknown",
        )

        # Step 1: Detect market phase (gating condition)
        try:
            from neotrade3.analysis.market_phase import detect_market_phase
            phase_result = detect_market_phase(
                db_path=self.db_path,
                target_date=target_date.isoformat(),
            )
            result.market_phase = phase_result.phase.value

            # In bear market, be very selective
            market_bullish = phase_result.phase.value in ("bull", "transition")
            market_score = phase_result.confidence if market_bullish else phase_result.confidence * 0.3
        except Exception as exc:
            logger.warning(
                "SignalGenerator market phase detection degraded on %s: %s",
                target_date.isoformat(),
                exc,
            )
            market_bullish = True
            market_score = 50.0

        # Step 2: Get candidate codes if not provided (None means auto-select, [] means empty)
        if codes is None:
            codes = self._get_candidate_codes(target_date)

        if not codes:
            result.total_analyzed = 0
            return result

        result.total_analyzed = len(codes)

        # Step 3: Analyze each stock
        for code in codes:
            signal = self._analyze_stock(
                code=code,
                target_date=target_date,
                market_bullish=market_bullish,
                market_score=market_score,
            )

            if signal is None:
                continue

            # Filter by minimum grade
            grade_order = {SignalGrade.A: 0, SignalGrade.B: 1, SignalGrade.C: 2}
            if grade_order.get(signal.grade, 3) > grade_order.get(min_grade, 2):
                continue

            # Only include BUY signals (sell signals handled separately)
            if signal.direction == SignalDirection.BUY:
                result.signals.append(signal)
                result.buy_signals += 1
                if signal.grade == SignalGrade.A:
                    result.grade_a_count += 1
                elif signal.grade == SignalGrade.B:
                    result.grade_b_count += 1
                else:
                    result.grade_c_count += 1

        # Sort by composite score descending
        result.signals.sort(key=lambda s: s.composite_score, reverse=True)

        return result

    def _analyze_stock(
        self,
        code: str,
        target_date: date,
        market_bullish: bool,
        market_score: float,
    ) -> TradingSignal | None:
        """Analyze a single stock and generate signal if warranted."""
        dimension_scores: list[DimensionScore] = []
        bullish_dimensions: list[SignalSource] = []
        name = ""
        current_price = 0.0

        # Get current price
        try:
            name, current_price = self._get_stock_info(code, target_date)
        except Exception as exc:
            logger.warning(
                "SignalGenerator stock info lookup failed for %s on %s: %s",
                code,
                target_date.isoformat(),
                exc,
            )
            return None

        if current_price <= 0:
            return None

        # Dimension 1: Resonance Score (三维共振)
        # Use factor_matrix data if available, otherwise compute simplified score
        resonance_score = 0.0
        try:
            # Try to get resonance score from factor_matrix data
            # This is computed in factor_matrix module using ResonanceScorer
            # For now, use a simplified calculation based on price momentum
            with sqlite3.connect(self.db_path) as conn:
                # Get 20-day price change as proxy for momentum
                row = conn.execute(
                    """
                    SELECT pct_change, turnover
                    FROM daily_prices
                    WHERE code = ? AND trade_date <= ?
                    ORDER BY trade_date DESC
                    LIMIT 1
                    """,
                    (code, target_date.isoformat()),
                ).fetchone()
                if row:
                    pct_chg = row[0] or 0
                    turnover = row[1] or 0
                    # Simplified resonance: base 50 + momentum contribution
                    resonance_score = 50.0 + pct_chg * 2 + min(turnover, 10) * 2
                    resonance_score = max(0, min(100, resonance_score))
            
            if resonance_score >= self.MIN_BULLISH_SCORE:
                bullish_dimensions.append(SignalSource.RESONANCE)
            dimension_scores.append(DimensionScore(
                source=SignalSource.RESONANCE,
                score=resonance_score,
                is_bullish=resonance_score >= self.MIN_BULLISH_SCORE,
                weight=self.DIMENSION_WEIGHTS[SignalSource.RESONANCE],
                detail=f"共振分{resonance_score:.0f} (基于动量)",
            ))
        except Exception as exc:
            logger.warning(
                "SignalGenerator resonance analysis degraded for %s on %s: %s",
                code,
                target_date.isoformat(),
                exc,
            )

        # Dimension 2: Elliott Wave (波浪位置)
        wave_signal = None
        try:
            from neotrade3.analysis.elliott_wave import ElliottWaveAnalyzer
            analyzer = ElliottWaveAnalyzer(db_path=self.db_path)
            wave_result = analyzer.analyze(code=code, target_date=target_date)

            if wave_result and wave_result.signals:
                primary = wave_result.get_primary_signal()
                if primary:
                    wave_signal = primary
                    is_bull = primary.wave_position.value in ("ideal_entry", "caution_entry")
                    if is_bull:
                        bullish_dimensions.append(SignalSource.ELLIOTT_WAVE)
                    dimension_scores.append(DimensionScore(
                        source=SignalSource.ELLIOTT_WAVE,
                        score=primary.confidence,
                        is_bullish=is_bull,
                        weight=self.DIMENSION_WEIGHTS[SignalSource.ELLIOTT_WAVE],
                        detail=f"Wave {primary.current_wave.value} {primary.wave_position.value} R/R:{primary.risk_reward_ratio:.1f}",
                    ))
        except Exception as exc:
            logger.warning(
                "SignalGenerator Elliott Wave analysis degraded for %s on %s: %s",
                code,
                target_date.isoformat(),
                exc,
            )

        # Dimension 3: Sector Rotation (板块轮动)
        try:
            from neotrade3.analysis.sector_rotation import SectorRotationAnalyzer
            rot_analyzer = SectorRotationAnalyzer(db_path=self.db_path)
            rot_result = rot_analyzer.analyze(target_date=target_date.isoformat())

            # Check if stock's sector is in top sectors
            stock_sector = self._get_stock_sector(code)
            is_top_sector = False
            sector_rps_score = 0.0
            is_policy_mainline = False

            if stock_sector and rot_result.top_sectors:
                for sr in rot_result.top_sectors:
                    if sr.sector_name == stock_sector:
                        sector_rps_score = sr.rps_120
                        is_top_sector = True
                        is_policy_mainline = sr.is_mainline
                        break

            is_bull = is_top_sector or sector_rps_score > 70
            if is_bull:
                bullish_dimensions.append(SignalSource.SECTOR_ROTATION)
            dimension_scores.append(DimensionScore(
                source=SignalSource.SECTOR_ROTATION,
                score=sector_rps_score,
                is_bullish=is_bull,
                weight=self.DIMENSION_WEIGHTS[SignalSource.SECTOR_ROTATION],
                detail=f"板块{stock_sector or '?'} RPS120:{sector_rps_score:.0f} {'主线' if is_policy_mainline else '非主线'}",
            ))
        except Exception as exc:
            logger.warning(
                "SignalGenerator sector rotation analysis degraded for %s on %s: %s",
                code,
                target_date.isoformat(),
                exc,
            )

        # Dimension 4: Stock Tiering (个股分层)
        try:
            from neotrade3.analysis.stock_tiering import StockTieringAnalyzer, StockTier
            tier_analyzer = StockTieringAnalyzer(db_path=self.db_path)
            tier_result = tier_analyzer.analyze(codes=[code], target_date=target_date)

            tier = "unknown"
            leadership_score = 0.0
            if tier_result.all_tiered_stocks:
                ts = tier_result.all_tiered_stocks[0]
                tier = ts.tier.value
                leadership_score = ts.metrics.leadership_score

            is_bull = tier in ("leader", "core")
            if is_bull:
                bullish_dimensions.append(SignalSource.STOCK_TIERING)
            dimension_scores.append(DimensionScore(
                source=SignalSource.STOCK_TIERING,
                score=leadership_score,
                is_bullish=is_bull,
                weight=self.DIMENSION_WEIGHTS[SignalSource.STOCK_TIERING],
                detail=f"分层:{tier} 领导分:{leadership_score:.0f}",
            ))
        except Exception as exc:
            logger.warning(
                "SignalGenerator stock tiering analysis degraded for %s on %s: %s",
                code,
                target_date.isoformat(),
                exc,
            )

        # Dimension 5: Market Phase (市场相位)
        is_bull = market_bullish
        if is_bull:
            bullish_dimensions.append(SignalSource.MARKET_PHASE)
        # Get market phase name for display
        market_phase_name = "bull" if market_bullish else "bear"
        dimension_scores.append(DimensionScore(
            source=SignalSource.MARKET_PHASE,
            score=market_score,
            is_bullish=is_bull,
            weight=self.DIMENSION_WEIGHTS[SignalSource.MARKET_PHASE],
            detail=f"市场{market_phase_name} 确信度{market_score:.0f}",
        ))

        # Calculate composite score
        composite_score = sum(d.score * d.weight for d in dimension_scores)
        normalized_score = min(100, composite_score)

        # Determine grade
        n_bullish = len(bullish_dimensions)
        if n_bullish >= self.GRADE_A_MIN_DIMENSIONS and normalized_score >= 75:
            grade = SignalGrade.A
        elif n_bullish >= self.GRADE_B_MIN_DIMENSIONS and normalized_score >= 60:
            grade = SignalGrade.B
        elif n_bullish >= 2 and normalized_score >= 50:
            grade = SignalGrade.C
        else:
            return None  # Not enough conviction

        # Calculate price levels
        stop_loss, tp1, tp2, tp3 = self._calculate_price_levels(
            current_price, dimension_scores, wave_signal
        )

        # Calculate expected return
        expected_return = self._calculate_expected_return(
            grade=grade,
            composite_score=normalized_score,
            entry_price=current_price,
            take_profit_1=tp1,
            take_profit_2=tp2,
            wave_signal=wave_signal,
        )

        # Risk metrics
        risk = current_price - stop_loss
        reward = tp1 - current_price
        risk_reward = reward / risk if risk > 0 else 0
        max_loss_pct = (risk / current_price) * 100 if current_price > 0 else 0

        # Build reasoning
        reasoning = self._build_reasoning(
            code=code,
            name=name,
            grade=grade,
            bullish_dimensions=bullish_dimensions,
            dimension_scores=dimension_scores,
            wave_signal=wave_signal,
        )

        # Signal validity: 5 trading days
        valid_until = target_date + timedelta(days=7)

        return TradingSignal(
            signal_id=f"{target_date.isoformat()}_{code}_{grade.value}",
            code=code,
            name=name,
            direction=SignalDirection.BUY,
            grade=grade,
            entry_price=current_price,
            stop_loss=stop_loss,
            take_profit_1=tp1,
            take_profit_2=tp2,
            take_profit_3=tp3,
            composite_score=normalized_score,
            dimension_scores=dimension_scores,
            expected_return=expected_return,
            risk_reward_ratio=risk_reward,
            max_loss_pct=max_loss_pct,
            signal_date=target_date,
            valid_until=valid_until,
            contributing_dimensions=bullish_dimensions,
            reasoning=reasoning,
        )

    def _calculate_price_levels(
        self,
        current_price: float,
        dimension_scores: list[DimensionScore],
        wave_signal: Any | None,
    ) -> tuple[float, float, float, float]:
        """Calculate stop loss and take profit levels."""
        # Stop loss: use wave signal if available, otherwise 8% below
        if wave_signal:
            stop_loss = wave_signal.stop_loss
        else:
            stop_loss = current_price * 0.92

        # Take profit levels based on composite score
        avg_score = sum(d.score for d in dimension_scores) / len(dimension_scores) if dimension_scores else 50

        if avg_score >= 80:
            tp1 = current_price * 1.15   # +15%
            tp2 = current_price * 1.25   # +25%
            tp3 = current_price * 1.40   # +40%
        elif avg_score >= 70:
            tp1 = current_price * 1.12   # +12%
            tp2 = current_price * 1.20   # +20%
            tp3 = current_price * 1.30   # +30%
        elif avg_score >= 60:
            tp1 = current_price * 1.08   # +8%
            tp2 = current_price * 1.15   # +15%
            tp3 = current_price * 1.22   # +22%
        else:
            tp1 = current_price * 1.05   # +5%
            tp2 = current_price * 1.10   # +10%
            tp3 = current_price * 1.15   # +15%

        # Override with wave targets if available
        if wave_signal:
            if wave_signal.take_profit_1 > current_price:
                tp1 = max(tp1, wave_signal.take_profit_1)
            if wave_signal.take_profit_2 > current_price:
                tp2 = max(tp2, wave_signal.take_profit_2)

        return stop_loss, tp1, tp2, tp3

    def _calculate_expected_return(
        self,
        grade: SignalGrade,
        composite_score: float,
        entry_price: float,
        take_profit_1: float,
        take_profit_2: float,
        wave_signal: Any | None,
    ) -> ExpectedReturn:
        """Calculate expected return range."""
        base_return = ((take_profit_1 - entry_price) / entry_price) * 100 if entry_price > 0 else 0
        optimistic_return = ((take_profit_2 - entry_price) / entry_price) * 100 if entry_price > 0 else 0

        # Conservative estimate: 50% of base target
        conservative_return = base_return * 0.5

        # Adjust by grade
        grade_multiplier = {SignalGrade.A: 1.0, SignalGrade.B: 0.8, SignalGrade.C: 0.6}
        mult = grade_multiplier.get(grade, 0.6)

        # Holding period based on wave or grade
        if wave_signal:
            holding_min = 10
            holding_max = 50
        elif grade == SignalGrade.A:
            holding_min = 20
            holding_max = 50
        elif grade == SignalGrade.B:
            holding_min = 15
            holding_max = 40
        else:
            holding_min = 10
            holding_max = 30

        # Confidence in prediction
        confidence = composite_score * mult

        return ExpectedReturn(
            conservative_pct=conservative_return,
            base_pct=base_return,
            optimistic_pct=optimistic_return,
            holding_days_min=holding_min,
            holding_days_max=holding_max,
            confidence_pct=min(95, confidence),
        )

    def _build_reasoning(
        self,
        code: str,
        name: str,
        grade: SignalGrade,
        bullish_dimensions: list[SignalSource],
        dimension_scores: list[DimensionScore],
        wave_signal: Any | None,
    ) -> str:
        """Build human-readable reasoning for the signal."""
        parts = [f"{name}({code}) {grade.value}级买入信号"]

        dim_names = {
            SignalSource.RESONANCE: "三维共振",
            SignalSource.ELLIOTT_WAVE: "波浪位置",
            SignalSource.SECTOR_ROTATION: "板块轮动",
            SignalSource.STOCK_TIERING: "个股分层",
            SignalSource.MARKET_PHASE: "市场环境",
            SignalSource.CUP_HANDLE: "杯柄形态",
        }

        aligned = [dim_names.get(d, d.value) for d in bullish_dimensions]
        parts.append(f"对齐维度({len(aligned)}/{len(dimension_scores)}): {', '.join(aligned)}")

        for ds in dimension_scores:
            flag = "✓" if ds.is_bullish else "✗"
            parts.append(f"  {flag} {dim_names.get(ds.source, ds.source.value)}: {ds.detail}")

        if wave_signal:
            parts.append(f"波浪信号: {wave_signal.reason}")

        return "\n".join(parts)

    def _get_stock_info(self, code: str, target_date: date) -> tuple[str, float]:
        """Get stock name and current price."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT s.name, dp.close
                FROM stocks s
                LEFT JOIN daily_prices dp ON s.code = dp.code AND dp.trade_date = ?
                WHERE s.code = ?
                """,
                (target_date.isoformat(), code),
            ).fetchone()
            if row:
                return row[0] or "", row[1] or 0.0
            return "", 0.0

    def _get_stock_sector(self, code: str) -> str | None:
        """Get stock sector."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT sector_lv1 AS sector FROM stocks WHERE code = ?",
                (code,),
            ).fetchone()
            return row[0] if row else None

    def _get_candidate_codes(self, target_date: date) -> list[str]:
        """Get candidate stock codes from screener results."""
        codes: list[str] = []
        project_root = self._find_project_root()

        if not project_root:
            return codes

        # Try cup_handle_v4 results
        import json

        artifact_path = (
            project_root
            / f"var/artifacts/screener_runs/{target_date.isoformat()}/screener_cup_handle_v4_result.json"
        )
        if artifact_path.exists():
            try:
                payload = json.loads(artifact_path.read_text(encoding="utf-8"))
                picks = payload.get("picks", [])
                for pick in picks:
                    if isinstance(pick, str):
                        codes.append(pick)
                    elif isinstance(pick, dict):
                        c = pick.get("code", "")
                        if c:
                            codes.append(c)
            except (OSError, json.JSONDecodeError):
                pass

        # If no screener results, get top stocks by volume
        if not codes:
            with sqlite3.connect(self.db_path) as conn:
                rows = conn.execute(
                    """
                    SELECT DISTINCT code FROM daily_prices
                    WHERE trade_date = ?
                    ORDER BY amount DESC
                    LIMIT 100
                    """,
                    (target_date.isoformat(),),
                ).fetchall()
                codes = [row[0] for row in rows]

        return list(set(codes))  # Deduplicate

    def _find_project_root(self) -> Path | None:
        """Find project root directory."""
        # Try common paths
        db_path = Path(self.db_path)
        for parent in [db_path.parent, db_path.parent.parent, db_path.parent.parent.parent]:
            if (parent / "config").exists():
                return parent
        return None
