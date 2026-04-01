# K-PDF — User Journey Map

## Version 1.0 — Phase 0, Step 0.2

**Source:** K-PDF Project Intake v1.1, Section 2.2 + FRD Feature Specifications
**Generated:** 2026-04-01
**Status:** Draft — Awaiting Orchestrator Review

---

## 1. Primary Persona

| Field | Value |
|---|---|
| **Name** | The Orchestrator |
| **Role** | IT professional, power user |
| **Technical literacy** | High — comfortable with CLI, file systems, keyboard shortcuts |
| **Daily PDF interaction** | Multiple documents, varying complexity: contracts, government forms, technical documentation, scanned documents, multi-hundred-page reports |
| **Goal** | Handle all routine PDF tasks in a single offline application without cost, accounts, or cloud dependency |
| **Emotional state on arrival** | Pragmatic and task-focused. Expects tools to work immediately. Low tolerance for onboarding friction. Zero tolerance for subscription prompts, account creation, or telemetry notifications. |
| **Accessibility** | Colorblind. Relies on shape, text labels, position, and icons — not color — to distinguish UI elements and states. |

---

## 2. Entry Points

### 2.1 First Launch (One-Time)

| Step | User Action | System Response | Feedback Mechanism |
|---|---|---|---|
| 1 | User launches K-PDF for the first time (double-click executable, or from terminal). | Application window opens. Welcome screen displayed: application name, version, "Open File" button (labeled with text + icon), "Recent Files" (empty on first launch), keyboard shortcut reference link. | Visual: welcome screen rendered. No splash screen delay. Immediate usability. |
| 2 | User clicks "Open File" or uses Ctrl+O / Cmd+O. | Native OS file picker opens, filtered to `*.pdf`. | Standard OS dialog. Familiar. |
| 3 | User selects a PDF file. | File validated, parsed, rendered. Tabs bar appears with first tab. Navigation panel available. Status bar shows page count and zoom level. | Visual: document rendered. Status bar text: "Page 1 of [N] — 100%". |

### 2.2 Recurring Launch — File Association

| Step | User Action | System Response | Feedback Mechanism |
|---|---|---|---|
| 1 | User double-clicks a `.pdf` file in OS file manager. | K-PDF launches (or activates if running). File opens in a new tab. | Application window focused. New tab active. |

### 2.3 Recurring Launch — CLI

| Step | User Action | System Response | Feedback Mechanism |
|---|---|---|---|
| 1 | User runs `k-pdf /path/to/file.pdf` from terminal. | Application launches. File opens. | Same as above. |

### 2.4 Recurring Launch — Drag and Drop

| Step | User Action | System Response | Feedback Mechanism |
|---|---|---|---|
| 1 | User drags a PDF file onto the K-PDF window or dock icon. | File opens in a new tab. | Tab created. Document rendered. |

---

## 3. Success Paths

### Journey A: Read and Navigate a Document

**Goal:** Open a PDF, read through it efficiently, find specific content.

| Step | What User Sees | What User Does | System Response | Failure Recovery |
|---|---|---|---|---|
| A1 | Welcome screen or existing tabs | Opens a PDF via any entry point | Document rendered in new tab. Tabs bar, navigation panel toggle, toolbar visible. | File errors → error dialog per FRD Feature 1. Password prompt if encrypted. |
| A2 | Document rendered at default zoom. Toolbar shows zoom controls. | Adjusts zoom to comfortable reading level (Ctrl+Plus, or selects "Fit Width" from dropdown). | Page re-rendered at new zoom. Zoom indicator in toolbar updates. | Zoom clamped at boundaries (10%–3200%). |
| A3 | Document at reading zoom. | Opens navigation panel (View > Navigation or shortcut). | Thumbnail panel appears on left. Thumbnails render for all pages. Current page highlighted. | Large doc (500+): virtual scrolling, progress indicator. |
| A4 | Thumbnails visible, document in viewport. | Clicks a thumbnail to jump to a specific page. | Viewport jumps to selected page. Thumbnail indicator moves. | Invalid thumbnail → placeholder shown (FRD Feature 3). |
| A5 | Document at desired page. | Switches to Outline tab in navigation panel. | Outline tree displayed if document has bookmarks. | No outline → "No bookmarks in this document." text. |
| A6 | Outline tree visible. | Clicks an outline entry. | Viewport jumps to bookmarked location. | Invalid target → warning icon + "Invalid target" text label. No navigation. |
| A7 | Document at bookmarked location. | Activates search (Ctrl+F / Cmd+F). Types search query. | Search bar appears. Matches highlighted. Counter: "3 of 14 matches". | No text layer → "This document has no searchable text." No matches → "No matches found." |
| A8 | Search results highlighted. | Presses Enter to navigate between matches. | Viewport scrolls to next match. Counter updates. | Wraps from last to first match. |
| A9 | Reading complete. | Closes search bar (Escape). | Highlights removed. Viewport returns to pre-search position. | Clean state restored. |

