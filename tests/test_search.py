import asyncio

from bookfinder.adapters.base import BaseAdapter
from bookfinder.models import BookQuery, BookResult, Condition
from bookfinder.search import search_all


class _Adapter(BaseAdapter):
    def __init__(self, name: str, results: list[BookResult]):
        self._name = name
        self._results = results

    @property
    def name(self) -> str:
        return self._name

    @property
    def base_url(self) -> str:
        return "https://example.com"

    async def search(self, query: BookQuery) -> list[BookResult]:
        return self._results


def test_search_sorting_by_total_price():
    q = BookQuery(query="dune", max_results=5)

    results_a = [
        BookResult(
            title="A",
            author="X",
            price=5.0,
            shipping=1.0,
            currency="USD",
            condition=Condition.USED,
            source="A",
            url="https://a",
        )
    ]
    results_b = [
        BookResult(
            title="B",
            author="Y",
            price=3.0,
            shipping=0.0,
            currency="USD",
            condition=Condition.USED,
            source="B",
            url="https://b",
        )
    ]
    results_c = [
        BookResult(
            title="C",
            author="Z",
            price=0.0,
            shipping=None,
            currency="USD",
            condition=Condition.UNKNOWN,
            source="C",
            url="https://c",
        )
    ]

    adapters = [
        _Adapter("A", results_a),
        _Adapter("B", results_b),
        _Adapter("C", results_c),
    ]

    results = asyncio.run(search_all(q, adapters=adapters))

    assert [r.title for r in results] == ["B", "A", "C"]