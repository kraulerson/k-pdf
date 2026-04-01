# K-PDF — Product Manifesto

## Version 1.0 — Phase 0, Step 0.4

**Source:** FRD v1.0, User Journey Map v1.0, Data Contract v1.0, Project Intake v1.1
**Generated:** 2026-04-01
**Status:** Approved — Open Questions resolved 2026-04-01

---

## 1. Product Intent

K-PDF is a free, offline, cross-platform desktop PDF reader and editor that handles the 80% use case: open, read, navigate, annotate, fill forms, and manage pages — without subscriptions, accounts, cloud dependencies, or telemetry. It targets a single power user (the Orchestrator) as the initial user, with potential public release after personal validation. The application must function with the network adapter disabled, must never rely on color alone to convey meaning (the Orchestrator is colorblind), and must ship as a single self-contained executable per platform (Windows, macOS, Linux) via Nuitka AOT compilation.

---

## 2. MVP Cutline — Hard Line

**Only these features ship in the first release. Everything else goes to the Post-MVP Backlog. Architecture that contradicts this Manifesto is rejected. Features not in this Cutline are not built in Phase 2.**

### 2.1 MVP Features (Must-Have)

| # | Feature | Summary | FRD Reference |
|---|---|---|---|
| 1 | Open and Render PDF | Open via File > Open, drag-and-drop, CLI arg, OS file association. Validate, parse, render. Lazy rendering for performance. | FRD §2 F1 |
| 2 | Multi-Tab Document Support | Multiple documents in tabs. Independent per-tab state. Unsaved-changes guard on close. | FRD §2 F2 |
| 3 | Page Navigation | Thumbnail sidebar, outline/bookmark tree, keyboard navigation, Go-to-page dialog. | FRD §2 F3 |
| 4 | Text Search | Ctrl+F search with match highlighting, match counter, Next/Previous navigation. Case sensitivity and whole-word toggles. | FRD §2 F4 |
| 5 | Zoom, Rotate, Page Fit | Slider, numeric input, presets, keyboard shortcuts, scroll-wheel zoom. View rotation (non-destructive). | FRD §2 F5 |
| 6 | Text Markup Annotations | Highlight, underline, strikethrough on selected text. Color selection. Annotation panel integration. | FRD §2 F6 |
| 7 | Sticky Notes & Text Boxes | Place sticky notes and text boxes on pages. Edit content. | FRD §2 F7 |
| 8 | AcroForm Filling & Save | Detect and activate AcroForm fields. Fill text, checkbox, dropdown, radio. Save with embedded form data. | FRD §2 F8 |
| 9 | Page Management | Add, delete, reorder, rotate pages. Permanent rotation (modifies PDF). | FRD §2 F9 |
| 10 | Merge PDFs | Select multiple PDFs, set merge order, output merged file. | FRD §2 F10 |
| 11 | Dark / Night Mode | Dark UI theme. Two sub-modes: Original PDF, Inverted PDF. Labeled controls, not icon-only. | FRD §2 F11 |
| 12 | Annotation Summary Panel | List all annotations with page, type (text + icon), author, timestamp. Click-to-navigate. Filter and sort. | FRD §2 F12 |

### 2.2 Implicit MVP Requirements (Not Separate Features)

These are capabilities required by the MVP features above. They are NOT separate features — they are implementation requirements.

| Capability | Required By | Specification |
|---|---|---|
| Undo/Redo | F6, F7, F8, F9 | Per-tab, in-session only. Default depth: 50 operations. Ctrl+Z / Cmd+Z (undo), Ctrl+Shift+Z / Cmd+Shift+Z (redo). |
| Keyboard Shortcut System | All features | Unified, non-conflicting shortcut map. Documented in Help menu. Not customizable in MVP. |
| Preferences/Settings Dialog | F5, F11, general UX | Access via Edit > Preferences (Windows/Linux) or K-PDF > Settings (macOS). Settings: default zoom, dark mode, annotation author name, recent files count. |
| Text Copy to Clipboard | F6 (text selection) | Ctrl+C / Cmd+C copies selected text. Standard OS clipboard. |
| File > Save As | F6, F7, F8, F9 | Save to a new path. Standard OS save dialog. |
| Recent Files List | F1 (file open) | Most recent 20 files. Displayed on welcome screen and in File menu. Stale paths shown grayed with "File not found." |
| Basic Printing | All features (expected capability) | File > Print opens OS native print dialog (QPrintDialog). Not a virtual printer driver — sends to system printer only. |

### 2.3 Post-MVP Backlog (v1.1+)

From Intake Section 4.2. **Not in Phase 2. Not in this release. Prioritized by user feedback after MVP validation.**

1. Find-and-replace text in PDF content (fully embedded fonts only)
2. Freehand drawing / ink annotations
3. Shape annotations (rectangle, ellipse, arrow, line)
4. Split PDF / extract page ranges
5. Insert images into PDF pages
6. Export PDF pages as images (JPG/PNG)
7. Export PDF to plain text

### 2.4 Will-Not-Have (Explicit Exclusions)

