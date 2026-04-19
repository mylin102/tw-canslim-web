import os
import json
import time
import logging
import requests
import pandas as pd
import yfinance as yf
from io import StringIO
from datetime import UTC, datetime, timedelta
from typing import Dict, List, Optional, Tuple
from excel_processor import ExcelDataProcessor
from finmind_processor import FinMindProcessor
from tej_processor import TEJProcessor
from core_selection import build_core_universe
from provider_policies import ProviderRetryExhaustedError, call_with_provider_policy, get_provider_policy
from yfinance_provider import get_price_history_with_policy

from core.logic import calculate_accumulation_strength, compute_canslim_score, compute_canslim_score_etf, calculate_l_factor, calculate_mansfield_rs, calculate_volatility_grid, check_n_factor
from publish_safety import (
    PublishTransactionError,
    PublishValidationError,
    load_artifact_json,
    publish_artifact_bundle,
    validate_resume_stock_entry,
)

# TAIEX via yfinance
TAIEX_SYMBOL = "^TWII"
RS_LOOKBACK_DAYS = 180  # ~6 months

# --- Configuration ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "docs")
DATA_FILE = os.path.join(OUTPUT_DIR, "data.json")
SCHEMA_VERSION = "1.0"

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

def get_all_tw_tickers(*, runtime_state: dict | None = None):
    """Fetch both TWSE and TPEx tickers with correct metadata."""
    logger.info("Fetching full TWSE and TPEx ticker lists...")
    ticker_map = {}
    requests_policy = get_provider_policy("requests")

    def fetch_csv(url: str) -> Optional[pd.DataFrame]:
        logger.debug(
            "Requests provider policy: min_interval_seconds=%s quota_window_seconds=%s max_requests_per_window=%s",
            requests_policy.min_interval_seconds,
            requests_policy.quota_window_seconds,
            requests_policy.max_requests_per_window,
        )
        try:
            response = call_with_provider_policy(
                "requests",
                lambda: requests.get(url, timeout=15),
                runtime_state=runtime_state,
                should_retry=lambda candidate: getattr(candidate, "status_code", None) in requests_policy.retryable_statuses,
            )
        except ProviderRetryExhaustedError as exc:
            logger.error(f"Failed to fetch ticker CSV {url}: {exc}")
            return None
        except requests.RequestException as exc:
            logger.error(f"Failed to fetch ticker CSV {url}: {exc}")
            return None

        try:
            response.raise_for_status()
        except requests.RequestException as exc:
            logger.error(f"Ticker CSV response failed for {url}: {exc}")
            return None
        return pd.read_csv(StringIO(response.text), encoding="utf-8")
    
    # 1. Listed (上市)
    try:
        df_l = fetch_csv(TWSE_TICKER_URL)
        if df_l is None:
            raise ValueError("TWSE ticker response unavailable")
        for _, row in df_l.iterrows():
            tid = str(row['公司代號']).strip()
            if len(tid) == 4:
                ticker_map[tid] = {"name": str(row['公司簡稱']), "suffix": ".TW"}
        logger.info(f"Fetched {len(ticker_map)} TWSE tickers")
    except Exception as e:
        logger.error(f"Failed to fetch TWSE tickers: {e}")
    
    # 2. OTC (上櫃)
    try:
        df_o = fetch_csv(TPEx_TICKER_URL)
        if df_o is None:
            raise ValueError("TPEx ticker response unavailable")
        for _, row in df_o.iterrows():
            tid = str(row['公司代號']).strip()
            if len(tid) == 4:
                ticker_map[tid] = {"name": str(row['公司簡稱']), "suffix": ".TWO"}
        logger.info(f"Fetched {len(ticker_map)} total tickers")
    except Exception as e:
        logger.error(f"Failed to fetch TPEx tickers: {e}")
    
    # 3. Add ETFs from cache
    cache_file = os.path.join(SCRIPT_DIR, "etf_cache.json")
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                cache_data = json.load(f)
                etfs = cache_data.get("etfs", {})
                for tid, info in etfs.items():
                    # Preserve existing stock if ID collision (rare for 4-digit)
                    if tid not in ticker_map or "ETF" in info.get("name", ""):
                        suffix = ".TW" if info.get("market") == "TWSE" else ".TWO"
                        ticker_map[tid] = {"name": info["name"], "suffix": suffix}
            logger.info(f"Integrated {len(etfs)} ETFs from cache")
        except Exception as e:
            logger.error(f"Failed to integrate ETF cache: {e}")

    # Add known stocks that might be missing
    for code, name in KNOWN_STOCK_NAMES.items():
        if code not in ticker_map:
            ticker_map[code] = {"name": name, "suffix": ".TWO"}
            logger.info(f"Added fallback name for {code}: {name}")
    
    return ticker_map

