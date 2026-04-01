# K-PDF — Functional Requirements Document (FRD)

## Version 1.0 — Phase 0, Step 0.1

**Source:** K-PDF Project Intake v1.1, Sections 2 and 4
**Generated:** 2026-04-01
**Status:** Draft — Awaiting Orchestrator Review

---

## 1. Product Intent

K-PDF is a free, offline, cross-platform desktop PDF reader and editor covering the 80% use case — read, annotate, fill forms, and manage pages — without subscriptions, accounts, or cloud dependencies. It targets a single power user (the Orchestrator) who needs all routine PDF tasks handled by one application that functions with the network adapter disabled.

---

## 2. MVP Feature Specifications

### Feature 1: Open and Render PDF

**Priority:** Must-Have (MVP) — Foundational. All other features depend on this.

**Business Logic Specification:**

| Trigger | System Action | Output |
|---|---|---|
| User opens a PDF via File > Open | System displays a native OS file picker filtered to `*.pdf`. User selects a file. System reads the file from disk. | File bytes loaded into memory or streaming buffer. |
| User opens a PDF via drag-and-drop | User drags a file onto the application window or dock/taskbar icon. System validates the drop payload is a file path ending in `.pdf`. | Same as File > Open from the validation step onward. |
| User opens a PDF via CLI argument | User launches `k-pdf /path/to/file.pdf` from terminal. System reads the path from `sys.argv`. | Same as File > Open from the validation step onward. |
| User opens a PDF via OS file association | User double-clicks a `.pdf` file in the OS file manager. OS launches K-PDF with the file path as argument. | Same as CLI argument path. |
| System validates the file | System checks: (1) file exists at path, (2) file is readable (OS permissions), (3) first bytes contain `%PDF-` header. | Validation pass → proceed to parse. Validation fail → error dialog (see failure states). |
| System parses the PDF | PyMuPDF opens the document. System reads page count, metadata, outline, and AcroForm presence. | Document object ready for rendering. |
| System renders all pages | Pages rendered at current zoom level. Text, images, and vector graphics displayed. Rendering is lazy — only visible pages and a small buffer of adjacent pages are rendered initially. | Pages visible in the main viewport. Scroll to access additional pages. |

**Failure States:**

| Condition | User Feedback | Recovery |
|---|---|---|
| File not found | Error dialog: "File not found: [full path]." OK button. | User dismissed dialog, no document opened. Recent files list does NOT add this path. |
| File not readable (permissions) | Error dialog: "Cannot open [filename]: permission denied." OK button. | Same as above. |
| Invalid PDF (no `%PDF-` header) | Error dialog: "Cannot open [filename]: this file does not appear to be a valid PDF." OK button. | Same as above. |
| Corrupt PDF (valid header, parse fails) | Error dialog: "Cannot open [filename]: the file is damaged or corrupted. [PyMuPDF error detail]." OK button. | Same as above. |
| Password-protected PDF | Password dialog: "This document is protected. Enter the password to open it." Text input + OK + Cancel. | Correct password → proceed to render. Wrong password → dialog remains with "Incorrect password. Try again." Cancel → no document opened. Three wrong attempts → no lockout (no security reason to lock out on a local file). |
| File too large to buffer entirely (>100MB heuristic) | Progress indicator in the status bar: "Loading [filename]... [X]%" with cancel button. | Cancel → no document opened, memory released. Complete → normal rendering. |
| Single page render failure | In the main viewport, the failed page displays a placeholder: gray rectangle with page number and text label "Render error on page [N]". All other pages render normally. | No crash. User can continue viewing other pages. Placeholder uses text label, not color, to indicate error (accessibility). |
| PyMuPDF raises unexpected exception during open | Error dialog: "An unexpected error occurred while opening [filename]: [exception type]: [message]." OK button. | No crash. Application remains in its prior state. |

**Implicit Dependencies Identified:**

1. **OS file association registration** — For double-click-to-open to work, the installer/packaging must register K-PDF as a PDF handler with the OS. This is a Phase 4 / packaging concern but must be architecturally planned in Phase 1. **Flag: Nuitka packaging must support file association registration on all three platforms.**
2. **Lazy rendering / streaming** — The Intake says "file too large to buffer entirely → stream render with progress indicator." PyMuPDF loads the entire file into memory by default. For very large files (>100MB), this may be acceptable on 96GB RAM but problematic on lower-spec machines. **Flag: Decide whether to implement true streaming or accept full-file load with a progress indicator during the load phase.**
3. **Recent files list** — Referenced implicitly by the file-open flow. Must persist across sessions. Covered by Data Persistence (Intake Section 5.4) but not listed as a standalone feature. **Recommendation: Add "recent files list" to the persistence specification, not as a separate feature but as part of Feature 1's complete specification.**

