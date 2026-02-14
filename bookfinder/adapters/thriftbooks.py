"""ThriftBooks adapter — HTML scraping.

ThriftBooks server-side renders search results with class names like
AllEditionsItem-tile, SearchResultTileItem-topSector, etc.
"""

import re

import httpx
from bs4 import BeautifulSoup

from bookfinder.adapters.base import BaseAdapter
from bookfinder.models import BookQuery, BookResult, Condition

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

        async with httpx.AsyncClient(
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "en-US,en;q=0.9",
            },
            timeout=20.0,
        ) as client:
            resp = await client.get(SEARCH_URL, params=params)
            resp.raise_for_status()

        return self._parse(resp.text)

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

            # Price/condition
            row = tile.find(class_=re.compile(r"SearchResultTileItem-rowWrapper"))
            price = 0.0
            condition = Condition.USED
            if row:
                row_text = row.get_text()
                # Price
                price_match = re.search(r"\$([\d,]+\.?\d*)", row_text)
                if price_match:
                    price = float(price_match.group(1).replace(",", ""))

                # Condition
                cond_match = re.search(r"Condition:\s*(\w[\w\s]*?)(?:$|Format|List|Save)", row_text)
                if cond_match:
                    cond_text = cond_match.group(1).strip().lower()
                    if cond_text == "new":
                        condition = Condition.NEW
                    else:
                        condition = Condition.USED

            if price <= 0:
                continue

            # Link
            link = tile.find("a", href=re.compile(r"/w/"))
            href = str(link.get("href", "")) if link else ""
            url = href if href.startswith("http") else f"https://www.thriftbooks.com{href}"
            # Strip tracking params
            if "#" in url:
                url = url.split("#")[0]
            if "?" in url:
                url = url.split("?")[0]

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
