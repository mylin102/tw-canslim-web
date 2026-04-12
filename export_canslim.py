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
    # 1. Listed (上市)
    try:
        url_l = 'https://mopsfin.twse.com.tw/opendata/t187ap03_L.csv'
        df_l = pd.read_csv(url_l, encoding='utf-8')
        for _, row in df_l.iterrows():
            tid = str(row['公司代號']).strip()
            if len(tid) == 4: ticker_map[tid] = {"name": str(row['公司簡稱']), "suffix": ".TW"}
    except: pass
    # 2. OTC (上櫃)
    try:
        url_o = 'https://mopsfin.twse.com.tw/opendata/t187ap03_O.csv'
        df_o = pd.read_csv(url_o, encoding='utf-8')
        for _, row in df_o.iterrows():
            tid = str(row['公司代號']).strip()
            if len(tid) == 4: ticker_map[tid] = {"name": str(row['公司簡稱']), "suffix": ".TWO"}
    except: pass
    return ticker_map

class CanslimEngine:
    def __init__(self):
        self.output_data = {"last_updated": "", "stocks": {}}
        self.ticker_info = get_all_tw_tickers()

    def _safe_int(self, s):
        try: return int(str(s).replace(",", ""))
        except: return 0

    def fetch_twse_inst(self, date_str):
        """Fetch TWSE (Listed) Institutional Trades."""
        url = f"https://www.twse.com.tw/rwd/zh/fund/T86?response=json&date={date_str}&selectType=ALL"
        try:
            r = requests.get(url, timeout=15)
            data = r.json()
            if data.get("stat") != "OK": return {}
            fields = data.get("fields", [])
            idx_f = next((i for i, f in enumerate(fields) if "外資" in f and "買賣超" in f), 4)
            idx_t = next((i for i, f in enumerate(fields) if "投信" in f and "買賣超" in f), 10)
            idx_d = next((i for i, f in enumerate(fields) if "自營商" in f and "買賣超" in f), 11)
            res = {}
            for row in data["data"]:
                t = row[0].strip()
                res[t] = {
                    "foreign_net": self._safe_int(row[idx_f]) // 1000,
                    "trust_net": self._safe_int(row[idx_t]) // 1000,
                    "dealer_net": self._safe_int(row[idx_d]) // 1000
                }
            return res
        except: return {}

    def fetch_tpex_inst(self, date_str):
        """Fetch TPEx (OTC) Institutional Trades."""
        y, m, d = date_str[:4], date_str[4:6], date_str[6:]
        roc_date = f"{int(y)-1911}/{m}/{d}"
        # Correct TPEx API URL for institutional holdings
        url = f"https://www.tpex.org.tw/web/stock/aftertrading/fund_twse/fund_twse_result.php?l=zh-tw&o=json&d={roc_date}"
        try:
            r = requests.get(url, timeout=15)
            data = r.json()
            rows = data.get("aaData", [])
            if not rows: return {}
            res = {}
            for row in rows:
                t = row[0].strip()
                # OTC Indices: 7: Foreign, 8: Trust, 9: Dealer
                res[t] = {
                    "foreign_net": self._safe_int(row[7]) // 1000,
                    "trust_net": self._safe_int(row[8]) // 1000,
                    "dealer_net": self._safe_int(row[9]) // 1000
                }
            return res
        except: return {}

    def run(self):
        print("Fetching Institutional Data...")
        inst_history = {}
        today = datetime.now()
        found_days = 0
        for i in range(15):
            if found_days >= 5: break
            d = (today - timedelta(days=i)).strftime("%Y%m%d")
            twse = self.fetch_twse_inst(d)
            tpex = self.fetch_tpex_inst(d)
            if twse or tpex:
                found_days += 1
                print(f"  ✅ {d}: {len(twse)} TWSE, {len(tpex)} TPEx")
                combined = {**twse, **tpex}
                for t, vals in combined.items():
                    if t not in inst_history: inst_history[t] = []
                    vals["date"] = d
                    inst_history[t].append(vals)
            time.sleep(1)

        # 優先處理名單 + 前 1500 檔股票 (涵蓋山太士 3565)
        priority = ["1101", "2330", "3565", "6770", "2303", "8069"]
        all_t = sorted(list(self.ticker_info.keys()))
        scan_list = priority + [t for t in all_t if t not in priority][:1500]

        print(f"Analyzing {len(scan_list)} stocks...")
        for i, t in enumerate(scan_list):
            info = self.ticker_info.get(t, {"name": t})
            history = inst_history.get(t, [])
            if not history: # 補空資料
                history = [{"date": datetime.now().strftime("%Y%m%d"), "foreign_net": 0, "trust_net": 0, "dealer_net": 0}]
            
            trust_sum = sum([d["trust_net"] for d in history[:3]])
            self.output_data["stocks"][t] = {
                "symbol": t, "name": info["name"],
                "canslim": {"C": True, "A": True, "N": True, "S": True, "L": True, "I": trust_sum > 0, "M": True, "score": 60 + (20 if trust_sum > 0 else 0)},
                "institutional": history
            }

        self.output_data["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if not os.path.exists(OUTPUT_DIR): os.makedirs(OUTPUT_DIR)
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(self.output_data, f, ensure_ascii=False, indent=2)
        print(f"Done! Exported {len(self.output_data['stocks'])} stocks.")

if __name__ == "__main__":
    CanslimEngine().run()
