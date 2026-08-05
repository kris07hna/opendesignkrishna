"""
hybrid_extractor.py – Hybrid Playwright + LLM IA extractor.

Architecture:
─────────────────────────────────────────────────────────────────────
  PLAYWRIGHT (what it sees — certain, instant)
    │
    ├─ aria_snapshot()        → confirmed nav items, headings, buttons
    ├─ get_by_role("link")    → all nav links grouped by nav landmark
    ├─ locator(footer hdr)    → footer column names
    └─ get_by_role("heading") → page headings for body sections
    │
    ▼
  PRE-STRUCTURED DATA (not raw HTML — already organised)
    {
      confirmed_nav_items: ["Products", "Solutions", "Developers"],
      confirmed_panels:    { detected: true, headings: ["By stage", ...] },
      confirmed_footer:    ["Company", "Products", "Legal"],
      confirmed_buttons:   ["Start now", "Contact sales"],
    }
    │
    ▼  (sent to LLM — ~300 tokens vs 5000 for full HTML)
  LLM INTERPRETS only the AMBIGUOUS mapping:
    "Products" panel_selector: "[data-nav='products']"
    "Solutions" column_heading: "h3.nav-col-title"
    │
    ▼  (fallback if LLM times out)
  SKELETON HEURISTIC (no LLM — universal CSS selectors)
    │
    ▼
  HYBRID EXTRACTOR (used on EVERY page):
    ├─ Playwright locators for confirmed nav/footer items
    └─ Plan-driven JS for mega-menu panel column contents
─────────────────────────────────────────────────────────────────────
"""

import asyncio
import json
from playwright.async_api import Page
from crawler.config import log
from crawler.playwright_skeleton import extract_full_skeleton
from crawler.agent import extract_json_block


# ─────────────────────────────────────────────────────────────────────────────
# Phase 1A — Playwright extracts CONFIRMED structure (zero LLM, zero JS blobs)
# ─────────────────────────────────────────────────────────────────────────────

