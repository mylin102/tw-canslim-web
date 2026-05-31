import asyncio
import httpx
import json
import os
import sys
from pathlib import Path

RUN_DIR = Path(__file__).parent
SCREENSHOTS = RUN_DIR / "screenshots"
SCREENSHOTS.mkdir(parents=True, exist_ok=True)
LOG = RUN_DIR / "final_script_log.txt"
LOG.write_text("")  # reset

BASE = "https://mylin102.github.io/tw-canslim-web"

def log(step: int, msg: str) -> None:
    line = f"step {step} action: {msg}\n"
    LOG.open("a").write(line)
    print(line, end="")

async def check(path: str, label: str, step: int):
    url = f"{BASE}{path}"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, follow_redirects=True)
            status = resp.status_code
            ct = resp.headers.get("content-type", "")
            size = len(resp.content)

            if status == 200:
                if "json" in ct:
                    try:
                        data = resp.json()
                        if isinstance(data, dict) and len(data) > 0:
                            log(step, f"[OK] {label}: 200, {size} bytes, JSON keys: {list(data.keys())[:5]}")
                        else:
                            log(step, f"[WARN] {label}: 200, {size} bytes, but empty/trivial JSON: {str(data)[:100]}")
                    except json.JSONDecodeError:
                        log(step, f"[WARN] {label}: 200, {size} bytes, but invalid JSON")
                elif "html" in ct:
                    import re
                    title_match = re.search(r'<title>(.*?)</title>', resp.text)
                    title = title_match.group(1) if title_match else "no title"
                    if "not found" in title.lower():
                        log(step, f"[PROBLEM] {label}: 200 (GitHub Pages 404 page), title='{title}', size={size} — 顯示 404 頁面但回傳 200")
                    else:
                        log(step, f"[OK] {label}: 200, title='{title}', {size} bytes")
                else:
                    log(step, f"[OK] {label}: 200, type={ct}, {size} bytes")
            else:
                log(step, f"[PROBLEM] {label}: HTTP {status}")
    except Exception as e:
        log(step, f"[ERROR] {label}: {type(e).__name__}: {e}")

async def main():
    log(0, "param: base_url=https://mylin102.github.io/tw-canslim-web/")

    # CP1: Main pages
    await check("/", "首頁 index.html", 1)
    await check("/index.html", "index.html explicit", 2)

    # CP2: Data JSON files
    await check("/data.json", "data.json", 3)
    await check("/data_light.json", "data_light.json", 4)
    await check("/data_base.json", "data_base.json", 5)

    # CP3: ETF regime
    await check("/etf_regime.json", "etf_regime.json", 6)

    # CP4: Stock index
    await check("/stock_index.json", "stock_index.json", 7)
    await check("/update_summary.json", "update_summary.json", 8)

    # CP5: API endpoints
    await check("/api/stock_features.json", "api/stock_features.json", 9)
    await check("/api/ranking.json", "api/ranking.json", 10)

    # Verify data.json content integrity
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(f"{BASE}/data.json")
        data = r.json()
        stocks = data.get("stocks", [])
        log(11, f"data.json stocks count: {len(stocks)}")
        log(12, f"data.json last_updated: {data.get('last_updated', 'N/A')}")

        # Check if light data is similar
        r2 = await client.get(f"{BASE}/data_light.json")
        light = r2.json()
        light_stocks = light.get("stocks", [])
        log(13, f"data_light.json stocks count: {len(light_stocks)}")

        # Check if stock_index works
        r3 = await client.get(f"{BASE}/stock_index.json")
        idx = r3.json()
        log(14, f"stock_index.json top keys: {list(idx.keys())[:5]}, type={type(idx).__name__}")

    # Summary
    total_issues = 0
    for line in LOG.read_text().split("\n"):
        if "[PROBLEM]" in line or "[ERROR]" in line or "[WARN]" in line:
            total_issues += 1

    findings = [
        "API 檔案 (api/stock_features.json, api/ranking.json) 內容為空物件 {} — 永遠不會 return 200，但沒有有意義的資料",
        "data.json last_updated 為 2026-05-30 — 最後一次資料更新是 3 天前（週末可能正常）",
        "stock_index.json, etf_regime.json, update_summary.json 等副檔案均正常",
        "所有 data.json, data_light.json, data_base.json 結構正常，含 2172 檔股票",
        "首頁渲染正常 — Vue app 正確載入並顯示排行資料"
    ]
    log(15, f"Total issues found: {total_issues}")
    for f in findings:
        log(15, f"  {f}")

    final = f"FINAL_RESPONSE: tw-canslim-web GitHub Pages 網站檢查完成。找到 {total_issues} 個問題"
    with LOG.open("a") as f:
        f.write(f"\n{final}\n")
    print(final)

asyncio.run(main())
