"""Task scheduler for NeoTrade3."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .task_scheduler import NeoTradeScheduler as NeoTradeScheduler

__all__ = ["NeoTradeScheduler"]


def __getattr__(name: str):
    if name == "NeoTradeScheduler":
        from .task_scheduler import NeoTradeScheduler

        return NeoTradeScheduler
    raise AttributeError(name)