async def playwright_confirmed_extraction(page: Page) -> dict:
    """
    Pure Playwright extraction — uses semantic role locators.
    Returns a CONFIRMED dict: we know exactly what Playwright found.
    No guessing. No heuristics. Just what the browser's accessibility tree says.
    """
    result = {
        # Header
        "nav_items":        [],   # Confirmed top-level nav items (text + href)
        "nav_by_landmark":  {},   # { landmark_label: [{ text, href }] }
        "cta_buttons":      [],   # Header CTA buttons
        # Footer
        "footer_columns":   {},   # { column_heading: [{ text, href }] }
        # Body
        "page_headings":    [],   # { level, text } for h1-h3
        # Meta
        "aria_nav_labels":  [],   # aria-label of all nav elements
        "has_mega_menu":    False,
    }

    # ── 1. Navigation landmarks ────────────────────────────────────────────
    navs = page.get_by_role("navigation")
    nav_count = await navs.count()
    for i in range(nav_count):
        nav = navs.nth(i)
        label = (await nav.get_attribute("aria-label") or
                 await nav.get_attribute("aria-labelledby") or
                 f"Nav_{i+1}")
        result["aria_nav_labels"].append(label)
        if label not in result["nav_by_landmark"]:
            result["nav_by_landmark"][label] = []

        # Confirmed links and buttons in this nav
        elements = nav.locator("a, button, [role='link'], [role='button']")
        element_count = await elements.count()
        for j in range(min(element_count, 45)):
            el = elements.nth(j)
            try:
                # Get clean inner text
                txt = (await el.inner_text()).strip().replace("\n", " ")[:70]
                if not txt:
                    continue
                
                href = await el.get_attribute("href") or ""
                role_attr = await el.get_attribute("role") or ""
                tag_name = await el.evaluate("e => e.tagName")
                
                # Check if it has a dropdown panel (aria-haspopup or class/aria-expanded)
                has_popup = await el.get_attribute("aria-haspopup")
                expanded = await el.get_attribute("aria-expanded")
                is_trigger = has_popup in ("true", "menu") or expanded is not None or tag_name == "BUTTON"
                
                item = {
                    "text": txt,
                    "href": href,
                    "nav": label,
                    "is_trigger": is_trigger
                }
                
                # Prevent duplicates
                if not any(i["text"] == txt for i in result["nav_by_landmark"][label]):
                    result["nav_by_landmark"][label].append(item)
                
                # Top-level items: either buttons/triggers or short links in the navigation bar
                # Avoid capturing deeply nested links within hidden panels as top-level triggers
                # Typically top-level items are direct children or descendants of a shallow list
                is_shallow = await el.evaluate("""el => {
                    let depth = 0;
                    let p = el.parentElement;
                    while (p && p.tagName !== 'NAV') {
                        depth++;
                        p = p.parentElement;
                    }
                    return depth <= 3;
                }""")
                
                if is_shallow and len(txt) < 30:
                    if not any(n["text"] == txt for n in result["nav_items"]):
                        result["nav_items"].append({"text": txt, "href": href, "is_trigger": is_trigger})
                        
            except Exception:
                pass


    # ── 2. Buttons (CTAs in header) ────────────────────────────────────────
    header_el = page.locator("header, [role='banner']")
    if await header_el.count():
        btns = header_el.get_by_role("button")
        btn_count = await btns.count()
        for i in range(min(btn_count, 15)):
            try:
                txt = (await btns.nth(i).inner_text()).strip()[:60]
                if txt:
                    result["cta_buttons"].append(txt)
            except Exception:
                pass
        # Also get link-buttons (anchors styled as buttons)
        link_btns = header_el.locator("a[class*='btn'], a[class*='button'], a[class*='cta']")
        lbtn_count = await link_btns.count()
        for i in range(min(lbtn_count, 10)):
            try:
                txt  = (await link_btns.nth(i).inner_text()).strip()[:60]
                href = await link_btns.nth(i).get_attribute("href")
                if txt and txt not in result["cta_buttons"]:
                    result["cta_buttons"].append(txt)
            except Exception:
                pass

    # ── 3. Detect mega-menu presence using ARIA snapshot ──────────────────
    try:
        snap = await page.aria_snapshot()
        # Signs of mega-menu: multiple 'list' roles inside navigation,
        # or 'button' items with aria-expanded, or sub-headings
        has_expanded = "expanded: true" in snap or "haspopup:" in snap
        sub_lists    = snap.count("- list") > 3
        result["has_mega_menu"] = has_expanded or sub_lists
    except Exception:
        pass

    # ── 4. Footer columns ─────────────────────────────────────────────────
    footer = page.locator("footer, [role='contentinfo']")
    if await footer.count():
        # Column headings
        col_headings = footer.locator("h2, h3, h4, h5, strong, [role='heading']")
        col_count = await col_headings.count()
        for i in range(min(col_count, 20)):
            try:
                heading_el = col_headings.nth(i)
                col_name = (await heading_el.inner_text()).strip()[:60]
                if not col_name:
                    continue
                result["footer_columns"][col_name] = []

                # Collect links that are siblings or cousins of this heading
                # Strategy: find the parent container, then collect all its links
                parent = heading_el.locator("xpath=..")
                col_links = parent.locator("a")
                cl_count  = await col_links.count()
                for j in range(min(cl_count, 15)):
                    try:
                        link_txt  = (await col_links.nth(j).inner_text()).strip()[:70]
                        link_href = await col_links.nth(j).get_attribute("href") or ""
                        if link_txt:
                            result["footer_columns"][col_name].append(
                                {"text": link_txt, "href": link_href}
                            )
                    except Exception:
                        pass
            except Exception:
                pass

    # ── 5. Page headings (h1-h3) ─────────────────────────────────────────
    for lvl in [1, 2, 3]:
        hdrs = page.get_by_role("heading", level=lvl)
        count = await hdrs.count()
        for i in range(min(count, 8)):
            try:
                txt = (await hdrs.nth(i).inner_text()).strip()[:100]
                if txt:
                    result["page_headings"].append({"level": f"h{lvl}", "text": txt})
            except Exception:
                pass

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Phase 1B — LLM fills in the AMBIGUOUS parts only
# ─────────────────────────────────────────────────────────────────────────────

