"""
ux_ia.py – LLM-as-Strategist UX IA Crawler

Two-phase architecture:
  Phase 1 (once):   Extract navigation skeleton → LLM returns site-specific plan → build extractor JS
  Phase 2 (n pages): All workers run the plan-compiled JS deterministically — zero more LLM calls
"""

import asyncio
import os
import json
import re
from urllib.parse import urljoin, urlparse
from playwright.async_api import async_playwright
from crawler.config import log, MAX_STEPS, VERSION, DEFAULT_MODEL
from crawler.engine import make_context, settle_page, check_and_handle_auth_gate
from crawler.extractor import extract_information_architecture
from crawler.agent import ask_opencode
from crawler.hybrid_extractor import build_hybrid_plan


def is_valid_link(start_url, full_url):
    if not full_url or full_url.startswith(('javascript:', 'mailto:', 'tel:', '#')):
        return False

    # 1. Must be same domain
    if urlparse(start_url).netloc != urlparse(full_url).netloc:
        return False

    # 2. Locale Isolation (Path prefix locking)
    start_path = urlparse(start_url).path
    if not start_path.endswith('/'):
        parts = start_path.split('/')
        if len(parts) > 1 and len(parts[1]) <= 5:  # likely a locale like /in or /en-us
            start_path = f"/{parts[1]}/"
        else:
            start_path = "/"

    if start_path != '/':
        target_path = urlparse(full_url).path
        if not target_path.startswith(start_path) and target_path not in ['/', '']:
            return False

    # 3. I18n block
    if start_path == '/':
        target_path = urlparse(full_url).path
        if len(target_path) > 1:
            first_segment = target_path.strip('/').split('/')[0]
            if re.match(r'^([a-z]{2,3}|[a-z]{2}-[a-z]{2})$', first_segment, re.IGNORECASE):
                return False

    # 4. Auth loop prevention
    skip_keywords = ['login', 'signup', 'register', 'auth', 'signin', 'checkout', 'cart', 'password', 'account']
    if any(kw in full_url.lower() for kw in skip_keywords):
        return False

    return True

