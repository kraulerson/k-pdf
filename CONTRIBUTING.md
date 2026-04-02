# Contributing to K-PDF

## Development Setup

```bash
# Clone and set up
git clone https://github.com/kraulerson/k-pdf.git
cd k-pdf
uv sync

# Daily workflow
uv run ruff check .                                    # Lint
uv run ruff format .                                   # Format
uv run mypy k_pdf/                                     # Type check
uv run pytest                                          # Test
uv run pytest --cov=k_pdf --cov-report=term-missing    # Coverage
```

## Coding Standards

### Tooling

| Tool | Purpose | Config |
|---|---|---|
| ruff | Lint + format | `pyproject.toml` — line-length=100, Python 3.13 target |
| mypy | Type checking | `pyproject.toml` — strict=true |
| pytest | Testing | `pyproject.toml` — testpaths=["tests"] |
| pytest-qt | Qt widget tests | Used with `qtbot` fixture |
| pre-commit | Git hooks | `.pre-commit-config.yaml` |

### Rules

- **Type hints required** on all function signatures (enforced by mypy strict).
- **Docstrings** on all public classes and functions (Google style, enforced by ruff D rules).
- **No wildcard imports.** `from fitz import *` is banned.
- **No mutable default arguments.**
- **Import ordering:** stdlib, third-party, local (enforced by ruff I rules).

### Test Naming

```
test_<behavior>_when_<condition>
```

Examples:
- `test_returns_error_when_file_not_found`
- `test_renders_page_when_pdf_opened`
- `test_shows_password_dialog_when_encrypted`

### Architecture Rules

1. **PyMuPDF imports ONLY in `k_pdf/services/`.** This isolates the AGPL dependency.
2. **Views never call services directly.** All data flows through presenters.
3. **Long-running operations in QThread.** Never block the Qt event loop.
4. **Undo/redo managed by presenters.** Wrap state-modifying actions in UndoAction.
5. **Feature gate checked in presenters.** Pro features never reach views in the free tier.
6. **No `os.system()` or `subprocess.Popen(shell=True)` anywhere.**

### Never Do This

- Add features not in the MVP Cutline
- Import `fitz` or `pymupdf` outside `k_pdf/services/`
- Add dependencies without justification
- Use `--no-verify` to bypass Git hooks
- Delete tests to make them pass
- Include credentials, real PII, or passwords in code, comments, or test fixtures
- Use `os.system()` or `subprocess.Popen(shell=True)`
- Commit `.env` files or secrets
- Log file contents, form field values, passwords, or annotation text
- Modify the SQLite schema directly — use the migration system

## Accessibility

**This is a hard constraint.** See PROJECT_BIBLE.md Section 12.

- Never rely on color alone for any meaning
- WCAG 2.1 AA contrast ratios in both themes
- All interactive elements keyboard navigable
- Annotation types distinguished by icon + text label
