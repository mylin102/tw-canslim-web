# Coding Conventions

**Analysis Date:** 2025-04-16

## Naming Patterns

**Files:**
- Snake case: `export_canslim.py`, `finmind_processor.py`, `tej_processor.py`
- Module files use verb_noun pattern: `excel_processor.py`, `institutional_analyzer.py`
- Test files use pattern: `test_*.py` (e.g., `test_canslim.py`, `test_finmind.py`)
- Verification/batch scripts use verb_noun: `verify_local.py`, `batch_strategy_analysis.py`
- Underscore separates logical sections: `quick_auto_update.py`, `export_dashboard_data.py`

**Classes:**
- PascalCase with descriptive names
- Examples: `CanslimEngine`, `FinMindProcessor`, `ExcelDataProcessor`, `TEJProcessor`, `Order`, `OrderStatus`
- Class names reflect their primary responsibility (processor, engine, manager)

**Functions:**
- Snake case universally
- Action verbs for functions: `calculate_c_factor()`, `fetch_institutional_data()`, `check_n_factor()`
- Boolean functions use `check_` or `calculate_` prefix: `check_i_institutional()`, `calculate_a_factor()`
- Helper methods use verb_noun: `_safe_int()`, `_load_etf_cache()`, `_fetch_with_retry()`
- Private methods prefixed with underscore: `_find_excel_files()`, `_load_excel_data()`

**Variables:**
- Snake case throughout: `total_shares`, `current_eps`, `market_hist`, `target_tickers`
- Constants in UPPER_CASE: `C_QUARTERLY_GROWTH_THRESHOLD = 0.25`, `TAIEX_SYMBOL = "^TWII"`
- Loop variables descriptive: `for t in target_tickers:` not `for t in tickers:` or `for i, row in df.iterrows():`
- Boolean flags descriptive: `is_etf`, `available`, `initialized` rather than simple `is_a`

**Types:**
- Type hints used extensively: `pd.Series`, `pd.DataFrame`, `Dict[str, Dict]`, `Optional[pd.DataFrame]`
- Examples from codebase:
  - `def calculate_c_factor(eps_series: pd.Series, threshold: float = 0.25) -> bool:`
  - `def fetch_institutional_investors(self, stock_id: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:`

## Code Style

**Formatting:**
- No enforced formatter (no Black, Ruff, or autopep8 config found)
- Follows PEP 8 conventions (4-space indentation)
- Line breaks used strategically to group related operations
- Example from `core/logic.py` lines 22-30: Empty line after imports, logic grouped by operation

**Linting:**
- No linting configuration file found
- Code follows Python conventions implicitly
- Error handling uses try/except blocks (see Exception Handling section)

**Import Organization:**
- Standard library imports first (os, sys, json, logging, etc.)
- Third-party imports second (pandas, yfinance, requests, openpyxl)
- Local imports last (from export_canslim import, from core.logic import)
- Example from `export_canslim.py` lines 1-14:
  ```python
  import os
  import json
  import time
  import logging
  import requests
  import pandas as pd
  import yfinance as yf
  from datetime import datetime, timedelta
  from typing import Dict, List, Optional, Tuple
  from excel_processor import ExcelDataProcessor
  from finmind_processor import FinMindProcessor
  ```

## Error Handling

**Patterns:**
- Try/except blocks used extensively for API calls and file I/O
- Generic `except Exception as e:` for broad error catching
- Specific exceptions like `requests.RequestException` when possible
- Graceful degradation: Return `None` or empty dict/list on failure
- Examples from `export_canslim.py`:
  ```python
  try:
      df_l = pd.read_csv(TWSE_TICKER_URL, encoding='utf-8')
      for _, row in df_l.iterrows():
          # process data
  except Exception as e:
      logger.error(f"Failed to fetch TWSE tickers: {e}")
  ```

**Retry Logic:**
- Custom retry mechanism with exponential backoff (see `_fetch_with_retry()` in `export_canslim.py`)
- Max retries parameter (default 3)
- Sleep between retries using `time.sleep()`
- Example from lines 196-211:
  ```python
  def _fetch_with_retry(self, url: str, params: Dict = None, max_retries: int = 3) -> Optional[requests.Response]:
      """Fetch URL with retry logic and exponential backoff."""
      for attempt in range(max_retries):
          try:
              response = requests.get(url, params=params, timeout=10)
              response.raise_for_status()
              return response
          except requests.RequestException as e:
              if attempt < max_retries - 1:
                  wait_time = 2 ** attempt
                  time.sleep(wait_time)
  ```

