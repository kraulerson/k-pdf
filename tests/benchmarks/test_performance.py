"""Performance benchmarks for large-document operations.

Run with:  pytest tests/benchmarks/ -m slow -v
Skip with: pytest -m "not slow"

Uses plain time.perf_counter() timing with upper-bound assertions.
"""

from __future__ import annotations

import sys
import time

if sys.platform != "win32":
    import resource
from pathlib import Path

import pymupdf
import pytest
from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QGuiApplication

from k_pdf.core.thumbnail_cache import ThumbnailCache
from k_pdf.services.page_engine import PageEngine
from k_pdf.services.pdf_engine import PdfEngine
from k_pdf.services.search_engine import SearchWorker

# ---------------------------------------------------------------------------
# Timing helpers
# ---------------------------------------------------------------------------

SLOW = pytest.mark.slow


def _timed(fn):
    """Execute *fn* and return (result, elapsed_seconds)."""
    start = time.perf_counter()
    result = fn()
    elapsed = time.perf_counter() - start
    return result, elapsed


def _rss_mb() -> float:
    """Return current RSS in megabytes (macOS/Linux). Returns 0 on Windows."""
    if sys.platform == "win32":
        return 0.0
    usage = resource.getrusage(resource.RUSAGE_SELF)  # type: ignore[name-defined]
    # macOS reports in bytes, Linux in kilobytes
    if sys.platform == "darwin":
        return usage.ru_maxrss / (1024 * 1024)
    return usage.ru_maxrss / 1024


# ---------------------------------------------------------------------------
# Fixtures — generate large PDFs once per test session
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def _qapp():
    """Ensure a QGuiApplication exists for the session (needed by QImage/QPixmap)."""
    app = QGuiApplication.instance() or QCoreApplication.instance()
    if app is None:
        app = QGuiApplication([])
    return app


@pytest.fixture(scope="session")
def large_pdf_500(tmp_path_factory) -> Path:
    """Generate a 500-page PDF with text content on every page."""
    path = tmp_path_factory.mktemp("bench") / "large_500.pdf"
    doc = pymupdf.open()
    for i in range(500):
        page = doc.new_page(width=612, height=792)
        page.insert_text(pymupdf.Point(72, 72), f"Page {i + 1} benchmark content")
        page.insert_text(pymupdf.Point(72, 120), f"Lorem ipsum dolor sit amet {i}")
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture(scope="session")
def large_pdf_100(tmp_path_factory) -> Path:
    """Generate a 100-page PDF with text content on every page."""
    path = tmp_path_factory.mktemp("bench") / "large_100.pdf"
    doc = pymupdf.open()
    for i in range(100):
        page = doc.new_page(width=612, height=792)
        page.insert_text(pymupdf.Point(72, 72), f"Page {i + 1} benchmark content")
        page.insert_text(pymupdf.Point(72, 120), f"Lorem ipsum dolor sit amet {i}")
        if i % 10 == 0:
            page.insert_text(pymupdf.Point(72, 168), "NEEDLE_SEARCH_TARGET")
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture(scope="session")
def source_pdf_10(tmp_path_factory) -> Path:
    """Generate a 10-page PDF to use as an insert source."""
    path = tmp_path_factory.mktemp("bench") / "source_10.pdf"
    doc = pymupdf.open()
    for i in range(10):
        page = doc.new_page(width=612, height=792)
        page.insert_text(pymupdf.Point(72, 72), f"Inserted page {i + 1}")
    doc.save(str(path))
    doc.close()
    return path


# ---------------------------------------------------------------------------
# 1. Document open time
# ---------------------------------------------------------------------------


@SLOW
class TestDocumentOpenPerformance:
    """Benchmark: opening large PDFs via PdfEngine."""

    def test_open_500_page_pdf(self, large_pdf_500: Path) -> None:
        """Opening a 500-page PDF should complete in under 10 seconds."""
        engine = PdfEngine()
        result, elapsed = _timed(lambda: engine.open_document(large_pdf_500))
        engine.close_document(result.doc_handle)

        print(f"\n  [BENCH] Open 500-page PDF: {elapsed:.3f}s")
        assert elapsed < 10.0, f"Open took {elapsed:.3f}s, expected < 10s"

    def test_open_100_page_pdf(self, large_pdf_100: Path) -> None:
        """Opening a 100-page PDF should complete in under 3 seconds."""
        engine = PdfEngine()
        result, elapsed = _timed(lambda: engine.open_document(large_pdf_100))
        engine.close_document(result.doc_handle)

        print(f"\n  [BENCH] Open 100-page PDF: {elapsed:.3f}s")
        assert elapsed < 3.0, f"Open took {elapsed:.3f}s, expected < 3s"


# ---------------------------------------------------------------------------
# 2. Page render time
# ---------------------------------------------------------------------------