From Intake Section 4.3. **These are never built. Period.**

1. Virtual printer driver / system-level print-to-PDF
2. XFA dynamic form creation or filling
3. OCR / text layer generation for scanned documents
4. Cloud sync, accounts, telemetry, or any network connectivity
5. Basic form field creation (authoring new AcroForm fields)
6. Real-time multi-user collaborative editing
7. Word-processor-style in-place text editing with reflow

---

## 3. Manifesto Rules

1. **Architecture that contradicts this Manifesto is rejected.** If a proposed architecture requires network access, accounts, or a backend — it is rejected.
2. **Features not in the MVP Cutline (Section 2.1) are not built in Phase 2.** If the AI suggests a feature not on this list, the response is: "Not in the Manifesto. Not in Phase 2. Post-MVP Backlog."
3. **Post-MVP features are prioritized by user feedback, not this document.** The ordering in Section 2.3 is advisory only.
4. **Implicit requirements (Section 2.2) are implementation concerns, not feature scope expansions.** They do not add features — they ensure the listed features work correctly.
5. **Accessibility is a hard constraint, not a nice-to-have.** Every UI element, state indicator, annotation type, error/warning, mode toggle, and status must use shape, position, text labels, patterns, or icons in addition to or instead of color. No exceptions. Verified in Phase 3.
6. **Offline operation is absolute.** The application must function with the network adapter disabled. No fallback to online. No "enhanced experience with internet." Zero network calls.

---

## 4. Success Criteria (from Intake Section 2.3)

| Metric | Target | Measurement |
|---|---|---|
| Daily PDF workflow coverage | All routine tasks handled without opening another tool | Orchestrator self-assessment at 90 days post-MVP |
| Zero fallback incidents | No task requires Adobe, browser tools, or paid alternatives | Orchestrator self-tracking |
| Stability on real-world files | Handles the Orchestrator's actual PDF corpus without crashes or data loss | Orchestrator self-assessment at 90 days post-MVP |

---

## 5. Resolved Design Decisions

*Identified during Steps 0.1–0.3. Resolved by Orchestrator on 2026-04-01.*

| # | Decision | Resolution | Impact |
|---|---|---|---|
| OQ-1 | Basic printing in MVP? | **Yes.** Added as implicit requirement (Section 2.2). File > Print opens OS native print dialog. | Added to implicit requirements table. |
| OQ-2 | Auto-save / crash recovery? | **No.** Explicit-save-only for MVP. Auto-save deferred to Post-MVP Backlog. | No architectural impact. |
| OQ-3 | Large file strategy? | **Full memory load** with progress indicator. No streaming in MVP. Warning dialog if file exceeds available memory heuristic. | Simplifies implementation. Streaming deferred to post-MVP if needed. |
| OQ-4 | Undo/Redo depth? | **50 operations per tab.** | Confirmed as default. Configurable in post-MVP if needed. |

---

## 6. Revenue Model & Unit Economics

*From Intake Section 7. Reviewed for consistency with expanded feature set.*

| Field | Value |
|---|---|
| **Pricing model** | Freemium — free and open source (MVP). Future paid Pro tier. |
| **License** | MIT — permissive. Supports closed-source Pro tier without dual-licensing. |
| **Per-user cost** | $0 — fully offline. No hosting costs. |
| **Distribution** | GitHub Releases. No package managers in MVP. |
| **Pro tier candidates** | Signed/notarized builds. File format conversion (DOCX/XLSX/PPTX → PDF). TBD. |

**Feature Gate Requirement:** The architecture must include a build-time feature gate mechanism from Phase 1. A build-time flag or local license file is sufficient. The code structure must support adding Pro features without refactoring the free tier codebase.

**Consistency check:** The expanded feature set (12 MVP features + implicit requirements) does not affect the revenue model. All MVP features are free tier. Pro tier candidates remain separate from MVP scope.

---

## 7. Orchestrator Competency Matrix

*From Intake Section 6.2. Reviewed in context of the expanded FRD and Data Contract.*

| Domain | Self-Assessment | Automated Tooling Required | Notes from FRD/Data Contract |
|---|---|---|---|
| Product/UX Logic | Yes | No | Orchestrator validates feature behavior directly. |
| Desktop UI (PySide6/Qt6) | No | Yes — UI tests, widget behavior validation | Every feature involves Qt widgets. All UI must be tested. |
| Application Logic | No | Yes — type checking (mypy), linting (ruff), unit tests (pytest) | Core logic: PDF parse, annotation create, form fill, page management, merge. |
| Data Storage (SQLite preferences) | Partially | Yes — schema validation, migration tests | Simple schema. Migration path must be tested. |
| Security (file handling, encryption, passwords) | Partially | Yes — pip-audit, no-credential-storage audit | Password handling is the critical path. File system access must be validated. |
| DevOps / Infrastructure | Yes | No | CI/CD, GitHub Actions, Nuitka builds. |
| Accessibility (colorblind-safe UI, keyboard nav) | Partially | Yes — automated accessibility audit in Phase 3 | Hard constraint. Every UI element must pass. |
| Performance (large file rendering, page operations) | Partially | Yes — benchmarking suite | 500-page document performance targets in Data Contract. |
| Desktop Packaging (Nuitka) | No | Yes — build validation on all platforms in CI/CD | Nuitka + PyMuPDF (C extension) + PySide6 = complex build. |

