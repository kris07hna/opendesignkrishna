import os
import re
import asyncio
from urllib.parse import urlparse
from playwright.async_api import BrowserContext, Page
from crawler.config import log

def resolve_screenshot_path(output_dir: str, url: str, viewport: str, step: int = 1, page_name: str = "") -> str:
    """
    Constructs a clean domain/category/ folder path labeled by page title/slug.
    Example: screenshots_ai/stripe_com/products/desktop_01_checkout.png
    """
    parsed = urlparse(url)
    domain = parsed.netloc.replace("www.", "").replace(".", "_") or "site"
    path_parts = [p for p in parsed.path.strip("/").split("/") if p]

    if len(path_parts) > 1:
        parent_category = re.sub(r'[^a-zA-Z0-9_\-]', '_', path_parts[0].lower())
        category_dir = os.path.join(output_dir, domain, parent_category)
        slug = re.sub(r'[^a-zA-Z0-9_\-]', '_', path_parts[-1].lower())
    elif len(path_parts) == 1:
        parent_category = re.sub(r'[^a-zA-Z0-9_\-]', '_', path_parts[0].lower())
        category_dir = os.path.join(output_dir, domain, parent_category)
        slug = "overview"
    else:
        category_dir = os.path.join(output_dir, domain)
        slug = "home"

    os.makedirs(category_dir, exist_ok=True)

    if page_name and page_name.strip():
        clean_title = re.sub(r'[^a-zA-Z0-9_\-]', '_', page_name.lower().strip())[:30]
        filename = f"{viewport}_{step:02d}_{clean_title}.png"
    else:
        filename = f"{viewport}_{step:02d}_{slug}.png"

    return os.path.join(category_dir, filename)

VIEWPORTS = {
    "desktop": {"width": 1440, "height": 900, "is_mobile": False},
    "mobile": {"width": 390, "height": 844, "is_mobile": True, "device_scale_factor": 3}
}
USER_AGENTS = {
    "desktop": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "mobile": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
}

