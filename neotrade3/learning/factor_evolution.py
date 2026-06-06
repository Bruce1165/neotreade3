"""Factor discovery and elimination for NeoTrade3 self-evolution.

因子发现与淘汰 - 自动评估因子有效性，发现新因子，淘汰失效因子
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import Enum
from pathlib import Path
from typing import Any


class FactorStatus(str, Enum):
    """Status of a factor in the evolution system."""
    ACTIVE = "active"           # 活跃使用中
    CANDIDATE = "candidate"     # 候选因子（观察期）
    UNDER_REVIEW = "under_review"  # 复审中
    DEPRECATED = "deprecated"   # 已淘汰
    ARCHIVED = "archived"       # 已归档


@dataclass
class FactorPerformance:
    """Performance metrics for a factor."""
    # Time range
    start_date: date
    end_date: date
    
    # Prediction accuracy
    hit_rate: float = 0.0           # 命中率 (%)
    precision: float = 0.0          # 精确率 (%)
    recall: float = 0.0             # 召回率 (%)
    
    # Return metrics
    avg_return_when_signal: float = 0.0   # 信号发出后平均收益
    avg_return_when_no_signal: float = 0.0  # 无信号时平均收益
    excess_return: float = 0.0       # 超额收益
    
    # Risk metrics
    max_drawdown_when_signal: float = 0.0  # 信号期最大回撤
    volatility: float = 0.0          # 收益波动率
    
    # Stability
    consistency_score: float = 0.0   # 一致性得分 (0-100)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "period": {
                "start": self.start_date.isoformat(),
                "end": self.end_date.isoformat(),
            },
            "accuracy": {
                "hit_rate": round(self.hit_rate, 2),
                "precision": round(self.precision, 2),
                "recall": round(self.recall, 2),
            },
            "returns": {
                "avg_when_signal": round(self.avg_return_when_signal, 2),
                "avg_when_no_signal": round(self.avg_return_when_no_signal, 2),
                "excess": round(self.excess_return, 2),
            },
            "risk": {
                "max_drawdown": round(self.max_drawdown_when_signal, 2),
                "volatility": round(self.volatility, 2),
            },
            "consistency_score": round(self.consistency_score, 2),
        }


@dataclass
class Factor:
    """A factor in the evolution system."""
    factor_id: str
    name: str
    description: str
    category: str  # e.g., "technical", "fundamental", "sentiment"
    
    # Status
    status: FactorStatus
    created_at: date
    
    # Configuration
    parameters: dict[str, Any] = field(default_factory=dict)
    
    # Performance history
    performance_history: list[FactorPerformance] = field(default_factory=list)
    
    # Current score (0-100)
    current_score: float = 50.0
    
    # Evolution tracking
    last_evaluated: date | None = None
    evaluation_count: int = 0
    
    def get_latest_performance(self) -> FactorPerformance | None:
        """Get the most recent performance record."""
        if not self.performance_history:
            return None
        return max(self.performance_history, key=lambda p: p.end_date)
    
    def update_score(self, new_performance: FactorPerformance) -> None:
        """Update factor score based on new performance."""
        self.performance_history.append(new_performance)
        
        # Simple scoring: weighted average of recent performances
        if len(self.performance_history) >= 3:
            recent = self.performance_history[-3:]
        else:
            recent = self.performance_history
        
        # Score components
        hit_rate_score = new_performance.hit_rate
        excess_return_score = min(100, max(0, new_performance.excess_return * 5 + 50))
        consistency_score = new_performance.consistency_score
        
        # Weighted composite
        self.current_score = (
            hit_rate_score * 0.4 +
            excess_return_score * 0.4 +
            consistency_score * 0.2
        )
        
        self.last_evaluated = new_performance.end_date
        self.evaluation_count += 1
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "factor_id": self.factor_id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "current_score": round(self.current_score, 2),
            "evaluation_count": self.evaluation_count,
            "last_evaluated": self.last_evaluated.isoformat() if self.last_evaluated else None,
            "latest_performance": self.get_latest_performance().to_dict() if self.get_latest_performance() else None,
        }


class FactorDiscovery:
    """Discovers and manages factors for self-evolution."""
    
    # Score thresholds
    CANDIDATE_THRESHOLD = 55.0      # 进入候选池
    ACTIVE_THRESHOLD = 65.0         # 升级为活跃
    REVIEW_THRESHOLD = 45.0         # 进入复审
    DEPRECATE_THRESHOLD = 35.0      # 淘汰
    
    # Evaluation periods (days)
    CANDIDATE_OBSERVATION_DAYS = 30
    ACTIVE_EVALUATION_DAYS = 90
    
    def __init__(
        self,
        db_path: str,
        factors_storage_path: str | None = None,
    ) -> None:
        self.db_path = db_path
        self.factors: dict[str, Factor] = {}
        
        if factors_storage_path:
            self.storage_path = Path(factors_storage_path)
            self._load_factors()
        else:
            self.storage_path = None
            self._init_builtin_factors()
    
    def _init_builtin_factors(self) -> None:
        """Initialize built-in factors."""
        builtin_factors = [
            Factor(
                factor_id="resonance_technical",
                name="技术面共振",
                description="基于价格形态、趋势、动量的技术评分",
                category="technical",
                status=FactorStatus.ACTIVE,
                created_at=date.today(),
                parameters={"weight": 0.40},
            ),
            Factor(
                factor_id="resonance_capital",
                name="资金面共振",
                description="基于成交量、资金流向的资金评分",
                category="technical",
                status=FactorStatus.ACTIVE,
                created_at=date.today(),
                parameters={"weight": 0.30},
            ),
            Factor(
                factor_id="resonance_policy",
                name="政策面共振",
                description="基于政策关键词、公告的政策评分",
                category="sentiment",
                status=FactorStatus.ACTIVE,
                created_at=date.today(),
                parameters={"weight": 0.30},
            ),
            Factor(
                factor_id="elliott_wave_position",
                name="波浪位置",
                description="艾略特波浪理论中的Wave 3/5/B位置",
                category="technical",
                status=FactorStatus.ACTIVE,
                created_at=date.today(),
                parameters={"weight": 0.25},
            ),
            Factor(
                factor_id="sector_rps",
                name="板块RPS",
                description="相对价格强度排名",
                category="technical",
                status=FactorStatus.ACTIVE,
                created_at=date.today(),
                parameters={"weight": 0.15},
            ),
            Factor(
                factor_id="stock_tier",
                name="个股分层",
                description="龙头/中军/跟随分层",
                category="technical",
                status=FactorStatus.ACTIVE,
                created_at=date.today(),
                parameters={"weight": 0.15},
            ),
        ]
        
        for f in builtin_factors:
            self.factors[f.factor_id] = f
    
    def _load_factors(self) -> None:
        """Load factors from storage."""
        if not self.storage_path or not self.storage_path.exists():
            self._init_builtin_factors()
            return
        
        try:
            data = json.loads(self.storage_path.read_text(encoding="utf-8"))
            for f_data in data.get("factors", []):
                factor = Factor(
                    factor_id=f_data["factor_id"],
                    name=f_data["name"],
                    description=f_data["description"],
                    category=f_data["category"],
                    status=FactorStatus(f_data["status"]),
                    created_at=date.fromisoformat(f_data["created_at"]),
                    parameters=f_data.get("parameters", {}),
                    current_score=f_data.get("current_score", 50.0),
                    evaluation_count=f_data.get("evaluation_count", 0),
                    last_evaluated=date.fromisoformat(f_data["last_evaluated"]) if f_data.get("last_evaluated") else None,
                )
                self.factors[factor.factor_id] = factor
        except (OSError, json.JSONDecodeError, KeyError):
            self._init_builtin_factors()
    
    def save_factors(self) -> None:
        """Save factors to storage."""
        if not self.storage_path:
            return
        
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            "saved_at": date.today().isoformat(),
            "factors": [
                {
                    "factor_id": f.factor_id,
                    "name": f.name,
                    "description": f.description,
                    "category": f.category,
                    "status": f.status.value,
                    "created_at": f.created_at.isoformat(),
                    "parameters": f.parameters,
                    "current_score": f.current_score,
                    "evaluation_count": f.evaluation_count,
                    "last_evaluated": f.last_evaluated.isoformat() if f.last_evaluated else None,
                }
                for f in self.factors.values()
            ],
        }
        
        self.storage_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    
    def evaluate_all_factors(
        self,
        start_date: date,
        end_date: date,
    ) -> dict[str, FactorPerformance]:
        """Evaluate all active factors over a period."""
        results: dict[str, FactorPerformance] = {}
        
        for factor_id, factor in self.factors.items():
            if factor.status not in (FactorStatus.ACTIVE, FactorStatus.CANDIDATE):
                continue
            
            performance = self._evaluate_factor(factor, start_date, end_date)
            if performance:
                factor.update_score(performance)
                results[factor_id] = performance
                
                # Update status based on score
                self._update_factor_status(factor)
        
        self.save_factors()
        return results
    
    def _evaluate_factor(
        self,
        factor: Factor,
        start_date: date,
        end_date: date,
    ) -> FactorPerformance | None:
        """Evaluate a single factor's performance."""
        # This is a simplified evaluation
        # In production, this would query actual signal and trade data
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Get signals generated by this factor
                # (Simplified: assume we have a signals table)
                
                # Mock evaluation for demonstration
                # In reality, this would calculate from actual trade results
                
                # Simulate different performance by factor type
                if factor.factor_id.startswith("resonance"):
                    hit_rate = 65.0
                    excess_return = 8.5
                elif factor.factor_id.startswith("elliott"):
                    hit_rate = 58.0
                    excess_return = 6.2
                elif factor.factor_id.startswith("sector"):
                    hit_rate = 62.0
                    excess_return = 5.8
                else:
                    hit_rate = 55.0
                    excess_return = 4.5
                
                # Adjust by current score (regression to mean)
                hit_rate = (hit_rate + factor.current_score) / 2
                
                return FactorPerformance(
                    start_date=start_date,
                    end_date=end_date,
                    hit_rate=hit_rate,
                    precision=hit_rate * 0.9,
                    recall=hit_rate * 0.85,
                    avg_return_when_signal=excess_return,
                    avg_return_when_no_signal=-2.0,
                    excess_return=excess_return,
                    max_drawdown_when_signal=-8.0,
                    volatility=12.0,
                    consistency_score=70.0 if hit_rate > 60 else 50.0,
                )
        except Exception:
            return None
    
    def _update_factor_status(self, factor: Factor) -> None:
        """Update factor status based on current score."""
        if factor.status == FactorStatus.CANDIDATE:
            if factor.current_score >= self.ACTIVE_THRESHOLD:
                factor.status = FactorStatus.ACTIVE
            elif factor.current_score < self.REVIEW_THRESHOLD:
                factor.status = FactorStatus.UNDER_REVIEW
        
        elif factor.status == FactorStatus.ACTIVE:
            if factor.current_score < self.REVIEW_THRESHOLD:
                factor.status = FactorStatus.UNDER_REVIEW
        
        elif factor.status == FactorStatus.UNDER_REVIEW:
            if factor.current_score >= self.ACTIVE_THRESHOLD:
                factor.status = FactorStatus.ACTIVE
            elif factor.current_score < self.DEPRECATE_THRESHOLD:
                factor.status = FactorStatus.DEPRECATED
        
        elif factor.status == FactorStatus.DEPRECATED:
            if factor.current_score >= self.CANDIDATE_THRESHOLD:
                factor.status = FactorStatus.CANDIDATE
    
    def discover_new_factors(
        self,
        start_date: date,
        end_date: date,
    ) -> list[Factor]:
        """Discover potential new factors from data using correlation analysis."""
        discovered: list[Factor] = []

        # Try to connect to the database for data-driven discovery
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            discovered = self._discover_from_db(conn, start_date, end_date)
            conn.close()
        except Exception:
            # Fallback: generate heuristic candidates
            discovered = self._discover_heuristic_candidates()

        # Add to factor pool
        for f in discovered:
            if f.factor_id not in self.factors:
                self.factors[f.factor_id] = f

        self.save_factors()
        return discovered

    def _discover_from_db(
        self,
        conn: sqlite3.Connection,
        start_date: date,
        end_date: date,
    ) -> list[Factor]:
        """Discover factors by analyzing price-volume patterns in the database."""
        discovered: list[Factor] = []
        today_str = date.today().strftime("%Y%m%d")

        # --- Factor 1: Volume-price divergence ---
        # Stocks where price drops but volume spikes tend to reverse
        try:
            rows = conn.execute(
                """
                SELECT code,
                       AVG(CASE WHEN pct_change < -0.02 AND volume > avg_vol * 1.5
                           THEN 1.0 ELSE 0.0 END) as signal_freq,
                       AVG(CASE WHEN pct_change < -0.02 AND volume > avg_vol * 1.5
                           THEN LEAD(pct_change, 5) OVER (
                               PARTITION BY code ORDER BY trade_date) END) as fwd_return
                FROM (
                    SELECT code, trade_date, pct_change, volume,
                           AVG(volume) OVER (
                               PARTITION BY code ORDER BY trade_date
                               ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING) as avg_vol
                    FROM daily_prices
                    WHERE trade_date >= ? AND trade_date <= ?
                ) sub
                GROUP BY code
                HAVING signal_freq > 0.01
                LIMIT 20
                """,
                (start_date.isoformat(), end_date.isoformat()),
            ).fetchall()

            if rows:
                avg_fwd = sum(
                    r["fwd_return"] for r in rows if r["fwd_return"] is not None
                ) / max(1, sum(1 for r in rows if r["fwd_return"] is not None))

                if avg_fwd > 0:
                    discovered.append(
                        Factor(
                            factor_id=f"vol_price_divergence_{today_str}",
                            name="量价背离因子",
                            description="放量下跌后5日收益率为正的股票，捕捉恐慌抛售后的反弹",
                            category="technical",
                            status=FactorStatus.CANDIDATE,
                            created_at=date.today(),
                            parameters={
                                "lookback_volume": 20,
                                "drop_threshold": -0.02,
                                "volume_multiplier": 1.5,
                                "forward_days": 5,
                                "avg_forward_return": round(avg_fwd * 100, 2),
                            },
                        )
                    )
        except Exception:
            pass

        # --- Factor 2: Consecutive down-day reversal ---
        try:
            rows = conn.execute(
                """
                SELECT code,
                       COUNT(*) as reversal_count,
                       AVG(fwd_5d) as avg_fwd_5d
                FROM (
                    SELECT code, trade_date, pct_change,
                           LEAD(pct_change, 1) OVER (PARTITION BY code ORDER BY trade_date) as next_chg,
                           LEAD(pct_change, 5) OVER (PARTITION BY code ORDER BY trade_date) as fwd_5d
                    FROM daily_prices
                    WHERE trade_date >= ? AND trade_date <= ?
                ) sub
                WHERE pct_change < -0.01 AND next_chg > 0.01
                GROUP BY code
                HAVING reversal_count >= 3
                LIMIT 20
                """,
                (start_date.isoformat(), end_date.isoformat()),
            ).fetchall()

            if rows:
                avg_fwd = sum(
                    r["avg_fwd_5d"] for r in rows if r["avg_fwd_5d"] is not None
                ) / max(1, len(rows))

                if avg_fwd > 0:
                    discovered.append(
                        Factor(
                            factor_id=f"consec_down_reversal_{today_str}",
                            name="连阴反转因子",
                            description="连续下跌后次日反转的股票，5日平均收益为正",
                            category="technical",
                            status=FactorStatus.CANDIDATE,
                            created_at=date.today(),
                            parameters={
                                "min_consecutive": 2,
                                "drop_threshold": -0.01,
                                "reversal_threshold": 0.01,
                                "forward_days": 5,
                                "avg_forward_return": round(avg_fwd * 100, 2),
                            },
                        )
                    )
        except Exception:
            pass

        # --- Factor 3: High turnover rate momentum ---
        try:
            rows = conn.execute(
                """
                SELECT code,
                       AVG(turnover) as avg_turnover,
                       AVG(CASE WHEN turnover > 5.0 THEN LEAD(pct_change, 5) OVER (
                           PARTITION BY code ORDER BY trade_date) END) as high_turn_fwd
                FROM daily_prices
                WHERE trade_date >= ? AND trade_date <= ? AND turnover IS NOT NULL
                GROUP BY code
                HAVING avg_turnover > 3.0
                LIMIT 20
                """,
                (start_date.isoformat(), end_date.isoformat()),
            ).fetchall()

            if rows:
                avg_fwd = sum(
                    r["high_turn_fwd"] for r in rows if r["high_turn_fwd"] is not None
                ) / max(1, sum(1 for r in rows if r["high_turn_fwd"] is not None))

                if avg_fwd > 0:
                    discovered.append(
                        Factor(
                            factor_id=f"high_turnover_momentum_{today_str}",
                            name="高换手动量因子",
                            description="换手率超过5%的股票，5日平均收益为正",
                            category="technical",
                            status=FactorStatus.CANDIDATE,
                            created_at=date.today(),
                            parameters={
                                "turnover_threshold": 5.0,
                                "avg_turnover_min": 3.0,
                                "forward_days": 5,
                                "avg_forward_return": round(avg_fwd * 100, 2),
                            },
                        )
                    )
        except Exception:
            pass

        # If no data-driven factors found, fall back to heuristics
        if not discovered:
            discovered = self._discover_heuristic_candidates()

        return discovered

    def _discover_heuristic_candidates(self) -> list[Factor]:
        """Generate heuristic factor candidates when DB is unavailable."""
        today_str = date.today().strftime("%Y%m%d")
        return [
            Factor(
                factor_id=f"momentum_20d_{today_str}",
                name="20日动量因子",
                description="基于20日价格变化率的动量因子",
                category="technical",
                status=FactorStatus.CANDIDATE,
                created_at=date.today(),
                parameters={"lookback_days": 20, "threshold": 5.0},
            ),
            Factor(
                factor_id=f"volatility_contraction_{today_str}",
                name="波动率收缩因子",
                description="识别波动率收缩后可能突破的股票",
                category="technical",
                status=FactorStatus.CANDIDATE,
                created_at=date.today(),
                parameters={"lookback_days": 10, "contraction_ratio": 0.5},
            ),
        ]
    
    def get_active_factors(self) -> list[Factor]:
        """Get all active factors."""
        return [f for f in self.factors.values() if f.status == FactorStatus.ACTIVE]
    
    def get_factors_for_elimination(self) -> list[Factor]:
        """Get factors marked for elimination."""
        return [f for f in self.factors.values() if f.status == FactorStatus.DEPRECATED]
    
    def get_evolution_summary(self) -> dict[str, Any]:
        """Get summary of factor evolution state."""
        status_counts: dict[str, int] = {}
        for f in self.factors.values():
            status_counts[f.status.value] = status_counts.get(f.status.value, 0) + 1
        
        avg_score = sum(f.current_score for f in self.factors.values()) / len(self.factors) if self.factors else 0
        
        return {
            "total_factors": len(self.factors),
            "status_distribution": status_counts,
            "average_score": round(avg_score, 2),
            "top_factors": [
                f.to_dict()
                for f in sorted(self.factors.values(), key=lambda x: x.current_score, reverse=True)[:5]
            ],
            "factors_for_review": [
                f.to_dict()
                for f in self.factors.values()
                if f.status == FactorStatus.UNDER_REVIEW
            ],
        }
