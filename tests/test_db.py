import pytest
from pathlib import Path
from bookfinder.db.database import PriceDatabase
from bookfinder.models import BookResult, Condition

@pytest.fixture
def temp_db(tmp_path):
    db_path = tmp_path / "test_prices.db"
    db = PriceDatabase(db_path)
    yield db
    db.close()

def test_db_save_and_get_history(temp_db):
    results = [
        BookResult(
            title="Dune",
            author="Frank Herbert",
            price=10.0,
            currency="USD",
            condition=Condition.USED,
            source="TestStore",
            url="http://example.com/dune",
            isbn="1234567890"
        )
    ]
    temp_db.save_results(results)
    
    history = temp_db.get_price_history(isbn="1234567890")
    assert len(history) == 1
    assert history[0]["title"] == "Dune"
    assert history[0]["price"] == 10.0

def test_wishlist_operations(temp_db):
    wishlist_id = temp_db.add_to_wishlist("Dune", "Frank Herbert", "1234567890", 15.0)
    assert wishlist_id > 0
    
    wishlist = temp_db.get_wishlist()
    assert len(wishlist) == 1
    assert wishlist[0]["title"] == "Dune"
    
    # Check deal
    results = [
        BookResult(
            title="Dune",
            author="Frank Herbert",
            price=12.0,
            currency="USD",
            condition=Condition.USED,
            source="TestStore",
            url="http://example.com/dune",
            isbn="1234567890"
        )
    ]
    deals = temp_db.check_wishlist_deals(results)
    assert len(deals) == 1
    assert deals[0][1].price == 12.0

    temp_db.remove_from_wishlist(wishlist_id)
    assert len(temp_db.get_wishlist()) == 0
