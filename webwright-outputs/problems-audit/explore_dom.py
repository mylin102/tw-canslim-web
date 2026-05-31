import asyncio
import os
from pathlib import Path

from playwright.async_api import async_playwright

WORKSPACE = Path(os.environ.get("WORKSPACE_DIR", "."))
SCREENSHOTS = WORKSPACE / "screenshots"
SCREENSHOTS.mkdir(parents=True, exist_ok=True)

async def main():
    console_messages = []
    failed_requests = []
    
    async with async_playwright() as playwright:
        browser = await playwright.firefox.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1280, "height": 1800})
        page = await context.new_page()
        
        page.on("console", lambda msg: console_messages.append(f"[{msg.type}] {msg.text[:200]}"))
        page.on("pageerror", lambda err: console_messages.append(f"[PAGE_ERROR] {err}"))
        page.on("requestfailed", lambda req: failed_requests.append(f"{req.url} - {req.failure}"))

        await page.goto("https://mylin102.github.io/tw-canslim-web/", wait_until="domcontentloaded", timeout=30000)
        
        # Wait longer for Vue to mount and fetch data
        await asyncio.sleep(8)
        
        await page.screenshot(path=str(SCREENSHOTS / "explore_3_after_load.png"))
        
        print("URL:", page.url)
        print("TITLE:", await page.title())
        
        # Filter out font warnings, focus on actual issues
        print("\n=== PAGE ERRORS ===")
        for msg in console_messages:
            if msg.startswith("[PAGE_ERROR") or msg.startswith("[error") or "404" in msg or "Failed" in msg or "NetworkError" in msg:
                print(msg)
        
        print("\n=== FAILED REQUESTS ===")
        for req in failed_requests:
            print(req)
        
        # Check the DOM state
        print("\n=== DOM STATE ===")
        has_leaders = await page.locator("text=今日強勢領頭羊").count()
        has_stocks = await page.locator("text=台積電").count()
        has_search = await page.locator("text=個股查詢").count()
        print(f"Has '今日強勢領頭羊': {has_leaders}")
        print(f"Has '台積電': {has_stocks}")
        print(f"Has '個股查詢': {has_search}")
        
        body = await page.locator("body").inner_text()
        print(f"\nBody text lines ({len(body)} chars):")
        for line in body.split('\n'):
            line = line.strip()
            if line:
                print(f"  | {line}")
        
        await browser.close()

asyncio.run(main())
