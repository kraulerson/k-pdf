# K-PDF — Project Bible

## Version 1.0 — Phase 1, Step 1.6

**Status:** Draft — Awaiting Orchestrator Review (DECISION GATE)

---

## 1. Product Manifesto (Summary)

K-PDF is a free, offline, cross-platform desktop PDF reader and editor covering the 80% use case. Fully offline. Zero accounts. Zero telemetry. Single self-contained executable per platform.

**Full Manifesto:** See `PRODUCT_MANIFESTO.md`

**MVP Cutline:** 12 features + 7 implicit requirements.

| # | Feature |
|---|---|
| 1 | Open and Render PDF |
| 2 | Multi-Tab Document Support |
| 3 | Page Navigation (Thumbnails, Bookmarks, Outline) |
| 4 | Text Search Within Document |
| 5 | Zoom, Rotate, Page Fit Modes |
| 6 | Text Markup Annotations (Highlight, Underline, Strikethrough) |
| 7 | Sticky Notes & Text Box Annotations |
| 8 | AcroForm Filling & Save |
| 9 | Page Management (Add, Delete, Reorder, Rotate) |
| 10 | Merge Multiple PDFs |
| 11 | Dark / Night Reading Mode |
| 12 | Annotation Summary Panel |

**Implicit requirements:** Undo/Redo (50 ops/tab), Keyboard Shortcuts, Preferences Dialog, Text Copy, Basic Printing, File > Save As, Recent Files List.

**Resolved decisions:** No auto-save. Full memory load (no streaming). 50-op undo depth.

---

## 2. Revenue Model & Cost Constraints

- **Price:** Free (MVP). Future paid Pro tier.
- **License:** MIT (free tier). Pro tier TBD.
- **Infrastructure cost:** $0. Fully offline.
- **Distribution:** GitHub Releases only.
- **Feature gate:** Build-time flag system required from Phase 1. Presenters check gate. Pro service modules excluded from free builds via Nuitka `--nofollow-import-to`.

---

## 3. Architecture Decision Record

**Selected: Option B — Model-View-Presenter (MVP pattern) with Event Bus**

**Full ADR:** See `docs/ARCHITECTURE_DECISION.md`

### 3.1 Stack

| Component | Technology | Version |
|---|---|---|
| Language | Python | 3.13.x |
| UI Framework | PySide6 (Qt6) | 6.10.x |
| PDF Engine | PyMuPDF | 1.26.x |
| Packaging | Nuitka | 4.0.x |
| Data Storage | SQLite (stdlib sqlite3) | Bundled |
| Project Management | uv | 0.11+ |

### 3.2 Application Structure

```
k_pdf/
├── main.py                  # Entry point
├── app.py                   # QApplication shell, event bus init
├── core/
│   ├── event_bus.py         # Qt signal-based event system
│   ├── document_model.py    # In-memory document state
│   ├── feature_gate.py      # Build-time feature flag system
│   └── undo_manager.py      # Per-tab undo/redo stack
├── services/                # Business logic (NO Qt imports, NO PyMuPDF imports outside this dir)
│   ├── pdf_engine.py        # PyMuPDF wrapper: open, render, save
│   ├── annotation_engine.py # Create, modify, delete annotations
│   ├── form_engine.py       # AcroForm field detection and filling
│   ├── page_engine.py       # Page manipulation (add, delete, reorder, rotate)
│   ├── merge_engine.py      # Multi-PDF merge
│   └── search_engine.py     # Text search
├── presenters/              # Mediation layer (coordinates services ↔ views)
│   ├── document_presenter.py
│   ├── annotation_presenter.py
│   ├── navigation_presenter.py
│   ├── search_presenter.py
│   └── page_management_presenter.py
├── views/                   # Qt widgets (pure UI, no business logic)
│   ├── main_window.py
│   ├── pdf_viewport.py
│   ├── tab_bar.py
│   ├── navigation_panel.py
│   ├── annotation_panel.py
│   ├── search_bar.py
│   ├── page_manager_panel.py
│   ├── merge_dialog.py
│   ├── preferences_dialog.py
│   └── themes/
│       ├── light.qss
│       └── dark.qss
├── persistence/
│   ├── settings_db.py       # SQLite preferences
│   └── recent_files.py
└── resources/
    ├── icons/
    └── fonts/
```

