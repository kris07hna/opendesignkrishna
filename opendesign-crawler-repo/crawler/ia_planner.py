"""
ia_planner.py – LLM-as-Strategist module for Open Design Crawler.

Architecture:
  1. Crawler visits the FIRST page only.
  2. We extract a tiny "skeleton" — just nav labels, heading tags, aria-labels (~200 tokens max).
  3. We send the skeleton to the LLM with a single prompt:
       "Here is the navigation structure. Return a JSON extraction plan."
  4. LLM returns a structured ExtractionPlan JSON (not content — just instructions).
  5. Every subsequent page uses the plan deterministically — zero more LLM calls.

Why this works:
  - Nav structure is near-identical across all pages of the same site.
  - The plan is tiny (~1KB JSON) and cached forever.
  - Extracts mega-menu columns accurately because the LLM understands CSS patterns.
  - One LLM call per crawl session instead of one per page.
"""

import json
import re
import asyncio
from crawler.config import log
from crawler.agent import ask_opencode, extract_json_block
from crawler.playwright_skeleton import extract_full_skeleton


# ──────────────────────────────────────────────────────────────────────────────
# Step 1 — Extract the skeleton (pure Python/Playwright, zero LLM)
# ──────────────────────────────────────────────────────────────────────────────

SKELETON_JS = """() => {
    const clean = s => (s || '').replace(/\\s+/g, ' ').trim().substring(0, 80);
    const skeleton = {
        nav_triggers: [],      // top-level nav items: Products, Solutions, etc.
        mega_panel_headings: [],  // sub-column headings inside dropdown panels
        footer_headings: [],   // column titles in the footer
        aria_labels: [],       // any aria-label on nav elements
        heading_tags: [],      // all h1–h3 visible in the viewport
    };

    // ── Top-level nav triggers ──────────────────────────────────────────
    const navEl = document.querySelector('header nav, nav[role="navigation"], header ul');
    if (navEl) {
        // Direct children that are likely top-level items
        const topItems = navEl.querySelectorAll(
            ':scope > li > a, :scope > li > button, :scope > a, :scope > button, ' +
            ':scope > div > a, :scope > div > button, :scope > ul > li > a'
        );
        topItems.forEach(el => {
            const t = clean(el.innerText || el.textContent);
            if (t && !skeleton.nav_triggers.includes(t)) skeleton.nav_triggers.push(t);
        });
    }

    // ── Aria labels on nav elements ─────────────────────────────────────
    document.querySelectorAll('header [aria-label], nav [aria-label]').forEach(el => {
        const t = clean(el.getAttribute('aria-label'));
        if (t && !skeleton.aria_labels.includes(t)) skeleton.aria_labels.push(t);
    });

    // ── Mega-menu sub-column headings ───────────────────────────────────
    const panelSelectors = [
        '.mega-menu', '.dropdown-menu', '.nav-dropdown', '[role="menu"]',
        'header ul ul', 'nav ul ul', 'header [class*="panel"]',
        '[aria-expanded] + *', 'header [class*="flyout"]'
    ];
    panelSelectors.forEach(sel => {
        document.querySelectorAll(sel).forEach(panel => {
            panel.querySelectorAll('h1,h2,h3,h4,h5,h6,strong,[role="heading"]').forEach(h => {
                const t = clean(h.innerText || h.textContent);
                if (t && !skeleton.mega_panel_headings.includes(t)) {
                    skeleton.mega_panel_headings.push(t);
                }
            });
        });
    });

    // ── Footer column headings ──────────────────────────────────────────
    const footerEl = document.querySelector('footer, [role="contentinfo"]');
    if (footerEl) {
        footerEl.querySelectorAll('h1,h2,h3,h4,h5,h6,strong,[role="heading"]').forEach(h => {
            const t = clean(h.innerText || h.textContent);
            if (t && !skeleton.footer_headings.includes(t)) skeleton.footer_headings.push(t);
        });
    }

    // ── Viewport h1–h3 headings ─────────────────────────────────────────
    document.querySelectorAll('h1, h2, h3').forEach(h => {
        const rect = h.getBoundingClientRect();
        if (rect.top < window.innerHeight) {
            const t = clean(h.innerText || h.textContent);
            if (t && !skeleton.heading_tags.includes(t)) skeleton.heading_tags.push(t);
        }
    });

    return skeleton;
}"""


