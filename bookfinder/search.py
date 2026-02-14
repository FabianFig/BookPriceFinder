"""Core search engine — queries all adapters in parallel."""

import asyncio

from bookfinder.adapters.base import BaseAdapter
from bookfinder.adapters.registry import get_all_adapters
from bookfinder.models import BookQuery, BookResult


async def search_all(
    query: BookQuery,
    adapters: list[BaseAdapter] | None = None,
) -> list[BookResult]:
    """Search all registered adapters concurrently and return sorted results."""
    adapters = adapters or get_all_adapters()

    async def _safe_search(adapter: BaseAdapter) -> list[BookResult]:
        try:
            return await adapter.search(query)
        except Exception as e:
            # Keep going if one source fails
            print(f"[warning] {adapter.name} failed: {e}")
            return []

    tasks = [_safe_search(a) for a in adapters]
    nested = await asyncio.gather(*tasks)

    # Flatten and sort (cheapest first)
    results = [r for batch in nested for r in batch]
    results.sort(key=lambda r: (r.price == 0, r.total_price))

    return results
