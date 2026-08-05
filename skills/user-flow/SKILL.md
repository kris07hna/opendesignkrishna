---
name: user-flow
en_name: User Flow Generator (Legacy)
zh_name: 用户流图生成器
description: >
  Generates a visual user flow sitemap diagram for a given website URL and user goal.
  USE WHEN the user wants to map a website flow, build a sitemap, generate user flow,
  or run the user flow web agent. Redirects to the upgraded web-flow-map skill.
triggers:
  - "user-flow"
  - "user flow"
  - "generate flow"
  - "website flow"
  - "sitemap flow"
metadata:
  author: Open Design
  version: "1.1.0"
  deprecated: true
  superseded_by: web-flow-map
od:
  mode: prototype
  scenario: web-flow-map
  surface: web
  category: screenshots
  design_system:
    requires: false
---

# User Flow Generator

> **Upgraded**: This skill has been superseded by [`web-flow-map`](../web-flow-map/SKILL.md)
> which adds dual-viewport capture (desktop + mobile), nav-first crawling,
> responsive diff detection, and a professional Excalidraw whiteboard layout.
>
> Use `web-flow-map` for all new user flow mapping tasks.

---

## Execution Procedure

### 1. Verify Python Environment

```bash
python -m venv .venv
.venv/Scripts/python -m pip install playwright
.venv/Scripts/python -m playwright install chromium
```

*(On macOS/Linux use `.venv/bin/python` instead of `.venv/Scripts/python`)*

### 2. Run the Crawler

```bash
.venv/Scripts/python crawl_map_ai.py \
  --url "<targetUrl>" \
  --goal "<userGoal>" \
  --full-page \
  --output-dir screenshots_ai
```

For dual-viewport (desktop + mobile) output — the enterprise default:

```bash
.venv/Scripts/python crawl_map_ai.py \
  --url "<targetUrl>" \
  --goal "Map all top navigation sections. Dismiss all popups and banners automatically. Stop at login or payment walls." \
  --full-page \
  --output-dir screenshots_ai
```

### 3. Open the Whiteboard

The script generates `screenshots_ai/userflow.sketch.json`.
Open this file in the Open Design workspace viewer to present the interactive flow map.
