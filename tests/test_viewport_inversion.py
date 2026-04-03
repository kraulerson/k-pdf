"""Tests for PdfViewport PDF inversion mode."""

from __future__ import annotations

from PySide6.QtGui import QColor, QImage, QPixmap

from k_pdf.core.document_model import PageInfo
from k_pdf.views.pdf_viewport import PdfViewport


class TestViewportInversion:
    def test_invert_pdf_default_false(self, qapp) -> None:
        vp = PdfViewport()
        assert vp.invert_pdf is False

    def test_set_invert_pdf_true(self, qapp) -> None:
        vp = PdfViewport()
        vp.set_invert_pdf(True)
        assert vp.invert_pdf is True

    def test_set_invert_pdf_false(self, qapp) -> None:
        vp = PdfViewport()
        vp.set_invert_pdf(True)
        vp.set_invert_pdf(False)
        assert vp.invert_pdf is False

    def test_set_page_pixmap_inverts_when_flag_true(self, qapp) -> None:
        """Verify pixel color is inverted when inversion is enabled."""
        vp = PdfViewport()
        pages = [
            PageInfo(index=0, width=100, height=100, rotation=0, has_text=False, annotation_count=0)
        ]
        vp.set_document(pages, zoom=1.0)

        # Create a white pixmap
        white_pixmap = QPixmap(100, 100)
        white_pixmap.fill(QColor(255, 255, 255))

        vp.set_invert_pdf(True)
        vp.set_page_pixmap(0, white_pixmap)

        # Get the displayed pixmap item
        item = vp._page_items.get(0)
        assert item is not None
        displayed_pixmap = item.pixmap()
        image = displayed_pixmap.toImage()

        # After inversion, white (255,255,255) should become black (0,0,0)
        center_color = QColor(image.pixel(50, 50))
        assert center_color.red() == 0
        assert center_color.green() == 0
        assert center_color.blue() == 0

    def test_set_page_pixmap_no_inversion_when_flag_false(self, qapp) -> None:
        """Verify pixel color is unchanged when inversion is disabled."""
        vp = PdfViewport()
        pages = [
            PageInfo(index=0, width=100, height=100, rotation=0, has_text=False, annotation_count=0)
        ]
        vp.set_document(pages, zoom=1.0)

        # Create a white pixmap
        white_pixmap = QPixmap(100, 100)
        white_pixmap.fill(QColor(255, 255, 255))

        vp.set_invert_pdf(False)
        vp.set_page_pixmap(0, white_pixmap)

        item = vp._page_items.get(0)
        assert item is not None
        displayed_pixmap = item.pixmap()
        image = displayed_pixmap.toImage()

        center_color = QColor(image.pixel(50, 50))
        assert center_color.red() == 255
        assert center_color.green() == 255
        assert center_color.blue() == 255

    def test_inversion_preserves_alpha(self, qapp) -> None:
        """Verify that invertPixels with InvertRgb preserves alpha channel."""
        vp = PdfViewport()
        pages = [
            PageInfo(index=0, width=50, height=50, rotation=0, has_text=False, annotation_count=0)
        ]
        vp.set_document(pages, zoom=1.0)

        # Use a fully opaque image to test inversion without alpha complications
        img = QImage(50, 50, QImage.Format.Format_ARGB32)
        img.fill(QColor(200, 100, 50, 255))
        pixmap = QPixmap.fromImage(img)

        vp.set_invert_pdf(True)
        vp.set_page_pixmap(0, pixmap)

        item = vp._page_items.get(0)
        assert item is not None
        displayed = item.pixmap().toImage()

        center_color = QColor(displayed.pixel(25, 25))
        # RGB should be inverted: 200->55, 100->155, 50->205
        assert center_color.red() == 55
        assert center_color.green() == 155
        assert center_color.blue() == 205
        # Alpha preserved (fully opaque)
        assert center_color.alpha() == 255

    def test_red_pixmap_inverts_to_cyan(self, qapp) -> None:
        """Verify that red inverts to cyan."""
        vp = PdfViewport()
        pages = [
            PageInfo(index=0, width=20, height=20, rotation=0, has_text=False, annotation_count=0)
        ]
        vp.set_document(pages, zoom=1.0)

        red_pixmap = QPixmap(20, 20)
        red_pixmap.fill(QColor(255, 0, 0))

        vp.set_invert_pdf(True)
        vp.set_page_pixmap(0, red_pixmap)

        item = vp._page_items.get(0)
        assert item is not None
        displayed = item.pixmap().toImage()

        c = QColor(displayed.pixel(10, 10))
        assert c.red() == 0
        assert c.green() == 255
        assert c.blue() == 255