**Cross-Feature Dependencies:**
- Feature 2 (Multi-tab) depends on this: successful open triggers tab creation.
- Feature 3 (Navigation) depends on this: thumbnails and outline require a parsed document.
- Feature 4 (Search) depends on this: search requires a rendered, text-layer-accessible document.

---

### Feature 2: Multi-Tab Document Support

**Priority:** Must-Have (MVP) — Core UX pattern.

**Business Logic Specification:**

| Trigger | System Action | Output |
|---|---|---|
| User opens a second PDF while one is open | System creates a new tab in the tab bar. New document loads and renders in the new tab. Previous tab remains in its current state. | Tab bar visible with [N] tabs. Each tab shows the filename (truncated with ellipsis if too long) and a close button. Active tab visually distinct by position/underline, not color alone. |
| User switches tabs | User clicks a tab in the tab bar. System swaps the main viewport to show that tab's document at its preserved scroll position, zoom, rotation, and annotation state. | Viewport updates. All per-tab state is preserved independently. |
| User closes a tab (no unsaved changes) | User clicks the close button on a tab or uses Ctrl+W / Cmd+W. Tab removed. If it was the last tab, the application shows an empty state (welcome screen or blank). | Tab removed from tab bar. Memory for that document released. |
| User closes a tab (unsaved changes) | Modal dialog: "Unsaved changes in [filename]. Save before closing?" with three buttons: Save / Discard / Cancel. | Save → execute save flow (Feature 8/9/6/7 depending on what changed), then close tab. Discard → close tab, changes lost. Cancel → return to tab, no action. |
| User reorders tabs | User drags a tab to a new position in the tab bar. | Tab bar reflects new order. No functional change. |
| System detects memory pressure | OS signals low memory (platform-specific). System displays a non-modal warning in the status bar: "System memory is low. Consider closing unused tabs." | Warning text in status bar with icon. No tabs are force-closed. User decides. |

**Failure States:**

| Condition | User Feedback | Recovery |
|---|---|---|
| Opening a file that is already open in another tab | System activates the existing tab instead of opening a duplicate. Status bar message: "This file is already open." | Focus switches to existing tab. |
| Tab close fails during save | Error from save operation propagated to user. Tab remains open. | User resolves save issue, then reattempts close. |

**Implicit Dependencies:**
1. **Unsaved change tracking** — Each tab must track a "dirty" state. This requires a modification flag set by Features 6, 7, 8, 9 (annotations, form filling, page management). The tab title must show a modification indicator (text marker like `*` or `[modified]`, not color change alone).
2. **Memory management** — Tab count is unlimited per Intake, but each open PDF consumes memory (PyMuPDF document object + rendered page cache). **Flag: Define a soft warning threshold (e.g., >2GB total, or >20 tabs) and the memory pressure detection mechanism per platform.**

**Cross-Feature Dependencies:**
- Depends on Feature 1 (Open/Render).
- Features 3-12 all operate within the context of a tab.

---

### Feature 3: Page Navigation — Thumbnails, Bookmarks, Outline

**Priority:** Must-Have (MVP) — Core navigation.

**Business Logic Specification:**

| Trigger | System Action | Output |
|---|---|---|
| User opens the navigation panel | Side panel appears (left side, collapsible). Panel has two tabs (text-labeled, not icon-only): "Thumbnails" and "Outline". Default: Thumbnails. | Side panel visible. Main viewport resizes to accommodate. Panel width is user-resizable with drag handle. |
| Thumbnail panel active | All pages rendered as small thumbnails in a scrollable vertical list. Current page thumbnail has a visible border/highlight (not color alone — uses a thick border or selection indicator). Each thumbnail shows its page number as text below it. | Thumbnails visible, scrolled to show current page area. |
| User clicks a thumbnail | Main viewport jumps to that page. Thumbnail selection indicator moves to clicked thumbnail. | Viewport shows the selected page. |
| Outline panel active | Document's embedded bookmarks/outline displayed as a collapsible tree. Each node shows the bookmark title text. Expandable nodes have a +/- indicator. | Tree view of bookmarks. |
| User clicks an outline entry | Main viewport jumps to the page and position referenced by that bookmark. | Viewport navigates to target. |
| Document has no embedded outline | Outline tab either hidden entirely or shows a panel with text: "No bookmarks in this document." | Thumbnail panel remains usable. |
| User navigates via keyboard | Page Up/Down, Home/End, arrow keys scroll the main viewport. Ctrl+G / Cmd+G opens a "Go to page" dialog with numeric input. | Viewport scrolls. Go-to-page dialog: text input for page number, OK/Cancel. Invalid input (non-numeric, out of range) shows inline validation message. |

