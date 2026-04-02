"""Document text search bar.

Non-modal search widget with text input, match counter, navigation
buttons, case/whole-word toggles, and close button. Starts hidden.
Activated by Ctrl+F from the main window.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QTimer, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QWidget,
)

logger = logging.getLogger("k_pdf.views.search_bar")


class SearchBar(QWidget):
    """Search bar with input, toggles, match counter, and navigation."""

    search_requested = Signal(str, bool, bool)  # (query, case_sensitive, whole_word)
    next_requested = Signal()
    previous_requested = Signal()
    closed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the search bar, hidden by default."""
        super().__init__(parent)
        self.hide()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(4)

        # Search input
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Find in document...")
        self._search_input.setClearButtonEnabled(True)
        self._search_input.setMinimumWidth(200)
        layout.addWidget(self._search_input)

        # Match counter label
        self._match_label = QLabel("")
        self._match_label.setMinimumWidth(120)
        layout.addWidget(self._match_label)

        # Previous button
        self._prev_btn = QPushButton("Previous")
        self._prev_btn.setToolTip("Previous match (Shift+Enter)")
        self._prev_btn.clicked.connect(self.previous_requested.emit)
        layout.addWidget(self._prev_btn)

        # Next button
        self._next_btn = QPushButton("Next")
        self._next_btn.setToolTip("Next match (Enter)")
        self._next_btn.clicked.connect(self.next_requested.emit)
        layout.addWidget(self._next_btn)

        # Case-sensitive toggle
        self._case_btn = QPushButton("Aa")
        self._case_btn.setToolTip("Case sensitive")
        self._case_btn.setCheckable(True)
        self._case_btn.setMaximumWidth(36)
        self._case_btn.clicked.connect(self._on_toggle_changed)
        layout.addWidget(self._case_btn)

        # Whole-word toggle
        self._word_btn = QPushButton("W")
        self._word_btn.setToolTip("Whole word")
        self._word_btn.setCheckable(True)
        self._word_btn.setMaximumWidth(36)
        self._word_btn.clicked.connect(self._on_toggle_changed)
        layout.addWidget(self._word_btn)

        # Close button
        self._close_btn = QPushButton("\u00d7")
        self._close_btn.setToolTip("Close search bar (Escape)")
        self._close_btn.setMaximumWidth(30)
        self._close_btn.clicked.connect(self.closed.emit)
        layout.addWidget(self._close_btn)

        # Debounce timer for search input
        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(300)
        self._debounce_timer.timeout.connect(self._emit_search)

        # Connect text changes to debounced search
        self._search_input.textChanged.connect(self._on_text_changed)

        # Enter -> next, Shift+Enter -> previous
        self._search_input.returnPressed.connect(self.next_requested.emit)

        # Escape closes the search bar
        escape_shortcut = QShortcut(QKeySequence("Escape"), self)
        escape_shortcut.activated.connect(self.closed.emit)

    def set_match_count(self, current: int, total: int) -> None:
        """Update the match counter label.

        Args:
            current: Current match number (1-based).
            total: Total match count.
        """
        word = "match" if total == 1 else "matches"
        self._match_label.setText(f"{current} of {total} {word}")

    def set_no_text_layer(self) -> None:
        """Show message indicating the document has no searchable text."""
        self._match_label.setText("This document has no searchable text.")

    def set_no_matches(self) -> None:
        """Show 'No matches found' message."""
        self._match_label.setText("No matches found")

    def focus_input(self) -> None:
        """Focus the search text input field."""
        self._search_input.setFocus()
        self._search_input.selectAll()

    def clear(self) -> None:
        """Reset the search bar to its initial state."""
        self._search_input.blockSignals(True)
        self._search_input.clear()
        self._search_input.blockSignals(False)
        self._match_label.setText("")
        self._case_btn.setChecked(False)
        self._word_btn.setChecked(False)

    def _on_text_changed(self, _text: str) -> None:
        """Restart debounce timer when search text changes."""
        self._debounce_timer.start()

    def _on_toggle_changed(self) -> None:
        """Handle toggle button state change -- trigger search immediately."""
        if self._search_input.text():
            self._emit_search()

    def _emit_search(self) -> None:
        """Emit search_requested with current query and toggle states."""
        query = self._search_input.text()
        case_sensitive = self._case_btn.isChecked()
        whole_word = self._word_btn.isChecked()
        self.search_requested.emit(query, case_sensitive, whole_word)
