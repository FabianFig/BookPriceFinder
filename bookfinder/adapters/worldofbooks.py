"""World of Books adapter — Shopify suggest.json API."""

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
        params = {
            "q": query.isbn if query.isbn else query.query,
            "resources[type]": "product",
            "resources[limit]": str(query.max_results),
        }
        data = await self._fetch_json(SUGGEST_URL, params=params)
        products = data.get("resources", {}).get("results", {}).get("products", [])

        results: list[BookResult] = []
        for product in products:
            title = product.get("title", "")
            if not title:
                continue

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

            url_path = product.get("url", "").split("?")[0]
            url = f"https://www.worldofbooks.com{url_path}" if url_path else ""

            results.append(
                BookResult(
                    title=title,
                    author=product.get("vendor", "Unknown"),
                    price=price,
                    currency="USD",
                    condition=Condition.USED,
                    source=self.name,
                    url=url,
                )
            )

        return results
