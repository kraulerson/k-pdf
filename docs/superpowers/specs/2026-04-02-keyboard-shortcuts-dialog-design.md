# Design Spec: Keyboard Shortcuts Dialog

## Overview
Read-only dialog listing all keyboard shortcuts in a categorized table.
Opened via Help > Keyboard Shortcuts (F1). Also adds Help > About K-PDF.

## Components

### KeyboardShortcutsDialog (QDialog)
- **File:** `k_pdf/views/keyboard_shortcuts_dialog.py`
- **Widget:** QTableWidget, 2 columns (Action, Shortcut), read-only
- **Categories:** File, Edit, View, Tools, Navigation — rendered as
  spanning header rows with bold text and distinct background
- **Platform keys:** Uses `Cmd` on macOS, `Ctrl` on Windows/Linux
  (detected at runtime via `sys.platform`)
- **Size:** 500x600 default, resizable
- **Accessibility:** Table is keyboard-navigable, no color-only meaning

### Shortcuts Data
Centralized list returned by a module-level function
`get_shortcut_definitions()` returning
`list[tuple[str, list[tuple[str, str]]]]` — category name + list of
(action, shortcut) pairs.

### Help Menu (MainWindow._setup_menus)
- Add `&Help` menu after Tools
- "Keyboard &Shortcuts" action, shortcut F1, opens dialog
- "&About K-PDF" action, opens QMessageBox with app name + version

### About Dialog
Simple `QMessageBox.about()` with:
- Title: "About K-PDF"
- Body: "K-PDF v{version}\n\nFree, offline, cross-platform PDF reader and editor."

## Constraints
- No shortcut customization (read-only reference)
- No new dependencies
- MVP pattern: dialog is a pure view, opened directly from menu action
  (no presenter needed — static data only)
- PyMuPDF not imported (view-only feature)

## Shortcuts to Display

| Category   | Action              | Shortcut          |
|------------|---------------------|--------------------|
| File       | Open                | Ctrl+O            |
| File       | Save                | Ctrl+S            |
| File       | Save As             | Ctrl+Shift+S      |
| File       | Close Tab           | Ctrl+W            |
| File       | Merge Documents     | Ctrl+Shift+M      |
| File       | Quit                | Ctrl+Q            |
| Edit       | Undo                | Ctrl+Z            |
| Edit       | Redo                | Ctrl+Shift+Z      |
| Edit       | Find                | Ctrl+F            |
| Edit       | Copy                | Ctrl+C            |
| View       | Zoom In             | Ctrl+=            |
| View       | Zoom Out            | Ctrl+-            |
| View       | Reset Zoom          | Ctrl+0            |
| View       | Rotate Clockwise    | Ctrl+R            |
| View       | Rotate CCW          | Ctrl+Shift+R      |
| View       | Navigation Panel    | F5                |
| View       | Annotation Panel    | F6                |
| View       | Page Manager        | F7                |
| View       | Toggle Dark Mode    | Ctrl+D            |
| Tools      | Text Selection      | Ctrl+T            |
| Navigation | Next Tab            | Ctrl+Tab          |
| Navigation | Previous Tab        | Ctrl+Shift+Tab    |
| Navigation | Page Down           | Page Down         |
| Navigation | Page Up             | Page Up           |
