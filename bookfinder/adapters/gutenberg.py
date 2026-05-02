"""Project Gutenberg adapter — finds free public domain ebooks."""

from bookfinder.adapters.base import BaseAdapter
from bookfinder.models import BookQuery, BookResult, Condition

API_URL = "https://gutendex.com/books/"


class GutenbergAdapter(BaseAdapter):
    @property
    def name(self) -> str:
        return "Project Gutenberg"

    @property
    def base_url(self) -> str:
        return "https://www.gutenberg.org"

    async def search(self, query: BookQuery) -> list[BookResult]:
        params = {"search": query.isbn if query.isbn else query.query}
        data = await self._fetch_json(API_URL, params=params)

        results: list[BookResult] = []
        for book in data.get("results", []):
            title = book.get("title", "Unknown")
            authors = [a.get("name", "Unknown") for a in book.get("authors", [])]
            author_str = ", ".join(authors) if authors else "Unknown"

            # Find a readable format link
            formats = book.get("formats", {})
            url = (
                formats.get("text/html")
                or formats.get("application/epub+zip")
                or f"https://www.gutenberg.org/ebooks/{book.get('id')}"
            )

            results.append(
                BookResult(
                    title=title,
                    author=author_str,
                    price=0.0,
                    currency="USD",
                    condition=Condition.NEW,
                    source=self.name,
                    url=url,
                    shipping=0.0,
                )
            )

        return results
