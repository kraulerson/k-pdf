# Solo Orchestrator — Project Intake Template

## Version 1.1

---

## Document Control

| Field | Value |
|---|---|
| **Document ID** | SOI-004-INTAKE |
| **Version** | 1.1 |
| **Classification** | Project Initialization |
| **Date** | 2026-04-01 |
| **Companion Documents** | SOI-002-BUILD v4.0 (Builder's Guide), SOI-003-GOV v1.2 (Enterprise Governance Framework) |

---

## 1. Project Identity

| Field | Value |
|---|---|
| **Project name** | K-PDF |
| **Project codename** | N/A |
| **One-sentence description** | A free, offline, cross-platform desktop PDF reader and editor covering the 80% use case — read, annotate, fill forms, and manage pages — without subscriptions, accounts, or cloud dependencies. |
| **Project track** | Standard |
| **Platform type** | Desktop |
| **Platform Module** | SOI-PM-DESKTOP |
| **Target platforms** | Windows 10+, macOS 12+, Ubuntu 22.04+ / major Linux distributions |
| **Is this a personal project or organizational deployment?** | Personal |
| **Repository URL** | TBD — create before Phase 0 begins |

---

## 2. Business Context

### 2.1 The Problem

```
Existing PDF tools that cover reading, annotation, editing, and form filling
either require paid subscriptions (Adobe Acrobat ~$20–25/month), are
feature-limited freeware, or lack reliable cross-platform support as
standalone executables. The Orchestrator needs a single offline desktop
application that handles all routine PDF work — open, read, annotate, fill
forms, merge, and do basic page manipulation — without cost, cloud
dependency, account requirements, or telemetry.
```

### 2.2 Who Has This Problem

| Field | Value |
|---|---|
| **Primary user persona** | The Orchestrator — IT professional, high technical literacy, daily PDF interaction involving documents of varying complexity, needs full offline capability, zero telemetry, zero accounts |
| **Secondary personas** | N/A — personal use only at launch |
| **How do they solve this problem today?** | Mix of Adobe Acrobat Reader (limited free tier), browser-based tools (Smallpdf, IlovePDF), paid tools as needed — multiple tools required for different tasks |
| **What's wrong with the current solution?** | Cost, subscription lock-in, account requirements, telemetry, cloud-only for key features, no single tool covers the full use case |

### 2.3 Success Criteria

| Metric | Target | How Measured |
|---|---|---|
| Daily PDF workflow coverage | All routine PDF tasks (open, read, annotate, fill forms, merge, page manipulation) handled without opening another tool | Orchestrator self-assessment at 90 days post-MVP |
| Zero fallback incidents | No task requires falling back to Adobe, browser tools, or any paid PDF tool | Orchestrator self-tracking |
| Stability on real-world files | Application handles the Orchestrator's actual PDF corpus (mixed sources, sizes, types) without crashes or data loss | Orchestrator self-assessment at 90 days post-MVP |

### 2.4 What This Is NOT

1. Not a cloud-based document collaboration platform — no sharing, real-time multi-user editing, sync, or accounts of any kind
2. Not an Adobe Acrobat clone — no page layout tools, preflight, print production workflows, or XFA dynamic forms
3. Not a document management system or file organizer
4. Not an OCR engine — scanned document text recognition is explicitly out of scope
5. Not a mobile application — desktop only (Windows, macOS, Linux)
6. Not a virtual printer driver — no OS-level print-to-PDF integration; export-as-PDF is a save operation, not a print driver

---

## 3. Constraints

### 3.1 Timeline

| Field | Value |
|---|---|
| **Target MVP date** | No fixed date — quality and completeness over schedule |
| **Hard deadline?** | No |
| **Orchestrator availability** | Variable — AI-directed development via Claude Code CLI; sessions as time allows |
| **Blocked time or interleaved?** | Interleaved with other work and projects |

### 3.2 Budget

| Field | Value |
|---|---|
| **Monthly infrastructure ceiling** | $0 — fully offline desktop application, no hosted backend |
| **One-time budget** | $0 — code signing deferred (see Section 10 and Known Risks) |
| **AI subscription** | Claude Max — already provisioned |
| **Who approves spending?** | Self |

### 3.3 Users

| Field | Value |
|---|---|
| **Users at launch** | 1 — Orchestrator only |
| **Users at 6 months** | 1 — personal use validation |
| **Users at 12 months** | TBD — public release decision at Orchestrator's discretion after personal validation |
| **Internal only or external?** | Internal (personal) only at launch |
| **Geographic distribution** | Single user, US |

---

## 4. Features & Requirements

### 4.1 Must-Have Features (MVP)

| # | Feature | Business Logic Trigger | Failure State |
|---|---|---|---|
| 1 | **Open and render PDF** | User opens a PDF via File > Open, drag-and-drop, or CLI argument → system parses the file, validates the PDF header (`%PDF-`), and renders all pages at the current zoom level; text, images, and vector graphics are displayed faithfully | File not found → error dialog with filename; corrupt or invalid file → error dialog with filename and reason, no crash; file is password-protected → password prompt before rendering; file too large to buffer entirely → stream render with progress indicator; any render failure on a single page → display placeholder with page number and "Render error" label, continue rendering other pages |
| 2 | **Multi-tab document support** | User opens a second PDF while one is already open → new tab is created in the same window; each tab maintains independent scroll position, zoom level, rotation state, annotation state, and unsaved-change marker | Closing a tab with unsaved changes → modal dialog: "Unsaved changes in [filename]. Save before closing?" with Save / Discard / Cancel; system memory pressure warning → alert user before allowing additional tabs to open; no artificial tab count limit, but performance degradation at >20 tabs is expected and documented |
| 3 | **Page navigation — thumbnails, bookmarks, outline** | User opens the navigation panel → page thumbnails render in a scrollable sidebar; document outline/bookmarks embedded in the file displayed as a collapsible tree in a separate panel tab; clicking any thumbnail or outline entry jumps the main view to that page | Document has no embedded outline → thumbnail panel shown, outline panel tab hidden or shows "No bookmarks in this document"; thumbnail render fails for a specific page → placeholder with page number shown, no crash; outline entries pointing to invalid page numbers → entry shown with warning icon and text label "Invalid target", clicking performs no navigation |
| 4 | **Text search within document** | User activates search (Ctrl+F / Cmd+F) and enters a query of 1+ characters → all matching text on all pages highlighted; match count and current position shown as text (e.g., "3 of 14 matches"); user navigates between hits with Next / Previous or Enter / Shift+Enter | No results → "No matches found" displayed as text; document has no text layer → "This document has no searchable text" notification; search cancelled → all highlights removed, view returns to pre-search scroll position |
| 5 | **Zoom, rotate, and page fit modes** | User adjusts zoom via slider, numeric input, keyboard shortcut, or preset (Fit Page, Fit Width, Actual Size, 50%, 75%, 100%, 150%, 200%) → rendering updates immediately; user rotates current page view via View menu or keyboard shortcut in 90° increments | Zoom below 10% → clamped to 10%, no error; zoom above 3200% → clamped to 3200%, no error; view rotation does NOT modify the file — only page management rotation (Feature 9) writes rotation to the PDF; preset labels are text, never icon-only |
| 6 | **Text markup annotations — highlight, underline, strikethrough** | User selects text on a rendered page using click-drag → annotation toolbar appears with markup options labeled with both icon and text; user selects a markup type → annotation rendered on the page and added to the annotation summary panel; document marked modified | Markup attempted on a page with no text layer → "Text markup requires selectable text. This page does not have a text layer."; file is read-only by the OS → "This file is read-only. Use File > Save As to save a copy with annotations."; annotation cannot be embedded in a locked PDF → same Save As notification; annotation type never conveyed by color alone — each type uses a distinct icon plus text label in the annotation list |
| 7 | **Sticky notes and text box annotations** | User selects the sticky note or text box tool and clicks a location on the page → annotation created at that position; sticky notes display as an icon with a text label on the page; text boxes display their content inline; both appear in the annotation summary panel with page number, type (text label + icon), author, and timestamp | Empty text box on save → "This annotation is empty. Save anyway?" with Save / Delete options; annotation panel shows type as text label + icon, never icon alone; annotations created by external tools → displayed with author name and "External" label in type column |
| 8 | **AcroForm filling and save** | User opens a PDF containing interactive AcroForm fields → fields automatically detected and activated; clicking a field opens it for input appropriate to field type (text, checkbox, dropdown, radio); File > Save embeds all form data into the output PDF | PDF contains XFA dynamic forms → notify: "This document uses XFA dynamic forms, which are not supported. Only AcroForms are supported."; partially filled form → allowed to save without warning; form save fails due to permissions → notify with Save As alternative; field validation rules embedded in the PDF → enforce on submit, display field-level error as text label adjacent to the field |
| 9 | **Page management — add, delete, reorder, rotate pages** | User accesses the page management panel → all pages shown as thumbnails in a scrollable grid; pages can be dragged to reorder; individual pages can be selected and deleted or rotated in 90° increments; changes previewed in real-time; document marked modified | Attempt to delete all pages → blocked: "A PDF must contain at least one page."; operations on 100+ page documents → progress indicator shown for operations taking more than 1 second; rotation in page management writes to the file (unlike view rotation in Feature 5, which is view-only) |
| 10 | **Merge multiple PDFs** | User selects File > Merge Documents → file picker opens for multiple PDF selection; user sets merge order via drag-and-drop list; merged output saved as a new file at a user-specified path | Any source file is corrupt or unreadable → skip that file, notify user with filename and reason, offer to proceed with remaining files; source file is password-protected → prompt for password; if declined, skip and notify; output path is read-only → prompt for alternate location; merge of 0 or 1 files → blocked with notification |
| 11 | **Dark / night reading mode** | User activates dark mode via View menu or keyboard shortcut → app UI switches to dark theme; mode toggle is a labeled control with both icon and text (never icon-only); two labeled sub-modes available: "Dark UI / Original PDF" and "Dark UI / Inverted PDF" | Mode state persists across sessions via user preferences; mode indicator uses text label, never color alone; inverted rendering is applied to the rendering layer only — it does NOT modify the PDF file |
| 12 | **Annotation summary panel** | The annotation panel lists all annotations in the currently active document; each entry shows: page number (numeric), annotation type (text label + icon), author, and timestamp; clicking an entry navigates to that annotation's page | No annotations → empty state with text: "No annotations in this document."; documents with 500+ annotations → panel must remain responsive (virtual scrolling if necessary); annotations missing metadata fields → display available fields only, no crash; panel updates immediately when annotations are added or deleted |

### 4.2 Should-Have Features (Post-MVP v1.1)

1. **Find-and-replace text in PDF content** — Locate specific text strings within a page's content stream and replace them where the original font is fully embedded and the replacement fits the available space. Behavior on unsupported files: clear error ("Text editing requires fully embedded fonts. This document's fonts are subset-embedded and cannot be edited."), never silent corruption. This is explicitly NOT word-processor-style editing — no reflow, no font substitution, no paragraph restructuring.
2. **Freehand drawing / ink annotations** — Path-based annotation tool for freehand markup; stored as standard PDF ink annotations
3. **Shape annotations** — Rectangle, ellipse, arrow, and line annotation tools; extension of the annotation system
4. **Split PDF / extract page ranges** — User specifies a page range or individual pages and exports them as a new PDF
5. **Insert images into PDF pages** — User places a raster image (JPG, PNG) onto a page at a specified position and size
6. **Export PDF pages as images** — Export individual pages or page ranges as JPG or PNG at a specified resolution
7. **Export PDF to plain text** — Extract the text layer of a PDF to a .txt file

### 4.3 Will-Not-Have Features (Explicit Exclusions)

1. **Virtual printer driver / system-level print-to-PDF** — Requires an OS kernel-mode driver. "Export as PDF" (a save operation) is the supported equivalent.
2. **XFA dynamic form creation or filling** — Deprecated Adobe proprietary format. Only AcroForms are supported.
3. **OCR / text layer generation for scanned documents** — Separate specialized problem. Permanently out of scope unless scoped as a separate module.
4. **Cloud sync, accounts, telemetry, or any network connectivity** — Hard constraint. Application must function with the network adapter disabled.
5. **Basic form field creation (authoring new AcroForm fields from scratch)** — Pro tier / post-v1.1 candidate at the earliest.
6. **Real-time multi-user collaborative editing** — Architecturally incompatible with offline-only, no-accounts constraint. Future separate product, not a feature within K-PDF.
7. **Word-processor-style in-place text editing with reflow** — Explicitly excluded. Replaced by scoped find-and-replace (Post-MVP v1.1) with documented limitations.

---

## 5. Data & Integrations

### 5.1 Data Inputs

| Input | Data Type | Validation Rules | Sensitivity | Required? |
|---|---|---|---|---|
| PDF file | Binary | Valid PDF header (`%PDF-`); file extension `.pdf`; no maximum file size enforced, but 500-page documents must perform within spec | Confidential (user-controlled; may contain anything) | Yes |
| Annotation content | Text | Max 10,000 characters per annotation; stored in PDF metadata fields; no external storage | Confidential (user-controlled) | No |
| Form field input | Text / Boolean / Selection | Per-field type validation per AcroForm field dictionary; max length per PDF spec | Confidential (user-controlled) | No |
| User preferences / settings | Structured (JSON or SQLite) | Schema-validated on read; version migration on schema mismatch; stored in OS-standard config directory | Internal | No |
| Password for encrypted PDFs | Text | Passed directly to PyMuPDF for decryption; never stored to disk, never logged, cleared from memory after use | Confidential | No |

### 5.2 Data Outputs

| Output | Format | Latency Expectation |
|---|---|---|
| Modified PDF (annotations, form data, page edits, merge) | PDF binary | < 5 seconds for 500-page document save on development hardware |
| Merged PDF | PDF binary | < 10 seconds for 5 source documents; < 30 seconds for 20 source documents |
| Exported page images (Post-MVP) | JPG / PNG | < 2 seconds per page |
| Exported plain text (Post-MVP) | UTF-8 TXT | < 5 seconds for 500-page document |

### 5.3 Third-Party Integrations

None. K-PDF is fully offline. No external APIs, no network calls, no telemetry endpoints. The application must function with the host machine's network adapter disabled.

### 5.4 Data Persistence

| Question | Answer |
|---|---|
| **What data must persist across sessions?** | User preferences (zoom default, dark mode state, UI panel layout, recent files list, annotation author name); stored in OS-standard config directory (`%APPDATA%\K-PDF` on Windows, `~/.config/k-pdf` on Linux, `~/Library/Application Support/K-PDF` on macOS) |
| **What data can be ephemeral (browser/device only)?** | Rendering cache, undo/redo history stack (in-session only), clipboard contents |
| **Expected data volume at 12 months** | Negligible — settings file ~KB; application manages no user data beyond preferences |
| **Data retention requirements** | N/A — application stores no user data; PDF files are user-managed |
| **Backup requirements** | N/A — no application-managed data to back up |

---

## 6. Technical Preferences

### 6.1 Orchestrator Technical Profile

| Field | Value |
|---|---|
| **Languages you know well** | None — AI-directed development |
| **Frameworks you've used** | Next.js / React / Supabase (web apps); React Native / Expo (Tender Reminders mobile app) |
| **Languages/frameworks you're willing to learn** | Whatever the architecture requires; infrastructure and tooling concepts are familiar |
| **Languages/frameworks you refuse to use** | None specified |
| **Database experience** | SQLite (via Supabase patterns); basic schema design |
| **DevOps experience level** | Advanced — CI/CD, GitHub Actions, build pipelines, cross-compilation, release automation |
| **Mobile development experience** | Some — React Native / Expo cross-platform (Tender Reminders) |

### 6.2 Competency Matrix

_Domains are interpreted for a desktop application context. "Frontend Code" = desktop UI framework (PySide6/Qt6). "Backend / API Design" = application logic and service layer. "Mobile" = N/A for this project._

| Domain | Self-Assessment | Automated Tooling Required? |
|---|---|---|
| Product/UX Logic | Yes | No |
| Frontend Code (desktop UI — PySide6/Qt6) | No | Yes — UI tests, widget behavior validation |
| Backend / API Design (application logic layer) | No | Yes — type checking (mypy), linting (ruff), unit tests (pytest) |
| Database Design & Queries | Partially | Yes — schema validation, migration tests |
| Security (file handling, encryption, password handling) | Partially | Yes — dependency audit (pip-audit), no-credential-storage audit |
| DevOps / Infrastructure | Yes | No |
| Accessibility (WCAG / colorblind-safe UI, keyboard navigation) | Partially | Yes — automated accessibility audit in Phase 3 |
| Performance Optimization | Partially | Yes — benchmarking suite for large-file rendering and page operations |
| Desktop Packaging (Nuitka, cross-platform builds) | No | Yes — build validation on all three target platforms in CI/CD |

_Every "No" or "Partially" domain requires mandatory automated tooling coverage in Phase 3._

### 6.3 Development Environment

| Field | Value |
|---|---|
| **Primary development machine** | Corsair workstation — AMD Ryzen AI Max+ 395, 96GB RAM, Windows 11 |
| **Secondary machines** | Lenovo P15V Gen 3 (Ubuntu 22.04); Mac mini (macOS — macOS platform builds and testing) |
| **IDE/Editor** | Claude Code CLI — primary and exclusive development tool |
| **Docker available?** | Yes |
| **Node.js version** | N/A — Python project |
| **Python version** | TBD — agent must specify minimum version compatible with PySide6 6.x and PyMuPDF current stable; recommend Python 3.11+ |
| **Claude Code installed?** | Yes |
| **AI subscription tier** | Claude Max |

### 6.4 Architecture Preferences & Constraints

**All Platforms:**

| Field | Value | Hard Constraint or Preference? |
|---|---|---|
| **Primary language** | Python | Hard Constraint |
| **Data storage** | SQLite via Python stdlib `sqlite3` for preferences; PDF files are user-managed (file system only) | Preference |
| **Authentication** | None — local application, no accounts | Hard Constraint |

**Web Applications:**

| Field | Value | Hard Constraint or Preference? |
|---|---|---|
| **Frontend framework** | N/A | N/A |
| **Backend framework** | N/A | N/A |
| **Hosting** | N/A | N/A |

**Desktop Applications:**

| Field | Value | Hard Constraint or Preference? |
|---|---|---|
| **UI framework** | PySide6 (Qt6) | Hard Constraint |
| **Packaging format** | Nuitka AOT compilation — single self-contained executable per platform; no runtime dependencies for the end user | Hard Constraint |
| **Auto-update strategy** | Manual download from GitHub Releases — no in-app auto-update in MVP | Preference |
| **Offline requirement** | Fully offline — must function with network adapter disabled | Hard Constraint |

**Mobile Applications:**

| Field | Value | Hard Constraint or Preference? |
|---|---|---|
| **Framework** | N/A | N/A |
| **Minimum OS version** | N/A | N/A |
| **App store distribution** | N/A | N/A |

**Cross-Cutting:**

| Field | Value | Hard Constraint or Preference? |
|---|---|---|
| **Monorepo or separate repos?** | Single repository | Preference |
| **Web + Desktop, Web + Mobile, or single platform?** | Single platform — Desktop only | Hard Constraint |

**Architecture Rationale (for agent reference):**
PyMuPDF wraps the MuPDF C library — the same engine licensed by Foxit and others — and is the gold standard for open-source PDF rendering, annotation, AcroForm handling, page manipulation, password handling, and content stream access. PySide6 (Qt6) is the official Python binding for Qt6: mature, well-documented, cross-platform native UI framework. Nuitka compiles Python to C and links it into a self-contained executable, eliminating user-facing Python runtime dependency. Target executable size: ≤150MB (target), ≤200MB (hard ceiling).

### 6.5 Existing Infrastructure to Integrate With

| System | Details | Integration Required? |
|---|---|---|
| **SSO / Identity Provider** | N/A | N/A |
| **Logging / SIEM** | N/A | N/A |
| **Monitoring** | N/A | N/A |
| **Data Warehouse** | N/A | N/A |
| **Backup Infrastructure** | N/A | N/A |
| **CI/CD Platform** | GitHub Actions — automated builds for Windows, macOS, Linux; test suite execution; release artifact packaging | Yes |
| **Repository Platform** | GitHub | Yes |
| **Other** | N/A | N/A |

---

## 7. Revenue Model

| Field | Value |
|---|---|
| **Pricing model** | Freemium — free and open source initially; future paid Pro tier |
| **Open source license** | MIT — permissive; preserves the ability to offer a closed-source Pro tier without dual-licensing complexity |
| **Target price point** | TBD — not yet scoped |
| **Competitive price range** | Foxit PDF Editor ~$10/mo; PDF Expert (macOS) ~$80 one-time; PDF24 free |
| **Per-user cost estimate** | $0 — fully offline, no backend |
| **Break-even user count** | N/A for free tier; TBD for Pro tier |
| **Hosting cost ceiling at launch** | $0 — distribution via GitHub Releases |
| **Hosting cost ceiling at 1,000 users** | $0 |
| **Hosting cost ceiling at 10,000 users** | $0 |

**Pro Tier Feature Candidates (informs architecture feature gate placement):**
1. Signed and notarized builds — clean install experience with no OS security warnings
2. File format conversion to PDF — DOCX, XLSX, PPTX → PDF via bundled LibreOffice headless (~+200MB Pro executable)
3. TBD based on user feedback after personal validation

**Feature Gate Architecture Requirement:**
Even though Pro features are not being built now, the architecture must include a feature gate mechanism from Phase 1. A build-time flag or local license file is sufficient — but the code structure must support adding Pro features without refactoring the free tier codebase.

---

## 8. Governance Pre-Flight

**Personal project — section skipped (N/A).**

---

## 9. Accessibility & UX Constraints

| Field | Value |
|---|---|
| **Accessibility requirements** | WCAG 2.1 AA as baseline; all interactive elements must be keyboard navigable with visible focus indicators |
| **Color vision deficiency considerations** | **Yes — HARD CONSTRAINT enforced throughout.** The Orchestrator is colorblind. The application must NEVER rely on color alone to convey meaning. Every UI element, state indicator, annotation type, error/warning, mode toggle, and status must use shape, position, text labels, patterns, or icons IN ADDITION TO OR INSTEAD OF color. Specific applications: annotation types distinguished by icon + text label (never color alone); error and warning states use icon + text label; toolbar button states (active/inactive) use position or shape, not color shift alone; dark mode toggle is a labeled control, not a color indicator. This is a Day 1 architectural constraint enforced in Phase 1 and verified in Phase 3. |
| **Supported browsers** | N/A — desktop application |
| **Mobile responsive required?** | No — desktop only |
| **Supported devices** | Desktop only: Windows 10+, macOS 12+, Ubuntu 22.04+ / major Linux distributions |
| **Branding / style guide** | None — agent's discretion, with colorblind-safe UI as a hard constraint |
| **Dark mode required?** | Yes — required in MVP (Feature 11) |

---

## 10. Distribution & Operations Preferences

**All Platforms:**

| Field | Value |
|---|---|
| **Notification preferences for alerts** | N/A — no hosted infrastructure |
| **Uptime expectation** | N/A — desktop application |
| **Environment strategy** | Development (local), feature branches for in-progress work, tagged releases for versioned builds; no staging server |

**Web Applications:**

| Field | Value |
|---|---|
| **Domain name** | N/A |
| **SSL certificate** | N/A |
| **Maintenance window preferences** | N/A |

**Desktop Applications:**

| Field | Value |
|---|---|
| **Distribution channels** | GitHub Releases only — no package managers (winget, Homebrew, Flatpak, etc.) |
| **Code signing** | Deferred — personal use only at launch; revisit before any public distribution |
| **Code signing certificates** | None — deferred. Trade-off documented in Section 11. |
| **Auto-update mechanism** | Manual download from GitHub Releases — no in-app auto-update in MVP |
| **Minimum supported OS versions** | Windows 10+, macOS 12+, Ubuntu 22.04+ |
| **Installer format preferences** | Windows: portable executable (.exe, no installer — user runs directly); macOS: DMG; Linux: AppImage (single file, no installation required) |

**Mobile Applications:**

| Field | Value |
|---|---|
| **Distribution** | N/A |
| **Developer accounts** | N/A |
| **Beta testing** | N/A |

---

## 11. Known Risks & Concerns

```
1. CODE SIGNING — DOCUMENTED USER EXPERIENCE DEGRADATION (ACCEPTED)
   Unsigned executables are an accepted constraint (zero budget, personal use).
   On macOS, users must manually allow the app via System Settings > Privacy &
   Security > "Open Anyway." On Windows, SmartScreen displays an "unrecognized
   app" warning on every new install. Linux has no signing requirement.
   Distribution documentation must include step-by-step bypass instructions for
   all affected platforms. If K-PDF ever moves to public distribution, signed
   builds are a prerequisite, not optional.

2. DESKTOP DEVELOPMENT IS A NEW PARADIGM FOR THIS ORCHESTRATOR
   All prior Solo Orchestrator projects have been web applications. Desktop
   native development has a fundamentally different execution model: event
   loops, native file system access, window lifecycle management, OS-level
   clipboard and drag-and-drop, application packaging, and platform-specific
   behavior differences. Budget 20–30% more time than equivalent web projects.
   Automated tooling coverage for all "No" competency domains (Section 6.2)
   is mandatory.

3. PDF SPEC COMPLEXITY AND REAL-WORLD FILE VARIANCE
   The PDF specification is 1,000+ pages. Real-world PDFs from diverse sources
   (Word exports, scanned files, legacy tools, web-generated PDFs, government
   forms) contain edge cases that deviate from spec. A QA corpus of diverse
   real-world PDFs is required — test against actual files the Orchestrator
   uses, not synthetic test PDFs. Every feature touching PDF content streams
   (annotations, form filling, find-and-replace) needs edge case coverage.

4. FIND-AND-REPLACE TEXT LIMITATIONS ARE A USER-FACING CONSTRAINT, NOT A BUG
   Post-MVP text find-and-replace (v1.1) works only on PDFs with fully embedded
   fonts where the replacement fits the available space. The majority of
   real-world PDFs have subset-embedded fonts. This must be communicated clearly
   at the point of failure — never silently produce corrupt output. Treat as a
   documented limitation, not a defect queue.

5. NUITKA COMPILATION COMPLEXITY
   Nuitka is the right packaging tool but has build configuration complexity
   for applications with C extensions (PyMuPDF) and large UI frameworks
   (PySide6). The build pipeline must be validated on all three target platforms
   in CI/CD from Phase 2 onward — not deferred to Phase 4.

6. FEATURE GATE ARCHITECTURE MUST BE IN FROM PHASE 1
   The freemium Pro tier requires a feature gate in the codebase. Failing to
   design the gate in Phase 1 means refactoring later. The agent must include
   a lightweight feature gate system in the architecture proposal.

7. LICENSE REVIEW GATE — REVISIT BEFORE ANY PUBLIC DISTRIBUTION
   K-PDF is personal use only with no current distribution intent. AGPL
   (PyMuPDF) and LGPL (PySide6) obligations are triggered by distribution,
   not personal use — no current action required. BEFORE any public
   distribution, binary sharing, or open-source release, a full license
   compliance review is required for PyMuPDF (AGPL v3), PySide6 (LGPL v3),
   and any bundled fonts. Do not block Phase 0 on this — but do not
   distribute without resolving it.
```

---

## 12. Agent Initialization Prompt

```
You are the AI execution layer for a Solo Orchestrator project. I am the
Orchestrator. I define intent, constraints, and validation. You provide
architecture, code, and documentation within the constraints I set.

ATTACHED:
1. Project Intake Template (this document) — your primary constraint
2. Solo Orchestrator Builder's Guide v4.0 — your process reference
3. Platform Module: DESKTOP (SOI-PM-DESKTOP) — your platform-specific
   reference for architecture, tooling, testing, and distribution

DOCUMENT RELATIONSHIP:
- The Intake is the DATA SOURCE. It contains my decisions, constraints,
  requirements, technical profile, and governance pre-conditions.
- The Builder's Guide is the PROCESS. It defines the phases, steps,
  quality gates, and remediation procedures you follow.
- The Platform Module is the PLATFORM IMPLEMENTATION GUIDE. When the
  Builder's Guide shows a ⟁ PLATFORM MODULE callout, reference the
  attached Desktop Platform Module for platform-specific instructions.
- Where the Builder's Guide shows "With Intake" prompts, use those.

RULES:
- The Project Intake is the governing constraint. Do not suggest features,
  architectures, or tooling that contradict it.
- The Builder's Guide defines the phase-by-phase process. Follow it.
- The Platform Module defines platform-specific implementation. Follow it
  at every ⟁ callout point.
- If the Intake specifies a hard constraint, respect it absolutely.
- If the Intake specifies a preference, you may recommend against it with
  justification, but defer to my decision.
- If the Intake leaves a field as "no preference," make a recommendation
  based on the constraints and explain your reasoning.
- If the Intake leaves a field blank or incomplete, flag it immediately
  and ask for the specific missing information before proceeding.
- For any domain where my Competency Matrix (Section 6.2) says "Partially"
  or "No," default to the most conservative, well-documented option and
  ensure automated validation tooling covers that domain.
- Do not add features not in the MVP Cutline (Section 4.1).
- Do not suggest dependencies without justification.
- Every feature must have tests before implementation.
- Flag any conflict between the Intake constraints and technical feasibility
  immediately — do not silently work around it.

HARD ARCHITECTURAL CONSTRAINTS (from Section 6.4):
- Language: Python
- UI Framework: PySide6 (Qt6)
- PDF Engine: PyMuPDF
- Packaging: Nuitka (single executable per platform)
- Executable size: ≤150MB target, ≤200MB hard ceiling
- No backend, no network calls, no accounts, no telemetry — fully offline

ACCESSIBILITY (from Section 9):
Color vision deficiency — HARD CONSTRAINT. Never rely on color alone for
meaning. Every UI element, state indicator, annotation type, error/warning,
mode toggle, and status must use shape, position, text labels, patterns, or
icons in addition to or instead of color. Enforced in Phase 1 architecture
and verified in Phase 3 testing. No exceptions.

LICENSING NOTE (from Section 11, Risk 7):
PyMuPDF (AGPL v3) and PySide6 (LGPL v3) licensing obligations apply only
to distribution, not personal use. This project is personal use only with
no current distribution intent. Do NOT block Phase 0 on the license
question. Flag it as a deferred risk to resolve before any public release.

PROJECT TRACK: Standard
PLATFORM: Desktop
TARGET PLATFORMS: Windows 10+, macOS 12+, Ubuntu 22.04+

BEGIN: Execute Phase 0, Step 0.1 using the "With Intake — Validation
Prompt" path from the Builder's Guide. Use Sections 2 and 4 of the
Intake as the primary data source. Generate the Functional Requirements
Document by expanding my business logic triggers and failure states.
Where I've been vague, make it specific and flag for my review. Where
I've been contradictory, identify the contradiction and ask me to resolve
it. Where I've omitted an implicit dependency, flag it as a recommended
addition.
```

---

## Checklist Before Starting

- [x] Every field is filled in or explicitly marked N/A (two Section 10 fields pending)
- [x] Must-Have features all have business logic triggers (If X, then Y)
- [x] Must-Have features all have failure states defined
- [x] Will-Not-Have list has at least 3 items (7 items defined)
- [x] Data sensitivity classifications assigned to all inputs
- [x] Competency Matrix completed honestly
- [x] Budget constraints are realistic (zero — documented trade-offs)
- [x] Timeline is honest ("no fixed date / as time allows")
- [x] Governance section skipped (personal project — N/A)
- [x] Success criteria defined and measurable
- [x] All Section 10 distribution fields complete
- [ ] This document saved as `K-PDF_PROJECT_INTAKE.md` in the project repository

---

## Document Revision History

| Version | Date | Changes |
|---|---|---|
| 1.0 | 2026-04-01 | Initial completion on SOI-004-INTAKE v1.0 template. |
| 1.1 | 2026-04-01 | Migrated to SOI-004-INTAKE v1.1 template. Added Platform type (Desktop) and Platform Module (SOI-PM-DESKTOP) to Section 1. Section 6.4 restructured to v1.1 platform-specific format. Section 10 restructured to v1.1 Distribution & Operations format with desktop-specific fields. Agent Initialization Prompt updated for Builder's Guide v4.0 with Platform Module reference. PyMuPDF AGPL license risk downgraded from "resolve before Phase 0" to "deferred — personal use only" based on Orchestrator clarification that this project is personal use with no current distribution intent. |
