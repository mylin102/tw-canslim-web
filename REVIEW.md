---
phase: code-review
reviewed: 2025-05-24T10:00:00Z
depth: standard
files_reviewed: 4
files_reviewed_list:
  - tej_processor.py
  - export_canslim.py
  - core/logic.py
  - finmind_processor.py
findings:
  critical: 3
  warning: 3
  info: 1
  total: 7
status: issues_found
---

# Phase: Code Review Report

**Reviewed:** 2025-05-24T10:00:00Z
**Depth:** standard
**Files Reviewed:** 4
**Status:** issues_found

## Summary

本次審查重點在於 `tej_processor.py` 的財務成長邏輯以及 `export_canslim.py` 中新加入的 Mansfield RS 實作。

審查發現 `tej_processor.py` 在計算 EPS 成長（CANSLIM C 和 A 分量）時存在嚴重的邏輯錯誤，會導致成長率計算不正確或失效。此外，`export_canslim.py` 對大盤指數符號的處理方式會導致無法正確抓取 TAIEX 數據，進而使 Mansfield RS 失去效用（始終為 0）。

營收成長計算邏輯（`get_revenue_quarterly_growth`）本身實作正確，但目前在主流程中尚未被使用，僅作為預留的 proxy 邏輯。

---

## Critical Issues

### CR-01: `tej_processor.py` EPS 成長計算邏輯錯誤 (YoY Comparison)

**File:** `tej_processor.py:255-257`
**Issue:** 
1. `get_quarterly_financials` 被限制僅抓取 4 季數據（`[:4]`），這使得 YoY（Year-over-Year）比較不可能實現，因為 YoY 需要當季與去年同季（至少需要 5 季數據）。
2. `calculate_canslim_c_and_a` 中的 C 計算將 `eps_list[0]` 與 `eps_list[3]` 比較。在正常季度序列中，索引 3 是前一年的 Q4（若當前是 Q3），而非去年同季（應該是索引 4）。
3. A 的計算需要 8 季數據來計算 TTM YoY，由於數據源被限制為 4 季，A 的計算將始終失效。

**Fix:**
```python
# In get_quarterly_financials
unique_dates = sorted(data['mdate'].unique(), reverse=True)[:8] # 至少 8 季

# In calculate_canslim_c_and_a
if len(eps_list) >= 5:
    current_q_eps = eps_list[0]
    same_q_last_year_eps = eps_list[4] # 去年同季
    # ... logic ...
```

### CR-02: `export_canslim.py` 大盤符號處理錯誤導致 Mansfield RS 失效

**File:** `export_canslim.py:507`
**Issue:** `TAIEX_SYMBOL.replace("^", "")` 會將 `^TWII` 改為 `TWII`。在 `get_price_history` 中，這會被補上 `.TW` 變成 `TWII.TW`。Yahoo Finance 並不支援 `TWII.TW` 作為大盤指數，正確符號應維持 `^TWII`。這會導致大盤數據抓取失敗，所有股票的 `m_rs` 都會變成預設值 0.0。

**Fix:**
```python
# 移除 .replace("^", "")
market_hist = self.get_price_history(TAIEX_SYMBOL, period="2y")
```

### CR-03: `tej_processor.py` 財務數據抓取數量不足

**File:** `tej_processor.py:214`
**Issue:** 同 CR-01，`get_quarterly_financials` 內部寫死了 `[:4]`。這不僅影響 `calculate_canslim_c_and_a`，也限制了所有依賴此方法進行多季趨勢分析的功能。

**Fix:** 將 `[:4]` 改為可配置的參數或預設增加到 8 以上。

---

## Warnings

### WR-01: Resume 邏輯未檢查數據完整性

**File:** `export_canslim.py:520`
**Issue:** 目前的 Resume 邏輯只要股票代號存在於 `data.json` 中就會跳過。由於 Mansfield RS 和機構增持強度是新加入的欄位，舊有的 `data.json` 中不包含這些數據。這會導致在不手動刪除舊數據的情況下，新算法無法應用於已掃描過的股票。

**Fix:** 增加欄位檢查，或在版本更動（如增加 Mansfield RS）時強迫重刷：
```python
if t in self.output_data["stocks"] and "mansfield_rs" in self.output_data["stocks"][t].get("canslim", {}):
    continue
```

### WR-02: `yf.history` 循環抓取效能低下

**File:** `export_canslim.py:545`
**Issue:** 在循環中對每一支股票調用 `yf.Ticker.history` 速度極慢，且容易觸發 Yahoo Finance 的 Rate Limit（速率限制）。

**Fix:** 建議改用 `yf.download(list_of_tickers, ...)` 進行批次抓取，或僅針對進入初步篩選的股票抓取 2 年歷史。

### WR-03: `tej_processor.py` 營收成長計算邊界檢查不夠嚴謹

**File:** `tej_processor.py:279`
**Issue:** `get_revenue_growth_rate` 在數據長度不足 12 個月時，會 fallback 到 `iloc[0]` 進行比較，這會導致計算出的「年增率」實際上並非 YoY，而是與數據起點的比較。

**Fix:** 嚴格檢查 `len(revenues) >= 12`。

---

## Info

### IN-01: `get_revenue_quarterly_growth` 尚未整合

**File:** `tej_processor.py:294`
**Issue:** 新增的營收季增率計算邏輯實作正確（sum of 3 months vs sum of previous 15-12 months），但在 `export_canslim.py` 中尚未被作為 `C` 因子的 fallback 或輔助指標使用。
**Fix:** 建議在 `calculate_canslim_c_and_a` 中，當 EPS 尚未公佈時，調用此營收成長邏輯作為參考。

---

_Reviewed: 2025-05-24_
_Reviewer: gsd-code-reviewer_
_Depth: standard_
