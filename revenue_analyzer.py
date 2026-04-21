"""
Revenue Feature Analyzer for tw-canslim-web.
Calculates YoY, MoM growth and acceleration factors.
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, List

def calculate_revenue_score(features: Dict) -> int:
    """
    Calculate revenue score based on growth thresholds.
    Spec:
    - if rev_yoy > 0.25: score += 1
    - if rev_yoy > 0.50: score += 1
    - if rev_mom > 0: score += 1
    - if rev_mom > 0.1: score += 1
    - if rev_acc_1 > 0: score += 1
    - if rev_acc_2 > 0: score += 1
    """
    score = 0
    yoy = features.get('rev_yoy', 0) or 0
    mom = features.get('rev_mom', 0) or 0
    acc1 = features.get('rev_acc_1', 0) or 0
    acc2 = features.get('rev_acc_2', 0) or 0
    
    if yoy > 0.25: score += 1
    if yoy > 0.50: score += 1
    if mom > 0: score += 1
    if mom > 0.1: score += 1
    if acc1 > 0: score += 1
    if acc2 > 0: score += 1
    
    return score

def calculate_revenue_features(rev_df: pd.DataFrame) -> Optional[Dict]:
    """
    Calculate revenue features from monthly revenue dataframe.
    Requires at least 15 months of data to compute 3 months of YoY growth.
    """
    if rev_df is None or len(rev_df) < 15:
        return None
    
    # Identify revenue column
    rev_col = None
    for col in ['r16', 'r17', 'r18', 'r19']:
        if col in rev_df.columns:
            rev_col = col
            break
    
    if rev_col is None:
        # Fallback to any numeric column that might be revenue if common ones are missing
        numeric_cols = rev_df.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) > 0:
            rev_col = numeric_cols[0]
        else:
            return None

    # Ensure sorted by date
    if 'mdate' in rev_df.columns:
        df = rev_df.sort_values('mdate').copy()
    else:
        df = rev_df.copy()

    try:
        rev_series = df[rev_col].astype(float)
        
        # Latest values
        rev_now = rev_series.iloc[-1]
        rev_prev = rev_series.iloc[-2]
        rev_last_year = rev_series.iloc[-13]
        
        # YoY calculations
        # rev_yoy = (rev_now - rev_last_year) / rev_last_year
        def calc_growth(current, previous):
            if previous > 0:
                return (current - previous) / previous
            return 0.0

        rev_yoy_now = calc_growth(rev_now, rev_last_year)
        rev_yoy_prev = calc_growth(rev_prev, rev_series.iloc[-14])
        rev_yoy_prev2 = calc_growth(rev_series.iloc[-3], rev_series.iloc[-15])
        
        rev_mom = calc_growth(rev_now, rev_prev)
        
        rev_acc_1 = rev_yoy_now - rev_yoy_prev
        rev_acc_2 = rev_yoy_prev - rev_yoy_prev2
        
        features = {
            'rev_yoy': rev_yoy_now,
            'rev_mom': rev_mom,
            'rev_acc_1': rev_acc_1,
            'rev_acc_2': rev_acc_2,
            'rev_accelerating': rev_yoy_now > rev_yoy_prev > rev_yoy_prev2,
            'rev_strong': rev_yoy_now > 0.3 and rev_mom > 0.1
        }
        
        features['revenue_score'] = calculate_revenue_score(features)
        
        return features
        
    except Exception as e:
        # Log error in real implementation, here we return None as per spec/T-05-01
        return None
