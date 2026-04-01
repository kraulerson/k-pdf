# K-PDF — Data Contract

## Version 1.0 — Phase 0, Step 0.3

**Source:** K-PDF Project Intake v1.1, Section 5 + FRD + User Journey Map
**Generated:** 2026-04-01
**Status:** Draft — Awaiting Orchestrator Review

---

## 1. Data Inputs

### 1.1 PDF File (Primary Input)

| Field | Value |
|---|---|
| **Data type** | Binary file |
| **Entry points** | File > Open, drag-and-drop, CLI argument, OS file association |
| **Validation rules** | (1) File exists at path. (2) File is readable (OS permissions). (3) First bytes contain `%PDF-` header. (4) No maximum file size enforced — but 500-page documents must perform within spec. (5) File extension: `.pdf` (warning if missing but `%PDF-` header present — open anyway). |
| **Sensitivity** | Confidential — user-controlled. May contain anything: PII, financial data, legal documents, medical records. K-PDF never transmits, copies, or caches file content outside the user's explicit actions (save, save as). |
| **Required?** | Yes — the application has no function without a PDF file. |

### 1.2 Annotation Content (User-Created)

| Field | Value |
|---|---|
| **Data type** | Text (UTF-8) |
| **Entry points** | Sticky note editor, text box editor |
| **Validation rules** | Max 10,000 characters per annotation. No format restrictions (plain text). Stored in PDF annotation metadata fields per PDF spec. No external storage. |
| **Sensitivity** | Confidential — user-controlled. |
| **Required?** | No — annotations are optional. |

### 1.3 Form Field Input (User-Entered)

| Field | Value |
|---|---|
| **Data type** | Text (text fields), Boolean (checkboxes), Selection (dropdowns, radio buttons) |
| **Entry points** | Interactive AcroForm fields in the rendered document |
| **Validation rules** | Per-field type validation per the PDF's AcroForm field dictionary. Text fields: max length per field definition. Checkboxes: on/off. Dropdowns: value must be in the defined option list. Radio: one-of-group. |
| **Sensitivity** | Confidential — user-controlled. Form data is typically PII (names, addresses, SSNs, financial data). |
| **Required?** | No — form filling is optional. |

### 1.4 User Preferences / Settings

| Field | Value |
|---|---|
| **Data type** | Structured (SQLite database or JSON file) |
| **Entry points** | Application settings/preferences dialog, implicit capture (window size, panel state) |
| **Validation rules** | Schema-validated on read. If schema version mismatch: migrate forward. If migration fails: reset to defaults with user notification. |
| **Sensitivity** | Internal — no PII. Contains: zoom default, dark mode state, panel layout, recent files list (file paths), annotation author name. |
| **Required?** | No — defaults used if no preferences file exists. |
| **Storage location** | OS-standard config directory: `%APPDATA%\K-PDF` (Windows), `~/.config/k-pdf` (Linux), `~/Library/Application Support/K-PDF` (macOS). |

### 1.5 Password for Encrypted PDFs

| Field | Value |
|---|---|
| **Data type** | Text (UTF-8) |
| **Entry points** | Password dialog when opening an encrypted PDF |
| **Validation rules** | Passed directly to PyMuPDF for decryption. |
| **Sensitivity** | **Critical.** Never stored to disk. Never logged. Never written to preferences, history, or any persistent storage. Cleared from memory after use (overwrite the string, do not rely on garbage collection). Held only for the duration of the decryption call. |
| **Required?** | Conditional — only when opening password-protected PDFs. |

---

## 2. Data Transformations

### 2.1 PDF Parse Pipeline

```
Input: PDF file bytes
  → Validate header (%PDF-)
  → PyMuPDF document open (fitz.open())
  → Extract metadata (page count, title, author, outline, form presence)
  → For each visible page: render to pixmap at current zoom/rotation
  → Cache rendered pixmaps (in-memory, per-tab)
Output: Rendered page images in viewport + document metadata for UI
```

### 2.2 Annotation Pipeline

```
Input: User action (text selection + markup type, or placement + note content)
  → Create annotation object (PyMuPDF annotation API)
  → Write annotation to document's in-memory representation
  → Re-render affected page
  → Update annotation summary panel
  → Set tab dirty flag
Output: Annotation visible on page + entry in annotation panel
```

