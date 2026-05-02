import pytest
from bookfinder.adapters.abebooks import AbeBooksAdapter
from bookfinder.models import BookQuery, Condition

@pytest.mark.asyncio
async def test_abebooks_parser():
    adapter = AbeBooksAdapter()
    html = """
    <li data-test-id="listing-item">
        <meta itemprop="isbn" content="1234567890" />
        <meta itemprop="name" content="Dune" />
        <meta itemprop="author" content="Frank Herbert" />
        <div data-test-id="item-price">US$ 10.00</div>
        <div data-test-id="listing-book-condition">Used</div>
        <a data-test-id="listing-title" href="/dune-link">Dune</a>
        <div data-test-id="buy-box-data-1">US$ 3.50 shipping</div>
    </li>
    """
    results = adapter._parse(html)
    assert len(results) == 1
    assert results[0].title == "Dune"
    assert results[0].price == 10.0
    assert results[0].shipping == 3.5
    assert results[0].condition == Condition.USED
    assert results[0].isbn == "1234567890"
    assert "abebooks.com/dune-link" in results[0].url

@pytest.mark.asyncio
async def test_abebooks_search_mock(httpx_mock):
    httpx_mock.add_response(text='<li data-test-id="listing-item"><div data-test-id="item-price">US$ 5.00</div><a data-test-id="listing-title" href="/link">Title</a></li>')
    
    adapter = AbeBooksAdapter()
    query = BookQuery(query="Dune")
    results = await adapter.search(query)
    
    assert len(results) == 1
    assert results[0].price == 5.0
