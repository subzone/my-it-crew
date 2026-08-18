import pytest
from src.cache_service import CacheService

cache_service = CacheService()

def test_get_set_delete):
    key = 'test_key'
    value = 'test_value'
    ttl = 60
    assert cache_service.set(key, value, ttl)
    assert cache_service.get(key) == value.encode('utf-8')
    assert cache_service.delete(key) == 1