**Failure States:**

| Condition | User Feedback | Recovery |
|---|---|---|
| Thumbnail render fails for a specific page | Placeholder thumbnail: gray rectangle with page number text and "Render error" label. | Other thumbnails render normally. No crash. |
| Outline entry points to invalid page number | Entry shown in tree with warning icon (⚠) and text label "Invalid target". Clicking performs no navigation. Status bar message: "This bookmark points to an invalid page." | Entry remains visible but non-functional. |
| Very large document (500+ pages) thumbnails | Thumbnails use virtual scrolling — only visible thumbnails + buffer are rendered. Progress indicator during initial thumbnail generation. | Smooth scrolling. No freeze. |

**Implicit Dependencies:**
1. **Panel layout persistence** — Panel open/closed state and width should persist across sessions (user preference).
2. **Synchronization** — As user scrolls the main viewport, the thumbnail panel should scroll to keep the current page's thumbnail visible (passive sync, not jarring forced scroll).

---

### Feature 4: Text Search Within Document

**Priority:** Must-Have (MVP) — Core utility.

**Business Logic Specification:**

| Trigger | System Action | Output |
|---|---|---|
| User activates search (Ctrl+F / Cmd+F) | Search bar appears at the top of the viewport (non-modal). Text input field, match counter, Previous/Next buttons (labeled with text + icon), Close button. | Search bar visible. Focus in text input. |
| User types 1+ characters | System searches all pages for matching text. All matches highlighted on rendered pages. Match counter shows "X of Y matches" as text. First match scrolled into view. | Highlights visible. Counter updated. Current match has a distinct highlight (e.g., different border/pattern, not just different color). |
| User presses Enter or clicks Next | Viewport navigates to the next match. Counter updates to "[current] of [total]". Wraps from last to first. | Next match scrolled into view and marked as current. |
| User presses Shift+Enter or clicks Previous | Viewport navigates to the previous match. Wraps from first to last. | Previous match visible. |
| User clears search or closes search bar | All highlights removed. Viewport returns to the scroll position it was at before search was activated. | Clean state restored. |
| User toggles case sensitivity | Search bar includes a toggle button (labeled "Aa" with tooltip "Case sensitive"). Re-executes search with new setting. | Results update. |
| User toggles whole word match | Search bar includes a toggle button (labeled "W" with tooltip "Whole words"). Re-executes search with new setting. | Results update. |

**Failure States:**

| Condition | User Feedback | Recovery |
|---|---|---|
| No results found | Match counter shows "No matches found" as text. No highlights. | User modifies query or closes search. |
| Document has no text layer | Non-modal notification in search bar area: "This document has no searchable text." | User understands limitation. Search bar remains open but non-functional for this document. |
| Search on very large document is slow | Progress indicator in search bar: "Searching... [X]% ([N] matches so far)" with cancel button. | Cancel stops search and shows results found so far. Complete → normal display. |
| Regex or special characters in query | Search treats input as literal text by default. No regex mode in MVP. Special characters searched literally. | Consistent behavior. |

**Implicit Dependencies:**
1. **Highlight rendering** — Search highlights must overlay the PDF rendering layer without modifying the PDF. This is a rendering-layer concern.
2. **Cross-page search** — Search must work across all pages, not just the currently visible page. PyMuPDF's `search_for()` operates per-page, so the implementation must iterate all pages.

---

### Feature 5: Zoom, Rotate, and Page Fit Modes

**Priority:** Must-Have (MVP) — Core viewing.

**Business Logic Specification:**

| Trigger | System Action | Output |
|---|---|---|
| User adjusts zoom via slider | Slider in toolbar. Numeric display shows current percentage. Rendering updates as slider moves (debounced for performance). | Page rendered at new zoom level. |
| User enters numeric zoom | Click on zoom percentage display to edit. Type a number. Press Enter. | Zoom set to entered value (clamped to 10%-3200%). |
| User selects a zoom preset | Dropdown/menu with labeled options: "Fit Page", "Fit Width", "Actual Size (100%)", "50%", "75%", "150%", "200%". Text labels, not icon-only. | Zoom set to selected preset. Fit Page and Fit Width recalculate on window resize. |
| User zooms via keyboard | Ctrl+Plus / Cmd+Plus = zoom in (step: 10%). Ctrl+Minus / Cmd+Minus = zoom out. Ctrl+0 / Cmd+0 = reset to 100%. | Zoom level changes. |
| User zooms via scroll wheel | Ctrl+Scroll / Cmd+Scroll = zoom. Without modifier = normal scroll. | Zoom level changes, centered on cursor position. |
| User rotates current page view | View > Rotate Clockwise (Ctrl+R / Cmd+R). View > Rotate Counterclockwise (Ctrl+Shift+R / Cmd+Shift+R). 90° increments. | Page view rotated. **This does NOT modify the PDF file.** View rotation resets on tab close. |

