"""Shared async HTTP client with rate-limiting, retry, caching, and ETag support.

Each provider gets its own client instance (to isolate rate-limit buckets).
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

import httpx
from cachetools import TTLCache
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

logger = logging.getLogger(__name__)

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (compatible; SportsOracle/1.0; +https://github.com/sports-oracle)"
)
_USER_AGENT = os.environ.get("PROVIDER_USER_AGENT", DEFAULT_USER_AGENT)


def _is_retryable(exc: BaseException) -> bool:
    """Retry on network errors and 5xx/429 HTTP responses."""
    if isinstance(exc, httpx.TransportError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in (429, 500, 502, 503, 504)
    return False


class TokenBucket:
    """Simple token-bucket rate limiter (async-safe, single-process)."""

    def __init__(self, rate: float, capacity: float) -> None:
        self._rate = rate  # tokens per second
        self._capacity = capacity
        self._tokens = capacity
        self._last = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last
            self._last = now
            self._tokens = min(self._capacity, self._tokens + elapsed * self._rate)
            if self._tokens < 1:
                wait = (1 - self._tokens) / self._rate
                await asyncio.sleep(wait)
                self._tokens = 0
            else:
                self._tokens -= 1


class SportHttpClient:
    """Async HTTP client for a single provider.

    Parameters
    ----------
    provider_name:
        Human-readable name used for log messages and cache namespacing.
    base_url:
        Provider's base URL (may be empty string for multi-base providers).
    rate_per_second:
        Maximum requests per second allowed to this provider.
    cache_ttl:
        TTL (seconds) for the dedup cache.  Set to 0 to disable.
    cache_maxsize:
        Maximum number of entries in the dedup TTL cache.
    extra_headers:
        Additional headers merged into every request (e.g. auth headers).
    """

    def __init__(
        self,
        provider_name: str,
        base_url: str = "",
        rate_per_second: float = 5.0,
        cache_ttl: int = 60,
        cache_maxsize: int = 512,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        self._name = provider_name
        self._bucket = TokenBucket(rate=rate_per_second, capacity=rate_per_second * 2)
        self._etags: dict[str, str] = {}
        self._cache: TTLCache[str, Any] = (
            TTLCache(maxsize=cache_maxsize, ttl=cache_ttl) if cache_ttl > 0 else None  # type: ignore[assignment]
        )
        headers = {"User-Agent": _USER_AGENT, **(extra_headers or {})}
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers=headers,
            timeout=httpx.Timeout(10.0, connect=5.0),
            follow_redirects=True,
        )

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def get_json(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        use_cache: bool = True,
    ) -> Any:
        """Perform a GET request and return the decoded JSON body.

        Results are deduplicated via an in-process TTLCache.  ETag headers are
        tracked and sent as ``If-None-Match``; a 304 response returns the cached
        value without consuming a cache slot.
        """
        cache_key = self._cache_key(url, params)

        # Dedup cache hit
        if use_cache and self._cache is not None and cache_key in self._cache:
            logger.debug("[%s] cache hit: %s", self._name, url)
            return self._cache[cache_key]

        return await self._fetch_with_retry(url, params, cache_key, use_cache)

    async def close(self) -> None:
        await self._client.aclose()

    @asynccontextmanager
    async def lifespan(self) -> AsyncGenerator[None, None]:
        try:
            yield
        finally:
            await self.close()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _cache_key(self, url: str, params: dict[str, Any] | None) -> str:
        if not params:
            return f"{self._name}:{url}"
        sorted_params = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
        return f"{self._name}:{url}?{sorted_params}"

    @retry(
        retry=retry_if_exception(_is_retryable),
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=0.5, max=8, jitter=1),
        reraise=True,
    )
    async def _fetch_with_retry(
        self,
        url: str,
        params: dict[str, Any] | None,
        cache_key: str,
        use_cache: bool,
    ) -> Any:
        await self._bucket.acquire()

        request_headers: dict[str, str] = {}
        etag = self._etags.get(cache_key)
        if etag and use_cache and self._cache is not None:
            request_headers["If-None-Match"] = etag

        logger.debug("[%s] GET %s params=%s", self._name, url, params)
        response = await self._client.get(url, params=params, headers=request_headers)

        # 304 Not Modified — return cached value
        if response.status_code == 304 and self._cache is not None and cache_key in self._cache:
            logger.debug("[%s] 304 not modified: %s", self._name, url)
            return self._cache[cache_key]

        response.raise_for_status()

        data = response.json()
        new_etag = response.headers.get("ETag")
        if new_etag:
            self._etags[cache_key] = new_etag
        if use_cache and self._cache is not None:
            self._cache[cache_key] = data
        return data
