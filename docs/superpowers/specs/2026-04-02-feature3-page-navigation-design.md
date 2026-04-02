# Feature 3: Page Navigation — Thumbnails, Bookmarks, Outline — Design Spec

**Date:** 2026-04-02
**Status:** Approved
**Depends on:** Feature 1 (Open/Render), Feature 2 (Multi-Tab)
**FRD Reference:** FUNCTIONAL_REQUIREMENTS.md Section 2, Feature 3
**UI Reference:** UI_SCAFFOLDING.md Section 2.1 (Navigation Panel)

---

## 1. Architecture Overview

**Navigation panel:** QDockWidget docked left, containing a QTabWidget with "Thumbnails" and "Outline" tabs. Collapsible, resizable, toggled via F5.

**Presenter:** New `NavigationPresenter` subscribes to `TabManager` signals (document_ready, tab switch, tab close) and coordinates between the active tab's data and the NavigationPanel view.

**Thumbnail rendering:** `ThumbnailCache` pre-renders all page thumbnails on document load via a dedicated QThread per document. Thumbnails stored as small QPixmaps (~90px wide) for instant scrolling.

**Outline parsing:** `OutlineService` in services/ calls PyMuPDF's `get_toc()` and transforms the flat list into an `OutlineNode` tree in core/. PyMuPDF stays isolated in services/.

### Signal Flow

1. `TabManager.document_ready(session_id, model)` →
2. `NavigationPresenter._on_document_ready()` — creates ThumbnailCache, fetches outline via OutlineService →
3. ThumbnailCache emits `thumbnail_ready(page_index, pixmap)` as each renders →
4. NavigationPresenter forwards to NavigationPanel view
5. User clicks thumbnail/outline → NavigationPresenter calls `PdfViewport.scroll_to_page()`
6. User scrolls viewport → `PdfViewport.current_page_changed(int)` → NavigationPresenter highlights current thumbnail

---

## 2. New Files

### `k_pdf/core/outline_model.py`

**`OutlineNode` frozen dataclass:**

| Field | Type | Description |
|---|---|---|
| `title` | `str` | Bookmark title text |
| `page` | `int` | 0-based page index (-1 if invalid target) |
| `children` | `list[OutlineNode]` | Child nodes for nested bookmarks |

Pure data, no Qt or PyMuPDF imports.

### `k_pdf/services/outline_service.py`

**`get_outline(doc_handle) -> list[OutlineNode]`**

- Calls `doc.get_toc()` → `list[list[level, title, page_1based]]`
- Transforms flat level-based list into nested `OutlineNode` tree
- Converts page numbers to 0-based
- Invalid page references (page < 0 or >= page_count) get `page = -1`
- Returns empty list if document has no outline

PyMuPDF import isolated here per AGPL rule.

### `k_pdf/core/thumbnail_cache.py`

**`ThumbnailCache(QObject)` class:**

Constructor takes:
- `doc_handle` — opaque PyMuPDF document handle
- `pages: list[PageInfo]`
- `thumb_width: int = 90`

Signals:
- `thumbnail_ready(int, QPixmap)` — (page_index, thumbnail pixmap)
- `all_thumbnails_ready()` — pre-rendering complete

Methods:
- `start()` — begin pre-rendering on a dedicated QThread
- `get(page_index: int) -> QPixmap | None` — retrieve cached thumbnail
- `cancel()` — abort rendering (e.g., tab closed mid-render)
- `shutdown()` — stop thread and clean up

Implementation:
- Calculates zoom factor per page: `thumb_width / page.width`
- Spawns a QThread with a worker that calls `PdfEngine.render_page()` for each page at the low zoom
- Stores results in `dict[int, QPixmap]`
- Thread is separate from the main page-rendering thread

One instance per open document. Discarded when tab closes.

### `k_pdf/presenters/navigation_presenter.py`

**`NavigationPresenter(QObject)` class:**

Constructor takes:
- `tab_manager: TabManager`
- `parent: QObject | None`

Internal state:
- `_thumbnail_caches: dict[str, ThumbnailCache]` — per session_id
- `_outlines: dict[str, list[OutlineNode]]` — per session_id
- `_active_session_id: str | None`

Signals:
- `thumbnail_ready(int, QPixmap)` — forwarded from active tab's cache
- `outline_ready(list)` — list[OutlineNode] for active tab
- `active_thumbnail_changed(int)` — current page highlight

Connects to TabManager:
- `document_ready(session_id, model)` → create ThumbnailCache, fetch outline, push to view
- Tab switch → swap active thumbnails/outline in view
- Tab close → cancel rendering, discard cache and outline
- `tab_count_changed(0)` → clear panel

Methods:
- `_on_document_ready(session_id, model)` — create cache, start rendering, fetch outline
- `_on_tab_switched(session_id)` — swap panel to new tab's data
- `_on_tab_closed(session_id)` — cancel and discard
- `navigate_to_page(page_index)` — tell active viewport to scroll to page

### `k_pdf/views/navigation_panel.py`

**`NavigationPanel(QDockWidget)` class:**

Replaces existing stub file.

Structure:
- QDockWidget, title "Navigation"
- Contains QTabWidget with two text-labeled tabs: "Thumbnails" and "Outline"
- Default tab: Thumbnails

**Thumbnails tab:**
- QListWidget in icon mode, vertical flow
- Each item: small QPixmap + page number text label below
- Current page has thick border selection indicator (not color alone)
- Clicking emits `thumbnail_clicked(int)` signal

