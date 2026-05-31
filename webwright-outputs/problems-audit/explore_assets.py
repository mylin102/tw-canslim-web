import asyncio
import os
import httpx
import json
from pathlib import Path

WORKSPACE = Path(os.environ.get("WORKSPACE_DIR", "."))
SCREENSHOTS = WORKSPACE / "screenshots"
SCREENSHOTS.mkdir(parents=True, exist_ok=True)

BASE = "https://mylin102.github.io/tw-canslim-web"

async def check_url(client, path, label):
    url = f"{BASE}{path}"
    print(f"\n{'='*60}")
    print(f"Checking: {url}")
    try:
        resp = await client.get(url, follow_redirects=True, timeout=15)
        print(f"Status: {resp.status_code}")
        print(f"Content-Type: {resp.headers.get('content-type', '?')}")
        print(f"Content-Length: {len(resp.content)} bytes")
        
        if "json" in resp.headers.get("content-type", "").lower():
            try:
                data = resp.json()
                print(f"JSON Keys: {list(data.keys()) if isinstance(data, dict) else 'list/other'}")
                if isinstance(data, dict):
                    for k, v in data.items():
                        if isinstance(v, list):
                            print(f"  {k}: list of {len(v)} items")
                        elif isinstance(v, dict):
                            print(f"  {k}: dict with {list(v.keys())[:5]}...")
                        elif isinstance(v, (str, int, float)):
                            val_str = str(v)
                            print(f"  {k}: {val_str[:100]}")
                            if len(val_str) > 100:
                                print(f"    (truncated, total {len(val_str)} chars)")
            except json.JSONDecodeError as e:
                print(f"JSON PARSE ERROR: {e}")
                print(f"First 500 chars: {resp.text[:500]}")
        elif "html" in resp.headers.get("content-type", "").lower():
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text, 'html.parser')
            print(f"Title: {soup.title.string if soup.title else 'N/A'}")
            # Check for broken scripts/links
            broken = [s.get('src') for s in soup.find_all('script') if s.get('src') and '404' in resp.url.path]
            if broken:
                print(f"Potential broken scripts: {broken}")
        else:
            print(f"Content preview: {resp.text[:300]}")
            
    except httpx.HTTPStatusError as e:
        print(f"HTTP ERROR: {e.response.status_code}")
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")
    
    return resp if 'resp' in dir() else None

async def main():
    async with httpx.AsyncClient() as client:
        # Core pages
        await check_url(client, "/", "index.html")
        await check_url(client, "/index.html", "index.html explicit")
        await check_url(client, "/docs/", "docs/ directory")
        await check_url(client, "/docs/index.html", "docs/index.html")
        
        # Data files
        await check_url(client, "/docs/data.json", "data.json")
        await check_url(client, "/docs/data_light.json", "data_light.json")
        await check_url(client, "/docs/data_base.json", "data_base.json")
        await check_url(client, "/docs/data_fix.json", "data_fix.json")
        await check_url(client, "/docs/data_remote.json", "data_remote.json")
        
        # ETF & stock index
        await check_url(client, "/docs/etf_regime.json", "etf_regime.json")
        await check_url(client, "/docs/stock_index.json", "stock_index.json")
        await check_url(client, "/docs/update_summary.json", "update_summary.json")
        
        # HTML dashboards
        await check_url(client, "/docs/incremental_dashboard.html", "incremental_dashboard.html")
        await check_url(client, "/docs/test_github_pages.html", "test_github_pages.html")

        # API endpoints
        await check_url(client, "/docs/api/", "api directory")
        
        # Check for 404 pages
        await check_url(client, "/nonexistent", "404 test")

asyncio.run(main())
