from src.services.cache_service import delete, get, set as cache_set


def test_get_set_delete():
    key = "test_key"
    value = "test_value"
    ttl = 60
    cache_set(key, value, ttl)
    assert get(key) == value
    delete(key)
    assert get(key) == ""
