# 🇹🇼 台股 CANSLIM 戰情室 (tw-canslim-web)

這是一個基於 **gstack** 方法論開發的輕量化台股分析工具，專門用於追蹤符合 CANSLIM 原則的潛力股，並特別強化了「三大法人籌碼明細」的視覺化展示。

## 🚀 核心功能
*   **CANSLIM 自動評分**：自動分析 (C)季成長、(A)年成長、(N)新高、(S)供需、(L)強勢股、(I)法人認同度。
*   **Excel 數據整合**：支援讀取「股票健診」與「股票基本面數據」Excel 檔案，整合 Composite Rating、EPS Rating、RS Rating、SMR Rating 等專業指標。
*   **法人籌碼圖表**：使用 Chart.js 展示外資、投信、自營商最近 20 個交易日的買賣超趨勢。
*   **反應式搜尋**：使用 Vue 3 實作，輸入台股代號（如 2330）即時顯示分析結果，支援搜尋建議。
*   **零成本部署**：採用靜態生成 (SSG) 架構，部署於 GitHub Pages。

## 🛠 技術架構
*   **後端 (Data)**: Python (yfinance, requests, pandas)
*   **前端 (UI)**: Vue 3 (Composition API), Tailwind CSS, Chart.js
*   **自動化 (CI/CD)**: GitHub Actions (每日 16:30 自動更新資料)

## 📂 檔案結構
```text
tw-canslim-web/
├── docs/               # 網頁部署目錄 (GitHub Pages 來源)
│   ├── index.html      # 前端主頁面
│   ├── app.js          # Vue 邏輯與圖表渲染
│   └── data.json       # 每日產出的靜態資料庫
├── export_canslim.py   # 資料收集與 CANSLIM 分析引擎
└── .github/workflows/  # GitHub Actions 自動化排程
```

## 💻 本地運行 (Local Development)

### 1. 安裝依賴
```bash
pip install -r requirements.txt
```

### 2. 準備 Excel 數據 (選用)
將以下 Excel 檔案放置於專案根目錄，系統會自動讀取：
*   `股票健診60313.xlsm` - 包含 CANSLIM 評分 (Composite, EPS, RS, SMR Rating)
*   `股票基本面數據60313.xlsm` - 包含歷史 EPS 與營收數據

> **注意**: Excel 檔案已加入 `.gitignore`，不會被提交至 Git，僅供本地使用。

### 3. 生成資料
```bash
python3 export_canslim.py
```

### 4. 啟動網頁
```bash
cd docs
python3 -m http.server 8000
```
瀏覽 `http://localhost:8000` 即可查看。

## 🤖 自動化更新
專案包含 GitHub Actions 工作流，每個交易日盤後會自動執行：
1. 抓取證交所最新法人資料。
2. 計算最新 CANSLIM 指標。
3. 更新 `docs/data.json` 並推送到分支，自動觸發網頁更新。

---
*免責聲明：本工具僅供研究參考，不構成任何投資建議。投資有風險，入市需謹慎。*
