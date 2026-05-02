"""Core search engine — queries all adapters in parallel."""

import asyncio
import logging
import time
from typing import Callable, Optional

from bookfinder.adapters.base import BaseAdapter
from bookfinder.adapters.registry import get_all_adapters
from bookfinder.models import BookQuery, BookResult, SearchReport

log = logging.getLogger(__name__)

# Type for health logging callback
HealthLogger = Callable[[str, bool, Optional[str]], None]


async def search_all_with_report(
    query: BookQuery,
    adapters: list[BaseAdapter] | None = None,
    health_logger: HealthLogger | None = None,
) -> SearchReport:
    """Search all adapters and return results with per-source status."""
    adapters = adapters or get_all_adapters()
    report = SearchReport()
    start = time.monotonic()

    async def _safe_search(adapter: BaseAdapter) -> list[BookResult]:
        retries = 2
        last_error = ""
        for i in range(retries + 1):
            try:
                results = await adapter.search(query)
                report.source_counts[adapter.name] = len(results)
                if health_logger:
                    health_logger(adapter.name, True, None)
                return results
            except Exception as e:
                last_error = str(e)
                if i < retries:
                    log.debug("%s failed (attempt %d/%d): %s", adapter.name, i+1, retries+1, e)
                    await asyncio.sleep(1.0 * (i + 1))
                else:
                    log.warning("%s failed after %d retries: %s", adapter.name, retries, e)
        
        report.errors[adapter.name] = last_error
        if health_logger:
            health_logger(adapter.name, False, last_error)
        return []

    tasks = [_safe_search(a) for a in adapters]
    nested = await asyncio.gather(*tasks)

    # Flatten results
    report.results = [r for batch in nested for r in batch]
    
    # Sort: prices with 0 at the end, then by total price
    report.results.sort(key=lambda r: (r.price == 0, r.total_price))
    
    report.elapsed = time.monotonic() - start
    return report
