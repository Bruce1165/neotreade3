"""Cailianpress (财联社) telegraph/news adapter for fetching financial news."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime

import requests

logger = logging.getLogger(__name__)

_API_URL = "https://www.cls.cn/nodeapi/telegraphList"
_DEFAULT_HEADERS = {
    "Referer": "https://www.cls.cn/telegraph",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
}
_TIMEOUT = 15  # seconds


@dataclass(frozen=True)
class NewsItem:
    """A single news item from Cailianpress telegraph."""

    id: str
    title: str
    content: str
    ctime: datetime
    subjects: list[str] = field(default_factory=list)
    stock_codes: list[str] = field(default_factory=list)


class ClsNewsAdapter:
    """Adapter for fetching financial news from Cailianpress (财联社).

    Usage:
        adapter = ClsNewsAdapter()
        news = adapter.fetch_telegraph(limit=10)
        for item in news:
            print(f"[{item.ctime}] {item.title or item.content[:50]}")
    """

    def __init__(
        self,
        timeout: int = _TIMEOUT,
        headers: dict[str, str] | None = None,
    ) -> None:
        self._timeout = timeout
        self._headers = headers or _DEFAULT_HEADERS

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch_telegraph(self, limit: int = 20) -> list[NewsItem]:
        """Fetch the latest telegraph news items.

        Args:
            limit: Maximum number of items to return (1-100).

        Returns:
            List of NewsItem, sorted by time descending.
        """
        limit = max(1, min(limit, 100))
        params = {"app": "CailianpressWeb", "os": "web", "rn": str(limit)}

        try:
            resp = requests.get(
                _API_URL,
                params=params,
                headers=self._headers,
                timeout=self._timeout,
            )
            resp.raise_for_status()
        except requests.Timeout:
            logger.warning("请求财联社接口超时 (timeout=%d)", self._timeout)
            return []
        except requests.RequestException as exc:
            logger.error("请求财联社接口失败: %s", exc)
            return []

        return self._parse_response(resp.json())

    def fetch_stock_related_news(self, stock_code: str) -> list[NewsItem]:
        """Fetch news items that mention a specific stock code.

        This fetches a batch of recent news and filters locally.

        Args:
            stock_code: Stock code to filter by, e.g. "600519".

        Returns:
            Filtered list of NewsItem mentioning the stock.
        """
        all_news = self.fetch_telegraph(limit=80)
        code_normalized = stock_code.strip()

        matched: list[NewsItem] = []
        for item in all_news:
            # Check explicit stock field
            if code_normalized in item.stock_codes:
                matched.append(item)
                continue
            # Fallback: check if code appears in content or title
            if code_normalized in item.content or code_normalized in item.title:
                matched.append(item)

        logger.info(
            "股票 %s 相关新闻: %d/%d 条",
            stock_code,
            len(matched),
            len(all_news),
        )
        return matched

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_response(data: dict) -> list[NewsItem]:
        """Parse the JSON response into NewsItem objects."""
        items: list[NewsItem] = []

        roll_data = (data.get("data") or {}).get("roll_data")
        if not roll_data or not isinstance(roll_data, list):
            logger.warning("财联社返回数据格式异常: roll_data 为空或非列表")
            return items

        for entry in roll_data:
            try:
                ctime_ts = entry.get("ctime")
                ctime = (
                    datetime.fromtimestamp(int(ctime_ts))
                    if ctime_ts
                    else datetime.now()
                )
                subjects = entry.get("subjects") or []
                subject_names = [
                    s.get("subject_name", "")
                    if isinstance(s, dict)
                    else str(s)
                    for s in subjects
                ]
                stock_info = entry.get("stock") or {}
                stock_codes = (
                    [stock_info.get("code", "")]
                    if isinstance(stock_info, dict) and stock_info.get("code")
                    else []
                )

                items.append(
                    NewsItem(
                        id=str(entry.get("id", "")),
                        title=entry.get("title") or "",
                        content=entry.get("content") or "",
                        ctime=ctime,
                        subjects=subject_names,
                        stock_codes=stock_codes,
                    )
                )
            except Exception as exc:
                logger.debug("解析单条新闻失败: %s", exc)
                continue

        return items