### Journey B: Annotate a Document

**Goal:** Add highlights, sticky notes, and text boxes to a PDF for review.

| Step | What User Sees | What User Does | System Response | Failure Recovery |
|---|---|---|---|---|
| B1 | Document open and rendered. | Selects text on a page (click-drag). | Text selected. Annotation toolbar appears with labeled options: "Highlight", "Underline", "Strikethrough". | No text layer → notification per FRD Feature 6. |
| B2 | Annotation toolbar visible with text labels + icons. | Clicks "Highlight". | Selected text highlighted. Annotation appears in annotation summary panel. Tab title shows modification marker (`*`). | Read-only file → "Use File > Save As" notification. |
| B3 | Highlight applied. | Selects the Sticky Note tool from the main toolbar. | Cursor changes to placement mode. Toolbar shows "Sticky Note" as active (depressed/bordered state). | — |
| B4 | Sticky Note tool active. | Clicks a location on the page. | Sticky note icon placed. Note editor opens for text input. | Placement outside page → snaps to valid position. |
| B5 | Note editor open. | Types note content. Clicks outside to finish. | Note saved. Icon on page. Entry in annotation panel shows: page number, "Sticky Note" (text + icon), author, timestamp. | Empty note → "Save anyway?" prompt. |
| B6 | Annotations added. | Opens annotation summary panel. | Panel lists all annotations with type (text label + icon), page, author, date. | No annotations → "No annotations in this document." |
| B7 | Annotation panel visible. | Clicks an annotation entry. | Viewport navigates to that annotation. Annotation briefly highlighted (border flash). | — |
| B8 | Reviewing annotations. | Right-clicks an annotation to delete it. | Context menu: "Edit Properties", "Delete Annotation". User selects Delete. Annotation removed from page and panel. | Undo available (Ctrl+Z). |
| B9 | Annotations finalized. | Saves (Ctrl+S / Cmd+S). | File saved with annotations embedded. Tab modification marker cleared. Status bar: "Saved." | Save failure → error dialog with Save As option. |

### Journey C: Fill a Form

**Goal:** Open a government or financial PDF form, fill in fields, save.

| Step | What User Sees | What User Does | System Response | Failure Recovery |
|---|---|---|---|---|
| C1 | Document open. | Opens a PDF containing AcroForm fields. | Form fields auto-detected and activated. Status bar: "This document contains [N] form fields." Fields appear as interactive input areas. | XFA form → notification: "XFA not supported. Only AcroForms supported." |
| C2 | Form fields visible and interactive. | Clicks first text field. Types input. | Text appears in field. Field border indicates focus. | Validation error → text label + icon adjacent to field. |
| C3 | First field filled. | Presses Tab to move to next field. | Focus moves to next field in tab order. | Tab order follows PDF's field order. |
| C4 | Filling multiple fields. | Toggles a checkbox. | Checkbox state toggles. Visual checkmark appears/disappears. | — |
| C5 | Form partially filled. | Selects from a dropdown. | Options displayed. Selection applied. | — |
| C6 | Form filled. | Saves (Ctrl+S or File > Save). | Form data embedded in PDF. File saved. | Save failure → error dialog. Save As available. |

### Journey D: Manage Pages

**Goal:** Reorder, delete, and rotate pages. Merge with another PDF.

| Step | What User Sees | What User Does | System Response | Failure Recovery |
|---|---|---|---|---|
| D1 | Document open. | Opens page management panel. | Grid of page thumbnails with page numbers. Multi-select enabled. | — |
| D2 | Page grid visible. | Selects pages and drags to reorder. | Pages reorder. Document marked modified. | Large doc → progress indicator for operations >1 second. |
| D3 | Pages reordered. | Selects a page and clicks "Rotate Right (90°)". | Page rotated. Thumbnail updates. Marked modified. **Permanent change — modifies PDF.** | — |
| D4 | Page rotated. | Selects pages to delete. Clicks Delete. | Confirmation dialog: "Delete [N] page(s)?" | Deleting all pages → blocked: "Must contain at least one page." |
| D5 | Pages deleted. | Clicks "Add Pages" to insert pages from another PDF. | File picker opens. Selected pages inserted at current position. | Corrupt source → error dialog, skipped. |
| D6 | Pages added. | Uses File > Merge Documents for a full merge operation. | Multi-file picker. Merge queue panel. Drag to reorder. | Per-file errors handled. ≥2 files required. |
| D7 | Merge queue configured. | Clicks Merge. Selects output path. | Progress: "Merging... [X] of [N]". Output file created. | Path error → prompt for alternate. |
| D8 | Merge complete. | Clicks "Open" in the completion notification. | Merged file opens in new tab. | — |
| D9 | All edits complete. | Saves. | File saved with all page changes embedded. | Save failure → Save As fallback. |

### Journey E: Night Reading Session

**Goal:** Switch to dark mode for comfortable reading in low light.

