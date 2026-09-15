from typing import TypeVar, Generic
from ..models.websocket.responses import (
    GetUserOutfitResponse
)

T = TypeVar("T")

class Cache(Generic[T]):
    """A simple key/value cache with no expiry. Entries live until
    explicitly invalidated or cleared."""

    def __init__(self) -> None:
        self._store: dict[str, T] = {}

    def get(self, key: str) -> T | None:
        return self._store.get(key)

    def set(self, key: str, value: T) -> None:
        self._store[key] = value

    def invalidate(self, key: str) -> None:
        self._store.pop(key, None)

    def clear(self) -> None:
        self._store.clear()

class CacheManager:
    """Holds per-resource caches. Each resource type gets its own
    Cache instance so invalidation stays scoped and predictable."""

    def __init__(self) -> None:
        self.outfit: Cache[GetUserOutfitResponse] = Cache()

    def clear_all(self) -> None:
        """Clears every cache. Useful on reconnect, since cached
        state may be stale after a dropped connection."""
        
        self.outfit.clear()