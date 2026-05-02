from bookfinder.web.utils import looks_like_isbn, bool_value

def test_looks_like_isbn():
    assert looks_like_isbn("1234567890") is True
    assert looks_like_isbn("123456789X") is True
    assert looks_like_isbn("9781234567890") is True
    assert looks_like_isbn("978-1-234-56789-0") is True
    assert looks_like_isbn("Dune") is False
    assert looks_like_isbn("123") is False

def test_bool_value():
    assert bool_value("1") is True
    assert bool_value("true") is True
    assert bool_value("on") is True
    assert bool_value("0") is False
    assert bool_value(None) is False
    assert bool_value("off") is False
