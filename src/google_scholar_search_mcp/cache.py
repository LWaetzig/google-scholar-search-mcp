"""In-memory cache for successful Scholar answers.

Every uncached call costs a 5-15 s delay and one or more requests that count
towards Scholar's bot detection. Agents repeat lookups (the same paper, the same
query), so answering those from memory is faster and makes a block less likely.
Only successful results are stored; errors are never cached.
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from collections.abc import Hashable
from typing import Any


class TTLCache:
    """A small thread-safe LRU cache whose entries expire."""

    def __init__(self, ttl_seconds: float = 3600.0, max_entries: int = 256) -> None:
        """Create a cache.

        Args:
            ttl_seconds (float): Seconds an entry stays valid. ``0`` disables
                the cache (nothing is stored).
            max_entries (int): Most entries kept; the least recently used is
                dropped first.
        """
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self._items: OrderedDict[Hashable, tuple[float, Any]] = OrderedDict()
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0

    @property
    def enabled(self) -> bool:
        """Whether the cache stores anything."""
        return self.ttl_seconds > 0 and self.max_entries > 0

    def get(self, key: Hashable) -> Any | None:
        """Look up a fresh entry.

        Args:
            key (Hashable): Cache key.

        Returns:
            Any | None: The stored value, or ``None`` if absent or expired.
        """
        with self._lock:
            entry = self._items.get(key)
            if entry is None or entry[0] < time.monotonic():
                self._items.pop(key, None)
                self.misses += 1
                return None
            self._items.move_to_end(key)
            self.hits += 1
            return entry[1]

    def set(self, key: Hashable, value: Any) -> None:
        """Store a value (no-op while the cache is disabled).

        Args:
            key (Hashable): Cache key.
            value (Any): Value to keep.
        """
        if not self.enabled:
            return
        with self._lock:
            self._items[key] = (time.monotonic() + self.ttl_seconds, value)
            self._items.move_to_end(key)
            while len(self._items) > self.max_entries:
                self._items.popitem(last=False)

    def clear(self) -> None:
        """Drop all entries and reset the counters."""
        with self._lock:
            self._items.clear()
            self.hits = self.misses = 0

    def __len__(self) -> int:
        """Number of stored entries, expired ones included."""
        with self._lock:
            return len(self._items)


def normalize(text: str | None) -> str:
    """Normalize free text for use in a cache key.

    Args:
        text (str | None): Query, title or id.

    Returns:
        str: Lower-cased with collapsed whitespace; empty for ``None``.
    """
    return " ".join((text or "").lower().split())
