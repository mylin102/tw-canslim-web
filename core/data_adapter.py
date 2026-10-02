"""
Data Adapter for handling historical time-series alignment.
Implements Safe Release Lag logic to prevent look-ahead bias.
"""

import pandas as pd
from datetime import datetime, timedelta

def apply_announcement_lag(df_eps: pd.DataFrame) -> pd.DataFrame:
    """
    Adjusts the date of EPS data points to reflect the statutory 
    announcement deadlines in Taiwan.
    
    Rules:
    - Q1 (ending 03-31): Effective on 05-15
    - Q2 (ending 06-30): Effective on 08-14
    - Q3 (ending 09-30): Effective on 11-14
    - Q4 (ending 12-31): Effective on 03-31 of next year
    
    Input DataFrame must have columns: ['stock_id', 'date', 'eps']
    """
    df = df_eps.copy()
    df['date'] = pd.to_datetime(df['date'])
    
    def get_lagged_date(row_date):
        year = row_date.year
        month = row_date.month
        
        if month <= 3:   # Q4 of previous year
            return datetime(year, 3, 31)
        elif month <= 6: # Q1
            return datetime(year, 5, 15)
        elif month <= 9: # Q2
            return datetime(year, 8, 14)
        else:            # Q3
            return datetime(year, 11, 14)

    df['effective_date'] = df['date'].apply(get_lagged_date)
    # If the lagged date is actually before the data date (unlikely but safe), 
    # use the data date
    df['effective_date'] = df.apply(
        lambda x: max(x['effective_date'], x['date'] + timedelta(days=1)), axis=1
    )
    
    return df.sort_values(['stock_id', 'effective_date'])

def apply_dividend_adjustment(df_price: pd.DataFrame, df_dividend: pd.DataFrame) -> pd.DataFrame:
    """
    Back-adjusts OHLC columns for ex-dividend/ex-rights price drops, using the
    same before/after ex-date reference prices TWSE itself publishes
    (FinMind's TaiwanStockDividendResult). Without this, raw close prices
    understate returns for dividend-paying stocks -- TWSE issuers average a
    3-5%/year yield, which compounds to a 15-25% return gap over 5 years and
    skews return-based ranking (e.g. the L/relative-strength factor).

    Input df_price must have columns: ['date', 'open', 'max', 'min', 'close'].
    Input df_dividend must have columns: ['date', 'before_price', 'after_price']
    (one row per ex-dividend/ex-rights event, as returned by
    DataLoader.taiwan_stock_dividend_result).
    """
    df = df_price.copy()
    df['date'] = pd.to_datetime(df['date'])

    if df_dividend is None or df_dividend.empty:
        df['close_adj'] = df['close']
        return df

    events = df_dividend.copy()
    events['date'] = pd.to_datetime(events['date'])
    events = events.dropna(subset=['before_price', 'after_price'])
    events = events[events['before_price'] != 0]
    events = events.sort_values('date', ascending=False)

    # Standard backward adjustment: for each ex-date event, scale every price
    # strictly before that date by after_price/before_price, applied
    # cumulatively from the most recent event back to the earliest.
    factor = pd.Series(1.0, index=df.index)
    for _, ev in events.iterrows():
        ratio = ev['after_price'] / ev['before_price']
        mask = df['date'] < ev['date']
        factor.loc[mask] *= ratio

    for col in ('open', 'max', 'min', 'close'):
        if col in df.columns:
            df[f'{col}_adj'] = df[col] * factor

    return df


def resample_to_daily(df_historical: pd.DataFrame, start_date: str, end_date: str) -> pd.DataFrame:
    """
    Resamples quarterly/intermittent data to daily frequency using forward fill.
    Ensures backtest engine has a score for every trading day.
    """
    date_range = pd.date_range(start=start_date, end=end_date, freq='D')
    all_stocks = df_historical['stock_id'].unique()
    
    full_index = pd.MultiIndex.from_product(
        [all_stocks, date_range], names=['stock_id', 'date']
    )
    
    # Drop original 'date' to avoid column conflict after rename
    df_resample = df_historical.drop(columns=['date'])
    df_daily = df_resample.set_index(['stock_id', 'effective_date'])
    df_daily.index.names = ['stock_id', 'date']
    
    # Reindex and forward fill to carry the last known score/eps forward
    df_daily = df_daily.reindex(full_index).groupby('stock_id').ffill().reset_index()
    
    return df_daily
