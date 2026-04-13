"""
TEJ API Processor for CANSLIM analysis.
Fetches company basics, monthly revenue, quarterly EPS, and shareholder data.
"""

import os
import logging
import pandas as pd
import tejapi
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# Key accounting codes in TAIM1AQ
TEJ_ACC_CODE = {
    'revenue': '0100',      # 營業收入 (thousands NTD)
    'net_income': '0010',   # 繼續營業單位淨利 (thousands NTD)
    'eps_quarterly': 'R411', # 基本每股盈餘 (NTD, per quarter)
    'eps_cumulative': 'R403', # 累積每股盈餘 (NTD)
    'gross_margin': 'R401',  # 營業毛利率 (%)
    'operating_margin': 'R402', # 營業利益率 (%)
    'net_margin': 'R410',    # 稅後淨利率 (%)
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
    
    def get_quarterly_financials(self, coid: str) -> Optional[Dict]:
        """
        Get quarterly financial data from TRAIL/TAIM1AQ.
        Returns dict with EPS, revenue, net income for last 4 quarters.
        """
        if not self.initialized:
            return None
        
        try:
            data = tejapi.get('TRAIL/TAIM1AQ', coid=[coid], paginate=True)
            if data is None or len(data) == 0:
                return None
            
            # Get unique quarter dates (sorted descending)
            unique_dates = sorted(data['mdate'].unique(), reverse=True)[:4]
            
            result = {
                'quarters': [],
                'eps_list': [],
                'revenue_list': [],
                'net_income_list': []
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
                if quarter_info['eps'] is not None:
                    result['eps_list'].append(quarter_info['eps'])
                if quarter_info['revenue'] is not None:
                    result['revenue_list'].append(quarter_info['revenue'])
                if quarter_info['net_income'] is not None:
                    result['net_income_list'].append(quarter_info['net_income'])
            
            return result
            
        except Exception as e:
            logger.error(f"TEJ TAIM1AQ error for {coid}: {e}")
            return None
    
    def calculate_canslim_c_and_a(self, coid: str) -> Dict:
        """
        Calculate CANSLIM C (quarterly EPS growth) and A (annual EPS growth).
        Returns dict with C, A booleans and raw values.
        """
        result = {'C': False, 'A': False, 'c_eps': None, 'c_growth': None, 
                  'a_eps_current': None, 'a_eps_previous': None, 'a_growth': None}
        
        fin_data = self.get_quarterly_financials(coid)
        if fin_data is None or len(fin_data['eps_list']) < 2:
            return result
        
        eps_list = fin_data['eps_list']
        
        # C: Current quarter EPS vs same quarter last year
        if len(eps_list) >= 4:
            current_q_eps = eps_list[0]
            same_q_last_year_eps = eps_list[3] if len(eps_list) >= 4 else eps_list[0]
            
            result['c_eps'] = current_q_eps
            if same_q_last_year_eps > 0:
                c_growth = (current_q_eps - same_q_last_year_eps) / same_q_last_year_eps
                result['c_growth'] = c_growth
                result['C'] = c_growth >= 0.25  # 25% growth threshold
        
        # A: Annual EPS growth (compare cumulative EPS at year-end)
        # Use cumulative EPS (R403) - need to fetch yearly data
        # For now, use quarterly EPS annualized
        if len(eps_list) >= 4:
            # Sum of last 4 quarters (TTM EPS)
            ttm_eps = sum(eps_list[:4])
            # Sum of 4 quarters before that
            if len(eps_list) >= 8:
                prev_year_eps = sum(eps_list[4:8])
            else:
                # Estimate: use available quarters * (4/available)
                prev_year_eps = sum(eps_list[4:]) * (4 / max(len(eps_list) - 4, 1))
            
            result['a_eps_current'] = ttm_eps
            result['a_eps_previous'] = prev_year_eps
            
            if prev_year_eps > 0:
                a_growth = (ttm_eps - prev_year_eps) / prev_year_eps
                result['a_growth'] = a_growth
                result['A'] = a_growth >= 0.25  # 25% growth threshold
        
        return result
    
    def get_revenue_growth_rate(self, coid: str) -> Optional[float]:
        """
        Calculate latest revenue YoY growth rate.
        Returns growth rate as decimal (e.g. 0.15 = 15% growth).
        """
        rev_data = self.get_monthly_revenue(coid)
        if rev_data is None or len(rev_data) < 12:
            return None
        
        # Use the most recent 12 months
        recent = rev_data.tail(12)
        
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
            if len(revenues) >= 2:
                # Compare latest month vs same month last year
                latest = revenues.iloc[-1]
                year_ago = revenues.iloc[-12] if len(revenues) >= 12 else revenues.iloc[0]
                
                if year_ago > 0:
                    growth = (latest - year_ago) / year_ago
                    return growth
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