**Additional domain identified from FRD:**
| PDF specification compliance | Partially | Yes — diverse real-world PDF test corpus | Real-world PDFs deviate from spec. Edge case coverage is critical. |

---

## 8. Deferred Risks

### 8.1 License Compliance (AGPL/LGPL)

**Status:** Deferred. Not blocking Phase 0 or Phase 1.

**Summary:** PyMuPDF is AGPL v3. PySide6 is LGPL v3. Both licenses' obligations are triggered by *distribution*, not personal use. K-PDF is personal use only with no current distribution intent. Before any public distribution, binary sharing, or open-source release, a full license compliance review is required.

**Action:** Flag in Phase 1. Review before Phase 4 if distribution is planned.

### 8.2 Code Signing

**Status:** Accepted degradation. Not blocking any phase.

**Summary:** Unsigned executables trigger OS security warnings (macOS Gatekeeper, Windows SmartScreen). Accepted for personal use. Distribution documentation must include bypass instructions. Signed builds are a prerequisite for public distribution.

---

## Confirmation

**I will use this Manifesto as my primary constraint for all subsequent phases.**

- Architecture that contradicts the Manifesto is rejected.
- Features not in the MVP Cutline are not built in Phase 2.
- Post-MVP priorities are determined by user feedback, not this document.

---

## 9. Trademark & Legal Pre-Check (Step 0.7)

### 9.1 Trademark Search

| Search Target | Result | Risk |
|---|---|---|
| **KPDF (KDE)** | Discontinued KDE 3 PDF viewer (kpdf.kde.org). Evolved into Okular. Open source (GPL). No commercial presence. Name is "KPDF" (no hyphen). | **Low.** Discontinued, different naming, no trademark registration found. |
| **KDAN PDF** | Active commercial product by KDAN Mobile Software Ltd. PDF editor for iOS, Mac, Android, Windows. Brand is "KDAN PDF" not "K-PDF". | **Low-Medium.** Different brand name ("KDAN" vs "K"), different market positioning (mobile-first vs desktop-offline), but phonetic similarity exists. Monitor if K-PDF goes to public distribution. |
| **K:PDF Viewer** | Shopify app for embedding PDFs in e-commerce stores. Uses "K:PDF" with colon. Niche product. | **Low.** Different product category, different naming. |
| **USPTO direct search** | Not completed from this environment. | **Action required:** Manual search at [tmsearch.uspto.gov](https://tmsearch.uspto.gov/) before any public release. Not blocking for personal use. |

**Assessment:** The name "K-PDF" (with hyphen) does not appear to be registered or in active commercial use. The closest match is KDAN PDF, which is a different brand. For personal use, the name is safe. **Before public distribution, complete a formal USPTO search.**

### 9.2 License Compliance

| Dependency | License | Obligation Trigger | Status |
|---|---|---|---|
| **PyMuPDF** | AGPL v3 | Distribution of the application | **Deferred.** Personal use only — no current distribution. AGPL requires source disclosure on distribution. Must resolve before public release. Options: (a) open-source K-PDF under AGPL-compatible license, (b) purchase a commercial PyMuPDF license from Artifex, (c) replace PyMuPDF. |
| **PySide6** | LGPL v3 | Distribution of the application | **Deferred.** Personal use only. LGPL allows proprietary use if PySide6 is dynamically linked (standard for Python imports). Must verify Nuitka's linking behavior before distribution. |
| **Qt6** (bundled via PySide6) | LGPL v3 | Same as PySide6 | Same as PySide6. |
| **Python stdlib** | PSF License | No obligation | **Clear.** Permissive license. |
| **Nuitka** | Apache 2.0 | Distribution | **Clear.** Permissive license. |

**Assessment:** No license blockers for personal use. The AGPL (PyMuPDF) issue is the most significant — it requires full source disclosure on distribution. This must be resolved before any public release but does not block development.

### 9.3 Data Privacy

No PII is collected, transmitted, or stored by the application (beyond user-controlled content in PDFs and file paths in the recent files list). No privacy policy required for personal use. A privacy policy will be needed before public distribution to document the zero-data-collection posture.

### 9.4 Distribution Channel Requirements

GitHub Releases only. No app store submission requirements. No package manager listing requirements. Code signing deferred (accepted degradation for personal use — see Intake Section 11, Risk 1).

---

## Document History

| Version | Date | Changes |
|---|---|---|
| 1.0 | 2026-04-01 | Initial synthesis from FRD v1.0, User Journey Map v1.0, Data Contract v1.0. Includes Steps 0.5 (Revenue Model), 0.6 (Competency Matrix), and 0.7 (Trademark & Legal Pre-Check). |