**Outline tab:**
- QTreeWidget displaying OutlineNode tree
- Each node shows bookmark title text
- Expandable nodes have +/- indicator
- Clicking emits `outline_clicked(int)` signal (target page index)
- Nodes with `page == -1`: warning icon + "Invalid target" text, click does nothing
- Empty state: QLabel "No bookmarks in this document."

Signals:
- `thumbnail_clicked(int)` — page index
- `outline_clicked(int)` — page index

Methods:
- `set_thumbnails(thumbnails: dict[int, QPixmap], page_count: int)` — populate thumbnail list
- `add_thumbnail(page_index: int, pixmap: QPixmap)` — add single thumbnail as it renders
- `set_outline(nodes: list[OutlineNode])` — populate outline tree
- `set_current_page(page_index: int)` — highlight current thumbnail
- `clear()` — reset both tabs to empty state

---

## 3. Modified Files

### `k_pdf/views/main_window.py`

- Add NavigationPanel as QDockWidget: `addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, nav_panel)`
- Expose `navigation_panel` property
- View menu: add "Navigation Panel" toggle action with F5 shortcut, connected to `nav_panel.toggleViewAction()`
- Panel starts hidden

### `k_pdf/views/pdf_viewport.py`

- New signal: `current_page_changed(int)` — emitted when topmost visible page changes during scroll
- New instance variable: `_current_page: int = -1` — tracks last emitted page
- Modify `_on_scroll()`: after calculating visible range, check if first visible page changed, emit if so
- New method: `scroll_to_page(page_index: int)` — scroll viewport to position given page at top using `_page_y_offsets`

### `k_pdf/app.py`

- Create `NavigationPresenter`, wire to `TabManager` and `MainWindow.navigation_panel`
- Connect NavigationPanel signals (thumbnail_clicked, outline_clicked) to NavigationPresenter.navigate_to_page
- Connect NavigationPresenter signals to NavigationPanel methods

### `k_pdf/presenters/tab_manager.py`

- Add `tab_switched(str)` signal — emits session_id when active tab changes (NavigationPresenter needs this)
- Emit from `_on_tab_switched()` after updating `_active_session_id`
- Add `tab_closed(str)` signal — emits session_id when a tab is removed (for NavigationPresenter cleanup)
- Emit from `close_tab()` before removing from `_tabs`
- Add `get_active_viewport() -> PdfViewport | None` method — NavigationPresenter needs this to connect `current_page_changed` signal and call `scroll_to_page()`

---

## 4. Unchanged Files

- `k_pdf/core/document_model.py` — unchanged
- `k_pdf/core/page_cache.py` — unchanged
- `k_pdf/presenters/document_presenter.py` — unchanged
- `k_pdf/services/pdf_engine.py` — `render_page()` already supports arbitrary zoom, reused by ThumbnailCache

---

## 5. Accessibility

- Thumbnail selection: thick border indicator, not color change alone
- Outline tree: text labels, expandable +/- indicators
- Navigation panel toggle: F5 keyboard shortcut
- All interactive elements keyboard navigable
- "No bookmarks" shown as text label, not empty space

---

## 6. Error Handling & Edge Cases

**Document with no outline:** Outline tab shows "No bookmarks in this document." label. Thumbnails tab works normally.

**Outline entry with invalid page:** Node shows warning icon + "Invalid target" text. Click does nothing. Status bar message: "This bookmark points to an invalid page."

**Thumbnail render failure for a page:** Placeholder thumbnail: gray rectangle with page number text and "Render error" label. Other thumbnails render normally.

**Very large document (500+ pages):** ThumbnailCache pre-renders all on background thread. QListWidget handles virtual scrolling natively. Progress is incremental — thumbnails appear as they render.

**Tab closed during thumbnail rendering:** `ThumbnailCache.cancel()` stops the worker thread. Cache discarded.

**Tab switch:** NavigationPresenter swaps panel contents to new tab's cached data. If thumbnails are still rendering for new tab, they stream in as they complete.

---

## 7. Testing Strategy

### Unit Tests

| File | Tests |
|---|---|
| `tests/test_outline_model.py` | OutlineNode construction, tree nesting, frozen dataclass |
| `tests/test_outline_service.py` | Flat toc → tree, empty outline, invalid page → -1, multi-level nesting |
| `tests/test_thumbnail_cache.py` | Pre-renders all pages, get() returns pixmap after ready, cancel stops rendering |
| `tests/test_navigation_presenter.py` | document_ready triggers cache+outline, tab switch swaps data, tab close discards |
| `tests/test_navigation_panel.py` | Thumbnail click emits signal, outline click emits signal, empty outline shows label, invalid entry non-functional |

### Integration Tests (`tests/test_navigation_integration.py`)

| Test | Verifies |
|---|---|
| `test_open_pdf_shows_thumbnails` | Open PDF → thumbnail count matches page count |
| `test_click_thumbnail_scrolls_viewport` | Click thumbnail → viewport scrolls to that page |
| `test_open_pdf_with_outline` | Open PDF with bookmarks → outline tree populated |
| `test_switch_tabs_updates_panel` | Switch tabs → panel shows new tab's thumbnails/outline |
| `test_close_last_tab_clears_panel` | Close only tab → panel cleared |

**New fixture:** PDF with embedded bookmarks/outline for outline tests.

**Coverage target:** Maintain 65%+.

---

## 8. Deferred Items

- **Panel width persistence** — spec says panel width should persist across sessions. Deferred to Preferences feature (implicit feature).
- **Panel open/closed state persistence** — same, deferred to Preferences.
- **Thumbnail sync smoothness** — passive sync (scroll thumbnail list to keep current page visible) without jarring forced scroll. Basic implementation now, polish later if needed.
