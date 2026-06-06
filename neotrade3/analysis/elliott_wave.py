"""Elliott Wave Theory analysis module for NeoTrade3.

艾略特波浪理论自动识别 - 重点检测 Wave 3/5/B
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import Enum
from typing import Any


class WaveType(str, Enum):
    """Elliott wave types."""
    WAVE_1 = "1"      # 启动浪
    WAVE_2 = "2"      # 回调浪
    WAVE_3 = "3"      # 主升浪 ⭐重点
    WAVE_4 = "4"      # 调整浪
    WAVE_5 = "5"      # 末升浪 ⭐重点
    WAVE_A = "A"      # 调整A浪
    WAVE_B = "B"      # 反弹B浪 ⭐重点
    WAVE_C = "C"      # 调整C浪
    UNKNOWN = "?"


class WaveDirection(str, Enum):
    """Wave direction."""
    UP = "up"
    DOWN = "down"


class WavePosition(str, Enum):
    """Trading position based on wave."""
    IDEAL_ENTRY = "ideal_entry"      # 最佳入场点
    CAUTION_ENTRY = "caution_entry"  # 谨慎入场点
    AVOID = "avoid"                  # 避免交易
    WATCH = "watch"                  # 观察等待


@dataclass
class PivotPoint:
    """A pivot point (swing high/low)."""
    date: date
    price: float
    is_high: bool  # True = swing high, False = swing low
    index: int     # Position in price series


@dataclass
class Wave:
    """A single Elliott wave."""
    wave_type: WaveType
    direction: WaveDirection
    start_date: date
    end_date: date
    start_price: float
    end_price: float
    
    # Fibonacci measurements
    fib_ratio: float = 0.0  # 相对于前浪的比例
    
    # Confidence
    confidence: float = 0.0  # 0-100
    
    # Volume confirmation
    avg_volume: float = 0.0
    volume_trend: str = ""  # "increasing", "decreasing", "flat"
    
    @property
    def price_change(self) -> float:
        """Absolute price change."""
        return self.end_price - self.start_price
    
    @property
    def price_change_pct(self) -> float:
        """Percentage price change."""
        if self.start_price == 0:
            return 0.0
        return (self.price_change / self.start_price) * 100
    
    @property
    def duration_days(self) -> int:
        """Wave duration in days."""
        return (self.end_date - self.start_date).days


@dataclass
class WaveSequence:
    """A sequence of Elliott waves (1-2-3-4-5 or A-B-C)."""
    waves: list[Wave] = field(default_factory=list)
    sequence_type: str = ""  # "impulse", "corrective", "unknown"
    
    # Overall metrics
    start_date: date | None = None
    end_date: date | None = None
    start_price: float = 0.0
    end_price: float = 0.0
    
    # Completion status
    is_complete: bool = False
    expected_next: WaveType = WaveType.UNKNOWN
    
    def add_wave(self, wave: Wave) -> None:
        """Add a wave to the sequence."""
        self.waves.append(wave)
        self._update_metrics()
        self._determine_next_wave()
    
    def _update_metrics(self) -> None:
        """Update sequence metrics."""
        if not self.waves:
            return
        
        self.start_date = self.waves[0].start_date
        self.end_date = self.waves[-1].end_date
        self.start_price = self.waves[0].start_price
        self.end_price = self.waves[-1].end_price
        
        # Determine sequence type
        if len(self.waves) >= 3:
            wave_types = [w.wave_type for w in self.waves[:3]]
            if wave_types == [WaveType.WAVE_1, WaveType.WAVE_2, WaveType.WAVE_3]:
                self.sequence_type = "impulse"
            elif wave_types == [WaveType.WAVE_A, WaveType.WAVE_B, WaveType.WAVE_C]:
                self.sequence_type = "corrective"
    
    def _determine_next_wave(self) -> None:
        """Determine what wave should come next."""
        if not self.waves:
            self.expected_next = WaveType.WAVE_1
            return
        
        last_wave = self.waves[-1].wave_type
        
        next_map = {
            WaveType.WAVE_1: WaveType.WAVE_2,
            WaveType.WAVE_2: WaveType.WAVE_3,
            WaveType.WAVE_3: WaveType.WAVE_4,
            WaveType.WAVE_4: WaveType.WAVE_5,
            WaveType.WAVE_5: WaveType.WAVE_A,
            WaveType.WAVE_A: WaveType.WAVE_B,
            WaveType.WAVE_B: WaveType.WAVE_C,
            WaveType.WAVE_C: WaveType.WAVE_1,  # New cycle
        }
        
        self.expected_next = next_map.get(last_wave, WaveType.UNKNOWN)
        
        # Check if sequence is complete
        if last_wave in [WaveType.WAVE_5, WaveType.WAVE_C]:
            self.is_complete = True


@dataclass
class WaveTradingSignal:
    """Trading signal derived from wave analysis."""
    code: str
    name: str
    signal_date: date
    
    # Wave info
    current_wave: WaveType
    wave_position: WavePosition
    
    # Entry recommendation
    entry_price: float
    stop_loss: float
    take_profit_1: float  # 第一目标位
    take_profit_2: float  # 第二目标位
    
    # Risk metrics
    risk_reward_ratio: float
    confidence: float  # 0-100
    
    # Reasoning
    reason: str
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "code": self.code,
            "name": self.name,
            "signal_date": self.signal_date.isoformat(),
            "current_wave": self.current_wave.value,
            "wave_position": self.wave_position.value,
            "entry_price": round(self.entry_price, 2),
            "stop_loss": round(self.stop_loss, 2),
            "take_profit_1": round(self.take_profit_1, 2),
            "take_profit_2": round(self.take_profit_2, 2),
            "risk_reward_ratio": round(self.risk_reward_ratio, 2),
            "confidence": round(self.confidence, 1),
            "reason": self.reason,
        }


@dataclass
class ElliottWaveResult:
    """Complete Elliott wave analysis result."""
    code: str
    name: str
    analysis_date: date
    
    # Wave structure
    sequence: WaveSequence
    
    # Trading signals
    signals: list[WaveTradingSignal] = field(default_factory=list)
    
    # Current state
    current_price: float = 0.0
    trend_direction: str = ""  # "uptrend", "downtrend", "sideways"
    
    def get_primary_signal(self) -> WaveTradingSignal | None:
        """Get the highest confidence signal."""
        if not self.signals:
            return None
        return max(self.signals, key=lambda s: s.confidence)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "code": self.code,
            "name": self.name,
            "analysis_date": self.analysis_date.isoformat(),
            "current_price": self.current_price,
            "trend_direction": self.trend_direction,
            "wave_sequence": {
                "type": self.sequence.sequence_type,
                "is_complete": self.sequence.is_complete,
                "expected_next": self.sequence.expected_next.value,
                "waves": [
                    {
                        "type": w.wave_type.value,
                        "direction": w.direction.value,
                        "start_date": w.start_date.isoformat(),
                        "end_date": w.end_date.isoformat(),
                        "price_change_pct": round(w.price_change_pct, 2),
                        "duration_days": w.duration_days,
                        "confidence": round(w.confidence, 1),
                    }
                    for w in self.sequence.waves
                ],
            },
            "signals": [s.to_dict() for s in self.signals],
            "primary_signal": self.get_primary_signal().to_dict() if self.get_primary_signal() else None,
        }


class ElliottWaveAnalyzer:
    """Analyzer for Elliott Wave patterns."""
    
    # Fibonacci ratios commonly used in Elliott Wave
    FIB_RATIOS = {
        "0.236": 0.236,
        "0.382": 0.382,
        "0.5": 0.5,
        "0.618": 0.618,
        "0.786": 0.786,
        "1.0": 1.0,
        "1.272": 1.272,
        "1.618": 1.618,
        "2.618": 2.618,
    }
    
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
    
    def analyze(
        self,
        code: str,
        target_date: date | None = None,
        lookback_days: int = 120,
    ) -> ElliottWaveResult | None:
        """Analyze Elliott Wave pattern for a stock.
        
        Args:
            code: Stock code
            target_date: Analysis date (default: today)
            lookback_days: Days to look back for pattern detection
            
        Returns:
            ElliottWaveResult or None if analysis fails
        """
        if target_date is None:
            target_date = date.today()
        elif isinstance(target_date, str):
            target_date = date.fromisoformat(target_date)
        
        start_date = target_date - timedelta(days=lookback_days)
        
        # Get price data
        price_data = self._get_price_data(code, start_date, target_date)
        if not price_data or len(price_data) < 30:
            return None
        
        # Get stock name
        name = self._get_stock_name(code)
        
        # Detect pivot points (swing highs/lows)
        pivots = self._detect_pivots(price_data)
        if len(pivots) < 5:
            return None
        
        # Identify wave sequence
        sequence = self._identify_waves(pivots)
        
        # Create result
        result = ElliottWaveResult(
            code=code,
            name=name,
            analysis_date=target_date,
            sequence=sequence,
            current_price=price_data[-1]["close"],
        )
        
        # Determine trend
        result.trend_direction = self._determine_trend(price_data)
        
        # Generate trading signals
        result.signals = self._generate_signals(result, pivots)
        
        return result
    
    def _get_price_data(
        self,
        code: str,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
        """Get price data from database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT trade_date AS date, open, high, low, close, volume
                FROM daily_prices
                WHERE code = ? AND trade_date BETWEEN ? AND ?
                ORDER BY trade_date ASC
                """,
                (code, start_date.isoformat(), end_date.isoformat()),
            ).fetchall()
            
            return [
                {
                    "date": date.fromisoformat(row["date"]),
                    "open": row["open"],
                    "high": row["high"],
                    "low": row["low"],
                    "close": row["close"],
                    "volume": row["volume"] or 0,
                }
                for row in rows
            ]
    
    def _get_stock_name(self, code: str) -> str:
        """Get stock name from database."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT name FROM stocks WHERE code = ?",
                (code,),
            ).fetchone()
            return row[0] if row else ""
    
    def _detect_pivots(
        self,
        price_data: list[dict[str, Any]],
        window: int = 5,
    ) -> list[PivotPoint]:
        """Detect swing highs and lows (pivot points)."""
        pivots: list[PivotPoint] = []
        
        for i in range(window, len(price_data) - window):
            current = price_data[i]
            prev_prices = [price_data[j]["high"] for j in range(i - window, i)]
            next_prices = [price_data[j]["high"] for j in range(i + 1, i + window + 1)]
            
            # Check for swing high
            if current["high"] > max(prev_prices) and current["high"] > max(next_prices):
                pivots.append(PivotPoint(
                    date=current["date"],
                    price=current["high"],
                    is_high=True,
                    index=i,
                ))
                continue
            
            # Check for swing low
            prev_prices = [price_data[j]["low"] for j in range(i - window, i)]
            next_prices = [price_data[j]["low"] for j in range(i + 1, i + window + 1)]
            
            if current["low"] < min(prev_prices) and current["low"] < min(next_prices):
                pivots.append(PivotPoint(
                    date=current["date"],
                    price=current["low"],
                    is_high=False,
                    index=i,
                ))
        
        return pivots
    
    def _identify_waves(self, pivots: list[PivotPoint]) -> WaveSequence:
        """Identify Elliott Wave sequence from pivot points."""
        sequence = WaveSequence()
        
        if len(pivots) < 5:
            return sequence
        
        # Simple wave identification logic
        # In a real implementation, this would be more sophisticated
        
        # Look for 5-wave impulse pattern
        # Wave 1: Low -> High
        # Wave 2: High -> Low (retrace ~38-62% of Wave 1)
        # Wave 3: Low -> High (longer than Wave 1)
        # Wave 4: High -> Low (retrace ~38-50% of Wave 3)
        # Wave 5: Low -> High (shorter than Wave 3)
        
        i = 0
        while i < len(pivots) - 4:
            # Try to identify Wave 1 start
            if not pivots[i].is_high:  # Start from a low
                wave1 = self._try_identify_wave1(pivots, i)
                if wave1:
                    sequence.add_wave(wave1)
                    
                    wave2 = self._try_identify_wave2(pivots, wave1)
                    if wave2:
                        sequence.add_wave(wave2)
                        
                        wave3 = self._try_identify_wave3(pivots, wave1, wave2)
                        if wave3:
                            sequence.add_wave(wave3)
                            
                            wave4 = self._try_identify_wave4(pivots, wave3)
                            if wave4:
                                sequence.add_wave(wave4)
                                
                                wave5 = self._try_identify_wave5(pivots, wave3, wave4)
                                if wave5:
                                    sequence.add_wave(wave5)
                                    break
            i += 1
        
        return sequence
    
    def _try_identify_wave1(
        self,
        pivots: list[PivotPoint],
        start_idx: int,
    ) -> Wave | None:
        """Try to identify Wave 1 (Low -> High)."""
        if start_idx >= len(pivots) - 1:
            return None
        
        start = pivots[start_idx]
        
        # Find next high
        for i in range(start_idx + 1, len(pivots)):
            if pivots[i].is_high:
                end = pivots[i]
                
                # Wave 1 should be a significant move
                price_change = (end.price - start.price) / start.price
                if price_change > 0.05:  # At least 5% move
                    return Wave(
                        wave_type=WaveType.WAVE_1,
                        direction=WaveDirection.UP,
                        start_date=start.date,
                        end_date=end.date,
                        start_price=start.price,
                        end_price=end.price,
                        confidence=60.0,
                    )
                break
        
        return None
    
    def _try_identify_wave2(
        self,
        pivots: list[PivotPoint],
        wave1: Wave,
    ) -> Wave | None:
        """Try to identify Wave 2 (High -> Low, retrace Wave 1)."""
        # Find pivot after Wave 1 end
        wave1_end_idx = None
        for i, p in enumerate(pivots):
            if p.date == wave1.end_date and p.price == wave1.end_price:
                wave1_end_idx = i
                break
        
        if wave1_end_idx is None or wave1_end_idx >= len(pivots) - 1:
            return None
        
        # Find next low
        for i in range(wave1_end_idx + 1, len(pivots)):
            if not pivots[i].is_high:  # It's a low
                end = pivots[i]
                
                # Calculate retrace ratio
                wave1_range = wave1.end_price - wave1.start_price
                retrace = wave1.end_price - end.price
                retrace_ratio = retrace / wave1_range if wave1_range > 0 else 0
                
                # Wave 2 typically retraces 38.2% - 61.8% of Wave 1
                if 0.382 <= retrace_ratio <= 0.786:
                    return Wave(
                        wave_type=WaveType.WAVE_2,
                        direction=WaveDirection.DOWN,
                        start_date=wave1.end_date,
                        end_date=end.date,
                        start_price=wave1.end_price,
                        end_price=end.price,
                        fib_ratio=retrace_ratio,
                        confidence=70.0 if 0.5 <= retrace_ratio <= 0.618 else 50.0,
                    )
                break
        
        return None
    
    def _try_identify_wave3(
        self,
        pivots: list[PivotPoint],
        wave1: Wave,
        wave2: Wave,
    ) -> Wave | None:
        """Try to identify Wave 3 (Low -> High, longest wave)."""
        # Find pivot after Wave 2 end
        wave2_end_idx = None
        for i, p in enumerate(pivots):
            if p.date == wave2.end_date and p.price == wave2.end_price:
                wave2_end_idx = i
                break
        
        if wave2_end_idx is None or wave2_end_idx >= len(pivots) - 1:
            return None
        
        # Find next high
        for i in range(wave2_end_idx + 1, len(pivots)):
            if pivots[i].is_high:
                end = pivots[i]
                
                wave3_range = end.price - wave2.end_price
                wave1_range = wave1.end_price - wave1.start_price
                
                # Wave 3 should be longer than Wave 1 (typically 1.618x)
                if wave3_range > wave1_range:
                    extension_ratio = wave3_range / wave1_range if wave1_range > 0 else 0
                    
                    return Wave(
                        wave_type=WaveType.WAVE_3,
                        direction=WaveDirection.UP,
                        start_date=wave2.end_date,
                        end_date=end.date,
                        start_price=wave2.end_price,
                        end_price=end.price,
                        fib_ratio=extension_ratio,
                        confidence=80.0 if extension_ratio >= 1.618 else 65.0,
                    )
                break
        
        return None
    
    def _try_identify_wave4(
        self,
        pivots: list[PivotPoint],
        wave3: Wave,
    ) -> Wave | None:
        """Try to identify Wave 4 (High -> Low, retrace Wave 3)."""
        wave3_end_idx = None
        for i, p in enumerate(pivots):
            if p.date == wave3.end_date and p.price == wave3.end_price:
                wave3_end_idx = i
                break
        
        if wave3_end_idx is None or wave3_end_idx >= len(pivots) - 1:
            return None
        
        for i in range(wave3_end_idx + 1, len(pivots)):
            if not pivots[i].is_high:
                end = pivots[i]
                
                wave3_range = wave3.end_price - wave3.start_price
                retrace = wave3.end_price - end.price
                retrace_ratio = retrace / wave3_range if wave3_range > 0 else 0
                
                # Wave 4 typically retraces 38.2% - 50% of Wave 3
                if 0.25 <= retrace_ratio <= 0.5:
                    return Wave(
                        wave_type=WaveType.WAVE_4,
                        direction=WaveDirection.DOWN,
                        start_date=wave3.end_date,
                        end_date=end.date,
                        start_price=wave3.end_price,
                        end_price=end.price,
                        fib_ratio=retrace_ratio,
                        confidence=65.0,
                    )
                break
        
        return None
    
    def _try_identify_wave5(
        self,
        pivots: list[PivotPoint],
        wave3: Wave,
        wave4: Wave,
    ) -> Wave | None:
        """Try to identify Wave 5 (Low -> High, shorter than Wave 3)."""
        wave4_end_idx = None
        for i, p in enumerate(pivots):
            if p.date == wave4.end_date and p.price == wave4.end_price:
                wave4_end_idx = i
                break
        
        if wave4_end_idx is None or wave4_end_idx >= len(pivots) - 1:
            return None
        
        for i in range(wave4_end_idx + 1, len(pivots)):
            if pivots[i].is_high:
                end = pivots[i]
                
                wave5_range = end.price - wave4.end_price
                wave3_range = wave3.end_price - wave3.start_price
                wave1_range = wave3.start_price - wave4.start_price  # Approximate
                
                # Wave 5 should be shorter than Wave 3
                # And often equals Wave 1 or is 0.618 of Wave 1-3
                if wave5_range < wave3_range and wave5_range > 0:
                    ratio_to_wave1 = wave5_range / wave1_range if wave1_range > 0 else 0
                    
                    return Wave(
                        wave_type=WaveType.WAVE_5,
                        direction=WaveDirection.UP,
                        start_date=wave4.end_date,
                        end_date=end.date,
                        start_price=wave4.end_price,
                        end_price=end.price,
                        fib_ratio=ratio_to_wave1,
                        confidence=70.0 if 0.5 <= ratio_to_wave1 <= 1.0 else 55.0,
                    )
                break
        
        return None
    
    def _determine_trend(self, price_data: list[dict[str, Any]]) -> str:
        """Determine overall trend direction."""
        if len(price_data) < 20:
            return "unknown"
        
        # Simple moving average comparison
        recent = [d["close"] for d in price_data[-20:]]
        older = [d["close"] for d in price_data[-60:-40]] if len(price_data) >= 60 else recent
        
        recent_avg = sum(recent) / len(recent)
        older_avg = sum(older) / len(older)
        
        change_pct = (recent_avg - older_avg) / older_avg * 100 if older_avg > 0 else 0
        
        if change_pct > 5:
            return "uptrend"
        elif change_pct < -5:
            return "downtrend"
        else:
            return "sideways"
    
    def _generate_signals(
        self,
        result: ElliottWaveResult,
        pivots: list[PivotPoint],
    ) -> list[WaveTradingSignal]:
        """Generate trading signals based on wave analysis."""
        signals: list[WaveTradingSignal] = []
        
        if not result.sequence.waves:
            return signals
        
        current_wave = result.sequence.waves[-1]
        
        # Wave 3 detection - IDEAL ENTRY
        if current_wave.wave_type == WaveType.WAVE_2:
            # We're at the end of Wave 2, Wave 3 should start
            signal = self._create_wave3_entry_signal(result, current_wave)
            if signal:
                signals.append(signal)
        
        # Wave 5 detection - CAUTION ENTRY
        elif current_wave.wave_type == WaveType.WAVE_4:
            signal = self._create_wave5_entry_signal(result, current_wave)
            if signal:
                signals.append(signal)
        
        # Wave B detection - SHORT TERM
        elif current_wave.wave_type == WaveType.WAVE_A:
            signal = self._create_waveb_entry_signal(result, current_wave)
            if signal:
                signals.append(signal)
        
        return signals
    
    def _create_wave3_entry_signal(
        self,
        result: ElliottWaveResult,
        wave2: Wave,
    ) -> WaveTradingSignal | None:
        """Create entry signal for Wave 3."""
        entry_price = result.current_price
        
        # Stop loss below Wave 2 low
        stop_loss = wave2.end_price * 0.98
        
        # Target: 1.618x Wave 1 projection
        wave1 = result.sequence.waves[0] if result.sequence.waves else None
        if wave1:
            wave1_range = wave1.end_price - wave1.start_price
            take_profit_1 = wave2.end_price + wave1_range * 1.0
            take_profit_2 = wave2.end_price + wave1_range * 1.618
        else:
            take_profit_1 = entry_price * 1.15
            take_profit_2 = entry_price * 1.25
        
        risk = entry_price - stop_loss
        reward = take_profit_1 - entry_price
        risk_reward = reward / risk if risk > 0 else 0
        
        return WaveTradingSignal(
            code=result.code,
            name=result.name,
            signal_date=result.analysis_date,
            current_wave=WaveType.WAVE_3,
            wave_position=WavePosition.IDEAL_ENTRY,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit_1=take_profit_1,
            take_profit_2=take_profit_2,
            risk_reward_ratio=risk_reward,
            confidence=80.0,
            reason="Wave 3 主升浪入场点 - 趋势最强波段，盈亏比优秀",
        )
    
    def _create_wave5_entry_signal(
        self,
        result: ElliottWaveResult,
        wave4: Wave,
    ) -> WaveTradingSignal | None:
        """Create entry signal for Wave 5."""
        entry_price = result.current_price
        
        # Stop loss below Wave 4 low
        stop_loss = wave4.end_price * 0.99
        
        # Target: equal to Wave 1 or 0.618 of Waves 1-3
        take_profit_1 = entry_price * 1.08
        take_profit_2 = entry_price * 1.15
        
        risk = entry_price - stop_loss
        reward = take_profit_1 - entry_price
        risk_reward = reward / risk if risk > 0 else 0
        
        return WaveTradingSignal(
            code=result.code,
            name=result.name,
            signal_date=result.analysis_date,
            current_wave=WaveType.WAVE_5,
            wave_position=WavePosition.CAUTION_ENTRY,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit_1=take_profit_1,
            take_profit_2=take_profit_2,
            risk_reward_ratio=risk_reward,
            confidence=65.0,
            reason="Wave 5 末升浪入场点 - 趋势尾声，谨慎参与，设置严格止损",
        )
    
    def _create_waveb_entry_signal(
        self,
        result: ElliottWaveResult,
        wave_a: Wave,
    ) -> WaveTradingSignal | None:
        """Create entry signal for Wave B (counter-trend)."""
        entry_price = result.current_price
        
        # Tight stop for counter-trend
        stop_loss = entry_price * 0.97
        
        # Limited upside for B wave
        take_profit_1 = entry_price * 1.05
        take_profit_2 = entry_price * 1.08
        
        risk = entry_price - stop_loss
        reward = take_profit_1 - entry_price
        risk_reward = reward / risk if risk > 0 else 0
        
        return WaveTradingSignal(
            code=result.code,
            name=result.name,
            signal_date=result.analysis_date,
            current_wave=WaveType.WAVE_B,
            wave_position=WavePosition.CAUTION_ENTRY,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit_1=take_profit_1,
            take_profit_2=take_profit_2,
            risk_reward_ratio=risk_reward,
            confidence=55.0,
            reason="Wave B 反弹浪 - 逆势操作，快进快出，仓位要轻",
        )
