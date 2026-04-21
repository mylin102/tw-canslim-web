import os
import json
import time
import logging
import requests
import pandas as pd
import yfinance as yf
from io import BytesIO
from datetime import UTC, datetime, timedelta
from typing import Dict, List, Optional, Tuple
from excel_processor import ExcelDataProcessor
from finmind_processor import FinMindProcessor
from tej_processor import TEJProcessor
from core_selection import build_core_universe
from orchestration_state import DEFAULT_STATE_PATH, enqueue_retry_failure, save_rotation_state
from provider_policies import (
    ProviderRetryExhaustedError,
    call_with_provider_policy,
    compute_backoff_seconds,
    get_provider_policy,
)
from rotation_orchestrator import (
    build_daily_plan,
    finalize_failure,
    finalize_success,
    load_state,
    mark_symbol_completed,
    write_in_progress,
)
from yfinance_provider import get_price_history_with_policy
from publish_projection import build_publish_projection_bundle

from core.logic import (
    calculate_accumulation_strength, 
    calculate_i_score_v2,
    compute_canslim_score_v2,
    calculate_score_delta,
    get_market_sentiment,
    calculate_l_factor, 
    calculate_mansfield_rs, 
    calculate_volatility_grid, 
    check_n_factor
)
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
ROTATION_STATE_FILE = str(DEFAULT_STATE_PATH)
RUNTIME_BUDGET_FILE = os.path.join(SCRIPT_DIR, ".orchestration", "runtime_budget.json")
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
        return pd.read_csv(BytesIO(response.content), encoding="utf-8-sig")
    
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
        self.refreshed_symbols = []
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
        if not hasattr(self, "refreshed_symbols") or not isinstance(self.refreshed_symbols, list):
            self.refreshed_symbols = []
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

    def _publish_snapshot(
        self,
        *,
        rotation_state: dict,
        selection,
        all_symbols: list[str],
        scheduled_batch: dict,
    ) -> Dict:
        """Publish live artifacts through one bundle-safe transaction."""
        self._ensure_runtime_state()
        baseline_payload = {"stocks": {}}
        baseline_file = os.path.join(OUTPUT_DIR, "data_base.json")
        if os.path.exists(baseline_file):
            baseline_payload = load_artifact_json(baseline_file, artifact_kind="data_base", logger=logger)

        projected = build_publish_projection_bundle(
            output_data=self.output_data,
            baseline_payload=baseline_payload,
            ticker_info=self.ticker_info,
            freshness_state=rotation_state,
            failure_details=self.failure_details,
            failure_stats=self.failure_stats,
            refreshed_symbols=self.refreshed_symbols,
            all_symbols=all_symbols,
            selection=selection,
            scheduled_batch=scheduled_batch,
            as_of=self._rotation_timestamp(),
        )

        update_summary_file = os.path.join(OUTPUT_DIR, "update_summary.json")
        stock_index_file = os.path.join(OUTPUT_DIR, "stock_index.json")
        bundle = {
            DATA_FILE: {
                "artifact_kind": "data",
                "payload": projected["data"],
            },
            stock_index_file: {
                "artifact_kind": "stock_index",
                "payload": projected["stock_index"],
            },
            update_summary_file: {
                "artifact_kind": "update_summary",
                "payload": projected["update_summary"],
            },
        }
        return publish_artifact_bundle(
            bundle,
            logger=logger,
            json_default=self._json_default,
        )

    def _export_leaders_json(self, selection) -> Dict:
        """Export core leaders to data/leaders.json according to External Alpha contract."""
        self._ensure_runtime_state()
        leaders_dir = os.path.join(SCRIPT_DIR, "data")
        if not os.path.exists(leaders_dir):
            os.makedirs(leaders_dir)
        leaders_file = os.path.join(leaders_dir, "leaders.json")
        
        # Build industry rank mapping
        industry_strength = self.output_data.get("industry_strength", [])
        industry_rank_map = {item["industry"]: i + 1 for i, item in enumerate(industry_strength)}
        
        universe = []
        core_set = set(selection.core_symbols)
        
        # Priority 1: Add symbols from Excel health check if score is high or explicitly present
        excel_symbols = set()
        if self.excel_ratings:
            for symbol, ratings in self.excel_ratings.items():
                # Force include if composite rating > 70 OR it's a known important symbol
                comp_rating = ratings.get("composite_rating")
                if comp_rating and comp_rating >= 70:
                    excel_symbols.add(symbol)
            logger.info(f"Identified {len(excel_symbols)} potential leaders from Excel health check.")

        # Combine selection core with high-quality excel symbols
        final_universe_symbols = sorted(list(core_set.union(excel_symbols)))
        
        for symbol in final_universe_symbols:
            # Check if we have processed data for this symbol
            stock_data = self.output_data["stocks"].get(symbol)
            
            # Fallback for symbols present in Excel but not in current batch output
            if not stock_data:
                # Try to get basic info if missing
                info = self.ticker_info.get(symbol, {"name": symbol})
                excel_ratings = self.get_excel_canslim_ratings(symbol)
                
                # If we have neither processed data nor Excel ratings, skip
                if not excel_ratings:
                    continue
                    
                entry = {
                    "symbol": symbol,
                    "name": info["name"],
                    "rs_rating": int(excel_ratings.get("rs_rating") or 0),
                    "breakout_score": 0.5, # Default since no price data
                    "volume_score": 0.5,
                    "composite_score": round((excel_ratings.get("composite_rating") or 0) / 100.0, 3),
                    "industry_rank": 999,
                    "tags": ["leader", "from_excel"]
                }
            else:
                canslim = stock_data["canslim"]
                
                # Map breakout_score: 1.0 if N is True, else 0.5
                breakout_score = 1.0 if canslim.get("N") else 0.5
                
                # Map volume_score: 1.0 if S is True, else 0.5
                volume_score = 1.0 if canslim.get("S") else 0.5
                
                # RS Rating: use excel_ratings if available
                rs_rating = 0
                excel_ratings = canslim.get("excel_ratings")
                if excel_ratings and excel_ratings.get("rs_rating"):
                    rs_rating = int(excel_ratings["rs_rating"])
                elif canslim.get("mansfield_rs"):
                    rs_rating = min(99, max(1, 50 + int(canslim["mansfield_rs"] * 5)))

                # Blended composite score: 70% CANSLIM, 30% Revenue
                canslim_score = float(canslim.get("score") or 0.0)
                revenue_score = float(canslim.get("revenue_score") or 0.0)
                blended_score = 0.7 * (canslim_score / 100.0) + 0.3 * (revenue_score / 6.0)

                entry = {
                    "symbol": symbol,
                    "name": stock_data["name"],
                    "rs_rating": rs_rating,
                    "breakout_score": breakout_score,
                    "volume_score": volume_score,
                    "composite_score": round(blended_score, 3),
                    "industry_rank": industry_rank_map.get(stock_data.get("industry"), 999),
                    "tags": ["leader"]
                }
                if canslim.get("N"):
                    entry["tags"].append("breakout_candidate")
                if canslim.get("rev_accelerating"):
                    entry["tags"].append("rev_acc")
                if canslim.get("rev_strong"):
                    entry["tags"].append("rev_strong")
                if symbol in excel_symbols:
                    entry["tags"].append("verified")
                
            universe.append(entry)
            
        payload = {
            "schema_version": 1,
            "date": datetime.now(UTC).strftime("%Y-%m-%d"),
            "generated_at": self._utc_timestamp(),
            "universe": universe
        }
        
        bundle = {
            leaders_file: {
                "artifact_kind": "leaders",
                "payload": payload,
            }
        }
        
        logger.info(f"Exporting {len(universe)} leaders to {leaders_file} (including Excel-sourced)...")
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
    
    def fetch_institutional_data_batch(self, tickers: List[str], days: int = 5):
        """
        Efficiently fetch institutional data for many stocks using market-wide data.
        """
        if not self.finmind_processor.available:
            logger.warning("FinMind unavailable, skipping batch institutional fetch")
            return
            
        logger.info(f"Starting batch institutional fetch for {len(tickers)} stocks...")
        
        # Calculate recent trading dates (last N days)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=10)
        
        current = start_date
        self.inst_cache = {} 
        
        while current <= end_date:
            date_str = current.strftime('%Y-%m-%d')
            df = self.finmind_processor.fetch_all_institutional_investors(date_str)
            
            if df is not None and not df.empty:
                df['net'] = df['buy'] - df['sell']
                
                df['type'] = 'other'
                df.loc[df['name'].str.contains('Foreign_Investor'), 'type'] = 'foreign'
                df.loc[df['name'].str.contains('Investment_Trust'), 'type'] = 'trust'
                df.loc[df['name'].str.contains('Dealer'), 'type'] = 'dealer'
                
                day_grouped = df.groupby(['stock_id', 'type'])['net'].sum().unstack(fill_value=0)
                date_compact = date_str.replace('-', '')
                
                for tid, row in day_grouped.iterrows():
                    if tid not in self.inst_cache:
                        self.inst_cache[tid] = []
                    
                    self.inst_cache[tid].append({
                        'date': date_compact,
                        'foreign_net': int(row.get('foreign', 0) // 1000),
                        'trust_net': int(row.get('trust', 0) // 1000),
                        'dealer_net': int(row.get('dealer', 0) // 1000),
                    })
            
            current += timedelta(days=1)
            
        logger.info(f"Batch institutional fetch complete. Cached data for {len(self.inst_cache)} stocks.")

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

    def _get_excel_health_record(self, ticker: str) -> Dict:
        if not self.excel_ratings:
            return {}
        return dict(self.excel_ratings.get(ticker) or {})

    def _excel_c_fallback(self, ticker: str) -> bool:
        excel_data = self._get_excel_health_record(ticker)
        if not excel_data:
            return False

        quarterly_eps_growth = excel_data.get("quarterly_eps_growth_pct")
        three_quarter_eps_growth = excel_data.get("three_quarter_eps_growth_pct")
        quarterly_revenue_growth = excel_data.get("quarterly_revenue_growth_pct")
        eps_rating = excel_data.get("eps_rating") or 0

        return bool(
            (quarterly_eps_growth is not None and quarterly_eps_growth >= C_QUARTERLY_GROWTH_THRESHOLD * 100)
            or (three_quarter_eps_growth is not None and three_quarter_eps_growth >= C_QUARTERLY_GROWTH_THRESHOLD * 100)
            or (
                quarterly_revenue_growth is not None
                and quarterly_revenue_growth >= C_QUARTERLY_GROWTH_THRESHOLD * 100
                and eps_rating >= 80
            )
        )

    def _excel_a_fallback(self, ticker: str) -> bool:
        excel_data = self._get_excel_health_record(ticker)
        if not excel_data:
            return False

        annual_eps_growth = excel_data.get("annual_eps_growth_pct")
        three_year_eps_growth = excel_data.get("three_year_eps_growth_pct")
        eps_growth_years = excel_data.get("eps_growth_years")
        eps_rating = excel_data.get("eps_rating") or 0

        return bool(
            (annual_eps_growth is not None and annual_eps_growth >= 25)
            or (three_year_eps_growth is not None and three_year_eps_growth >= 25)
            or (eps_growth_years is not None and eps_growth_years >= 2 and eps_rating >= 80)
        )

    def _excel_i_fallback(self, ticker: str, current_score: float) -> Tuple[float, Dict]:
        excel_data = self._get_excel_health_record(ticker)
        fund_data = dict(self.fund_holdings.get(ticker) or {}) if self.fund_holdings else {}
        if not excel_data and not fund_data:
            return current_score, {}

        candidate_score = float(current_score or 0.0)
        details: Dict[str, float | str | int] = {}

        sponsorship_score = excel_data.get("sponsorship_score")
        if sponsorship_score is not None:
            candidate_score = max(candidate_score, float(sponsorship_score))
            details["sponsorship_score"] = float(sponsorship_score)

        current_month = fund_data.get("current_month")
        change = fund_data.get("change")
        change_pct = fund_data.get("change_pct")
        if current_month is not None:
            fund_score = 40.0 + min(float(current_month) / 10.0, 40.0)
            if change is not None and change > 0:
                fund_score += min(float(change), 20.0)
            candidate_score = max(candidate_score, min(fund_score, 100.0))
            details["fund_current_month"] = int(current_month)
        if change is not None:
            details["fund_change"] = int(change)
        if change_pct is not None:
            details["fund_change_pct"] = float(change_pct)

        institutional_holding_pct = excel_data.get("institutional_holding_pct")
        if institutional_holding_pct is not None:
            details["institutional_holding_pct"] = float(institutional_holding_pct)

        if candidate_score > float(current_score or 0.0):
            details["source"] = "excel_fallback"
        return min(candidate_score, 100.0), details
    
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

    def _rotation_timestamp(self) -> str:
        """Return a UTC timestamp for durable rotation metadata."""
        return self._utc_timestamp()

    def _rotation_retry_due_at(self, provider_name: str, attempt_count: int, failed_at: datetime) -> str:
        """Return the next retry time for a failed non-core symbol."""
        try:
            policy = get_provider_policy(provider_name)
            wait_seconds = compute_backoff_seconds(policy, min(max(1, attempt_count), policy.max_attempts))
        except (KeyError, ValueError):
            wait_seconds = 300.0
        return (failed_at + timedelta(seconds=wait_seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")

    def _persist_non_scheduled_success(
        self,
        state: dict,
        *,
        symbol: str,
        attempted_at: str,
        succeeded_at: str,
        rotation_generation: str,
        source: str,
    ) -> dict:
        """Persist freshness for core/retry successes and drop any stale retry queue entry."""
        next_state = save_rotation_state(self._normalized_rotation_state(state), path=None)
        next_state["retry_queue"] = [entry for entry in next_state["retry_queue"] if entry.get("symbol") != symbol]
        next_state["freshness"][symbol] = {
            "last_attempted_at": attempted_at,
            "last_succeeded_at": succeeded_at,
            "last_batch_generation": rotation_generation,
            "source": source,
        }
        return save_rotation_state(next_state, path=ROTATION_STATE_FILE)

    def _persist_non_scheduled_failure(
        self,
        state: dict,
        *,
        symbol: str,
        error: str,
        failed_at: datetime,
        scheduled_batch: dict,
        provider_name: str = "requests",
    ) -> dict:
        """Queue a failed retry symbol without overwriting prior success freshness."""
        next_state = save_rotation_state(self._normalized_rotation_state(state), path=None)
        existing_entry = next(
            (entry for entry in next_state["retry_queue"] if entry.get("symbol") == symbol),
            None,
        )
        next_state["retry_queue"] = [entry for entry in next_state["retry_queue"] if entry.get("symbol") != symbol]
        attempt_count = 1 if existing_entry is None else int(existing_entry.get("attempt_count", 1)) + 1
        due_at = self._rotation_retry_due_at(
            existing_entry.get("provider", provider_name) if existing_entry else provider_name,
            attempt_count,
            failed_at,
        )
        return enqueue_retry_failure(
            next_state,
            path=ROTATION_STATE_FILE,
            symbol=symbol,
            provider=existing_entry.get("provider", provider_name) if existing_entry else provider_name,
            error=error,
            due_at=due_at,
            failed_at=failed_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
            batch_index=scheduled_batch["batch_index"],
            rotation_generation=scheduled_batch["rotation_generation"],
            attempt_count=attempt_count,
        )

    def _normalized_rotation_state(self, state: dict) -> dict:
        """Fill any missing rotation-state keys for test seams and defensive writes."""
        normalized = {
            "schema_version": SCHEMA_VERSION,
            "current_batch_index": 0,
            "rotation_generation": "",
            "retry_queue": [],
            "freshness": {},
            "in_progress": None,
            "last_completed_batch": None,
        }
        normalized.update(state)
        normalized["retry_queue"] = list(normalized.get("retry_queue", []))
        normalized["freshness"] = dict(normalized.get("freshness", {}))
        return normalized

    def _write_runtime_budget(self, started_at: float) -> dict:
        """Persist runtime budget metrics for workflow validation."""
        payload = {
            "elapsed_seconds": round(max(0.0, time.monotonic() - started_at), 3),
            "retry_attempts": self.failure_stats.get("retry_attempts", 0),
            "retry_failures": self.failure_stats.get("retry_failures", 0),
            "provider_wait_seconds": round(self.failure_stats.get("provider_wait_seconds", 0.0), 3),
        }
        runtime_dir = os.path.dirname(RUNTIME_BUDGET_FILE)
        if not os.path.exists(runtime_dir):
            os.makedirs(runtime_dir)
        with open(RUNTIME_BUDGET_FILE, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        return payload

    def run(self):
        started_at = time.monotonic()
        self._ensure_runtime_state()
        logger.info("="*80)
        logger.info("Starting CANSLIM Analysis with Mansfield RS & Resume Capability")
        logger.info("="*80)
        rotation_state = self._normalized_rotation_state(load_state(path=ROTATION_STATE_FILE))
        try:
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
            
            # 2b. Batch fetch institutional data for all tickers to save API calls
            self.fetch_institutional_data_batch(all_t, days=5)

            # 2c. Load revenue features
            revenue_features = {}
            revenue_path = os.path.join(OUTPUT_DIR, "api", "stock_features.json")
            if os.path.exists(revenue_path):
                try:
                    with open(revenue_path, "r", encoding="utf-8") as handle:
                        revenue_features = json.load(handle)
                    logger.info(f"Loaded revenue features for {len(revenue_features)} stocks.")
                except Exception as e:
                    logger.warning(f"Failed to load revenue features: {e}")

            selection = build_core_universe(
                all_symbols=all_t,
                config_path=os.path.join(SCRIPT_DIR, "core_selection_config.json"),
                fused_path=os.path.join(SCRIPT_DIR, "master_canslim_signals_fused.parquet"),
                master_path=os.path.join(SCRIPT_DIR, "master_canslim_signals.parquet"),
                baseline_path=os.path.join(OUTPUT_DIR, "data_base.json"),
                revenue_path=revenue_path,
            )
            daily_plan = build_daily_plan(
                all_symbols=all_t,
                selection=selection,
                state=rotation_state,
                as_of=self._rotation_timestamp(),
            )
            scan_list = selection.core_symbols + daily_plan["worklist"]
            scheduled_batch = daily_plan["scheduled_batch"]
            scheduled_symbols = set(scheduled_batch["symbols"])
            retry_symbols = set(daily_plan["retry_symbols"])

            logger.info(
                "Dynamic core selector produced %s core symbols with bucket counts %s",
                len(selection.core_symbols),
                selection.bucket_counts,
            )
            logger.info(
                "Rotation plan selected %s retries and %s scheduled non-core symbols",
                len(daily_plan["retry_symbols"]),
                len(scheduled_batch["symbols"]),
            )
            logger.info("Final scan list contains %s symbols", len(scan_list))

            if scheduled_batch["symbols"] and rotation_state.get("in_progress") is None:
                rotation_state = write_in_progress(
                    rotation_state,
                    planned_batch=scheduled_batch,
                    path=ROTATION_STATE_FILE,
                )
                if rotation_state.get("in_progress") is None:
                    rotation_state = self._normalized_rotation_state(rotation_state)
                    rotation_state["rotation_generation"] = scheduled_batch["rotation_generation"]
                    rotation_state["in_progress"] = {
                        "batch_index": scheduled_batch["batch_index"],
                        "rotation_generation": scheduled_batch["rotation_generation"],
                        "symbols": list(scheduled_batch["symbols"]),
                        "completed_symbols": list(scheduled_batch.get("completed_symbols", [])),
                        "remaining_symbols": list(scheduled_batch.get("remaining_symbols", scheduled_batch["symbols"])),
                    }

            logger.info(f"Analyzing {len(scan_list)} stocks...")

            for i, t in enumerate(scan_list):
                is_scheduled_symbol = t in scheduled_symbols
                is_retry_symbol = t in retry_symbols
                source = "rotation" if is_scheduled_symbol else ("retry" if is_retry_symbol else "core")

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

                attempted_at_dt = datetime.now(UTC)
                attempted_at = attempted_at_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

                try:
                    info = self.ticker_info.get(t, {"name": t, "suffix": ".TW"})
                    
                    # Try batch cache first, fallback to individual if needed
                    history = self.inst_cache.get(t)
                    if not history:
                        logger.info(f"Cache miss for {t}, fetching individually...")
                        history = self.fetch_institutional_data_finmind(t, days=20)

                    if not history:
                        # Add a dummy record so the UI knows we tried but found nothing
                        history = [{"date": datetime.now().strftime("%Y%m%d"), "no_data": True, "foreign_net": 0, "trust_net": 0, "dealer_net": 0}]

                    # Convert to DataFrame for core logic
                    chip_df = pd.DataFrame(history)
                    financial_data = self.fetch_financial_data(t)
                    if not financial_data:
                        raise ValueError("Missing financial data")

                    # Load revenue features for this stock
                    rev_feat = revenue_features.get(t, {})
                    revenue_score = float(rev_feat.get("revenue_score", 0.0))
                    rev_accelerating = bool(rev_feat.get("rev_accelerating", False))
                    rev_strong = bool(rev_feat.get("rev_strong", False))

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
                    
                    # Institutional Scoring (v2)
                    inst_result = calculate_i_score_v2(chip_df, total_shares, days=20) if total_shares > 0 else {"score": 50.0, "details": {}}
                    i_score_abs = inst_result["score"]
                    i_pass = i_score_abs >= 60

                    tej_ca = {}
                    if self.tej_processor.initialized:
                        self.tej_processor.provider_runtime_state = self.failure_stats
                        tej_ca = self.tej_processor.calculate_canslim_c_and_a(t)

                    c_pass = tej_ca.get('C', False)
                    a_pass = tej_ca.get('A', False)
                    if not c_pass:
                        c_pass = self._excel_c_fallback(t)
                    if not a_pass:
                        a_pass = self._excel_a_fallback(t)

                    i_score_abs, excel_i_details = self._excel_i_fallback(t, i_score_abs)
                    if excel_i_details:
                        inst_result["details"] = {**inst_result.get("details", {}), **excel_i_details}
                    i_pass = i_score_abs >= 60
                    tej_financials = self.tej_processor.get_quarterly_financials(t) if self.tej_processor.initialized else None

                    n_pass = check_n_factor(stock_hist)
                    s_pass = self.check_s_volume(financial_data.get("volume", 0), financial_data.get("avg_volume", 0))
                    l_pass = calculate_l_factor(m_rs)

                    industry_info = self.industry_data.get(t) if self.industry_data else None
                    industry_name = industry_info.get('industry', '') if industry_info else ''
                    is_etf = (t in self.etf_list) or len(t) >= 5 or "ETF" in industry_name or "受益證券" in industry_name

                    factors = {"C": c_pass, "A": a_pass, "N": n_pass, "S": s_pass, "L": l_pass, "I": i_pass, "M": True}
                    
                    # Bonus for recent momentum (e.g. score jump)
                    momentum_bonus = 5 if n_pass and s_pass else 0
                    
                    # Calculate total score using v2
                    score = compute_canslim_score_v2(factors, i_score_abs=i_score_abs, momentum_bonus=momentum_bonus)
                    
                    # Calculate delta if previous data exists
                    yesterday_score = old_data.get("stocks", {}).get(t, {}).get("canslim", {}).get("score", score)
                    score_delta = calculate_score_delta(score, yesterday_score)

                    # Strategy Lab: Grid Strategy
                    grid_data = {
                        "volatility_daily": 0.0,
                        "volatility_annual": 0.0,
                        "spacing_pct": 0.0,
                        "levels": [],
                        "is_etf": is_etf,
                    }
                    if (score >= 60 or is_etf) and stock_hist is not None:
                        calculated_grid = calculate_volatility_grid(stock_hist, is_etf=is_etf)
                        if calculated_grid is not None:
                            grid_data = calculated_grid

                    stock_data = {
                        "schema_version": SCHEMA_VERSION,
                        "symbol": t, "name": info["name"],
                        "industry": industry_name,
                        "is_etf": is_etf,
                        "canslim": {
                            "C": bool(factors["C"]),
                            "A": bool(factors["A"]),
                            "N": bool(factors["N"]),
                            "S": bool(factors["S"]),
                            "L": bool(factors["L"]),
                            "I": bool(factors["I"]),
                            "M": bool(factors["M"]),
                            "score": int(score),
                            "score_delta": int(score_delta),
                            "i_score_abs": float(i_score_abs),
                            "inst_details": inst_result.get("details", {}),
                            "mansfield_rs": float(m_rs),
                            "revenue_score": float(revenue_score),
                            "rev_accelerating": bool(rev_accelerating),
                            "rev_strong": bool(rev_strong),
                            "grid_strategy": grid_data,
                            "excel_ratings": self.get_excel_canslim_ratings(t),
                            "fund_holdings": self.fund_holdings.get(t) if self.fund_holdings else None,
                        },
                        "institutional": history[:20], "financials": financial_data, "tej_quarterly": tej_financials,
                        "last_updated": attempted_at,
                    }

                    if self.validate_stock_data(stock_data):
                        self.output_data["stocks"][t] = stock_data

                    succeeded_at = self._rotation_timestamp()
                    if t not in self.refreshed_symbols:
                        self.refreshed_symbols.append(t)
                    if is_scheduled_symbol:
                        rotation_state = mark_symbol_completed(
                            rotation_state,
                            symbol=t,
                            attempted_at=attempted_at,
                            succeeded_at=succeeded_at,
                            source=source,
                            path=ROTATION_STATE_FILE,
                        )
                    else:
                        rotation_state = self._persist_non_scheduled_success(
                            rotation_state,
                            symbol=t,
                            attempted_at=attempted_at,
                            succeeded_at=succeeded_at,
                            rotation_generation=scheduled_batch["rotation_generation"],
                            source=source,
                        )

                    # INCREMENTAL SAVE: Save every 50 new stocks
                    if len(self.output_data["stocks"]) % 50 == 0:
                        self.output_data["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        logger.info(f"💾 Saving progress... ({len(self.output_data['stocks'])} stocks total)")
                        self._publish_snapshot(
                            rotation_state=rotation_state,
                            selection=selection,
                            all_symbols=all_t,
                            scheduled_batch=scheduled_batch,
                        )

                except (PublishValidationError, PublishTransactionError):
                    logger.exception("Publish failed while processing %s", t)
                    raise
                except Exception as e:
                    self._record_stock_failure(t, str(e), exc=None)
                    if is_scheduled_symbol:
                        failure_state = save_rotation_state(self._normalized_rotation_state(rotation_state), path=None)
                        failure_state["retry_queue"] = [
                            entry for entry in failure_state["retry_queue"] if entry.get("symbol") != t
                        ]
                        rotation_state = finalize_failure(
                            failure_state,
                            symbol=t,
                            provider="requests",
                            error=str(e),
                            failed_at=attempted_at,
                            due_at=self._rotation_retry_due_at("requests", 1, attempted_at_dt),
                            path=ROTATION_STATE_FILE,
                        )
                    elif is_retry_symbol:
                        rotation_state = self._persist_non_scheduled_failure(
                            rotation_state,
                            symbol=t,
                            error=str(e),
                            failed_at=attempted_at_dt,
                            scheduled_batch=scheduled_batch,
                        )
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
                self._publish_snapshot(
                    rotation_state=rotation_state,
                    selection=selection,
                    all_symbols=all_t,
                    scheduled_batch=scheduled_batch,
                )
                
                # Export Leaders for external alpha integration
                try:
                    self._export_leaders_json(selection)
                except Exception as e:
                    logger.error(f"Failed to export external alpha leaders: {e}")
            except (PublishValidationError, PublishTransactionError):
                logger.exception("Failed to publish CANSLIM artifact bundle")
                raise

            if (
                scheduled_batch["symbols"]
                and rotation_state.get("in_progress") is not None
                and not rotation_state["in_progress"].get("remaining_symbols")
            ):
                rotation_state = finalize_success(
                    rotation_state,
                    completed_at=self._rotation_timestamp(),
                    path=ROTATION_STATE_FILE,
                )

            logger.info(f"Done! Exported {len(self.output_data['stocks'])} stocks.")
        finally:
            self._write_runtime_budget(started_at)

if __name__ == "__main__":
    CanslimEngine().run()
