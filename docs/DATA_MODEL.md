# K-PDF — Data Model

## Version 1.0 — Phase 1, Step 1.4

---

## 1. Overview

K-PDF has two data domains:

1. **Persistent data** — User preferences and recent files. Stored in SQLite in the OS config directory. Small, low-sensitivity, schema-versioned.
2. **In-memory document state** — The open PDF documents, their rendered pages, annotations, form state, undo history. Lives entirely in RAM. Never persisted except via explicit user Save.

---

## 2. Persistent Data — SQLite Schema

**Database location:** `{config_dir}/k-pdf/settings.db`
- Windows: `%APPDATA%\K-PDF\settings.db`
- macOS: `~/Library/Application Support/K-PDF/settings.db`
- Linux: `~/.config/k-pdf/settings.db`

### 2.1 Schema Version Table

```sql
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Initial version
INSERT INTO schema_version (version) VALUES (1);
```

### 2.2 User Preferences Table

```sql
CREATE TABLE IF NOT EXISTS preferences (
    key TEXT PRIMARY KEY NOT NULL,
    value TEXT NOT NULL,       -- JSON-encoded value
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

**Default preference entries (inserted on first launch):**

| Key | Default Value | Type | Description |
|---|---|---|---|
| `default_zoom` | `"fit_width"` | string | One of: "fit_page", "fit_width", "actual_size", "50", "75", "100", "150", "200" |
| `dark_mode` | `"off"` | string | One of: "off", "dark_original", "dark_inverted" |
| `annotation_author` | `""` | string | Default author name for new annotations |
| `recent_files_max` | `20` | integer | Maximum recent files to retain |
| `nav_panel_visible` | `true` | boolean | Navigation panel open on launch |
| `nav_panel_width` | `250` | integer | Navigation panel width in pixels |
| `annotation_panel_visible` | `false` | boolean | Annotation panel open on launch |
| `window_width` | `1200` | integer | Last window width |
| `window_height` | `800` | integer | Last window height |
| `window_x` | `null` | integer or null | Last window X position (null = center) |
| `window_y` | `null` | integer or null | Last window Y position (null = center) |
| `window_maximized` | `false` | boolean | Was window maximized on close |
| `page_cache_limit` | `50` | integer | Max rendered pages per tab |
| `log_level` | `"INFO"` | string | Logging level |

### 2.3 Recent Files Table

```sql
CREATE TABLE IF NOT EXISTS recent_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT NOT NULL UNIQUE,
    last_opened_at TEXT NOT NULL DEFAULT (datetime('now')),
    page_number INTEGER DEFAULT 1,        -- Last viewed page
    zoom_level TEXT DEFAULT 'fit_width'    -- Last zoom setting
);

CREATE INDEX idx_recent_files_last_opened ON recent_files(last_opened_at DESC);
```

**Maintenance:** On each file open, upsert the entry. On display, validate `file_path` exists. Show stale entries grayed with "File not found." Trim to `recent_files_max` by deleting oldest entries.

### 2.4 Schema Migration Strategy

```python
MIGRATIONS = {
    1: "initial schema (preferences + recent_files)",
    # Future: 2: "ALTER TABLE ... ADD COLUMN ..."
}

def migrate(db: sqlite3.Connection, current_version: int, target_version: int):
    for version in range(current_version + 1, target_version + 1):
        apply_migration(db, version)
        db.execute("INSERT INTO schema_version (version) VALUES (?)", (version,))
    db.commit()
```

**Rollback:** For v1 MVP, rollback is "delete database, recreate from defaults." Schema changes in post-MVP will require proper down-migrations.

---

## 3. In-Memory Document Model

### 3.1 Entity Relationship

```
Application (singleton)
 └── TabManager
      └── Tab (1 per open document)
           ├── DocumentModel (1:1)
           │    ├── PyMuPDF Document handle
           │    ├── Metadata (page count, title, author, has_forms, has_outline)
           │    ├── Pages[] (page-level metadata, not rendered content)
           │    └── dirty flag (bool)
           ├── ViewState (1:1, per-tab)
           │    ├── current_page (int)
           │    ├── zoom_level (float)
           │    ├── view_rotation (int, 0/90/180/270)
           │    ├── scroll_position (x, y)
           │    ├── search_state (optional)
           │    └── selection_state (optional)
           ├── PageCache (1:1)
           │    └── LRU cache of rendered QPixmap objects
           ├── UndoStack (1:1)
           │    ├── undo_list[] (max 50)
           │    └── redo_list[]
           └── session_id (UUID, for log correlation)
```

### 3.2 Core Data Classes

```python
@dataclass
class DocumentMetadata:
    file_path: Path
    page_count: int
    title: str | None
    author: str | None
    has_forms: bool          # AcroForm fields detected
    has_outline: bool        # Bookmarks/outline present
    has_javascript: bool     # JavaScript actions in form fields
    is_encrypted: bool       # Was password-protected (now decrypted)
    file_size_bytes: int

