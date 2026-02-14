"""PangoBooks adapter — requires Playwright for JS rendering.

PangoBooks is a React SPA that loads search results client-side.
Falls back gracefully if Playwright is not installed.
"""

import re

from bs4 import BeautifulSoup

from bookfinder.adapters import _browser
from bookfinder.adapters.base import BaseAdapter
from bookfinder.models import BookQuery, BookResult, Condition

SEARCH_URL = "https://pangobooks.com/search"


class PangoBooksAdapter(BaseAdapter):
    @property
    def name(self) -> str:
        return "PangoBooks"

    @property
    def base_url(self) -> str:
        return "https://pangobooks.com"

    async def search(self, query: BookQuery) -> list[BookResult]:
        if not _browser.is_available():
            return []

        search_term = query.isbn if query.isbn else query.query
        url = f"{SEARCH_URL}?q={search_term}"

        html = await _browser.fetch_rendered_html(
            url,
            wait_selector="div[class*='book-tile'], a[href*='/books/']",
        )

        return self._parse(html)

    async def is_available(self) -> bool:
        return _browser.is_available()

    def _parse(self, html: str) -> list[BookResult]:
        soup = BeautifulSoup(html, "html.parser")
        results: list[BookResult] = []

        # Find listing cards
        cards = (
            soup.select("div[class*='book-tile'], div[class*='book-tile-wrapper']")
            or soup.select("[class*='BookCard'], [class*='book-card']")
            or soup.select("[class*='listing'], [class*='Listing']")
            or soup.select("a[href*='/books/']")
        )

        for card in cards:
            if card.name == "a":
                link = card
                container = card
            else:
                link = card.select_one("a[href*='/books/']") or card.select_one("a")
                container = card

            title_el = (
                container.select_one("[class*='title'], [class*='Title']")
                or container.select_one("h2, h3, h4")
            )
            author_el = container.select_one("[class*='author'], [class*='Author']")
            price_el = container.select_one("[class*='price'], [class*='Price']")
            condition_el = container.select_one("[class*='condition'], [class*='Condition']")

            title = title_el.get_text(strip=True) if title_el else ""
            if not title:
                continue

            price = 0.0
            if price_el:
                price = _parse_price(price_el.get_text())
            if price <= 0:
                continue

            href = ""
            if link:
                href = link.get("href", "")
            url = href if href.startswith("http") else f"https://pangobooks.com{href}"

            condition = Condition.USED  # Used books
            if condition_el:
                cond_text = condition_el.get_text(strip=True).lower()
                if "new" in cond_text or "like new" in cond_text:
                    condition = Condition.NEW

            results.append(
                BookResult(
                    title=title,
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
