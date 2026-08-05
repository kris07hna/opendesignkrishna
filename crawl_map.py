#!/usr/bin/env python3
import os
import sys
import json
import asyncio
import argparse
from urllib.parse import urlparse, urljoin, urldefrag
from playwright.async_api import async_playwright, Page

# Authentication page detection heuristics
async def is_auth_page(page: Page) -> bool:
    """
    Analyzes the current page to detect if it is an authentication/login page.
    Checks for password fields, login-related forms, labels, and buttons.
    """
    # 1. Check for password input fields (most reliable check)
    password_fields = await page.locator("input[type='password']").count()
    if password_fields > 0:
        return True

    # 2. Check for common login/auth patterns in input names/IDs
    auth_selectors = [
        "input[name*='login']", "input[id*='login']",
        "input[name*='username']", "input[id*='username']",
        "input[name*='signin']", "input[id*='signin']",
    ]
    for selector in auth_selectors:
        try:
            if await page.locator(selector).count() > 0:
                # Double check if there are also submit or text fields typical for logins
                return True
        except Exception:
            pass

    # 3. Check form text or submit button labels
    buttons = await page.locator("button, input[type='submit']").all()
    for btn in buttons:
        try:
            text = (await btn.text_content() or await btn.input_value() or "").lower()
            if any(kw in text for kw in ["log in", "login", "sign in", "signin", "authenticate"]):
                # If there's also an email/text input, it's highly likely a login page
                inputs = await page.locator("input[type='text'], input[type='email']").count()
                if inputs > 0:
                    return True
        except Exception:
            pass

    return False

def clean_url(url: str) -> str:
    """Removes fragments and normalizes the URL."""
    defragmented, _ = urldefrag(url)
    if defragmented.endswith("/"):
        defragmented = defragmented[:-1]
    return defragmented

def get_screenshot_filename(url: str, output_dir: str) -> str:
    """Generates a safe filename for a screenshot from a URL."""
    parsed = urlparse(url)
    path = parsed.path.strip("/").replace("/", "_")
    if not path:
        path = "index"
    query = parsed.query.replace("=", "_").replace("&", "_")
    if query:
        path = f"{path}_{query}"
    # Remove any unsafe characters
    safe_path = "".join(c for c in path if c.isalnum() or c in ("-", "_"))
    return os.path.join(output_dir, f"{safe_path}.png")

def print_tree(node: str, sitemap: dict, indent: str = "", visited: set = None):
    """Prints a clean hierarchical tree of the mapped website."""
    if visited is None:
        visited = set()
    
    if node in visited:
        print(f"{indent}|-- {node} (already mapped)")
        return
    visited.add(node)
    
    print(f"{indent}|-- {node}")
    children = sitemap.get(node, [])
    for i, child in enumerate(children):
        is_last = (i == len(children) - 1)
        next_indent = indent + ("    " if is_last else "|   ")
        print_tree(child, sitemap, next_indent, visited)

async def crawl_site(start_url: str, max_depth: int, output_dir: str):
    print("=" * 60)
    print(f"[START] Beginning crawl at: {start_url}")
    print(f"Depth limit: {max_depth} | Output directory: {output_dir}")
    print("=" * 60)

    if start_url and not start_url.startswith("http://") and not start_url.startswith("https://"):
        start_url = "https://" + start_url
    start_url = clean_url(start_url)
    domain = urlparse(start_url).netloc

    visited = set()
    sitemap = {}
    auth_pages = set()
    queue = [(start_url, 0, None)]  # (url, current_depth, parent_url)

    async with async_playwright() as p:
        # Launch headless Chromium browser
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        # Set default timeout to 15 seconds
        page.set_default_timeout(15000)

        while queue:
            url, depth, parent = queue.pop(0)
            url = clean_url(url)

            # Record sitemap edge
            if parent:
                if parent not in sitemap:
                    sitemap[parent] = []
                if url not in sitemap[parent]:
                    sitemap[parent].append(url)

            if url in visited:
                continue
            visited.add(url)

            print(f"\n[VISITING] {url} (Depth: {depth})")
            try:
                # Load the page
                response = await page.goto(url, wait_until="domcontentloaded")
                if not response:
                    print(f"[WARN] No response received for {url}")
                    continue

                # Detect if page is an authentication form
                is_auth = await is_auth_page(page)
                if is_auth:
                    print(f"[AUTH] Authentication gate detected at: {url}")
                    print("[HALT] Stopping screenshots and deeper crawling on this branch.")
                    auth_pages.add(url)
                    continue

                # Wait slightly for dynamic elements
                await page.wait_for_timeout(1000)

                # Capture screenshot
                screenshot_path = get_screenshot_filename(url, output_dir)
                await page.screenshot(path=screenshot_path, full_page=True)
                print(f"[SCREENSHOT] Captured full-page at: {screenshot_path}")

                # If we haven't hit the depth limit, extract and queue links
                if depth < max_depth:
                    # Find all <a> tags with hrefs
                    hrefs = await page.eval_on_selector_all("a[href]", "elements => elements.map(el => el.href)")
                    for href in hrefs:
                        joined_url = urljoin(url, href)
                        cleaned_child = clean_url(joined_url)
                        parsed_child = urlparse(cleaned_child)

                        # Standard validation checks
                        if parsed_child.netloc != domain:
                            continue  # Keep to the same domain

                        # Skip common asset files to speed up crawling
                        if parsed_child.path.lower().endswith(
                            (".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip", ".tar", ".gz", ".mp4", ".css", ".js")
                        ):
                            continue

                        # Add to queue if not visited
                        if cleaned_child not in visited and not any(q[0] == cleaned_child for q in queue):
                            queue.append((cleaned_child, depth + 1, url))

            except Exception as e:
                print(f"[ERROR] Failed to process {url}: {e}")

        await browser.close()

    # Save mapping results
    sitemap_file = os.path.join(output_dir, "sitemap.json")
    with open(sitemap_file, "w", encoding="utf-8") as f:
        json.dump({
            "start_url": start_url,
            "crawled_urls": list(visited),
            "auth_gated_urls": list(auth_pages),
            "graph": sitemap
        }, f, indent=2)

    print("\n" + "=" * 60)
    print("[COMPLETE] Website mapped successfully")
    print(f"Sitemap saved to: {sitemap_file}")
    print(f"Screenshots saved to: {output_dir}/")
    print("=" * 60)
    print("\nVisual Page Hierarchy Map:")
    print_tree(start_url, sitemap)
    print("=" * 60)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Recursively crawl, screenshot, and map web pages.")
    parser.add_argument("--url", required=True, help="Starting URL to crawl")
    parser.add_argument("--max-depth", type=int, default=2, help="Maximum crawling depth (default: 2)")
    parser.add_argument("--output-dir", default="screenshots", help="Directory for output sitemap and screenshots")
    
    args = parser.parse_args()
    
    try:
        asyncio.run(crawl_site(args.url, args.max_depth, args.output_dir))
    except KeyboardInterrupt:
        print("\nCrawl cancelled by user.")
