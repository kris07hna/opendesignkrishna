#!/usr/bin/env python3
import os
import sys
import json
import asyncio
from urllib.parse import urlparse
from playwright.async_api import async_playwright, Page

# Hardcoded target URLs
HOMEPAGE_URL = (
    "https://www.amazon.in/?&tag=googhydrabk1-21&ref=pd_sl_7hz2t19t5c_e"
    "&adgrpid=155259815513&hvpone=&hvptwo=&hvadid=815461303151&hvpos="
    "&hvnetw=g&hvrand=3931857747114171464&hvqmt=e&hvdev=c&hvdvcmdl="
    "&hvlocint=&hvlocphy=9300146&hvtargid=kwd-10573980&hydadcr=14453_2462831"
    "&mcid=4c22dcdee2bf3a71b0b832c5c4ba9c17&hvocijid=3931857747114171464--"
    "&hvexpln=nav&gad_source=1"
)

PRODUCT_URL = (
    "https://www.amazon.in/Sony-Bluetooth-Headphones-Multipoint-Connectivity/dp/B0BS1RT9S2/"
    "?*encoding=UTF8&pd_rd_w=eEJum&content-id=amzn1.sym.b01ec959-5d64-4319-9228-31ffe490fcf3"
    "&pf_rd_p=b01ec959-5d64-4319-9228-31ffe490fcf3&pf_rd_r=DT2KPYF5Y1YFMRBPBEDF"
    "&pd_rd_wg=lN4J0&pd_rd_r=3133113c-1840-46ab-9723-97d3c3c797d9"
    "&ref*=pd_hp_d_btf_ls_gwc_pc_en2_&th=1"
)

OUTPUT_DIR = "screenshots"
os.makedirs(OUTPUT_DIR, exist_ok=True)

async def is_auth_page(page: Page) -> bool:
    """Detects if we are on a login or sign-in page."""
    # 1. Check for password input fields
    if await page.locator("input[type='password']").count() > 0:
        return True
    
    # 2. Check for typical Amazon sign-in selectors
    amazon_auth_selectors = ["#ap_email", "#ap_password", "input[name='signIn']", "form[name='signIn']"]
    for sel in amazon_auth_selectors:
        if await page.locator(sel).count() > 0:
            return True

    # 3. Check for keywords in URL or title
    url = page.url.lower()
    title = (await page.title()).lower()
    if "signin" in url or "login" in url or "sign in" in title or "log in" in title:
        return True

    return False

