import asyncio
import os
from pathlib import Path

from playwright.async_api import async_playwright

WORKSPACE = Path(os.environ.get("WORKSPACE_DIR", "."))
SCREENSHOTS = WORKSPACE / "screenshots"
SCREENSHOTS.mkdir(parents=True, exist_ok=True)

async def main():
    console_messages = []
    
    async with async_playwright() as playwright:
        browser = await playwright.firefox.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1280, "height": 1800})
        page = await context.new_page()
        
        # Capture all console messages
        page.on("console", lambda msg: console_messages.append(f"[{msg.type}] {msg.text}"))
        page.on("pageerror", lambda err: console_messages.append(f"[PAGE_ERROR] {err}"))
        page.on("requestfailed", lambda req: console_messages.append(f"[REQUEST_FAILED] {req.url} - {req.failure}"))

        await page.goto("https://mylin102.github.io/tw-canslim-web/", wait_until="networkidle", timeout=30000)
        await asyncio.sleep(5)  # Let JS finish loading and rendering
        
        await page.screenshot(path=str(SCREENSHOTS / "explore_2_full_load.png"))
        
        print("URL:", page.url)
        print("TITLE:", await page.title())
        
        print("\n--- CONSOLE MESSAGES ---")
        for msg in console_messages:
            print(msg)
        
        print(f"\nTotal console messages: {len(console_messages)}")
        
        # Check network requests for data files
        print("\n--- CHECK DATA IN APP ---")
        stock_list = await page.locator(".stock-list, .stock-item, [class*='stock'], table, .leader-card").all()
        print(f"Found {len(stock_list)} stock-related elements")
        
        # Look for the body content
        body_text = await page.locator("body").inner_text()
        print(f"\nBody text length: {len(body_text)}")
        
        # Check for visible data - look for stock numbers
        import re
        stock_codes = re.findall(r'\b\d{4}\b', body_text)
        print(f"Stock codes found: {stock_codes[:20]}")
        
        # Check if data.json actually works
        import httpx
        r = httpx.get("https://mylin102.github.io/tw-canslim-web/data.json", timeout=10)
        data = r.json()
        print(f"\ndata.json: {len(data)} top-level keys: {list(data.keys()) if isinstance(data, dict) else type(data)}")
        if isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, list):
                    print(f"  {k}: {len(v)} items")
                    if len(v) > 0 and isinstance(v[0], dict):
                        print(f"    sample keys: {list(v[0].keys())[:10]}")
        
        await browser.close()

asyncio.run(main())
