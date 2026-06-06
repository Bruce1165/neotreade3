"""Core models for the NeoTrade3 data control bootstrap."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum


class DataControlStage(str, Enum):
    """Documented stages for the daily data control chain."""

    CAPTURE = "capture"
    COMPOSE = "compose"
    PUBLISH = "publish"


@dataclass
class DataControlStepDefinition:
    """Minimal step definition for the data control bootstrap."""

    stage: DataControlStage
    entrypoint: str
    description: str
    writes_to_official_store: bool = False


@dataclass
class DataControlPlan:
    """Planning result for a single target date."""

    target_date: date
    steps: list[DataControlStepDefinition] = field(default_factory=list)


@dataclass
class DataControlStepResult:
    """Bootstrap result returned by placeholder stage methods."""

    stage: DataControlStage
    status: str
    message: str
