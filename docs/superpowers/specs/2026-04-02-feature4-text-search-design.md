# Feature 4: Text Search Within Document — Design Spec

**Date:** 2026-04-02
**Status:** Approved
**Depends on:** Feature 1 (Open/Render), Feature 2 (Multi-Tab)
**FRD Reference:** FUNCTIONAL_REQUIREMENTS.md Section 2, Feature 4
**UI Reference:** UI_SCAFFOLDING.md Section 2.1 (Search Bar)

---

## 1. Architecture Overview

**Search bar:** Non-modal widget above the viewport, activated by Ctrl+F. Text input with match counter, Prev/Next, case/whole-word toggles, close button.

**Search execution:** `SearchWorker` runs on a dedicated QThread, iterates all pages calling PyMuPDF's `page.search_for()`, emits results progressively. Cancel supported.

**Highlights:** Semi-transparent `QGraphicsRectItem` overlays on the existing QGraphicsScene. Current match gets a distinct thicker border. Non-destructive — no PDF modification.

**Presenter:** `SearchPresenter` manages per-tab `SearchResult`, coordinates between SearchWorker, search bar, and viewport highlight overlays. Subscribes to TabManager signals for tab switch/close.

### Signal Flow

1. User presses Ctrl+F → MainWindow shows search bar, focuses input
2. User types query (debounced 300ms) → SearchPresenter starts SearchWorker
3. SearchWorker emits `page_matches(page_index, rects)` per page with matches
4. SearchPresenter stores results, pushes highlight overlays to viewport, updates match counter
5. SearchWorker emits `search_complete(total_count)` → SearchPresenter navigates to first match
6. User clicks Next/Prev → SearchPresenter advances cursor, scrolls viewport, updates current highlight
7. User closes search → highlights cleared, scroll position restored

---

## 2. New Files

### `k_pdf/core/search_model.py`

**`SearchResult` dataclass:**

| Field | Type | Description |
|---|---|---|
| `query` | `str` | The search text |
| `case_sensitive` | `bool` | Whether search was case-sensitive |
| `whole_word` | `bool` | Whether search was whole-word |
| `matches` | `dict[int, list[tuple[float, float, float, float]]]` | page_index → list of (x0, y0, x1, y1) rects |
| `total_count` | `int` | Total match count across all pages |
| `current_page` | `int` | Page index of current match (-1 if none) |
| `current_index` | `int` | Index within current page's matches (-1 if none) |

Not frozen — `current_page` and `current_index` mutate during navigation.

Methods:
- `advance()` — move to next match, wraps last → first
- `retreat()` — move to previous match, wraps first → last
- `current_match_number() -> int` — 1-based position in total sequence for "X of Y" display
- `current_rect() -> tuple[float, float, float, float] | None` — the current match's bounding box

Rects stored as plain tuples, not PyMuPDF Rect objects (model stays PyMuPDF-free).

### `k_pdf/services/search_service.py`

**`SearchWorker(QObject)` class:**

Signals:
- `page_matches(int, list)` — (page_index, list of rect tuples) per page with matches
- `search_complete(int)` — total match count when done
- `no_text_layer()` — document has no searchable text

Slot:
- `search(doc_handle, query, page_count, case_sensitive, whole_word)` — iterate all pages, call `page.search_for()`, convert Rect to tuple, emit per-page

Cancellation: `_cancelled` flag checked between pages. `cancel()` method sets it.

No-text detection: If no pages have extractable text, emit `no_text_layer()` and return early.

PyMuPDF import isolated here per AGPL rule.

### `k_pdf/presenters/search_presenter.py`

**`SearchPresenter(QObject)` class:**

Constructor takes:
- `tab_manager: TabManager`
- `parent: QObject | None`

Internal state:
- `_results: dict[str, SearchResult]` — per session_id
- `_active_session_id: str | None`
- `_worker: SearchWorker` — single instance
- `_thread: QThread` — dedicated search thread
- `_scroll_before_search: dict[str, int]` — saved scroll position per tab

Signals:
- `matches_updated(int, int)` — (current_match_number, total_count)
- `highlight_page(int, list)` — (page_index, rects) push overlays
- `clear_highlights()` — remove all overlays
- `no_text_layer()` — document has no searchable text
- `search_started()` — for progress indicator
- `search_finished()` — progress done

Connects to TabManager:
- `tab_switched` → save current search, restore new tab's search or clear
- `tab_closed` → discard SearchResult and saved scroll

Methods:
- `start_search(query, case_sensitive, whole_word)` — cancel running, save scroll, start worker
- `next_match()` — advance cursor, scroll viewport, update highlights
- `previous_match()` — retreat cursor, scroll viewport, update highlights
- `close_search()` — clear highlights, restore scroll, discard active result
- `shutdown()` — stop thread, clean up

