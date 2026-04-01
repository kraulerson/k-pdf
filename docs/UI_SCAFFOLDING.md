# K-PDF — UI & UX Scaffolding

## Version 1.0 — Phase 1, Step 1.5

---

## 1. Main Window Layout

```
┌──────────────────────────────────────────────────────────────────┐
│ Menu Bar                                                         │
│ [File] [Edit] [View] [Tools] [Help]                              │
├──────────────────────────────────────────────────────────────────┤
│ Toolbar                                                          │
│ [Open] [Save] [Print] | [Zoom: ─●── 100% ▾] | [Highlight ▾]    │
│                        | [◀ Prev] [▶ Next]   | [Sticky Note]    │
│                        |                      | [Text Box]       │
├────────────┬─────────────────────────────────┬───────────────────┤
│ Navigation │                                 │ Annotation        │
│ Panel      │     PDF Viewport                │ Panel             │
│ (Left)     │     (Center)                    │ (Right)           │
│            │                                 │                   │
│ [Thumbs]   │  ┌─────────────────────────┐    │ Page | Type | ... │
│ [Outline]  │  │                         │    │ ─────┼──────┼──── │
│            │  │    Rendered PDF Page     │    │   1  │ Note │ ... │
│ ┌────────┐ │  │                         │    │   3  │ High │ ... │
│ │ pg 1   │ │  │                         │    │   5  │ Under│ ... │
│ ├────────┤ │  │                         │    │                   │
│ │ pg 2   │ │  └─────────────────────────┘    │                   │
│ │ [sel]  │ │                                 │                   │
│ ├────────┤ │                                 │                   │
│ │ pg 3   │ │                                 │                   │
│ └────────┘ │                                 │                   │
├────────────┴─────────────────────────────────┴───────────────────┤
│ Status Bar                                                       │
│ Page 2 of 45 │ 100% │ Dark Mode: Off │ Saved                    │
├──────────────────────────────────────────────────────────────────┤
│ Tab Bar (below status bar or above viewport — TBD in Phase 2)    │
│ [document1.pdf ×] [document2.pdf * ×] [+]                        │
└──────────────────────────────────────────────────────────────────┘
```

### Layout Principles

1. **Resizable panels.** Navigation and Annotation panels have drag handles. User can collapse either panel entirely.
2. **Tab bar position:** Above the viewport (below toolbar), consistent with browser/editor conventions.
3. **Status bar is always visible.** Shows: page number/count, zoom level, mode indicator (text), save status.
4. **All toolbar buttons are labeled.** Icon + text, or text-only with tooltip. Never icon-only.
5. **Menu bar follows platform conventions.** macOS: app menu under "K-PDF". Windows/Linux: File/Edit/View/Tools/Help.

---

## 2. Key Component Specifications

### 2.1 PDF Viewport (Most Important Component)

**Widget type:** Custom QWidget with QPainter rendering (or QGraphicsView for pan/zoom).

**States:**

| State | What User Sees | Trigger |
|---|---|---|
| **Empty** | Welcome screen: app name, version, "Open File" button (text + icon), recent files list, keyboard shortcut reference link. Centered in viewport. | Application launch with no file argument. Last tab closed. |
| **Loading** | Progress bar centered in viewport: "Loading [filename]... [X]%". Cancel button below. Gray background. | File open initiated, parsing in progress. |
| **Error** | Error message centered in viewport: icon (⚠) + "Cannot open [filename]" + reason text + "Open Another File" button. | File validation or parse failure. |
| **Success (Rendering)** | Rendered PDF page(s) in scrollable viewport. Scroll bar on right. Current page number in status bar. | File successfully parsed. |
| **Page Error** | Individual page shows gray placeholder with page number text + "Render error" label. Other pages render normally. | Single page render failure. |
| **Search Active** | Search bar at top of viewport. Match highlights overlaid on pages. | Ctrl+F activated. |

**Interactions:**
- Scroll: mouse wheel (vertical), horizontal scroll bar or Shift+wheel (horizontal)
- Zoom: Ctrl+wheel, pinch (macOS trackpad), toolbar slider
- Pan: click-drag when no text selection tool is active
- Text select: click-drag when text selection tool is active
- Annotation placement: click when annotation tool is active

### 2.2 Tab Bar

**Widget type:** QTabBar (custom-styled) or custom QWidget.

**States:**