**Failure States:**

| Condition | User Feedback | Recovery |
|---|---|---|
| Zoom below 10% | Clamped to 10%. No error. Slider/input reflects 10%. | Transparent clamping. |
| Zoom above 3200% | Clamped to 3200%. No error. | Transparent clamping. |
| High zoom causes rendering lag | Tile-based rendering — render visible area first, then surrounding tiles. Progress indicator if rendering takes >500ms. | Viewport updates progressively. |

**Clarification Required — View Rotation vs. Page Rotation:**
The Intake explicitly distinguishes view rotation (Feature 5, view-only, does NOT modify PDF) from page management rotation (Feature 9, modifies the PDF). **This distinction must be clear in the UI.** View rotation is in the View menu. Page rotation is in the Page Management panel. They are separate operations with separate keyboard shortcuts.

**Cross-Feature Dependencies:**
- Feature 5 state (zoom, rotation) is per-tab (Feature 2).
- Default zoom level persists as a user preference (data persistence).

---

### Feature 6: Text Markup Annotations — Highlight, Underline, Strikethrough

**Priority:** Must-Have (MVP) — Core annotation.

**Business Logic Specification:**

| Trigger | System Action | Output |
|---|---|---|
| User selects text on a page | Click-drag on rendered text. System detects text selection using PyMuPDF's text extraction coordinates. Selection highlighted with standard OS text selection appearance. | Text selected. Annotation toolbar appears near selection (floating or fixed). |
| Annotation toolbar appears | Toolbar shows three markup options, each with **icon + text label**: "Highlight", "Underline", "Strikethrough". Toolbar also shows a color picker (with named color labels, not swatches alone). | Toolbar visible with labeled options. |
| User selects a markup type | System creates a PDF annotation of the selected type on the selected text region. Annotation rendered on the page. Annotation added to the annotation summary panel (Feature 12). Document marked as modified (tab dirty flag). | Annotation visible on page. Tab title shows modification indicator. |
| User selects a color for markup | Color applied to the annotation. Default colors: Yellow (Highlight), Red (Underline), Red (Strikethrough) — but each annotation type is always distinguished by **icon + text label** in the annotation panel, never by color alone. | Annotation rendered in selected color. |
| User right-clicks an existing annotation | Context menu: "Edit Properties", "Delete Annotation". | Menu visible. |
| User deletes an annotation | Annotation removed from page and from annotation summary panel. Document marked modified. | Page re-rendered without annotation. |

**Failure States:**

| Condition | User Feedback | Recovery |
|---|---|---|
| Text markup attempted on page with no text layer | Non-modal notification: "Text markup requires selectable text. This page does not have a text layer." Icon + text, not color alone. | Notification auto-dismisses after 5 seconds or on user action. |
| File is read-only (OS permissions) | Non-modal notification: "This file is read-only. Use File > Save As to save a copy with annotations." | User can still add annotations in-memory. Save As works. Save is disabled/grayed with tooltip. |
| Annotation cannot be embedded in a locked/encrypted PDF | Same as read-only notification with Save As guidance. | Same recovery. |

**Accessibility Constraint Enforcement:**
- Annotation type is NEVER conveyed by color alone.
- In the annotation panel (Feature 12): each annotation shows type as **icon + text label** ("Highlight", "Underline", "Strikethrough").
- On the page: different annotation types use different rendering styles (highlight = filled background, underline = line below text, strikethrough = line through text). These are visually distinct by shape/position, not just color.

**Cross-Feature Dependencies:**
- Depends on Feature 1 (rendered document with text layer access).
- Interacts with Feature 2 (sets tab dirty flag).
- Feeds Feature 12 (annotation summary panel).

---

### Feature 7: Sticky Notes and Text Box Annotations

**Priority:** Must-Have (MVP) — Core annotation.

**Business Logic Specification:**

