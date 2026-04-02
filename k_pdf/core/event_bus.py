"""Qt signal-based event system.

Singleton signal hub for app-wide events. Components connect to
signals here rather than directly to each other, reducing coupling.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal


class EventBus(QObject):
    """Central signal bus for application-wide events."""

    # File operations
    file_open_requested = Signal(Path)
    document_ready = Signal(object)  # DocumentModel
    document_closed = Signal(str)  # session_id

    # Error signals
    error_occurred = Signal(str, str)  # (title, message)
    password_required = Signal(Path)

    # Page rendering
    page_ready = Signal(int, object)  # (page_index, QPixmap)
    pages_requested = Signal(list)  # list[int] page indices

    # Status updates
    status_message = Signal(str)  # status bar text
    loading_progress = Signal(int)  # 0-100 percentage


# Module-level singleton
_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    """Return the global EventBus singleton.

    Creates the instance on first call. Must be called after QApplication exists.
    """
    global _bus
    if _bus is None:
        _bus = EventBus()
    return _bus
