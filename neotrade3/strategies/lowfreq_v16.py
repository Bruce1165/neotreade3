from __future__ import annotations

from dataclasses import fields
from typing import Any

from lowfreq_engine_v16_advanced import ExecutionConstraints
from lowfreq_engine_v16_advanced import LowFreqTradingEngineV16
from lowfreq_engine_v16_advanced import LowFreqV16Config
from lowfreq_engine_v16_advanced import TradeCostModel

from neotrade3.strategy_config import StrategyConfig


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_float(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _convert_value(*, expected_type: type, value: object, key: str) -> object:
    if expected_type is int:
        if not _is_int(value):
            raise ValueError(f"invalid type for {key}: expected int")
        return int(value)
    if expected_type is float:
        if not _is_float(value):
            raise ValueError(f"invalid type for {key}: expected float")
        return float(value)
    if expected_type is bool:
        if not isinstance(value, bool):
            raise ValueError(f"invalid type for {key}: expected bool")
        return bool(value)
    if expected_type is str:
        if not isinstance(value, str):
            raise ValueError(f"invalid type for {key}: expected str")
        return str(value)
    raise ValueError(f"unsupported field type for {key}: {expected_type}")


def _field_type_map(cls: type) -> dict[str, type]:
    out: dict[str, type] = {}
    for f in fields(cls):
        if isinstance(f.type, type):
            out[str(f.name)] = f.type
    return out


_LOWFREQ_V16_ALLOWED_TOP_LEVEL_KEYS = {
    name
    for name in _field_type_map(LowFreqV16Config).keys()
    if name not in {"version", "cost_model", "execution"}
}
_LOWFREQ_V16_TOP_LEVEL_TYPES = _field_type_map(LowFreqV16Config)
_LOWFREQ_V16_COST_MODEL_TYPES = _field_type_map(TradeCostModel)
_LOWFREQ_V16_EXECUTION_TYPES = _field_type_map(ExecutionConstraints)
_LOWFREQ_V16_ENGINE_DIRECT_TYPES: dict[str, type] = {
    "RELATIVE_STRENGTH_BONUS_CAP": float,
    "ROTATION_MIN_RETURN_PCT": float,
    "ROTATION_SCORE_DELTA": float,
    "SECTOR_ACCEL_BONUS_ENABLED": bool,
}
_LOWFREQ_V16_ALLOWED_TOP_LEVEL_KEYS = _LOWFREQ_V16_ALLOWED_TOP_LEVEL_KEYS | set(
    _LOWFREQ_V16_ENGINE_DIRECT_TYPES.keys()
)


def build_lowfreq_v16_config_from_strategy(*, strategy: StrategyConfig) -> LowFreqV16Config:
    if strategy.strategy_id != "lowfreq_v16":
        raise ValueError("strategy_id must be lowfreq_v16")
    parameters = strategy.parameters or {}
    if not isinstance(parameters, dict):
        raise ValueError("strategy.parameters must be a JSON object")

    raw_cost_model = parameters.get("cost_model")
    raw_execution = parameters.get("execution")

    unknown_top_level = sorted(
        set(parameters.keys())
        - _LOWFREQ_V16_ALLOWED_TOP_LEVEL_KEYS
        - {"cost_model", "execution"}
    )
    if unknown_top_level:
        raise ValueError(f"unknown lowfreq_v16 parameters: {', '.join(unknown_top_level)}")

    config = LowFreqV16Config()

    for key, raw_value in parameters.items():
        if key in {"cost_model", "execution"}:
            continue
        if key not in _LOWFREQ_V16_ALLOWED_TOP_LEVEL_KEYS:
            raise ValueError(f"unknown lowfreq_v16 parameter: {key}")
        expected_type = _LOWFREQ_V16_TOP_LEVEL_TYPES.get(key) or _LOWFREQ_V16_ENGINE_DIRECT_TYPES.get(
            key
        )
        if expected_type is None:
            raise ValueError(f"unknown lowfreq_v16 parameter: {key}")
        converted = _convert_value(expected_type=expected_type, value=raw_value, key=key)
        setattr(config, key, converted)

    if raw_cost_model is not None:
        if not isinstance(raw_cost_model, dict):
            raise ValueError("cost_model must be a JSON object")
        unknown_cost_model = sorted(set(raw_cost_model.keys()) - set(_LOWFREQ_V16_COST_MODEL_TYPES.keys()))
        if unknown_cost_model:
            raise ValueError(f"unknown cost_model parameters: {', '.join(unknown_cost_model)}")
        cm = TradeCostModel()
        for key, raw_value in raw_cost_model.items():
            expected_type = _LOWFREQ_V16_COST_MODEL_TYPES[key]
            converted = _convert_value(
                expected_type=expected_type, value=raw_value, key=f"cost_model.{key}"
            )
            setattr(cm, key, converted)
        config.cost_model = cm

    if raw_execution is not None:
        if not isinstance(raw_execution, dict):
            raise ValueError("execution must be a JSON object")
        unknown_execution = sorted(set(raw_execution.keys()) - set(_LOWFREQ_V16_EXECUTION_TYPES.keys()))
        if unknown_execution:
            raise ValueError(f"unknown execution parameters: {', '.join(unknown_execution)}")
        ex = ExecutionConstraints()
        for key, raw_value in raw_execution.items():
            expected_type = _LOWFREQ_V16_EXECUTION_TYPES[key]
            converted = _convert_value(
                expected_type=expected_type, value=raw_value, key=f"execution.{key}"
            )
            setattr(ex, key, converted)
        config.execution = ex

    return config


def apply_lowfreq_v16_strategy_config(
    *, engine: LowFreqTradingEngineV16, strategy: StrategyConfig
) -> None:
    config = build_lowfreq_v16_config_from_strategy(strategy=strategy)
    engine.config = config
    engine._apply_config(config)