| Trigger | System Action | Output |
|---|---|---|
| User selects the Sticky Note tool | Tool activated from annotation toolbar. Cursor changes to indicate placement mode. Toolbar shows "Sticky Note" tool as active (text label + icon, depressed/bordered state — not color change alone). | Tool active. |
| User clicks a location on the page | Sticky note annotation created at click position. A note editor opens: text area for note content, author name auto-populated from user preferences. | Sticky note icon + text label ("Note") displayed at position on page. Editor open for text input. |
| User finishes editing sticky note | User clicks outside the editor or presses Escape. Note content saved to annotation. If content is empty, prompt: "This annotation is empty. Save anyway?" with Save / Delete buttons. | Note displayed as icon with truncated preview on hover/click. Entry added to annotation summary panel. |
| User selects the Text Box tool | Tool activated. Cursor changes to crosshair. | Tool active. |
| User draws a text box on the page | Click-drag defines the text box rectangle. Text input area appears within the box. | Text box visible on page with editable content area. |
| User finishes editing text box | Same empty-check as sticky note. Content rendered inline on the page within the box boundaries. | Text box visible with content. |
| User edits an existing annotation | Double-click on annotation → editor opens with existing content. | Editor open for modification. |

**Failure States:**

| Condition | User Feedback | Recovery |
|---|---|---|
| Empty annotation on save | Dialog: "This annotation is empty. Save anyway?" Save / Delete. | User chooses. Delete removes it. Save keeps empty annotation. |
| Annotation placed outside page bounds | Annotation snaps to nearest valid position within page. | Transparent correction. |
| Annotations from external tools | Displayed with original author name and "External" label in the type column of the annotation panel. Fully editable. | Compatible with standard PDF annotation spec. |

**Accessibility:**
- Sticky notes on page: icon + text label ("Note"), never icon alone.
- Text boxes: visible border (not color-only) when selected.
- Annotation panel: type column shows text label + icon for all annotation types.

**Cross-Feature Dependencies:**
- Same as Feature 6: depends on Feature 1, interacts with Feature 2, feeds Feature 12.

---

### Feature 8: AcroForm Filling and Save

**Priority:** Must-Have (MVP) — Core utility.

**Business Logic Specification:**

| Trigger | System Action | Output |
|---|---|---|
| User opens a PDF containing AcroForm fields | System detects AcroForm fields via PyMuPDF's `doc.is_form_pdf` or equivalent. Fields automatically activated — text fields show as editable input areas, checkboxes show as toggleable, dropdowns show option lists, radio buttons show as selectable groups. | Form fields visible and interactive. Visual indicator that form mode is active (status bar text: "This document contains [N] form fields"). |
| User clicks a text field | Field receives focus. Text cursor appears. User types input. | Text appears in field. Tab key moves to next field. |
| User clicks a checkbox | Checkbox toggles checked/unchecked state. | Visual state change (checkmark appears/disappears). |
| User selects from a dropdown | Dropdown options displayed. User selects one. | Selected value shown in field. |
| User selects a radio button | Selected radio button filled. Others in group deselected. | Visual state change. |
| User saves (File > Save or Ctrl+S / Cmd+S) | System embeds all form data into the PDF using PyMuPDF's form-save API. File written to its original location. | File saved. Tab dirty flag cleared. Status bar: "Saved." |
| User saves to new location (File > Save As) | Save dialog opens. User specifies path. Form data embedded in new file. | New file created. Tab now references new file path. |

**Failure States:**

| Condition | User Feedback | Recovery |
|---|---|---|
| PDF contains XFA dynamic forms | Non-modal notification: "This document uses XFA dynamic forms, which are not supported. Only AcroForms are supported." Icon + text. | AcroForm fields (if any coexist) still work. XFA fields non-interactive. |
| PDF has no form fields | No notification needed — document simply has no interactive fields. Status bar does not show form field count. | Normal viewing mode. |
| Form field validation fails (embedded rules) | Field-level error displayed as text label adjacent to the field (red-bordered text, not color alone — includes error icon + message text). | User corrects input. Validation re-evaluated on change. |
| Save fails (permissions, disk full, path invalid) | Error dialog: "Cannot save [filename]: [OS error message]. Use File > Save As to save to a different location." | User uses Save As or resolves OS issue. |
| Partially filled form | Allowed to save without warning. Partially filled is a valid state. | Normal save. |

**Implicit Dependencies:**
1. **Font handling** — Form fields use fonts defined in the PDF. PyMuPDF handles this, but edge cases exist with missing or subset-embedded fonts. **Flag: Test form filling with diverse real-world forms (government forms, financial forms, etc.).**
2. **Save architecture** — File > Save must handle the case where the file is open by the OS or another application. On Windows, file locking is aggressive. **Flag: Define save-failure recovery per platform.**

---

### Feature 9: Page Management — Add, Delete, Reorder, Rotate Pages