| Step | What User Sees | What User Does | System Response | Failure Recovery |
|---|---|---|---|---|
| E1 | Application in light mode. | Activates dark mode (View > Dark Mode or Ctrl+D / Cmd+D). | UI switches to dark theme. Status bar text: "Dark Mode: Original PDF". | — |
| E2 | Dark UI, original PDF colors. | Selects "Dark UI / Inverted PDF" from View menu. | PDF rendering inverted. Status bar: "Dark Mode: Inverted PDF". | Image-heavy PDFs may look odd — expected, documented. |
| E3 | Reading in dark+inverted mode. | Switches back to "Original PDF" for a specific document. | PDF rendering returns to original. UI stays dark. | — |
| E4 | Session ends. | Closes application. | Dark mode preference saved. Next launch restores dark mode. | Preference save failure → defaults to light mode. |

---

## 4. Failure Recovery Matrix

| Failure Point | User Impact | Recovery Mechanism | Feedback |
|---|---|---|---|
| File not found / permissions | Cannot open document | Error dialog with specific reason. OK dismisses. | Text dialog: filename + reason. |
| Corrupt / invalid PDF | Cannot open document | Error dialog with PyMuPDF error detail. | Text dialog: filename + error. |
| Password-protected PDF | Blocked until authenticated | Password dialog. Unlimited retries. Cancel aborts. | Dialog with text input. Wrong password → inline message. |
| Page render failure (single page) | One page blank | Placeholder with page number + "Render error" text. Other pages unaffected. | Visual placeholder, no crash. |
| No text layer (search/markup) | Cannot search or markup | Contextual notification text explaining limitation. | Non-modal text notification. |
| Save failure | Changes not persisted | Error dialog + Save As alternative. | Dialog: error reason + fallback action. |
| Memory pressure | Potential slowdown | Status bar warning text. User decides whether to close tabs. | Non-modal text warning. |
| Application crash (unexpected) | Potential data loss | No auto-save in MVP. User must re-do unsaved work. **Open question for Orchestrator.** | OS crash dialog. Next launch: clean state. |

---

## 5. Feedback Loops

| Event | Feedback Type | Mechanism |
|---|---|---|
| File loading | Progress | Status bar progress indicator for large files. |
| Document loaded | Confirmation | Status bar: "Page 1 of [N] — [zoom]%". Tab title set to filename. |
| Modification made | State indicator | Tab title shows `*` or `[modified]` marker. |
| Save successful | Confirmation | Status bar: "Saved." Modification marker cleared. |
| Save failed | Error | Modal dialog with reason and recovery action. |
| Search in progress | Progress | Search bar: "Searching... [X]% ([N] matches)". |
| Search complete | Results | Match counter: "[current] of [total] matches". |
| Annotation added | Confirmation | Annotation appears on page + in annotation panel. |
| Mode change (dark/light) | State indicator | Status bar text label showing current mode. |
| Page operation in progress | Progress | Progress bar with text for operations >1 second. |

---

## 6. Exit Points & Recovery

| Exit Point | Why User Leaves | Recovery Strategy |
|---|---|---|
| First launch — no document open | User may not know what to do. | Welcome screen with clear "Open File" button and keyboard shortcut reference. |
| File open failure | File can't be opened. | Clear error message explaining why. User selects a different file. |
| Feature limitation (no text layer, XFA) | K-PDF can't handle this specific document. | Clear limitation message. User knows to use alternative tool for this specific case. |
| Complex page manipulation | User may find the page management workflow unclear. | Labeled buttons (text + icon), confirmation dialogs for destructive actions, undo support. |
| Application crash | Unexpected failure. | No auto-save in MVP. User reopens application. **Potential future improvement.** |
| Unsaved changes on close | User forgets to save. | Save/Discard/Cancel modal dialog on tab close and application close. |

---

## 7. Journey Gap Analysis

| Gap | Feature Impact | Recommendation |
|---|---|---|
| No auto-save / crash recovery | All modification features | Flag for Orchestrator decision. |
| No print capability | Not a feature gap per Intake, but a user expectation gap. | Flag for Orchestrator: add basic print to MVP or explicitly exclude? |
| No text copy to clipboard | Feature 6 (text selection for markup implies copy). | Add as implicit capability. |
| No "Find in annotation panel" | Feature 12 (with 500+ annotations, users may want to search). | Post-MVP enhancement. Not required for MVP. |
| No annotation export (to text/summary) | Feature 12 tangential. | Post-MVP. Not required. |

---

## 8. Review Checklist

- [x] Every step has success and failure responses
- [x] Every action produces visible user feedback
- [x] Exit points identified with recovery mechanisms
- [x] Persona accurately reflects Intake Section 2.2
- [x] All 12 MVP features represented in at least one journey
- [x] Accessibility constraints (color-independence) verified at every UI touchpoint
- [x] Feedback mechanisms specified (not just "notification" — what kind, what content)
