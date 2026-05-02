"""ThriftBooks adapter — HTML scraping."""

import re
from bs4 import BeautifulSoup

from bookfinder.adapters.base import BaseAdapter
from bookfinder.models import BookQuery, BookResult, Condition
from bookfinder.utils.parsing import parse_condition, parse_price

SEARCH_URL = "https://www.thriftbooks.com/browse/"


class ThriftBooksAdapter(BaseAdapter):
    @property
    def name(self) -> str:
        return "ThriftBooks"

    @property
    def base_url(self) -> str:
        return "https://www.thriftbooks.com"

    async def search(self, query: BookQuery) -> list[BookResult]:
        search_term = query.isbn if query.isbn else query.query
        params = {"b.search": search_term}
        html = await self._fetch_html(SEARCH_URL, params=params)
        return self._parse(html)

    def _parse(self, html: str) -> list[BookResult]:
        soup = BeautifulSoup(html, "html.parser")
        results: list[BookResult] = []

        # Result tiles
        for tile in soup.find_all(class_=re.compile(r"AllEditionsItem-tile")):
            # Title
            title_el = tile.find(class_=re.compile(r"AllEditionsItem-tileTitle"))
            title = title_el.get_text(strip=True) if title_el else ""
            if not title:
                continue

            # Author
            author_el = tile.find(class_=re.compile(r"SearchResultListItem-subheading"))
            author = ""
            if author_el:
                author = re.sub(r"^By\s*", "", author_el.get_text(strip=True))

            # Price/condition/format
            row = tile.find(class_=re.compile(r"SearchResultTileItem-rowWrapper"))
            price = 0.0
            condition = Condition.USED
            if row:
                row_text = row.get_text()
                
                # Filter out non-book media
                row_lower = row_text.lower()
                if any(media in row_lower for media in ["dvd", "vhs", "blu-ray", "audio cd", "cassette"]):
                    continue

                # Price
                price = parse_price(row_text)

                # Condition
                cond_match = re.search(r"Condition:\s*(\w[\w\s]*?)(?:$|Format|List|Save)", row_text)
                if cond_match:
                    condition = parse_condition(cond_match.group(1).strip())

            if price <= 0:
                continue

            # Link
            link = tile.find("a", href=re.compile(r"/w/"))
            href = str(link.get("href", "")) if link else ""
            url = href if href.startswith("http") else f"https://www.thriftbooks.com{href}"
            url = url.split("#")[0].split("?")[0] # Clean tracking

            results.append(
                BookResult(
                    title=title,
                    author=author or "Unknown",
                    price=price,
                    currency="USD",
                    condition=condition,
                    source=self.name,
                    url=url,
                )
            )

        return results