@dataclass
class PageInfo:
    index: int               # 0-based page index
    width: float             # Points (1/72 inch)
    height: float            # Points
    rotation: int            # 0, 90, 180, 270 (from PDF, not view rotation)
    has_text: bool           # Text layer present
    annotation_count: int    # Number of annotations on this page

@dataclass
class AnnotationData:
    page_index: int
    annotation_type: str     # "highlight", "underline", "strikethrough", "sticky_note", "text_box"
    rect: tuple[float, float, float, float]  # (x0, y0, x1, y1) in page coordinates
    content: str             # Text content (for sticky notes, text boxes)
    author: str
    created_at: datetime
    modified_at: datetime
    color: tuple[float, float, float]  # RGB, 0.0-1.0
    # Display metadata (for accessibility)
    type_label: str          # Human-readable type name
    type_icon: str           # Icon resource name

@dataclass
class FormFieldData:
    page_index: int
    field_name: str
    field_type: str          # "text", "checkbox", "dropdown", "radio"
    value: str | bool | None
    options: list[str] | None  # For dropdown/radio
    rect: tuple[float, float, float, float]
    has_javascript: bool     # Field has JS actions
    max_length: int | None   # For text fields
    is_required: bool

@dataclass
class SearchMatch:
    page_index: int
    rect: tuple[float, float, float, float]  # Match location on page
    text: str               # Matched text

@dataclass
class UndoAction:
    description: str         # Human-readable ("Add highlight on page 3")
    do: Callable             # Function to apply the action
    undo: Callable           # Function to reverse the action
```

### 3.3 Data Flow Per Feature

| Feature | Data Source | In-Memory State | Persistence |
|---|---|---|---|
| F1: Open/Render | PDF file → PyMuPDF | DocumentModel + PageCache | None (read-only) |
| F2: Multi-Tab | Tab creation/switching | TabManager.tabs[] | Recent files updated on open |
| F3: Navigation | DocumentModel metadata | ViewState.current_page | Nav panel layout in preferences |
| F4: Search | PyMuPDF text extraction | ViewState.search_state → SearchMatch[] | None |
| F5: Zoom/Rotate | User input | ViewState.zoom_level, view_rotation | Default zoom in preferences |
| F6: Text Markup | User selection + type | AnnotationData → UndoStack | Embedded in PDF on Save |
| F7: Sticky/Text Box | User placement + text | AnnotationData → UndoStack | Embedded in PDF on Save |
| F8: AcroForm | PDF field definitions | FormFieldData[] → UndoStack | Embedded in PDF on Save |
| F9: Page Management | User actions | PageInfo[] modified → UndoStack | Written to PDF on Save |
| F10: Merge | Multiple PDF files | Temporary merge state | New PDF file on completion |
| F11: Dark Mode | User toggle | ViewState (theme) | Preference persisted |
| F12: Annotation Panel | DocumentModel annotations | AnnotationData[] (read from model) | None (reflects model state) |

---

## 4. Data Isolation & Access Control

| Concern | Control |
|---|---|
| Tab isolation | Each tab has its own DocumentModel, ViewState, PageCache, and UndoStack. No shared mutable state between tabs. |
| File system access | Only via native OS file dialogs (open/save) and explicitly user-initiated operations. No background file scanning. |
| Preferences isolation | Single SQLite database. No multi-user concern (single-user application). |
| Password handling | Never stored. Never in DocumentModel. Passed directly to PyMuPDF, cleared immediately. |
| Annotation content | In-memory only until explicit Save. No temp files for annotation state. |

---

## 5. Data Sensitivity Controls

| Data | Classification | Control |
|---|---|---|
| PDF file content | Confidential | Never logged. Never transmitted. Never cached to disk (in-memory only). |
| Form field values | Confidential (PII) | Same as PDF content. Never logged. |
| Annotation text | Confidential | Same. Never logged. |
| PDF passwords | Critical | Never stored. Never logged. Cleared from memory after decryption. Held only for duration of `fitz.open(filename, password=pw)` call. |
| File paths | Internal | Logged (for debugging). Stored in recent files. Validated before use. |
| User preferences | Internal | Stored in SQLite. No PII except file paths. |
| Log files | Internal | Rotate at 5MB, keep 3 backups. Never contain file content, form values, or passwords. |

---

## 6. Review Checklist

- [x] All entity definitions with relationships
- [x] Data isolation strategy (per-tab, no shared mutable state)
- [x] Data sensitivity controls per Data Contract
- [x] Versioned, reversible schema (SQLite with migration table)
- [x] Both "create" and "rollback" operations defined
- [x] Password handling explicitly secured
