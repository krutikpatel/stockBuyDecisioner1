from cachetools import TTLCache
from threading import Lock
from typing import Any, Optional

from app.config import settings

_price_cache: TTLCache = TTLCache(maxsize=256, ttl=settings.cache_ttl_price_seconds)
_fundamental_cache: TTLCache = TTLCache(maxsize=256, ttl=settings.cache_ttl_fundamentals_seconds)
_lock = Lock()


def get_cached(cache: TTLCache, key: str) -> Optional[Any]:
    with _lock:
        return cache.get(key)


def set_cached(cache: TTLCache, key: str, value: Any) -> None:
    with _lock:
        cache[key] = value


def price_cache_key(ticker: str, period: str, interval: str) -> str:
    return f"{ticker}:{period}:{interval}"


def fundamental_cache_key(ticker: str) -> str:
    return f"fundamental:{ticker}"


def get_price_cache() -> TTLCache:
    return _price_cache


def get_fundamental_cache() -> TTLCache:
    return _fundamental_cache
