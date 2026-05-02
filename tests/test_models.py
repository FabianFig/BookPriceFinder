import pytest
from pydantic import ValidationError
from bookfinder.models import BookResult, BookQuery, Condition

def test_book_result_validation():
    # Valid data
    res = BookResult(
        title="Dune",
        author="Frank Herbert",
        price=10.0,
        currency="USD",
        condition=Condition.USED,
        source="Test",
        url="http://example.com"
    )
    assert res.title == "Dune"
    assert res.total_price == 10.0

    # Invalid price
    with pytest.raises(ValidationError):
        BookResult(
            title="Dune",
            author="Frank Herbert",
            price="free",
            currency="USD",
            condition=Condition.USED,
            source="Test",
            url="http://example.com"
        )

def test_book_result_total_price():
    res = BookResult(
        title="Dune",
        author="Frank Herbert",
        price=10.0,
        currency="USD",
        condition=Condition.USED,
        source="Test",
        url="http://example.com",
        shipping=2.5
    )
    assert res.total_price == 12.5

def test_book_query_validation():
    q = BookQuery(query="Dune")
    assert q.max_results == 5
    
    q2 = BookQuery(query="Dune", max_results=10)
    assert q2.max_results == 10