### 2.3 Form Fill Pipeline

```
Input: User input in form field
  → Validate input per field definition
  → Write value to field in document's in-memory representation
  → Set tab dirty flag
Output: Field value visible in form + tab marked modified
```

### 2.4 Save Pipeline

```
Input: Save command (Ctrl+S or File > Save)
  → If file path is original and writable:
    → PyMuPDF incremental save (preserves original structure, appends changes)
    → Verify write succeeded (file size > 0, no OS error)
    → Clear tab dirty flag
  → If file is read-only or Save As:
    → Save dialog → user selects new path
    → Full save to new path
    → Update tab to reference new path
Output: Modified PDF file on disk
```

### 2.5 Page Management Pipeline

```
Input: Page operation (reorder, delete, rotate, add)
  → Apply operation to in-memory document representation
  → Re-render affected thumbnails
  → Update page count metadata
  → Set tab dirty flag
  → If delete: validate at least 1 page remains
Output: Modified document in-memory, ready for save
```

### 2.6 Merge Pipeline

```
Input: List of PDF file paths in user-defined order
  → For each source file:
    → Validate (exists, readable, valid PDF header)
    → If password-protected: prompt for password
    → Open with PyMuPDF
  → Create new empty document
  → Insert pages from each source in order
  → Save to user-specified output path
Output: New merged PDF file on disk
```

### 2.7 Search Pipeline

```
Input: Search query string + options (case sensitive, whole word)
  → For each page in document:
    → Extract text (PyMuPDF page.get_text())
    → Search for query matches
    → Record match positions (page number, coordinates)
  → Highlight all matches on rendered pages
  → Navigate to first match
Output: Highlighted matches in viewport + match counter
```

---

## 3. Data Outputs

| Output | Format | Latency Expectation | Notes |
|---|---|---|---|
| Modified PDF (annotations, form data, page edits) | PDF binary | < 5 seconds for 500-page document save | Incremental save preferred for performance. Full save for Save As. |
| Merged PDF | PDF binary | < 10 seconds for 5 source documents; < 30 seconds for 20 source documents | New file — does not modify sources. |
| Rendered page (viewport) | In-memory pixmap (QPixmap/QImage) | < 200ms per page at standard zoom on development hardware | Lazy rendering: only visible pages + buffer. |
| Search results | In-memory match list + viewport highlights | < 3 seconds for full-document search on 500-page document | Progressive results acceptable for very large documents. |

---

## 4. Third-Party Data

**None.** K-PDF has zero third-party integrations. No APIs, no network calls, no telemetry endpoints. The application must function with the host machine's network adapter disabled.

No fallback behavior needed — there is nothing to fall back from.

---

## 5. State & Persistence

### 5.1 Persistent Data (Across Sessions)

| Data | Storage | Format | Migration Strategy |
|---|---|---|---|
| User preferences (zoom default, dark mode, panel layout, annotation author name) | OS config directory | SQLite or JSON (Phase 1 decision) | Schema version field. Forward migration on version mismatch. Reset to defaults if migration fails. |
| Recent files list (ordered list of file paths, max 20) | OS config directory (same file/db as preferences) | Same as above | Same as above. Paths are validated on display — stale paths shown grayed with "File not found" label. |
| Window size and position | OS config directory | Same as above | Same. Invalid values (off-screen, negative) → reset to defaults. |

### 5.2 Ephemeral Data (In-Session Only)

| Data | Scope | Lifecycle |
|---|---|---|
| Rendered page cache (pixmaps) | Per-tab | Created on render. Invalidated on zoom/rotation change. Released on tab close. LRU eviction if memory pressure. |
| Undo/redo history stack | Per-tab | Created per modification. Lost on tab close. Not persisted. Default depth: 50 operations (configurable). |
| Clipboard contents | Application-wide | Standard OS clipboard. Not managed by K-PDF beyond copy/paste operations. |
| Search state (matches, current position) | Per-tab | Created on search activation. Cleared on search close. |
| In-memory document representation | Per-tab | PyMuPDF document object. Modified by annotations, form filling, page operations. Persisted only on explicit save. Released on tab close. |
| Password (for encrypted PDFs) | Temporary | Held only during decryption call. Cleared immediately after. Never persisted. |