@SLOW
class TestPageRenderPerformance:
    """Benchmark: rendering a single page at various zoom levels."""

    @pytest.mark.parametrize("zoom", [1.0, 2.0, 4.0], ids=["1x", "2x", "4x"])
    def test_render_single_page(self, _qapp, large_pdf_500: Path, zoom: float) -> None:
        """Rendering one page should complete in under 1 second at any zoom."""
        engine = PdfEngine()
        result = engine.open_document(large_pdf_500)
        doc = result.doc_handle

        _, elapsed = _timed(lambda: engine.render_page(doc, 0, zoom=zoom))
        engine.close_document(doc)

        print(f"\n  [BENCH] Render page @{zoom}x zoom: {elapsed:.3f}s")
        assert elapsed < 1.0, f"Render took {elapsed:.3f}s at {zoom}x, expected < 1s"

    def test_render_10_pages_sequential(self, _qapp, large_pdf_500: Path) -> None:
        """Rendering 10 pages sequentially should complete in under 5 seconds."""
        engine = PdfEngine()
        result = engine.open_document(large_pdf_500)
        doc = result.doc_handle

        def render_batch():
            for i in range(10):
                engine.render_page(doc, i, zoom=1.5)

        _, elapsed = _timed(render_batch)
        engine.close_document(doc)

        print(f"\n  [BENCH] Render 10 pages @1.5x: {elapsed:.3f}s")
        assert elapsed < 5.0, f"Batch render took {elapsed:.3f}s, expected < 5s"


# ---------------------------------------------------------------------------
# 3. Thumbnail generation time
# ---------------------------------------------------------------------------


@SLOW
class TestThumbnailPerformance:
    """Benchmark: ThumbnailCache pre-rendering for 100 pages."""

    def test_thumbnail_generation_100_pages(self, _qapp, large_pdf_100: Path) -> None:
        """Pre-rendering 100 thumbnails should complete in under 10 seconds."""
        engine = PdfEngine()
        result = engine.open_document(large_pdf_100)
        doc = result.doc_handle
        pages = result.pages

        cache = ThumbnailCache(doc_handle=doc, pages=pages, thumb_width=90)

        rendered_count = 0

        def on_thumb(index, _img):
            nonlocal rendered_count
            rendered_count += 1

        cache.thumbnail_ready.connect(on_thumb)

        start = time.perf_counter()
        cache.start()

        # Process events until all thumbnails are rendered or timeout
        deadline = start + 15.0
        while rendered_count < len(pages) and time.perf_counter() < deadline:
            QCoreApplication.processEvents()

        elapsed = time.perf_counter() - start
        cache.shutdown()
        engine.close_document(doc)

        print(f"\n  [BENCH] Thumbnail gen 100 pages: {elapsed:.3f}s ({rendered_count} rendered)")
        assert rendered_count == len(pages), (
            f"Only {rendered_count}/{len(pages)} thumbnails rendered"
        )
        assert elapsed < 10.0, f"Thumbnail gen took {elapsed:.3f}s, expected < 10s"


# ---------------------------------------------------------------------------
# 4. Search time
# ---------------------------------------------------------------------------


@SLOW
class TestSearchPerformance:
    """Benchmark: full-document search on 100 pages."""

    def test_search_all_pages(self, _qapp, large_pdf_100: Path) -> None:
        """Searching 100 pages for a string should complete in under 5 seconds."""
        engine = PdfEngine()
        result = engine.open_document(large_pdf_100)
        doc = result.doc_handle

        worker = SearchWorker()
        total_matches = 0
        search_done = False

        def on_page_matches(_page_idx, rects):
            nonlocal total_matches
            total_matches += len(rects)

        def on_complete(_count):
            nonlocal search_done
            search_done = True

        worker.page_matches.connect(on_page_matches)
        worker.search_complete.connect(on_complete)

        start = time.perf_counter()
        worker.search(
            doc,
            "NEEDLE_SEARCH_TARGET",
            doc.page_count,
            case_sensitive=True,
            whole_word=False,
        )
        elapsed = time.perf_counter() - start

        engine.close_document(doc)

        print(f"\n  [BENCH] Search 100 pages: {elapsed:.3f}s ({total_matches} matches)")
        assert search_done, "Search did not complete"
        assert total_matches > 0, "Expected at least one match"
        assert elapsed < 5.0, f"Search took {elapsed:.3f}s, expected < 5s"

    def test_search_no_results(self, _qapp, large_pdf_100: Path) -> None:
        """Searching for a non-existent string should still be fast."""
        engine = PdfEngine()
        result = engine.open_document(large_pdf_100)
        doc = result.doc_handle

        worker = SearchWorker()
        search_done = False

        def on_complete(_count):
            nonlocal search_done
            search_done = True

        worker.search_complete.connect(on_complete)

        start = time.perf_counter()
        worker.search(
            doc,
            "ZZZZZ_NONEXISTENT_STRING_12345",
            doc.page_count,
            case_sensitive=True,
            whole_word=False,
        )
        elapsed = time.perf_counter() - start

        engine.close_document(doc)

        print(f"\n  [BENCH] Search 100 pages (no match): {elapsed:.3f}s")
        assert search_done, "Search did not complete"
        assert elapsed < 5.0, f"Search took {elapsed:.3f}s, expected < 5s"


