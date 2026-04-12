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
# In production, this would be a full list. For prototype, we use top stocks.
TICKERS_TO_SCAN = ["2330", "2317", "2454", "2308", "2382", "3711", "2412", "2881", "2882", "2303", 
                   "3034", "2357", "2603", "3231", "2301", "2408", "2886", "2891", "2884", "5880", "1590"]

class CanslimEngine:
    def __init__(self):
        self.output_data = {
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "stocks": {}
        }

    def fetch_institutional_trades(self, days=10):
        """Fetch TWSE institutional trades for the last N days."""
        history = {}
        today = datetime.now()
        count = 0
        for i in range(days + 5): # buffer for holidays
            if count >= days: break
            d = (today - timedelta(days=i)).strftime("%Y%m%d")
            url = f"https://www.twse.com.tw/rwd/zh/fund/T86?response=json&date={d}&selectType=ALL"
            try:
                r = requests.get(url, timeout=10)
                data = r.json()
                if data.get("stat") != "OK": continue
                
                for row in data["data"]:
                    ticker = row[0].strip()
                    if ticker not in TICKERS_TO_SCAN: continue
                    
                    if ticker not in history: history[ticker] = []
                    history[ticker].append({
                        "date": d,
                        "foreign_net": int(row[4].replace(",", "")) // 1000,
                        "trust_net": int(row[10].replace(",", "")) // 1000,
                        "dealer_net": int(row[11].replace(",", "")) // 1000
                    })
                count += 1
                time.sleep(1) # respect TWSE
            except:
                continue
        return history

    def analyze_stock(self, ticker, inst_history):
        """Perform CANSLIM analysis for a single stock."""
        try:
            full_ticker = f"{ticker}.TW"
            stock = yf.Ticker(full_ticker)
            hist = stock.history(period="1y")
            if hist.empty: return None

            info = stock.info
            price = hist['Close'].iloc[-1]
            
            # Simplified CANSLIM Logic based on MY_2026_V1.0
            # Note: C and A usually require FinMind API, mocking pass/fail for demo 
            # while focusing on I (Institutional)
            
            # [I] Institutional - Pass if Trust net buy in last 5 days > 0
            trust_recent = sum([day['trust_net'] for day in inst_history[:5]]) if inst_history else 0
            is_i_pass = trust_recent > 0
            
            # [N] New Highs - within 15% of 52w high
            high_52w = hist['Close'].max()
            is_n_pass = (price / high_52w) >= 0.85
            
            # [S] Supply/Demand - volume spike > 1.2x of 50d average
            avg_vol_50d = hist['Volume'].rolling(window=50).mean().iloc[-1]
            is_s_pass = (hist['Volume'].iloc[-1] / avg_vol_50d) > 1.2 if avg_vol_50d > 0 else False

            # [L] Leader - Price above 200d MA
            ma_200 = hist['Close'].rolling(window=200).mean().iloc[-1]
            is_l_pass = price > ma_200 if not pd.isna(ma_200) else False

            # Mock C and A for now (requires FinMind token/logic)
            is_c_pass = True # placeholder
            is_a_pass = True # placeholder
            
            score = sum([is_c_pass, is_a_pass, is_n_pass, is_s_pass, is_l_pass, is_i_pass]) * 15 + 10

            return {
                "symbol": ticker,
                "name": info.get("shortName", f"股票 {ticker}"),
                "canslim": {
                    "C": bool(is_c_pass), "A": bool(is_a_pass), "N": bool(is_n_pass), 
                    "S": bool(is_s_pass), "L": bool(is_l_pass), "I": bool(is_i_pass),
                    "M": True, "score": int(score)
                },
                "institutional": inst_history
            }
        except Exception as e:
            print(f"Error analyzing {ticker}: {e}")
            return None

    def run(self):
        print("Fetching Institutional Data...")
        all_inst_history = self.fetch_institutional_trades(days=10)
        
        print(f"Analyzing {len(TICKERS_TO_SCAN)} stocks...")
        for ticker in TICKERS_TO_SCAN:
            print(f"Processing {ticker}...")
            result = self.analyze_stock(ticker, all_inst_history.get(ticker, []))
            if result:
                self.output_data["stocks"][ticker] = result
        
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(self.output_data, f, ensure_ascii=False, indent=2)
        print(f"Exported data to {DATA_FILE}")

if __name__ == "__main__":
    engine = CanslimEngine()
    engine.run()