STEALTH_INIT_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
window.chrome = { runtime: {} };
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
"""

async def make_context(pw, viewport_name: str) -> BrowserContext:
    vp = VIEWPORTS[viewport_name]
    browser = await pw.chromium.launch(
        headless=True,
        args=[
            "--no-sandbox", "--disable-setuid-sandbox",
            "--disable-dev-shm-usage", "--disable-gpu",
            "--disable-blink-features=AutomationControlled",
            "--disable-extensions", "--no-first-run", "--mute-audio",
            "--disable-background-networking",
            "--disable-background-timer-throttling",
            "--font-render-hinting=none",
            "--disable-http2",
        ]
    )
    ctx_args = dict(
        viewport={"width": vp["width"], "height": vp["height"]},
        device_scale_factor=vp.get("device_scale_factor", 1),
        user_agent=USER_AGENTS[viewport_name],
        ignore_https_errors=True,
        java_script_enabled=True,
        locale="en-US",
        timezone_id="America/New_York",
        color_scheme="light",
        extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
    )
    if vp.get("is_mobile"):
        ctx_args["is_mobile"] = True
        ctx_args["has_touch"] = True
    context = await browser.new_context(**ctx_args)
    await context.add_init_script(STEALTH_INIT_SCRIPT)
    return browser, context

def extract_dynamic_categories_from_site(site_graph: dict) -> dict:
    categories = {}
    for url, page_data in site_graph.items():
        ia = page_data.get("ia", {}) if isinstance(page_data, dict) else {}
        nav_items = ia.get("navigation", [])
        for item in nav_items:
            if isinstance(item, dict) and item.get("name"):
                name = item.get("name").strip()
                href = item.get("href", "")
                if not name or len(name) > 45:
                    continue

                parsed_path = [p for p in urlparse(href).path.strip("/").split("/") if p]
                if parsed_path:
                    cat_name = parsed_path[0].replace("-", " ").replace("_", " ").title()
                    if len(cat_name) <= 22 and not cat_name.isdigit():
                        if cat_name not in categories:
                            categories[cat_name] = []
                        if name not in categories[cat_name]:
                            categories[cat_name].append(name)
                        continue

                if "Main Navigation" not in categories:
                    categories["Main Navigation"] = []
                if name not in categories["Main Navigation"]:
                    categories["Main Navigation"].append(name)

    return categories

def generate_figma_artifacts(output_dir: str, site_graph: dict):
    """
    Generates Figma-compatible JSON (sitemap_figma.json), figma_import_bundle.json,
    and drag-and-drop vector SVG (sitemap_visual.svg) 100% dynamically for any website.
    Shared across ALL crawler modes (ux-ia, spider, runner).
    """
    try:
        categories = extract_dynamic_categories_from_site(site_graph)
        figma_nodes = []

        for url, page_data in site_graph.items():
            if not isinstance(page_data, dict):
                continue
            ia = page_data.get("ia", {})
            title = ia.get("page_title") or page_data.get("title") or url
            nav_items = ia.get("navigation", [])

            children = []
            for item in nav_items:
                if isinstance(item, dict) and item.get("name"):
                    name = item.get("name").strip()
                    href = item.get("href", "")
                    children.append({"name": name, "href": href, "type": "LINK"})

            figma_nodes.append({
                "id": url,
                "title": title,
                "url": url,
                "type": "FRAME",
                "children": children
            })

        # Save Figma-compatible JSON artifact (sitemap_figma.json)
        figma_data = {
            "version": "1.0",
            "generator": "OpenDesign Web Flow Mapper",
            "total_nodes": len(figma_nodes),
            "nodes": figma_nodes
        }
        figma_path = os.path.join(output_dir, "sitemap_figma.json")
        with open(figma_path, "w", encoding="utf-8") as f:
            json.dump(figma_data, f, indent=2)
        log(f"Figma JSON artifact saved to {figma_path}", "INFO")

        # Save figma_import_bundle.json dynamically for any website
        nav_tree = {}
        for url, page_data in site_graph.items():
            if not isinstance(page_data, dict):
                continue
            vh = page_data.get("visual_hierarchy", {})
            header_drops = vh.get("Header", {}).get("Dropdowns", {})
            if isinstance(header_drops, dict):
                for drop_name, col_map in header_drops.items():
                    if drop_name not in nav_tree:
                        nav_tree[drop_name] = {}
                    if isinstance(col_map, dict):
                        for col_name, items in col_map.items():
                            if isinstance(items, list):
                                item_names = [it.get("text") for it in items if isinstance(it, dict) and it.get("text")]
                                if item_names:
                                    nav_tree[drop_name][col_name] = item_names

        if not nav_tree and categories:
            nav_tree = {cat: {"Links": items} for cat, items in categories.items() if items}

        bundle_data = {
            "version": "3.0",
            "generator": "OpenDesign Web Flow Mapper",
            "navigation_tree": nav_tree
        }
        bundle_path = os.path.join(output_dir, "figma_import_bundle.json")
        with open(bundle_path, "w", encoding="utf-8") as f:
            json.dump(bundle_data, f, indent=2)
        log(f"Dynamic Figma Import Bundle saved to {bundle_path}", "INFO")

        # Save SVG vector sitemap (sitemap_visual.svg) for direct drag-and-drop into Figma
        cat_keys = list(categories.keys()) or ["Main Nav"]
        box_w, box_h, gap_x, padding = 180, 40, 40, 60
        num_cats = len(cat_keys)
        svg_w = max(1200, num_cats * (box_w + gap_x) + padding * 2)
        max_items = max((len(items) for items in categories.values()), default=1)
        svg_h = 240 + max_items * (box_h + 14)

        root_x = svg_w / 2 - box_w / 2
        root_y = padding

        svg_lines = [
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {svg_w} {svg_h}" width="{svg_w}" height="{svg_h}" style="background-color: #0f172a; font-family: sans-serif;">',
            f'<rect width="100%" height="100%" fill="#0f172a"/>',
            f'<g transform="translate({root_x}, {root_y})">',
            f'  <rect width="{box_w}" height="48" rx="8" fill="#6366f1" stroke="#818cf8" stroke-width="2"/>',
            f'  <text x="{box_w/2}" y="28" fill="#ffffff" font-size="14" font-weight="bold" text-anchor="middle">Sitemap Topology</text>',
            f'</g>'
        ]

        start_x = (svg_w - (num_cats * box_w + (num_cats - 1) * gap_x)) / 2
        for i, cat_name in enumerate(cat_keys):
            cat_x = start_x + i * (box_w + gap_x)
            cat_y = root_y + 110
            svg_lines.append(f'<path d="M {root_x + box_w/2} {root_y + 48} C {root_x + box_w/2} {root_y + 80}, {cat_x + box_w/2} {cat_y - 30}, {cat_x + box_w/2} {cat_y}" fill="none" stroke="#475569" stroke-width="2"/>')
            svg_lines.append(f'<g transform="translate({cat_x}, {cat_y})"><rect width="{box_w}" height="{box_h}" rx="6" fill="#1e293b" stroke="#3b82f6" stroke-width="2"/><text x="{box_w/2}" y="25" fill="#f8fafc" font-size="13" font-weight="bold" text-anchor="middle">{cat_name}</text></g>')

            sub_list = categories.get(cat_name, [])
            for j, item_name in enumerate(sub_list):
                item_y = cat_y + 60 + j * (box_h + 12)
                svg_lines.append(f'<path d="M {cat_x + box_w/2} {cat_y + box_h} L {cat_x + box_w/2} {item_y}" fill="none" stroke="#334155" stroke-width="1.5" stroke-dasharray="4,4"/>')
                svg_lines.append(f'<g transform="translate({cat_x}, {item_y})"><rect width="{box_w}" height="34" rx="5" fill="#0f172a" stroke="#334155" stroke-width="1.5"/><text x="{box_w/2}" y="21" fill="#94a3b8" font-size="11" font-weight="500" text-anchor="middle">{item_name[:25]}</text></g>')

        svg_lines.append('</svg>')
        svg_path = os.path.join(output_dir, "sitemap_visual.svg")
        with open(svg_path, "w", encoding="utf-8") as f:
            f.write("\n".join(svg_lines))
        log(f"Visual SVG sitemap saved to {svg_path}", "INFO")

    except Exception as e:
        log(f"Failed to generate Figma artifacts ({e})", "WARN")

_OVERLAY_JS = """
() => {
    let dismissed = 0;
    const closeSelectors = [
        'button[aria-label*="Close" i]', 'button[aria-label*="close" i]',
        'button[aria-label*="Dismiss" i]', 'button[aria-label*="dismiss" i]',
        '[data-dismiss="modal"]', '[data-role="close"]',
        '.modal-close', '.popup-close', '.close-modal', '.close-popup',
        '#onetrust-accept-btn-handler', '.cc-btn.cc-dismiss', '.cc-dismiss',
        '#cookie-accept', '.accept-cookies', '[id*="cookie-accept"]',
        'button[id*="accept"]', 'button[class*="accept"]',
        'button:has-text("Not now")', 'button:has-text("Maybe later")',
        'button:has-text("Skip")', 'button:has-text("No thanks")',
    ];

    function deepQuery(root, sel) {
        let nodes = [];
        try { nodes = Array.from(root.querySelectorAll(sel)); } catch(e) {}
        try {
            root.querySelectorAll('*').forEach(el => {
                if (el.shadowRoot) nodes = nodes.concat(deepQuery(el.shadowRoot, sel));
            });
        } catch(e) {}
        return nodes;
    }

    closeSelectors.forEach(sel => {
        deepQuery(document, sel).forEach(btn => {
            try {
                if ((btn.offsetWidth > 0 || btn.offsetHeight > 0)) {
                    btn.click();
                    dismissed++;
                }
            } catch(e) {}
        });
    });

    const vw = window.innerWidth, vh = window.innerHeight;
    document.querySelectorAll('div,section,aside,dialog,form,iframe,[role="dialog"],[role="alertdialog"]').forEach(el => {
        try {
            const s = window.getComputedStyle(el);
            const z = parseInt(s.zIndex || '0');
            if ((s.position === 'fixed' || s.position === 'absolute') && z > 100) {
                const r = el.getBoundingClientRect();
                const area = r.width * r.height;
                if (area > vw * vh * 0.40 &&
                    !['BODY','MAIN','SECTION','ARTICLE','NAV','HEADER','FOOTER'].includes(el.tagName)) {
                    el.style.setProperty('display', 'none', 'important');
                    dismissed++;
                }
            }
        } catch(e) {}
    });

    document.body.style.setProperty('overflow', 'auto', 'important');
    document.documentElement.style.setProperty('overflow', 'auto', 'important');
    document.body.style.setProperty('position', 'static', 'important');

    return dismissed;
}
"""

async def dismiss_all_overlays(page: Page) -> int:
    try:
        await page.keyboard.press("Escape")
        await asyncio.sleep(0.15)
    except Exception:
        pass
    try:
        count = await page.evaluate(_OVERLAY_JS)
        if count > 0:
            log(f"Dismissed {count} overlay(s)", "INFO")
        return count
    except Exception:
        return 0

async def check_and_handle_auth_gate(page: Page, output_dir: str, viewport: str, step: int) -> bool:
    """
    Detects if the current page or active modal is an Auth/Login/Signup Gate.
    If detected:
      1. Takes a screenshot of the popup/gate for documentation
      2. Logs the gate detection
      3. Automatically returns back (page.go_back) or dismisses modal so crawling continues.
    """
    try:
        url = page.url.lower()
        title = (await page.title()).lower()

        auth_keywords = ["login", "sign-in", "signin", "signup", "register", "auth/", "account/login"]
        is_auth_url = any(kw in url or kw in title for kw in auth_keywords)

        is_auth_modal = await page.evaluate("""() => {
            const authSel = '[class*="login" i], [class*="signup" i], [class*="auth" i], [id*="login" i], [id*="signup" i], form[action*="login" i], form[action*="signup" i]';
            const modals = document.querySelectorAll('dialog, [role="dialog"], .modal, .popup');
            for (const m of modals) {
                if (m.querySelector(authSel) || m.innerText.toLowerCase().includes('sign in') || m.innerText.toLowerCase().includes('log in')) {
                    const style = window.getComputedStyle(m);
                    if (style.display !== 'none' && style.visibility !== 'hidden') {
                        return true;
                    }
                }
            }
            return false;
        }""")

        if is_auth_url or is_auth_modal:
            log(f"Detected Auth/Login/Signup Gate at {url}", "WARN")
            try:
                shot_path = resolve_screenshot_path(output_dir, url, viewport, step, "auth_gate")
                await page.screenshot(path=shot_path, full_page=False, type="png")
                log(f"Saved auth gate screenshot: {os.path.basename(shot_path)}", "SNAP")
            except Exception:
                pass

            if is_auth_url:
                log("Navigating back from login page to continue crawl...", "INFO")
                try:
                    await page.go_back(wait_until="domcontentloaded", timeout=5000)
                except Exception:
                    pass
            else:
                await dismiss_all_overlays(page)

            return True

        return False
    except Exception:
        return False

async def expand_all_dropdowns(page: Page):
    """
    Finds and interacts with all header/footer dropdown triggers and submenus
    so hidden megamenu links are rendered into the DOM.
    """
    try:
        triggers = page.locator(
            "header [aria-expanded='false'], header button[aria-haspopup], "
            "nav [aria-expanded='false'], nav button[aria-haspopup], "
            "header .dropdown-toggle, nav .dropdown-toggle, "
            "header .menu-item-has-children > a, nav .menu-item-has-children > a"
        )
        count = await triggers.count()
        for i in range(min(count, 15)):
            try:
                el = triggers.nth(i)
                if await el.is_visible():
                    await el.hover(timeout=1000)
                    await asyncio.sleep(0.2)
            except Exception:
                pass
    except Exception:
        pass

async def settle_page(page: Page, full_scroll: bool = True):
    for state in ("networkidle", "domcontentloaded", "load"):
        try:
            await page.wait_for_load_state(state, timeout=4000)
            break
        except Exception:
            continue

    if full_scroll:
        try:
            await page.evaluate("""
            async () => {
                const delay = ms => new Promise(r => setTimeout(r, ms));
                const total = Math.max(document.body.scrollHeight, document.documentElement.scrollHeight);
                const step = Math.min(600, Math.ceil(total / 10));
                for (let y = 0; y < total; y += step) {
                    window.scrollTo(0, y);
                    await delay(80);
                }
                window.scrollTo(0, 0);
                await delay(150);
            }
            """)
        except Exception:
            pass

    await dismiss_all_overlays(page)
    await expand_all_dropdowns(page)
    await asyncio.sleep(1)

async def take_screenshot(page: Page, path: str, full_page: bool = True):
    await settle_page(page, full_scroll=full_page)
    try:
        await page.screenshot(path=path, full_page=full_page, type="png")
        log(f"Screenshot saved: {os.path.basename(path)}", "SNAP")
    except Exception as e:
        log(f"Screenshot failed ({e}), retrying viewport-only", "WARN")
        try:
            await page.screenshot(path=path, full_page=False, type="png")
        except Exception:
            pass
