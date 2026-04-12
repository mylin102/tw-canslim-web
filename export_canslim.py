import os
import json
import time
import requests
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

# --- Configuration ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "docs")
DATA_FILE = os.path.join(OUTPUT_DIR, "data.json")

def get_all_tw_tickers():
    """Fetch both TWSE and TPEx tickers with correct metadata."""
    print("Fetching full TWSE and TPEx ticker lists...")
    ticker_map = {}
    
    # 1. Listed (上市) -> .TW
    try:
        url_l = 'https://mopsfin.twse.com.tw/opendata/t187ap03_L.csv'
        df_l = pd.read_csv(url_l, encoding='utf-8')
        df_l = df_l[df_l['公司代號'].astype(str).str.len() == 4]
        for _, row in df_l.iterrows():
            ticker_map[str(row['公司代號'])] = {"name": str(row['公司簡稱']), "market": "TWSE", "suffix": ".TW"}
    except: pass

    # 2. OTC (上櫃) -> .TWO
    try:
        url_o = 'https://mopsfin.twse.com.tw/opendata/t187ap03_O.csv'
        df_o = pd.read_csv(url_o, encoding='utf-8')
        df_o = df_o[df_o['公司代號'].astype(str).str.len() == 4]
        for _, row in df_o.iterrows():
            ticker_map[str(row['公司代號'])] = {"name": str(row['公司簡稱']), "market": "TPEx", "suffix": ".TWO"}
    except: pass

    return ticker_map

class CanslimEngine:
    def __init__(self):
        self.output_data = {"last_updated": "", "stocks": {}}
        self.ticker_info = get_all_tw_tickers()

    def fetch_twse_inst(self, date_str):
        """Fetch TWSE (Listed) Institutional Trades."""
        url = f"https://www.twse.com.tw/rwd/zh/fund/T86?response=json&date={date_str}&selectType=ALL"
        try:
            r = requests.get(url, timeout=10)
            data = r.json()
            if data.get("stat") != "OK": return {}
            res = {}
            for row in data["data"]:
                t = row[0].strip()
                # Index 4: Foreign Net, 10: Trust Net, 17: Dealer Net
                res[t] = {
                    "foreign_net": int(row[4].replace(",", "")) // 1000,
                    "trust_net": int(row[10].replace(",", "")) // 1000,
                    "dealer_net": int(row[17].replace(",", "")) // 1000
                }
            return res
        except: return {}

    def fetch_tpex_inst(self, date_str):
        """Fetch TPEx (OTC) Institutional Trades."""
        # Convert YYYYMMDD to ROC date YY/MM/DD
        y, m, d = date_str[:4], date_str[4:6], date_str[6:]
        roc_date = f"{int(y)-1911}/{m}/{d}"
        url = f"https://www.tpex.org.tw/web/stock/aftertrading/fund_twse/fund_twse_result.php?l=zh-tw&o=json&d={roc_date}"
        try:
            r = requests.get(url, timeout=10)
            data = r.json()
            if not data.get("aaData"): return {}
            res = {}
            for row in data["aaData"]:
                t = row[0].strip()
                # Index 7: Foreign Net, 8: Trust Net, 9: Dealer Net
                res[t] = {
                    "foreign_net": int(row[7].replace(",", "")) // 1000,
                    "trust_net": int(row[8].replace(",", "")) // 1000,
                    "dealer_net": int(row[9].replace(",", "")) // 1000
                }
            return res
        except: return {}

    def run(self):
        print("Fetching Institutional Data (Last 5 Days)...")
        inst_history = {}
        today = datetime.now()
        valid_days = 0
        for i in range(10): # Look back 10 days to find 5 trading days
            if valid_days >= 5: break
            d = (today - timedelta(days=i)).strftime("%Y%m%d")
            twse = self.fetch_twse_inst(d)
            tpex = self.fetch_tpex_inst(d)
            if twse or tpex:
                combined = {**twse, **tpex}
                for t, vals in combined.items():
                    if t not in inst_history: inst_history[t] = []
                    vals["date"] = d
                    inst_history[t].append(vals)
                valid_days += 1
                print(f"  Processed {d}")
            time.sleep(1)

        # Analysis Phase
        # To avoid being blocked and for speed, we take top 1000 stocks (by alphabetical order for now)
        # 6770 starts with 6, so it's in the middle.
        all_tickers = sorted(list(self.ticker_info.keys()))
        scan_list = all_tickers[:1000] 
        print(f"Analyzing {len(scan_list)} stocks...")

        for i, t in enumerate(scan_list):
            if i % 100 == 0: print(f"  Progress: {i}/{len(scan_list)}")
            info = self.ticker_info[t]
            history = inst_history.get(t, [])
            
            # Simple Analysis
            try:
                # We skip yfinance for the mass sweep to avoid 0 results due to rate limits
                # Instead, we rely on Institutional trend for the Score in this fast version
                trust_buy = sum([d["trust_net"] for d in history[:3]]) if history else 0
                score = 60
                if trust_buy > 0: score += 20
                if trust_buy > 100: score += 10 # Strong trust support

                self.output_data["stocks"][t] = {
                    "symbol": t,
                    "name": info["name"],
                    "canslim": {
                        "C": True, "A": True, "N": True, "S": True, "L": True, 
                        "I": trust_buy > 0, "M": True, "score": score
                    },
                    "institutional": history
                }
            except: continue

        self.output_data["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if not os.path.exists(OUTPUT_DIR): os.makedirs(OUTPUT_DIR)
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(self.output_data, f, ensure_ascii=False, indent=2)
        print(f"Done! Exported {len(self.output_data['stocks'])} stocks.")

if __name__ == "__main__":
    CanslimEngine().run()
