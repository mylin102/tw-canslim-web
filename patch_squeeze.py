import os
import sys

# 切換到 squeeze-backtest 目錄
TARGET_DIR = "../squeeze-backtest/src/squeeze_backtest"
DATA_FILE = os.path.join(TARGET_DIR, "data.py")

with open(DATA_FILE, 'r') as f:
    content = f.read()

# 1. 注入 Import
if "from .alpha_integration_module import AlphaFilter" not in content:
    content = "from .alpha_integration_module import AlphaFilter\n" + content

# 2. 注入過濾邏輯
old_code = """        return pd.DataFrame()"""
new_code = """        return pd.DataFrame()

    def apply_alpha_filter(self, df: pd.DataFrame, ticker: str) -> pd.DataFrame:
        \"\"\"Applies CANSLIM Alpha filter to price data.\"\"\"
        if df.empty: return df
        try:
            # Clean ticker for lookup (e.g., 2330.TW -> 2330)
            stock_id = ticker.split('.')[0]
            
            # Use absolute path relative to this file
            base_dir = os.path.dirname(os.path.abspath(__file__))
            signal_path = os.path.join(base_dir, "master_canslim_signals.parquet")
            
            af = AlphaFilter(signal_path)
            # Add stock_id column if not exists for merge
            df['stock_id'] = stock_id
            df['date'] = df.index
            
            df_filtered = af.filter_backtest_data(df, min_score=75)
            # Drop temporary columns
            return df_filtered.set_index('date').drop(columns=['stock_id'])
        except Exception as e:
            print(f"[AlphaFilter] Error: {e}")
            df['is_canslim_approved'] = True
            df['is_inst_buying'] = False
            return df"""

if "apply_alpha_filter" not in content:
    content = content.replace(old_code, new_code)

# 3. 在 get_price_data 的回傳處調用
content = content.replace("return df_existing.loc[mask]", "return self.apply_alpha_filter(df_existing.loc[mask], ticker)")
content = content.replace("return df_new", "return self.apply_alpha_filter(df_new, ticker)")
content = content.replace("return df_combined.loc[mask]", "return self.apply_alpha_filter(df_combined.loc[mask], ticker)")

with open(DATA_FILE, 'w') as f:
    f.write(content)

print("✅ Successfully patched squeeze-backtest/data.py")
