"""LRU cache of rendered QPixmap objects.

One PageCache instance per open tab. Capacity defaults to 50 pages.
Uses collections.OrderedDict for O(1) get/put/eviction.
"""

from __future__ import annotations

from collections import OrderedDict

from PySide6.QtGui import QPixmap


class PageCache:
    """LRU cache mapping page indices to rendered QPixmap objects."""

    def __init__(self, max_pages: int = 50) -> None:
        """Initialize the cache.

        Args:
            max_pages: Maximum number of pages to cache.
        """
        self._max_pages = max_pages
        self._cache: OrderedDict[int, QPixmap] = OrderedDict()

    def get(self, page_index: int) -> QPixmap | None:
        """Retrieve a cached pixmap, refreshing its LRU position.

        Args:
            page_index: The 0-based page index.

        Returns:
            The cached QPixmap, or None if not cached.
        """
        if page_index not in self._cache:
            return None
        self._cache.move_to_end(page_index)
        return self._cache[page_index]

    def put(self, page_index: int, pixmap: QPixmap) -> None:
        """Cache a rendered pixmap, evicting the oldest entry if full.

        Args:
            page_index: The 0-based page index.
            pixmap: The rendered page pixmap.
        """
        if page_index in self._cache:
            self._cache.move_to_end(page_index)
            self._cache[page_index] = pixmap
            return

        if len(self._cache) >= self._max_pages:
            self._cache.popitem(last=False)

        self._cache[page_index] = pixmap

    def invalidate(self, page_index: int | None = None) -> None:
        """Remove cached entries.

        Args:
            page_index: If given, remove only that page. If None, clear all.
        """
        if page_index is None:
            self._cache.clear()
        else:
            self._cache.pop(page_index, None)

    def size(self) -> int:
        """Return the number of currently cached pages."""
        return len(self._cache)
