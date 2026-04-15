
import os
import logging
import pandas as pd
from tej_processor import TEJProcessor
from core.logic import calculate_volatility_grid

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_tej():
    # Ensure API key is present
    api_key = os.environ.get('TEJ_API_KEY')
    if not api_key:
        print("❌ TEJ_API_KEY not found in environment variables.")
        return

    tej = TEJProcessor(api_key)
    if not tej.initialized:
        print("❌ Failed to initialize TEJ API.")
        return

    test_symbols = ["2330", "0050", "00631L"]
    
    print("\n" + "="*50)
    print("🚀 TEJ Processor & Core Logic Integration Test")
    print("="*50)

    for sym in test_symbols:
        print(f"\n--- Testing Symbol: {sym} ---")
        
        # 1. Check ETF status
        is_etf = tej.is_etf(sym)
        print(f"Type: {'ETF' if is_etf else 'Stock'}")

        # 2. Test CANSLIM C and A
        print("Calculating CANSLIM C & A...")
        # Debug: check raw quarterly financials
        fin_raw = tej.get_quarterly_financials(sym, count=12)
        if fin_raw:
            print(f"  Raw Financials Found: {len(fin_raw.get('quarters', []))} quarters")
            print(f"  Dates: {[q['date'] for q in fin_raw['quarters']]}")
        else:
            print("  ❌ No raw quarterly financials found.")

        canslim_data = tej.calculate_canslim_c_and_a(sym)
        if canslim_data and canslim_data.get('c_eps') is not None:
            print(f"  C Factor (Quarterly Growth): {canslim_data.get('C')} (EPS: {canslim_data.get('c_eps')})")
            print(f"  A Factor (Annual Growth): {canslim_data.get('A')} (TTM EPS: {canslim_data.get('a_eps_current')})")
        else:
            print("  ⚠️ No processed financial data available for C/A calculation.")

        # 3. Test Daily Prices and Grid
        print("Fetching Daily Prices & Calculating Grid...")
        from datetime import datetime, timedelta
        start_date = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
        df_prices = tej.get_daily_prices(sym, start_date=start_date)
        
        if df_prices is not None and not df_prices.empty:
            print(f"  Prices Found: {len(df_prices)} rows")
            grid = calculate_volatility_grid(df_prices['close'], is_etf=is_etf)
            if grid:
                print(f"  Volatility (Daily): {grid['volatility_daily']}%")
                print(f"  Grid Spacing: {grid['spacing_pct']}%")
                print(f"  Pivot: {grid['levels'][2]['price']}")
        else:
            print("  ❌ No price data found (Check permissions/table name).")

    print("\n" + "="*50)
    print("✅ Test Completed.")
    print("="*50)

if __name__ == "__main__":
    test_tej()
