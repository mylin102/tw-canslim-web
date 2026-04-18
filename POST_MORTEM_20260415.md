# 技術檢討報告 (Post-Mortem) - 2026-04-15

## 📝 事故概述
今日在進行 TEJ 財報整合與 ETF 網格功能擴充時，發生了多次系統性錯誤，包含邏輯功能回歸、前端白屏當機以及資料產出不一致。雖然最終均已修復，但過程暴露了執行流程中的重大漏洞。

---

## 🔍 錯誤分析與根本原因

### 1. 邏輯功能回歸 (Logic Regression)
*   **現象**：在推送資料時發生 `ImportError`，顯示 `calculate_accumulation_strength` 遺失。
*   **根本原因**：
    *   **代碼覆蓋失誤**：在處理 Git 衝突並使用 `write_file` 修復 `core/logic.py` 時，提供的代碼塊不完整，意外刪除了舊有的關鍵函數。
    *   **驗證缺失**：在 Push 前未執行 `verify_local.py` 或單元測試，違反了 GSD 的「先驗證再發佈」原則。

### 2. 前端白屏當機 (Frontend White Screen)
*   **現象**：搜尋 0050 或部分 ETF 時，網頁變成一片空白。
*   **根本原因**：
    *   **型別不安全**：在渲染表格時，對 `undefined` 或 `null` 的欄位（如 ETF 缺失的淨買超張數）直接呼叫了 `.toLocaleString()` 或 `.toFixed()`。
    *   **資料結構假設錯誤**：預設所有標的都具備相同的財務與籌碼欄位，未考慮到 ETF 與個股的資料異質性。

### 3. 資料與分值不一致 (Data Inconsistency)
*   **現象**：族群清單顯示 ETF 50 分，但詳情顯示 100 分；台積電出現 0 分。
*   **根本原因**：
    *   **邏輯中心化失敗**：`fast_data_gen.py` 擁有一套硬編碼的計分邏輯，未與 `core/logic.py` 同步。
    *   **GitHub Actions 覆蓋**：自動化腳本使用了舊邏輯產生資料，覆蓋了本地修正後的正確資料。
    *   **代號後綴遺失**：yfinance 下載時缺少 `.TW` 後綴，導致備援抓取失敗，RS 數值歸零。

### 4. 序列化與資料損毀 (Serialization Failure)
*   **現象**：`data.json` 檔案變成 86 位元組（空的），或產出 0 檔標的。
*   **根本原因**：
    *   **非序列化物件**：TEJ/Pandas 回傳的 `Timestamp` 與 `numpy.bool_` 無法直接轉為 JSON，導致寫入中斷。
    *   **維度不匹配**：yfinance 批次下載回傳的 MultiIndex DataFrame 未經 `.squeeze()` 處理，導致 RS 計算函數崩潰。

---

## 🛠️ 行動方針與預防措施 (The New GSD Rules)

### 1. 強制性 V-Cycle 檢查
以後任何涉及 `core/logic.py` 或 `data.json` 的變更，**Push 前必須強制執行以下指令組合**：
```bash
PYTHONPATH=. pytest tests/test_logic_v2.py && python3 verify_local.py
```
*不通過，絕對不准 Push。*

### 2. 邏輯去中心化 (DRY 原則)
*   所有執行腳本（`export_canslim.py`, `fast_data_gen.py`, `verify_local.py`）**嚴禁內建計算邏輯**。
*   必須統一調用 `core/logic.py` 中的函數。

### 3. 前端防禦性編碼規範
*   所有數值渲染必須使用 `(val || 0).toLocaleString()` 或加上 `typeof === 'number'` 檢查。
*   存取深層物件屬性必須使用 `v-if="obj && obj.sub"` 或是 Optional Chaining。

### 4. 資料救援與備份機制
*   在執行全市場掃描前，必須先執行 `cp docs/data.json docs/data_backup.json`。
*   發生衝突時，優先以 `verify_local.py` 產出的高品質資料為準，再進行大融合 (`fuse_data_json.py`)。

---
**核准人：Gemini CLI - GSD Engine**
**日期：2026-04-15**
