# Implementation Plan: Keyboard Shortcuts Dialog

## Baseline
- 727 tests passing, 84% coverage
- No Help menu exists yet

## Tasks (TDD order)

### Task 1: KeyboardShortcutsDialog view
1. Write `tests/test_keyboard_shortcuts_dialog.py`:
   - Test dialog creates with correct title and size
   - Test table has correct column headers (Action, Shortcut)
   - Test all category headers are present
   - Test all shortcut rows are present with correct data
   - Test platform-appropriate modifier key (Cmd on macOS)
   - Test table is read-only (no edit triggers)
   - Test dialog has close button
2. Create `k_pdf/views/keyboard_shortcuts_dialog.py`:
   - `get_shortcut_definitions()` function
   - `KeyboardShortcutsDialog(QDialog)` class
3. Green: all tests pass

### Task 2: Help menu + About dialog
1. Write `tests/test_help_menu.py`:
   - Test Help menu exists in menu bar
   - Test Help menu has "Keyboard Shortcuts" action with F1 shortcut
   - Test Help menu has "About K-PDF" action
   - Test triggering Keyboard Shortcuts action opens dialog
   - Test About dialog shows version string
2. Update `k_pdf/views/main_window.py`:
   - Add Help menu in `_setup_menus()`
   - Add `keyboard_shortcuts_requested` signal
   - Add `about_requested` signal or handle inline
3. Green: all tests pass

### Task 3: Integration wiring
1. Verify KPdfApp works with new Help menu (existing test_views.py
   tests still pass)
2. Update CLAUDE.md with feature completion

### Task 4: Quality gates
1. `uv run ruff check .`
2. `uv run ruff format .`
3. `uv run mypy k_pdf/`
4. `uv run pytest --cov=k_pdf --cov-report=term-missing`
5. All pass, coverage >= 65%
