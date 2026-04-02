"""Tests for LRU page cache."""

from __future__ import annotations

from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QApplication

from k_pdf.core.page_cache import PageCache

# QPixmap requires a QApplication instance
_app: QApplication | None = None


def setup_module() -> None:
    """Ensure QApplication exists for QPixmap operations."""
    global _app
    if QApplication.instance() is None:
        _app = QApplication([])


def _make_pixmap(w: int = 10, h: int = 10) -> QPixmap:
    """Create a small test QPixmap."""
    img = QImage(w, h, QImage.Format.Format_RGB888)
    img.fill(0)
    return QPixmap.fromImage(img)


def test_put_and_get() -> None:
    """Test basic put and get."""
    cache = PageCache(max_pages=5)
    pix = _make_pixmap()
    cache.put(0, pix)
    assert cache.get(0) is not None
    assert cache.size() == 1


def test_get_returns_none_for_missing() -> None:
    """Test get returns None for uncached page."""
    cache = PageCache(max_pages=5)
    assert cache.get(42) is None


def test_lru_eviction_when_full() -> None:
    """Test oldest entry is evicted when cache exceeds max_pages."""
    cache = PageCache(max_pages=3)
    for i in range(4):
        cache.put(i, _make_pixmap())
    # Page 0 should have been evicted (oldest)
    assert cache.get(0) is None
    assert cache.get(1) is not None
    assert cache.get(3) is not None
    assert cache.size() == 3


def test_get_refreshes_lru_order() -> None:
    """Test that get() refreshes the entry's position in LRU order."""
    cache = PageCache(max_pages=3)
    cache.put(0, _make_pixmap())
    cache.put(1, _make_pixmap())
    cache.put(2, _make_pixmap())
    # Access page 0 to refresh it
    cache.get(0)
    # Add page 3 — page 1 should be evicted (oldest untouched)
    cache.put(3, _make_pixmap())
    assert cache.get(0) is not None  # was refreshed
    assert cache.get(1) is None  # evicted
    assert cache.get(3) is not None


def test_invalidate_single_page() -> None:
    """Test invalidating a specific page."""
    cache = PageCache(max_pages=5)
    cache.put(0, _make_pixmap())
    cache.put(1, _make_pixmap())
    cache.invalidate(0)
    assert cache.get(0) is None
    assert cache.get(1) is not None
    assert cache.size() == 1


def test_invalidate_all_pages() -> None:
    """Test invalidating all pages clears the cache."""
    cache = PageCache(max_pages=5)
    for i in range(3):
        cache.put(i, _make_pixmap())
    cache.invalidate()
    assert cache.size() == 0