def extract_dynamic_categories_from_site(site_graph: dict) -> dict:
    """
    Dynamically groups navigation items into categories based on URL path prefixes
    or DOM landmarks — 100% dynamic for ANY website (Stripe, Guardian, Linear, Amazon, etc.).
    """
    categories = {}
    for url, page_data in site_graph.items():
        ia = page_data.get("ia", {})
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
    """
    try:
        categories = extract_dynamic_categories_from_site(site_graph)
        figma_nodes = []

        for url, page_data in site_graph.items():
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

        # Save PERFECT figma_import_bundle.json dynamically for any website
        nav_tree = {}
        for url, page_data in site_graph.items():
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
            "version": "2.0",
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


async def worker(worker_id: int, queue: asyncio.Queue, visited: set, site_graph: dict,
                 context, start_url: str, max_pages: int, extractor_js: str, plan_meta: dict, output_dir: str):
    """Parallel crawl worker — uses the pre-built plan-driven extractor_js on every page."""
    page = await context.new_page()


    # Block heavy assets for speed
    await page.route("**/*", lambda route: route.abort()
        if route.request.resource_type in ["image", "stylesheet", "media", "font"]
        else route.continue_())

    while True:
        current_url = await queue.get()

        if len(visited) >= max_pages:
            queue.task_done()
            continue

        log(f"[W{worker_id}] Page {len(visited)+1}/{max_pages} — {current_url}", "INFO")
        visited.add(current_url)

        try:
            await page.goto(current_url, wait_until="domcontentloaded", timeout=30000)

            # Check and handle login gate or popup modal
            await check_and_handle_auth_gate(page, output_dir, "desktop", len(visited))

            # ── Step 1: Base extraction (extracts Buttons, Body, Footer columns) ────
            ia_data = await extract_information_architecture(page)
            categorized_links = await page.evaluate(extractor_js)


            # ── Step 2: Sequential hover + visible dropdown panel extraction ──────
            if plan_meta.get("has_mega_menu"):
                dropdowns = {}
                selectors = plan_meta.get("selectors", {})
                panel_sel = selectors.get("dropdown_panel_selector")
                col_hdg   = selectors.get("column_heading_selector")
                item_sel  = selectors.get("column_item_selector")

                for trigger in plan_meta.get("nav_items", []):
                    try:
                        # Find trigger in header
                        loc = page.locator("header nav, [role='navigation'], header").get_by_text(trigger, exact=False).first
                        cnt = await loc.count()
                        log(f"[W{worker_id}] Trigger '{trigger}' found count={cnt}", "INFO")
                        if not cnt or not await loc.is_visible():
                            continue

                        try:
                            await loc.hover(force=True, timeout=1500)
                            log(f"[W{worker_id}] Hovered trigger '{trigger}'", "INFO")
                            await asyncio.sleep(0.3)  # Wait for transition/render
                        except Exception:
                            pass

                        # Extract currently visible panel
                        panel_data = await page.evaluate("""({panelSel, colHdgSel, itemSel}) => {
                                const clean = (s, n=80) => (s||'').replace(/\\s+/g,' ').trim().slice(0,n);
                                const panels = Array.from(document.querySelectorAll(panelSel));
                                const visiblePanel = panels.find(p => {
                                    const style = window.getComputedStyle(p);
                                    return style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0';
                                });
                                if (!visiblePanel) return null;

                                const columns = {};
                                const colHeadings = Array.from(visiblePanel.querySelectorAll(colHdgSel));
                                if (colHeadings.length > 0) {
                                    for (const hEl of colHeadings) {
                                        const colName = clean(hEl.innerText||hEl.textContent);
                                        if (!colName) continue;
                                        columns[colName] = [];

                                        let sib = hEl.nextElementSibling;
                                        while (sib) {
                                            if (['H1','H2','H3','H4','H5','H6','STRONG'].includes(sib.tagName)) break;
                                            sib.querySelectorAll(itemSel || 'a').forEach(a => {
                                                const t = clean(a.innerText||a.textContent);
                                                const h = a.getAttribute('href');
                                                if (t && !columns[colName].find(i=>i.text===t)) {
                                                    columns[colName].push({text:t, href:h});
                                                }
                                            });
                                            sib = sib.nextElementSibling;
                                        }
                                    }
                                } else {
                                    columns['Links'] = [];
                                    visiblePanel.querySelectorAll('a').forEach(a => {
                                        const t = clean(a.innerText||a.textContent);
                                        const h = a.getAttribute('href');
                                        if (t) columns['Links'].push({text:t, href:h});
                                    });
                                }
                                return columns;
                            }""", {"panelSel": panel_sel, "colHdgSel": col_hdg, "itemSel": item_sel})


                        if panel_data and isinstance(panel_data, dict):
                            # Only add if it actually extracted links
                            has_links = False
                            for col, items in panel_data.items():
                                if items and len(items) > 0:
                                    has_links = True
                                    break
                            if has_links:
                                dropdowns[trigger] = panel_data

                    except Exception as e:
                        log(f"[W{worker_id}] Error hovering/extracting trigger '{trigger}': {e}", "WARN")
                        import traceback; traceback.print_exc()


                # Merge dropdowns back into categorized_links
                if "Header" not in categorized_links:
                    categorized_links["Header"] = {}
                
                # Merge into existing dropdowns or replace
                if "Dropdowns" not in categorized_links["Header"]:
                    categorized_links["Header"]["Dropdowns"] = {}
                for k, v in dropdowns.items():
                    categorized_links["Header"]["Dropdowns"][k] = v


            # Extract hrefs for BFS crawl queue
            def get_hrefs(d):
                urls = []
                if isinstance(d, dict):
                    for k, v in d.items():
                        if k == 'href' and isinstance(v, str):
                            urls.append(v)
                        else:
                            urls.extend(get_hrefs(v))
                elif isinstance(d, list):
                    for i in d:
                        urls.extend(get_hrefs(i))
                return urls

            for href in get_hrefs(categorized_links):
                full_url = urljoin(current_url, href).split('#')[0]
                if is_valid_link(start_url, full_url) and full_url not in visited:
                    queue.put_nowait(full_url)

            title = await page.title()
            site_graph[current_url] = {
                "title": title,
                "ia": ia_data,
                "visual_hierarchy": categorized_links
            }

        except Exception as e:
            log(f"[W{worker_id}] Error on {current_url}: {e}", "WARN")

        queue.task_done()

    await page.close()


async def run_ux_ia(start_url: str, output_dir: str, model: str = DEFAULT_MODEL,
                    max_pages: int = MAX_STEPS, no_llm_plan: bool = False, no_screenshots: bool = False):

    domain = urlparse(start_url).netloc.replace("www.", "").replace(".", "_") or "site"
    site_dir = os.path.join(output_dir, domain)
    os.makedirs(site_dir, exist_ok=True)
    log(f"LLM-as-Strategist IA Crawler v{VERSION}", "INFO")
    log(f"URL            : {start_url}", "INFO")
    log(f"Domain Label   : {domain}", "INFO")
    log(f"Max Pages      : {max_pages}", "INFO")
    log(f"No Screenshots : {no_screenshots}", "INFO")
    log(f"Output         : {site_dir}/", "INFO")

    site_graph = {}
    visited = set()
    queue = asyncio.Queue()

    CONCURRENCY = 5


    async with async_playwright() as pw:
        browser, context = await make_context(pw, "desktop")

        # ── Phase 1: Hybrid extraction plan (Playwright + optional LLM) ──────
        log("Phase 1: Playwright confirmed extraction + hybrid plan build...", "INFO")
        probe_page = await context.new_page()
        await probe_page.route("**/*", lambda route: route.abort()
            if route.request.resource_type in ["image", "stylesheet", "media", "font"]
            else route.continue_())
        try:
            await probe_page.goto(start_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(0.8)  # let JS hydrate
            
            # Align start_url to actual redirected URL (fixes locale lock for /in etc)
            redirected_url = probe_page.url
            if redirected_url != start_url:
                log(f"Redirected: {start_url} -> {redirected_url}. Updating locale boundary.", "INFO")
                start_url = redirected_url

            plan_meta, extractor_js = await build_hybrid_plan(
                probe_page, model, no_llm=no_llm_plan
            )


            # Export the plan for inspection / reuse
            plan_path = os.path.join(output_dir, "ia_hybrid_plan.json")
            with open(plan_path, "w", encoding="utf-8") as f:
                json.dump(plan_meta, f, indent=2)
            log(f"Hybrid plan saved to {plan_path} (source={plan_meta.get('source')})", "INFO")
        except Exception as e:
            log(f"Phase 1 hybrid plan failed ({e}), using heuristic fallback.", "WARN")
            import traceback; traceback.print_exc()
            extractor_js = """() => ({ Header: { Dropdowns: {} }, Footer: { Columns: {} } })"""
        finally:
            await probe_page.close()

        # ── Phase 2: Parallel crawl using the plan-driven extractor ────────────
        queue.put_nowait(start_url)
        log(f"Phase 2: Starting {CONCURRENCY} parallel workers...", "INFO")

        workers = [
            asyncio.create_task(
                worker(i, queue, visited, site_graph, context, start_url, max_pages, extractor_js, plan_meta, site_dir)
            )
            for i in range(CONCURRENCY)
        ]


        join_task = asyncio.create_task(queue.join())

        while True:
            if len(visited) >= max_pages:
                break
            if join_task.done():
                break
            await asyncio.sleep(0.5)

        for w in workers:
            if not w.done():
                w.cancel()

        await browser.close()

    # 1. Export Raw Graph
    raw_path = os.path.join(output_dir, "raw_ia_graph.json")
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(site_graph, f, indent=2)
    log(f"Raw IA Graph exported to {raw_path} ({len(site_graph)} pages)", "INFO")

    # 1B. Export Figma-compatible JSON & Visual SVG for direct drag-and-drop into Figma
    generate_figma_artifacts(output_dir, site_graph)

    # 2. AI UX Synthesis — sends structured dropdown hierarchy (dropdown -> categories -> items)
    log(f"Phase 3: Feeding IA structure to LLM for UX synthesis ({model})...", "AI")

    dropdown_summary = {}
    footer_summary = {}
    for url, page_data in site_graph.items():
        vh = page_data.get("visual_hierarchy", {})
        header_drops = vh.get("Header", {}).get("Dropdowns", {})
        if isinstance(header_drops, dict):
            for drop_name, col_map in header_drops.items():
                if drop_name not in dropdown_summary:
                    dropdown_summary[drop_name] = {}
                if isinstance(col_map, dict):
                    for col_name, items in col_map.items():
                        if isinstance(items, list):
                            item_names = [it.get("text") for it in items if isinstance(it, dict) and it.get("text")]
                            if item_names:
                                dropdown_summary[drop_name][col_name] = item_names

        footer_cols = vh.get("Footer", {}).get("Columns", {})
        if isinstance(footer_cols, dict):
            for col_name, items in footer_cols.items():
                if col_name not in footer_summary and isinstance(items, list):
                    item_names = [it.get("text") for it in items if isinstance(it, dict) and it.get("text")]
                    if item_names:
                        footer_summary[col_name] = item_names

    summary = {
        "total_pages": len(site_graph),
        "header_dropdowns": dropdown_summary,
        "footer_columns": footer_summary,
        "extraction_plan_used": os.path.exists(os.path.join(output_dir, "ia_extraction_plan.json"))
    }

    prompt = f"""You are a Senior UX Architect analyzing the Navigation Information Architecture of a website.