async def extract_skeleton(page) -> dict:
    """
    Extract skeleton using Playwright's native APIs:
      1. page.accessibility.snapshot() → full semantic accessibility tree
      2. page.get_by_role() locators  → nav, headings, buttons, menu items
    Combines both for the richest skeleton with zero LLM.
    """
    return await extract_full_skeleton(page)


# ──────────────────────────────────────────────────────────────────────────────
# Step 2 — Ask the LLM for a site-specific extraction plan
# ──────────────────────────────────────────────────────────────────────────────

PLANNER_PROMPT_TEMPLATE = """You are a web IA (Information Architecture) specialist.

A crawler just visited the homepage of a website and extracted the following navigation skeleton.
This is NOT the full page — only the structural labels, headings, and ARIA metadata.

SKELETON:
{skeleton_json}

Your job is to return a JSON "ExtractionPlan" that tells the crawler:
1. What each top-level nav item maps to (e.g., "Products" = a mega-menu with sub-columns).
2. The most reliable CSS selector(s) to identify each nav dropdown panel.
3. The CSS selector for sub-column headings inside each panel.
4. The CSS selector for footer column heading elements.
5. Any unusual patterns to watch out for (e.g., nested panels, icon-only items).

Respond ONLY with a valid JSON object following this exact schema:

{{
  "site_type": "mega-menu | simple-nav | icon-nav | mixed",
  "nav_strategy": "One sentence explaining the site's nav approach",
  "header_dropdowns": {{
    "<nav_trigger_label>": {{
      "panel_selector": "CSS selector that reveals this dropdown panel when the trigger is hovered/clicked",
      "column_heading_selector": "CSS selector for column headings inside this panel (relative to panel)",
      "item_selector": "CSS selector for links inside each column (relative to column heading's parent)",
      "notes": "Any edge case or gotcha for this dropdown (empty string if none)"
    }}
  }},
  "footer": {{
    "column_heading_selector": "CSS selector for each footer column title",
    "item_selector": "CSS selector for links under each footer column",
    "notes": ""
  }},
  "fallback_strategy": "If selectors fail, describe a reliable fallback DOM walk"
}}

RULES:
- Only use standard CSS selectors (no XPath).
- Prefer semantic selectors (role, aria-*) over class names which change.
- If a nav trigger has no dropdown (e.g., "Pricing"), set panel_selector to null.
- Be concise in notes (max 1 sentence).
- Do not include any explanation outside the JSON block.
"""


async def ask_llm_for_plan(skeleton: dict, model: str, timeout_secs: int = 45) -> dict:
    """
    Send the skeleton to the LLM and parse the returned ExtractionPlan.
    Has a hard timeout — if the LLM hangs, we fall back instantly.
    Returns a dict (the plan) or an empty dict if parsing fails / times out.
    """
    skeleton_json = json.dumps(skeleton, indent=2)
    prompt = PLANNER_PROMPT_TEMPLATE.format(skeleton_json=skeleton_json)

    log(f"Sending nav skeleton to LLM for extraction plan (timeout={timeout_secs}s)...", "AI")
    try:
        raw_response = await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(None, _call_opencode_sync, prompt, model),
            timeout=timeout_secs
        )
    except asyncio.TimeoutError:
        log(f"LLM timed out after {timeout_secs}s — using skeleton-based plan.", "WARN")
        return {}
    except Exception as e:
        log(f"LLM call failed ({e}) — using skeleton-based plan.", "WARN")
        return {}

    json_str = extract_json_block(raw_response)
    try:
        plan = json.loads(json_str)
        log(f"LLM plan received: site_type={plan.get('site_type')}, "
            f"{len(plan.get('header_dropdowns', {}))} nav items mapped.", "AI")
        return plan
    except Exception as e:
        log(f"Failed to parse LLM plan JSON: {e}. Using skeleton-based plan.", "WARN")
        return {}