### 5.3 Persistence Boundary

The boundary between "stored permanently" and "stored in session" is clear:

- **Permanently stored:** Only user preferences and recent files list. These are small (KB), low-sensitivity (no PII beyond file paths), and stored in the OS-standard config directory.
- **In session only:** Everything about the open documents — rendered pages, modification history, search state, document object. All released on tab close or application exit.
- **User-managed:** PDF files themselves. K-PDF reads and writes PDF files at user-specified paths. It does not move, copy, index, or manage PDF files. The file system is the user's responsibility.

---

## 6. Data Flow Diagram

```
[User] → Opens PDF → [File System] → Read bytes → [PyMuPDF] → Parse
                                                       ↓
                                                  [In-Memory Doc]
                                                       ↓
                                              [Render Pipeline]
                                                       ↓
                                              [Page Cache (RAM)]
                                                       ↓
                                              [Qt Viewport (UI)]
                                                       ↓
[User] ← Views rendered pages ← [Qt Widgets]

[User] → Annotates/Fills/Edits → [In-Memory Doc] → Modified state
                                                       ↓
[User] → Save command → [PyMuPDF Save] → [File System] → PDF on disk

[User Preferences] ↔ [OS Config Directory] (SQLite/JSON)
```

---

## 7. Data Sensitivity Summary

| Data Category | Classification | Protection Measures |
|---|---|---|
| PDF file contents | Confidential | No transmission. No caching outside user's explicit actions. No telemetry. No logging of content. |
| Form field inputs | Confidential (potential PII) | Same as above. Stored only in PDF on explicit save. |
| Annotation content | Confidential | Same as above. |
| PDF passwords | Critical | Never persisted. Never logged. Cleared from memory immediately after use. |
| User preferences | Internal | No PII except file paths in recent files list. Stored in OS config directory with OS-standard permissions. |
| Rendered pages | Ephemeral | In-memory only. Released on tab close. No disk caching. |

---

## 8. Validation Against FRD

| FRD Feature | Data Inputs Used | Data Outputs Produced | Covered? |
|---|---|---|---|
| F1: Open/Render | PDF file | Rendered pages | Yes |
| F2: Multi-tab | Per-tab state | Per-tab state | Yes |
| F3: Navigation | Document metadata (outline, page count) | Thumbnails, outline tree | Yes |
| F4: Search | Search query | Match list + highlights | Yes |
| F5: Zoom/Rotate | Zoom/rotation input | Re-rendered pages | Yes |
| F6: Text Markup | Text selection + markup type | Annotation in PDF | Yes |
| F7: Sticky Notes/Text Box | Placement + text content | Annotation in PDF | Yes |
| F8: AcroForm | Form field input | Form data in PDF | Yes |
| F9: Page Management | Page operation commands | Modified page structure | Yes |
| F10: Merge | Multiple PDF files | New merged PDF | Yes |
| F11: Dark Mode | Mode toggle | Preference persisted | Yes |
| F12: Annotation Panel | Annotation metadata | Panel display | Yes |

**All features have data flows fully specified.**

---

## 9. Inputs Implied by Features but Not Listed in Intake

| Implied Input | Feature | Assessment |
|---|---|---|
| Search query text | F4 | Covered above (Section 2.7). Not listed in Intake Section 5.1 because it's transient UI input, not persisted data. Acceptable. |
| Keyboard shortcuts | All | Not a data input — it's a UI interaction mechanism. No gap. |
| Drag-and-drop file path | F1, F9, F10 | Covered by PDF file input. The OS provides the file path. No additional data contract needed. |
| Annotation author name | F6, F7 | Stored in preferences. Listed in Intake Section 5.4. Covered. |

**No missing inputs identified.**

---

## 10. Review Checklist

- [x] Every input has validation rules and sensitivity classification
- [x] Every transformation is a discrete, documented operation
- [x] Every output has format and latency expectations
- [x] No third-party dependencies (offline constraint verified)
- [x] PII-adjacent fields identified (form inputs, passwords, file paths)
- [x] Persistence boundary clearly defined
- [x] Password handling explicitly secured (never stored, cleared from memory)
- [x] Data flow covers all 12 MVP features