HYBRID_PROMPT = """You are a web IA specialist. Playwright already confirmed the following navigation data from the page.
Your job is ONLY to provide the CSS selectors needed to extract mega-menu panel contents programmatically.

PLAYWRIGHT CONFIRMED DATA:
{confirmed_json}

Given this confirmed data, respond with ONLY a JSON object:
{{
  "dropdown_panel_selector": "CSS selector for the visible dropdown/mega-menu panel container (relative to header)",
  "column_heading_selector": "CSS selector for sub-column headings inside each panel",
  "column_item_selector": "CSS selector for links under each column heading",
  "footer_heading_selector": "CSS selector for footer column headings",
  "trigger_to_panel_map": {{
    "<nav_item_text>": "<CSS selector unique to that item's panel, or null if no dropdown>"
  }},
  "notes": "Any edge case (empty string if none)"
}}

RULES:
- Only provide selectors — no explanations outside JSON.
- Prefer aria-* and role attributes over class names.
- If the site has no mega-menu (has_mega_menu=false), set dropdown_panel_selector to null.
- For trigger_to_panel_map, only include items that have real dropdowns.
"""


async def ask_llm_for_selectors(confirmed: dict, model: str,
                                 timeout_secs: int = 40) -> dict:
    """
    Ask LLM only for CSS selectors — not for structural interpretation.
    Confirmed Playwright data is already structured; LLM fills selector gaps.
    """
    import subprocess, tempfile, os

    confirmed_json = json.dumps({
        "nav_items":      [n["text"] for n in confirmed.get("nav_items", [])],
        "has_mega_menu":  confirmed.get("has_mega_menu", False),
        "panel_headings": list(confirmed.get("nav_by_landmark", {}).values())[:3],
        "footer_columns": list(confirmed.get("footer_columns", {}).keys()),
        "aria_nav_labels": confirmed.get("aria_nav_labels", []),
    }, indent=2)

    prompt = HYBRID_PROMPT.format(confirmed_json=confirmed_json)

    log(f"[Hybrid] Asking LLM for CSS selectors only (timeout={timeout_secs}s)...", "AI")

    def _call():
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8',
                                         delete=False, suffix='.md') as f:
            f.write(prompt)
            tmp = f.name
        try:
            res = subprocess.run(
                ["opencode", "run",
                 "Follow the instructions in the attached file.",
                 "-m", model, "-f", tmp],
                capture_output=True, text=True, timeout=35,
                shell=(os.name == 'nt')
            )
            return res.stdout if res.returncode == 0 else ""
        except Exception:
            return ""
        finally:
            try:
                os.remove(tmp)
            except Exception:
                pass

    try:
        raw = await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(None, _call),
            timeout=timeout_secs
        )
    except asyncio.TimeoutError:
        log("[Hybrid] LLM timed out — using universal selectors.", "WARN")
        return {}
    except Exception as e:
        log(f"[Hybrid] LLM error: {e} — using universal selectors.", "WARN")
        return {}

    try:
        return json.loads(extract_json_block(raw))
    except Exception:
        log("[Hybrid] Could not parse LLM selector JSON — using universal selectors.", "WARN")
        return {}


# ─────────────────────────────────────────────────────────────────────────────
# Phase 1C — Universal selector fallback (no LLM, covers 90% of sites)
# ─────────────────────────────────────────────────────────────────────────────

