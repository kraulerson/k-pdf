"""QApplication shell and event bus initialization.

Creates the main window, tab manager, and wires signals together.
Handles CLI file arguments.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from k_pdf.persistence.recent_files import RecentFiles
from k_pdf.persistence.settings_db import init_db
from k_pdf.presenters.navigation_presenter import NavigationPresenter
from k_pdf.presenters.search_presenter import SearchPresenter
from k_pdf.presenters.tab_manager import TabManager
from k_pdf.views.main_window import MainWindow

logger = logging.getLogger("k_pdf.app")


class KPdfApp:
    """Application controller — wires TabManager to views."""

    def __init__(self, app: QApplication, file_path: str | None = None) -> None:
        """Initialize the app controller.

        Args:
            app: The QApplication instance.
            file_path: Optional path to open on startup (from CLI args).
        """
        self._app = app
        self._db = init_db()
        self._recent_files = RecentFiles(self._db)
        self._window = MainWindow()
        self._tab_manager = TabManager(
            tab_widget=self._window.tab_widget,
            recent_files=self._recent_files,
        )
        self._nav_presenter = NavigationPresenter(
            tab_manager=self._tab_manager,
        )
        self._search_presenter = SearchPresenter(
            tab_manager=self._tab_manager,
        )
        self._initial_file = file_path

        self._connect_signals()
        self._window.show()

        # Open file from CLI argument after event loop starts
        if self._initial_file:
            QTimer.singleShot(0, self._open_initial_file)

    @property
    def window(self) -> MainWindow:
        """Return the main window."""
        return self._window

    @property
    def tab_manager(self) -> TabManager:
        """Return the tab manager."""
        return self._tab_manager

    @property
    def navigation_presenter(self) -> NavigationPresenter:
        """Return the navigation presenter."""
        return self._nav_presenter

    @property
    def search_presenter(self) -> SearchPresenter:
        """Return the search presenter."""
        return self._search_presenter

    def _connect_signals(self) -> None:
        """Wire MainWindow signals to TabManager and vice versa."""
        # View → TabManager
        self._window.file_open_requested.connect(self._tab_manager.open_file)
        self._window.tab_close_requested.connect(self._on_close_current_tab)
        self._window.password_submitted.connect(self._on_password_submitted)

        # TabManager → View
        self._tab_manager.error_occurred.connect(self._window.show_error)
        self._tab_manager.password_requested.connect(self._window.show_password_dialog)
        self._tab_manager.status_message.connect(self._window.update_status_message)
        self._tab_manager.active_page_status.connect(self._window.update_page_status)
        self._tab_manager.tab_count_changed.connect(self._on_tab_count_changed)

        # NavigationPresenter → NavigationPanel
        nav = self._nav_presenter
        panel = self._window.navigation_panel
        nav.thumbnail_ready.connect(panel.add_thumbnail)
        nav.outline_ready.connect(panel.set_outline)
        nav.active_thumbnail_changed.connect(panel.set_current_page)

        # NavigationPanel → NavigationPresenter
        panel.thumbnail_clicked.connect(nav.navigate_to_page)
        panel.outline_clicked.connect(nav.navigate_to_page)

        # Clear panel on tab switch and when all tabs close
        self._tab_manager.tab_switched.connect(lambda _: panel.clear())
        self._tab_manager.tab_count_changed.connect(self._on_nav_tab_count)

        # SearchBar -> SearchPresenter
        search_bar = self._window.search_bar
        search_bar.search_requested.connect(
            lambda q, cs, ww: self._search_presenter.start_search(
                q, case_sensitive=cs, whole_word=ww
            )
        )
        search_bar.next_requested.connect(self._search_presenter.next_match)
        search_bar.previous_requested.connect(self._search_presenter.previous_match)
        search_bar.closed.connect(self._search_presenter.close_search)

        # SearchPresenter -> SearchBar
        sp = self._search_presenter
        sp.matches_updated.connect(search_bar.set_match_count)
        sp.no_text_layer.connect(search_bar.set_no_text_layer)

        # SearchPresenter -> PdfViewport (highlight overlays)
        sp.highlight_page.connect(self._on_search_highlight_page)
        sp.clear_highlights.connect(self._on_search_clear_highlights)

    def _on_tab_count_changed(self, count: int) -> None:
        """Toggle between welcome screen and tab view."""
        if count == 0:
            self._window.show_welcome()
        else:
            self._window.show_tabs()

    def _on_close_current_tab(self) -> None:
        """Close the currently active tab."""
        sid = self._tab_manager.active_session_id
        if sid is not None:
            self._tab_manager.close_tab(sid)

    def _on_password_submitted(self, path: Path, password: str) -> None:
        """Forward password to the active tab's presenter."""
        presenter = self._tab_manager.get_active_presenter()
        if presenter is not None:
            presenter.open_file_with_password(path, password)

    def _open_initial_file(self) -> None:
        """Open the file passed via CLI argument."""
        if self._initial_file:
            self._tab_manager.open_file(Path(self._initial_file))

    def _on_nav_tab_count(self, count: int) -> None:
        """Clear navigation panel when all tabs close."""
        if count == 0:
            self._window.navigation_panel.clear()

    def _on_search_highlight_page(
        self,
        page_index: int,
        rects: list[tuple[float, float, float, float]],
    ) -> None:
        """Route highlight overlay to the active viewport."""
        viewport = self._tab_manager.get_active_viewport()
        if viewport is not None:
            viewport.add_search_highlights(page_index, rects, zoom=1.0)

    def _on_search_clear_highlights(self) -> None:
        """Clear search highlights on the active viewport."""
        viewport = self._tab_manager.get_active_viewport()
        if viewport is not None:
            viewport.clear_search_highlights()

    def shutdown(self) -> None:
        """Clean up resources before exit."""
        self._search_presenter.shutdown()
        self._nav_presenter.shutdown()
        self._tab_manager.shutdown()
