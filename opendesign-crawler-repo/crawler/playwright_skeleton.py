"""
playwright_skeleton.py – Pure Playwright IA skeleton extractor.

Playwright's built-in tools that extract page structure with ZERO LLM:

1. page.accessibility.snapshot()
   → Returns the full Accessibility Tree as nested JSON.
   → This is exactly what screen readers see: headings, links, menus, buttons.
   → The browser itself builds this tree from ARIA roles + semantic HTML.

2. page.locator() by role
   → Find all navigation, menu, heading, link elements by semantic role.
   → Works across ALL websites regardless of CSS class names.

3. page.evaluate(JS)
   → For edge cases where accessibility tree is incomplete.

Why this beats raw JS scraping:
   - The accessibility tree respects aria-hidden elements (they're invisible to a11y)
   - Heading levels (h1/h2/h3) are preserved
   - ARIA labels are automatically resolved
   - Menu hierarchy is preserved (menubar → menu → menuitem)
   - Works on SPAs because it sees the live DOM post-hydration
"""

import asyncio
import json
from playwright.async_api import async_playwright, Page


# ─────────────────────────────────────────────────────────────────────────────
# 1.  Accessibility Tree extraction (most semantic approach)
# ─────────────────────────────────────────────────────────────────────────────

async def extract_via_accessibility_tree(page: Page) -> dict:
    """
    Use Playwright's modern aria_snapshot() API (replaces deprecated page.accessibility).
    Returns an ARIA YAML snapshot — parsed to extract nav structure.

    page.aria_snapshot() is available in Playwright >= 1.46.
    It returns a YAML string like:
      - navigation "Main":
        - link "Products"
        - link "Solutions"
    """
    result = {
        "navigation": [],
        "headings":   [],
        "buttons":    [],
        "menus":      [],
    }

    try:
        # Get ARIA snapshot of header/nav region specifically
        header_el = page.locator("header, nav, [role='navigation']").first
        snapshot_yaml = await header_el.aria_snapshot()

        # Parse the YAML text to extract nav structure (simple line-by-line parse)
        current_nav = None
        for line in snapshot_yaml.splitlines():
            stripped = line.strip()
            if stripped.startswith("- navigation"):
                label = stripped.replace("- navigation", "").strip().strip('"')
                current_nav = {"label": label or "Navigation", "items": []}
                result["navigation"].append(current_nav)
            elif stripped.startswith("- link") and current_nav is not None:
                link_name = stripped.replace("- link", "").strip().strip('"')
                if link_name:
                    current_nav["items"].append({"text": link_name, "role": "link"})
            elif stripped.startswith("- heading"):
                heading_text = stripped.replace("- heading", "").strip().strip('"')
                if heading_text:
                    result["headings"].append({"level": "h2", "text": heading_text})
            elif stripped.startswith("- button"):
                btn_text = stripped.replace("- button", "").strip().strip('"')
                if btn_text:
                    result["buttons"].append({"text": btn_text})

    except Exception as e:
        # Fallback: try full page snapshot
        try:
            snapshot_yaml = await page.aria_snapshot()
            for line in snapshot_yaml.splitlines():
                stripped = line.strip()
                if stripped.startswith("- link"):
                    link_name = stripped.replace("- link", "").strip().strip('"')
                    if link_name and len(link_name) < 60:
                        if not result["navigation"]:
                            result["navigation"].append({"label": "Navigation", "items": []})
                        result["navigation"][0]["items"].append({"text": link_name, "role": "link"})
        except Exception:
            pass  # aria_snapshot not available at all — locator fallback handles it

    return result



# ─────────────────────────────────────────────────────────────────────────────
# 2.  Playwright Locator-based extraction (semantic role selectors)
# ─────────────────────────────────────────────────────────────────────────────

async def extract_via_locators(page: Page) -> dict:
    """
    Use Playwright's role-based locators to extract IA semantically.
    These selectors are framework-agnostic — they work on React, Vue, plain HTML.

    Key locators used:
      page.get_by_role("navigation")   → all nav elements
      page.get_by_role("heading")      → all headings
      page.get_by_role("link")         → all links
      page.get_by_role("button")       → all buttons
      page.get_by_role("menubar")      → menubar elements
      page.get_by_role("menu")         → dropdown menus
      page.get_by_role("menuitem")     → items inside menus
    """
    result = {
        "nav_labels":      [],   # Labels of all navigation landmarks
        "nav_links":       [],   # All links inside nav zones
        "headings_h1":     [],   # h1 text
        "headings_h2":     [],   # h2 text
        "headings_h3":     [],   # h3 text
        "cta_buttons":     [],   # Button texts
        "menu_items":      [],   # Items in ARIA menus
    }

    # ── Navigation landmarks ─────────────────────────────────────────────
    navs = page.get_by_role("navigation")
    nav_count = await navs.count()
    for i in range(nav_count):
        nav = navs.nth(i)
        label = await nav.get_attribute("aria-label") or f"Nav {i+1}"
        result["nav_labels"].append(label)

        # Get all links and buttons inside this nav
        nav_els = nav.locator("a, button, [role='link'], [role='button']")
        el_count = await nav_els.count()
        for j in range(min(el_count, 35)):
            el = nav_els.nth(j)
            try:
                txt = (await el.inner_text()).strip().replace("\n", " ")[:80]
                href = await el.get_attribute("href") or ""
                if txt:
                    result["nav_links"].append({"nav": label, "text": txt, "href": href})
            except Exception:
                pass


    # ── Headings by level ─────────────────────────────────────────────────
    for level, key in [(1, "headings_h1"), (2, "headings_h2"), (3, "headings_h3")]:
        headings = page.get_by_role("heading", level=level)
        count = await headings.count()
        for i in range(min(count, 20)):
            try:
                txt = (await headings.nth(i).inner_text()).strip()[:100]
                if txt:
                    result[key].append(txt)
            except Exception:
                pass

    # ── CTA Buttons ───────────────────────────────────────────────────────
    buttons = page.get_by_role("button")
    btn_count = await buttons.count()
    for i in range(min(btn_count, 20)):
        try:
            txt = (await buttons.nth(i).inner_text()).strip()[:60]
            if txt:
                result["cta_buttons"].append(txt)
        except Exception:
            pass

    # ── ARIA menu items ───────────────────────────────────────────────────
    menu_items = page.get_by_role("menuitem")
    mi_count = await menu_items.count()
    for i in range(min(mi_count, 50)):
        try:
            txt = (await menu_items.nth(i).inner_text()).strip()[:80]
            if txt:
                result["menu_items"].append(txt)
        except Exception:
            pass

    return result


