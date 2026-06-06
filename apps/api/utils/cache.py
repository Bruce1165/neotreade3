"""API caching utilities."""

from dataclasses import dataclass
from typing import Any, Optional
import time


@dataclass
class ApiCacheEntry:
    """Minimal in-memory cache entry for bootstrap API payloads."""

    payload: Any
    expires_at: float


class ApiCache:
    """Simple in-memory cache with TTL support."""

    def __init__(self):
        self._cache: dict[str, ApiCacheEntry] = {}

    def get(self, key: str) -> Optional[Any]:
        """Get cached value if not expired."""
        entry = self._cache.get(key)
        if entry is None:
            return None
        if time.time() > entry.expires_at:
            del self._cache[key]
            return None
        return entry.payload

    def set(self, key: str, value: Any, ttl_seconds: float = 60.0) -> None:
        """Set cache entry with TTL."""
        self._cache[key] = ApiCacheEntry(
            payload=value,
            expires_at=time.time() + ttl_seconds,
        )

    def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()

    def delete(self, key: str) -> None:
        """Delete specific cache entry."""
        self._cache.pop(key, None)
