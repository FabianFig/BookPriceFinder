"""Open Library adapter — free API, no key required."""

from bookfinder.adapters.base import BaseAdapter
from bookfinder.models import BookQuery, BookResult, Condition

API_BASE = "https://openlibrary.org"


class OpenLibraryAdapter(BaseAdapter):
    @property
    def name(self) -> str:
        return "Open Library"

    @property
    def base_url(self) -> str:
        return API_BASE

    async def search(self, query: BookQuery) -> list[BookResult]:
        params: dict[str, str | int] = {"limit": query.max_results}

        if query.isbn:
            params["isbn"] = query.isbn
        else:
            params["q"] = query.query

        data = await self._fetch_json(f"{API_BASE}/search.json", params=params)

        results: list[BookResult] = []
        for doc in data.get("docs", []):
            isbn_list = doc.get("isbn", [])
            isbn = isbn_list[0] if isbn_list else ""
            key = doc.get("key", "")

            results.append(
                BookResult(
                    title=doc.get("title", "Unknown"),
                    author=", ".join(doc.get("author_name", ["Unknown"])),
                    price=0.0,
                    currency="USD",
                    condition=Condition.UNKNOWN,
                    source=self.name,
                    url=f"{API_BASE}{key}",
                    isbn=isbn,
                )
            )

        return results
