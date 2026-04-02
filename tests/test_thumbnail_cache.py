"""Tests for ThumbnailCache."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pymupdf
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication

from k_pdf.core.document_model import PageInfo
from k_pdf.core.thumbnail_cache import ThumbnailCache

_app: QApplication | None = None


def setup_module() -> None:
    global _app
    if QApplication.instance() is None:
        _app = QApplication([])


def test_pre_renders_all_pages(valid_pdf: Path, qtbot: object) -> None:
    doc = pymupdf.open(str(valid_pdf))
    pages = [
        PageInfo(index=i, width=612, height=792, rotation=0, has_text=True, annotation_count=0)
        for i in range(doc.page_count)
    ]
    cache = ThumbnailCache(doc_handle=doc, pages=pages, thumb_width=90)
    ready_spy = MagicMock()
    cache.all_thumbnails_ready.connect(ready_spy)

    cache.start()

    def check_done() -> None:
        assert ready_spy.call_count == 1

    qtbot.waitUntil(check_done, timeout=10000)

    for i in range(3):
        thumb = cache.get(i)
        assert thumb is not None
        assert isinstance(thumb, QPixmap)
        assert thumb.width() > 0

    cache.shutdown()
    doc.close()


def test_get_returns_none_before_render() -> None:
    doc = MagicMock()
    pages = [
        PageInfo(index=0, width=612, height=792, rotation=0, has_text=True, annotation_count=0),
    ]
    cache = ThumbnailCache(doc_handle=doc, pages=pages, thumb_width=90)
    assert cache.get(0) is None


def test_thumbnail_ready_signal(valid_pdf: Path, qtbot: object) -> None:
    doc = pymupdf.open(str(valid_pdf))
    pages = [
        PageInfo(index=i, width=612, height=792, rotation=0, has_text=True, annotation_count=0)
        for i in range(doc.page_count)
    ]
    cache = ThumbnailCache(doc_handle=doc, pages=pages, thumb_width=90)
    ready_spy = MagicMock()
    cache.thumbnail_ready.connect(ready_spy)

    cache.start()

    def check_all() -> None:
        assert ready_spy.call_count == 3

    qtbot.waitUntil(check_all, timeout=10000)

    cache.shutdown()
    doc.close()
