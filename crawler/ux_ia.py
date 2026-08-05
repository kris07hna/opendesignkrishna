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
from crawler.engine import make_context, settle_page
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


async def worker(worker_id: int, queue: asyncio.Queue, visited: set, site_graph: dict,
                 context, start_url: str, max_pages: int, extractor_js: str, plan_meta: dict):
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
                    # Direct links do not have dropdowns
                    is_simple = trigger.lower().strip() in [
                        'pricing', 'blog', 'careers', 'about', 'contact', 'login',
                        'sign in', 'sign up', 'get started', 'start now', 'try free',
                        'docs', 'status', 'contact sales', 'sign in sign in'
                    ]
                    if is_simple:
                        continue
                    try:
                        # Find trigger in header
                        loc = page.locator("header nav, [role='navigation'], header").get_by_text(trigger, exact=False).first
                        cnt = await loc.count()
                        log(f"[W{worker_id}] Trigger '{trigger}' found count={cnt}", "INFO")
                        if cnt:
                            await loc.hover()
                            log(f"[W{worker_id}] Hovered trigger '{trigger}'", "INFO")
                            await asyncio.sleep(0.3)  # Wait for transition/render

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
                    max_pages: int = MAX_STEPS, no_llm_plan: bool = False):

    os.makedirs(output_dir, exist_ok=True)
    log(f"LLM-as-Strategist IA Crawler v{VERSION}", "INFO")
    log(f"URL       : {start_url}", "INFO")
    log(f"Max Pages : {max_pages}", "INFO")
    log(f"Output    : {output_dir}/", "INFO")

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
                worker(i, queue, visited, site_graph, context, start_url, max_pages, extractor_js, plan_meta)
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

    # 2. AI UX Synthesis — sends only a compressed summary, not the full graph
    log(f"Phase 3: Feeding IA structure to LLM for UX synthesis ({model})...", "AI")

    # Build a compact summary (not raw graph) to save tokens
    dropdown_summary = {}
    footer_summary = {}
    for url, page_data in site_graph.items():
        vh = page_data.get("visual_hierarchy", {})
        for drop_name, col_map in (vh.get("Header", {}).get("Dropdowns", {})).items():
            if drop_name not in dropdown_summary:
                dropdown_summary[drop_name] = list(col_map.keys()) if isinstance(col_map, dict) else []
        for col_name in (vh.get("Footer", {}).get("Columns", {})).keys():
            footer_summary[col_name] = True

    summary = {
        "total_pages": len(site_graph),
        "header_dropdowns": dropdown_summary,
        "footer_columns": list(footer_summary.keys()),
        "extraction_plan_used": os.path.exists(os.path.join(output_dir, "ia_extraction_plan.json"))
    }

    prompt = f"""You are a Senior UX Engineer analyzing the Information Architecture of a website.
A crawler extracted {summary['total_pages']} pages using a plan-driven mega-menu extractor.

Navigation Summary:
{json.dumps(summary, indent=2)}

Synthesize this into a clean, professional IA overview in Markdown format including:
1. Executive UX Overview (2-3 paragraphs on the site's structure and user intent).
2. Mermaid Diagram: A `flowchart TD` with subgraphs for each Header Dropdown and its sub-columns.
3. Section Map: Bullet-list breakdown of Header dropdowns → sub-columns → key items.
4. UX Recommendations: 3 specific improvements based on the IA structure.
"""

    ai_response = await ask_opencode(prompt, model=model)

    md_path = os.path.join(output_dir, "ux_ia_overview.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(ai_response)

    log(f"UX Overview generated at {md_path}", "INFO")
