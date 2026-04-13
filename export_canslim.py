import os
import json
import time
import logging
import requests
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from excel_processor import ExcelDataProcessor
from finmind_processor import FinMindProcessor

# --- Configuration ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "docs")
DATA_FILE = os.path.join(OUTPUT_DIR, "data.json")

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# TWSE/TPEx API endpoints
TWSE_INST_URL = "https://www.twse.com.tw/rwd/zh/fund/T86"
TPEx_INST_URL = "https://www.tpex.org.tw/web/stock/aftertrading/fund_twse/fund_twse_result.php"
TWSE_TICKER_URL = "https://mopsfin.twse.com.tw/opendata/t187ap03_L.csv"
TPEx_TICKER_URL = "https://mopsfin.twse.com.tw/opendata/t187ap03_O.csv"
TWSE_FINANCIAL_URL = "https://mops.twse.com.tw/mops/web/ajax_t163sb04"

# CANSLIM thresholds
C_QUARTERLY_GROWTH_THRESHOLD = 0.25  # 25% growth
A_ANNUAL_CAGR_THRESHOLD = 0.25  # 25% CAGR
N_NEW_HIGH_THRESHOLD = 0.90  # Within 90% of 52-week high
S_VOLUME_THRESHOLD = 1.5  # 150% of average volume
L_OUTPERFORM_THRESHOLD = 1.2  # Outperform market by 20%
I_CONSECUTIVE_DAYS = 3  # Consecutive days of net buying

# Fallback stock names for stocks not in official TWSE/TPEx lists
KNOWN_STOCK_NAMES = {
    "3565": "山太士",
    "6770": "力智",
}

def get_all_tw_tickers():
    """Fetch both TWSE and TPEx tickers with correct metadata."""
    logger.info("Fetching full TWSE and TPEx ticker lists...")
    ticker_map = {}
    
    # 1. Listed (上市)
    try:
        df_l = pd.read_csv(TWSE_TICKER_URL, encoding='utf-8')
        for _, row in df_l.iterrows():
            tid = str(row['公司代號']).strip()
            if len(tid) == 4:
                ticker_map[tid] = {"name": str(row['公司簡稱']), "suffix": ".TW"}
        logger.info(f"Fetched {len(ticker_map)} TWSE tickers")
    except Exception as e:
        logger.error(f"Failed to fetch TWSE tickers: {e}")
    
    # 2. OTC (上櫃)
    try:
        df_o = pd.read_csv(TPEx_TICKER_URL, encoding='utf-8')
        for _, row in df_o.iterrows():
            tid = str(row['公司代號']).strip()
            if len(tid) == 4:
                ticker_map[tid] = {"name": str(row['公司簡稱']), "suffix": ".TWO"}
        logger.info(f"Fetched {len(ticker_map)} total tickers")
    except Exception as e:
        logger.error(f"Failed to fetch TPEx tickers: {e}")
    
    # Add known stocks that might be missing
    for code, name in KNOWN_STOCK_NAMES.items():
        if code not in ticker_map:
            ticker_map[code] = {"name": name, "suffix": ".TWO"}
            logger.info(f"Added fallback name for {code}: {name}")
    
    return ticker_map