### 3.3 Key Architectural Rules

1. **PyMuPDF imports ONLY in `services/`.** Enforce with linting rule. This isolates the AGPL dependency and makes engine replacement feasible.
2. **Views never call services directly.** All data flows through presenters.
3. **Long-running operations in QThread.** Presenters dispatch to background threads via QThreadPool. Views receive results via Qt signals.
4. **Undo/redo managed by presenters.** Presenters wrap every state-modifying action in an UndoAction and push to the per-tab UndoStack.
5. **Feature gate checked in presenters.** Pro features never reach views in the free tier.
6. **No `os.system()` or `subprocess.Popen(shell=True)` anywhere.**

### 3.4 Rejected Alternatives

- **Option A (Flat Layered):** Rejected — undo/redo and feature gate are structurally difficult without a presenter layer.
- **Option C (Plugin Architecture):** Rejected — over-engineered for 12 known features. Dynamic discovery complicates Nuitka compilation.

---

## 4. Risk/Mitigation Matrix

**Full matrix:** See `docs/RISK_MITIGATION_MATRIX.md`

### P0 Risks (Architect In Now)

| Risk | Mitigation |
|---|---|
| Qt event loop blocked by PDF operations | All long-running service ops in QThread. Presenters dispatch/receive via signals. |
| MuPDF code execution via crafted PDF | Keep PyMuPDF updated. pip-audit in CI. No elevated privileges. |
| AGPL license blocks distribution | PyMuPDF isolated in services/. Import linting enforced. Engine replaceable. |

### P1 Risks (Build Into Phase 2)

| Risk | Mitigation |
|---|---|
| Memory exhaustion (multi-tab) | Process memory monitoring. Warnings at 60% RAM. Block at 80%. |
| Page cache memory pressure | LRU cache, 50 pages/tab max. Render at screen resolution. |
| Nuitka compilation failures | CI builds on all 3 platforms from Phase 2 start. |
| Malformed annotations | Try/except per annotation. Graceful degradation. |
| Path traversal | Canonicalize all paths. Never follow embedded references automatically. |
| File locking on Windows | Error handling + Save As fallback. |

---

## 5. Data Model

**Full specification:** See `docs/DATA_MODEL.md`

### 5.1 Persistent (SQLite)

- `schema_version` — migration tracking
- `preferences` — key-value store, JSON-encoded values
- `recent_files` — file paths, last page, last zoom

### 5.2 In-Memory (Per Tab)

- `DocumentModel` — PyMuPDF handle, metadata, dirty flag
- `ViewState` — current page, zoom, rotation, search state
- `PageCache` — LRU cache of rendered QPixmap, max 50 pages
- `UndoStack` — max 50 operations, do/undo callables

---

## 6. Auth & Identity Strategy

Not applicable. No accounts. No authentication. Offline-only. Intake hard constraint.

---

## 7. Observability & Logging Strategy

| Aspect | Decision |
|---|---|
| Library | Python `logging` stdlib + JSON formatter |
| Format | JSON lines: timestamp, level, module, message, context |
| Output | File: `{config_dir}/logs/k-pdf.log` (rotating, 5MB, 3 backups) |
| Levels | DEBUG (dev), INFO (default), WARNING, ERROR, CRITICAL |
| Correlation | Per-tab session UUID |
| Sensitive data | NEVER log: file contents, form values, passwords, annotation text |

---

## 8. UI Component Specifications

**Full specification:** See `docs/UI_SCAFFOLDING.md`

### Key Layout