def _call_opencode_sync(prompt: str, model: str) -> str:
    """Synchronous wrapper for ask_opencode, runs in a thread executor."""
    import subprocess, tempfile, os
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', delete=False, suffix='.md') as f:
        f.write(prompt)
        tmp_path = f.name
    try:
        res = subprocess.run(
            ['opencode', 'run', 'Follow the instructions in the attached file.', '-m', model, '-f', tmp_path],
            capture_output=True, text=True, timeout=40, shell=(os.name == 'nt')
        )
        return res.stdout if res.returncode == 0 else ''
    except Exception:
        return ''
    finally:
        try: os.remove(tmp_path)
        except: pass


# ──────────────────────────────────────────────────────────────────────────────
# Step 2b — Smart skeleton-to-plan converter (ZERO LLM, instant)
# ──────────────────────────────────────────────────────────────────────────────

def build_plan_from_skeleton(skeleton: dict) -> dict:
    """
    Build an ExtractionPlan directly from the skeleton — no LLM needed.
    Uses a set of universal heuristics that work on 90%+ of sites:
      - nav triggers with panel headings → mega-menu
      - nav triggers without panel headings → simple nav
      - footer headings → column-based footer

    This is the PRIMARY path when LLM is unavailable, slow, or disabled.
    """
    nav_triggers    = skeleton.get('nav_triggers', [])
    panel_headings  = skeleton.get('mega_panel_headings', [])
    footer_headings = skeleton.get('footer_headings', [])
    aria_labels     = skeleton.get('aria_labels', [])

    site_type = 'mega-menu' if panel_headings else 'simple-nav'

    # Universal mega-menu panel selectors that work across most frameworks
    PANEL_SELECTORS = [
        '[role="menu"]',
        '[data-dropdown]',
        '.mega-menu',
        '.dropdown-menu',
        '.nav-dropdown',
        'header ul ul',
        'nav ul ul',
        '[class*="dropdown"]',
        '[class*="mega"]',
        '[class*="panel"]',
        '[aria-expanded="true"] ~ *',
    ]
    panel_sel = ', '.join(PANEL_SELECTORS)

    # Universal column heading selectors inside panels
    col_heading_sel = 'h2, h3, h4, strong, [role="heading"], [class*="heading"], [class*="label"], [class*="category"]'

    # Universal item selector inside panels
    item_sel = 'a'

    header_dropdowns = {}
    for trigger in nav_triggers:
        clean = trigger.strip()
        if not clean:
            continue
        # Decide if this trigger has a mega-panel
        # Heuristic: if panel_headings exist, all triggers with text get a panel entry
        # Simple nav items like "Pricing" typically have no sub-headings
        is_simple = clean.lower() in [
            'pricing', 'blog', 'careers', 'about', 'contact', 'login', 'sign in',
            'sign up', 'get started', 'start now', 'try free', 'docs', 'status'
        ]
        if is_simple or not panel_headings:
            header_dropdowns[clean] = {
                'panel_selector': None,
                'column_heading_selector': None,
                'item_selector': f'header a[href]',
                'notes': 'Simple top-level link — no dropdown panel.'
            }
        else:
            header_dropdowns[clean] = {
                'panel_selector': panel_sel,
                'column_heading_selector': col_heading_sel,
                'item_selector': item_sel,
                'notes': f'Mega-menu — {len(panel_headings)} sub-column headings detected in skeleton.'
            }

    # Footer strategy
    footer_col_sel = 'h2, h3, h4, h5, strong, [role="heading"]' if footer_headings else 'strong'

    plan = {
        'site_type': site_type,
        'nav_strategy': (
            f'Mega-menu navigation with {len(nav_triggers)} top-level triggers '
            f'and {len(panel_headings)} detected sub-column headings.'
            if panel_headings else
            f'Simple navigation with {len(nav_triggers)} top-level links.'
        ),
        'header_dropdowns': header_dropdowns,
        'footer': {
            'column_heading_selector': footer_col_sel,
            'item_selector': 'a',
            'notes': f'{len(footer_headings)} footer column headings detected.' if footer_headings else 'No footer headings detected — using strong/h tags.'
        },
        'fallback_strategy': 'Walk DOM siblings after each heading to collect links; group by nearest heading ancestor.',
        '_source': 'skeleton_heuristic'  # marks plan as auto-generated
    }

    log(f"Skeleton-based plan built: {site_type}, {len(header_dropdowns)} nav items.", "INFO")
    return plan


