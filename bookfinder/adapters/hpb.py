"""Half Price Books (hpb.com) adapter — uses Playwright for bot protection bypass.

HPB has aggressive bot protection (403 for plain HTTP requests).
Uses Playwright headless browser when available, falls back to httpx.
"""

import logging
import re

import httpx
from bs4 import BeautifulSoup

from bookfinder.adapters import _browser
from bookfinder.adapters.base import BaseAdapter
from bookfinder.models import BookQuery, BookResult, Condition

SEARCH_URL = "https://www.hpb.com/products"


class HPBAdapter(BaseAdapter):
    @property
    def name(self) -> str:
        return "Half Price Books"

    @property
    def base_url(self) -> str:
        return "https://www.hpb.com"

    async def search(self, query: BookQuery) -> list[BookResult]:
        search_term = query.isbn if query.isbn else query.query

        if _browser.is_available():
            html = await self._fetch_with_playwright(search_term)
        else:
            html = await self._fetch_with_httpx(search_term)

        return self._parse(html)

    async def _fetch_with_playwright(self, search_term: str) -> str:
        url = f"{SEARCH_URL}?keyword={search_term}"
        return await _browser.fetch_rendered_html(url)

    async def _fetch_with_httpx(self, search_term: str) -> str:
        params = {"keyword": search_term}

        async with httpx.AsyncClient(
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
            },
            timeout=20.0,
        ) as client:
            await client.get("https://www.hpb.com")
            resp = await client.get(SEARCH_URL, params=params)
            resp.raise_for_status()
            return resp.text

    def _parse(self, html: str) -> list[BookResult]:
        soup = BeautifulSoup(html, "html.parser")
        results: list[BookResult] = []

        page_text = soup.get_text(" ", strip=True).lower()
        if "we got lost in a good book" in page_text:
            logging.getLogger(__name__).warning("Half Price Books blocked the request.")
            return []

        cards = (
            soup.select(".product-item")
            or soup.select(".product-card")
            or soup.select("[class*='product'] [class*='item']")
            or soup.select("[data-product-id]")
        )

        for card in cards:
            title_el = (
                card.select_one("[class*='title']")
                or card.select_one("h2 a, h3 a")
            )
            price_el = (
                card.select_one("[class*='price']")
                or card.select_one(".money")
            )

            if not (title_el and price_el):
                continue

            price = _parse_price(price_el.get_text())
            if price <= 0:
                continue

            author_el = card.select_one("[class*='author']")
            condition_el = card.select_one("[class*='condition']")
            link_el = card.select_one("a[href*='/products/']") or card.select_one("a[href]")

            condition_text = condition_el.get_text(strip=True).lower() if condition_el else ""
            condition = Condition.USED
            if "new" in condition_text:
                condition = Condition.NEW

            href = str(link_el.get("href", "")) if link_el else ""
            url = href if href.startswith("http") else f"https://www.hpb.com{href}"

            results.append(
                BookResult(
                    title=title_el.get_text(strip=True),
                    author=author_el.get_text(strip=True) if author_el else "Unknown",
                    price=price,
                    currency="USD",
                    condition=condition,
                    source=self.name,
                    url=url,
                )
            )

        return results


def _parse_price(text: str) -> float:
    match = re.search(r"\$?([\d,]+\.?\d*)", text.replace(",", ""))
    return float(match.group(1)) if match else 0.0
