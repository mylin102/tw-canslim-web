---
phase: 02-code-review
reviewed: 2024-03-21T10:00:00Z
depth: standard
files_reviewed: 2
files_reviewed_list:
  - tej_processor.py
  - export_canslim.py
findings:
  critical: 1
  warning: 2
  info: 2
  total: 5
status: issues_found
---

# Code Review Report: YoY Logic and TAIEX Symbols

**Reviewed:** 2024-03-21
**Depth:** standard
**Files Reviewed:** 2
**Status:** issues_found

## Summary

The review focused on verifying the fix for critical logic errors related to **YoY (Year-over-Year) calculations** and the **TAIEX symbol** used for market benchmarking. While the TAIEX symbol has been correctly updated to `^TWII`, the **YoY calculation logic in `tej_processor.py` still contains a critical logic error** regarding negative base values and remains fragile due to fixed indexing. Additionally, a poor heuristic for Relative Strength (RS) approximation was discovered in `export_canslim.py`.

## Critical Issues

### CR-01: Incorrect YoY Growth Calculation for Negative Base

**File:** `tej_processor.py:230-234`
**Issue:** The growth calculation `(current_q_eps - same_q_last_year_eps) / same_q_last_year_eps` is mathematically incorrect when the denominator (`same_q_last_year_eps`) is negative. Furthermore, the code explicitly skips calculation if the previous value is <= 0 (`if same_q_last_year_eps > 0:`), which fails to detect "turnaround" stocks (moving from loss to profit), a key indicator in CANSLIM.
**Fix:**
```python
# Use the robust logic from core/logic.py or update to:
if same_q_last_year_eps == 0:
    c_growth = 1.0 if current_q_eps > 0 else 0.0
else:
    # Use abs() for the denominator to handle negative base correctly
    c_growth = (current_q_eps - same_q_last_year_eps) / abs(same_q_last_year_eps)

result['c_growth'] = c_growth
# Consider a turnaround (negative to positive) as meeting the threshold
result['C'] = c_growth >= 0.25 or (same_q_last_year_eps <= 0 and current_q_eps > 0)
```

## Warnings

### WR-01: Fragile Fixed Indexing for YoY Comparison

**File:** `tej_processor.py:227`
**Issue:** The code assumes `eps_list[4]` is exactly the same quarter from the previous year. If the TEJ data has missing quarters (e.g., a company delayed reporting or data is missing), `eps_list[4]` will point to the wrong period, leading to a false YoY comparison.
**Fix:** Verify the date of `eps_list[4]` corresponds to the same month/quarter of the previous year as `eps_list[0]`.

### WR-02: Misleading RS Ratio Approximation

**File:** `export_canslim.py:408`
**Issue:** The code uses `stock_return_approx = stock_range_pos * 0.8 - 0.2` to approximate stock return for the `rs_ratio`. This is a heuristic mapping the 52-week range position to a -20% to +60% return, which is not a real return calculation and can lead to incorrect Relative Strength rankings.
**Fix:** Use the actual `stock_hist` (already fetched on line 386) to calculate the 6-month return.
```python
# Calculate actual return from history
if stock_hist is not None and len(stock_hist) > 120:
    actual_return = (stock_hist.iloc[-1] - stock_hist.iloc[-120]) / stock_hist.iloc[-120]
    rs_ratio = actual_return / market_return if abs(market_return) > 0.01 else 1.0
```

## Info

### IN-01: Inefficient TEJ Data Fetching

**File:** `tej_processor.py:155`
**Issue:** `get_quarterly_financials` fetches the *entire history* of all accounting codes for a company from TEJ every time it is called. When running a bulk scan of 2000 stocks, this will cause massive overhead and potential API throttling.
**Fix:** Add `acc_code` and `mdate` filters to the `tejapi.get` call to fetch only the necessary last 8-12 quarters for specific codes.

### IN-02: Duplicate Code and Unreachable Logic

**File:** `export_canslim.py:321-325`
**Issue:** `calculate_canslim_score` is defined twice in `CanslimEngine`. In the second definition, the code after the `return` statement is unreachable.
**Fix:** Remove the duplicate definition and clean up the unreachable code.

---

_Reviewed: 2024-03-21_
_Reviewer: gsd-code-reviewer_
_Depth: standard_
