"""AbeBooks adapter — HTML scraping with data-test-id selectors and microdata.

AbeBooks uses data-test-id attributes (Cypress-style) and Schema.org
microdata (itemprop) on search results.
"""

import re

import httpx
from bs4 import BeautifulSoup

from bookfinder.adapters.base import BaseAdapter
from bookfinder.models import BookQuery, BookResult, Condition

SEARCH_URL = "https://www.abebooks.com/servlet/SearchResults"


class AbeBooksAdapter(BaseAdapter):
    @property
    def name(self) -> str:
        return "AbeBooks"

    @property
    def base_url(self) -> str:
        return "https://www.abebooks.com"

    async def search(self, query: BookQuery) -> list[BookResult]:
        params: dict[str, str | int] = {"sortby": "17", "ds": query.max_results}
        if query.isbn:
            params["isbn"] = query.isbn
        else:
            params["kn"] = query.query

        async with httpx.AsyncClient(
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64; rv:120.0) "
                    "Gecko/20100101 Firefox/120.0"
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

        for item in soup.select('li[data-test-id="listing-item"]'):
            # Prefer microdata
            isbn_meta = item.select_one('meta[itemprop="isbn"]')
            name_meta = item.select_one('meta[itemprop="name"]')
            author_meta = item.select_one('meta[itemprop="author"]')

            # Fallback to data-test-id
            title_el = item.select_one('[data-test-id="listing-title"]')
            author_el = item.select_one('[data-test-id="listing-author"]')
            price_el = item.select_one('[data-test-id="item-price"]')
            cond_el = item.select_one('[data-test-id="listing-book-condition"]')

            title = (name_meta["content"] if name_meta else
                     title_el.get_text(strip=True) if title_el else "")
            if not title or not price_el:
                continue

            author = (author_meta["content"] if author_meta else
                      author_el.get_text(strip=True) if author_el else "Unknown")
            isbn = isbn_meta["content"] if isbn_meta else ""

            price = _parse_price(price_el.get_text())

            # Parse condition
            condition = Condition.UNKNOWN
            cond_text = cond_el.get_text(strip=True).lower() if cond_el else ""
            if "new" in cond_text and "used" not in cond_text:
                condition = Condition.NEW
            elif "used" in cond_text:
                condition = Condition.USED

            # Shipping info
            shipping = None
            # Check buy box for free shipping
            buy_box = item.select_one('[data-test-id^="buy-box-data"]')
            if buy_box:
                bb_text = buy_box.get_text()
                if "Free S" in bb_text or "free shipping" in bb_text.lower():
                    shipping = 0.0
                else:
                    ship_match = re.search(r"US\$\s*([\d.]+)\s*shipping", bb_text)
                    if ship_match:
                        shipping = float(ship_match.group(1))

            # Build URL
            href = title_el.get("href", "") if title_el and title_el.name == "a" else ""
            if not href:
                link = title_el.find("a") if title_el else None
                if not link:
                    link = item.select_one("a[data-test-id='listing-title']")
                href = link.get("href", "") if link else ""
            url = href if href.startswith("http") else f"https://www.abebooks.com{href}"

            results.append(
                BookResult(
                    title=title,
                    author=author,
                    price=price,
                    currency="USD",
                    condition=condition,
                    source=self.name,
                    url=url,
                    isbn=isbn,
                    shipping=shipping,
                )
            )

        return results


def _parse_price(text: str) -> float:
    match = re.search(r"[\d,]+\.?\d*", text.replace(",", ""))
    return float(match.group()) if match else 0.0
