"""East Money (东方财富) concept/sector adapter."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

import requests

logger = logging.getLogger(__name__)

_API = "https://push2.eastmoney.com/api/qt/clist/get"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Referer": "https://data.eastmoney.com/",
}
_TIMEOUT = 15
_MAX_RETRIES = 3
_RETRY_DELAY = 1.0  # seconds between retries
_MIN_INTERVAL = 0.5  # minimum seconds between requests (rate limit)


@dataclass(frozen=True)
class ConceptStock:
    """A stock belonging to a concept sector."""
    code: str
    name: str
    price: float
    change_pct: float


@dataclass(frozen=True)
class ConceptSector:
    """A concept/sector from East Money."""
    code: str
    name: str
    change_pct: float
    stock_count: int
    top_stocks: list[ConceptStock] = field(default_factory=list)


class EastmoneyConceptAdapter:
    """Adapter for fetching concept sectors from East Money (东方财富)."""

    def __init__(self, timeout: int = _TIMEOUT, headers: dict[str, str] | None = None) -> None:
        self._timeout = timeout
        self._headers = headers or _HEADERS
        self._last_request_time: float = 0
        self._errors: list[str] = []

    @property
    def errors(self) -> list[str]:
        return list(self._errors)

    def _get(self, params: dict) -> dict:
        # Rate limit: wait if last request was too recent
        elapsed = time.time() - self._last_request_time
        if elapsed < _MIN_INTERVAL:
            time.sleep(_MIN_INTERVAL - elapsed)

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                resp = requests.get(_API, params=params, headers=self._headers, timeout=self._timeout)
                self._last_request_time = time.time()
                resp.raise_for_status()
                return resp.json()
            except requests.Timeout:
                self._errors.append(f"timeout attempt={attempt}/{_MAX_RETRIES}")
                logger.warning("请求东方财富接口超时 (attempt %d/%d)", attempt, _MAX_RETRIES)
                if attempt < _MAX_RETRIES:
                    time.sleep(_RETRY_DELAY * attempt)
            except requests.RequestException as exc:
                self._errors.append(f"request_error attempt={attempt}/{_MAX_RETRIES}: {exc}")
                logger.error("请求东方财富接口失败 (attempt %d/%d): %s", attempt, _MAX_RETRIES, exc)
                if attempt < _MAX_RETRIES:
                    time.sleep(_RETRY_DELAY * attempt)
        return {}

    def fetch_hot_concepts(self, limit: int = 20) -> list[ConceptSector]:
        """Fetch top concept sectors sorted by change percentage."""
        params = {
            "pn": "1", "pz": str(limit), "po": "1", "np": "1",
            "fltt": "2", "invt": "2", "fid": "f3",
            "fs": "m:90+t:3", "fields": "f2,f3,f4,f12,f14",
        }
        data = self._get(params)
        return self._parse_concepts(data)

    def fetch_all_concepts(self, *, page_size: int = 200, max_pages: int = 50) -> list[ConceptSector]:
        sectors: list[ConceptSector] = []
        total: int | None = None
        for pn in range(1, int(max_pages) + 1):
            params = {
                "pn": str(pn),
                "pz": str(int(page_size)),
                "po": "1",
                "np": "1",
                "fltt": "2",
                "invt": "2",
                "fid": "f12",
                "fs": "m:90+t:3",
                "fields": "f2,f3,f4,f12,f14",
            }
            data = self._get(params)
            if total is None:
                try:
                    total_raw = (data.get("data") or {}).get("total")
                except Exception:
                    total_raw = None
                try:
                    total = int(total_raw) if total_raw is not None else None
                except Exception:
                    total = None
            page_items = self._parse_concepts(data)
            if not page_items:
                break
            sectors.extend(page_items)
            if total is not None and len(sectors) >= total:
                break
        uniq: dict[str, ConceptSector] = {}
        for s in sectors:
            if s.code and s.code not in uniq:
                uniq[s.code] = s
        return list(uniq.values())

    def fetch_concept_stocks(self, concept_code: str, limit: int = 50) -> list[ConceptStock]:
        """Fetch stocks belonging to a concept sector."""
        params = {
            "pn": "1", "pz": str(limit), "po": "1", "np": "1",
            "fltt": "2", "invt": "2", "fid": "f3",
            "fs": f"b:{concept_code}+f:!50", "fields": "f2,f3,f4,f12,f14",
        }
        data = self._get(params)
        return self._parse_stocks(data)

    @staticmethod
    def _parse_concepts(data: dict) -> list[ConceptSector]:
        """Parse concept list response."""
        sectors: list[ConceptSector] = []
        diff = (data.get("data") or {}).get("diff")
        if not diff or not isinstance(diff, list):
            logger.warning("东方财富概念板块返回数据格式异常")
            return sectors
        for item in diff:
            try:
                sectors.append(ConceptSector(
                    code=str(item.get("f12", "")), name=item.get("f14", ""),
                    change_pct=float(item.get("f3", 0)), stock_count=int(item.get("f2", 0)),
                ))
            except Exception as exc:
                logger.debug("解析单条概念板块失败: %s", exc)
        logger.info("东方财富概念板块: 共解析 %d 个板块", len(sectors))
        return sectors

    @staticmethod
    def _parse_stocks(data: dict) -> list[ConceptStock]:
        """Parse stock list response."""
        stocks: list[ConceptStock] = []
        diff = (data.get("data") or {}).get("diff")
        if not diff or not isinstance(diff, list):
            logger.warning("东方财富成分股返回数据格式异常")
            return stocks
        for item in diff:
            try:
                stocks.append(ConceptStock(
                    code=str(item.get("f12", "")), name=item.get("f14", ""),
                    price=float(item.get("f2", 0)), change_pct=float(item.get("f3", 0)),
                ))
            except Exception as exc:
                logger.debug("解析单条成分股失败: %s", exc)
        logger.info("东方财富成分股: 共解析 %d 只股票", len(stocks))
        return stocks
