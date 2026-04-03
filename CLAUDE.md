# CLAUDE.md — K-PDF Project Instructions

## Role
You are the AI execution layer for a Solo Orchestrator project.
The Orchestrator defines intent, constraints, and validation.
You provide architecture, code, and documentation within the
constraints set by the Project Intake and Project Bible.

## Process Reference
@K-PDF_PROJECT_INTAKE.md
@PROJECT_BIBLE.md
@PRODUCT_MANIFESTO.md
@CONTRIBUTING.md

Follow the Solo Orchestrator Builder's Guide (SOI-002-BUILD v4.0)
phase-by-phase process. Work autonomously between decision gates.
At each decision gate, present your recommendation and wait for
Orchestrator approval. Between gates, only stop if you encounter
a conflict, ambiguity, or blocker you cannot resolve from the
Intake, Bible, or prior context.

## Current State
- **Project:** K-PDF
- **Phase:** 2 (Construction)
- **Track:** Standard
- **Features built:** Features 1-12 (Open/Render, Multi-Tab, Navigation, Search, Zoom/Rotate, Text Markup, Sticky Notes, Forms/Save, Page Management, Merge PDFs, Dark Mode, Annotation Summary) + Printing (implicit)
- **Features remaining:** 6 implicit (see MVP Cutline)
- **Known issues:** Coverage at 84%+ (threshold 65%)
- **Last session summary:** Implemented Printing (Ctrl+P) implicit feature — PrintService renders pages at 300 DPI to QPrinter via QPainter. File > Print... action with full page range support. 754 tests, 84% coverage.

Update this section at the end of every session.

## Commands
```bash
uv run ruff check .                                    # Lint
uv run ruff format .                                   # Format
uv run mypy k_pdf/                                     # Type check
uv run pytest                                          # Test
uv run pytest --cov=k_pdf --cov-report=term-missing    # Coverage
uv run pip-audit                                       # Dependency vulnerabilities
uv run pip-licenses                                    # License compliance
semgrep scan --config auto k_pdf/                      # SAST scan
gitleaks detect --source .                             # Secret detection
```

## Tool Usage

### Superpowers (Agentic Skills Framework)
Superpowers skills activate automatically. Follow their workflows
when they trigger, with these constraints:

**Brainstorming skill:** Use ONLY for implementation-level design
decisions within a feature (component structure, data structures,
algorithm selection). Do NOT use brainstorming to reconsider
product requirements (governed by Product Manifesto) or
architecture decisions (governed by Project Bible). If the
brainstorming skill suggests features not in the MVP Cutline,
reject them.

**Writing-plans skill:** Plans must align with the MVP Cutline.
If a generated plan includes tasks for features outside the
Cutline, remove those tasks before executing.

**Subagent-driven-development:** Use for Phase 2 feature
construction. Each subagent task must pass both review stages
(spec compliance, then code quality) before merging.

**Test-driven-development:** This skill enforces RED-GREEN-REFACTOR.
Do not write implementation code before a failing test exists.
Do not skip the "verify it fails" step.

**Git worktrees:** Create a worktree for each feature. Verify
clean test baseline before starting work. Use the
finishing-a-development-branch skill to merge when complete.

### Context7 (Library Documentation)
When making implementation decisions that depend on a specific
library's API, query Context7 for current documentation before
writing code. Do not rely on training data for version-specific
API details. Priority use cases:
- PySide6 widget API and signal/slot syntax
- PyMuPDF document manipulation API
- Nuitka compilation flags and options
- pytest-qt fixture usage

### Qdrant (Semantic Memory)
Store and retrieve project context using the Qdrant MCP tools.

**Store (qdrant-store) after:**
- Completing each feature: summary, key decisions, patterns used
- Resolving a significant bug: problem, root cause, fix
- Each phase gate transition: what was approved, what changed
- End of each session: current state summary for next session

**Retrieve (qdrant-find) before:**
- Starting a new session: "latest project state for K-PDF"
- Starting a new feature: "architecture decisions related to [DOMAIN]"
- Debugging: "prior issues similar to [SYMPTOM]"
- Context Health Checks: "features completed for K-PDF"

### Claude Dev Framework (Compliance Hooks)
Git hooks enforce standards automatically. Do not attempt to
bypass hooks. If a hook blocks a commit:
1. Read the hook's error message
2. Fix the violation
3. Re-attempt the commit
Never use --no-verify to skip hooks.

## Architecture Constraints
- **Pattern:** Model-View-Presenter (MVP) with Event Bus
- **Stack:** Python 3.13 + PySide6 6.11 + PyMuPDF 1.27 + Nuitka 4.0
- **Database:** SQLite via stdlib sqlite3, schema-versioned migrations
- **Logging:** Structured JSON, rotating file, per-tab session UUID correlation
- **PyMuPDF imports ONLY in k_pdf/services/** — AGPL isolation
- **Views never call services** — all data flows through presenters
- **Long-running ops in QThread** — never block Qt event loop

## Accessibility Requirements
- **HARD CONSTRAINT:** Never rely on color alone for any meaning
- WCAG 2.1 AA contrast ratios in both light and dark themes
- All interactive elements keyboard navigable with visible focus indicators
- Annotation types distinguished by icon + text label (never color alone)
- State indicators use non-color differentiators

## Never Do This
- Do not add features not in the MVP Cutline
- Do not import fitz or pymupdf outside k_pdf/services/
- Do not modify the SQLite schema directly — use the migration system
- Do not add dependencies without justification
- Do not use `--no-verify` to bypass Git hooks
- Do not delete tests to make them pass
- Do not include credentials, real PII, or passwords in code, comments, or test fixtures
- Do not use `os.system()` or `subprocess.Popen(shell=True)`
- Do not commit .env files or secrets
- Do not log file contents, form field values, passwords, or annotation text
- Do not proceed past a decision gate without Orchestrator approval

## Competency Gaps — Extra Validation Required
- **Desktop UI (PySide6):** No experience — always run pytest-qt after UI changes
- **Application Logic:** No experience — always run full test suite
- **Security:** Partial — always run semgrep + pip-audit after security-related changes
- **Accessibility:** Partial — verify color-independence on every UI component
- **Desktop Packaging (Nuitka):** No experience — rely on CI build verification
