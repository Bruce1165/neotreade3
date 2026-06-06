"""External data source adapters for NeoTrade3."""

from .cninfo_adapter import Announcement, CninfoAdapter
from .eastmoney_concept_adapter import (
    ConceptSector,
    ConceptStock,
    EastmoneyConceptAdapter,
)
from .eastmoney_guba_adapter import EastmoneyGubaAdapter, GubaPost
from .mootdx_adapter import FinancialRecord, MootdxAdapter

try:
    from .cls_adapter import ClsNewsAdapter
except Exception:
    ClsNewsAdapter = None

__all__ = [
    "MootdxAdapter",
    "FinancialRecord",
    "CninfoAdapter",
    "Announcement",
    "EastmoneyConceptAdapter",
    "ConceptSector",
    "ConceptStock",
    "EastmoneyGubaAdapter",
    "GubaPost",
]

if ClsNewsAdapter is not None:
    __all__.insert(0, "ClsNewsAdapter")
