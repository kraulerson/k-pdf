# K-PDF — Risk/Mitigation Matrix

## Version 1.0 — Phase 1, Step 1.3

**Architecture Under Test:** Option B — Model-View-Presenter with Event Bus
**Stack:** Python 3.13 / PySide6 6.10 / PyMuPDF 1.26 / Nuitka 4.0 / SQLite

---

## 1. Edge Cases Where This Stack Fails

### EC-1: PyMuPDF Memory Exhaustion on Multi-Tab Large Documents

**Scenario:** User opens 10+ tabs, each with a 50-100MB PDF. PyMuPDF loads each document fully into memory. With rendered page caches (pixmaps), total memory consumption reaches 4-8GB. On machines with 8GB RAM, the application triggers OS-level memory pressure, becomes unresponsive, or is killed by the OOM killer (Linux) or compressed to swap (macOS/Windows).

**Trigger condition:** >2GB aggregate PyMuPDF document memory + rendered page caches.

**Mitigation:**
- Monitor process memory via `psutil.Process().memory_info().rss` on a 10-second timer.
- At 60% of system RAM: status bar warning ("System memory is low. Consider closing unused tabs.").
- At 80% of system RAM: block new tab opens with dialog ("Insufficient memory to open another document. Close existing tabs first.").
- Implement LRU eviction for rendered page caches: pages not visible for >30 seconds have their pixmaps released and re-rendered on demand.
- Set a per-tab page cache limit (e.g., 50 rendered pages per tab, evict oldest).

### EC-2: PDF with Malformed Annotation Structures

**Scenario:** A PDF created by a buggy third-party tool has annotations with invalid rectangles (negative dimensions, coordinates outside page bounds), missing required keys, or circular reference chains in the annotation tree. PyMuPDF may return partial data, raise exceptions on specific annotations, or silently skip them.

