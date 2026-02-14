"""Core search engine — queries all adapters in parallel."""

import asyncio
import logging
import time
from dataclasses import dataclass, field

from bookfinder.adapters.base import BaseAdapter
from bookfinder.adapters.registry import get_all_adapters
from bookfinder.models import BookQuery, BookResult

log = logging.getLogger(__name__)


@dataclass
class SearchReport:
    """Results plus per-source status info."""

    results: list[BookResult] = field(default_factory=list)
    source_counts: dict[str, int] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)
    elapsed: float = 0.0


async def search_all(
    query: BookQuery,
    adapters: list[BaseAdapter] | None = None,
) -> list[BookResult]:
    """Search all registered adapters concurrently and return sorted results."""
    report = await search_all_with_report(query, adapters)
    return report.results


async def search_all_with_report(
    query: BookQuery,
    adapters: list[BaseAdapter] | None = None,
) -> SearchReport:
    """Search all adapters and return results with per-source status."""
    adapters = adapters or get_all_adapters()
    report = SearchReport()
    start = time.monotonic()

    async def _safe_search(adapter: BaseAdapter) -> list[BookResult]:
        try:
            results = await adapter.search(query)
            report.source_counts[adapter.name] = len(results)
            return results
        except Exception as e:
            log.warning("%s failed: %s", adapter.name, e)
            report.errors[adapter.name] = str(e)
            return []

    tasks = [_safe_search(a) for a in adapters]
    nested = await asyncio.gather(*tasks)

    report.results = [r for batch in nested for r in batch]
    report.results.sort(key=lambda r: (r.price == 0, r.total_price))
    report.elapsed = time.monotonic() - start

    return report
