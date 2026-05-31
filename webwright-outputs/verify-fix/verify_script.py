import asyncio
import httpx
import json
import os
from pathlib import Path

WORKSPACE = Path(os.environ.get("WORKSPACE_DIR", "."))
SCREENSHOTS = WORKSPACE / "screenshots"
SCREENSHOTS.mkdir(parents=True, exist_ok=True)

BASE = "https://mylin102.github.io/tw-canslim-web"

async def main():
    findings = []
    async with httpx.AsyncClient(timeout=30) as client:
        # CP1: stock_features.json
        r = await client.get(f"{BASE}/api/stock_features.json")
        data = r.json()
        if isinstance(data, dict) and len(data) > 0:
            sample = dict(list(data.items())[:3])
            findings.append(f"[OK] api/stock_features.json: {len(data)} entries. Samples: {json.dumps(sample, ensure_ascii=False)[:300]}")
        else:
            findings.append(f"[PROBLEM] api/stock_features.json still empty: {data}")

        # CP2: ranking.json
        r = await client.get(f"{BASE}/api/ranking.json")
        data = r.json()
        if isinstance(data, dict) and len(data) > 0:
            sample = dict(list(data.items())[:3])
            findings.append(f"[OK] api/ranking.json: {len(data)} entries. Samples: {json.dumps(sample, ensure_ascii=False)[:300]}")
        else:
            findings.append(f"[PROBLEM] api/ranking.json still empty: {data}")

        # CP3: data.json
        r = await client.get(f"{BASE}/data.json")
        data = r.json()
        stocks = data.get("stocks", {})
        findings.append(f"[OK] data.json: {len(stocks)} stocks, last_updated={data.get('last_updated','?')}")

        # CP3: stock_index.json
        r = await client.get(f"{BASE}/stock_index.json")
        idx = r.json()
        idx_stocks = idx.get("stocks", {})
        findings.append(f"[OK] stock_index.json: {len(idx_stocks)} index entries")

        # CP4: main page
        r = await client.get(f"{BASE}/")
        if "台股 CANSLIM 戰情室" in r.text:
            findings.append(f"[OK] 首頁載入正常 (200, {len(r.content)} bytes)")
        else:
            findings.append(f"[PROBLEM] 首頁異常")

    print("\n".join(findings))
    final = f"FINAL_RESPONSE: {'所有檢查通過' if all('[OK]' in f for f in findings) else '有問題需修復'}"
    print(f"\n{final}")

asyncio.run(main())
