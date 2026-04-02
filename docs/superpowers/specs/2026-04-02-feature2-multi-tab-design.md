# Feature 2: Multi-Tab Document Support — Design Spec

**Date:** 2026-04-02
**Status:** Approved
**Depends on:** Feature 1 (Open and Render PDF)
**FRD Reference:** FUNCTIONAL_REQUIREMENTS.md Section 2, Feature 2
**UI Reference:** UI_SCAFFOLDING.md Section 2.2 (Tab Bar)

---

## 1. Architecture Overview

**Pattern:** One `DocumentPresenter` per tab, each with its own `PdfWorker` thread, `PageCache`, and `DocumentModel`. A new `TabManager` in `presenters/` coordinates tab lifecycle.

**View layer:** `QTabWidget` replaces the single `PdfViewport` as central content. A `QStackedWidget` wraps `QTabWidget` + `WelcomeWidget` for the empty state (no tabs open).

**Thread model:** One `QThread` per tab. Each `DocumentPresenter` owns its thread (same as Feature 1). Threads are destroyed when tabs close.

### Component Hierarchy

```
KPdfApp (thin wiring shell)
├── TabManager (presenters/) — tab lifecycle coordinator
│   ├── dict[session_id → TabContext]
│   │   ├── DocumentPresenter (owns model, cache, worker thread)
│   │   ├── PdfViewport (QGraphicsView per tab)
│   │   └── session_id + resolved_path
│   ├── active_session_id
│   └── _open_paths: dict[Path → session_id] (duplicate detection)
│
├── MainWindow (views/)
│   └── QStackedWidget (central widget)
│       ├── page 0: WelcomeWidget (no tabs open)
│       └── page 1: QTabWidget (holds PdfViewports)
│
└── RecentFiles (persistence/)
```

### Signal Flow: Opening a File

1. `MainWindow.file_open_requested(path)` →
2. `TabManager.open_file(path)` — resolve path, check duplicates, create TabContext, add viewport to QTabWidget, call `presenter.open_file(path)` →
3. `DocumentPresenter.document_ready(model)` →
4. `TabManager._on_document_ready(session_id, model)` — update tab title, register in `_open_paths`, add to recent files, update status bar

---

## 2. New Files

### `k_pdf/presenters/tab_manager.py`

**`TabContext` dataclass:**

| Field | Type | Description |
|---|---|---|
| `session_id` | `str` | UUID generated at tab creation time (passed to DocumentPresenter for correlation) |
| `presenter` | `DocumentPresenter` | Owns model, cache, worker thread |
| `viewport` | `PdfViewport` | QGraphicsView for this tab |
| `resolved_path` | `Path \| None` | None until `document_ready` fires, then `path.resolve()` |

**`TabManager(QObject)` class:**

Constructor takes:
- `tab_widget: QTabWidget`
- `recent_files: RecentFiles`
- `parent: QObject | None`

Internal state:
- `_tabs: dict[str, TabContext]` — session_id to context
- `_open_paths: dict[Path, str]` — resolved path to session_id
- `_active_session_id: str | None`

Signals emitted:
- `document_ready(str, object)` — (session_id, DocumentModel)
- `error_occurred(str, str)` — forwarded from active presenter
- `password_requested(object)` — forwarded from active presenter
- `tab_count_changed(int)` — for MainWindow stacked widget toggling
- `status_message(str)` — forwarded from active presenter
- `active_page_status(int, int)` — (current_page, total_pages) on tab switch

Methods:

**`open_file(path: Path)`**
1. `resolved = path.resolve()`
2. If `resolved` in `_open_paths` → activate that tab, emit status message "This file is already open", return
3. Create `DocumentPresenter` and `PdfViewport`
4. Connect presenter signals to internal handlers (wrapping session_id via `functools.partial`)
5. Connect viewport's `visible_pages_changed` to presenter's `request_pages`
6. Create `TabContext(session_id, presenter, viewport, resolved_path=None)`
7. Add viewport to `QTabWidget` with title "Loading..."
8. Store in `_tabs` and activate
9. Call `presenter.open_file(path)`

**`close_tab(session_id: str)`**
1. Look up `TabContext`
2. If `presenter.model` and `presenter.model.dirty` → emit signal for unsaved changes dialog (deferred — always False until Features 6-9)
3. Call `presenter.shutdown()` (stops thread, closes doc)
4. Remove viewport from `QTabWidget`
5. Remove from `_tabs` and `_open_paths`
6. If no tabs left → emit `tab_count_changed(0)`

**`activate_tab(session_id: str)`**
1. Set `_active_session_id`
2. Switch `QTabWidget` to that tab's index
3. Push that tab's page status and zoom to status bar

**`_on_document_ready(session_id: str, model: DocumentModel)`**
1. Update `TabContext.resolved_path`
2. Register in `_open_paths`
3. Update tab title to filename (truncated, with `*` if dirty)
4. Call `viewport.set_document(model.pages)`
5. Add to recent files
6. Emit `document_ready` and status update

**`shutdown()`** — iterate all tabs, call `presenter.shutdown()` on each

### `tests/test_tab_manager.py` and `tests/test_tab_integration.py`

See Section 6 (Testing Strategy).

---

## 3. Modified Files

### `k_pdf/views/main_window.py`

**Central widget swap:**
- Replace `self.setCentralWidget(PdfViewport())` with `QStackedWidget`
- Page 0: `WelcomeWidget` (moved from `pdf_viewport.py`)
- Page 1: `QTabWidget` (configured below)
- MainWindow exposes `tab_widget` property for `TabManager`