## Logging

**Framework:** `logging` module (standard library)

**Patterns:**
- Logger initialized per module: `logger = logging.getLogger(__name__)`
- Centralized config in main modules using `logging.basicConfig()`
- Levels used: `DEBUG`, `INFO`, `WARNING`, `ERROR`
- 577 logger calls across codebase indicate heavy logging usage

**Log Messages:**
- Informational: `logger.info(f"Fetching institutional data for {stock_id} ({start_date} to {end_date})")`
- Warnings: `logger.warning("FinMind package is not installed; FinMind-backed data fetches are disabled")`
- Errors: `logger.error(f"Failed to fetch TWSE tickers: {e}")`
- Format includes timestamps and levels: `'%(asctime)s - %(levelname)s - %(message)s'`

## Comments

**When to Comment:**
- Algorithm explanations: "Turnaround: Negative/Zero to Positive" (in `calculate_c_factor()`)
- Non-obvious business logic: "Taiwan stock chips are in 'shares' (1 lot = 1000 shares)"
- Data structure assumptions: "Note: To avoid seasonality, compare with the same quarter of last year"
- Workarounds for anomalies: "Self-Correction: If MRIS is extremely negative but price is at short-term high, it's likely a data split anomaly"

**Docstrings:**
- Triple-quoted strings for all functions and classes
- Example from `finmind_processor.py` lines 51-67:
  ```python
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
  ```

## Function Design

**Size:** Most functions are 10-30 lines, keeping logic focused
- Pure functions preferred (e.g., `calculate_c_factor()` at 20 lines)
- Methods can be longer (up to 50+ lines) but remain focused on single responsibility

**Parameters:** 
- Explicit parameters preferred (no *args/**kwargs abuse)
- Default parameters used for thresholds: `threshold: float = 0.25`
- Optional parameters typed with `Optional[]`: `roe: Optional[float] = None`
- Longer parameter lists formatted with one per line

**Return Values:**
- Boolean for validation functions: `calculate_c_factor()` returns `bool`
- Numeric for calculations: `calculate_accumulation_strength()` returns `float`
- DataFrame/Dict for data processing: `fetch_institutional_investors()` returns `Optional[pd.DataFrame]`
- `None` used for missing/failed operations rather than raising exceptions in API processors

## Module Design

**Exports:**
- Classes and functions exported as needed, no explicit `__all__` used
- Functions are module-level (not forced into classes unnecessarily)
- Processor classes (FinMindProcessor, TEJProcessor, ExcelDataProcessor) are stateful and instantiated
- Pure functions in `core/logic.py` are stateless

**Barrel Files:**
- No barrel files (`__init__.py`) with re-exports observed
- Core module has minimal init files
- `core/order_management/__init__.py` exists but checked to be sparse

**Directory Structure for Logic:**
- Core algorithmic functions in `core/logic.py` (stateless, pure)
- Data processors as separate modules: `finmind_processor.py`, `tej_processor.py`, `excel_processor.py`
- Main orchestration in `export_canslim.py` (CanslimEngine class)
- Order management in `core/order_management/` (Order, OrderStatus enums)

## Data Handling Conventions

**DataFrame Operations:**
- Consistent column naming with underscores: `foreign_net`, `trust_net`, `dealer_net`
- Date columns as strings initially, converted to `pd.to_datetime()` when needed
- Indices used meaningfully: `set_index(['stock_id', 'date'])` for resampling
- Missing data handled explicitly with `dropna()`, `fillna()`, or forward fill `.ffill()`

**Optional Data:**
- APIs may return `None` or empty DataFrames
- Callers check for validity: `if df is None or len(df) == 0:`
- Fallback mechanisms built in (e.g., Excel backup for TEJ data in `verify_local.py`)

**Constants:**
- Configuration constants at module level
- Thresholds grouped: C_QUARTERLY_GROWTH_THRESHOLD, A_ANNUAL_CAGR_THRESHOLD, etc.
- Example from `export_canslim.py` lines 39-45:
  ```python
  C_QUARTERLY_GROWTH_THRESHOLD = 0.25  # 25% growth
  A_ANNUAL_CAGR_THRESHOLD = 0.25       # 25% CAGR
  N_NEW_HIGH_THRESHOLD = 0.90          # Within 90% of 52-week high
  S_VOLUME_THRESHOLD = 1.5             # 150% of average volume
  ```

---

*Convention analysis: 2025-04-16*
