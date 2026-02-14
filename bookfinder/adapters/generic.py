"""Generic adapter for Schema.org Product/Offer data."""

import json
import re

import httpx
from bs4 import BeautifulSoup

from bookfinder.adapters.base import BaseAdapter
from bookfinder.models import BookQuery, BookResult, Condition


class GenericAdapter(BaseAdapter):
    """Scrape any site that uses Schema.org Product/Offer structured data."""

    def __init__(self, name: str, base_url: str, search_url_template: str):
        """
        Args:
            name: Display name for this source.
            base_url: The site's base URL.
            search_url_template: URL template with {query}.
        """
        self._name = name
        self._base_url = base_url
        self._search_url_template = search_url_template

    @property
    def name(self) -> str:
        return self._name

    @property
    def base_url(self) -> str:
        return self._base_url

    async def search(self, query: BookQuery) -> list[BookResult]:
        search_term = query.isbn if query.isbn else query.query
        url = self._search_url_template.format(query=search_term)

        async with httpx.AsyncClient(
            follow_redirects=True,
            headers={"User-Agent": "BookPriceFinder/0.1"},
            timeout=15.0,
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()

        return self._parse_structured_data(resp.text, resp.url)

    def _parse_structured_data(self, html: str, page_url: httpx.URL) -> list[BookResult]:
        """Extract offers from JSON-LD."""
        soup = BeautifulSoup(html, "html.parser")
        results: list[BookResult] = []

        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
            except (json.JSONDecodeError, TypeError):
                continue

            items = data if isinstance(data, list) else [data]
            for item in items:
                if item.get("@type") not in ("Product", "Book"):
                    continue

                offers = item.get("offers", {})
                if isinstance(offers, dict):
                    offers = [offers]

                for offer in offers:
                    price = offer.get("price") or offer.get("lowPrice")
                    if price is None:
                        continue

                    condition_raw = offer.get("itemCondition", "")
                    if "New" in condition_raw:
                        condition = Condition.NEW
                    elif "Used" in condition_raw:
                        condition = Condition.USED
                    else:
                        condition = Condition.UNKNOWN

                    results.append(
                        BookResult(
                            title=item.get("name", "Unknown"),
                            author=_extract_author(item),
                            price=float(price),
                            currency=offer.get("priceCurrency", "USD"),
                            condition=condition,
                            source=self._name,
                            url=offer.get("url", str(page_url)),
                        )
                    )

        return results


def _extract_author(item: dict) -> str:
    author = item.get("author", "")
    if isinstance(author, dict):
        return author.get("name", "Unknown")
    if isinstance(author, list):
        names = [a.get("name", "") if isinstance(a, dict) else str(a) for a in author]
        return ", ".join(n for n in names if n)
    return str(author) if author else "Unknown"
