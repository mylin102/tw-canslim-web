
import requests
import json
import os
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ETF_CACHE_FILE = "etf_cache.json"

def sync_etf_list():
    """Fetch all Taiwan ETFs (Listed & OTC) and save to local JSON."""
    etf_map = {}

    # 1. Fetch TWSE (Listed) ETFs
    try:
        logger.info("Fetching Listed ETFs from TWSE...")
        # Official TWSE ETF list JSON
        url = "https://www.twse.com.tw/rwd/zh/ETF/list?response=json"
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            data = response.json()
            # TWSE returns data in 'data' field, rows contain code, name, etc.
            rows = data.get('data', [])
            for row in rows:
                if len(row) >= 3:
                    # TWSE ETF JSON: [上市日期, 證券代號, 證券簡稱, ...]
                    code = str(row[1]).strip()
                    name = str(row[2]).strip()
                    
                    etf_map[code] = {
                        "name": name,
                        "market": "TWSE",
                        "type": "ETF"
                    }
            logger.info(f"Added {len(rows)} listed ETFs")
    except Exception as e:
        logger.error(f"Failed to fetch Listed ETFs: {e}")

    # 2. Fetch TPEx (OTC) ETFs
    try:
        logger.info("Fetching OTC ETFs from TPEx...")
        # Improved URL from reference analysis (Daily quotes for all securities)
        # Category 01 is usually Index Stocks/ETFs
        url = "https://www.tpex.org.tw/web/stock/aftertrading/otc_quotes_no1430/otc_quotes_no1430_result.php?l=zh-tw&o=json"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            data = response.json()
            rows = data.get('aaData', [])
            count = 0
            for row in rows:
                if len(row) < 2: continue
                code = row[0].strip()
                name = row[1].strip()
                
                # Logic: In TPEx, ETFs are usually listed in this table. 
                # We can filter by code length (5+ for bonds/complex) or specific start patterns.
                # Common patterns: 007XX, 008XX, 009XX, or ending with B/U/R
                is_etf_code = (
                    len(code) >= 5 or 
                    code.startswith('00') or 
                    code.endswith(('B', 'U', 'R'))
                )
                
                if is_etf_code:
                    etf_map[code] = {
                        "name": name,
                        "market": "TPEx",
                        "type": "ETF"
                    }
                    count += 1
            logger.info(f"Added {count} OTC ETFs")
    except Exception as e:
        logger.error(f"Failed to fetch OTC ETFs: {e}")

    # Save to local file
    with open(ETF_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_count": len(etf_map),
            "etfs": etf_map
        }, f, ensure_ascii=False, indent=2)
    
    logger.info(f"Successfully created {ETF_CACHE_FILE} with {len(etf_map)} entries.")

if __name__ == "__main__":
    sync_etf_list()
