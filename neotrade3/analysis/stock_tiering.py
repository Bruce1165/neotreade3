"""Stock tiering module for NeoTrade3 - 个股分层 (龙头/中军/跟随)."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import Enum
from typing import Any


class StockTier(str, Enum):
    """Stock tier classification."""
    LEADER = "leader"      # 龙头
    CORE = "core"          # 中军
    FOLLOWER = "follower"  # 跟随


@dataclass
class StockTierMetrics:
    """Metrics used for tiering classification."""
    code: str
    name: str
    sector: str | None
    
    # Volume metrics
    avg_amount_20d: float = 0.0  # 20日平均成交额(万元)
    amount_rank_in_sector: int = 0  # 行业内成交额排名
    
    # Price momentum metrics
    return_5d: float = 0.0   # 5日涨幅
    return_20d: float = 0.0  # 20日涨幅
    volatility_20d: float = 0.0  # 20日波动率
    
    # Relative strength
    rs_vs_sector_20d: float = 0.0  # 相对行业强弱
    rs_vs_market_20d: float = 0.0  # 相对市场强弱
    
    # Composite score
    leadership_score: float = 0.0  # 龙头潜力分 (0-100)


@dataclass
class TieredStock:
    """A stock with its tier classification."""
    code: str
    name: str
    sector: str | None
    tier: StockTier
    metrics: StockTierMetrics
    tier_confidence: float = 0.0  # 分层置信度


@dataclass
class SectorTieringResult:
    """Tiering result for a single sector."""
    sector: str
    total_stocks: int = 0
    leaders: list[TieredStock] = field(default_factory=list)
    cores: list[TieredStock] = field(default_factory=list)
    followers: list[TieredStock] = field(default_factory=list)


@dataclass
class StockTieringResult:
    """Overall tiering result for a date."""
    target_date: date
    lookback_days: int = 20
    sectors: list[SectorTieringResult] = field(default_factory=list)
    all_tiered_stocks: list[TieredStock] = field(default_factory=list)
    
    def get_by_tier(self, tier: StockTier) -> list[TieredStock]:
        """Get all stocks of a specific tier."""
        return [s for s in self.all_tiered_stocks if s.tier == tier]
    
    def get_by_sector(self, sector: str) -> SectorTieringResult | None:
        """Get tiering result for a specific sector."""
        for s in self.sectors:
            if s.sector == sector:
                return s
        return None


class StockTieringAnalyzer:
    """Analyzer for stock tiering classification."""
    
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
    
    def analyze(
        self,
        codes: list[str] | None = None,
        target_date: date | None = None,
        lookback_days: int = 20,
    ) -> StockTieringResult:
        """Analyze and tier stocks.
        
        Args:
            codes: List of stock codes to analyze. If None, analyze all.
            target_date: Analysis date. If None, use latest available.
            lookback_days: Days to look back for metrics calculation.
            
        Returns:
            StockTieringResult with tiering classification.
        """
        if target_date is None:
            target_date = date.today()
        elif isinstance(target_date, str):
            target_date = date.fromisoformat(target_date)
            
        start_date = target_date - timedelta(days=lookback_days * 2)
        
        # Get stock data
        metrics_list = self._calculate_metrics(
            codes=codes,
            start_date=start_date,
            end_date=target_date,
            lookback_days=lookback_days,
        )
        
        # Classify by sector and tier
        sector_groups: dict[str, list[StockTierMetrics]] = {}
        for m in metrics_list:
            sector = m.sector or "未知"
            if sector not in sector_groups:
                sector_groups[sector] = []
            sector_groups[sector].append(m)
        
        # Tier each sector
        sectors_result: list[SectorTieringResult] = []
        all_tiered: list[TieredStock] = []
        
        for sector, sector_metrics in sector_groups.items():
            sector_result = self._tier_sector(sector, sector_metrics)
            sectors_result.append(sector_result)
            all_tiered.extend(sector_result.leaders)
            all_tiered.extend(sector_result.cores)
            all_tiered.extend(sector_result.followers)
        
        return StockTieringResult(
            target_date=target_date,
            lookback_days=lookback_days,
            sectors=sectors_result,
            all_tiered_stocks=all_tiered,
        )
    
    def _calculate_metrics(
        self,
        codes: list[str] | None,
        start_date: date,
        end_date: date,
        lookback_days: int,
    ) -> list[StockTierMetrics]:
        """Calculate metrics for all stocks."""
        metrics_list: list[StockTierMetrics] = []
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            # Get stock basic info
            stock_query = "SELECT code, name, sector_lv1 AS sector FROM stocks"
            if codes:
                placeholders = ",".join("?" * len(codes))
                stock_query += f" WHERE code IN ({placeholders})"
                stock_rows = conn.execute(stock_query, codes).fetchall()
            else:
                stock_rows = conn.execute(stock_query).fetchall()
            
            for row in stock_rows:
                code = row["code"]
                name = row["name"]
                sector = row["sector"]
                
                metrics = self._calculate_single_stock_metrics(
                    conn, code, name, sector, start_date, end_date, lookback_days
                )
                if metrics:
                    metrics_list.append(metrics)
        
        return metrics_list
    
    def _calculate_single_stock_metrics(
        self,
        conn: sqlite3.Connection,
        code: str,
        name: str,
        sector: str | None,
        start_date: date,
        end_date: date,
        lookback_days: int,
    ) -> StockTierMetrics | None:
        """Calculate metrics for a single stock."""
        # Get price data
        rows = conn.execute(
            """SELECT trade_date AS date, close, volume, amount, high, low 
               FROM daily_prices 
               WHERE code = ? AND trade_date BETWEEN ? AND ?
               ORDER BY trade_date DESC
               LIMIT ?""",
            (code, start_date.isoformat(), end_date.isoformat(), lookback_days + 5)
        ).fetchall()
        
        if len(rows) < lookback_days // 2:  # Need at least half the data
            return None
        
        # Calculate metrics
        closes = [r["close"] for r in rows]
        amounts = [r["amount"] or 0 for r in rows]
        
        if len(closes) < 2 or not amounts:
            return None
        
        avg_amount = sum(amounts[:lookback_days]) / len(amounts[:lookback_days])
        
        # Returns
        return_5d = (closes[0] - closes[min(4, len(closes)-1)]) / closes[min(4, len(closes)-1)] * 100 if len(closes) > 4 else 0
        return_20d = (closes[0] - closes[-1]) / closes[-1] * 100 if len(closes) > 1 else 0
        
        # Volatility
        if len(closes) > 1:
            daily_returns = [(closes[i] - closes[i+1]) / closes[i+1] for i in range(min(19, len(closes)-1))]
            volatility = (sum((r - sum(daily_returns)/len(daily_returns))**2 for r in daily_returns) / len(daily_returns))**0.5 * 100 if daily_returns else 0
        else:
            volatility = 0
        
        metrics = StockTierMetrics(
            code=code,
            name=name,
            sector=sector,
            avg_amount_20d=avg_amount,
            return_5d=return_5d,
            return_20d=return_20d,
            volatility_20d=volatility,
        )
        
        return metrics
    
    def _tier_sector(
        self,
        sector: str,
        metrics_list: list[StockTierMetrics],
    ) -> SectorTieringResult:
        """Tier stocks within a sector."""
        if not metrics_list:
            return SectorTieringResult(sector=sector)
        
        # Sort by average amount (descending) for ranking
        sorted_by_amount = sorted(metrics_list, key=lambda m: m.avg_amount_20d, reverse=True)
        for i, m in enumerate(sorted_by_amount, 1):
            m.amount_rank_in_sector = i
        
        # Calculate sector average for relative strength
        avg_sector_return = sum(m.return_20d for m in metrics_list) / len(metrics_list)
        
        # Calculate leadership score and relative strength
        for m in metrics_list:
            m.rs_vs_sector_20d = m.return_20d - avg_sector_return
            
            # Leadership score components:
            # - Amount rank (top 20% gets high score)
            # - Return (positive return gets score)
            # - Consistency (low volatility bonus)
            
            amount_score = max(0, (len(metrics_list) - m.amount_rank_in_sector + 1) / len(metrics_list) * 40)
            return_score = max(0, min(m.return_20d / 20 * 30, 30)) if m.return_20d > 0 else 0
            consistency_score = max(0, (10 - m.volatility_20d) / 10 * 20) if m.volatility_20d < 10 else 0
            momentum_score = max(0, min(m.return_5d / 5 * 10, 10)) if m.return_5d > 0 else 0
            
            m.leadership_score = amount_score + return_score + consistency_score + momentum_score
        
        # Tier classification rules:
        # - Leader: top 10% by leadership score, must have positive return
        # - Core: next 30% by leadership score
        # - Follower: remaining
        
        sorted_by_score = sorted(metrics_list, key=lambda m: m.leadership_score, reverse=True)
        
        n = len(sorted_by_score)
        leader_count = max(1, n // 10)  # Top 10%
        core_count = max(1, n * 3 // 10)  # Next 30%
        
        leaders: list[TieredStock] = []
        cores: list[TieredStock] = []
        followers: list[TieredStock] = []
        
        for i, m in enumerate(sorted_by_score):
            if i < leader_count and m.return_20d > 0:
                tier = StockTier.LEADER
                confidence = min(100, m.leadership_score)
            elif i < leader_count + core_count:
                tier = StockTier.CORE
                confidence = min(90, m.leadership_score * 0.9)
            else:
                tier = StockTier.FOLLOWER
                confidence = min(80, max(30, m.leadership_score * 0.8))
            
            tiered = TieredStock(
                code=m.code,
                name=m.name,
                sector=m.sector,
                tier=tier,
                metrics=m,
                tier_confidence=confidence,
            )
            
            if tier == StockTier.LEADER:
                leaders.append(tiered)
            elif tier == StockTier.CORE:
                cores.append(tiered)
            else:
                followers.append(tiered)
        
        return SectorTieringResult(
            sector=sector,
            total_stocks=len(metrics_list),
            leaders=leaders,
            cores=cores,
            followers=followers,
        )
