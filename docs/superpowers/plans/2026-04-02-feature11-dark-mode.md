# Feature 11: Dark / Night Reading Mode — Implementation Plan

**Date:** 2026-04-02
**Spec:** `docs/superpowers/specs/2026-04-02-feature11-dark-mode-design.md`
**Branch:** `feature/dark-mode`
**Depends on:** Features 1, 2 (all complete)

---

## Task Overview

| # | Task | Type | Files |
|---|------|------|-------|
| 1 | ThemeMode enum + ThemeManager core | model | `k_pdf/core/theme_manager.py`, `tests/test_theme_manager.py` |
| 2 | QSS stylesheets (light + dark) | resource | `k_pdf/resources/themes/light.qss`, `k_pdf/resources/themes/dark.qss`, `tests/test_theme_manager.py` |
| 3 | PdfViewport inversion support | view | `k_pdf/views/pdf_viewport.py`, `tests/test_viewport_inversion.py` |
| 4 | MainWindow: Dark Mode submenu + Ctrl+D + status bar | view | `k_pdf/views/main_window.py`, `tests/test_views.py` |
| 5 | KPdfApp: wire ThemeManager signals | app | `k_pdf/app.py`, `tests/test_dark_mode_integration.py` |
| 6 | Mypy overrides + CLAUDE.md update | config | `pyproject.toml`, `CLAUDE.md` |

---

## Task 1: ThemeMode enum + ThemeManager core

### RED — Write failing tests

**File: `tests/test_theme_manager.py`**

```python
"""Tests for ThemeManager and ThemeMode."""

from k_pdf.core.theme_manager import ThemeManager, ThemeMode


class TestThemeMode:
    def test_off_value(self):
        assert ThemeMode.OFF.value == "off"

    def test_dark_original_value(self):
        assert ThemeMode.DARK_ORIGINAL.value == "dark_original"

    def test_dark_inverted_value(self):
        assert ThemeMode.DARK_INVERTED.value == "dark_inverted"

    def test_all_members(self):
        assert set(ThemeMode) == {
            ThemeMode.OFF,
            ThemeMode.DARK_ORIGINAL,
            ThemeMode.DARK_INVERTED,
        }


class TestThemeManager:
    def test_initial_mode_is_off(self, qapp):
        mgr = ThemeManager(qapp)
        assert mgr.mode is ThemeMode.OFF

    def test_set_mode_dark_original(self, qapp):
        mgr = ThemeManager(qapp)
        mgr.set_mode(ThemeMode.DARK_ORIGINAL)
        assert mgr.mode is ThemeMode.DARK_ORIGINAL

    def test_set_mode_dark_inverted(self, qapp):
        mgr = ThemeManager(qapp)
        mgr.set_mode(ThemeMode.DARK_INVERTED)
        assert mgr.mode is ThemeMode.DARK_INVERTED

    def test_is_dark_false_when_off(self, qapp):
        mgr = ThemeManager(qapp)
        assert mgr.is_dark is False

    def test_is_dark_true_when_dark_original(self, qapp):
        mgr = ThemeManager(qapp)
        mgr.set_mode(ThemeMode.DARK_ORIGINAL)
        assert mgr.is_dark is True

    def test_is_inverted_false_when_dark_original(self, qapp):
        mgr = ThemeManager(qapp)
        mgr.set_mode(ThemeMode.DARK_ORIGINAL)
        assert mgr.is_inverted is False

    def test_is_inverted_true_when_dark_inverted(self, qapp):
        mgr = ThemeManager(qapp)
        mgr.set_mode(ThemeMode.DARK_INVERTED)
        assert mgr.is_inverted is True

    def test_toggle_from_off_goes_dark_original_default(self, qapp):
        mgr = ThemeManager(qapp)
        mgr.toggle()
        assert mgr.mode is ThemeMode.DARK_ORIGINAL

    def test_toggle_from_dark_goes_off(self, qapp):
        mgr = ThemeManager(qapp)
        mgr.set_mode(ThemeMode.DARK_ORIGINAL)
        mgr.toggle()
        assert mgr.mode is ThemeMode.OFF

    def test_toggle_remembers_last_dark_mode(self, qapp):
        mgr = ThemeManager(qapp)
        mgr.set_mode(ThemeMode.DARK_INVERTED)
        mgr.toggle()  # -> OFF
        mgr.toggle()  # -> should go back to DARK_INVERTED
        assert mgr.mode is ThemeMode.DARK_INVERTED

    def test_theme_changed_signal(self, qapp, qtbot):
        mgr = ThemeManager(qapp)
        with qtbot.waitSignal(mgr.theme_changed, timeout=1000):
            mgr.set_mode(ThemeMode.DARK_ORIGINAL)

    def test_inversion_changed_signal_emitted(self, qapp, qtbot):
        mgr = ThemeManager(qapp)
        with qtbot.waitSignal(mgr.inversion_changed, timeout=1000):
            mgr.set_mode(ThemeMode.DARK_INVERTED)

    def test_no_signal_when_same_mode(self, qapp, qtbot):
        mgr = ThemeManager(qapp)
        mgr.set_mode(ThemeMode.DARK_ORIGINAL)
        with qtbot.assertNotEmitted(mgr.theme_changed):
            mgr.set_mode(ThemeMode.DARK_ORIGINAL)

    def test_set_mode_off_restores_light_theme(self, qapp):
        mgr = ThemeManager(qapp)
        mgr.set_mode(ThemeMode.DARK_ORIGINAL)
        mgr.set_mode(ThemeMode.OFF)
        assert mgr.mode is ThemeMode.OFF
        assert mgr.is_dark is False
```

