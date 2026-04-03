"""Per-tab undo/redo stack.

Each tab maintains its own UndoManager with a capped stack of UndoAction
objects. Actions capture reversible operations via undo_fn/redo_fn callables.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal

logger = logging.getLogger("k_pdf.core.undo_manager")

_DEFAULT_MAX_SIZE = 50


@dataclass
class UndoAction:
    """A reversible action for the undo/redo stack.

    Attributes:
        description: Human-readable label (e.g. "Add Highlight").
        undo_fn: Callable that reverses the action.
        redo_fn: Callable that re-applies the action.
    """

    description: str
    undo_fn: Callable[[], None]
    redo_fn: Callable[[], None]


class UndoManager(QObject):
    """Per-tab undo/redo stack with configurable size limit.

    Maintains two stacks (undo and redo). Pushing a new action clears
    the redo stack. Undo moves the top action to redo and calls its
    undo_fn. Redo moves the top redo action back and calls redo_fn.
    """

    state_changed = Signal()

    def __init__(
        self,
        max_size: int = _DEFAULT_MAX_SIZE,
        parent: QObject | None = None,
    ) -> None:
        """Initialize the undo manager.

        Args:
            max_size: Maximum number of actions to keep on the undo stack.
            parent: Optional parent QObject.
        """
        super().__init__(parent)
        self._undo_stack: list[UndoAction] = []
        self._redo_stack: list[UndoAction] = []
        self._max_size = max_size

    @property
    def max_size(self) -> int:
        """Return the maximum stack size."""
        return self._max_size

    @property
    def can_undo(self) -> bool:
        """Return True if there are actions to undo."""
        return len(self._undo_stack) > 0

    @property
    def can_redo(self) -> bool:
        """Return True if there are actions to redo."""
        return len(self._redo_stack) > 0

    @property
    def undo_description(self) -> str:
        """Return the description of the next action to undo, or empty string."""
        if self._undo_stack:
            return self._undo_stack[-1].description
        return ""

    @property
    def redo_description(self) -> str:
        """Return the description of the next action to redo, or empty string."""
        if self._redo_stack:
            return self._redo_stack[-1].description
        return ""

    def push(self, action: UndoAction) -> None:
        """Push an action onto the undo stack.

        Clears the redo stack and trims the undo stack to max_size.

        Args:
            action: The action to push.
        """
        self._redo_stack.clear()
        self._undo_stack.append(action)

        # Trim oldest if over limit
        if len(self._undo_stack) > self._max_size:
            self._undo_stack = self._undo_stack[-self._max_size :]

        self.state_changed.emit()
        logger.debug(
            "Pushed undo action: %s (stack size: %d)",
            action.description,
            len(self._undo_stack),
        )

    def undo(self) -> None:
        """Undo the most recent action.

        Pops from undo stack, calls undo_fn, pushes to redo stack.
        No-op if undo stack is empty.
        """
        if not self._undo_stack:
            return

        action = self._undo_stack.pop()
        action.undo_fn()
        self._redo_stack.append(action)

        self.state_changed.emit()
        logger.debug("Undid action: %s", action.description)

    def redo(self) -> None:
        """Redo the most recently undone action.

        Pops from redo stack, calls redo_fn, pushes to undo stack.
        No-op if redo stack is empty.
        """
        if not self._redo_stack:
            return

        action = self._redo_stack.pop()
        action.redo_fn()
        self._undo_stack.append(action)

        self.state_changed.emit()
        logger.debug("Redid action: %s", action.description)

    def clear(self) -> None:
        """Clear both undo and redo stacks."""
        self._undo_stack.clear()
        self._redo_stack.clear()
        self.state_changed.emit()
        logger.debug("Cleared undo/redo stacks")
