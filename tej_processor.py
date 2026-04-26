"""
TEJ API Processor for CANSLIM analysis.
Fetches company basics, monthly revenue, quarterly EPS, and shareholder data.
"""

import os
import logging
import pandas as pd
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

from provider_policies import ProviderRetryExhaustedError, call_with_provider_policy, get_provider_policy

try:
    import tejapi
except ImportError:  # pragma: no cover - exercised via environments without tejapi
    tejapi = None

logger = logging.getLogger(__name__)

# Key accounting codes in TAIM1AQ and specific tables
TEJ_ACC_CODE = {
    'revenue': '0100',      # 營業收入 (thousands NTD)
    'net_income': '0010',   # 繼續營業單位淨利 (thousands NTD)
    'eps_quarterly': 'R411', # 基本每股盈餘 (NTD, per quarter)
    'eps_cumulative': 'R403', # 累積每股盈餘 (NTD)
    'gross_margin': 'R401',  # 營業毛利率 (%)
    'operating_margin': 'R402', # 營業利益率 (%)
    'net_margin': 'R410',    # 稅後淨利率 (%)
    'equity': '3000',        # 權益總額 (thousands NTD) - for ROE
    'operating_cash_flow': 'C001', # 營業活動現金流量
}

class TEJProcessor:
    """Process TEJ API data for CANSLIM engine."""
    
    def __init__(self, api_key: str = None):
        self.error_count = 0
        self.max_errors = 3
        self.provider_runtime_state = {
            "retry_attempts": 0,
            "retry_failures": 0,
            "provider_wait_seconds": 0.0,
        }
        if tejapi is None:
            logger.warning("tejapi package is not installed")
            self.api_key = None
            self.initialized = False
            return

        self.api_key = api_key or os.environ.get('TEJ_API_KEY')
        if not self.api_key:
            # Try to load from .env file
            try:
                with open('.env') as f:
                    for line in f:
                        if line.startswith('TEJ_API_KEY='):
                            self.api_key = line.split('=', 1)[1].strip()
                            break
            except:
                pass
        
        if not self.api_key:
            logger.warning("TEJ API key not set")
            self.initialized = False
            return
        
        tejapi.ApiConfig.api_key = self.api_key
        tejapi.ApiConfig.ignoretz = True
        self.initialized = True
        logger.info("TEJ API initialized")

    def _tej_get_with_policy(self, table: str, **kwargs) -> Optional[pd.DataFrame]:
        """Route all TEJ table fetches through the shared provider policy contract."""
        if not self.initialized or tejapi is None:
            return None
        
        if self.error_count >= self.max_errors:
            if self.initialized:
                logger.warning("🚀 TEJ Circuit Breaker Tripped: Disabling TEJ for this run to save time.")
                self.initialized = False
            return None

        policy = get_provider_policy("tej")
        try:
            res = call_with_provider_policy(
                "tej",
                lambda: tejapi.get(table, **kwargs),
                runtime_state=self.provider_runtime_state,
            )
            self.error_count = 0
            return res
        except ProviderRetryExhaustedError as exc:
            self.error_count += 1
            logger.warning(f"TEJ {table} unavailable (limit or permission): {exc}")
            return None
        except Exception as exc:
            err_str = str(exc)
            if "LimitExceededError" in err_str or "ForbiddenError" in err_str:
                self.error_count += 1
                logger.warning(f"TEJ {table} failed with quota/auth error: {err_str}")
            return None

    def get_daily_prices(self, coid: str, 
                         start_date: str = None, 
                         end_date: str = None,
                         count: int = None,
                         suffix: str = None) -> Optional[pd.DataFrame]:
        """
        Get daily price data. Tries TRAIL/TAPRCD, then falls back to yfinance 
        if permission is denied.
        """
        if not self.initialized:
            # 這裡必須支援即便 TEJ 未初始化，也要能觸發 yfinance fallback
            pass
        else:
            try:
                params = {'coid': [coid], 'paginate': True}
                if start_date:
                    params['mdate'] = {'gte': start_date}
                
                # 1. Try TEJ
                data = None
                for table in ['TRAIL/TAPRCD', 'TRAIL/APRCD']:
                    try:
                        data = self._tej_get_with_policy(table, **params)
                        if data is not None and not data.empty:
                            logger.info(f"Fetched prices from TEJ {table}")
                            break
                    except Exception as exc:
                        logger.warning(f"TEJ {table} failed: {exc}. Trying next table or fallback...")
                        continue

                if data is not None and not data.empty:
                    # Standardize columns
                    data = data.rename(columns={
                        'mdate': 'date', 'open_d': 'open', 'high_d': 'high',
                        'low_d': 'low', 'close_d': 'close', 'vol': 'volume'
                    })
                    data['date'] = pd.to_datetime(data['date'])
                    data = data.sort_values('date')
                    # 確保時區正確 (tz-naive)
                    if data['date'].dt.tz is not None:
                        data['date'] = data['date'].dt.tz_localize(None)
                    return data
            except Exception as e:
                logger.error(f"TEJ price fetch logic error for {coid}: {e}")

        # 2. Fallback to yfinance
        import yfinance as yf
        logger.info(f"Falling back to yfinance for {coid}")
        
        if coid == "TAIEX":
            ticker_id = "^TWII"
        elif suffix:
            ticker_id = f"{coid}{suffix}"
        else:
            actual_suffix = ".TWO" if len(coid) == 4 and coid[0] in '34568' else ".TW"
            ticker_id = f"{coid}{actual_suffix}"
            
        try:
            yf_data = yf.download(ticker_id, start=start_date, end=end_date, progress=False)
            if not yf_data.empty:
                if isinstance(yf_data.columns, pd.MultiIndex):
                    yf_data.columns = yf_data.columns.get_level_values(0)
                
                yf_data = yf_data.reset_index()
                yf_data.columns = [str(c).lower() for c in yf_data.columns]
                if 'adj close' in yf_data.columns:
                    yf_data = yf_data.rename(columns={'adj close': 'close'})
                
                # 強制 tz-naive
                if 'date' in yf_data.columns:
                    yf_data['date'] = pd.to_datetime(yf_data['date']).dt.tz_localize(None)
                return yf_data
        except Exception as e:
            logger.error(f"yfinance download failed for {ticker_id}: {e}")
            
        return None

    def get_income_statement(self, coid: str, count: int = 8) -> Optional[pd.DataFrame]:
        """Fetch income statement from TEJ."""
        return self._tej_get_with_policy('TRAIL/TAIM1AQ', coid=[coid], paginate=True)

    def get_quarterly_financials(self, coid: str) -> Optional[Dict[str, Any]]:
        """Extract key metrics from income statement."""
        df = self.get_income_statement(coid)
        if df is None or df.empty:
            return None
        return {"raw_count": len(df)} # 簡化版，僅用於示範

    def calculate_canslim_c_and_a(self, coid: str) -> Dict[str, Any]:
        """Place holder for C and A factors derived from financials."""
        return {}
