"""PangoBooks adapter — requires Playwright for JS rendering.

PangoBooks is a React SPA that loads search results client-side.
Falls back gracefully if Playwright is not installed.
"""

from bs4 import BeautifulSoup

from bookfinder.adapters import _browser
from bookfinder.adapters.base import BaseAdapter
from bookfinder.models import BookQuery, BookResult
from bookfinder.utils.parsing import parse_condition, parse_price

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

        # Broaden wait selector
        html = await _browser.fetch_rendered_html(
            url,
            wait_selector="[data-testid*='book'], [class*='book'], [class*='listing']",
        )

        return self._parse(html)

    async def is_available(self) -> bool:
        return _browser.is_available()

    def _parse(self, html: str) -> list[BookResult]:
        soup = BeautifulSoup(html, "html.parser")
        results: list[BookResult] = []

        # Find listing cards with broader patterns
        cards = (
            soup.select("[data-testid*='book-card']")
            or soup.select("div[class*='book-tile']")
            or soup.select("[class*='BookCard']")
            or soup.select("[class*='listing-card']")
            or soup.select("a[href*='/books/']")
        )

        for card in cards:
            if card.name == "a":
                link = card
                container = card
            else:
                link = card.select_one("a[href*='/books/']") or card.select_one("a")  # type: ignore[assignment]
                container = card

            title_el = (
                container.select_one("[class*='title'], [class*='Title'], [data-testid*='title']")
                or container.select_one("h2, h3, h4")
            )
            author_el = container.select_one("[class*='author'], [class*='Author'], [data-testid*='author']")
            price_el = container.select_one("[class*='price'], [class*='Price'], [data-testid*='price']")
            condition_el = container.select_one("[class*='condition'], [class*='Condition']")

            title = title_el.get_text(strip=True) if title_el else ""
            if not title:
                continue

            price = 0.0
            if price_el:
                price = parse_price(price_el.get_text())
            if price <= 0:
                continue

            href = ""
            if link:
                href = str(link.get("href", ""))
            url = href if href.startswith("http") else f"https://pangobooks.com{href}"

            condition = parse_condition(condition_el.get_text(strip=True) if condition_el else "used")

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
