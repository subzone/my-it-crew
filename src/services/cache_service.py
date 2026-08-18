from typing import Dict

cache: Dict[str, str] = {}


def get(key: str) -> str:
    return cache.get(key, "")

def set(key: str, value: str, ttl: int) -> None:
    cache[key] = value

def delete(key: str) -> None:
    if key in cache:
        del cache[key]