**Priority:** Must-Have (MVP) — Core editing.

**Business Logic Specification:**

| Trigger | System Action | Output |
|---|---|---|
| User opens page management panel | Panel appears (can replace or coexist with navigation panel). All pages shown as thumbnails in a scrollable grid. Multi-select supported (Ctrl+Click, Shift+Click). | Grid of page thumbnails with page numbers. |
| User drags pages to reorder | Drag one or more selected pages to a new position. Drop indicator shows insertion point. | Pages reordered. Document marked modified. |
| User rotates selected pages | Toolbar buttons in panel: "Rotate Left (90°)" and "Rotate Right (90°)" — labeled with icon + text. Rotation applied to selected pages. **This writes rotation to the PDF** (unlike Feature 5 view rotation). | Thumbnails update to show rotated pages. Document marked modified. |
| User deletes selected pages | Confirmation dialog: "Delete [N] page(s)? This cannot be undone after saving." Delete / Cancel. If deleting would leave 0 pages: "A PDF must contain at least one page." (delete blocked). | Pages removed. Thumbnails update. Document marked modified. |
| User adds pages | "Add Pages" button → file picker for selecting another PDF. Pages from selected file inserted at the current selection point (or end if nothing selected). | New pages inserted. Thumbnails update. Document marked modified. |
| Operations on large documents (100+ pages) | Progress indicator shown for operations taking >1 second. Cancel available for long operations. | Progress bar with text: "Reordering pages... [X]%". |

**Failure States:**

| Condition | User Feedback | Recovery |
|---|---|---|
| Attempt to delete all pages | Blocked. Error text: "A PDF must contain at least one page." | Delete button disabled when all pages selected. |
| Add pages from corrupt/invalid PDF | Error dialog: "Cannot read [filename]: [reason]." Skipped. | Remaining operation completes. |
| Reorder on very large document causes lag | Progress indicator. UI remains responsive (operation runs in background thread). | Operation completes. Cancel aborts and reverts. |

**Critical Distinction — UI Must Be Clear:**
- Feature 5 rotation = VIEW rotation (temporary, per-session, View menu)
- Feature 9 rotation = PAGE rotation (permanent, modifies PDF, Page Management panel)
- **Both must be clearly labeled. Feature 9 rotation buttons should include text like "Rotate Page (modifies file)" to distinguish from view rotation.**

**Cross-Feature Dependencies:**
- Depends on Feature 1.
- Page deletion/reorder affects Feature 3 (thumbnails/outline), Feature 4 (search results), Feature 12 (annotation positions).
- Add pages is closely related to Feature 10 (Merge) — add pages inserts from another PDF.

---

### Feature 10: Merge Multiple PDFs

**Priority:** Must-Have (MVP) — Core utility.

**Business Logic Specification:**

| Trigger | System Action | Output |
|---|---|---|
| User selects File > Merge Documents | File picker opens allowing multiple PDF selection. Selected files listed in a merge queue panel. | Merge queue panel showing selected files with their page counts. |
| User adjusts merge order | Drag-and-drop to reorder files in the merge queue. Remove button (labeled "Remove" with icon) per file. | Queue reflects new order. |
| User initiates merge | User clicks "Merge" button. System prompts for output file path via save dialog. System merges all source files in queue order into a single output PDF. | Progress indicator: "Merging... [X] of [N] files." Output file created at specified path. |
| Merge completes | Status notification: "Merge complete. [N] files merged into [output filename]." Option to open the merged file. | Notification with "Open" button. |

**Failure States:**

| Condition | User Feedback | Recovery |
|---|---|---|
| Source file is corrupt or unreadable | Warning in merge queue: "[filename]: Cannot read — [reason]. This file will be skipped." Merge queue shows file with error icon + text. User can remove it or proceed. | Merge proceeds with remaining files. Final notification lists skipped files. |
| Source file is password-protected | Password prompt per protected file. If user cancels, file is skipped with notification. | Same as above. |
| Output path is read-only or invalid | Error dialog: "Cannot save to [path]: [reason]. Choose a different location." Save dialog reopens. | User selects valid path. |
| Merge of 0 files | Blocked. "Select at least two files to merge." | Merge button disabled until ≥2 files in queue. |
| Merge of 1 file | Blocked. Same message as above. | Same as above. |
| Very large merge (20+ files) | Progress indicator with per-file progress and cancel button. | Cancel aborts, no partial output written. |

**Cross-Feature Dependencies:**
- Output file can be opened in a new tab (Feature 2).
- Merge output is a new file — does not modify any source file.

---

