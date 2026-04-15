"""
TEJ API Processor for CANSLIM analysis.
Fetches company basics, monthly revenue, quarterly EPS, and shareholder data.
"""

import os
import logging
import pandas as pd
import tejapi
from typing import Dict, List, Optional
from datetime import datetime, timedelta

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

    def get_daily_prices(self, coid: str, 
                         start_date: str = None, 
                         end_date: str = None,
                         count: int = None) -> Optional[pd.DataFrame]:
        """
        Get daily price data. Tries TRAIL/TAPRCD then TWN/APRCD.
        Used for RS score, technical analysis, and grid trading.
        """
        if not self.initialized:
            return None
        
        try:
            params = {'coid': [coid], 'paginate': True}
            if start_date:
                params['mdate'] = {'gte': start_date}
            if end_date:
                if 'mdate' not in params: params['mdate'] = {}
                params['mdate']['lte'] = end_date
            
            # Try TRAIL first (common for trial keys)
            try:
                data = tejapi.get('TRAIL/TAPRCD', **params)
            except:
                # Fallback to standard TWN table
                data = tejapi.get('TWN/APRCD', **params)

            if data is None or len(data) == 0:
                return None
            
            # Standardize columns
            data = data.rename(columns={
                'mdate': 'date',
                'open_d': 'open',
                'high_d': 'high',
                'low_d': 'low',
                'close_d': 'close',
                'vol_nk': 'volume'
            })
            
            # Sort by date and take latest N
            data['date'] = pd.to_datetime(data['date'])
            data = data.sort_values('date')
            if count:
                data = data.tail(count)
                
            return data
        except Exception as e:
            logger.error(f"TEJ price fetch error for {coid}: {e}")
            return None

    def get_income_statement(self, coid: str, count: int = 8) -> Optional[pd.DataFrame]:
        """Fetch income statement. Tries TRAIL/TAINDB then TWN/AINSTB."""
        data = self._get_financial_statement('TRAIL/TAINDB', coid, count)
        if data is None:
            data = self._get_financial_statement('TWN/AINSTB', coid, count)
        return data

    def get_balance_sheet(self, coid: str, count: int = 8) -> Optional[pd.DataFrame]:
        """Fetch balance sheet. Tries TRAIL/TABSTB then TWN/ABSTB."""
        data = self._get_financial_statement('TRAIL/TABSTB', coid, count)
        if data is None:
            data = self._get_financial_statement('TWN/ABSTB', coid, count)
        return data

    def get_cash_flow(self, coid: str, count: int = 8) -> Optional[pd.DataFrame]:
        """Fetch cash flow. Tries TRAIL/TACFTB then TWN/ACFTB."""
        data = self._get_financial_statement('TRAIL/TACFTB', coid, count)
        if data is None:
            data = self._get_financial_statement('TWN/ACFTB', coid, count)
        return data

    def get_official_revenue(self, coid: str, count: int = 24) -> Optional[pd.DataFrame]:
        """Fetch official revenue. Tries TRAIL/TAPREV then TWN/APREV."""
        data = self._get_financial_statement('TRAIL/TAPREV', coid, count)
        if data is None:
            data = self._get_financial_statement('TWN/APREV', coid, count)
        return data

    def _get_financial_statement(self, table: str, coid: str, count: int) -> Optional[pd.DataFrame]:
        """Generic fetcher for TWN financial tables."""
        if not self.initialized:
            return None
        try:
            # TWN tables usually have coid, mdate, and acc_code/val patterns
            # Or they might be pivoted. For these specific tables, they are usually in 'acc_code' format
            data = tejapi.get(table, coid=[coid], paginate=True)
            if data is None or len(data) == 0:
                return None
            
            # Sort by date descending and take top N unique dates
            unique_dates = sorted(data['mdate'].unique(), reverse=True)[:count]
            return data[data['mdate'].isin(unique_dates)]
        except Exception as e:
            logger.error(f"TEJ {table} error for {coid}: {e}")
            return None
    
    def get_company_info(self, coid: str) -> Optional[Dict]:
        """
        Get company basic info from TRAIL/AIND.
        Returns industry, listing status, contact info.
        """
        if not self.initialized:
            return None
        
        try:
            data = tejapi.get('TRAIL/AIND', coid=[coid], paginate=True)
            if data is None or len(data) == 0:
                return None
            
            row = data.iloc[0]
            return {
                'coid': row.get('coid'),
                'mkt': row.get('mkt'),  # TSE or OTC
                'elist_day1': str(row.get('elist_day1')) if pd.notna(row.get('elist_day1')) else None,
                'ind1': row.get('ind1'),
                'tejind1_c': row.get('tejind1_c'),  # 產業分類
                'tejind2_c': row.get('tejind2_c'),  # 次產業
                'tejind3_c': row.get('tejind3_c'),  # 細分類
                'empsum': row.get('empsum'),  # 員工人數
                'parvalue': row.get('parvalue'),
                'estb_date': str(row.get('estb_date')) if pd.notna(row.get('estb_date')) else None,
                'website': row.get('website'),
                'fnamec': row.get('fnamec'),
                'inamec': row.get('inamec'),
            }
        except Exception as e:
            logger.error(f"TEJ AIND error for {coid}: {e}")
            return None
    
    def get_monthly_revenue(self, coid: str, 
                           start_date: str = None, 
                           end_date: str = None) -> Optional[pd.DataFrame]:
        """
        Get monthly revenue from TRAIL/TASALE.
        Used for CANSLIM C (quarterly EPS growth) and A (annual growth).
        """
        if not self.initialized:
            return None
        
        try:
            params = {'coid': [coid], 'paginate': True}
            if start_date and end_date:
                params['mdate'] = {'gte': start_date, 'lte': end_date}
            
            data = tejapi.get('TRAIL/TASALE', **params)
            if data is None or len(data) == 0:
                return None
            
            # Select key columns
            key_cols = ['mdate', 'annd_s', 'd0001', 'd0002', 'd0003', 'r16', 'r17', 
                       'r18', 'r19', 'r25', 'r26', 'r27', 'r28', 'r29', 'r30', 'r31']
            available_cols = [c for c in key_cols if c in data.columns]
            
            return data[available_cols]
            
        except Exception as e:
            logger.error(f"TEJ TASALE error for {coid}: {e}")
            return None
    
    def get_shareholder_meetings(self, coid: str,
                                start_date: str = None,
                                end_date: str = None) -> Optional[pd.DataFrame]:
        """
        Get shareholder meeting data from TRAIL/TAMT.
        Used for dividend info, capital increase, etc.
        """
        if not self.initialized:
            return None
        
        try:
            params = {'coid': [coid], 'paginate': True}
            if start_date and end_date:
                params['mdate'] = {'gte': start_date, 'lte': end_date}
            
            data = tejapi.get('TRAIL/TAMT', **params)
            if data is None or len(data) == 0:
                return None
            
            return data
            
        except Exception as e:
            logger.error(f"TEJ TAMT error for {coid}: {e}")
            return None
    
    def get_quarterly_financials(self, coid: str, count: int = 8) -> Optional[Dict]:
        """
        Get quarterly financial data from TRAIL/TAIM1AQ.
        Returns dict with EPS, revenue, net income for last N quarters.
        """
        if not self.initialized:
            return None
        
        try:
            # Optimize: fetch only required accounting codes and recent dates
            # We need at least 'count' unique dates
            # Fetch last 3 years to be safe
            start_date = (datetime.now() - timedelta(days=365*3)).strftime('%Y-%m-%d')
            data = tejapi.get('TRAIL/TAIM1AQ', 
                              coid=[coid], 
                              acc_code=list(TEJ_ACC_CODE.values()),
                              mdate={'gte': start_date},
                              paginate=True)
            
            if data is None or len(data) == 0:
                return None
            
            # Get unique quarter dates (sorted descending)
            unique_dates = sorted(data['mdate'].unique(), reverse=True)[:count]
            
            result = {
                'quarters': [],
                'eps_list': [],
                'revenue_list': [],
                'net_income_list': [],
                'dates': []
            }
            
            for mdate in unique_dates:
                q_data = data[data['mdate'] == mdate]
                
                quarter_info = {
                    'date': str(mdate),
                    'eps': None,
                    'revenue': None,
                    'net_income': None,
                    'gross_margin': None,
                    'operating_margin': None,
                    'net_margin': None,
                }
                
                for _, row in q_data.iterrows():
                    code = row['acc_code']
                    val = row['acc_value']
                    if pd.isna(val):
                        continue
                    
                    if code == TEJ_ACC_CODE['eps_quarterly']:
                        quarter_info['eps'] = float(val)
                    elif code == TEJ_ACC_CODE['revenue']:
                        quarter_info['revenue'] = float(val) / 1e6
                    elif code == TEJ_ACC_CODE['net_income']:
                        quarter_info['net_income'] = float(val) / 1e6
                    elif code == TEJ_ACC_CODE['gross_margin']:
                        quarter_info['gross_margin'] = float(val)
                    elif code == TEJ_ACC_CODE['operating_margin']:
                        quarter_info['operating_margin'] = float(val)
                    elif code == TEJ_ACC_CODE['net_margin']:
                        quarter_info['net_margin'] = float(val)
                
                result['quarters'].append(quarter_info)
                result['dates'].append(mdate)
                # Still keep lists for backward compatibility in calculate logic
                result['eps_list'].append(quarter_info['eps'] if quarter_info['eps'] is not None else 0.0)
                result['revenue_list'].append(quarter_info['revenue'] if quarter_info['revenue'] is not None else 0.0)
                result['net_income_list'].append(quarter_info['net_income'] if quarter_info['net_income'] is not None else 0.0)
            
            return result
            
        except Exception as e:
            logger.error(f"TEJ TAIM1AQ error for {coid}: {e}")
            return None
    
    def is_etf(self, coid: str) -> bool:
        """
        Detects if a symbol is an ETF in Taiwan market.
        Rule: Starts with '00' and is 5 or 6 digits, or has L/R suffixes.
        """
        # Rule 1: 00-prefix with 5-6 digits (e.g., 0050, 00631L, 00981A)
        if coid.startswith('00') and (len(coid) == 5 or len(coid) == 6 or len(coid) == 4):
            return True
            
        # Rule 2: Leveraged/Inverse suffixes (older pattern)
        if coid.endswith('L') or coid.endswith('R'): 
            return True
            
        return False

    def calculate_canslim_c_and_a(self, coid: str) -> Dict:
        """
        Calculate CANSLIM C and A using refined logic.
        Delegates core calculation to core.logic.
        """
        from core.logic import calculate_c_factor, calculate_a_factor
        
        result = {'C': False, 'A': False, 'c_eps': None, 'c_growth': None, 
                  'a_eps_current': None, 'a_eps_previous': None, 'a_growth': None,
                  'is_etf': self.is_etf(coid)}
        
        if result['is_etf']:
            return result # Skip C/A for ETFs
            
        fin_data = self.get_quarterly_financials(coid, count=12)
        if fin_data is None or len(fin_data['eps_list']) < 5:
            return result
        
        eps_list = fin_data['eps_list']
        # eps_list is [current, q-1, q-2, q-3, q-4, ...]
        # core.logic expects series where iloc[-1] is current
        eps_series = pd.Series(eps_list[::-1]) 
        
        # Calculate C
        result['C'] = calculate_c_factor(eps_series)
        result['c_eps'] = eps_list[0]
        
        # Calculate A (Annual)
        # Prepare annual EPS (sum of 4 quarters)
        annual_eps = []
        if len(eps_list) >= 8:
            annual_eps.append(sum(eps_list[4:8])) # Previous Year
            annual_eps.append(sum(eps_list[:4]))  # Current Year (TTM)
            
            # Get ROE if possible (Net Income / Avg Equity)
            # For simplicity, use latest Net Income / latest Equity from Balance Sheet
            roe = None
            try:
                # This would ideally be calculated from get_balance_sheet
                # For now, if we have it in TAIM1AQ result
                # (Need to ensure TAIM1AQ fetch includes equity code)
                pass
            except:
                pass
                
            result['A'] = calculate_a_factor(pd.Series(annual_eps), roe=roe)
            result['a_eps_current'] = annual_eps[1]
            result['a_eps_previous'] = annual_eps[0]
            
        return result
    
    def get_revenue_growth_rate(self, coid: str) -> Optional[float]:
        """
        Calculate latest revenue YoY growth rate.
        Returns growth rate as decimal (e.g. 0.15 = 15% growth).
        """
        rev_data = self.get_monthly_revenue(coid)
        if rev_data is None or len(rev_data) < 13: # Need 13 months for YoY
            return None
        
        # Use the most recent 13 months to get current and month last year
        recent = rev_data.tail(13)
        
        # Look for revenue column (common names in TASALE)
        rev_col = None
        for col in ['r16', 'r17', 'r18', 'r19']:
            if col in recent.columns:
                rev_col = col
                break
        
        if rev_col is None:
            return None
        
        try:
            revenues = recent[rev_col].astype(float)
            # Compare latest month vs same month last year
            latest = revenues.iloc[-1]
            year_ago = revenues.iloc[-13]
            
            if year_ago > 0:
                growth = (latest - year_ago) / year_ago
                return growth
        except:
            pass
        
        return None
    
    def get_revenue_quarterly_growth(self, coid: str) -> Optional[float]:
        """
        Calculate latest quarterly revenue YoY growth rate.
        Used as a proxy for CANSLIM C if EPS is not yet available.
        """
        rev_data = self.get_monthly_revenue(coid)
        if rev_data is None or len(rev_data) < 15:
            return None
        
        # Calculate quarterly revenue (sum of 3 months)
        try:
            rev_col = None
            for col in ['r16', 'r17', 'r18', 'r19']:
                if col in rev_data.columns:
                    rev_col = col
                    break
            
            if rev_col is None: return None
            
            # Latest 3 months vs same 3 months last year
            current_q = rev_data[rev_col].iloc[-3:].sum()
            last_year_q = rev_data[rev_col].iloc[-15:-12].sum()
            
            if last_year_q > 0:
                return (current_q - last_year_q) / last_year_q
        except:
            pass
        return None

    def bulk_fetch_companies(self, coids: List[str]) -> Dict:
        """
        Fetch data for multiple stocks at once.
        Returns dict with company info and revenue data.
        """
        result = {}
        
        # Fetch company info in bulk
        if self.initialized:
            try:
                data = tejapi.get('TRAIL/AIND', coid=coids, paginate=True)
                if data is not None and len(data) > 0:
                    for _, row in data.iterrows():
                        coid = row.get('coid')
                        result[coid] = {
                            'company_info': {
                                'mkt': row.get('mkt'),
                                'tejind1_c': row.get('tejind1_c'),
                                'tejind2_c': row.get('tejind2_c'),
                                'tejind3_c': row.get('tejind3_c'),
                            }
                        }
            except Exception as e:
                logger.error(f"TEJ bulk AIND error: {e}")
        
        return result
