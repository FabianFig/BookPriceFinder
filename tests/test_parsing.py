from bookfinder.utils.parsing import parse_price, parse_condition, parse_shipping
from bookfinder.models import Condition

def test_parse_price():
    assert parse_price("$12.99") == 12.99
    assert parse_price("£10,000.50") == 10000.50
    assert parse_price("Free") == 0.0
    assert parse_price("") == 0.0

def test_parse_condition():
    assert parse_condition("Brand New") == Condition.NEW
    assert parse_condition("Very Good used copy") == Condition.USED
    assert parse_condition("Acceptable") == Condition.USED
    assert parse_condition("Unknown condition") == Condition.UNKNOWN

def test_parse_shipping():
    assert parse_shipping("+$3.50 shipping") == 3.50
    assert parse_shipping("FREE shipping") == 0.0
    assert parse_shipping("US$ 5.00 shipping") == 5.00
    assert parse_shipping("Calculated at checkout") is None
