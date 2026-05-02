"""AbeBooks adapter — HTML scraping with data-test-id selectors and microdata."""

from bs4 import BeautifulSoup

from bookfinder.adapters.base import BaseAdapter
from bookfinder.models import BookQuery, BookResult
from bookfinder.utils.parsing import parse_condition, parse_price, parse_shipping

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

        html = await self._fetch_html(SEARCH_URL, params=params)
        return self._parse(html)

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

            title = str(name_meta["content"] if name_meta else
                       title_el.get_text(strip=True) if title_el else "")
            if not title or not price_el:
                continue

            author = str(author_meta["content"] if author_meta else
                         author_el.get_text(strip=True) if author_el else "Unknown")
            isbn = str(isbn_meta["content"]) if isbn_meta else ""

            price = parse_price(price_el.get_text())
            condition = parse_condition(cond_el.get_text(strip=True) if cond_el else "")

            # Shipping info
            shipping = None
            buy_box = item.select_one('[data-test-id^="buy-box-data"]')
            if buy_box:
                shipping = parse_shipping(buy_box.get_text())

            # Build URL
            link = (
                item.select_one("a[data-test-id='listing-title']")
                or item.select_one("a[href*='/bd']")
                or item.select_one("a[href]")
            )
            href = str(link.get("href", "")) if link else ""
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