### Feature 11: Dark / Night Reading Mode

**Priority:** Must-Have (MVP) — UX essential for the Orchestrator.

**Business Logic Specification:**

| Trigger | System Action | Output |
|---|---|---|
| User activates dark mode via View menu or keyboard shortcut (Ctrl+D / Cmd+D) | Application UI switches to dark theme. Mode toggle is a labeled control: text + icon, never icon-only. | UI elements (menus, toolbars, panels, status bar) switch to dark palette. |
| User selects sub-mode | Two labeled sub-modes available in View menu or settings: (1) "Dark UI / Original PDF" — UI is dark, PDF rendering unchanged. (2) "Dark UI / Inverted PDF" — UI is dark, PDF rendering layer inverted (light↔dark). | Sub-mode indicator in status bar as text: "Dark Mode: Original PDF" or "Dark Mode: Inverted PDF". |
| User deactivates dark mode | Same toggle. UI returns to light theme. | Light theme applied. Status bar: "Light Mode". |
| Inverted rendering | Rendering layer applies color inversion to the PDF display. **Does NOT modify the PDF file.** Images may appear odd when inverted — this is expected behavior, documented. | PDF appears with inverted colors in the viewport only. Saved/exported PDF is unmodified. |

**Failure States:**

| Condition | User Feedback | Recovery |
|---|---|---|
| Mode preference fails to persist | Defaults to Light Mode. No error — silent fallback. | User re-selects. Investigate preferences storage issue. |
| Inverted mode causes readability issues on certain PDFs | No automatic handling. User switches to "Original PDF" sub-mode. | User choice. Documented limitation: inversion may reduce readability on image-heavy or already-dark PDFs. |

**Accessibility Constraint:**
- Mode toggle MUST be labeled with text, never icon-only.
- Mode indicator in status bar uses text, not color alone.
- Dark/light mode does not affect the accessibility of other UI elements — all contrast ratios must meet WCAG AA in both modes.

**Cross-Feature Dependencies:**
- Mode state persists across sessions (user preference).
- Inverted rendering interacts with annotation display — annotations must remain distinguishable in both modes.

---

### Feature 12: Annotation Summary Panel

**Priority:** Must-Have (MVP) — Annotation management.

**Business Logic Specification:**

| Trigger | System Action | Output |
|---|---|---|
| User opens the annotation panel | Panel appears (right side or bottom, distinct from navigation panel). Lists all annotations in the active document. | Panel visible with annotation list. |
| Annotation list entry | Each entry shows: page number (numeric), annotation type (text label + icon: "Highlight", "Underline", "Strikethrough", "Sticky Note", "Text Box"), author name, timestamp (date + time). | Tabular or list layout with all columns visible. Sortable by column. |
| User clicks an annotation entry | Main viewport navigates to the page containing that annotation and scrolls to the annotation's position. Annotation briefly highlighted (border flash or similar non-color-only indicator). | Viewport shows the annotation. |
| Annotation added/deleted | Panel updates immediately. If an annotation is added, it appears in the list. If deleted, it disappears. | Real-time sync. |
| Panel filter/sort | Filter by annotation type (dropdown with text labels). Sort by page number, type, author, or date. | Filtered/sorted list. |

**Failure States:**

| Condition | User Feedback | Recovery |
|---|---|---|
| No annotations in document | Empty state: "No annotations in this document." (text, centered in panel). | Informative empty state. |
| 500+ annotations | Virtual scrolling to maintain panel responsiveness. No performance degradation. | Smooth scrolling. |
| Annotation missing metadata (no author, no timestamp) | Display available fields. Missing fields show as empty or "—". No crash. | Graceful degradation. |
| Annotations created by external tools | Displayed with original metadata. Author shows original author name. Type shows closest match to K-PDF annotation types, or "Unknown" with icon. | Full compatibility with standard PDF annotations. |

**Accessibility Constraint:**
- Annotation type column: always text label + icon, never icon-only, never color-only.
- Sortable columns have text labels.
- Keyboard navigable (arrow keys to move between entries, Enter to navigate to annotation).

---

## 3. Cross-Feature Analysis

### 3.1 Contradictions Found

**None identified.** The Intake is internally consistent. The Feature 5 / Feature 9 rotation distinction is explicitly documented and not contradictory — it's a deliberate design decision.

### 3.2 Implicit Dependencies Not Listed in Intake

