import asyncio
import os
from pathlib import Path

from playwright.async_api import async_playwright

WORKSPACE = Path(os.environ.get("WORKSPACE_DIR", "."))
SCREENSHOTS = WORKSPACE / "screenshots"
SCREENSHOTS.mkdir(parents=True, exist_ok=True)

async def main():
    async with async_playwright() as playwright:
        browser = await playwright.firefox.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1280, "height": 1800})
        page = await context.new_page()

        # CP1: main page
        await page.goto("https://mylin102.github.io/tw-canslim-web/", wait_until="domcontentloaded", timeout=30000)
        await page.screenshot(path=str(SCREENSHOTS / "explore_1_main_page.png"))

        print("URL:", page.url)
        print("TITLE:", await page.title())

        # Check for console errors
        page.on("console", lambda msg: print(f"CONSOLE [{msg.type}]: {msg.text}"))

        # Wait a bit for JS to load
        await asyncio.sleep(3)

        # Get page content
        content = await page.content()
        print("PAGE CONTENT length:", len(content))

        # Check for any visible error messages on page
        body_text = await page.locator("body").inner_text()
        print("BODY TEXT (first 2000):", body_text[:2000])

        # ARIA snapshot
        snapshot = await page.locator("body").aria_snapshot()
        print("ARIA:", snapshot[:3000] if snapshot else "none")

        await browser.close()

asyncio.run(main())