- **Main window:** Menu bar, toolbar, three-panel layout (navigation | viewport | annotations), status bar, tab bar.
- **All toolbar buttons:** Icon + text label (never icon-only).
- **Panels:** Collapsible, resizable, state persisted in preferences.
- **Themes:** Light (default) + Dark. Both WCAG AA compliant.

### Component States

Every interactive component handles: **Empty, Loading, Error, Success** (and Disabled where applicable).

---

## 9. Coding Standards

### 9.1 Tooling

| Tool | Purpose | Config |
|---|---|---|
| ruff | Lint + format | `pyproject.toml` — `line-length = 100`, Python 3.13 target |
| mypy | Type checking | `pyproject.toml` — `strict = true` |
| pytest | Testing | `pyproject.toml` — `testpaths = ["tests"]` |
| pytest-qt | Qt widget tests | Used with `qtbot` fixture |
| pre-commit | Git hooks | `.pre-commit-config.yaml` |

### 9.2 Rules

- **Type hints required** on all function signatures (enforced by mypy strict).
- **Docstrings** on all public classes and functions (enforced by ruff D rules).
- **No wildcard imports.** `from fitz import *` is banned.
- **No mutable default arguments.**
- **Test naming:** `test_<behavior>_when_<condition>` (e.g., `test_returns_error_when_file_not_found`).
- **Import ordering:** stdlib, third-party, local (enforced by ruff I rules).

### 9.3 Never Do This

- Do not add features not in the MVP Cutline.
- Do not import `fitz` or `pymupdf` outside `services/`.
- Do not add dependencies without justification.
- Do not use `--no-verify` to bypass Git hooks.
- Do not delete tests to make them pass.
- Do not include credentials, real PII, or passwords in code, comments, or test fixtures.
- Do not use `os.system()` or `subprocess.Popen(shell=True)`.
- Do not commit `.env` files or secrets.
- Do not log file contents, form field values, passwords, or annotation text.
- Do not proceed past a decision gate without Orchestrator approval.
- Do not modify the SQLite schema directly — use the migration system.

---

## 10. Build & Distribution Strategy

### 10.1 Development

```bash
# Project setup
uv init k-pdf --python 3.13
uv add PySide6 PyMuPDF
uv add --dev pytest pytest-qt pytest-cov mypy ruff nuitka pip-audit pip-licenses pre-commit gitleaks semgrep

# Daily workflow
uv run ruff check .                    # Lint
uv run ruff format .                   # Format
uv run mypy src/                       # Type check
uv run pytest                          # Test
uv run pytest --cov=k_pdf --cov-report=term-missing  # Coverage
```

### 10.2 CI/CD (GitHub Actions)

**Matrix:** `{ubuntu-22.04, windows-latest, macos-latest} × {python-3.13}`

**Per-platform pipeline:**
1. Checkout + Python 3.13 (via uv)
2. Install deps
3. ruff check + ruff format --check
4. mypy strict
5. pytest with coverage (fail if <80%)
6. semgrep SAST scan
7. pip-audit (dependency vulnerabilities)
8. pip-licenses (license compliance)
9. gitleaks (secret detection)
10. Nuitka build (standalone mode for CI, onefile for release)
11. Upload artifact
12. (Release only) Create GitHub Release with platform artifacts

### 10.3 Distribution

| Platform | Format | Size Target |
|---|---|---|
| Windows | Portable `.exe` (Nuitka onefile) | ≤150MB (hard ceiling ≤200MB) |
| macOS | `.dmg` (app bundle) | ≤150MB |
| Linux | AppImage | ≤150MB |

### 10.4 Size Optimization

- Nuitka `--nofollow-import-to` to exclude: QtWebEngine, Qt3D, QtMultimedia, QtRemoteObjects, QtBluetooth, QtNfc, QtSensors, QtSerialPort, QtTest
- Strip debug symbols in release builds
- UPX compression if size exceeds target

---

## 11. Orchestrator Profile Summary

### Competency Gaps & Automated Coverage