### GREEN — Implement ThemeManager

**File: `k_pdf/core/theme_manager.py`** — ThemeMode enum + ThemeManager class with mode, toggle, is_dark, is_inverted, theme_changed/inversion_changed signals, QSS loading from resources/themes/.

### REFACTOR — None expected.

---

## Task 2: QSS Stylesheets

### RED — Add stylesheet loading tests to test_theme_manager.py

```python
class TestQssLoading:
    def test_light_qss_exists_and_nonempty(self):
        path = Path(__file__).parent.parent / "k_pdf" / "resources" / "themes" / "light.qss"
        assert path.exists()
        assert path.stat().st_size > 100

    def test_dark_qss_exists_and_nonempty(self):
        path = Path(__file__).parent.parent / "k_pdf" / "resources" / "themes" / "dark.qss"
        assert path.exists()
        assert path.stat().st_size > 100

    def test_dark_theme_applies_without_error(self, qapp):
        mgr = ThemeManager(qapp)
        mgr.set_mode(ThemeMode.DARK_ORIGINAL)
        assert qapp.styleSheet() != ""

    def test_light_theme_applied_on_off(self, qapp):
        mgr = ThemeManager(qapp)
        mgr.set_mode(ThemeMode.DARK_ORIGINAL)
        mgr.set_mode(ThemeMode.OFF)
        # Light theme is either empty or has light QSS content
        assert mgr.mode is ThemeMode.OFF
```

### GREEN — Write complete QSS files.

### REFACTOR — Validate contrast ratios are documented.

---

## Task 3: PdfViewport Inversion Support

### RED — Write failing tests

**File: `tests/test_viewport_inversion.py`**

```python
"""Tests for PdfViewport PDF inversion mode."""

class TestViewportInversion:
    def test_inversion_flag_default_false(self, qapp):
        vp = PdfViewport()
        assert vp.invert_pdf is False

    def test_set_invert_pdf_true(self, qapp):
        vp = PdfViewport()
        vp.set_invert_pdf(True)
        assert vp.invert_pdf is True

    def test_set_invert_pdf_false(self, qapp):
        vp = PdfViewport()
        vp.set_invert_pdf(True)
        vp.set_invert_pdf(False)
        assert vp.invert_pdf is False

    def test_set_page_pixmap_inverts_when_flag_true(self, qapp):
        # Create a white QPixmap, set inversion on, verify pixel changes
        ...

    def test_set_page_pixmap_no_inversion_when_flag_false(self, qapp):
        # Create a white QPixmap, verify no change
        ...
```

### GREEN — Add inversion logic to PdfViewport.

### REFACTOR — None expected.

---

## Task 4: MainWindow Dark Mode Submenu

### RED — Write failing tests

**File: `tests/test_views.py`** (extend existing)

```python
class TestDarkModeMenu:
    def test_dark_mode_submenu_exists(self, qapp):
        win = MainWindow()
        # Find View > Dark Mode submenu
        ...

    def test_dark_mode_actions_count(self, qapp):
        # Off + Dark UI / Original PDF + Dark UI / Inverted PDF = 3 actions
        ...

    def test_dark_mode_signal_emitted(self, qapp, qtbot):
        ...

    def test_ctrl_d_shortcut_exists(self, qapp):
        ...

    def test_mode_label_in_status_bar(self, qapp):
        ...
```

### GREEN — Add submenu, actions, signals, status bar label to MainWindow.

### REFACTOR — None expected.

---

## Task 5: KPdfApp Wiring + Integration Tests

### RED — Write failing integration tests

**File: `tests/test_dark_mode_integration.py`**

```python
class TestDarkModeIntegration:
    def test_menu_selection_changes_theme(self, qapp):
        ...

    def test_ctrl_d_toggle_full_cycle(self, qapp):
        ...

    def test_inversion_reaches_viewport(self, qapp):
        ...

    def test_status_bar_updates_on_mode_change(self, qapp):
        ...
```

### GREEN — Wire signals in KPdfApp.

### REFACTOR — None expected.

---

## Task 6: Mypy Overrides + CLAUDE.md Update

- Add mypy override for `k_pdf/core/theme_manager.py` if needed
- Update CLAUDE.md "Features built" to include Feature 11
- Update "Features remaining" count
