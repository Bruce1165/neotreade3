"""East Money Guba (股吧) sentiment adapter."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import requests

logger = logging.getLogger(__name__)

_API = "https://guba.eastmoney.com/interface/GetData.aspx"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Referer": "https://guba.eastmoney.com/",
}
_TIMEOUT = 15
_POS_KW = frozenset({"涨", "牛", "突破", "利好", "涨停", "大涨", "看多", "买入", "强势"})
_NEG_KW = frozenset({"跌", "熊", "崩盘", "利空", "跌停", "大跌", "看空", "卖出", "弱势"})


@dataclass(frozen=True)
class GubaPost:
    """A single post from East Money Guba (股吧)."""
    title: str
    content: str
    publish_time: str
    nickname: str
    read_count: int
    comment_count: int
    stock_code: str


class EastmoneyGubaAdapter:
    """Adapter for fetching forum posts from East Money Guba (东方财富股吧)."""

    def __init__(self, timeout: int = _TIMEOUT, headers: dict[str, str] | None = None) -> None:
        self._timeout = timeout
        self._headers = headers or _HEADERS

    def fetch_hot_posts(self, stock_code: str, limit: int = 10) -> list[GubaPost]:
        """Fetch hot posts for a stock from Guba."""
        code = stock_code.strip()
        params = {"path": "newguba/PostList", "param": f"code={code}&ps={limit}&p=1&type=1"}
        try:
            resp = requests.get(_API, params=params, headers=self._headers, timeout=self._timeout)
            resp.raise_for_status()
            if not resp.text or resp.text.strip() in ("", "url is null"):
                logger.warning("东方财富股吧接口返回空数据 (code=%s)", code)
                return []
            return self._parse_response(resp.json(), code)
        except requests.Timeout:
            logger.warning("请求东方财富股吧接口超时 (code=%s)", code)
            return []
        except (ValueError, requests.RequestException) as exc:
            logger.error("请求东方财富股吧接口失败: %s", exc)
            return []

    @staticmethod
    def calculate_sentiment_score(posts: list[GubaPost]) -> float:
        """Keyword-based sentiment score in [-1.0, +1.0]."""
        if not posts:
            return 0.0
        total = 0.0
        for post in posts:
            text = f"{post.title} {post.content}"
            total += sum(1 for kw in _POS_KW if kw in text)
            total -= sum(1 for kw in _NEG_KW if kw in text)
        max_possible = len(posts) * max(len(_POS_KW), len(_NEG_KW))
        if max_possible == 0:
            return 0.0
        score = max(-1.0, min(1.0, (total / max_possible) * 3))
        logger.info("股吧情绪分析: %d 篇帖子, 情绪得分=%.2f", len(posts), score)
        return round(score, 4)

    @staticmethod
    def _parse_response(data: dict, stock_code: str) -> list[GubaPost]:
        """Parse JSON response into GubaPost objects."""
        posts: list[GubaPost] = []
        post_list = (data.get("data") or {}).get("post_list")
        if not post_list or not isinstance(post_list, list):
            logger.warning("东方财富股吧返回数据格式异常")
            return posts
        for entry in post_list:
            try:
                posts.append(GubaPost(
                    title=entry.get("post_title", ""),
                    content=entry.get("post_content", ""),
                    publish_time=entry.get("post_publish_time", ""),
                    nickname=entry.get("post_nickname", ""),
                    read_count=int(entry.get("read_count", 0)),
                    comment_count=int(entry.get("comment_count", 0)),
                    stock_code=stock_code,
                ))
            except Exception as exc:
                logger.debug("解析单条股吧帖子失败: %s", exc)
        logger.info("东方财富股吧: 共解析 %d 条帖子", len(posts))
        return posts
