"""Web utilities for search, filtering, and caching."""

import time
from math import ceil
from typing import Any, Optional

from bookfinder.db.database import PriceDatabase
from bookfinder.models import BookQuery, BookResult, SearchReport
from bookfinder.search import search_all_with_report

_CACHE_TTL_SECONDS = 300
_CACHE_MAX_ITEMS = 50
_CACHE: dict[tuple[str, int, bool], tuple[float, SearchReport]] = {}


def bool_value(value: Optional[str]) -> bool:
    """Safely convert string/None to boolean."""
    if value is None:
        return False
    return value.lower() in {"1", "true", "yes", "on"}


def looks_like_isbn(query: str) -> bool:
    """Check if a query looks like an ISBN-10 or ISBN-13."""
    cleaned = query.replace("-", "").replace(" ", "").strip()
    if len(cleaned) == 13 and cleaned.isdigit():
        return True
    if len(cleaned) == 10 and (
        cleaned.isdigit() or (cleaned[:9].isdigit() and cleaned[9] in "0123456789Xx")
    ):
        return True
    return False


async def cached_search(
    query: str, max_results: int, isbn_only: bool, db: Optional[PriceDatabase] = None
) -> SearchReport:
    """Search with local memory cache."""
    key = (query, max_results, isbn_only)
    now = time.time()
    cached = _CACHE.get(key)
    
    if cached and now - cached[0] < _CACHE_TTL_SECONDS:
        return cached[1]

    book_query = BookQuery(
        query="" if isbn_only else query,
        isbn=query if isbn_only else "",
        max_results=max_results,
    )
    
    # Use database logger if available for health tracking
    logger = db.log_scraper_health if db else None
    report = await search_all_with_report(book_query, health_logger=logger)
    
    _CACHE[key] = (now, report)

    # Prune old cache entries
    if len(_CACHE) > _CACHE_MAX_ITEMS:
        oldest_key = min(_CACHE, key=lambda k: _CACHE[k][0])
        _CACHE.pop(oldest_key, None)

    return report


def get_book_cover_url(isbn: Optional[str]) -> Optional[str]:
    """Return Open Library cover URL for an ISBN."""
    if not isbn:
        return None
    clean_isbn = isbn.replace("-", "").replace(" ", "").strip()
    if not clean_isbn:
        return None
    return f"https://covers.openlibrary.org/b/isbn/{clean_isbn}-M.jpg"


def apply_filters(
    results: list[BookResult],
    filter_text: str,
    min_price: Optional[float],
    max_price: Optional[float],
    condition_filter: str,
    selected_sources: list[str],
    isbn_only: bool,
    isbn_query: str,
) -> list[BookResult]:
    """Apply search filters to a result list."""
    filtered = results

    if filter_text:
        needle = filter_text.lower()
        filtered = [
            r for r in filtered if needle in f"{r.title} {r.author} {r.source}".lower()
        ]

    if min_price is not None:
        filtered = [r for r in filtered if r.total_price >= min_price]
    if max_price is not None:
        filtered = [r for r in filtered if r.total_price <= max_price]

    if condition_filter:
        filtered = [r for r in filtered if r.condition.value == condition_filter]

    if selected_sources:
        filtered = [r for r in filtered if r.source in selected_sources]

    if isbn_only and isbn_query:
        filtered = [r for r in filtered if r.isbn == isbn_query]

    return filtered


def apply_sort(results: list[BookResult], sort_by: str) -> list[BookResult]:
    """Sort search results in-place."""
    if sort_by == "price-desc":
        results.sort(key=lambda r: r.total_price, reverse=True)
    elif sort_by == "title-asc":
        results.sort(key=lambda r: r.title)
    elif sort_by == "title-desc":
        results.sort(key=lambda r: r.title, reverse=True)
    elif sort_by == "source-asc":
        results.sort(key=lambda r: r.source)
    elif sort_by == "source-desc":
        results.sort(key=lambda r: r.source, reverse=True)
    else:
        # Default: price-asc
        results.sort(key=lambda r: r.total_price)
    return results


def paginate(results: list[BookResult], page: int, page_size: int) -> tuple[list[BookResult], int, int, int]:
    """Slice results for pagination. Returns (results, total, total_pages, current_page)."""
    total = len(results)
    total_pages = max(1, ceil(total / page_size))
    current_page = max(1, min(page, total_pages))
    
    start = (current_page - 1) * page_size
    end = start + page_size
    return results[start:end], total, total_pages, current_page


def compare_lowest_per_source(results: list[BookResult]) -> list[BookResult]:
    """Extract the cheapest copy from each available source."""
    lowest: dict[str, BookResult] = {}
    for r in results:
        if r.price <= 0:
            continue
        cur = lowest.get(r.source)
        if not cur or r.total_price < cur.total_price:
            lowest[r.source] = r
    return list(lowest.values())