**Trigger condition:** Real-world PDFs from diverse sources (government forms, scanned + OCR'd documents, old Acrobat versions).

**Mitigation:**
- Wrap every individual annotation read in try/except at the service layer.
- Failed annotations logged at WARNING level with page number and annotation index.
- Annotation panel shows successfully parsed annotations only. A counter at the bottom: "Showing [X] of [Y] annotations. [Z] could not be read."
- Rectangle validation in the annotation service: clamp to page bounds, reject negative dimensions.
- Build a test corpus of 50+ real-world PDFs from diverse sources (Phase 3 requirement).

### EC-3: Qt Event Loop Blocked by Long-Running PDF Operations

**Scenario:** User initiates a merge of 20 large PDFs, or searches a 500-page document, or loads a 200MB file. PyMuPDF operations run on the main thread, blocking the Qt event loop. UI freezes. On macOS, the spinning beach ball appears. On Windows, the window goes "Not Responding."

**Trigger condition:** Any PyMuPDF operation taking >200ms.

**Mitigation:**
- All potentially long-running service operations execute in a `QThread` or `QRunnable` via `QThreadPool`.
- Services emit progress signals (Qt signals or event bus events) consumed by presenters, which update progress UI in views.
- Every long operation must support cancellation via a `cancel_event` (threading.Event).
- The presenter layer is the boundary: presenters dispatch to background threads and receive results via signals. Views never interact with threads.
- Operations that must be on the main thread (Qt widget updates): only the final "update view with result" step.

### EC-4: Nuitka Compilation Fails with PyMuPDF C Extensions

**Scenario:** Nuitka's `--mode=onefile` struggles with PyMuPDF's C extension modules (`_fitz.so` / `_fitz.pyd`). The compiled binary runs on the build machine but crashes on a clean machine with missing shared libraries (libmupdf, platform-specific C runtime dependencies). Or Nuitka doesn't include PyMuPDF's bundled MuPDF library in the onefile archive.

**Trigger condition:** First build on each platform. Particularly Linux (varied libc versions) and Windows (MSVC runtime).

**Mitigation:**
- CI/CD builds on all three platforms from Phase 2 onward (not deferred to Phase 4).
- Test each build on a clean VM/container (no development tools installed) as part of CI.
- Use Nuitka `--include-module=fitz` and `--include-module=pymupdf` explicitly.
- For onefile mode: verify `--include-data-files` captures PyMuPDF's bundled shared libraries.
- If onefile fails: fall back to `--mode=standalone` with a wrapper script (acceptable for MVP).
- Document the exact Nuitka flags per platform in the Project Bible.

### EC-5: AcroForm Fields with Complex JavaScript Actions

**Scenario:** A PDF form has JavaScript-based field validation, calculated fields (e.g., "Total = Qty × Price"), or conditional field visibility. PyMuPDF does not execute JavaScript. The form appears to work (fields are fillable) but validation doesn't fire, calculated fields don't update, and conditional visibility doesn't change.

**Trigger condition:** Any form with `/AA` (Additional Actions) or `/JS` (JavaScript) entries in field dictionaries.

**Mitigation:**
- At form detection time: scan field dictionaries for `/AA` and `/JS` keys.
- If JavaScript actions detected: non-modal notification — "This form contains JavaScript-based features (calculated fields, conditional logic) that are not supported. All fields are fillable, but automated calculations and validations will not execute."
- Log which fields have JavaScript actions (for debugging/support).
- This is a documented limitation, not a bug. Add to user-facing documentation.

---

## 2. Security Vulnerabilities Inherent to This Design

### SV-1: Malicious PDF File Processing (Code Execution via MuPDF)

**Threat:** MuPDF (the C library underlying PyMuPDF) parses complex binary formats. A crafted PDF could exploit a buffer overflow, integer overflow, or use-after-free in MuPDF's C code, achieving code execution in the context of the K-PDF process.

**This is not theoretical — MuPDF has had CVEs** (e.g., CVE-2021-37220, CVE-2023-31794). PyMuPDF inherits all MuPDF vulnerabilities.

**Mitigation:**
- **Keep PyMuPDF updated.** Pin to exact version in lockfile. Monthly dependency audit (Phase 4 maintenance cadence). Subscribe to PyMuPDF GitHub releases for security advisories.
- **Run `pip-audit` in CI.** Block builds with known critical/high CVEs in PyMuPDF or its dependencies.
- **Do not process PDFs with elevated privileges.** K-PDF should never require admin/root. If packaged with Nuitka, the executable runs as the current user.
- **No network access.** Even if code execution is achieved, the application has no network capability — limiting exfiltration vectors. (This is a defense-in-depth benefit of the offline-only constraint.)
- **Future consideration (post-MVP):** Process PDF parsing in a subprocess with reduced OS privileges (sandboxing). Not justified for MVP personal use, but required before public distribution.

### SV-2: Path Traversal via PDF Content or File Dialogs

**Threat:** A PDF's embedded file specification, outline entry, or annotation link could contain a path traversal payload (e.g., `../../.ssh/id_rsa`). If the application follows such paths without validation, it could read or overwrite files outside the user's intended scope. Similarly, the recent files list stores file paths — if a malformed path is injected, it could be followed on next launch.

**Mitigation:**
- **Canonicalize all file paths** using `pathlib.Path.resolve()` before any file system operation.
- **Never follow embedded file references automatically.** PDF link actions that reference local files: prompt user with the full resolved path before opening.
- **Validate recent files list entries** on load: `Path.exists()` and `Path.is_file()`. Remove entries that fail validation (don't follow them).
- **Save dialog:** Use Qt's native file dialog (`QFileDialog.getSaveFileName`), which enforces OS-level path validation.
- **No `os.system()` or `subprocess.Popen(shell=True)` anywhere in the codebase.** This is a "Never Do This" rule.

### SV-3: Insecure Temporary File Handling During Merge and Save

**Threat:** During merge operations and Save (incremental save to the same file), the application may write temporary files. If these are created in a world-readable location with predictable names, another process could read the temp file (information disclosure) or replace it (data corruption via symlink attack).

**Mitigation:**
- Use `tempfile.NamedTemporaryFile(delete=False)` with default secure permissions (0o600 on Unix).
- Temporary files created in the user's OS temp directory (not the PDF's directory).
- Delete temporary files in a `finally` block after the operation completes.
- For incremental save: PyMuPDF writes directly to the file (no temp file needed). For Save As: write to a temp file in the destination directory, then `os.replace()` (atomic on all platforms).
- Verify: no temporary files left behind after operations (test in Phase 3).

---

## 3. Data Storage Bottleneck Risks

### DB-1: SQLite Preferences File Corruption on Concurrent Access

**Trigger condition:** User has two instances of K-PDF running (possible since there's no single-instance enforcement in MVP). Both instances write to the same SQLite preferences database simultaneously. SQLite handles concurrent reads but can fail on concurrent writes, potentially corrupting the database file.

**Mitigation:**
- **Single-instance enforcement:** On startup, create a lock file (`{config_dir}/k-pdf.lock`) using `fcntl.flock` (Unix) or `msvcrt.locking` (Windows). If lock acquisition fails, activate the existing instance (bring window to front) instead of launching a new one.
- **SQLite WAL mode:** Enable Write-Ahead Logging (`PRAGMA journal_mode=WAL`) which provides better concurrency and corruption resistance than the default rollback journal.
- **Recovery:** On database open, run `PRAGMA integrity_check`. If corrupt, rename the corrupt file as `.bak`, create a fresh database with defaults, and show notification: "Preferences were reset due to a data error. Your previous settings were backed up."

### DB-2: Rendered Page Cache Memory Pressure on Large Documents

**Trigger condition:** User opens a 500-page document and scrolls through all pages. Each rendered page at 150 DPI ≈ 3-5MB as a QPixmap. 500 pages × 4MB = 2GB of pixmap data in memory. Combined with the PyMuPDF document object (50-100MB for a large PDF), a single tab could consume 2.1GB.

**Mitigation:**
- **LRU page cache with fixed size:** Maximum 50 rendered pages per tab (configurable). When the cache is full, evict the least recently viewed page. Re-render on demand when scrolled back to.
- **Render at screen resolution, not maximum DPI:** Render pages at the current zoom level, not at maximum quality. A page at Fit Width on a 1920px-wide viewport needs ~2000px width, not 4000px.
- **Thumbnail cache is separate and smaller:** Thumbnails rendered at ~150px width ≈ 10-20KB each. 500 thumbnails = 5-10MB total. Acceptable.
- **Memory monitoring (same as EC-1):** Process-level memory tracking with warnings and tab-open blocking at high memory.

---

## 4. Rewrite Risk

### RR-1: PyMuPDF AGPL License Forces Architecture Change Before Public Distribution

**Trigger condition:** The Orchestrator decides to distribute K-PDF publicly (open source or commercial). PyMuPDF's AGPL v3 license requires that the entire application's source code be made available under AGPL-compatible terms — or that a commercial PyMuPDF license be purchased from Artifex.

**12-month scenario:**
- If K-PDF goes open source under AGPL: no issue (but constrains the MIT-licensed Pro tier — AGPL is viral).
- If K-PDF keeps MIT license: must purchase a commercial PyMuPDF license (cost unknown, likely $X,000/year).
- If neither is acceptable: **replace PyMuPDF** with an alternative PDF engine. Options: `pikepdf` (LGPL, uses QPDF — no rendering), `pdfium` (BSD, Google's PDF engine — has rendering but Python bindings are less mature), or direct MuPDF C bindings under commercial license.

**Mitigation:**
- **Architecture decision:** The MVP pattern isolates PyMuPDF behind the service layer (`pdf_engine.py`, `annotation_engine.py`, etc.). No PyMuPDF imports outside the `services/` directory. If PyMuPDF must be replaced, only the services change. Views and presenters are unaffected.
- **This isolation is a Phase 1 architectural requirement, not a "nice to have."** Enforce it with an import linting rule: `ruff` or a custom pre-commit check that flags `import fitz` or `import pymupdf` outside `services/`.
- **Decision point:** Before Phase 4, if distribution is planned, resolve the license. Budget 2-4 weeks for a PyMuPDF replacement if the commercial license is too expensive.

---

## 5. Platform-Specific Risks

### PS-1: macOS Gatekeeper Blocking Unsigned App

**Risk:** On macOS 12+, Gatekeeper quarantines unsigned applications downloaded from the internet. Users must right-click > Open > Open Anyway, or go to System Settings > Privacy & Security > Open Anyway. The DMG itself may also be quarantined.

**Mitigation:** Document bypass instructions in release notes. Not a code fix — accepted degradation for personal use. Code signing required before public distribution.

### PS-2: Windows SmartScreen Warning

**Risk:** Similar to macOS — SmartScreen flags unsigned executables. "Windows protected your PC" warning on every new download.

**Mitigation:** Same as macOS — documented bypass. Accepted for personal use.

### PS-3: Linux AppImage Font Rendering Differences

**Risk:** Qt6 on Linux uses system fonts. Different distributions have different font configurations. The application may look different (or have missing/ugly fonts) on Ubuntu vs Fedora vs Arch.

**Mitigation:** Bundle a default font (e.g., Noto Sans, OFL licensed) with the AppImage. Set `QT_QPA_FONTDIR` to the bundled font directory at startup. Fall back to system fonts if bundled fonts fail.

### PS-4: HiDPI Scaling Differences Across Platforms

**Risk:** Qt6 handles HiDPI differently across platforms. On Windows with 125%/150% scaling, widgets may render at wrong sizes. On Linux with mixed-DPI monitors (uncommon but possible), rendering may be inconsistent.

**Mitigation:** Set `QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)` at startup. Test on 100%, 150%, and 200% scaling in CI (at least on Windows and macOS). Use layout managers (not fixed pixel positions) for all UI elements.

### PS-5: File Locking Behavior Differences (Save Operation)

**Risk:** On Windows, when K-PDF has a file open via PyMuPDF, the OS may lock the file, preventing other applications from reading it. On Unix, file locking is advisory. The save operation may also fail on Windows if another application has the file open.

**Mitigation:** On all platforms: attempt save, catch OS errors, show error dialog with Save As fallback. On Windows specifically: PyMuPDF's `Document` holds a file handle — test whether incremental save works while the document is open (it should, but verify). If not, read into memory, close the handle, write, reopen.

---

## 6. Summary — Risk Priority

| # | Risk | Severity | Likelihood | Mitigation Cost | Priority |
|---|---|---|---|---|---|
| EC-3 | Qt event loop blocked by PDF ops | High | Certain | Medium (threading from start) | **P0 — Architect in** |
| SV-1 | MuPDF code execution via crafted PDF | High | Low | Low (dependency updates) | **P0 — Process** |
| RR-1 | AGPL license blocks distribution | High | Medium | Low now (isolate PyMuPDF) | **P0 — Architect in** |
| EC-1 | Memory exhaustion multi-tab | Medium | Likely | Medium (memory monitoring) | **P1 — Build in Phase 2** |
| DB-2 | Page cache memory pressure | Medium | Likely | Medium (LRU cache) | **P1 — Build in Phase 2** |
| EC-4 | Nuitka compilation failures | Medium | Likely | Medium (CI on all platforms) | **P1 — CI from Phase 2** |
| EC-2 | Malformed annotations | Medium | Likely | Low (try/except per annotation) | **P1 — Build in Phase 2** |
| SV-2 | Path traversal | Medium | Low | Low (path canonicalization) | **P1 — Build in Phase 2** |
| SV-3 | Insecure temp files | Medium | Low | Low (tempfile best practices) | **P1 — Build in Phase 2** |
| EC-5 | JavaScript in forms | Low | Medium | Low (detection + notification) | **P2 — Build in Phase 2** |
| DB-1 | SQLite concurrent access | Low | Low | Low (lock file + WAL) | **P2 — Build in Phase 2** |
| PS-1/2 | Unsigned app warnings | Low | Certain | None (accepted) | **P3 — Document** |
| PS-3 | Linux font differences | Low | Medium | Low (bundle font) | **P2 — Build in Phase 2** |
| PS-4 | HiDPI scaling | Low | Medium | Low (Qt config) | **P2 — Build in Phase 2** |
| PS-5 | File locking on Windows | Medium | Medium | Low (error handling) | **P1 — Build in Phase 2** |

**P0 items must be addressed in the architecture (this Phase). P1 items must be built into the code during Phase 2. P2 items are addressed during feature implementation. P3 items are documentation only.**
