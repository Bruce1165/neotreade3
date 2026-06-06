"""Cninfo (巨潮资讯) announcement adapter."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

import requests

logger = logging.getLogger(__name__)

_API_URL = "http://www.cninfo.com.cn/new/hisAnnouncement/query"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}
_TIMEOUT = 15


@dataclass(frozen=True)
class Announcement:
    """A single announcement from Cninfo."""
    id: str
    title: str
    type_name: str
    stock_code: str
    stock_name: str
    publish_date: str
    adjunct_url: str


class CninfoAdapter:
    """Adapter for fetching announcements from Cninfo (巨潮资讯)."""

    def __init__(self, timeout: int = _TIMEOUT, headers: dict[str, str] | None = None) -> None:
        self._timeout = timeout
        self._headers = headers or _HEADERS

    def fetch_announcements(
        self, stock_code: str, start_date: str, end_date: str, page_size: int = 10,
    ) -> list[Announcement]:
        """Fetch announcements for a stock within a date range.

        Args:
            stock_code: Stock code, e.g. "000001".
            start_date: Start date in YYYY-MM-DD format.
            end_date: End date in YYYY-MM-DD format.
            page_size: Number of results per page.
        """
        code = stock_code.strip()
        form_data = {
            "stock": code, "tabName": "fulltext", "category": "",
            "pageNum": "1", "pageSize": str(page_size), "column": "szse",
            "seDate": f"{start_date}~{end_date}", "searchkey": "", "secid": "",
            "plate": "", "sortName": "", "sortType": "", "isHLtitle": "true",
        }
        try:
            resp = requests.post(_API_URL, data=form_data, headers=self._headers, timeout=self._timeout)
            resp.raise_for_status()
        except requests.Timeout:
            logger.warning("请求巨潮资讯接口超时 (timeout=%d)", self._timeout)
            return []
        except requests.RequestException as exc:
            logger.error("请求巨潮资讯接口失败: %s", exc)
            return []
        return self._parse_response(resp.json(), code)

    def fetch_latest_announcements(self, stock_code: str, days: int = 30) -> list[Announcement]:
        """Convenience method: fetch announcements from the last *days* days."""
        end = datetime.now().strftime("%Y-%m-%d")
        start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        logger.info("获取 %s 最近 %d 天公告 (%s ~ %s)", stock_code, days, start, end)
        return self.fetch_announcements(stock_code, start, end)

    @staticmethod
    def _parse_response(data: dict, stock_code: str) -> list[Announcement]:
        """Parse JSON response into Announcement objects."""
        items: list[Announcement] = []
        announcements = data.get("announcements")
        if not announcements or not isinstance(announcements, list):
            logger.warning("巨潮资讯返回数据格式异常")
            return items
        for entry in announcements:
            try:
                items.append(Announcement(
                    id=str(entry.get("announcementId", "")),
                    title=entry.get("announcementTitle", ""),
                    type_name=entry.get("announcementTypeName", ""),
                    stock_code=stock_code,
                    stock_name=entry.get("secName", ""),
                    publish_date=entry.get("publishDate", ""),
                    adjunct_url=entry.get("adjunctUrl", ""),
                ))
            except Exception as exc:
                logger.debug("解析单条公告失败: %s", exc)
        logger.info("巨潮资讯: 共解析 %d 条公告", len(items))
        return items