# ---------------------------------------------------------------------------
# 5. Page management operations
# ---------------------------------------------------------------------------


@SLOW
class TestPageManagementPerformance:
    """Benchmark: page manipulation on 100-page documents."""

    def _fresh_doc(self, path: Path):
        """Open a fresh copy for mutation tests."""
        return pymupdf.open(str(path))

    def test_delete_pages(self, large_pdf_100: Path) -> None:
        """Deleting 10 pages from a 100-page doc should take under 2 seconds."""
        engine = PageEngine()
        doc = self._fresh_doc(large_pdf_100)
        indices = list(range(0, 100, 10))  # delete every 10th page

        _, elapsed = _timed(lambda: engine.delete_pages(doc, indices))
        doc.close()

        print(f"\n  [BENCH] Delete 10 pages from 100: {elapsed:.3f}s")
        assert elapsed < 2.0, f"Delete took {elapsed:.3f}s, expected < 2s"

    def test_rotate_pages(self, large_pdf_100: Path) -> None:
        """Rotating all 100 pages should take under 2 seconds."""
        engine = PageEngine()
        doc = self._fresh_doc(large_pdf_100)
        all_indices = list(range(doc.page_count))

        _, elapsed = _timed(lambda: engine.rotate_pages(doc, all_indices, 90))
        doc.close()

        print(f"\n  [BENCH] Rotate 100 pages: {elapsed:.3f}s")
        assert elapsed < 2.0, f"Rotate took {elapsed:.3f}s, expected < 2s"

    def test_insert_pages(self, large_pdf_100: Path, source_pdf_10: Path) -> None:
        """Inserting 10 pages into a 100-page doc should take under 2 seconds."""
        engine = PageEngine()
        doc = self._fresh_doc(large_pdf_100)

        _, elapsed = _timed(lambda: engine.insert_pages_from(doc, source_pdf_10, 50))
        doc.close()

        print(f"\n  [BENCH] Insert 10 pages at index 50: {elapsed:.3f}s")
        assert elapsed < 2.0, f"Insert took {elapsed:.3f}s, expected < 2s"

    def test_move_page(self, large_pdf_100: Path) -> None:
        """Moving a page in a 100-page doc should take under 1 second."""
        engine = PageEngine()
        doc = self._fresh_doc(large_pdf_100)

        _, elapsed = _timed(lambda: engine.move_page(doc, 0, 99))
        doc.close()

        print(f"\n  [BENCH] Move page 0 -> 99: {elapsed:.3f}s")
        assert elapsed < 1.0, f"Move took {elapsed:.3f}s, expected < 1s"


# ---------------------------------------------------------------------------
# 6. Memory usage
# ---------------------------------------------------------------------------


@SLOW
class TestMemoryUsage:
    """Benchmark: RSS change after opening a large document."""

    def test_memory_after_open_500_pages(self, _qapp, large_pdf_500: Path) -> None:
        """Opening a 500-page PDF should not increase RSS by more than 200 MB."""
        engine = PdfEngine()
        rss_before = _rss_mb()

        result = engine.open_document(large_pdf_500)
        rss_after = _rss_mb()
        delta = rss_after - rss_before

        engine.close_document(result.doc_handle)

        print(f"\n  [BENCH] Memory delta (500-page open): {delta:.1f} MB")
        print(f"          RSS before: {rss_before:.1f} MB, after: {rss_after:.1f} MB")
        assert delta < 200.0, f"RSS grew by {delta:.1f} MB, expected < 200 MB"

    def test_memory_after_render_burst(self, _qapp, large_pdf_500: Path) -> None:
        """Rendering 50 pages at 2x zoom should not push RSS up more than 500 MB."""
        engine = PdfEngine()
        result = engine.open_document(large_pdf_500)
        doc = result.doc_handle

        rss_before = _rss_mb()
        for i in range(50):
            engine.render_page(doc, i, zoom=2.0)
        rss_after = _rss_mb()
        delta = rss_after - rss_before

        engine.close_document(doc)

        print(f"\n  [BENCH] Memory delta (50 renders @2x): {delta:.1f} MB")
        print(f"          RSS before: {rss_before:.1f} MB, after: {rss_after:.1f} MB")
        assert delta < 500.0, f"RSS grew by {delta:.1f} MB, expected < 500 MB"
