"""Lab registry exports for NeoTrade3 bootstrap."""

from .registry import (
    LabArtifactContract,
    LabHealthCheck,
    LabJobContract,
    LabRegistration,
    LabRegistry,
)
from .runtime import LabRuntimeAdapter

__all__ = [
    "LabArtifactContract",
    "LabHealthCheck",
    "LabJobContract",
    "LabRegistration",
    "LabRegistry",
    "LabRuntimeAdapter",
]