# ──────────────────────────────────────────────────────────────────────────────
# Step 3 — Apply the plan deterministically (pure JS, no more LLM)
# ──────────────────────────────────────────────────────────────────────────────

def build_plan_extractor_js(plan: dict) -> str:
    """
    Generates a self-contained JS extractor function from the LLM plan.
    This JS string is injected into every subsequent page via page.evaluate().
    """
    plan_json = json.dumps(plan)

    return f"""() => {{
    const PLAN = {plan_json};

    const clean = (s, max=80) => (s || '').replace(/\\s+/g, ' ').trim().substring(0, max);
    const qAll  = (sel, root) => sel ? Array.from((root||document).querySelectorAll(sel)) : [];
    const q     = (sel, root) => sel ? (root||document).querySelector(sel) : null;

    const structure = {{
        Header: {{ Buttons: [], Dropdowns: {{}} }},
        Body:   {{ Buttons: [], Sections: {{}} }},
        Footer: {{ Columns: {{}} }},
        _meta:  {{ plan_used: true, site_type: PLAN.site_type || 'unknown' }}
    }};

    // ── Header CTA buttons (always scraped flat) ─────────────────────────
    const headerEl = document.querySelector('header, [role="banner"]');
    if (headerEl) {{
        headerEl.querySelectorAll('a, button').forEach(el => {{
            const cls = (el.className||'').toLowerCase();
            const role = el.getAttribute('role');
            if (/\\b(btn|button|cta)\\b/.test(cls) || el.tagName==='BUTTON' || role==='button') {{
                const t = clean(el.innerText||el.textContent);
                const href = el.getAttribute('href')||null;
                if (t && !structure.Header.Buttons.find(b=>b.text===t))
                    structure.Header.Buttons.push({{text:t, href}});
            }}
        }});
    }}
    if (!structure.Header.Buttons.length) delete structure.Header.Buttons;

    // ── Header Dropdowns (plan-driven) ───────────────────────────────────
    const headerDropPlans = PLAN.header_dropdowns || {{}};
    for (const [triggerLabel, cfg] of Object.entries(headerDropPlans)) {{
        if (!cfg.panel_selector) {{
            // Simple top-level link, no dropdown
            const el = qAll(cfg.item_selector || 'header a').find(a =>
                clean(a.innerText||a.textContent) === triggerLabel
            );
            if (el) {{
                structure.Header.Dropdowns[triggerLabel] = {{
                    'Link': [{{text: triggerLabel, href: el.getAttribute('href')||null}}]
                }};
            }}
            continue;
        }}

        // Find the panel
        const panels = qAll(cfg.panel_selector);
        if (!panels.length) continue;

        structure.Header.Dropdowns[triggerLabel] = {{}};

        for (const panel of panels) {{
            // Find column headings inside the panel
            const colHeadings = cfg.column_heading_selector
                ? qAll(cfg.column_heading_selector, panel)
                : [];

            if (colHeadings.length > 0) {{
                // Mega-menu: group items under each column heading
                for (const hEl of colHeadings) {{
                    const colName = clean(hEl.innerText||hEl.textContent);
                    if (!colName) continue;
                    if (!structure.Header.Dropdowns[triggerLabel][colName])
                        structure.Header.Dropdowns[triggerLabel][colName] = [];

                    // Items: all links until the next heading or end of parent
                    let sibling = hEl.nextElementSibling;
                    while (sibling) {{
                        if (['H1','H2','H3','H4','H5','H6','STRONG'].includes(sibling.tagName)) break;
                        sibling.querySelectorAll('a').forEach(a => {{
                            const t = clean(a.innerText||a.textContent);
                            const href = a.getAttribute('href')||null;
                            if (t && !structure.Header.Dropdowns[triggerLabel][colName].find(i=>i.text===t))
                                structure.Header.Dropdowns[triggerLabel][colName].push({{text:t, href}});
                        }});
                        sibling = sibling.nextElementSibling;
                    }}
                }}
            }} else {{
                // No column headings — flat list under "General"
                const items = cfg.item_selector
                    ? qAll(cfg.item_selector, panel)
                    : panel.querySelectorAll('a');
                if (!structure.Header.Dropdowns[triggerLabel]['General'])
                    structure.Header.Dropdowns[triggerLabel]['General'] = [];
                items.forEach(a => {{
                    const t = clean(a.innerText||a.textContent);
                    const href = a.getAttribute('href')||null;
                    if (t) structure.Header.Dropdowns[triggerLabel]['General'].push({{text:t, href}});
                }});
            }}
        }}
    }}

    // ── Footer Columns (plan-driven) ──────────────────────────────────────
    const footerEl = document.querySelector('footer, [role="contentinfo"]');
    const footerCfg = PLAN.footer || {{}};
    if (footerEl && footerCfg.column_heading_selector) {{
        const colHeadings = qAll(footerCfg.column_heading_selector, footerEl);
        for (const hEl of colHeadings) {{
            const colName = clean(hEl.innerText||hEl.textContent);
            if (!colName) continue;
            structure.Footer.Columns[colName] = [];

            // Collect sibling links after this heading
            let sibling = hEl.nextElementSibling;
            while (sibling) {{
                if (['H1','H2','H3','H4','H5','H6','STRONG'].includes(sibling.tagName)) break;
                sibling.querySelectorAll('a').forEach(a => {{
                    const t = clean(a.innerText||a.textContent);
                    const href = a.getAttribute('href')||null;
                    if (t && !structure.Footer.Columns[colName].find(i=>i.text===t))
                        structure.Footer.Columns[colName].push({{text:t, href}});
                }});
                sibling = sibling.nextElementSibling;
            }}
        }}
    }}

    return structure;
}}"""