async def run_flow():
    print("=" * 60)
    print("Starting Amazon Sony Headphones Purchase Flow")
    print("=" * 60)

    flow_map = []
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        # Using realistic browser context
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        )
        page = await context.new_page()
        page.set_default_timeout(20000)

        # -------------------------------------------------------------
        # STEP 1: Load Homepage
        # -------------------------------------------------------------
        print("\nStep 1: Navigating to Amazon.in Homepage...")
        await page.goto(HOMEPAGE_URL, wait_until="domcontentloaded")
        await page.wait_for_timeout(2000) # Let page load static assets
        
        # Take Homepage Screenshot
        homepage_screenshot = os.path.join(OUTPUT_DIR, "1_amazon_homepage.png")
        await page.screenshot(path=homepage_screenshot, full_page=True)
        print(f"Screenshot saved: {homepage_screenshot}")
        flow_map.append({"step": 1, "name": "Amazon Homepage", "url": page.url, "screenshot": homepage_screenshot})

        # -------------------------------------------------------------
        # STEP 2: Load Product Page
        # -------------------------------------------------------------
        print("\nStep 2: Navigating to Sony Headphones Product Page...")
        await page.goto(PRODUCT_URL, wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)

        # Check for immediate auth gate or CAPTCHA
        if await is_auth_page(page):
            print("[AUTH DETECTED] Reached authentication page immediately on product page.")
            await browser.close()
            return

        # Take Product Page Screenshot
        product_screenshot = os.path.join(OUTPUT_DIR, "2_product_page.png")
        await page.screenshot(path=product_screenshot, full_page=True)
        print(f"Screenshot saved: {product_screenshot}")
        flow_map.append({"step": 2, "name": "Sony Headphones Product Page", "url": page.url, "screenshot": product_screenshot})

        # -------------------------------------------------------------
        # STEP 3: Click Add to Cart
        # -------------------------------------------------------------
        print("\nStep 3: Clicking 'Add to Cart'...")
        
        # Selector options for add to cart
        add_to_cart_selectors = [
            "#add-to-cart-button",
            "input[name='submit.add-to-cart']",
            "#add-to-cart-button-ubb"
        ]
        
        cart_clicked = False
        for selector in add_to_cart_selectors:
            if await page.locator(selector).count() > 0:
                print(f"Clicking Add to Cart button: {selector}")
                await page.click(selector)
                cart_clicked = True
                break
        
        if not cart_clicked:
            print("Could not find 'Add to Cart' button. Proceeding directly to checkout/cart page...")
            await page.goto("https://www.amazon.in/gp/cart/view.html")
            
        await page.wait_for_timeout(3000)

        # Check if auth gate was triggered by add-to-cart
        if await is_auth_page(page):
            print("[AUTH DETECTED] Reached authentication gate after adding to cart.")
            print("Stopping screenshots and exiting workflow.")
            flow_map.append({"step": 3, "name": "Auth Gate (Sign-In)", "url": page.url, "screenshot": None, "auth_detected": True})
            await browser.close()
            save_results(flow_map)
            return

        # Take Cart Added Screenshot
        cart_screenshot = os.path.join(OUTPUT_DIR, "3_cart_added.png")
        await page.screenshot(path=cart_screenshot, full_page=True)
        print(f"Screenshot saved: {cart_screenshot}")
        flow_map.append({"step": 3, "name": "Added to Cart/Confirmation", "url": page.url, "screenshot": cart_screenshot})

        # -------------------------------------------------------------
        # STEP 4: Proceed to Checkout
        # -------------------------------------------------------------
        print("\nStep 4: Attempting to Proceed to Checkout...")
        
        checkout_selectors = [
            "input[name='proceedToRetailCheckout']",
            "#sc-buy-box-ptc-button",
            "#hlb-ptc-btn-native",
            "#attach-sidesheet-checkout-button"
        ]
        
        checkout_clicked = False
        for selector in checkout_selectors:
            if await page.locator(selector).count() > 0:
                print(f"Clicking Checkout button: {selector}")
                await page.click(selector)
                checkout_clicked = True
                break
                
        if not checkout_clicked:
            # Fallback direct cart checkout URL
            print("Redirecting to checkout URL directly...")
            await page.goto("https://www.amazon.in/gp/checkout/html/select.html")

        await page.wait_for_timeout(4000)

        # -------------------------------------------------------------
        # STEP 5: Verify Auth Gate (Sign-In page)
        # -------------------------------------------------------------
        is_auth = await is_auth_page(page)
        if is_auth:
            print("[AUTH DETECTED] Reached the Amazon checkout Sign-In page.")
            print("Stopping screenshots automatically to preserve security/credentials.")
            flow_map.append({"step": 4, "name": "Auth Gate (Sign-In Page)", "url": page.url, "screenshot": None, "auth_detected": True})
        else:
            # If not gated
            checkout_screenshot = os.path.join(OUTPUT_DIR, "4_checkout_page.png")
            await page.screenshot(path=checkout_screenshot, full_page=True)
            print(f"Screenshot saved: {checkout_screenshot}")
            flow_map.append({"step": 4, "name": "Checkout Page", "url": page.url, "screenshot": checkout_screenshot})

        await browser.close()
        
    save_results(flow_map)

def save_results(flow_map):
    results_file = os.path.join(OUTPUT_DIR, "amazon_flow_map.json")
    with open(results_file, "w", encoding="utf-8") as f:
        json.dump(flow_map, f, indent=2)
    
    print("\n" + "=" * 60)
    print("AMAZON USER FLOW MAP COMPLETE")
    print(f"Flow details saved to: {results_file}")
    print(f"Screenshots saved to: {OUTPUT_DIR}/")
    print("=" * 60)
    print("\nWorkflow Step Sequence:")
    for step in flow_map:
        screenshot_status = step.get('screenshot') or 'Skipped due to Auth Gate'
        print(f" Step {step['step']}: {step['name']}")
        print(f"   URL: {step['url']}")
        print(f"   Screenshot: {screenshot_status}")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(run_flow())
