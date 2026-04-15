"""
FinMind data processor for CANSLIM analysis.
Fetches institutional investors data from FinMind API.
"""

import os
import logging
import pandas as pd
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from FinMind.data import DataLoader

logger = logging.getLogger(__name__)


class FinMindProcessor:
    """Process FinMind API data for institutional investors."""
    
    def __init__(self):
        try:
            self.dl = DataLoader()
        except Exception as e:
            logger.error(f"Failed to initialize FinMind DataLoader: {e}")
            self.dl = None
            
        self.investor_name_map = {
            'Foreign_Investor': '外資',
            'Investment_Trust': '投信',
            'Dealer_self': '自營商',
            'Dealer_Hedging': '自營商避險',
            'Foreign_Dealer_Self': '外資自營商'
        }
    
    def calculate_net(self, buy: int, sell: int) -> int:
        """Calculate net buy/sell."""
        return buy - sell
    
    def map_investor_name(self, english_name: str) -> str:
        """Map English investor name to Chinese."""
        return self.investor_name_map.get(english_name, english_name)
    
    def fetch_institutional_investors(
        self,
        stock_id: str,
        start_date: str,
        end_date: str
    ) -> Optional[pd.DataFrame]:
        """
        Fetch institutional investors data from FinMind.
        
        Args:
            stock_id: Stock code (e.g., "2330")
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
        
        Returns:
            DataFrame with institutional data or None on failure
        """
        try:
            logger.info(f"Fetching institutional data for {stock_id} ({start_date} to {end_date})")
            
            df = self.dl.taiwan_stock_institutional_investors(
                stock_id=stock_id,
                start_date=start_date,
                end_date=end_date
            )
            
            if df is None or len(df) == 0:
                logger.warning(f"No institutional data for {stock_id}")
                return None
            
            logger.info(f"Fetched {len(df)} records for {stock_id}")
            return df
            
        except Exception as e:
            logger.error(f"Failed to fetch institutional data for {stock_id}: {e}")
            return None
    
    def parse_institutional_data(self, df: pd.DataFrame) -> Optional[Dict[str, Dict]]:
        """
        Parse and aggregate institutional data by date.
        
        Args:
            df: Raw DataFrame from FinMind API
        
        Returns:
            Dict with date as key and institutional flows as values
        """
        if df is None or len(df) == 0:
            return None
        
        try:
            result = {}
            
            # Group by date
            for date in df['date'].unique():
                day_data = df[df['date'] == date]
                
                foreign_net = 0
                trust_net = 0
                dealer_net = 0
                
                for _, row in day_data.iterrows():
                    name = row['name']
                    buy = row['buy'] if pd.notna(row['buy']) else 0
                    sell = row['sell'] if pd.notna(row['sell']) else 0
                    net = self.calculate_net(int(buy), int(sell))
                    
                    # Aggregate by investor type
                    if 'Foreign_Investor' in name:
                        foreign_net += net
                    elif 'Investment_Trust' in name:
                        trust_net += net
                    elif 'Dealer' in name:
                        dealer_net += net
                
                # Convert to lots (1 lot = 1000 shares)
                result[date] = {
                    'foreign_net': foreign_net // 1000,
                    'trust_net': trust_net // 1000,
                    'dealer_net': dealer_net // 1000,
                    'date': date.replace('-', '')
                }
            
            logger.info(f"Parsed institutional data for {len(result)} days")
            return result
            
        except Exception as e:
            logger.error(f"Failed to parse institutional data: {e}")
            return None
    
    def fetch_recent_trading_days(
        self,
        stock_id: str,
        days: int = 20
    ) -> Optional[Dict[str, Dict]]:
        """
        Fetch recent N trading days of institutional data.
        
        Args:
            stock_id: Stock code
            days: Number of trading days to fetch
        
        Returns:
            Parsed institutional data dict
        """
        try:
            # Calculate date range (add more buffer for holidays/weekends/long lookbacks)
            # For 60 trading days, we need about 90 calendar days
            end_date = datetime.now()
            start_date = end_date - timedelta(days=int(days * 1.6) + 7)  # Buffer factor 1.6 + 1 week
            
            start_str = start_date.strftime('%Y-%m-%d')
            end_str = end_date.strftime('%Y-%m-%d')
            
            # Fetch raw data
            df = self.fetch_institutional_investors(stock_id, start_str, end_str)
            
            if df is None:
                return None
            
            # Parse and aggregate
            parsed = self.parse_institutional_data(df)
            
            if parsed is None:
                return None
            
            # Return only the most recent N days
            sorted_dates = sorted(parsed.keys(), reverse=True)
            result = {date: parsed[date] for date in sorted_dates[:days]}
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to fetch recent trading days for {stock_id}: {e}")
            return None

    def fetch_stock_info(self, stock_id: str) -> Optional[pd.DataFrame]:
        """Fetch basic stock info including share issued."""
        try:
            df = self.dl.taiwan_stock_info()
            if df is not None:
                return df[df['stock_id'] == stock_id]
            return None
        except Exception as e:
            logger.error(f"Failed to fetch stock info for {stock_id}: {e}")
            return None
    
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