| Dependency | Required By | Recommendation |
|---|---|---|
| **Undo/Redo system** | Features 6, 7, 8, 9 (any modification operation) | The Intake mentions "undo/redo history stack (in-session only)" in Section 5.4 as ephemeral data, but no feature specification describes its behavior. **Recommendation: Add Undo/Redo as an implicit requirement of the annotation and page management features. Define: scope (per-tab), depth (configurable, default 50 operations), persistence (in-session only, lost on tab close).** |
| **Keyboard shortcut system** | All features reference keyboard shortcuts | A unified shortcut system is implied but not specified. **Recommendation: Define the complete shortcut map as an appendix to the FRD. Ensure no conflicts. Support customization as a post-MVP feature.** |
| **User preferences system** | Features 5, 11, 12 and general UX | The Intake mentions preferences in Section 5.4 but no feature describes the preferences UI. **Recommendation: Add a Settings/Preferences dialog as an implicit dependency, not a separate MVP feature. It's the access point for: default zoom, dark mode, annotation author name, recent files list length, panel layout.** |
| **Printing** | Not listed as MVP or Will-Not-Have | The Intake lists virtual printer as Will-Not-Have but does not mention basic OS print dialog (File > Print → send to system printer). **Flag for Orchestrator: Is basic printing (send to OS print dialog) in scope for MVP? It's expected in any PDF reader. If excluded, add to Will-Not-Have list explicitly.** |
| **Copy text** | Implied by text selection in Feature 6 | If the user can select text for markup, they expect Ctrl+C/Cmd+C to copy it. Not listed as a feature. **Recommendation: Add text copy to clipboard as an implicit capability of the text selection mechanism.** |
| **File > Save As** | Referenced in Features 6, 8 | Save As is referenced in failure states but not specified as a standalone flow. **Recommendation: Specify Save As as part of the file operations, not a separate feature.** |
| **OS file association** | Feature 1 (double-click to open) | Nuitka packaging must register K-PDF as a .pdf handler. Platform-specific concern for Phase 1/4. |
| **Application auto-save or crash recovery** | All modification features | Not mentioned. If the application crashes with unsaved changes, work is lost. **Flag for Orchestrator: Is auto-save (periodic save to a temp file) desired for MVP, or is explicit-save-only acceptable?** |

### 3.3 Will-Not-Have Validation

Checking if any Must-Have implicitly requires something on the exclusion list:

| Will-Not-Have | Conflict? | Assessment |
|---|---|---|
| Virtual printer driver | No | Feature set uses File > Save, not system print. **But see printing flag above.** |
| XFA dynamic forms | No | Feature 8 explicitly handles only AcroForms and shows an error for XFA. |
| OCR / text layer generation | No | Features 4 and 6 gracefully degrade when no text layer exists. |
| Cloud sync / accounts / telemetry | No | No feature requires network. |
| Form field creation | No | Feature 8 fills existing fields only. |
| Collaborative editing | No | Single-user application. |
| Word-processor text editing | No | No feature attempts in-place text reflow. Find-and-replace is post-MVP. |

**No conflicts between Must-Have and Will-Not-Have lists.**

### 3.4 Recommendations (Not Additions — Flagged Separately)

These are NOT feature additions. They are implicit capabilities required by the specified features:

1. **Undo/Redo** — Required by Features 6, 7, 8, 9. Scope: per-tab, in-session only.
2. **Keyboard shortcut map** — Required by all features. Unified, non-conflicting.
3. **Preferences dialog** — Required by Features 5, 11, and general UX. Access point for settings that persist.
4. **Text copy to clipboard** — Implied by text selection in Feature 6.
5. **File > Save As flow** — Referenced but not fully specified.
6. **Recent files list** — Mentioned in preferences but needs specification.

### 3.5 Open Questions for Orchestrator

1. **Printing:** Is basic OS print dialog (File > Print) in scope for MVP? Every PDF reader has it. If excluded, add to Will-Not-Have explicitly.
2. **Auto-save:** Should K-PDF auto-save to a temp file periodically, or is explicit-save-only acceptable for MVP?
3. **Large file strategy:** For PDFs >100MB, accept full memory load (with progress indicator) or implement true streaming? PyMuPDF loads fully by default.
4. **Undo/Redo depth:** Default 50 operations per tab acceptable?

---

## 4. Review Checklist

- [x] Every Must-Have has a logic trigger (If X, then Y) — expanded to complete specifications
- [x] Every Must-Have has defined failure states — expanded to complete error/recovery flows
- [x] No feature described in vague terms — all specifications include concrete UI behavior
- [x] Will-Not-Have list validated — no conflicts with Must-Have features
- [x] Implicit dependencies identified and flagged
- [x] Cross-feature dependencies mapped
- [x] Accessibility constraints enforced per feature (color-independence verified)
- [x] Open questions documented for Orchestrator decision