class CanslimEngine:
    def __init__(self):
        self.failure_stats = {
            "retry_attempts": 0,
            "retry_failures": 0,
            "resume_rejected": 0,
            "stock_failures": 0,
            "provider_wait_seconds": 0.0,
        }
        self.output_data = self._build_output_payload()
        self.ticker_info = get_all_tw_tickers(runtime_state=self.failure_stats)
        self.excel_processor = ExcelDataProcessor(SCRIPT_DIR)
        self.finmind_processor = FinMindProcessor()
        self.tej_processor = TEJProcessor()
        self.etf_list = self._load_etf_cache()
        self.excel_ratings = None
        self.fund_holdings = None
        self.industry_data = None
        self.industry_strength = None
        self.failure_details = []
        self._load_excel_data()

    def _build_output_payload(self) -> Dict:
        """Create the artifact envelope for the primary stock payload."""
        generated_at = self._utc_timestamp()
        return {
            "schema_version": SCHEMA_VERSION,
            "artifact_kind": "data",
            "run_id": self._build_run_id(),
            "generated_at": generated_at,
            "last_updated": "",
            "stocks": {},
        }

    def _build_run_id(self) -> str:
        """Build a stable run identifier for bundle publishes."""
        return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")

    def _utc_timestamp(self) -> str:
        """Return an ISO-like UTC timestamp."""
        return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    def _ensure_runtime_state(self) -> None:
        """Backfill runtime metadata for test-created engine instances."""
        if not hasattr(self, "failure_stats") or not isinstance(self.failure_stats, dict):
            self.failure_stats = {
                "retry_attempts": 0,
                "retry_failures": 0,
                "resume_rejected": 0,
                "stock_failures": 0,
                "provider_wait_seconds": 0.0,
            }
        if not hasattr(self, "failure_details") or not isinstance(self.failure_details, list):
            self.failure_details = []
        if not hasattr(self, "output_data") or not isinstance(self.output_data, dict):
            self.output_data = self._build_output_payload()

        self.output_data.setdefault("schema_version", SCHEMA_VERSION)
        self.output_data.setdefault("artifact_kind", "data")
        self.output_data.setdefault("run_id", self._build_run_id())
        self.output_data.setdefault("generated_at", self._utc_timestamp())
        self.output_data.setdefault("last_updated", "")
        self.output_data.setdefault("stocks", {})
        self.failure_stats.setdefault("provider_wait_seconds", 0.0)
        if hasattr(self, "finmind_processor") and self.finmind_processor is not None:
            self.finmind_processor.provider_runtime_state = self.failure_stats
        if hasattr(self, "tej_processor") and self.tej_processor is not None:
            self.tej_processor.provider_runtime_state = self.failure_stats

    def _record_stock_failure(self, ticker: str, message: str, exc: Exception | None = None) -> None:
        """Track a stock-level processing failure and log it explicitly."""
        self._ensure_runtime_state()
        self.failure_stats["stock_failures"] += 1
        detail = {"ticker": ticker, "message": message}
        self.failure_details.append(detail)
        if exc is not None:
            logger.exception("%s for %s", message, ticker)
        else:
            logger.error("%s for %s", message, ticker)

    def _build_update_summary(self) -> Dict:
        """Build the publish summary payload for the primary export path."""
        generated_at = self._utc_timestamp()
        status = "failed" if (
            self.failure_stats["retry_failures"] > 0 or self.failure_stats["stock_failures"] > 0
        ) else "success"
        return {
            "schema_version": SCHEMA_VERSION,
            "artifact_kind": "update_summary",
            "run_id": self.output_data["run_id"],
            "generated_at": generated_at,
            "status": status,
            "stats": {
                "retry_attempts": self.failure_stats.get("retry_attempts", 0),
                "retry_failures": self.failure_stats.get("retry_failures", 0),
                "resume_rejected": self.failure_stats.get("resume_rejected", 0),
                "stock_failures": self.failure_stats.get("stock_failures", 0),
                "provider_wait_seconds": self.failure_stats.get("provider_wait_seconds", 0.0),
            },
            "timestamp": generated_at,
            "update_type": "canslim_export",
            "description": "Primary CANSLIM export publish summary",
            "api_status": {
                "retry_failures": self.failure_stats["retry_failures"],
                "provider_wait_seconds": self.failure_stats.get("provider_wait_seconds", 0.0),
            },
            "data_stats": {
                "total_stocks": len(self.output_data["stocks"]),
                "updated_stocks": len(self.output_data["stocks"]),
            },
            "failures": list(self.failure_details),
        }

    def _json_default(self, obj):
        """Serialize datetime-like objects for publish payloads."""
        if isinstance(obj, (datetime, pd.Timestamp)):
            return obj.strftime("%Y-%m-%d")
        raise TypeError("Type %s not serializable" % type(obj))

    def _publish_snapshot(self) -> Dict:
        """Publish live artifacts through one bundle-safe transaction."""
        self._ensure_runtime_state()
        update_summary_file = os.path.join(OUTPUT_DIR, "update_summary.json")
        bundle = {
            DATA_FILE: {
                "artifact_kind": "data",
                "payload": self.output_data,
            },
            update_summary_file: {
                "artifact_kind": "update_summary",
                "payload": self._build_update_summary(),
            },
        }
        return publish_artifact_bundle(
            bundle,
            logger=logger,
            json_default=self._json_default,
        )

    def _load_etf_cache(self):
        """Load ETF list from local cache file."""
        cache_file = os.path.join(SCRIPT_DIR, "etf_cache.json")
        if os.path.exists(cache_file):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("etfs", {})
            except Exception as e:
                logger.error(f"Failed to load ETF cache: {e}")
        return {}

    def _load_excel_data(self):
        """Load Excel data if available."""
        try:
            self.excel_ratings = self.excel_processor.load_health_check_data()
            if self.excel_ratings:
                logger.info(f"Loaded Excel ratings for {len(self.excel_ratings)} stocks")
            
            self.fund_holdings = self.excel_processor.load_fund_holdings_data()
            if self.fund_holdings:
                logger.info(f"Loaded fund holdings for {len(self.fund_holdings)} stocks")
            
            # Load industry classification
            self.industry_data = self.excel_processor.load_industry_data()
            if self.industry_data:
                logger.info(f"Loaded industry data for {len(self.industry_data)} stocks")
            
            # Load industry strength ranking
            self.industry_strength = self.excel_processor.get_industry_strength()
            if self.industry_strength:
                logger.info(f"Loaded industry strength for {len(self.industry_strength)} industries")
        except Exception as e:
            logger.warning(f"Failed to load Excel data: {e}")
            self.excel_ratings = None
            self.fund_holdings = None
            self.industry_data = None
            self.industry_strength = None
    
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
        except (TypeError, ValueError):
            return 0

    def _fetch_with_retry(self, url: str, params: Dict = None, max_retries: int = 3) -> Optional[requests.Response]:
        """Fetch URL through the shared requests provider policy contract."""
        self._ensure_runtime_state()
        policy = get_provider_policy("requests")
        logger.debug(
            "Requests provider policy: min_interval_seconds=%s quota_window_seconds=%s max_requests_per_window=%s",
            policy.min_interval_seconds,
            policy.quota_window_seconds,
            policy.max_requests_per_window,
        )
        try:
            response = call_with_provider_policy(
                "requests",
                lambda: requests.get(url, params=params, timeout=15),
                runtime_state=self.failure_stats,
                should_retry=lambda candidate: getattr(candidate, "status_code", None) in policy.retryable_statuses,
                max_attempts=max_retries,
            )
        except ProviderRetryExhaustedError as exc:
            logger.error(f"All attempts failed for {url}: {exc}")
            return None
        except requests.RequestException as exc:
            logger.error(f"Non-retryable request failure for {url}: {exc}")
            return None

        try:
            response.raise_for_status()
        except requests.RequestException as exc:
            logger.error(f"Request failed for {url}: {exc}")
            return None
        return response

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
        self._ensure_runtime_state()
        policy = get_provider_policy("yfinance")
        try:
            # Use yfinance for basic financial data
            suffix = self.ticker_info.get(ticker, {}).get("suffix", ".TW")
            full_ticker = f"{ticker}{suffix}"
            logger.debug(
                "yfinance provider policy: min_interval_seconds=%s quota_window_seconds=%s max_requests_per_window=%s",
                policy.min_interval_seconds,
                policy.quota_window_seconds,
                policy.max_requests_per_window,
            )
            info = call_with_provider_policy(
                "yfinance",
                lambda: yf.Ticker(full_ticker).info,
                runtime_state=self.failure_stats,
            )
            
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
        self._ensure_runtime_state()
        policy = get_provider_policy("requests")
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
            
            response = call_with_provider_policy(
                "requests",
                lambda: requests.post(url, data=params, timeout=10),
                runtime_state=self.failure_stats,
                should_retry=lambda candidate: getattr(candidate, "status_code", None) in policy.retryable_statuses,
            )
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
                            except (TypeError, ValueError):
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
        except (TypeError, ValueError, ZeroDivisionError):
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

    def get_market_return_6m(self) -> Optional[float]:
        """Get TAIEX 6-month return using yfinance."""
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=RS_LOOKBACK_DAYS + 30)  # Buffer

            hist = get_price_history_with_policy(
                TAIEX_SYMBOL,
                start=start_date.strftime('%Y-%m-%d'),
                end=end_date.strftime('%Y-%m-%d'),
                runtime_state=self.failure_stats,
            )

            if hist is None or len(hist) < 30:
                logger.warning(f"Insufficient TAIEX data ({len(hist) if hist is not None else 0} rows)")
                return None
            
            # Get prices from ~180 trading days ago and latest
            start_price = hist.iloc[0]
            end_price = hist.iloc[-1]
            
            market_return = (end_price - start_price) / start_price
            logger.info(f"TAIEX 6mo return: {market_return*100:.2f}% ({start_price:.0f} → {end_price:.0f})")
            return market_return
            
        except Exception as e:
            logger.error(f"Failed to fetch TAIEX return: {e}")
            return None

    def check_l_relative_strength(self, stock_return: float, market_return: float) -> bool:
        """L - Leader or laggard (outperform market by 20%)."""
        if market_return is None:
            return False  # Can't calculate without market data
        
        # Handle near-zero market return (flat market)
        if abs(market_return) < 0.01:
            # Market is flat: use absolute return threshold
            return stock_return >= 0.05  # Stock up 5%+ in flat market
        
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

    def validate_stock_data(self, data: Dict) -> bool:
        """Validate stock data structure."""
        required_keys = ['symbol', 'name', 'canslim', 'institutional']
        if not all(key in data for key in required_keys):
            return False
        
        canslim_keys = ['C', 'A', 'N', 'S', 'L', 'I', 'M', 'score']
        if not all(key in data['canslim'] for key in canslim_keys):
            return False
        
        return True

    def get_price_history(self, ticker: str, period: str = "2y") -> Optional[pd.Series]:
        """Fetch historical close prices. Prefers TEJ, fallbacks to yfinance."""
        # 1. Try TEJ first
        if self.tej_processor.initialized:
            try:
                # TEJ index doesn't need ^
                tej_sym = ticker.replace("^", "")
                self.tej_processor.provider_runtime_state = self.failure_stats
                df_tej = self.tej_processor.get_daily_prices(tej_sym, count=500)
                if df_tej is not None and not df_tej.empty:
                    return pd.Series(df_tej['close'].values, index=pd.to_datetime(df_tej['date']))
            except Exception as e:
                logger.debug(f"TEJ history failed for {ticker}: {e}")

        # 2. Fallback to yfinance
        if ticker == "TWII" or ticker == "^TWII":
            yf_ticker = "^TWII"
        elif "." in ticker:
            yf_ticker = ticker
        else:
            # Add suffix from metadata or default to .TW
            suffix = self.ticker_info.get(ticker, {}).get("suffix", ".TW")
            yf_ticker = f"{ticker}{suffix}"

        return get_price_history_with_policy(
            yf_ticker,
            period=period,
            auto_adjust=True,
            runtime_state=self.failure_stats,
        )

    def run(self):
        self._ensure_runtime_state()
        logger.info("="*80)
        logger.info("Starting CANSLIM Analysis with Mansfield RS & Resume Capability")
        logger.info("="*80)
        
        # 1. Try to load existing data for resuming
        existing_count = 0
        if os.path.exists(DATA_FILE):
            try:
                old_data = load_artifact_json(DATA_FILE, artifact_kind="data", logger=logger)
            except PublishValidationError as exc:
                logger.warning(f"Existing artifact failed validation; scanning raw resume payload instead: {exc}")
                try:
                    with open(DATA_FILE, "r", encoding="utf-8") as handle:
                        old_data = json.load(handle)
                except (OSError, json.JSONDecodeError) as raw_exc:
                    logger.warning(f"Could not load existing data for resume: {raw_exc}")
                    old_data = {}
            except OSError as exc:
                logger.warning(f"Could not load existing data for resume: {exc}")
                old_data = {}

            if "stocks" in old_data:
                self.output_data["stocks"] = old_data["stocks"]
                existing_count = len(self.output_data["stocks"])
                logger.info(f"📂 Found existing data. Resuming with {existing_count} stocks already processed.")

        # 2. Fetch market benchmark history once
        logger.info(f"Fetching {TAIEX_SYMBOL} history for Mansfield RS...")
        market_hist = self.get_price_history(TAIEX_SYMBOL, period="2y")
        market_return = self.get_market_return_6m()
        
        all_t = sorted(list(self.ticker_info.keys()))
        selection = build_core_universe(
            all_symbols=all_t,
            config_path=os.path.join(SCRIPT_DIR, "core_selection_config.json"),
            fused_path=os.path.join(SCRIPT_DIR, "master_canslim_signals_fused.parquet"),
            master_path=os.path.join(SCRIPT_DIR, "master_canslim_signals.parquet"),
            baseline_path=os.path.join(OUTPUT_DIR, "data_base.json"),
        )
        scan_list = selection.core_symbols + [t for t in all_t if t not in selection.core_set][:2000]
        logger.info(
            "Dynamic core selector produced %s core symbols with bucket counts %s",
            len(selection.core_symbols),
            selection.bucket_counts,
        )
        logger.info("Final scan list contains %s symbols", len(scan_list))

        logger.info(f"Analyzing {len(scan_list)} stocks...")

        for i, t in enumerate(scan_list):
            if t in self.output_data["stocks"]:
                stock_entry = self.output_data["stocks"][t]
                try:
                    validate_resume_stock_entry(t, stock_entry, schema_version=SCHEMA_VERSION)
                    continue
                except PublishValidationError as exc:
                    self.failure_stats["resume_rejected"] += 1
                    logger.info(f"🔄 Resume rejected for {t}: {exc}. Re-processing...")

            if i % 10 == 0:
                logger.info(f"Processing {i}/{len(scan_list)}... (Current: {t})")
            
            try:
                info = self.ticker_info.get(t, {"name": t, "suffix": ".TW"})
                history = self.fetch_institutional_data_finmind(t, days=60)
                
                if not history:
                    history = [{"date": datetime.now().strftime("%Y%m%d"), "no_data": True}]
                
                chip_df = pd.DataFrame(history)
                financial_data = self.fetch_financial_data(t)
                if not financial_data:
                    self._record_stock_failure(t, "Missing financial data")
                    continue
                
                # Mansfield RS Calculation
                stock_hist = self.get_price_history(t, period="2y")
                m_rs = calculate_mansfield_rs(stock_hist, market_hist) if stock_hist is not None and market_hist is not None else 0.0

                price = financial_data.get("price", 0) or 0
                market_cap = financial_data.get("market_cap", 0) or 0
                shares_outstanding = financial_data.get("sharesOutstanding", 0) or 0
                
                total_shares = 0
                if price > 0 and market_cap > 0:
                    total_shares = market_cap / price
                elif shares_outstanding > 0:
                    total_shares = shares_outstanding
                
                tej_ca = {}
                if self.tej_processor.initialized:
                    tej_ca = self.tej_processor.calculate_canslim_c_and_a(t)
                
                c_score = tej_ca.get('C', False)
                a_score = tej_ca.get('A', False)
                tej_financials = self.tej_processor.get_quarterly_financials(t) if self.tej_processor.initialized else None

                n_score = check_n_factor(stock_hist)
                s_score = self.check_s_volume(financial_data.get("volume", 0), financial_data.get("avg_volume", 0))

                inst_strength_20d = calculate_accumulation_strength(chip_df, total_shares, days=20) if total_shares else 0.0
                inst_strength_5d = calculate_accumulation_strength(chip_df, total_shares, days=5) if total_shares else 0.0
                i_score = self.check_i_institutional(history)
                
                # New L factor based on Mansfield
                l_score = calculate_l_factor(m_rs)
                
                rs_ratio = 1.0
                if stock_hist is not None and market_return is not None:
                    # Calculate actual 6-month return (approx 120 trading days)
                    if len(stock_hist) >= 120:
                        stock_return_6m = (stock_hist.iloc[-1] - stock_hist.iloc[-120]) / stock_hist.iloc[-120]
                        rs_ratio = stock_return_6m / market_return if abs(market_return) > 0.01 else 1.0
                
                excel_ratings = self.get_excel_canslim_ratings(t)
                fund_data = self.fund_holdings.get(t) if self.fund_holdings else None
                industry_info = self.industry_data.get(t) if self.industry_data else None
                
                # ETF Identification
                industry_name = industry_info.get('industry', '') if industry_info else ''
                is_etf = (t in self.etf_list) or len(t) >= 5 or "ETF" in industry_name or "受益證券" in industry_name
                
                factors = {"C": c_score, "A": a_score, "N": n_score, "S": s_score, "L": l_score, "I": i_score, "M": True}
                
                if is_etf:
                    score = compute_canslim_score_etf(factors, institutional_strength=inst_strength_20d)
                else:
                    score = compute_canslim_score(factors, institutional_strength=inst_strength_20d)

                # Strategy Lab: Grid Strategy
                grid_data = None
                if (score >= 60 or is_etf) and stock_hist is not None:
                    grid_data = calculate_volatility_grid(stock_hist, is_etf=is_etf)

                stock_data = {
                    "schema_version": SCHEMA_VERSION,
                    "symbol": t, "name": info["name"],
                    "industry": industry_name,
                    "is_etf": is_etf,
                    "canslim": {
                        "C": c_score, "A": a_score, "N": n_score, "S": s_score, "L": l_score, "I": i_score, "M": True,
                        "score": score, 
                        "rs_ratio": round(rs_ratio, 2) if rs_ratio else None,
                        "mansfield_rs": round(m_rs, 3),
                        "inst_strength_20d": round(inst_strength_20d * 100, 3) if inst_strength_20d else 0,
                        "inst_strength_5d": round(inst_strength_5d * 100, 3) if inst_strength_5d else 0,
                        "excel_ratings": excel_ratings, "fund_holdings": fund_data,
                        "grid_strategy": grid_data
                    },
                    "institutional": history[:20], "financials": financial_data, "tej_quarterly": tej_financials
                }
                
                if self.validate_stock_data(stock_data):
                    self.output_data["stocks"][t] = stock_data

                # INCREMENTAL SAVE: Save every 50 new stocks
                if len(self.output_data["stocks"]) % 50 == 0:
                    self.output_data["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    logger.info(f"💾 Saving progress... ({len(self.output_data['stocks'])} stocks total)")
                    self._publish_snapshot()

            except (PublishValidationError, PublishTransactionError):
                logger.exception("Publish failed while processing %s", t)
                raise
            except Exception as e:
                self._record_stock_failure(t, "Error processing stock", exc=e)
                continue

        self.output_data["schema_version"] = SCHEMA_VERSION
        self.output_data["artifact_kind"] = "data"
        self.output_data["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.output_data["generated_at"] = self._utc_timestamp()

        # Calculate industry strength using CANSLIM data
        if self.industry_data:
            industry_stats = {}

            for t, stock in self.output_data["stocks"].items():
                ind = stock.get('industry')
                if not ind or ind == '未知':
                    continue

                if ind not in industry_stats:
                    industry_stats[ind] = {
                        'industry': ind,
                        'scores': [],
                        'inst_nets': [],
                        'high_score_count': 0,
                        'stock_count': 0
                    }

                industry_stats[ind]['scores'].append(stock['canslim']['score'])
                industry_stats[ind]['stock_count'] += 1

                if stock['canslim']['score'] >= 80:
                    industry_stats[ind]['high_score_count'] += 1

                # 3-day institutional net buying
                if stock.get('institutional') and len(stock['institutional']) >= 3:
                    net_3d = sum([
                        d.get('foreign_net', 0) + d.get('trust_net', 0) + d.get('dealer_net', 0)
                        for d in stock['institutional'][:3]
                    ])
                    industry_stats[ind]['inst_nets'].append(net_3d)

            # Build final industry strength ranking
            industry_strength = []
            for ind, stats in industry_stats.items():
                avg_score = sum(stats['scores']) / len(stats['scores']) if stats['scores'] else 0
                total_inst_net = sum(stats['inst_nets']) if stats['inst_nets'] else 0

                industry_strength.append({
                    'industry': ind,
                    'avg_score': round(avg_score, 1),
                    'total_inst_net_3d': int(total_inst_net),
                    'high_score_count': stats['high_score_count'],
                    'stock_count': stats['stock_count']
                })

            # Sort by average score (descending)
            industry_strength.sort(key=lambda x: x['avg_score'], reverse=True)
            self.output_data["industry_strength"] = industry_strength[:30]  # Top 30
            logger.info(f"Calculated industry strength for {len(industry_strength)} industries using CANSLIM data.")

        if not os.path.exists(OUTPUT_DIR):
            os.makedirs(OUTPUT_DIR)
        try:
            self._publish_snapshot()
        except (PublishValidationError, PublishTransactionError):
            logger.exception("Failed to publish CANSLIM artifact bundle")
            raise

        logger.info(f"Done! Exported {len(self.output_data['stocks'])} stocks.")

if __name__ == "__main__":
    CanslimEngine().run()
