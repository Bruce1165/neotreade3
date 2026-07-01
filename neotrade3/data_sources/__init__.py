"""External data source adapters for NeoTrade3."""

from .cninfo_adapter import Announcement, CninfoAdapter
from .mootdx_adapter import FinancialRecord, MootdxAdapter
from .tushare_market_adapter import TushareMarketAdapter

try:
    from .cls_adapter import ClsNewsAdapter
except Exception:
    ClsNewsAdapter = None

__all__ = [
    "MootdxAdapter",
    "FinancialRecord",
    "TushareMarketAdapter",
    "CninfoAdapter",
    "Announcement",
]

if ClsNewsAdapter is not None:
    __all__.insert(0, "ClsNewsAdapter")