**QTabWidget configuration:**
- `setTabsClosable(True)` — close buttons on each tab
- `setMovable(True)` — drag to reorder
- `setDocumentMode(True)` — cleaner look on macOS
- `setElideMode(Qt.TextElideMode.ElideRight)` — truncate long filenames

**New menu action:**
- File > Close Tab (Ctrl+W / Cmd+W) — emits `tab_close_requested` signal

**New signals:**
- `tab_close_requested()` — current tab close requested
- Existing `file_open_requested(Path)` unchanged

**Status bar:**
- "No document" when no tabs open
- Active tab's page count / zoom when tabs exist

### `k_pdf/views/pdf_viewport.py`

- Remove `WelcomeWidget` class (moved to `main_window.py`)
- Remove welcome overlay logic from `PdfViewport.__init__`
- Remove `show_welcome()` method
- `PdfViewport` becomes a pure document renderer — created only when a tab exists

### `k_pdf/app.py`

- Replace single `DocumentPresenter` with `TabManager`
- `_connect_signals` wires `MainWindow` signals to `TabManager` (not to a single presenter)
- `shutdown()` calls `TabManager.shutdown()` instead of single presenter shutdown
- Password dialog wiring goes through `TabManager`

---

## 4. Unchanged Files

These files require zero modifications:

- `k_pdf/presenters/document_presenter.py` — stays as-is (one model, one cache, one worker per instance)
- `k_pdf/core/document_model.py` — `DocumentModel` unchanged
- `k_pdf/core/page_cache.py` — `PageCache` unchanged
- `k_pdf/services/pdf_engine.py` — `PdfEngine` unchanged
- `k_pdf/services/pdf_errors.py` — error types unchanged
- `k_pdf/core/event_bus.py` — unchanged
- `k_pdf/persistence/recent_files.py` — unchanged (called by TabManager instead of KPdfApp)

---

## 5. Tab Title & Accessibility

**Tab title format:** `[*] filename.pdf`
- `*` prefix only when `model.dirty` is True (infrastructure in place, not triggered until Features 6-9)
- Filenames truncated via `Qt.TextElideMode.ElideRight`
- Tooltip on each tab shows the full absolute path

**Active tab indicator:**
- Styled via QSS: `QTabBar::tab:selected { border-bottom: 2px solid palette(text); }`
- Uses border, not color change — meets accessibility requirement

**Keyboard shortcuts:**
- Ctrl+Tab / Ctrl+Shift+Tab — cycle tabs (QTabWidget default behavior)
- Ctrl+W / Cmd+W — close current tab (new menu action)

**Tab close button:** `×` on each tab via `setTabsClosable(True)`. QTabWidget emits `tabCloseRequested(int)`.

**Drag reorder:** `setMovable(True)` — Qt native, no functional change.

---

## 6. Error Handling & Edge Cases

**Duplicate file:** Resolved path comparison via `Path.resolve()`. If duplicate found, activate existing tab and show "This file is already open" in status bar for 5 seconds. No error dialog.

**Load failure in new tab:** Tab created with "Loading..." title. If load fails, error dialog shown, then empty tab removed automatically. User returns to previous state.

**Password-protected PDF:** Tab stays at "Loading..." during password dialog. Correct password → normal flow. Cancel → remove empty tab.

**Last tab closed:** `tab_count_changed(0)` flips `QStackedWidget` to WelcomeWidget. Status bar shows "No document".

**App shutdown:** `TabManager.shutdown()` iterates all tabs, calls `presenter.shutdown()` on each.

**Memory:** Each tab's `PageCache` holds up to 50 pages. On tab close, cache + presenter + thread fully destroyed. Memory pressure warning deferred.

---

## 7. Testing Strategy

### Unit Tests (`tests/test_tab_manager.py`)

| Test | Verifies |
|---|---|
| `test_open_file_creates_tab` | TabContext created, viewport added to QTabWidget |
| `test_open_duplicate_activates_existing` | Same resolved path → one tab, second call activates first |
| `test_close_tab_removes_tab` | Removed from dicts, `presenter.shutdown()` called |
| `test_close_last_tab_emits_zero_count` | `tab_count_changed(0)` emitted |
| `test_activate_tab_switches_widget` | QTabWidget index changes |
| `test_document_ready_updates_title` | Tab title set to filename after load |
| `test_document_ready_registers_path` | `_open_paths` updated |
| `test_load_failure_removes_tab` | Empty tab cleaned up on error |
| `test_password_cancel_removes_tab` | Empty tab cleaned up on cancel |
| `test_shutdown_cleans_all_tabs` | All presenters shut down |
| `test_tab_title_dirty_prefix` | `*` prefix when `model.dirty` is True |

### Integration Tests (`tests/test_tab_integration.py`)

| Test | Verifies |
|---|---|
| `test_open_two_files_two_tabs` | Two PDFs → two tabs with correct titles |
| `test_switch_tab_preserves_state` | Each viewport shows its own pages after switching |
| `test_close_tab_shows_welcome` | Close only tab → welcome screen visible |

**Mocking:** `PdfEngine`/`PdfWorker` mocked in unit tests. Integration tests use real fixture PDFs from `tests/fixtures/`.

**Coverage target:** Maintain 65%+ threshold.

---

## 8. Deferred Items

These are specified in the FRD but deferred because they depend on features not yet built:

- **Unsaved changes dialog** — dirty flag infrastructure in place, but dialog only meaningful after Features 6-9 implement modifications
- **Memory pressure detection** — spec says status bar warning, no force-close. Deferred to a future pass.
- **Tab scroll arrows for overflow** — QTabWidget provides this by default via `setUsesScrollButtons(True)`, but visual testing deferred until we have enough tabs to trigger overflow
