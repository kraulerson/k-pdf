"""Find and replace bar — two-row search and replace widget.

Row 1: Search input, match counter, Previous/Next, Aa toggle, W toggle, Close.
Row 2: Replace input, Replace button, Replace All button.

Activated via Edit > Find and Replace (Ctrl+H). The existing SearchBar
(Ctrl+F) remains unchanged for search-only use.
"""

from __future__ import annotations

import logging
from typing import override

from PySide6.QtCore import QEvent, QObject, Qt, QTimer, Signal
from PySide6.QtGui import QKeyEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger("k_pdf.views.find_replace_bar")


class FindReplaceBar(QWidget):
    """Two-row find and replace bar with search and replacement controls.

    Signals:
        search_requested: (query, case_sensitive, whole_word)
        next_requested: Navigate to next match.
        previous_requested: Navigate to previous match.
        replace_requested: (replacement_text) Replace current match.
        replace_all_requested: (replacement_text) Replace all matches.
        closed: Bar was closed.
    """

    search_requested = Signal(str, bool, bool)
    next_requested = Signal()
    previous_requested = Signal()
    replace_requested = Signal(str)  # replacement text
    replace_all_requested = Signal(str)  # replacement text
    closed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the find-and-replace bar, hidden by default."""
        super().__init__(parent)
        self.hide()

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(6, 4, 6, 4)
        main_layout.setSpacing(2)

        # --- Row 1: Search ---
        row1 = QHBoxLayout()
        row1.setSpacing(4)

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Find in document...")
        self._search_input.setClearButtonEnabled(True)
        self._search_input.setMinimumWidth(200)
        self._search_input.setAccessibleName("Search text")
        row1.addWidget(self._search_input)

        self._match_label = QLabel("")
        self._match_label.setMinimumWidth(120)
        self._match_label.setAccessibleName("Match count")
        row1.addWidget(self._match_label)

        self._prev_btn = QPushButton("Previous")
        self._prev_btn.setToolTip("Previous match (Shift+Enter)")
        self._prev_btn.setAccessibleName("Previous match")
        self._prev_btn.clicked.connect(self.previous_requested.emit)
        row1.addWidget(self._prev_btn)

        self._next_btn = QPushButton("Next")
        self._next_btn.setToolTip("Next match (Enter)")
        self._next_btn.setAccessibleName("Next match")
        self._next_btn.clicked.connect(self.next_requested.emit)
        row1.addWidget(self._next_btn)

        self._case_btn = QPushButton("Aa")
        self._case_btn.setToolTip("Case sensitive")
        self._case_btn.setAccessibleName("Case sensitive toggle")
        self._case_btn.setCheckable(True)
        self._case_btn.setMaximumWidth(36)
        self._case_btn.clicked.connect(self._on_toggle_changed)
        row1.addWidget(self._case_btn)

        self._word_btn = QPushButton("W")
        self._word_btn.setToolTip("Whole word")
        self._word_btn.setAccessibleName("Whole word toggle")
        self._word_btn.setCheckable(True)
        self._word_btn.setMaximumWidth(36)
        self._word_btn.clicked.connect(self._on_toggle_changed)
        row1.addWidget(self._word_btn)

        self._close_btn = QPushButton("\u00d7")
        self._close_btn.setToolTip("Close (Escape)")
        self._close_btn.setAccessibleName("Close find and replace")
        self._close_btn.setMaximumWidth(30)
        self._close_btn.clicked.connect(self.closed.emit)
        row1.addWidget(self._close_btn)

        main_layout.addLayout(row1)

        # --- Row 2: Replace ---
        row2 = QHBoxLayout()
        row2.setSpacing(4)

        self._replace_input = QLineEdit()
        self._replace_input.setPlaceholderText("Replace with...")
        self._replace_input.setMinimumWidth(200)
        self._replace_input.setAccessibleName("Replacement text")
        row2.addWidget(self._replace_input)

        self._replace_btn = QPushButton("Replace")
        self._replace_btn.setToolTip("Replace current match")
        self._replace_btn.setAccessibleName("Replace current match")
        self._replace_btn.clicked.connect(self._on_replace)
        row2.addWidget(self._replace_btn)

        self._replace_all_btn = QPushButton("Replace All")
        self._replace_all_btn.setToolTip("Replace all matches")
        self._replace_all_btn.setAccessibleName("Replace all matches")
        self._replace_all_btn.clicked.connect(self._on_replace_all)
        row2.addWidget(self._replace_all_btn)

        row2.addStretch()
        main_layout.addLayout(row2)

        # Debounce timer for search input
        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(300)
        self._debounce_timer.timeout.connect(self._emit_search)

        self._search_input.textChanged.connect(self._on_text_changed)
        self._search_input.installEventFilter(self)

        # Escape closes the bar
        escape_shortcut = QShortcut(QKeySequence("Escape"), self)
        escape_shortcut.activated.connect(self.closed.emit)

    @override
    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        """Intercept Return/Shift+Return on the search input.

        Args:
            obj: The watched object.
            event: The event.

        Returns:
            True if the event was handled, False otherwise.
        """
        if obj is self._search_input and event.type() == QEvent.Type.KeyPress:
            key_event: QKeyEvent = event  # type: ignore[assignment]
            if key_event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if key_event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                    self.previous_requested.emit()
                else:
                    self.next_requested.emit()
                return True
        return super().eventFilter(obj, event)

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

    def set_status(self, message: str) -> None:
        """Show a status message in the match label area.

        Args:
            message: The status text to display.
        """
        self._match_label.setText(message)

    def focus_input(self) -> None:
        """Focus the search text input field."""
        self._search_input.setFocus()
        self._search_input.selectAll()

    def clear(self) -> None:
        """Reset the bar to its initial state."""
        self._search_input.blockSignals(True)
        self._search_input.clear()
        self._search_input.blockSignals(False)
        self._replace_input.clear()
        self._match_label.setText("")
        self._case_btn.setChecked(False)
        self._word_btn.setChecked(False)

    def _on_text_changed(self, _text: str) -> None:
        """Restart debounce timer when search text changes."""
        self._debounce_timer.start()

    def _on_toggle_changed(self) -> None:
        """Handle toggle button state change — trigger search immediately."""
        if self._search_input.text():
            self._emit_search()

    def _emit_search(self) -> None:
        """Emit search_requested with current query and toggle states."""
        query = self._search_input.text()
        case_sensitive = self._case_btn.isChecked()
        whole_word = self._word_btn.isChecked()
        self.search_requested.emit(query, case_sensitive, whole_word)

    def _on_replace(self) -> None:
        """Emit replace_requested with the replacement text."""
        self.replace_requested.emit(self._replace_input.text())

    def _on_replace_all(self) -> None:
        """Emit replace_all_requested with the replacement text."""
        self.replace_all_requested.emit(self._replace_input.text())
