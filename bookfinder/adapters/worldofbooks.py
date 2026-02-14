"""World of Books adapter — Shopify suggest.json API.

World of Books runs on Shopify, which exposes a search suggest API
that returns structured product data as JSON — much more reliable
than scraping HTML.
"""

import httpx

from bookfinder.adapters.base import BaseAdapter
from bookfinder.models import BookQuery, BookResult, Condition

SUGGEST_URL = "https://www.worldofbooks.com/search/suggest.json"


class WorldOfBooksAdapter(BaseAdapter):
    @property
    def name(self) -> str:
        return "World of Books"

    @property
    def base_url(self) -> str:
        return "https://www.worldofbooks.com"

    async def search(self, query: BookQuery) -> list[BookResult]:
        search_term = query.isbn if query.isbn else query.query
        params = {
            "q": search_term,
            "resources[type]": "product",
            "resources[limit]": str(query.max_results),
        }

        async with httpx.AsyncClient(
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
            },
            timeout=15.0,
        ) as client:
            resp = await client.get(SUGGEST_URL, params=params)
            resp.raise_for_status()

        data = resp.json()
        products = (
            data.get("resources", {})
            .get("results", {})
            .get("products", [])
        )

        results: list[BookResult] = []
        for product in products:
            title = product.get("title", "")
            if not title:
                continue

            # Use price_max if price is 0
            try:
                price = float(product.get("price", 0))
                if price <= 0:
                    price = float(product.get("price_max", 0))
                if price <= 0:
                    price = float(product.get("price_min", 0))
            except (ValueError, TypeError):
                continue
            if price <= 0:
                continue

            vendor = product.get("vendor", "Unknown")  # Often the author
            url_path = product.get("url", "")
            # Strip Shopify tracking params
            if "?" in url_path:
                url_path = url_path.split("?")[0]
            url = f"https://www.worldofbooks.com{url_path}" if url_path else ""

            results.append(
                BookResult(
                    title=title,
                    author=vendor,
                    price=price,
                    currency="USD",
                    condition=Condition.USED,  # WoB sells used books
                    source=self.name,
                    url=url,
                )
            )

        return results
