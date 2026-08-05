---
name: web-flow-map
en_name: Website Flow Mapper
zh_name: 网站流程图生成器
description: >
  Enterprise dual-viewport website flow mapper. USE WHEN the user wants to
  map a website's navigation structure, generate user flow diagrams, capture
  full-page screenshots at desktop and mobile viewports, conduct UX audits,
  competitive research, or create Excalidraw user flow whiteboards. Triggers
  on: "user flow", "map website", "website flow", "screenshot flow",
  "map navigation", "flow diagram", "UX map", "site map screenshots",
  "competitive analysis screenshots", "mobile desktop screenshots".
  Runs crawl_map_ai.py via Python venv — bypasses all popups, cookie banners,
  chat widgets, overlays; captures full-page dual-viewport screenshots;
  outputs Excalidraw whiteboard + sitemap.json.
triggers:
  - "user flow"
  - "website flow"
  - "map website"
  - "map this site"
  - "flow diagram"
  - "UX map"
  - "site map screenshots"
  - "screenshot flow"
  - "map navigation"
  - "competitive analysis"
  - "competitive screenshots"
  - "mobile desktop screenshots"
  - "navigation map"
  - "page flow"
  - "flow map"
  - "generate flow"
  - "userflow"
metadata:
  author: Open Design
  version: "2.0.0"
  use_case: >
    Enterprise website flow mapping — dual-viewport (desktop 1440px + mobile 390px),
    full-page screenshots, automatic overlay bypass, Excalidraw whiteboard output.
od:
  mode: prototype
  scenario: web-flow-map
  surface: web
  category: screenshots
  featured: 1
  preview:
    type: excalidraw
  design_system:
    requires: false
  capabilities_required:
    - file_write
    - shell
  example_prompt: >
    Map the complete website https://example.com — navigate every top navigation
    section, bypass all popups and cookie banners automatically, capture full-page
    screenshots at desktop (1440px) and mobile (390px) viewports, and output a
    dual-viewport Excalidraw user flow whiteboard with sitemap.json.
---

# Web Flow Mapper · Enterprise Website Flow Mapping

Maps any public website's navigation structure by autonomously clicking top-nav links,
bypassing all overlays, and capturing dual-viewport (desktop + mobile) full-page
screenshots. Outputs a professional Excalidraw user flow whiteboard and `sitemap.json`.

**All work is done inside the current Open Design project directory.**
Scripts are staged to `.od-skills/<skill-dir>/scripts/` at runtime.
Output screenshots and the whiteboard go to `<output-dir>/` in the project root.

---

## Iron Rule: Always run the script — never simulate it

> This skill executes `crawl_map_ai.py` via the Python virtual environment.
> Do **not** describe what the script would do without running it.
> Do **not** fabricate screenshots or whiteboard content.
> If the venv or Playwright is missing, set them up first (see Environment Setup below).

---

## Environment Setup (run once per project)

```bash
# 1. Create Python virtual environment
python -m venv .venv

# 2. Install Playwright
.venv/Scripts/python -m pip install playwright   # Windows
# OR
.venv/bin/python -m pip install playwright       # macOS / Linux

# 3. Install Chromium browser
.venv/Scripts/python -m playwright install chromium   # Windows
# OR
.venv/bin/python -m playwright install chromium       # macOS / Linux
```

> On Windows: use `.venv\Scripts\python`.  
> On macOS/Linux: use `.venv/bin/python`.  
> The script auto-detects the venv — no manual activation needed.

---

## Execution Procedure

### Step 1 — Verify environment

```bash
# Check Python venv exists
python -m venv .venv --upgrade-deps

# Verify Playwright is available
.venv/Scripts/python -c "from playwright.async_api import async_playwright; print('OK')"
```

If this fails, run the Environment Setup section above.

### Step 2 — Run the flow mapper

Choose the mode that matches the user's request:

#### 🌐 Full dual-viewport map (DEFAULT — any website)
```bash
.venv/Scripts/python crawl_map_ai.py \
  --url "TARGET_URL" \
  --goal "Map the complete website structure by clicking every top navigation link. Dismiss all popups, cookie banners, chat widgets, and overlays automatically." \
  --full-page \
  --output-dir screenshots_ai
```

