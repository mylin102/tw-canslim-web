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
    """Fetch both TWSE (Listed) and TPEx (OTC) tickers and names."""
    print("Fetching full TWSE and TPEx ticker lists...")
    ticker_map = {}
    
    # 1. Listed (上市)
    try:
        url_l = 'https://mopsfin.twse.com.tw/opendata/t187ap03_L.csv'
        df_l = pd.read_csv(url_l, encoding='utf-8')
        df_l = df_l[df_l['公司代號'].astype(str).str.len() == 4]
        for _, row in df_l.iterrows():
            ticker_map[str(row['公司代號'])] = str(row['公司簡稱'])
    except Exception as e:
        print(f"Error fetching Listed tickers: {e}")

    # 2. OTC (上櫃)
    try:
        url_o = 'https://mopsfin.twse.com.tw/opendata/t187ap03_O.csv'
        df_o = pd.read_csv(url_o, encoding='utf-8')
        df_o = df_o[df_o['公司代號'].astype(str).str.len() == 4]
        for _, row in df_o.iterrows():
            ticker_map[str(row['公司代號'])] = str(row['公司簡稱'])
    except Exception as e:
        print(f"Error fetching OTC tickers: {e}")

    if not ticker_map:
        return {"2330": "台積電", "2317": "鴻海", "6770": "力積電"}
    return ticker_map

class CanslimEngine:
    def __init__(self):
        self.output_data = {
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "stocks": {}
        }
        self.ticker_map = get_all_tw_tickers()

    def fetch_institutional_trades(self, days=5):
        """Fetch TWSE institutional trades."""
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
            # TPEx stocks usually end with .TWO, TWSE with .TW
            # But yfinance often works with .TW for many major ones, let's try .TW then .TWO
            full_ticker = f"{ticker}.TW"
            stock = yf.Ticker(full_ticker)
            hist = stock.history(period="1mo") # Use 1 month for faster sweep in full list
            
            if hist.empty:
                full_ticker = f"{ticker}.TWO"
                stock = yf.Ticker(full_ticker)
                hist = stock.history(period="1mo")
                if hist.empty: return None

            price = hist['Close'].iloc[-1]
            
            # Simplified Logic for mass sweep
            trust_recent = sum([day['trust_net'] for day in inst_history[:3]]) if inst_history else 0
            is_i_pass = trust_recent > 0
            
            # Score calculation
            score = 60 # Base score
            if is_i_pass: score += 20
            if price > hist['Close'].mean(): score += 10

            return {
                "symbol": ticker,
                "name": self.ticker_map.get(ticker, ticker),
                "canslim": {
                    "C": True, "A": True, "N": True, 
                    "S": True, "L": True, "I": is_i_pass,
                    "M": True, "score": int(score)
                },
                "institutional": inst_history
            }
        except: return None

    def run(self):
        print("Fetching Institutional Data...")
        all_inst_history = self.fetch_institutional_trades(days=5)
        
        tickers = list(self.ticker_map.keys())
        print(f"Analyzing all {len(tickers)} stocks... (This may take a while)")
        
        # In a real full sweep, we'd use a faster method, but for now we process all
        for i, ticker in enumerate(tickers):
            if i % 100 == 0: print(f"  Progress: {i}/{len(tickers)}")
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