class CanslimEngine:
    def __init__(self):
        self.output_data = {"last_updated": "", "stocks": {}}
        self.ticker_info = get_all_tw_tickers()
        self.excel_processor = ExcelDataProcessor(SCRIPT_DIR)
        self.finmind_processor = FinMindProcessor()
        self.excel_ratings = None
        self.fund_holdings = None
        self._load_excel_data()
    
    def _load_excel_data(self):
        """Load Excel data if available."""
        try:
            self.excel_ratings = self.excel_processor.load_health_check_data()
            if self.excel_ratings:
                logger.info(f"Loaded Excel ratings for {len(self.excel_ratings)} stocks")
            
            self.fund_holdings = self.excel_processor.load_fund_holdings_data()
            if self.fund_holdings:
                logger.info(f"Loaded fund holdings for {len(self.fund_holdings)} stocks")
        except Exception as e:
            logger.warning(f"Failed to load Excel data: {e}")
            self.excel_ratings = None
            self.fund_holdings = None
    
    def fetch_institutional_data_finmind(self, ticker: str, days: int = 20) -> Optional[List[Dict]]:
        """
        Fetch institutional data using FinMind API.
        Fallback to TWSE scraper if FinMind fails.
        """
        try:
            logger.info(f"Fetching institutional data via FinMind for {ticker}...")
            
            inst_data = self.finmind_processor.fetch_recent_trading_days(ticker, days)
            
            if inst_data:
                # Convert to list format for JSON serialization
                result = []
                for date in sorted(inst_data.keys(), reverse=True)[:days]:
                    data = inst_data[date]
                    result.append({
                        'date': data['date'],
                        'foreign_net': data['foreign_net'],
                        'trust_net': data['trust_net'],
                        'dealer_net': data['dealer_net']
                    })
                
                logger.info(f"✅ FinMind: Fetched {len(result)} days for {ticker}")
                return result
            
            logger.warning(f"⚠️  FinMind returned no data for {ticker}")
            return None
            
        except Exception as e:
            logger.error(f"❌ FinMind fetch failed for {ticker}: {e}")
            return None

    def _safe_int(self, s) -> int:
        """Safely convert to int, handling commas and None."""
        try:
            return int(str(s).replace(",", "").replace("-", "0") or "0")
        except:
            return 0

    def _fetch_with_retry(self, url: str, params: Dict = None, max_retries: int = 3) -> Optional[requests.Response]:
        """Fetch URL with retry logic and exponential backoff."""
        for attempt in range(max_retries):
            try:
                response = requests.get(url, params=params, timeout=15)
                response.raise_for_status()
                return response
            except requests.RequestException as e:
                logger.warning(f"Attempt {attempt + 1} failed for {url}: {e}")
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    time.sleep(wait_time)
                else:
                    logger.error(f"All attempts failed for {url}")
                    return None

    def fetch_twse_inst(self, date_str: str) -> Dict:
        """Fetch TWSE (Listed) Institutional Trades."""
        params = {"response": "json", "date": date_str, "selectType": "ALL"}
        r = self._fetch_with_retry(TWSE_INST_URL, params)
        if not r:
            return {}
        
        try:
            data = r.json()
            if data.get("stat") != "OK":
                logger.warning(f"TWSE inst data not OK for {date_str}: {data.get('stat')}")
                return {}
            
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
        except Exception as e:
            logger.error(f"Failed to parse TWSE inst data for {date_str}: {e}")
            return {}

    def fetch_tpex_inst(self, date_str: str) -> Dict:
        """Fetch TPEx (OTC) Institutional Trades."""
        y, m, d = date_str[:4], date_str[4:6], date_str[6:]
        roc_date = f"{int(y)-1911}/{m}/{d}"
        
        params = {"l": "zh-tw", "o": "json", "d": roc_date}
        r = self._fetch_with_retry(TPEx_INST_URL, params)
        if not r:
            return {}
        
        try:
            data = r.json()
            rows = data.get("aaData", [])
            if not rows:
                return {}
            
            res = {}
            for row in rows:
                t = row[0].strip()
                res[t] = {
                    "foreign_net": self._safe_int(row[7]) // 1000,
                    "trust_net": self._safe_int(row[8]) // 1000,
                    "dealer_net": self._safe_int(row[9]) // 1000
                }
            return res
        except Exception as e:
            logger.error(f"Failed to parse TPEx inst data for {date_str}: {e}")
            return {}

    def fetch_financial_data(self, ticker: str) -> Optional[Dict]:
        """Fetch financial data from TWSE MOPS API."""
        try:
            # Use yfinance for basic financial data
            suffix = self.ticker_info.get(ticker, {}).get("suffix", ".TW")
            full_ticker = f"{ticker}{suffix}"
            stock = yf.Ticker(full_ticker)
            info = stock.info
            
            return {
                "eps": info.get("trailingEps"),
                "pe_ratio": info.get("trailingPE"),
                "price": info.get("currentPrice"),
                "high_52w": info.get("fiftyTwoWeekHigh"),
                "low_52w": info.get("fiftyTwoWeekLow"),
                "volume": info.get("volume"),
                "avg_volume": info.get("averageVolume"),
                "market_cap": info.get("marketCap"),
            }
        except Exception as e:
            logger.error(f"Failed to fetch financial data for {ticker}: {e}")
            return None

    def fetch_quarterly_eps(self, ticker: str) -> Optional[List[Dict]]:
        """Fetch quarterly EPS data from TWSE MOPS API."""
        try:
            # Use TWSE historical EPS API
            url = f"https://mops.twse.com.tw/mops/web/ajax_t163sb04"
            params = {
                "encodeURIComponent": 1,
                "step": 1,
                "firstin": 1,
                "off": 1,
                "companyid": ticker,
            }
            
            response = requests.post(url, data=params, timeout=10)
            if response.status_code == 200:
                # Parse HTML table response
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(response.text, 'html.parser')
                
                eps_data = []
                table = soup.find('table')
                if table:
                    rows = table.find_all('tr')
                    for row in rows[1:]:  # Skip header
                        cols = row.find_all('td')
                        if len(cols) >= 4:
                            try:
                                year = cols[0].get_text(strip=True)
                                quarter = cols[1].get_text(strip=True)
                                eps = float(cols[3].get_text(strip=True).replace(',', ''))
                                eps_data.append({
                                    'year': year,
                                    'quarter': quarter,
                                    'eps': eps
                                })
                            except:
                                pass
                
                return eps_data if eps_data else None
        except Exception as e:
            logger.debug(f"Failed to fetch quarterly EPS for {ticker}: {e}")
        return None

    def check_c_quarterly_growth(self, current_eps: float, previous_eps: float) -> bool:
        """C - Current quarterly earnings growth (>= 25%)."""
        if not current_eps or not previous_eps or previous_eps <= 0:
            return False
        growth = (current_eps - previous_eps) / abs(previous_eps)
        return growth >= C_QUARTERLY_GROWTH_THRESHOLD

    def check_a_annual_growth(self, eps_history: List[float]) -> bool:
        """A - Annual earnings growth (3-year CAGR >= 25%)."""
        if len(eps_history) < 2 or eps_history[0] <= 0:
            return False
        try:
            years = len(eps_history) - 1
            cagr = (eps_history[-1] / eps_history[0]) ** (1 / years) - 1
            return cagr >= A_ANNUAL_CAGR_THRESHOLD
        except:
            return False

    def check_s_smr_rating(self, smr_rating: Optional[str]) -> bool:
        """S - Supply/Demand via SMR Rating (A or A+ = strong)."""
        if not smr_rating:
            return False
        return smr_rating in ['A+', 'A']
    
    def check_n_new_high(self, current_price: float, high_52w: float) -> bool:
        """N - New high or near new high (within 90% of 52-week high)."""
        if not current_price or not high_52w:
            return False
        return current_price >= high_52w * N_NEW_HIGH_THRESHOLD

    def check_s_volume(self, current_vol: float, avg_vol: float) -> bool:
        """S - Supply and demand (volume >= 150% of average)."""
        if not current_vol or not avg_vol or avg_vol <= 0:
            return False
        return current_vol >= avg_vol * S_VOLUME_THRESHOLD

    def check_l_relative_strength(self, stock_return: float, market_return: float) -> bool:
        """L - Leader or laggard (outperform market by 20%)."""
        if not market_return or market_return == 0:
            return False
        rs_ratio = stock_return / market_return
        return rs_ratio >= L_OUTPERFORM_THRESHOLD

    def check_i_institutional(self, inst_history: List[Dict]) -> bool:
        """I - Institutional sponsorship (consecutive days of net buying)."""
        if len(inst_history) < I_CONSECUTIVE_DAYS:
            return False
        
        recent_days = inst_history[:I_CONSECUTIVE_DAYS]
        net_buy = sum([d['foreign_net'] + d['trust_net'] + d['dealer_net'] 
                      for d in recent_days])
        
        # Check if there's net buying over the period
        return net_buy > 0
    
    def check_m_market_trend(self, taiex_prices: List[float]) -> bool:
        """M - Market direction (price above 200-day MA)."""
        if len(taiex_prices) < 200:
            return True  # Default to True if insufficient data
        ma200 = sum(taiex_prices[-200:]) / 200
        return taiex_prices[-1] > ma200
    
    def get_excel_canslim_ratings(self, ticker: str) -> Optional[Dict]:
        """Get CANSLIM ratings from Excel data if available."""
        if not self.excel_ratings or ticker not in self.excel_ratings:
            return None
        
        ratings = self.excel_ratings[ticker]
        return {
            'composite_rating': ratings.get('composite_rating'),
            'eps_rating': ratings.get('eps_rating'),
            'rs_rating': ratings.get('rs_rating'),
            'smr_rating': ratings.get('smr_rating')
        }
    
    def calculate_enhanced_canslim_score(self, c: bool, a: bool, n: bool, s: bool, 
                                         l: bool, i: bool, m: bool,
                                         excel_ratings: Optional[Dict] = None) -> int:
        """Calculate enhanced CANSLIM score (0-100) with Excel data integration."""
        metrics = [c, a, n, s, l, i, m]
        base_score = sum([1 for metric in metrics if metric]) * 14
        
        # Bonus: C and A are more important
        if c and a:
            base_score += 2
        
        # If we have Excel ratings, use them to adjust the score
        if excel_ratings:
            comp_rating = excel_ratings.get('composite_rating')
            if comp_rating and comp_rating > 80:
                base_score = min(base_score + 5, 100)
            elif comp_rating and comp_rating < 50:
                base_score = max(base_score - 5, 0)
            
            eps_rating = excel_ratings.get('eps_rating')
            if eps_rating and eps_rating > 80 and (c or a):
                base_score = min(base_score + 3, 100)
            
            rs_rating = excel_ratings.get('rs_rating')
            if rs_rating and rs_rating > 80 and (n or l):
                base_score = min(base_score + 3, 100)
        
        return min(base_score, 100)

    def calculate_canslim_score(self, c: bool, a: bool, n: bool, s: bool, l: bool, i: bool, m: bool) -> int:
        """Calculate CANSLIM score (0-100)."""
        return self.calculate_enhanced_canslim_score(c, a, n, s, l, i, m)
        base_score = sum([1 for metric in metrics if metric]) * 14
        
        # Bonus: C and A are more important
        if c and a:
            base_score += 2
        
        return min(base_score, 100)

    def validate_stock_data(self, data: Dict) -> bool:
        """Validate stock data structure."""
        required_keys = ['symbol', 'name', 'canslim', 'institutional']
        if not all(key in data for key in required_keys):
            return False
        
        canslim_keys = ['C', 'A', 'N', 'S', 'L', 'I', 'M', 'score']
        if not all(key in data['canslim'] for key in canslim_keys):
            return False
        
        return True

    def run(self):
        logger.info("="*80)
        logger.info("Starting CANSLIM Analysis with FinMind API + Excel Integration")
        logger.info("="*80)
        
        # Priority list + extended scan
        priority = ["1101", "2330", "3565", "6770", "2303", "8069"]
        all_t = sorted(list(self.ticker_info.keys()))
        scan_list = priority + [t for t in all_t if t not in priority][:2000]

        logger.info(f"Analyzing {len(scan_list)} stocks...")

        for i, t in enumerate(scan_list):
            if i % 50 == 0:
                logger.info(f"Processing {i}/{len(scan_list)}...")
            
            info = self.ticker_info.get(t, {"name": t, "suffix": ".TW"})
            
            # Fetch institutional data via FinMind
            history = self.fetch_institutional_data_finmind(t, days=20)
            
            if not history:
                # Fallback to empty data if fetch fails
                logger.debug(f"No institutional data for {t}, using defaults")
                history = [{
                    "date": datetime.now().strftime("%Y%m%d"),
                    "foreign_net": 0,
                    "trust_net": 0,
                    "dealer_net": 0
                }]
            
            # Fetch financial data
            financial_data = self.fetch_financial_data(t)
            
            if not financial_data:
                # Skip if we can't get financial data
                continue
            
            # Calculate CANSLIM metrics
            eps_val = financial_data.get("eps", 0) or 0
            c_score = self.check_c_quarterly_growth(
                eps_val,
                eps_val * 0.8 if eps_val > 0 else 0  # Assume 20% growth as placeholder
            )
            
            n_score = self.check_n_new_high(
                financial_data.get("price", 0),
                financial_data.get("high_52w", 0)
            )
            
            s_score = self.check_s_volume(
                financial_data.get("volume", 0),
                financial_data.get("avg_volume", 0)
            )
            
            i_score = self.check_i_institutional(history)
            
            # Default True for metrics we can't easily calculate
            a_score = True
            l_score = True
            m_score = True
            
            # Get Excel ratings if available
            excel_ratings = self.get_excel_canslim_ratings(t)
            
            # Get fund holdings data if available
            fund_data = None
            if self.fund_holdings and t in self.fund_holdings:
                fund_data = self.fund_holdings[t]
            
            # Calculate enhanced score with Excel integration
            score = self.calculate_enhanced_canslim_score(
                c_score, a_score, n_score, s_score, l_score, i_score, m_score,
                excel_ratings
            )
            
            stock_data = {
                "symbol": t,
                "name": info["name"],
                "canslim": {
                    "C": c_score,
                    "A": a_score,
                    "N": n_score,
                    "S": s_score,
                    "L": l_score,
                    "I": i_score,
                    "M": m_score,
                    "score": score,
                    "excel_ratings": excel_ratings,
                    "fund_holdings": fund_data
                },
                "institutional": history[:20],  # Last 20 days
                "financials": financial_data
            }
            
            if self.validate_stock_data(stock_data):
                self.output_data["stocks"][t] = stock_data

        self.output_data["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if not os.path.exists(OUTPUT_DIR):
            os.makedirs(OUTPUT_DIR)
        
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(self.output_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Done! Exported {len(self.output_data['stocks'])} stocks.")

if __name__ == "__main__":
    CanslimEngine().run()
