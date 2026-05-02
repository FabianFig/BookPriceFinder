"""Half Price Books (hpb.com) adapter — uses Playwright for bot protection bypass.

HPB has aggressive bot protection (403 for plain HTTP requests).
Uses Playwright headless browser when available.
"""

import logging

from bs4 import BeautifulSoup

from bookfinder.adapters import _browser
from bookfinder.adapters.base import BaseAdapter
from bookfinder.models import BookQuery, BookResult
from bookfinder.utils.parsing import parse_condition, parse_price

log = logging.getLogger(__name__)

SEARCH_URL = "https://www.hpb.com/products"


class HPBAdapter(BaseAdapter):
    @property
    def name(self) -> str:
        return "Half Price Books"

    @property
    def base_url(self) -> str:
        return "https://www.hpb.com"

    async def search(self, query: BookQuery) -> list[BookResult]:
        if not _browser.is_available():
            log.warning("Playwright not available, skipping HPB to avoid 403 block.")
            return []

        search_term = query.isbn if query.isbn else query.query
        url = f"{SEARCH_URL}?keyword={search_term}"
        
        try:
            html = await _browser.fetch_rendered_html(
                url, 
                wait_selector=".product-item, .product-card, [data-product-id]"
            )
            return self._parse(html)
        except Exception as e:
            log.error("HPB search failed: %s", e)
            return []

    def _parse(self, html: str) -> list[BookResult]:
        soup = BeautifulSoup(html, "html.parser")
        results: list[BookResult] = []

        page_text = soup.get_text(" ", strip=True).lower()
        if "we got lost in a good book" in page_text or "403 Forbidden" in html:
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

            price = parse_price(price_el.get_text())
            if price <= 0:
                continue

            author_el = card.select_one("[class*='author']")
            condition_el = card.select_one("[class*='condition']")
            link_el = card.select_one("a[href*='/products/']") or card.select_one("a[href]")

            condition = parse_condition(condition_el.get_text(strip=True) if condition_el else "")

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
