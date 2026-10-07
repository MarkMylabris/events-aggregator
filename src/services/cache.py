import time
from collections.abc import Callable, Hashable
from typing import Any


class TTLCache:
    """In-memory cache whose entries expire ``ttl`` seconds after being set."""

    def __init__(self, ttl: float, clock: Callable[[], float] = time.monotonic) -> None:
        self.ttl = ttl
        self.clock = clock
        self._items: dict[Hashable, tuple[float, Any]] = {}

    def get(self, key: Hashable) -> Any | None:
        item = self._items.get(key)
        if item is None:
            return None
        expires_at, value = item
        if self.clock() >= expires_at:
            del self._items[key]
            return None
        return value

    def set(self, key: Hashable, value: Any) -> None:
        self._items[key] = (self.clock() + self.ttl, value)

    def delete(self, key: Hashable) -> None:
        self._items.pop(key, None)