| Domain | Gap | Automated Tool |
|---|---|---|
| Desktop UI (PySide6) | No experience | pytest-qt, UI state tests |
| Application Logic | No experience | pytest, mypy strict |
| Data Storage | Partial | Schema migration tests |
| Security | Partial | pip-audit, gitleaks, semgrep, path validation tests |
| Accessibility | Partial | Automated contrast checks, annotation type differentiation tests |
| Performance | Partial | Benchmarking suite (500-page doc targets) |
| Desktop Packaging (Nuitka) | No experience | CI build on all 3 platforms |
| PDF Spec Compliance | Partial | Real-world PDF test corpus (50+ diverse files) |

---

## 12. Accessibility Requirements

**Source:** Intake Section 9. **This is a HARD CONSTRAINT.**

1. **Never rely on color alone** for any meaning. Every UI element, state, annotation type, error, warning, mode, and status uses shape, position, text labels, patterns, or icons in addition to or instead of color.
2. **WCAG 2.1 AA** contrast ratios in both light and dark themes.
3. **All interactive elements** keyboard navigable with visible focus indicators.
4. **Annotation types** distinguished by icon + text label (never color alone).
5. **State indicators** use non-color differentiators (see UI Scaffolding §7.3).

---

## 13. Platform-Specific Requirements (SOI-PM-DESKTOP)

| Requirement | Windows | macOS | Linux |
|---|---|---|---|
| Min OS | Windows 10+ | macOS 12+ | Ubuntu 22.04+ |
| Packaging | Nuitka onefile (.exe) | Nuitka → .app bundle → DMG | Nuitka → AppImage |
| Code signing | Deferred (SmartScreen warning) | Deferred (Gatekeeper warning) | Not required |
| File association | Registry entry via Nuitka | Info.plist in .app bundle | .desktop file in AppImage |
| Config directory | %APPDATA%\K-PDF | ~/Library/Application Support/K-PDF | ~/.config/k-pdf |
| Log directory | %APPDATA%\K-PDF\logs | ~/Library/Application Support/K-PDF/logs | ~/.config/k-pdf/logs |
| Single instance | msvcrt.locking on lock file | fcntl.flock on lock file | fcntl.flock on lock file |
| Font bundling | Not needed (system fonts OK) | Not needed | Bundle Noto Sans (OFL) |
| HiDPI | Qt handles via DPI awareness manifest | Native retina support | Set PassThrough rounding policy |

---

## 14. Context Management Plan

**Project size estimate:** Medium (30-100 files at completion).

**Strategy:** Module-level summaries + master index.

- **Phase 2 sessions:** Provide this Bible + the specific feature's FRD section + the relevant presenter/service/view files.
- **Context Health Check:** Every 3-4 features, agent summarizes features built/remaining/known issues. If drift detected, fresh session with Bible + last 3-4 active files.
- **Qdrant:** Store feature completion summaries, architecture decisions, and debugging insights for cross-session retrieval.

---

## DECISION GATE — Review Complete Bible

**This is the point of no return. After approval, Phase 2 construction begins.**

**Orchestrator: Review the complete Bible and all referenced documents. Approve to proceed to Phase 2, or request modifications.**

Referenced documents:
- `PRODUCT_MANIFESTO.md` — MVP Cutline, revenue model, resolved decisions
- `docs/ARCHITECTURE_DECISION.md` — 3 options evaluated, Option B selected
- `docs/RISK_MITIGATION_MATRIX.md` — 5 edge cases, 3 security vulns, 2 data bottlenecks, 1 rewrite risk
- `docs/DATA_MODEL.md` — SQLite schema, in-memory entities, data flow
- `docs/UI_SCAFFOLDING.md` — Layout, components, themes, keyboard shortcuts, accessibility
- `docs/FUNCTIONAL_REQUIREMENTS.md` — All 12 features expanded
- `docs/USER_JOURNEY_MAP.md` — 5 success paths
- `docs/DATA_CONTRACT.md` — Inputs, outputs, transformations, persistence
