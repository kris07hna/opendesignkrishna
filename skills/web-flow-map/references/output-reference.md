# Whiteboard Output Reference — Web Flow Mapper

Documents the structure of the Excalidraw whiteboard (`userflow.sketch.json`)
and the `sitemap.json` output produced by every crawl run.

---

## userflow.sketch.json

Standard Excalidraw file format (version 2). Open directly in Open Design
workspace viewer, or at https://excalidraw.com via File → Open.

### Layout Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│  HEADER BANNER                                                       │
│  🗺  User Flow Map — domain.com                                      │
│  Goal: [goal text]   Pages: N   Generated: [timestamp]              │
│  Viewports: desktop, mobile                                          │
│  Legend: [Desktop] [Mobile] [Gate] [Diff]                           │
└─────────────────────────────────────────────────────────────────────┘

┌── DESKTOP ROW (y=0) ─────────────────────────────────────────────────┐
│  ┌─────────────┐  ──→  ┌─────────────┐  ──→  ┌─────────────┐        │
│  │ [screenshot]│       │ [screenshot]│       │ [screenshot]│        │
│  │ Step 1 ●   │       │  Step 2 ●  │       │  Step 3 🚧  │        │
│  │ /           │       │  /features │       │  /login     │        │
│  │ Homepage    │       │  Features  │       │  Auth Gate  │        │
│  └─────────────┘       └─────────────┘       └─────────────┘        │
└──────────────────────────────────────────────────────────────────────┘
      │ (dashed)               │ (dashed)               │ (dashed)
┌── MOBILE ROW (y=660) ────────────────────────────────────────────────┐
│  ┌──────┐  →  ┌──────┐  →  ┌──────┐                                 │
│  │[shot]│     │[shot]│     │[shot]│                                  │
│  │ M 1  │     │ M 2  │     │ M 3 🚧│                                 │
│  └──────┘     └──────┘     └──────┘                                  │
└──────────────────────────────────────────────────────────────────────┘
```

### Visual Badge System

| Badge | Color | Meaning |
|---|---|---|
| `Step N` on desktop card | 🔵 Blue `#2f81f7` | Desktop navigation step |
| `Step N` on mobile card | 🟣 Purple `#7c3aed` | Mobile navigation step |
| `🚧 Auth Gate` | 🔴 Red `#da3633` | Login/payment/CAPTCHA wall — crawl stopped |
| `⚡ diff` | 🟠 Orange `#f0883e` | Desktop and mobile screenshots are visually different |

### Arrow Colors

| Arrow | Color | Meaning |
|---|---|---|
| Solid blue horizontal | `#2f81f7` | Desktop navigation flow |
| Solid purple horizontal | `#7c3aed` | Mobile navigation flow |
| Dashed grey vertical | `#8b949e` | Desktop ↔ Mobile pairing connector |

---

## sitemap.json

Structured JSON output written alongside the whiteboard.

### Full Schema

```json
{
  "version": "2.0.0",
  "generated_at": "2024-08-03T12:00:00Z",
  "start_url": "https://example.com",
  "goal": "Map all top navigation sections",
  "viewports": ["desktop", "mobile"],
  "total_steps": 8,
  "pages": [
    {
      "step": 1,
      "name": "Homepage",
      "url": "https://example.com",
      "auth_gate": false,
      "screenshot_desktop": "screenshots_ai/desktop_step_01_initial.png",
      "screenshot_mobile": "screenshots_ai/mobile_step_01_initial.png",
      "has_responsive_diff": false
    },
    {
      "step": 2,
      "name": "Features",
      "url": "https://example.com/features",
      "auth_gate": false,
      "screenshot_desktop": "screenshots_ai/desktop_step_02_navigate.png",
      "screenshot_mobile": "screenshots_ai/mobile_step_02_navigate.png",
      "has_responsive_diff": true
    },
    {
      "step": 3,
      "name": "Authentication Gate",
      "url": "https://example.com/login",
      "auth_gate": true,
      "screenshot_desktop": "screenshots_ai/desktop_step_03_gate.png",
      "screenshot_mobile": null,
      "has_responsive_diff": false
    }
  ]
}
```

### Field Reference

| Field | Type | Description |
|---|---|---|
| `version` | string | Mapper version that produced this output |
| `generated_at` | ISO8601 | UTC timestamp of the crawl completion |
| `start_url` | string | The URL passed to `--url` |
| `goal` | string | The goal passed to `--goal` |
| `viewports` | string[] | Which viewports were captured |
| `total_steps` | number | Total pages/steps mapped |
| `pages[].step` | number | Step index (1-based) |
| `pages[].name` | string | Page label (nav link text or path) |
| `pages[].url` | string | Full URL of the page at time of screenshot |
| `pages[].auth_gate` | boolean | `true` if a login/payment/CAPTCHA wall was detected |
| `pages[].screenshot_desktop` | string \| null | Relative path to desktop screenshot |
| `pages[].screenshot_mobile` | string \| null | Relative path to mobile screenshot |
| `pages[].has_responsive_diff` | boolean | `true` if desktop and mobile screenshots differ |

---

## Reporting to User

After the script completes, report this summary from `sitemap.json`:

```markdown
## Flow Map Complete

- **Pages mapped**: N
- **Viewports**: desktop (1440px) + mobile (390px)
- **Auth gates**: N pages stopped at login/payment walls
- **Responsive diffs**: N pages have different desktop vs mobile layouts

### Pages visited:
1. Homepage — /
2. Features — /features  ⚡ responsive diff
3. Pricing — /pricing
4. Login Gate 🚧 — /login (crawl stopped here)

**Whiteboard**: `screenshots_ai/userflow.sketch.json`
```

Open the whiteboard file in Open Design workspace viewer.
