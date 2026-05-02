"""Base adapter that all site adapters must implement."""

import random
import logging
from abc import ABC, abstractmethod
from typing import Any, Optional

import httpx

from bookfinder.models import BookQuery, BookResult

log = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]


class BaseAdapter(ABC):
    """Interface for a book price source."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name for this source (e.g. 'ThriftBooks')."""

    @property
    @abstractmethod
    def base_url(self) -> str:
        """Base URL of the site."""

    @abstractmethod
    async def search(self, query: BookQuery) -> list[BookResult]:
        """Search for books matching the query and return price results."""

    def get_headers(self) -> dict[str, str]:
        """Return common headers for requests."""
        return {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
        }

    async def _fetch_html(self, url: str, params: Optional[dict[str, Any]] = None, timeout: float = 20.0) -> str:
        """Shared helper to fetch HTML from a URL."""
        async with httpx.AsyncClient(
            follow_redirects=True,
            headers=self.get_headers(),
            timeout=timeout,
        ) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            return resp.text

    async def _fetch_json(self, url: str, params: Optional[dict[str, Any]] = None, timeout: float = 15.0) -> Any:
        """Shared helper to fetch JSON from a URL."""
        async with httpx.AsyncClient(
            follow_redirects=True,
            headers=self.get_headers(),
            timeout=timeout,
        ) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            return resp.json()

    async def is_available(self) -> bool:
        """Check if the source is reachable."""
        try:
            # Short timeout for health check
            await self._fetch_html(self.base_url, timeout=5.0)
            return True
        except Exception as e:
            log.debug("Availability check failed for %s: %s", self.name, e)
            return False