| State | What User Sees |
|---|---|
| **No tabs** | Tab bar hidden. Viewport shows Empty state. |
| **Single tab** | Tab bar visible with one tab. Tab shows filename (truncated with "..." if >30 chars). Close button (×) on tab. |
| **Multiple tabs** | Tab bar shows all tabs. Active tab has underline/border indicator (not color-only). Modified tabs show `*` prefix in title. |
| **Tab overflow** | Scroll arrows appear at tab bar edges when tabs exceed bar width. |

**Tab title format:** `[*] filename.pdf` where `*` appears only if the document has unsaved changes.

**Accessibility:**
- Active tab indicated by underline/border thickness, NOT color change alone.
- Modified state indicated by `*` text prefix, NOT color change alone.
- Keyboard: Ctrl+Tab / Ctrl+Shift+Tab to cycle tabs. Ctrl+W to close current tab.

---

## 3. Menu Structure

```
File
├── Open                    Ctrl+O
├── Open Recent            ▶ [submenu: recent files list]
├── Save                    Ctrl+S
├── Save As...              Ctrl+Shift+S
├── ─────────────
├── Print...                Ctrl+P
├── ─────────────
├── Merge Documents...
├── ─────────────
├── Close Tab               Ctrl+W
└── Quit                    Ctrl+Q / Cmd+Q

Edit
├── Undo                    Ctrl+Z
├── Redo                    Ctrl+Shift+Z
├── ─────────────
├── Copy                    Ctrl+C
├── Select All              Ctrl+A
├── ─────────────
├── Find...                 Ctrl+F
├── ─────────────
└── Preferences...          (Windows/Linux) / Settings... (macOS)

View
├── Zoom In                 Ctrl+=
├── Zoom Out                Ctrl+-
├── Reset Zoom              Ctrl+0
├── ─────────────
├── Fit Page
├── Fit Width
├── Actual Size (100%)
├── ─────────────
├── Rotate View Clockwise       Ctrl+R
├── Rotate View Counter-CW      Ctrl+Shift+R
├── ─────────────
├── Navigation Panel        F5
├── Annotation Panel        F6
├── ─────────────
├── Dark Mode              ▶
│   ├── Off
│   ├── Dark UI / Original PDF
│   └── Dark UI / Inverted PDF
└── ─────────────

Tools
├── Highlight               (text markup tools)
├── Underline
├── Strikethrough
├── ─────────────
├── Sticky Note
├── Text Box
├── ─────────────
└── Page Management         F7

Help
├── Keyboard Shortcuts      F1
├── About K-PDF
└── ─────────────
```

---

## 4. Keyboard Shortcut Map

| Action | Windows/Linux | macOS |
|---|---|---|
| Open File | Ctrl+O | Cmd+O |
| Save | Ctrl+S | Cmd+S |
| Save As | Ctrl+Shift+S | Cmd+Shift+S |
| Print | Ctrl+P | Cmd+P |
| Close Tab | Ctrl+W | Cmd+W |
| Quit | Ctrl+Q | Cmd+Q |
| Undo | Ctrl+Z | Cmd+Z |
| Redo | Ctrl+Shift+Z | Cmd+Shift+Z |
| Copy | Ctrl+C | Cmd+C |
| Select All | Ctrl+A | Cmd+A |
| Find | Ctrl+F | Cmd+F |
| Find Next | Enter / F3 | Enter / Cmd+G |
| Find Previous | Shift+Enter / Shift+F3 | Shift+Enter / Cmd+Shift+G |
| Zoom In | Ctrl+= | Cmd+= |
| Zoom Out | Ctrl+- | Cmd+- |
| Reset Zoom | Ctrl+0 | Cmd+0 |
| Rotate View CW | Ctrl+R | Cmd+R |
| Rotate View CCW | Ctrl+Shift+R | Cmd+Shift+R |
| Go to Page | Ctrl+G | Cmd+Option+G |
| Next Tab | Ctrl+Tab | Ctrl+Tab |
| Previous Tab | Ctrl+Shift+Tab | Ctrl+Shift+Tab |
| Toggle Nav Panel | F5 | F5 |
| Toggle Annotation Panel | F6 | F6 |
| Toggle Page Management | F7 | F7 |
| Dark Mode Toggle | Ctrl+D | Cmd+D |
| Page Down | Page Down | Page Down |
| Page Up | Page Up | Page Up |
| First Page | Home | Home / Cmd+Up |
| Last Page | End | End / Cmd+Down |

---

## 5. Theme System

### 5.1 Light Theme (Default)

