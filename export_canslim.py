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
    """Fetch the full list of TWSE tickers and names from MOPS."""
    print("Fetching full TWSE ticker list...")
    try:
        url = 'https://mopsfin.twse.com.tw/opendata/t187ap03_L.csv'
        df = pd.read_csv(url, encoding='utf-8')
        # Only take common stocks (4 digits)
        df = df[df['公司代號'].astype(str).str.len() == 4]
        ticker_map = {str(row['公司代號']): str(row['公司簡稱']) for _, row in df.iterrows()}
        return ticker_map
    except Exception as e:
        print(f"Error fetching tickers: {e}")
        return {"2330": "台積電", "2317": "鴻海", "2454": "聯發科", "1590": "亞德客-KY"}

class CanslimEngine:
    def __init__(self):
        self.output_data = {
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "stocks": {}
        }
        self.ticker_map = get_all_tw_tickers()

    def fetch_institutional_trades(self, days=5):
        """Fetch TWSE institutional trades for the last N days."""
        history = {}
        today = datetime.now()
        count = 0
        for i in range(days + 5):
            if count >= days: break
            d = (today - timedelta(days=i)).strftime("%Y%m%d")
            url = f"https://www.twse.com.tw/rwd/zh/fund/T86?response=json&date={d}&selectType=ALL"
            try:
                r = requests.get(url, timeout=10)
                data = r.json()
                if data.get("stat") != "OK": continue
                
                for row in data["data"]:
                    ticker = row[0].strip()
                    if ticker not in self.ticker_map: continue
                    
                    if ticker not in history: history[ticker] = []
                    history[ticker].append({
                        "date": d,
                        "foreign_net": int(row[4].replace(",", "")) // 1000,
                        "trust_net": int(row[10].replace(",", "")) // 1000,
                        "dealer_net": int(row[11].replace(",", "")) // 1000
                    })
                count += 1
                print(f"  Loaded institutional data for {d}")
                time.sleep(1)
            except: continue
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
            
            # [I] Institutional - Pass if Trust net buy in last 5 days > 0
            trust_recent = sum([day['trust_net'] for day in inst_history[:5]]) if inst_history else 0
            is_i_pass = trust_recent > 0
            
            # [N] New Highs - within 15% of 52w high
            high_52w = hist['Close'].max()
            is_n_pass = (price / high_52w) >= 0.85
            
            # [S] Supply/Demand
            avg_vol_50d = hist['Volume'].rolling(window=50).mean().iloc[-1]
            is_s_pass = (hist['Volume'].iloc[-1] / avg_vol_50d) > 1.2 if avg_vol_50d > 0 else False

            # [L] Leader
            ma_200 = hist['Close'].rolling(window=200).mean().iloc[-1]
            is_l_pass = price > ma_200 if not pd.isna(ma_200) else False

            is_c_pass, is_a_pass = True, True # Placeholder
            
            score = sum([is_c_pass, is_a_pass, is_n_pass, is_s_pass, is_l_pass, is_i_pass]) * 15 + 10

            return {
                "symbol": ticker,
                "name": self.ticker_map.get(ticker, ticker),
                "canslim": {
                    "C": bool(is_c_pass), "A": bool(is_a_pass), "N": bool(is_n_pass), 
                    "S": bool(is_s_pass), "L": bool(is_l_pass), "I": bool(is_i_pass),
                    "M": True, "score": int(score)
                },
                "institutional": inst_history
            }
        except: return None

    def run(self):
        print("Fetching Institutional Data...")
        all_inst_history = self.fetch_institutional_trades(days=5)
        
        # Scan all tickers from map (limited to first 300 for GitHub Action speed)
        tickers = list(self.ticker_map.keys())[:300]
        print(f"Analyzing {len(tickers)} stocks...")
        
        for ticker in tickers:
            result = self.analyze_stock(ticker, all_inst_history.get(ticker, []))
            if result:
                self.output_data["stocks"][ticker] = result
        
        if not os.path.exists(OUTPUT_DIR): os.makedirs(OUTPUT_DIR)
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(self.output_data, f, ensure_ascii=False, indent=2)
        print(f"Exported {len(self.output_data['stocks'])} stocks to {DATA_FILE}")

if __name__ == "__main__":
    engine = CanslimEngine()
    engine.run()
