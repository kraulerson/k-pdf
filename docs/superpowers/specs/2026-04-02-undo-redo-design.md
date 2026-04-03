# Implicit Feature: Undo/Redo — Design Spec

**Date:** 2026-04-02
**Status:** Approved
**Depends on:** Feature 1 (Open/Render), Feature 2 (Multi-Tab), Feature 6 (Text Markup), Feature 7 (Sticky Notes), Feature 8 (Forms/Save), Feature 9 (Page Management)
**FRD Reference:** FUNCTIONAL_REQUIREMENTS.md — Implicit Features (Undo/Redo)
**UI Reference:** UI_SCAFFOLDING.md — Edit menu (Ctrl+Z / Ctrl+Shift+Z)

---

## 1. Architecture Overview

**UndoManager:** Core class in `k_pdf/core/undo_manager.py` (replaces existing stub). Maintains a per-tab undo stack and redo stack of `UndoAction` objects. Exposes `push()`, `undo()`, `redo()`, `can_undo`, `can_redo`, and `clear()`. Stack size capped at 50 actions. When a new action is pushed, the redo stack is cleared (standard undo semantics).

**UndoAction:** Frozen dataclass holding `description: str`, `undo_fn: Callable[[], None]`, and `redo_fn: Callable[[], None]`. Each presenter creates UndoAction instances that capture the before/after state of an operation.

**Per-tab stacks:** Each tab gets its own UndoManager instance stored in `TabContext`. When a tab closes, its UndoManager is discarded. When a tab switches, the Edit menu Undo/Redo actions reflect the new tab's stack state.

### Signal Flow

1. Presenter performs an operation -> creates `UndoAction` with captured undo/redo lambdas -> pushes to active tab's `UndoManager`
2. User triggers Undo (Ctrl+Z) -> `KPdfApp._on_undo()` -> gets active tab's `UndoManager` -> calls `undo()` -> executes `UndoAction.undo_fn` -> emits `state_changed`
3. User triggers Redo (Ctrl+Shift+Z) -> `KPdfApp._on_redo()` -> gets active tab's `UndoManager` -> calls `redo()` -> executes `UndoAction.redo_fn` -> emits `state_changed`
4. Tab switch -> `KPdfApp._on_tab_switched_undo()` -> updates Undo/Redo action enabled state + text from new tab's UndoManager
5. Tab close -> `TabManager.force_close_tab()` -> UndoManager discarded with TabContext

---

## 2. New / Modified Files

### `k_pdf/core/undo_manager.py` (replace stub)

**`UndoAction` (dataclass):**
- `description: str` — human-readable label (e.g. "Add Highlight")
- `undo_fn: Callable[[], None]` — callable that reverses the action
- `redo_fn: Callable[[], None]` — callable that re-applies the action

**`UndoManager`:**

Instance variables:
- `_undo_stack: list[UndoAction]` — most recent action at end
- `_redo_stack: list[UndoAction]` — most recent redo at end
- `_max_size: int` — defaults to 50

Properties:
- `can_undo: bool` — True if undo stack non-empty
- `can_redo: bool` — True if redo stack non-empty
- `undo_description: str` — description of next undo action, or ""
- `redo_description: str` — description of next redo action, or ""

Methods:
- `push(action: UndoAction)` — push action, clear redo stack, trim to max_size, emit `state_changed`
- `undo()` — pop from undo stack, call `undo_fn`, push to redo stack, emit `state_changed`
- `redo()` — pop from redo stack, call `redo_fn`, push to undo stack, emit `state_changed`
- `clear()` — clear both stacks, emit `state_changed`

Signals:
- `state_changed` — emitted after any stack mutation (push/undo/redo/clear)

---

### `k_pdf/presenters/tab_manager.py` (modify)

Add `undo_manager: UndoManager` field to `TabContext` dataclass (default_factory creates a new instance). Update `TabManager` to expose `get_active_undo_manager() -> UndoManager | None`.

---

### `k_pdf/views/main_window.py` (modify)

Add to Edit menu:
- `Undo` action (Ctrl+Z) — emits `undo_requested` signal
- `Redo` action (Ctrl+Shift+Z) — emits `redo_requested` signal
- Both start disabled, updated via `set_undo_state(can_undo, undo_text, can_redo, redo_text)`

---

### `k_pdf/app.py` (modify)

Wire undo/redo:
- `MainWindow.undo_requested` -> `_on_undo()` -> active UndoManager.undo()
- `MainWindow.redo_requested` -> `_on_redo()` -> active UndoManager.redo()
- `TabManager.tab_switched` -> `_on_tab_switched_undo()` -> update menu state
- `UndoManager.state_changed` -> `_update_undo_menu_state()` -> update menu enabled/text

---

## 3. Integration Points

### AnnotationPresenter (`create_annotation`, `delete_annotation`)

On `create_annotation`: after engine call, push UndoAction where `undo_fn` deletes the annotation, `redo_fn` re-creates it.

On `delete_annotation`: before engine call, capture enough state. Push UndoAction where `undo_fn` re-creates, `redo_fn` re-deletes.

Note: Full annotation undo for complex types is deferred. Initial scope: push UndoAction with description only, undo/redo trigger page re-render. Phase 1 focuses on the framework; full reversible annotation operations require engine-level snapshot support that can be added later.

### FormPresenter (`on_field_changed`)

On field change: capture old value. Push UndoAction where `undo_fn` restores old value, `redo_fn` applies new value.

### PageManagementPresenter (`rotate_pages`, `delete_pages`, `move_page`, `insert_pages`)

Page operations are complex and often irreversible at the PyMuPDF level. Initial integration: push UndoAction with description for tracking. Full reversal deferred to a later phase.

---

## 4. Stack Size and Memory

- Max 50 UndoActions per tab
- UndoActions hold lambdas referencing presenter/engine state — no large data copies
- Stack cleared on tab close (TabContext disposal)

---

## 5. Accessibility

- Undo/Redo menu items include keyboard shortcuts visible in menu text
- Gray-out state provides non-color differentiation (enabled vs disabled)
- Status bar shows action description on undo/redo