```
Background:       #FFFFFF
Surface:          #F5F5F5
Panel background: #FAFAFA
Text primary:     #212121
Text secondary:   #757575
Border:           #E0E0E0
Accent:           #1976D2
Error:            #D32F2F
Warning:          #F57C00
Success:          #388E3C
Focus indicator:  2px solid #1976D2 (visible border, not color-only)
Active tab:       2px bottom border #1976D2 + bold text
```

### 5.2 Dark Theme

```
Background:       #121212
Surface:          #1E1E1E
Panel background: #252525
Text primary:     #E0E0E0
Text secondary:   #9E9E9E
Border:           #333333
Accent:           #90CAF9
Error:            #EF5350
Warning:          #FFB74D
Success:          #81C784
Focus indicator:  2px solid #90CAF9
Active tab:       2px bottom border #90CAF9 + bold text
```

### 5.3 Accessibility Verification

Both themes MUST pass:
- All text meets WCAG AA contrast ratio (4.5:1 for normal text, 3:1 for large text)
- Interactive elements have visible focus indicators (border/outline, not color-only)
- State changes (active, disabled, error) use shape/position/text, not color alone
- Annotation types distinguishable by icon + text label in both themes

---

## 6. Component State Matrix

Every interactive component must handle all applicable states:

| Component | Empty | Loading | Error | Success | Disabled |
|---|---|---|---|---|---|
| PDF Viewport | Welcome screen | Progress bar | Error message | Rendered pages | — |
| Tab Bar | Hidden | — | — | Tabs visible | — |
| Navigation Panel | "Open a document" | Thumbnail generation progress | Thumbnail error placeholders | Thumbnails + outline | — |
| Annotation Panel | "No annotations" | — | — | Annotation list | — |
| Search Bar | Placeholder text | "Searching..." | "No matches" / "No text layer" | Match counter + highlights | — |
| Form Fields | — | — | Validation error (text + icon) | Active input | Read-only indicator |
| Page Management | "Open a document" | Operation progress | Delete-all blocked | Page grid | — |
| Merge Queue | "Select files" | "Merging [X/N]..." | Per-file errors listed | "Merge complete" | Merge button disabled (<2 files) |
| Preferences Dialog | Defaults loaded | — | — | Current values shown | — |

---

## 7. Accessibility Baseline

### 7.1 Non-Negotiable Rules

1. **Never rely on color alone.** Every state, type, indicator, and distinction must use at least one non-color differentiator: shape, position, text label, pattern, icon, or border.
2. **All interactive elements have text labels or tooltips.** No icon-only buttons without a text alternative.
3. **Keyboard navigation for all core flows.** Tab order follows visual layout. Focus indicator is always visible. Escape closes dialogs/popups.
4. **WCAG AA contrast in both light and dark themes.**

### 7.2 Annotation Type Differentiation

| Annotation Type | Icon | Text Label | On-Page Appearance |
|---|---|---|---|
| Highlight | 🖍 (marker icon) | "Highlight" | Filled background behind text |
| Underline | U̲ (underlined U icon) | "Underline" | Line below text |
| Strikethrough | S̶ (struck-through S icon) | "Strikethrough" | Line through text |
| Sticky Note | 📝 (note icon) | "Sticky Note" | Note icon at position |
| Text Box | ☐ (box icon) | "Text Box" | Bordered rectangle with text |

Each type is distinguishable by **shape/position** on the page and by **icon + text label** in the annotation panel. Color is supplementary, never primary.

### 7.3 State Indicators

| State | Non-Color Indicator |
|---|---|
| Active tab | Bottom border (2px) + bold text |
| Modified document | `*` prefix in tab title |
| Error | ⚠ icon + text message |
| Warning | ⚠ icon + text message |
| Success | ✓ icon + text message |
| Disabled control | Reduced opacity + text "(disabled)" or crossed-out appearance |
| Selected (in list) | Bold text + left border or background pattern |
| Focus | 2px solid border |
| Search match (current) | Double border/thick outline |
| Search match (other) | Single border/thin outline |

---

## 8. Review Checklist

- [x] Layout structure for main window defined
- [x] 2 most important component skeletons specified (PDF Viewport, Tab Bar)
- [x] All interactive component states defined: Empty, Loading, Error, Success
- [x] Accessibility baseline: all elements have text labels, never color-only
- [x] Keyboard shortcut map complete with no conflicts
- [x] Theme system covers both light and dark modes
- [x] Platform conventions followed (macOS app menu, keyboard shortcuts)