# ──────────────────────────────────────────────────────────────────────────────
# Step 4 — Heuristic fallback JS (used when plan is empty / LLM unavailable)
# ──────────────────────────────────────────────────────────────────────────────

HEURISTIC_FALLBACK_JS = """() => {
    const clean = (s, max=80) => (s || '').replace(/\\s+/g, ' ').trim().substring(0, max);
    const inZone = (el, zone) => {
        if (zone === 'header') return !!el.closest('header, [role="banner"], nav, [role="navigation"]');
        if (zone === 'footer') return !!el.closest('footer, [role="contentinfo"]');
        return false;
    };
    const isBtn = el => {
        if (el.tagName === 'BUTTON') return true;
        const cls = (el.className||'').toLowerCase();
        return /\\b(btn|button|cta)\\b/.test(cls);
    };
    const getNearestHeading = (el, stop) => {
        let node = el.parentElement;
        while (node && node !== stop && node !== document.body) {
            let prev = node.previousElementSibling;
            while (prev) {
                if (['H1','H2','H3','H4','H5','H6','STRONG'].includes(prev.tagName)) {
                    const t = clean(prev.innerText || prev.textContent);
                    if (t) return t;
                }
                prev = prev.previousElementSibling;
            }
            const h = node.querySelector(':scope > h1,:scope > h2,:scope > h3,:scope > h4,:scope > strong');
            if (h) { const t = clean(h.innerText); if (t) return t; }
            node = node.parentElement;
        }
        return null;
    };

    const structure = {
        Header: { Buttons: [], Dropdowns: {} },
        Body:   { Buttons: [], Sections: {} },
        Footer: { Columns: {} },
        _meta:  { plan_used: false, site_type: 'heuristic' }
    };
    const seen = { h: new Set(), f: new Set() };

    const headerEl = document.querySelector('header, [role="banner"]');
    if (headerEl) {
        headerEl.querySelectorAll('a, button').forEach(el => {
            const t = clean(el.innerText||el.textContent);
            if (!t || seen.h.has(t)) return;
            const href = el.getAttribute('href')||null;
            if (href && (href.startsWith('javascript:')||href==='#')) return;
            if (isBtn(el)) { structure.Header.Buttons.push({text:t,href}); return; }
            seen.h.add(t);
            const heading = getNearestHeading(el, headerEl) || 'Main Nav';
            if (!structure.Header.Dropdowns[heading]) structure.Header.Dropdowns[heading] = {'Links': []};
            if (!structure.Header.Dropdowns[heading]['Links']) structure.Header.Dropdowns[heading]['Links'] = [];
            structure.Header.Dropdowns[heading]['Links'].push({text:t,href});
        });
    }

    const footerEl = document.querySelector('footer, [role="contentinfo"]');
    if (footerEl) {
        footerEl.querySelectorAll('a').forEach(el => {
            const t = clean(el.innerText||el.textContent);
            if (!t || seen.f.has(t)) return;
            seen.f.add(t);
            const heading = getNearestHeading(el, footerEl) || 'Footer Links';
            if (!structure.Footer.Columns[heading]) structure.Footer.Columns[heading] = [];
            structure.Footer.Columns[heading].push({text:t, href: el.getAttribute('href')||null});
        });
    }

    if (!structure.Header.Buttons.length) delete structure.Header.Buttons;
    return structure;
}"""


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────