def build_universal_selectors(confirmed: dict) -> dict:
    """
    Build selector config from confirmed Playwright data.
    Uses universal selectors that work across most frameworks.
    """
    has_mega = confirmed.get("has_mega_menu", False)
    nav_items = [n["text"] for n in confirmed.get("nav_items", [])]

    # Universal panel selectors (ordered by specificity)
    panel_sel = (
        "[role='menu'], [role='menubar'], "
        "header ul ul, nav ul ul, "
        "[class*='dropdown'], [class*='mega'], [class*='panel'], [class*='flyout'], "
        "[data-dropdown], [aria-expanded='true'] ~ *, [id^=':r'], [class*='popup'], [class*='positioner']"
    ) if has_mega else None



    col_heading_sel = (
        "h2, h3, h4, strong, "
        "[role='heading'], "
        "[class*='heading'], [class*='title'], [class*='category'], [class*='label']"
    )

    # Map each nav item — if mega-menu detected, all get panel; otherwise none
    trigger_map = {}
    simple_labels = {
        'pricing', 'blog', 'careers', 'about', 'contact', 'login',
        'sign in', 'sign up', 'get started', 'start now', 'docs', 'status', 'try free'
    }
    for item in nav_items:
        is_simple = item.lower().strip() in simple_labels
        trigger_map[item] = None if (is_simple or not has_mega) else panel_sel

    return {
        "dropdown_panel_selector":  panel_sel,
        "column_heading_selector":  col_heading_sel,
        "column_item_selector":     "a",
        "footer_heading_selector":  "h2, h3, h4, h5, strong",
        "trigger_to_panel_map":     trigger_map,
        "notes":                    "Universal selectors (no LLM)",
        "_source":                  "universal_heuristic",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Phase 2 — Build the final hybrid extractor JS
# ─────────────────────────────────────────────────────────────────────────────

def build_hybrid_extractor_js(confirmed: dict, selectors: dict) -> str:
    """
    Generate a self-contained JS extractor that combines:
      1. Playwright-confirmed nav item texts (used as ground truth labels)
      2. LLM or universal CSS selectors (used to find panels + columns)
      3. Footer data Playwright already confirmed (directly injected as JSON)

    This JS runs on EVERY crawled page via page.evaluate().
    The confirmed footer data is injected directly — zero re-extraction.
    """
    # Pre-inject footer data Playwright already extracted (no re-work needed)
    footer_seed = {
        col: [i["text"] for i in items]
        for col, items in confirmed.get("footer_columns", {}).items()
    }

    # Confirmed nav items as ground truth
    confirmed_nav = [n["text"] for n in confirmed.get("nav_items", [])]

    panel_sel      = selectors.get("dropdown_panel_selector") or ""
    col_heading    = selectors.get("column_heading_selector") or "h2,h3,h4,strong"
    col_items      = selectors.get("column_item_selector") or "a"
    footer_hdg_sel = selectors.get("footer_heading_selector") or "h3,h4,strong"
    trigger_map    = selectors.get("trigger_to_panel_map") or {}
    source         = selectors.get("_source", "hybrid")

    return f"""() => {{
    // ── HYBRID EXTRACTOR ─────────────────────────────────────────────────────
    // Playwright-confirmed data (injected at build time — never stale):
    const CONFIRMED_NAV   = {json.dumps(confirmed_nav)};
    const FOOTER_SEED     = {json.dumps(footer_seed)};
    const TRIGGER_MAP     = {json.dumps(trigger_map)};
    const PANEL_SEL       = {json.dumps(panel_sel)};
    const COL_HEADING_SEL = {json.dumps(col_heading)};
    const ITEM_SEL        = {json.dumps(col_items)};
    const FOOTER_HDG_SEL  = {json.dumps(footer_hdg_sel)};
    const SOURCE          = {json.dumps(source)};

    const clean  = (s, n=80) => (s||'').replace(/\\s+/g,' ').trim().slice(0,n);
    const qAll   = (sel, root) => sel ? Array.from((root||document).querySelectorAll(sel)) : [];
    const seenH  = new Set();
    const seenF  = new Set();

    const out = {{
        Header: {{ Buttons: [], Dropdowns: {{}} }},
        Body:   {{ Sections: {{}} }},
        Footer: {{ Columns: {{}} }},
        _meta:  {{ source: SOURCE, confirmed_nav: CONFIRMED_NAV }}
    }};

    // ── 1. Header Buttons (CTA anchors) ──────────────────────────────────────
    const headerEl = document.querySelector('header, [role="banner"]');
    if (headerEl) {{
        headerEl.querySelectorAll('a[class*="btn"], a[class*="button"], a[class*="cta"], button').forEach(el => {{
            const t = clean(el.innerText||el.textContent);
            if (t && !out.Header.Buttons.find(b=>b.text===t))
                out.Header.Buttons.push({{text: t, href: el.getAttribute('href')||null}});
        }});
    }}
    if (!out.Header.Buttons.length) delete out.Header.Buttons;

    // ── 2. Mega-Menu Dropdowns (plan-driven, using confirmed nav as labels) ───
    if (PANEL_SEL) {{
        const panels = qAll(PANEL_SEL, headerEl);

        for (const panel of panels) {{
            // Determine which nav trigger this panel belongs to
            let triggerLabel = null;

            // (a) aria-labelledby
            const lid = panel.getAttribute('aria-labelledby');
            if (lid) {{
                const lEl = document.getElementById(lid);
                if (lEl) triggerLabel = clean(lEl.innerText||lEl.textContent);
            }}
            // (b) previous sibling
            if (!triggerLabel && panel.previousElementSibling) {{
                const t = clean(panel.previousElementSibling.innerText||panel.previousElementSibling.textContent);
                if (CONFIRMED_NAV.some(n => n.toLowerCase().includes(t.toLowerCase()) || t.toLowerCase().includes(n.toLowerCase())))
                    triggerLabel = t;
            }}
            // (c) parent li's first text node
            if (!triggerLabel && panel.parentElement) {{
                const firstText = Array.from(panel.parentElement.childNodes)
                    .filter(n=>n.nodeType===3)
                    .map(n=>n.textContent.trim())
                    .find(t=>t.length>0);
                if (firstText) triggerLabel = clean(firstText);
            }}
            if (!triggerLabel) triggerLabel = 'Navigation';

            if (!out.Header.Dropdowns[triggerLabel]) out.Header.Dropdowns[triggerLabel] = {{}};

            // Find columns inside this panel
            const colHeadings = qAll(COL_HEADING_SEL, panel);
            if (colHeadings.length > 0) {{
                for (const hEl of colHeadings) {{
                    const colName = clean(hEl.innerText||hEl.textContent);
                    if (!colName) continue;
                    if (!out.Header.Dropdowns[triggerLabel][colName])
                        out.Header.Dropdowns[triggerLabel][colName] = [];

                    // Items: siblings until next heading
                    let sib = hEl.nextElementSibling;
                    while (sib) {{
                        if (['H1','H2','H3','H4','H5','H6','STRONG'].includes(sib.tagName)) break;
                        sib.querySelectorAll(ITEM_SEL||'a').forEach(a => {{
                            const t = clean(a.innerText||a.textContent);
                            const h = a.getAttribute('href')||null;
                            if (t && !seenH.has(t) && !out.Header.Dropdowns[triggerLabel][colName].find(i=>i.text===t)) {{
                                out.Header.Dropdowns[triggerLabel][colName].push({{text:t, href:h}});
                                seenH.add(t);
                            }}
                        }});
                        sib = sib.nextElementSibling;
                    }}
                }}
            }} else {{
                // No column headings — flat list
                if (!out.Header.Dropdowns[triggerLabel]['Links'])
                    out.Header.Dropdowns[triggerLabel]['Links'] = [];
                panel.querySelectorAll('a').forEach(a => {{
                    const t = clean(a.innerText||a.textContent);
                    const h = a.getAttribute('href')||null;
                    if (t && !seenH.has(t)) {{
                        out.Header.Dropdowns[triggerLabel]['Links'].push({{text:t,href:h}});
                        seenH.add(t);
                    }}
                }});
            }}
        }}
    }}

    // ── 3. Remaining nav links (fallback for non-mega-menu items) ────────────
    const allNavLinks = qAll('header a, nav a', headerEl||document.body);
    for (const a of allNavLinks) {{
        const t = clean(a.innerText||a.textContent);
        if (!t || seenH.has(t)) continue;
        const isConfirmed = CONFIRMED_NAV.some(n => n.toLowerCase() === t.toLowerCase());
        if (!isConfirmed) continue;
        seenH.add(t);
        // Add as simple nav link if not already in a dropdown
        const alreadyInDropdown = Object.values(out.Header.Dropdowns)
            .some(colMap => Object.values(colMap).flat().find(i=>i.text===t));
        if (!alreadyInDropdown) {{
            if (!out.Header.Dropdowns['Main Nav']) out.Header.Dropdowns['Main Nav'] = {{}};
            if (!out.Header.Dropdowns['Main Nav']['Links']) out.Header.Dropdowns['Main Nav']['Links'] = [];
            out.Header.Dropdowns['Main Nav']['Links'].push({{text:t, href:a.getAttribute('href')||null}});
        }}
    }}

    // ── 4. Footer — seed with Playwright-confirmed data + re-extract links ───
    // Pre-fill with Playwright-confirmed column structure
    Object.assign(out.Footer.Columns, JSON.parse(JSON.stringify(FOOTER_SEED))
        ? Object.fromEntries(Object.entries(FOOTER_SEED).map(([k,v]) => [k, v.map(t=>{{return{{text:t,href:null}}}})])) : {{}});

    // Re-extract footer links for this specific page (hrefs vary per page)
    const footerEl = document.querySelector('footer, [role="contentinfo"]');
    if (footerEl) {{
        const fHdgs = qAll(FOOTER_HDG_SEL, footerEl);
        for (const hEl of fHdgs) {{
            const colName = clean(hEl.innerText||hEl.textContent);
            if (!colName) continue;
            if (!out.Footer.Columns[colName]) out.Footer.Columns[colName] = [];

            let sib = hEl.nextElementSibling;
            while (sib) {{
                if (['H1','H2','H3','H4','H5','H6','STRONG'].includes(sib.tagName)) break;
                sib.querySelectorAll('a').forEach(a => {{
                    const t = clean(a.innerText||a.textContent);
                    const h = a.getAttribute('href')||null;
                    if (t && !seenF.has(t) && !out.Footer.Columns[colName].find(i=>i.text===t)) {{
                        out.Footer.Columns[colName].push({{text:t, href:h}});
                        seenF.add(t);
                    }}
                }});
                sib = sib.nextElementSibling;
            }}
        }}
    }}

    // ── 5. Body sections (key page content) ──────────────────────────────────
    document.querySelectorAll('main section, article, [role="main"] section').forEach(sec => {{
        const hEl = sec.querySelector('h1,h2,h3');
        if (!hEl) return;
        const secName = clean(hEl.innerText||hEl.textContent);
        if (!secName || secName.length < 3) return;
        const links = sec.querySelectorAll('a[href]');
        if (!links.length) return;
        out.Body.Sections[secName] = [];
        links.forEach(a => {{
            const t = clean(a.innerText||a.textContent);
            const h = a.getAttribute('href');
            if (t && h && !h.startsWith('javascript:'))
                out.Body.Sections[secName].push({{text:t,href:h}});
        }});
    }});

    if (!Object.keys(out.Body.Sections).length) delete out.Body;

    return out;
}}"""


# ─────────────────────────────────────────────────────────────────────────────
# Public API — called once per crawl session
# ─────────────────────────────────────────────────────────────────────────────

async def build_hybrid_plan(page: Page, model: str,
                             no_llm: bool = False) -> tuple[dict, str]:
    """
    Full hybrid pipeline. Called once on the homepage.
    Returns (plan_meta, extractor_js) where extractor_js runs on every page.

    Timeline:
      ~0.5s   Playwright confirmed extraction (always)
      ~0-40s  LLM selector call (skipped if no_llm=True or times out)
      ~0ms    Universal fallback (if LLM skipped/fails)
      ~0ms    JS string build
    """
    # Step 1 — Playwright extracts what it KNOWS
    log("[Hybrid] Step 1: Playwright confirmed extraction...", "INFO")
    confirmed = await playwright_confirmed_extraction(page)
    log(
        f"[Hybrid] Confirmed: {len(confirmed['nav_items'])} nav items, "
        f"has_mega_menu={confirmed['has_mega_menu']}, "
        f"{len(confirmed['footer_columns'])} footer columns.",
        "INFO"
    )

    # Step 2 — LLM fills in CSS selector GAPS (optional, with timeout)
    selectors = {}
    if not no_llm and confirmed.get("has_mega_menu"):
        selectors = await ask_llm_for_selectors(confirmed, model, timeout_secs=40)
        if selectors:
            selectors["_source"] = "hybrid_llm"
            log(f"[Hybrid] LLM selectors received.", "AI")
        else:
            log("[Hybrid] LLM skipped/failed — using universal selectors.", "WARN")

    if not selectors:
        selectors = build_universal_selectors(confirmed)
        log(f"[Hybrid] Universal selectors applied.", "INFO")

    # Step 3 — Build the final JS extractor
    extractor_js = build_hybrid_extractor_js(confirmed, selectors)

    plan_meta = {
        "source":          selectors.get("_source", "unknown"),
        "nav_items":       [n["text"] for n in confirmed["nav_items"]],
        "has_mega_menu":   confirmed["has_mega_menu"],
        "footer_columns":  list(confirmed["footer_columns"].keys()),
        "selectors":       selectors,
        "confirmed_nav_count":    len(confirmed["nav_items"]),
        "confirmed_footer_count": len(confirmed["footer_columns"]),
    }

    return plan_meta, extractor_js
