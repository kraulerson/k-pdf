# Feature 11: Dark / Night Reading Mode — Design Spec

**Date:** 2026-04-02
**Status:** Approved
**Depends on:** Feature 1 (Open/Render), Feature 2 (Multi-Tab)
**FRD Reference:** FUNCTIONAL_REQUIREMENTS.md Section 2, Feature 11
**UI Reference:** UI_SCAFFOLDING.md Section 3 (Menu Structure), Section 5 (Theme System)

---

## 1. Architecture Overview

**ThemeManager (core):** New module in `k_pdf/core/theme_manager.py`. Manages application-wide theme state with three modes: Off (light), Dark UI / Original PDF, Dark UI / Inverted PDF. Loads QSS stylesheets from `k_pdf/resources/themes/` and applies them to the QApplication instance. Has no PyMuPDF dependency. Emits signals on theme change so the viewport and status bar can update. Tracks last-used dark sub-mode for Ctrl+D toggle behavior.

**QSS Stylesheets:** Two complete stylesheet files in `k_pdf/resources/themes/`:
- `light.qss` — default light theme matching UI_SCAFFOLDING.md Section 5.1 colors
- `dark.qss` — dark theme matching UI_SCAFFOLDING.md Section 5.2 colors

Both meet WCAG 2.1 AA contrast ratios. The dark theme styles: QMainWindow, QDockWidget, QTabWidget, QToolBar, QStatusBar, QListWidget, QTreeWidget, QPushButton, QLineEdit, QLabel, QMenuBar, QMenu, QScrollBar, QGraphicsView, QComboBox, QSpinBox, QSlider, QSplitter.

**PDF Inversion:** For "Inverted PDF" sub-mode, PdfViewport applies QImage color inversion on pixmaps before display. The inversion is view-only — it does not modify the PDF file. The ThemeManager signals the inversion state; PdfViewport stores a flag and inverts incoming pixmaps in `set_page_pixmap()`. Already-displayed pixmaps are re-rendered by invalidating the cache and re-requesting visible pages.

**View Menu Submenu:** View > Dark Mode submenu with three radio-button actions: Off, Dark UI / Original PDF, Dark UI / Inverted PDF. Uses QActionGroup for mutual exclusion. Already specified in UI_SCAFFOLDING.md Section 3.

**Keyboard Shortcut:** Ctrl+D (Cmd+D on macOS) toggles between Off and last-used dark mode. If no dark mode was previously used, defaults to Dark UI / Original PDF.

**Per-Application State:** Theme applies to the entire application, not individual tabs. All tabs share the same theme and inversion state.

### Signal Flow

1. User selects View > Dark Mode > [mode] or presses Ctrl+D
2. MainWindow emits `dark_mode_changed(ThemeMode)` -> KPdfApp routes to `ThemeManager.set_mode()`
3. ThemeManager loads appropriate QSS stylesheet and applies it via `QApplication.instance().setStyleSheet()`
4. ThemeManager emits `theme_changed(ThemeMode)` -> status bar updates mode text
5. ThemeManager emits `inversion_changed(bool)` -> KPdfApp routes to all viewports
6. PdfViewport sets `_invert_pdf` flag -> DocumentPresenter invalidates cache -> visible pages re-rendered with inversion applied in `set_page_pixmap()`

### State Model

```
ThemeMode enum:
  OFF              -> light.qss, no inversion
  DARK_ORIGINAL    -> dark.qss, no inversion
  DARK_INVERTED    -> dark.qss, inversion ON
```

ThemeManager tracks:
- `_mode: ThemeMode` — current active mode
- `_last_dark_mode: ThemeMode` — last dark sub-mode used (for Ctrl+D toggle, defaults to DARK_ORIGINAL)

---

## 2. New Files

### `k_pdf/core/theme_manager.py`

**`ThemeMode` enum:**

| Value | Description |
|---|---|
| `OFF` | Light theme, no PDF inversion |
| `DARK_ORIGINAL` | Dark UI theme, PDF colors unchanged |
| `DARK_INVERTED` | Dark UI theme, PDF colors inverted |

**`ThemeManager(QObject)` class:**

| Method | Description |
|---|---|
| `__init__(app: QApplication)` | Store app reference, set initial mode to OFF, load stylesheet paths |
| `mode -> ThemeMode` | Property returning current mode |
| `set_mode(mode: ThemeMode) -> None` | Apply theme: load QSS, set stylesheet on app, emit signals |
| `toggle() -> None` | Toggle between OFF and last-used dark mode |
| `is_dark -> bool` | Property: True if mode is DARK_ORIGINAL or DARK_INVERTED |
| `is_inverted -> bool` | Property: True if mode is DARK_INVERTED |

| Signal | Description |
|---|---|
| `theme_changed(int)` | Emitted with ThemeMode.value when theme changes |
| `inversion_changed(bool)` | Emitted with True/False when PDF inversion state changes |

### `k_pdf/resources/themes/light.qss`

Complete QSS for the light theme using colors from UI_SCAFFOLDING.md Section 5.1.

### `k_pdf/resources/themes/dark.qss`

Complete QSS for the dark theme using colors from UI_SCAFFOLDING.md Section 5.2.

---

## 3. Modified Files

### `k_pdf/views/main_window.py`

- Add `dark_mode_changed = Signal(int)` signal
- Add View > Dark Mode submenu with three QAction radio buttons (Off, Dark UI / Original PDF, Dark UI / Inverted PDF) in a QActionGroup
- Add Ctrl+D shortcut action that triggers `ThemeManager.toggle()`
- Add `_mode_label` to status bar showing current mode as text
- Add `set_theme_mode(mode: ThemeMode)` method to sync menu radio state from external changes

### `k_pdf/views/pdf_viewport.py`

- Add `_invert_pdf: bool` flag (default False)
- Add `set_invert_pdf(invert: bool)` method
- Modify `set_page_pixmap()`: if `_invert_pdf` is True, convert QPixmap to QImage, call `invertPixels()`, convert back to QPixmap before displaying
- Inversion uses `QImage.invertPixels(QImage.InvertMode.InvertRgb)` — preserves alpha channel

### `k_pdf/app.py`

- Create ThemeManager instance in `__init__`
- Wire MainWindow dark mode signals to ThemeManager
- Wire ThemeManager signals to MainWindow status bar and viewport inversion
- On `inversion_changed`: iterate all open viewports, set inversion flag, invalidate caches, re-render visible pages

---

## 4. Accessibility

- Dark Mode submenu actions are text-labeled: "Off", "Dark UI / Original PDF", "Dark UI / Inverted PDF" — never icon-only
- Status bar mode indicator uses text: "Light Mode", "Dark Mode: Original PDF", "Dark Mode: Inverted PDF"
- Both themes meet WCAG 2.1 AA contrast ratios (4.5:1 for normal text, 3:1 for large text)
- All existing indicators (borders, underlines, focus rings) remain visible in dark theme
- Tab active state uses border, not color alone, in both themes
- Focus indicators use `#90CAF9` in dark theme (contrast ratio 5.2:1 against `#121212` background)

---

## 5. Testing Strategy

- **ThemeManager unit tests:** mode transitions, toggle behavior, last-dark-mode memory, signal emissions, stylesheet loading
- **PdfViewport inversion tests:** verify pixmap is inverted when flag is set, not inverted when flag is cleared
- **MainWindow menu tests:** verify submenu creation, radio group exclusivity, Ctrl+D shortcut action, status bar text updates
- **Integration tests:** full cycle from menu selection through theme application to viewport inversion
- **QSS loading tests:** verify stylesheet files exist and are non-empty, can be loaded without errors
