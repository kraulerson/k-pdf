# K-PDF — Architecture Decision Record

## Version 1.0 — Phase 1, Step 1.2

**Source:** Product Manifesto v1.0, Project Intake v1.1
**Generated:** 2026-04-01
**Status:** Approved — Option B selected by Orchestrator 2026-04-01

---

## 1. Fixed Stack (Hard Constraints — Not Negotiable)

| Component | Technology | Version | Rationale |
|---|---|---|---|
| Language | Python | 3.13.x | Latest stable with full PySide6, PyMuPDF, and Nuitka support. 3.14 excluded (pyo3/Rust binding incompatibilities with key ecosystem packages). |
| UI Framework | PySide6 (Qt6) | 6.10.x | Official Qt6 Python bindings. Intake hard constraint. |
| PDF Engine | PyMuPDF | 1.26.x | MuPDF C library bindings. Intake hard constraint. |
| Packaging | Nuitka | 4.0.x | AOT Python-to-C compiler. Intake hard constraint. |
| Data Storage | SQLite via `sqlite3` stdlib | Bundled with Python | Intake preference for preferences/settings. |

**Python 3.13 rationale:** PySide6 6.10 supports Python 3.9+. PyMuPDF 1.26 supports 3.9+. Nuitka 4.0 supports 3.13. Python 3.14 has ecosystem-wide Rust binding incompatibilities (pyo3 0.24 doesn't support 3.14). Python 3.13 is the most current fully-compatible version.

---

## 2. Architecture Options

The stack is predetermined. The decision is the **application architecture pattern** — how the code is organized, how components communicate, and how the feature gate mechanism is structured.

### Option A: Flat Layered (Services + Widgets)

```
k_pdf/
├── main.py                  # Entry point, QApplication setup
├── app.py                   # MainWindow, tab management, menu bar
├── services/                # Business logic (no Qt dependency)
│   ├── pdf_service.py       # Open, parse, render, save (wraps PyMuPDF)
│   ├── annotation_service.py
│   ├── form_service.py
│   ├── page_service.py
│   ├── merge_service.py
│   ├── search_service.py
│   └── preferences_service.py
├── widgets/                 # Qt widgets (UI only, delegates to services)
│   ├── pdf_viewport.py
│   ├── tab_bar.py
│   ├── navigation_panel.py
│   ├── annotation_panel.py
│   ├── search_bar.py
│   ├── page_manager.py
│   └── ...
├── models/                  # Data classes, no logic
│   ├── document.py
│   ├── annotation.py
│   └── preferences.py
└── resources/               # Icons, themes, stylesheets
```

**Pattern:** Two-layer — services (logic) and widgets (UI). Widgets call services directly. No intermediary. Simple.

**Pros:**
- Minimal abstraction. Easy to understand and navigate.
- Fast to build. Fewest files per feature.
- Services are independently testable (no Qt dependency in business logic).
- Nuitka has less to compile (simpler import graph).

**Cons:**
- Widgets directly coupled to services. Hard to swap implementations.
- Feature gate requires conditional imports or flags scattered across widgets.
- As features grow, services may bloat.

**Feature Gate:** Build-time constant in a `config.py` module. Widgets check `config.FEATURE_ENABLED["pro_feature_name"]` before rendering UI elements. Pro features are separate service modules excluded from free-tier builds via Nuitka `--nofollow-import-to`.

---

### Option B: Model-View-Presenter (MVP) with Event Bus

```
k_pdf/
├── main.py                  # Entry point
├── app.py                   # Application shell, event bus initialization
├── core/                    # Framework-agnostic core
│   ├── event_bus.py         # Signal/slot-style event system (or Qt signals)
│   ├── document_model.py    # In-memory document state
│   ├── feature_gate.py      # Build-time + runtime feature flag system
│   └── undo_manager.py      # Per-tab undo/redo stack
├── services/                # Business logic (no Qt dependency)
│   ├── pdf_engine.py        # PyMuPDF wrapper: open, render, save
│   ├── annotation_engine.py
│   ├── form_engine.py
│   ├── page_engine.py
│   ├── merge_engine.py
│   └── search_engine.py
├── presenters/              # Mediates between views and services
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
│   ├── preferences_dialog.py
│   └── themes/
│       ├── light.qss
│       └── dark.qss
├── persistence/             # Data storage
│   ├── settings_db.py       # SQLite preferences
│   └── recent_files.py
└── resources/               # Icons, fonts, platform-specific assets
```

**Pattern:** Three-layer — views (Qt widgets), presenters (mediation/coordination), services (business logic). Views never call services directly; presenters handle the data flow. Qt signals connect views to presenters.

**Pros:**
- Clean separation. Views are pure UI — testable with mock presenters.
- Services are pure logic — testable without Qt.
- Presenters coordinate state changes — single place to add undo/redo, logging, feature gates.
- Feature gate is centralized in presenters (presenters don't expose pro features in free tier).
- Undo manager lives in core, connected by presenters — clean per-tab undo/redo.
- Scales to 12+ features without bloat.

**Cons:**
- More files per feature (view + presenter + service).
- Presenter layer adds indirection.
- Slightly larger compiled binary (more modules).

**Feature Gate:** `feature_gate.py` reads a build-time JSON config or compile-time constant. Presenters check the gate before exposing functionality. Pro service modules excluded from free builds via Nuitka `--nofollow-import-to`. Views are identical in both tiers — they simply never receive pro-feature data from presenters.

---

### Option C: Plugin Architecture with Registration System

```
k_pdf/
├── main.py
├── app.py
├── core/
│   ├── plugin_registry.py   # Dynamic feature registration
│   ├── document_model.py
│   ├── event_bus.py
│   ├── undo_manager.py
│   └── feature_gate.py
├── plugins/                 # Each feature is a self-contained plugin
│   ├── pdf_viewer/
│   │   ├── __init__.py      # register() function
│   │   ├── service.py
│   │   ├── presenter.py
│   │   └── view.py
│   ├── annotations/
│   │   ├── __init__.py
│   │   ├── service.py
│   │   ├── presenter.py
│   │   └── view.py
│   ├── forms/
│   ├── search/
│   ├── page_management/
│   ├── merge/
│   ├── dark_mode/
│   └── pro/                 # Pro-tier plugins (excluded from free builds)
│       ├── file_conversion/
│       └── signed_builds/
├── persistence/
└── resources/
```

**Pattern:** Plugin-based. Each feature registers itself with a central registry. The app discovers and loads plugins at startup. Pro features are literally separate plugins.

**Pros:**
- Maximum modularity. Features are fully self-contained.
- Feature gate is trivial: pro plugins not included in free builds.
- Adding post-MVP features is clean (new plugin, no core changes).
- Third-party extension potential (distant future).

**Cons:**
- **Over-engineered for 12 MVP features.** The registration system, lifecycle management, and inter-plugin communication add complexity that isn't justified.
- Nuitka compilation with dynamic plugin discovery is more complex (must explicitly include plugins).
- Cross-plugin dependencies (e.g., annotations depend on document model) create implicit coupling that undermines the plugin isolation.
- More boilerplate per feature than either Option A or B.
- Testing plugin interactions requires integration tests that a simpler architecture avoids.

**Feature Gate:** Plugin exclusion from the build. `plugin_registry.py` only loads what's present. Pro plugins in a `pro/` directory excluded from free-tier Nuitka builds.

---

## 3. Evaluation Matrix

| Criterion | Weight | Option A (Flat) | Option B (MVP) | Option C (Plugin) |
|---|---|---|---|---|
| **Simplicity / Time to MVP** | High | ★★★★★ | ★★★★ | ★★ |
| **Testability (unit + integration)** | High | ★★★ | ★★★★★ | ★★★★ |
| **Feature gate cleanliness** | Medium | ★★ | ★★★★ | ★★★★★ |
| **Undo/redo architecture fit** | Medium | ★★ | ★★★★★ | ★★★★ |
| **Accessibility enforcement** | Medium | ★★★ | ★★★★ | ★★★★ |
| **Nuitka compilation simplicity** | Medium | ★★★★★ | ★★★★ | ★★ |
| **Binary size impact** | Low | ★★★★★ | ★★★★ | ★★★ |
| **Scalability to post-MVP features** | Low | ★★ | ★★★★ | ★★★★★ |
| **Solo maintainability** | High | ★★★★ | ★★★★★ | ★★ |

---

## 4. Recommendation: Option B — Model-View-Presenter (MVP) with Event Bus

**Rationale:**

1. **Testability is critical.** The Orchestrator's competency matrix shows "No" for desktop UI and application logic. Automated testing must cover both. Option B separates them cleanly — services tested without Qt, views tested with mock presenters, presenters tested with mock services.

2. **Undo/redo fits naturally.** The Manifesto requires per-tab undo/redo (50 ops). In Option B, presenters intercept all state-modifying actions and push them onto the undo stack. In Option A, undo must be wired into each widget individually. Option B is structurally cleaner.

3. **Feature gate is centralized.** Presenters are the natural gate point — they control what data flows from services to views. Pro features don't reach views in the free tier because presenters don't expose them. No scattered conditionals in widget code.

4. **Accessibility enforcement.** Presenters can enforce that all data passed to views includes accessibility metadata (text labels, icon names, state descriptions). Views receive complete accessibility data by contract, not by widget-level discipline.

5. **Not over-engineered.** Option C's plugin system adds registration, lifecycle, and discovery machinery that isn't needed for a known 12-feature MVP. Option B has one more layer than A but each layer has a clear, bounded responsibility.

6. **Nuitka-friendly.** All imports are static. No dynamic discovery. `--nofollow-import-to=k_pdf.services.pro.*` excludes pro modules cleanly.

**Rejection rationale:**
- **Option A rejected** because undo/redo and feature gate are structurally difficult to add cleanly. Acceptable for a 3-feature tool, but K-PDF has 12 features with cross-cutting concerns (undo, dirty-state tracking, accessibility metadata).
- **Option C rejected** because the plugin overhead is unjustified. The features are known at build time. Dynamic discovery adds risk (Nuitka compilation, startup performance, inter-plugin coupling) without corresponding benefit.

---

## 5. Build & Distribution Strategy

### 5.1 Development Tooling

| Tool | Purpose | Version |
|---|---|---|
| **uv** | Python project management (replaces pip, venv, pyenv) | 0.11+ |
| **ruff** | Linting + formatting (replaces flake8, black, isort) | Latest stable |
| **mypy** | Static type checking | Latest stable |
| **pytest** | Test runner | Latest stable |
| **pytest-qt** | Qt widget testing | Latest stable |
| **pytest-cov** | Coverage reporting | Latest stable |
| **pip-audit** | Dependency vulnerability scanning | Latest stable |
| **pip-licenses** | License compliance checking | Latest stable |
| **semgrep** | SAST scanning | Latest stable |
| **gitleaks** | Secret detection | Latest stable |
| **pre-commit** | Git hook management (Python ecosystem) | Latest stable |

### 5.2 Build Pipeline (Per Platform)

**Local development (macOS — current machine):**
```bash
# Create project with uv
uv init k-pdf --python 3.13
cd k-pdf
uv add PySide6 PyMuPDF
uv add --dev pytest pytest-qt pytest-cov mypy ruff nuitka pip-audit pip-licenses semgrep-cli pre-commit

# Run tests
uv run pytest

# Build standalone (macOS)
uv run python -m nuitka --mode=standalone --enable-plugin=pyside6 --output-dir=dist src/k_pdf/main.py
```

**CI/CD (GitHub Actions) — all three platforms:**
```yaml
# .github/workflows/build.yml
strategy:
  matrix:
    os: [ubuntu-22.04, windows-latest, macos-latest]
    python-version: ["3.13"]
```

Each platform job:
1. Checkout + install Python 3.13 via `uv`
2. Install dependencies
3. Run ruff (lint + format check)
4. Run mypy (type check)
5. Run pytest with coverage
6. Run semgrep (SAST)
7. Run pip-audit (dependency vulnerabilities)
8. Run pip-licenses (license compliance)
9. Run gitleaks (secret detection)
10. Build with Nuitka (`--mode=onefile` for distribution, `--mode=standalone` for CI validation)
11. Upload build artifact

### 5.3 Distribution

| Platform | Format | How User Gets It |
|---|---|---|
| Windows | Portable `.exe` (Nuitka onefile) | Download from GitHub Releases. Run directly. No installer. |
| macOS | `.dmg` containing the app bundle | Download from GitHub Releases. Open DMG, drag to Applications (or run from DMG). |
| Linux | AppImage (single file) | Download from GitHub Releases. `chmod +x`, run. No installation. |

**Auto-update:** None in MVP. Manual download from GitHub Releases.

### 5.4 Executable Size Strategy

| Component | Estimated Size |
|---|---|
| Python 3.13 runtime (compiled by Nuitka) | ~15-25 MB |
| PySide6 (Qt6 libs — platform-specific) | ~60-90 MB |
| PyMuPDF (MuPDF C library) | ~15-20 MB |
| K-PDF application code | ~1-3 MB |
| Icons, themes, resources | ~2-5 MB |
| **Estimated total** | **~93-143 MB** |

Target: ≤150 MB. Hard ceiling: ≤200 MB.

**Size optimization levers:**
1. Nuitka `--nofollow-import-to` to exclude unused Qt modules (QtWebEngine, Qt3D, QtMultimedia, etc.)
2. Strip debug symbols in release builds
3. Nuitka `--enable-plugin=pyside6` handles Qt plugin inclusion automatically
4. UPX compression for onefile mode (if size exceeds target)

---

## 6. Observability & Logging Strategy

**Structured logging from Day 1.** Even though K-PDF is offline with no monitoring backend, structured logs are essential for debugging user-reported issues.

| Aspect | Decision |
|---|---|
| **Library** | Python `logging` stdlib with JSON formatter |
| **Format** | JSON lines: `{"timestamp", "level", "module", "message", "context"}` |
| **Output** | File: `{config_dir}/logs/k-pdf.log` (rotating, max 5 MB, 3 backups) |
| **Levels** | DEBUG (dev), INFO (default), WARNING, ERROR, CRITICAL |
| **Correlation** | Per-tab session ID for tracing operations across a document lifecycle |
| **Sensitive data** | NEVER log: file contents, form field values, passwords, annotation text. Log: file paths (user-controlled), operation names, error messages. |

---

## 7. Secrets Management

**Not applicable in the traditional sense** — K-PDF has no API keys, no tokens, no cloud credentials.

The only sensitive data is PDF passwords (Feature 8), which are:
- Never stored to disk
- Never logged
- Passed directly to PyMuPDF for decryption
- Cleared from memory after the decryption call

No secrets management infrastructure needed.

---

## 8. Authentication & Identity

**Not applicable.** No accounts, no authentication. Local application. Intake hard constraint.

---

## DECISION GATE — RESOLVED

**Selected: Option B — Model-View-Presenter (MVP) with Event Bus.**
Approved by Orchestrator on 2026-04-01.