#### 🖥️ Desktop only (1440×900)
```bash
.venv/Scripts/python crawl_map_ai.py \
  --url "TARGET_URL" \
  --goal "GOAL" \
  --desktop-only \
  --full-page \
  --output-dir screenshots_ai
```

#### 📱 Mobile only (390×844 iPhone)
```bash
.venv/Scripts/python crawl_map_ai.py \
  --url "TARGET_URL" \
  --goal "GOAL" \
  --mobile-only \
  --full-page \
  --output-dir screenshots_ai
```

#### ⚡ Fast mode (no AI, heuristic nav only)
```bash
.venv/Scripts/python crawl_map_ai.py \
  --url "TARGET_URL" \
  --goal "GOAL" \
  --no-ai \
  --full-page \
  --output-dir screenshots_ai
```

#### 🔍 Custom steps + model
```bash
.venv/Scripts/python crawl_map_ai.py \
  --url "TARGET_URL" \
  --goal "GOAL" \
  --max-steps 20 \
  --model "google/gemini-2.0-flash" \
  --output-dir screenshots_ai
```

### Step 3 — Open the whiteboard

Once the script completes, open the generated Excalidraw whiteboard:

```
screenshots_ai/userflow.sketch.json
```

Open this file in the Open Design workspace viewer to present the interactive flow map to the user.

Also report from `screenshots_ai/sitemap.json`:
- Total pages mapped
- List of all URLs visited
- Any auth/payment gates detected
- Pages with responsive design differences (⚡ diff)

---

## CLI Flag Reference

| Flag | Default | Description |
|---|---|---|
| `--url` | required | Target website URL |
| `--goal` | required | Navigation goal / what sections to map |
| `--full-page` | off | Capture full scrolled-page height (recommended) |
| `--desktop-only` | off | Desktop viewport only (1440×900) |
| `--mobile-only` | off | Mobile viewport only (390×844) |
| `--no-ai` | off | Disable OpenCode AI, use deterministic nav heuristic |
| `--max-steps` | 16 | Max navigation steps per viewport |
| `--model` | gemini-flash-1.5-8b | OpenCode model for AI reasoning |
| `--output-dir` | screenshots_ai | Output directory name |

---

## Goal Templates by Website Type

Use these as the `--goal` value or in the chat goal description:

### Any website (universal)
```
Map the complete website structure by clicking every top navigation link and tab.
Dismiss all popups, cookie banners, chat widgets, newsletter modals, and geo dialogs.
Capture full-page screenshots at both desktop and mobile viewports.
Stop at any login or payment wall.
```

### SaaS / Product site
```
Map the full SaaS product website: homepage, features/product pages, pricing,
integrations, documentation entry, about, and blog. Dismiss all chat widgets
(Intercom, Drift, Zendesk), cookie banners, and trial prompts automatically.
```

### E-commerce
```
Map the complete e-commerce journey: homepage, all main category navigation links,
product listing page, product detail page, and cart entry. Bypass all promotional
popups, loyalty sign-up modals, live chat, cookie consent, and location pickers.
Stop at payment or login gate.
```

### Competitive research
```
Conduct a comprehensive competitive UX audit. Navigate every top navigation
section visible without login. Prioritize: homepage hero, features, pricing,
about/team, blog/resources, contact. Document each page layout.
```

### Documentation site
```
Map documentation site structure: all top-level sections and categories in
the sidebar or top navigation. Capture section landing pages only, not
individual articles. Desktop screenshots only.
```

### Mobile-first / PWA
```
Mobile-first UX mapping at 390px iPhone viewport. Navigate all top navigation
items including hamburger menu. Dismiss mobile app download banners, push
notification prompts, location requests, and cookie dialogs.
```

### Portfolio / Creative / WebGL
```
Map creative portfolio: homepage, work/projects gallery, individual case studies,
about, services, and contact. Wait for WebGL and canvas animations to fully render.
Full-page desktop screenshots for maximum visual fidelity.
```

---

## Output Files

Every run produces these files in `<output-dir>/`:

| File | Contents |
|---|---|
| `desktop_step_01_initial.png` | Full-page desktop screenshot — step 1 |
| `desktop_step_02_navigate.png` | Full-page desktop screenshot — step 2 |
| `mobile_step_01_initial.png` | Full-page mobile screenshot — step 1 |
| `mobile_step_02_navigate.png` | Full-page mobile screenshot — step 2 |
| `userflow.sketch.json` | **Excalidraw whiteboard** — open in Open Design |
| `sitemap.json` | Structured JSON: all pages, URLs, viewport diffs, gate flags |

### `sitemap.json` structure
```json
{
  "version": "2.0.0",
  "generated_at": "2024-01-01T12:00:00Z",
  "start_url": "https://example.com",
  "goal": "Map all sections",
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
      "has_responsive_diff": true
    }
  ]
}
```

---

## Whiteboard Layout

The Excalidraw whiteboard renders a two-row layout:

```
┌─────────────────────────────────────────────────────────────┐
│  🗺  User Flow Map — domain.com  │  Goal  │  Stats  │ Legend │
└─────────────────────────────────────────────────────────────┘

┌─ DESKTOP (1440px) ─┐  →  ┌─ DESKTOP ─┐  →  ┌─ DESKTOP ─┐
│   [screenshot]     │     │ [screenshot]│     │ [screenshot]│
│   Step 1           │     │   Step 2   │     │   Step 3   │
│   /homepage        │     │  /features │     │  /pricing  │
└────────────────────┘     └────────────┘     └────────────┘
         │ (dashed)                │                 │
┌─ MOBILE (390px) ───┐  →  ┌─ MOBILE ──┐  →  ┌─ MOBILE ──┐
│   [screenshot]     │     │ [screenshot]│     │ [screenshot]│
│   Step 1           │     │   Step 2   │     │   Step 3   │
└────────────────────┘     └────────────┘     └────────────┘
```

**Badges:**
- 🔵 Blue badge = Desktop step
- 🟣 Purple badge = Mobile step
- 🔴 Red border = Auth / payment gate detected
- 🟠 `⚡ diff` = Desktop and mobile layouts are visually different

---

## What Gets Bypassed Automatically

The script's overlay engine handles:

| Category | Examples |
|---|---|
| Cookie / GDPR | OneTrust, CookieYes, Osano, custom banners |
| Chat widgets | Intercom, Drift, Zendesk, HubSpot, Crisp, Tidio, Zopim |
| Newsletter / email | Klaviyo, OptinMonster, Mailchimp popups |
| Geo / location | City selector, pincode modal, country redirect |
| App install banners | Smart App Banner, custom mobile banners |
| Login / sign-up | Optional sign-in prompts, guest CTAs |
| Bot challenges | Cloudflare, reCAPTCHA (detected + flagged, not bypassed) |
| Fixed overlays | Any fixed/absolute element >40% viewport height |

> **Hard stops**: Login walls, payment pages, and CAPTCHA challenges are
> detected and flagged with a red gate card — the crawler stops gracefully.

---

## Capability Boundaries

**This skill can map:**
- Any public website with standard HTML navigation
- Single-page apps (React, Vue, Next.js, Angular)
- Multi-page marketing sites, portals, documentation
- E-commerce sites (product discovery, not checkout)
- Design-heavy sites (waits for animations/WebGL to render)

**This skill stops at:**
- Login / authentication walls
- Payment / checkout pages
- CAPTCHA challenges
- Pages that require user account data

**This skill does NOT:**
- Clone or download site assets
- Submit forms or perform account actions
- Bypass security checks or paywalls
- Capture authenticated / behind-login pages

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `ModuleNotFoundError: playwright` | Run: `.venv/Scripts/python -m pip install playwright` |
| `Browser not found` | Run: `.venv/Scripts/python -m playwright install chromium` |
| `TimeoutError` on navigation | Add `--no-ai` flag; some sites block headless browsers |
| All screenshots are blank/white | Site uses aggressive bot detection — try `--no-ai` first |
| Script exits at step 1 | Gate detected immediately — site requires login to browse |
| `opencode: command not found` | OpenCode not installed; add `--no-ai` to use heuristic mode |
