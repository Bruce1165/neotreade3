from __future__ import annotations

from pathlib import Path

import pytest

from lowfreq_engine_v16_advanced import LowFreqTradingEngineV16

from neotrade3.strategies.lowfreq_v16 import apply_lowfreq_v16_strategy_config
from neotrade3.strategies.lowfreq_v16 import build_lowfreq_v16_config_from_strategy
from neotrade3.strategy_config import StrategyConfig


def test_build_lowfreq_v16_config_from_strategy_maps_top_level_and_nested_parameters() -> None:
    strategy = StrategyConfig(
        strategy_id="lowfreq_v16",
        version=1,
        description="test",
        parameters={
            "BUY_THRESHOLD": 90.0,
            "MAX_POSITIONS": 2,
            "NO_LOOKAHEAD_ENFORCED": True,
            "cost_model": {"commission_rate": 0.0003, "slippage_bps": 5.0},
            "execution": {"lot_size": 100, "block_on_limit_up": True},
        },
    )

    config = build_lowfreq_v16_config_from_strategy(strategy=strategy)

    assert config.BUY_THRESHOLD == 90.0
    assert config.MAX_POSITIONS == 2
    assert config.NO_LOOKAHEAD_ENFORCED is True
    assert config.cost_model.commission_rate == 0.0003
    assert config.cost_model.slippage_bps == 5.0
    assert config.execution.lot_size == 100
    assert config.execution.block_on_limit_up is True


def test_apply_lowfreq_v16_strategy_config_applies_to_engine(tmp_path: Path) -> None:
    strategy = StrategyConfig(
        strategy_id="lowfreq_v16",
        version=1,
        description="test",
        parameters={
            "BUY_THRESHOLD": 91.0,
            "MAX_POSITIONS": 1,
            "cost_model": {"commission_rate": 0.0002},
        },
    )
    engine = LowFreqTradingEngineV16(db_path=tmp_path / "stock.db")

    apply_lowfreq_v16_strategy_config(engine=engine, strategy=strategy)

    assert float(getattr(engine, "BUY_THRESHOLD")) == 91.0
    assert int(getattr(engine, "MAX_POSITIONS")) == 1
    assert float(getattr(engine, "COMMISSION_RATE")) == 0.0002


def test_build_lowfreq_v16_config_from_strategy_fails_closed_on_wrong_strategy_id() -> None:
    strategy = StrategyConfig(
        strategy_id="other",
        version=1,
        description="test",
        parameters={},
    )
    with pytest.raises(ValueError):
        build_lowfreq_v16_config_from_strategy(strategy=strategy)


def test_build_lowfreq_v16_config_from_strategy_fails_closed_on_unknown_key() -> None:
    strategy = StrategyConfig(
        strategy_id="lowfreq_v16",
        version=1,
        description="test",
        parameters={"UNKNOWN_KEY": 1},
    )
    with pytest.raises(ValueError):
        build_lowfreq_v16_config_from_strategy(strategy=strategy)


def test_build_lowfreq_v16_config_from_strategy_fails_closed_on_type_mismatch() -> None:
    strategy = StrategyConfig(
        strategy_id="lowfreq_v16",
        version=1,
        description="test",
        parameters={"MAX_POSITIONS": "2"},
    )
    with pytest.raises(ValueError):
        build_lowfreq_v16_config_from_strategy(strategy=strategy)


def test_build_lowfreq_v16_config_from_strategy_fails_closed_on_bool_as_int() -> None:
    strategy = StrategyConfig(
        strategy_id="lowfreq_v16",
        version=1,
        description="test",
        parameters={"MAX_POSITIONS": True},
    )
    with pytest.raises(ValueError):
        build_lowfreq_v16_config_from_strategy(strategy=strategy)


def test_build_lowfreq_v16_config_from_strategy_fails_closed_on_unknown_nested_key() -> None:
    strategy = StrategyConfig(
        strategy_id="lowfreq_v16",
        version=1,
        description="test",
        parameters={"cost_model": {"unknown": 1.0}},
    )
    with pytest.raises(ValueError):
        build_lowfreq_v16_config_from_strategy(strategy=strategy)
