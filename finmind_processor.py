"""
FinMind data processor for CANSLIM analysis.
Fetches institutional investors data from FinMind API.
"""

import os
import time
import logging
import pandas as pd
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

from provider_policies import ProviderRetryExhaustedError, call_with_provider_policy, get_provider_policy

try:
    from FinMind.data import DataLoader
except ImportError:
    DataLoader = None

logger = logging.getLogger(__name__)


class FinMindProcessor:
    """Process FinMind API data with batch support and optimization."""
    
    def __init__(self, token: Optional[str] = None):
        self.available = DataLoader is not None
        self.dl = None
        self.token = token or os.environ.get("FINMIND_API_TOKEN")
        self.provider_runtime_state = {
            "retry_attempts": 0,
            "retry_failures": 0,
            "provider_wait_seconds": 0.0,
            "api_usage": {},
        }
        self.investor_name_map = {
            'Foreign_Investor': '外資',
            'Investment_Trust': '投信',
            'Dealer_self': '自營商',
            'Dealer_Hedging': '自營商避險',
            'Foreign_Dealer_Self': '外資自營商'
        }
        
        if not self.available:
            logger.warning("FinMind package is not installed; FinMind-backed data fetches are disabled")
            return

        try:
            self.dl = DataLoader()
            if self.token:
                self.dl.loginbyToken(self.token)
                logger.info("FinMind logged in with token")
        except Exception as exc:
            logger.warning(f"FinMind DataLoader initialization failed: {exc}")
            self.available = False

    def get_api_usage(self) -> Dict[str, Any]:
        """Fetch current API usage and limits."""
        if not self.available or not self.token:
            return {"error": "Token not provided or API unavailable"}
        
        # NOTE: FinMind has a usage API but DataLoader might not expose it directly
        # Typically one would call the user_info or similar endpoint
        try:
            # Placeholder for actual usage check if available in library
            # For now we use the state updated by our wrapper
            return self.provider_runtime_state.get("api_usage", {})
        except Exception:
            return {}

    def fetch_all_institutional_investors(
        self, 
        date: str,
    ) -> Optional[pd.DataFrame]:
        """
        Fetch institutional investors data for ALL stocks on a specific date.
        This is much more efficient than fetching stock-by-stock.
        """
        if not self.available or self.dl is None:
            return None

        try:
            logger.info(f"Fetching market-wide institutional data for {date}")
            
            df = call_with_provider_policy(
                "finmind",
                lambda: self.dl.taiwan_stock_institutional_investors(
                    start_date=date,
                    end_date=date,
                ),
                runtime_state=self.provider_runtime_state,
            )

            if df is None or len(df) == 0:
                logger.warning(f"No institutional data for date {date}")
                return None
            
            logger.info(f"Fetched {len(df)} records for market on {date}")
            return df
        except Exception as e:
            logger.error(f"Failed to fetch market institutional data: {e}")
            return None

    def fetch_institutional_investors(
        self,
        stock_id: str,
        start_date: str,
        end_date: str
    ) -> Optional[pd.DataFrame]:
        """
        Fetch institutional investors data for a single stock.
        """
        if not self.available or self.dl is None:
            return None
            
        try:
            df = call_with_provider_policy(
                "finmind",
                lambda: self.dl.taiwan_stock_institutional_investors(
                    stock_id=stock_id,
                    start_date=start_date,
                    end_date=end_date,
                ),
                runtime_state=self.provider_runtime_state,
            )

            if df is None or len(df) == 0:
                return None
            
            return df
        except Exception as e:
            logger.error(f"Failed to fetch data for {stock_id}: {e}")
            return None

    def parse_institutional_data(self, df: pd.DataFrame) -> Optional[Dict[str, Dict]]:
        """Parse and aggregate data by date."""
        if df is None or len(df) == 0:
            return None
        
        try:
            result = {}
            # Faster aggregation using pandas
            df['net'] = df['buy'] - df['sell']
            
            # Map investor types
            df['type'] = 'other'
            df.loc[df['name'].str.contains('Foreign_Investor'), 'type'] = 'foreign'
            df.loc[df['name'].str.contains('Investment_Trust'), 'type'] = 'trust'
            df.loc[df['name'].str.contains('Dealer'), 'type'] = 'dealer'
            
            grouped = df.groupby(['date', 'type'])['net'].sum().unstack(fill_value=0)
            
            for date, row in grouped.iterrows():
                result[date] = {
                    'foreign_net': int(row.get('foreign', 0) // 1000),
                    'trust_net': int(row.get('trust', 0) // 1000),
                    'dealer_net': int(row.get('dealer', 0) // 1000),
                    'date': date.replace('-', '')
                }
            
            return result
        except Exception as e:
            logger.error(f"Parse failure: {e}")
            return None

    def fetch_recent_trading_days(self, stock_id: str, days: int = 20) -> Optional[Dict[str, Dict]]:
        """Legacy helper for single-stock fetch."""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days * 2)
        df = self.fetch_institutional_investors(stock_id, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
        return self.parse_institutional_data(df)
    
    def get_institutional_summary(self, inst_data: Dict[str, Dict]) -> Dict:
        """
        Get summary statistics from institutional data.
        
        Args:
            inst_data: Parsed institutional data dict
        
        Returns:
            Summary statistics
        """
        if not inst_data:
            return {}
        
        dates = sorted(inst_data.keys())
        
        foreign_total = sum([data['foreign_net'] for data in inst_data.values()])
        trust_total = sum([data['trust_net'] for data in inst_data.values()])
        dealer_total = sum([data['dealer_net'] for data in inst_data.values()])
        
        # Consecutive buying/selling
        consecutive_buy = 0
        consecutive_sell = 0
        
        for date in dates:
            data = inst_data[date]
            total_net = data['foreign_net'] + data['trust_net'] + data['dealer_net']
            
            if total_net > 0:
                consecutive_buy += 1
                consecutive_sell = 0
            else:
                consecutive_sell += 1
                consecutive_buy = 0
        
        return {
            'foreign_total': foreign_total,
            'trust_total': trust_total,
            'dealer_total': dealer_total,
            'total_net': foreign_total + trust_total + dealer_total,
            'consecutive_buy': consecutive_buy,
            'consecutive_sell': consecutive_sell,
            'trading_days': len(dates)
        }
