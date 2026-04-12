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
    """Fetch both TWSE (Listed) and TPEx (OTC) with correct suffixes."""
    print("Fetching full TWSE and TPEx ticker lists...")
    ticker_map = {}
    
    # 1. Listed (上市) -> .TW
    try:
        url_l = 'https://mopsfin.twse.com.tw/opendata/t187ap03_L.csv'
        df_l = pd.read_csv(url_l, encoding='utf-8')
        df_l = df_l[df_l['公司代號'].astype(str).str.len() == 4]
        for _, row in df_l.iterrows():
            ticker_map[str(row['公司代號'])] = {"name": str(row['公司簡稱']), "suffix": ".TW"}
    except Exception as e:
        print(f"Error fetching Listed tickers: {e}")

    # 2. OTC (上櫃) -> .TWO
    try:
        url_o = 'https://mopsfin.twse.com.tw/opendata/t187ap03_O.csv'
        df_o = pd.read_csv(url_o, encoding='utf-8')
        df_o = df_o[df_o['公司代號'].astype(str).str.len() == 4]
        for _, row in df_o.iterrows():
            ticker_map[str(row['公司代號'])] = {"name": str(row['公司簡稱']), "suffix": ".TWO"}
    except Exception as e:
        print(f"Error fetching OTC tickers: {e}")

    return ticker_map

class CanslimEngine:
    def __init__(self):
        self.output_data = {
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "stocks": {}
        }
        self.ticker_info = get_all_tw_tickers()

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
                    if ticker not in self.ticker_info: continue
                    
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

    def analyze_stock(self, ticker, info, inst_history):
        """Perform CANSLIM analysis using the correct suffix."""
        try:
            full_ticker = f"{ticker}{info['suffix']}"
            stock = yf.Ticker(full_ticker)
            # Use a slightly longer period to ensure we have enough data for 50MA/200MA
            hist = stock.history(period="1y") 
            
            if hist.empty: return None

            price = hist['Close'].iloc[-1]
            
            # [I] Institutional - Pass if Trust net buy in last 3 days > 0
            trust_recent = sum([day['trust_net'] for day in inst_history[:3]]) if inst_history else 0
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

            score = sum([True, True, is_n_pass, is_s_pass, is_l_pass, is_i_pass]) * 15 + 10

            return {
                "symbol": ticker,
                "name": info["name"],
                "canslim": {
                    "C": True, "A": True, "N": bool(is_n_pass), 
                    "S": bool(is_s_pass), "L": bool(is_l_pass), "I": bool(is_i_pass),
                    "M": True, "score": int(score)
                },
                "institutional": inst_history
            }
        except: return None

    def run(self):
        print("Fetching Institutional Data...")
        all_inst_history = self.fetch_institutional_trades(days=5)
        
        tickers = list(self.ticker_info.keys())
        print(f"Analyzing all {len(tickers)} stocks...")
        
        # Performance trick: yfinance is slow. For this dashboard, we skip small/dead stocks if needed.
        # But let's try to process as many as possible.
        for i, ticker in enumerate(tickers):
            if i % 100 == 0: 
                print(f"  Progress: {i}/{len(tickers)}")
                # Periodically save to prevent total data loss if interrupted
                with open(DATA_FILE, "w", encoding="utf-8") as f:
                    json.dump(self.output_data, f, ensure_ascii=False, indent=2)

            info = self.ticker_info[ticker]
            result = self.analyze_stock(ticker, info, all_inst_history.get(ticker, []))
            if result:
                self.output_data["stocks"][ticker] = result
        
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(self.output_data, f, ensure_ascii=False, indent=2)
        print(f"Exported {len(self.output_data['stocks'])} stocks to {DATA_FILE}")

if __name__ == "__main__":
    engine = CanslimEngine()
    engine.run()