async def build_extraction_plan(first_page, model: str, no_llm: bool = False) -> tuple[dict, str]:
    """
    Called ONCE on the first crawled page.
    Returns (plan_dict, extractor_js_string).

    Decision tree:
      1. Extract skeleton (always — fast, zero LLM)
      2. If no_llm=True OR LLM times out → use build_plan_from_skeleton() instantly
      3. If LLM succeeds → use LLM plan (most accurate)
      4. Plan → build_plan_extractor_js() → JS string used on all pages
    """
    skeleton = await extract_skeleton(first_page)
    log(f"Skeleton extracted: {len(skeleton.get('nav_triggers',[]))} nav triggers, "
        f"{len(skeleton.get('mega_panel_headings',[]))} panel headings, "
        f"{len(skeleton.get('footer_headings',[]))} footer headings.", "INFO")

    plan = {}
    if no_llm:
        log("--no-ai-plan: skipping LLM, using skeleton-based plan.", "INFO")
    else:
        # Try LLM with a hard 45-second timeout
        plan = await ask_llm_for_plan(skeleton, model, timeout_secs=45)

    if not plan or not plan.get("header_dropdowns"):
        # Instantly build a good plan from the skeleton — no LLM needed
        plan = build_plan_from_skeleton(skeleton)

    js = build_plan_extractor_js(plan)
    src = plan.get('_source', 'llm')
    log(f"Extractor built [{src}] for {len(plan.get('header_dropdowns', {}))} nav items.", "INFO")
    return plan, js