### `k_pdf/views/search_bar.py`

**`SearchBar(QWidget)` class** (replaces stub):

Layout: text input | match counter label | Previous button | Next button | "Aa" toggle | "W" toggle | close button (×)

All buttons have text labels + tooltips, not icon-only. Starts hidden.

Signals:
- `search_requested(str, bool, bool)` — (query, case_sensitive, whole_word) on text change (debounced 300ms) and toggle changes
- `next_requested()` — Enter or Next button
- `previous_requested()` — Shift+Enter or Previous button
- `closed()` — close button or Escape

Methods:
- `set_match_count(current, total)` — update "X of Y" label
- `set_no_text_layer()` — show "This document has no searchable text."
- `set_no_matches()` — show "No matches found"
- `focus_input()` — focus the text field
- `clear()` — reset text and labels

---

## 3. Modified Files

### `k_pdf/views/pdf_viewport.py`

New methods for highlight overlays:
- `add_search_highlights(page_index: int, rects: list[tuple[float, float, float, float]], zoom: float)` — add semi-transparent QGraphicsRectItems at rect positions on the given page. Highlights use visible fill with border (not color alone).
- `set_current_highlight(page_index: int, rect: tuple[float, float, float, float], zoom: float)` — make one highlight visually distinct (thicker border)
- `clear_search_highlights()` — remove all highlight items from the scene

New instance variable: `_search_highlights: list[QGraphicsRectItem]` to track overlay items for removal.

### `k_pdf/views/main_window.py`

- Replace bare `QStackedWidget` as central widget with a `QVBoxLayout` container holding `SearchBar` + `QStackedWidget`. SearchBar sits above the viewport area.
- Expose `search_bar` property
- Edit menu: "Find..." action with Ctrl+F shortcut, shows/focuses search bar
- SearchBar starts hidden

### `k_pdf/app.py`

- Create SearchPresenter, wire to TabManager and MainWindow
- Connect SearchBar signals to SearchPresenter methods
- Connect SearchPresenter signals to SearchBar and PdfViewport highlight methods

---

## 4. Unchanged Files

- `k_pdf/core/document_model.py` — unchanged
- `k_pdf/presenters/document_presenter.py` — unchanged
- `k_pdf/presenters/tab_manager.py` — unchanged (already has needed signals)
- `k_pdf/presenters/navigation_presenter.py` — unchanged
- `k_pdf/services/pdf_engine.py` — unchanged (search uses PyMuPDF directly, not via PdfEngine)

---

## 5. Accessibility

- Search highlights use border + fill, not color alone
- Current match has thicker border, not just different color
- Match counter displays text "X of Y matches" or "No matches found"
- All search bar controls have text labels + tooltips
- Keyboard navigation: Ctrl+F opens, Enter for next, Shift+Enter for previous, Escape closes

---

## 6. Error Handling & Edge Cases

**No results found:** Counter shows "No matches found". No highlights.

**No text layer:** SearchWorker detects this, search bar shows "This document has no searchable text." Search bar stays open but non-functional.

**Large document:** Progressive results — match count updates as pages are scanned. Cancel supported.

**Query change while searching:** Cancel current, start new (debounced 300ms).

**Close search:** Clear highlights, restore scroll position to pre-search state.

**Tab switch during search:** Cancel running search. Restore new tab's search state if it has one, otherwise clear.

**Tab close:** Discard SearchResult and saved scroll position.

**Empty query:** No search, clear highlights and counter.

---

## 7. Testing Strategy

### Unit Tests

| File | Tests |
|---|---|
| `tests/test_search_model.py` | SearchResult construction, advance/retreat wrapping, current_match_number, empty results, current_rect |
| `tests/test_search_service.py` | Finds matches across pages, case sensitivity, whole word, empty results, no text layer, cancel |
| `tests/test_search_presenter.py` | start_search triggers worker, next/prev advance cursor, close restores scroll, tab switch saves/restores, tab close discards |
| `tests/test_search_bar.py` | search_requested on text change, next/previous signals, toggle states, match count display, close on Escape |

### Integration Tests (`tests/test_search_integration.py`)

| Test | Verifies |
|---|---|
| `test_search_finds_text` | Search for known text → matches found, counter updated |
| `test_next_previous_cycles` | Next/Previous navigates through matches |
| `test_close_search_clears_highlights` | Close → highlights removed |
| `test_no_text_document` | Search in image-only PDF → "no searchable text" message |

**Mocking:** PyMuPDF mocked in unit tests. Integration tests use real fixture PDFs.

**Coverage target:** Maintain 65%+.

---

## 8. Deferred Items

- **Regex search** — FRD says literal text only in MVP. No regex mode.
- **Search result persistence across tab switches** — basic save/restore of SearchResult. Full highlight re-rendering on tab switch deferred if complex.