CRITICAL INSTRUCTION:
- Focus STRICTLY on the extracted Header Dropdown categories and item link titles.
- DO NOT include body section headings, body paragraphs, marketing text, or page copy.
- In your Mermaid diagram, ALWAYS enclose ALL node labels in double quotes (e.g. N1["News & Media"] or N2["Payments (Online)"]) to prevent syntax errors.
- Your breakdown MUST detail each Header Dropdown -> Category Heading -> Dropdown Link Titles.

Extracted Navigation Structure:
{json.dumps(summary, indent=2)}

Synthesize this into a clean, professional UX IA overview in Markdown format:
1. Executive UX Overview (2-3 paragraphs analyzing the site's top-level navigation, categorization quality, and information density).
2. Mermaid Diagram: A valid `flowchart TD` with double-quoted labels for Header Dropdowns -> Category Headings -> Sub-Item Titles.
3. Section Map: Bullet-list breakdown detailing every Header Dropdown -> Sub-Category Heading -> Dropdown Item Link Titles.
4. UX Recommendations: 3 targeted recommendations to optimize navigation clarity, discoverability, and structure.
"""

    ai_response = await ask_opencode(prompt, model=model)

    md_path = os.path.join(output_dir, "ux_ia_overview.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(ai_response)

    log(f"UX Overview generated at {md_path}", "INFO")

    # 3. AI-Driven Figma Tree Bundle Synthesis — Uses LLM to organize raw links into clean 3-level tree
    log(f"Phase 3B: Using AI Strategist to synthesize 3-level navigation_tree for Figma...", "AI")
    tree_prompt = f"""You are a Senior UX Architect structuring a website's Navigation Information Architecture into a clean 3-level tree JSON format for a Figma Plugin.

INPUT DATA:
{json.dumps(summary, indent=2)}

TASK:
Organize all navigation links into a clean, professional 3-level JSON hierarchy:
Level 1: Primary Header Dropdowns (e.g. Products, Solutions, Developers, Resources, News, Opinion, Sport, Culture, Lifestyle, Company)
Level 2: Sub-Category Headings (e.g. Payments, Billing, World News, US Politics, Football, Film, etc.)
Level 3: Array of clean string item link titles.

OUTPUT INSTRUCTION:
- Return ONLY a valid JSON object wrapped in ```json ``` markdown code block.
- Schema MUST be:
```json
{{
  "navigation_tree": {{
    "Section 1": {{
      "Category A": ["Link Title 1", "Link Title 2"],
      "Category B": ["Link Title 3", "Link Title 4"]
    }},
    "Section 2": {{
      "Category C": ["Link Title 5", "Link Title 6"]
    }}
  }}
}}
```
"""
    try:
        json_ai_res = await ask_opencode(tree_prompt, model=model)
        json_match = re.search(r'```json\s*(\{.*?\})\s*```', json_ai_res, re.DOTALL)
        if json_match:
            ai_bundle = json.loads(json_match.group(1))
            if "navigation_tree" in ai_bundle and len(ai_bundle["navigation_tree"]) > 0:
                bundle_path = os.path.join(output_dir, "figma_import_bundle.json")
                ai_bundle["version"] = "2.0"
                ai_bundle["generator"] = "OpenDesign AI IA Synthesizer"
                with open(bundle_path, "w", encoding="utf-8") as f:
                    json.dump(ai_bundle, f, indent=2)
                log(f"AI-Synthesized Figma Import Bundle saved to {bundle_path}", "INFO")
    except Exception as e:
        log(f"AI Figma bundle synthesis fallback ({e})", "WARN")