# ─────────────────────────────────────────────────────────────────────────────
# 3.  Combined skeleton extractor (merges both approaches)
# ─────────────────────────────────────────────────────────────────────────────

async def extract_full_skeleton(page: Page) -> dict:
    """
    Combines accessibility tree + locator-based extraction.
    Returns a rich skeleton that can drive the plan builder without any LLM.
    """
    # Run both extractors
    a11y   = await extract_via_accessibility_tree(page)
    locator = await extract_via_locators(page)

    # Build merged result
    skeleton = {
        # From locators (most reliable for nav links)
        "nav_triggers":       list({l["text"] for l in locator.get("nav_links", [])
                                    if len(l["text"]) < 30})[:20],  # short = top-level
        "nav_links_by_nav":   {},   # { nav_label: [links] }
        "mega_panel_headings": [],
        "footer_headings":    [],
        "heading_tags":       [],
        "buttons":            locator.get("cta_buttons", [])[:10],
        "menu_items":         locator.get("menu_items", [])[:30],
        "navigation_labels":  locator.get("nav_labels", []),
        # From accessibility tree (best for semantic structure)
        "a11y_navs":          a11y.get("navigation", []),
        "a11y_menus":         a11y.get("menus", []),
        "a11y_headings":      a11y.get("headings", []),
    }

    # Group nav links by nav landmark
    for link in locator.get("nav_links", []):
        nav_lbl = link["nav"]
        if nav_lbl not in skeleton["nav_links_by_nav"]:
            skeleton["nav_links_by_nav"][nav_lbl] = []
        skeleton["nav_links_by_nav"][nav_lbl].append({"text": link["text"], "href": link["href"]})

    # Pull h2/h3 as potential mega-menu headings
    skeleton["mega_panel_headings"] = locator.get("headings_h3", [])[:20]
    skeleton["heading_tags"] = (
        [{"level": "h1", "text": t} for t in locator.get("headings_h1", [])] +
        [{"level": "h2", "text": t} for t in locator.get("headings_h2", [])] +
        [{"level": "h3", "text": t} for t in locator.get("headings_h3", [])]
    )

    # Footer headings: look for footer landmark in a11y tree
    footer_hdrs = await page.locator("footer h2, footer h3, footer h4, footer strong, [role='contentinfo'] h3").all_inner_texts()
    skeleton["footer_headings"] = [t.strip()[:60] for t in footer_hdrs if t.strip()][:20]

    return skeleton


# ─────────────────────────────────────────────────────────────────────────────
# 4.  Quick demo (run this file directly to test against any URL)
# ─────────────────────────────────────────────────────────────────────────────

async def demo(url: str):
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1440, "height": 900})

        # Block heavy assets for speed (same as crawler)
        await page.route("**/*", lambda route: route.abort()
            if route.request.resource_type in ["image", "media", "font"]
            else route.continue_())

        print(f"\n[LOAD] {url}")
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(0.5)

        print("\n[INFO] Extracting skeleton via Playwright (no LLM)...")
        skeleton = await extract_full_skeleton(page)

        print(f"\n[DONE] Skeleton extracted:")
        print(f"   Navigation labels  : {skeleton['navigation_labels']}")
        print(f"   Nav triggers       : {skeleton['nav_triggers'][:10]}")
        print(f"   Panel headings (h3): {skeleton['mega_panel_headings'][:10]}")
        print(f"   Footer headings    : {skeleton['footer_headings'][:10]}")
        print(f"   CTA buttons        : {skeleton['buttons'][:8]}")
        print(f"   ARIA menu items    : {skeleton['menu_items'][:10]}")
        print(f"\n[A11Y] Accessibility tree navs: {len(skeleton['a11y_navs'])}")
        for nav in skeleton['a11y_navs']:
            print(f"   [{nav['label']}] -> {len(nav['items'])} items")

        out_path = "playwright_skeleton_output.json"
        print(f"\n[OUT] Full skeleton JSON saved to {out_path}")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(skeleton, f, indent=2)

        await browser.close()


if __name__ == "__main__":
    import sys
    url = sys.argv[1] if len(sys.argv) > 1 else "https://stripe.com"
    asyncio.run(demo(url))

