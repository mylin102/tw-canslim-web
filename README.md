# 🇹🇼 台股 CANSLIM 戰情室 (tw-canslim-web)

基於 **gstack** 方法論開發的輕量化台股分析工具，自動追蹤符合 CANSLIM 原則的潛力股。

## 🚀 上線網站

**https://mylin102.github.io/tw-canslim-web/**

## ✨ 核心功能

### 1. CANSLIM 自動評分
- **C** - 當季 EPS 成長率 (>= 25%)
- **A** - 年度 EPS 年增率 (3 年 CAGR >= 25%)
- **N** - 股價接近 52 週新高
- **S** - SMR Rating 評估 (A/A+)
- **L** - 相對強度指標
- **I** - 三大法人連續買超
- **M** - 大盤趨勢判斷

### 2. 三大功能頁
| 頁面 | 功能 |
|------|------|
| 🔍 **個股查詢** | 輸入代號查看完整 CANSLIM 分析 |
| 🏆 **高分排名** | 自動列出評分最高的 20 檔股票 |
| 🎛 **條件選股** | 篩選符合條件的潛力股 |

### 3. 資料來源
- **FinMind API** - 每日自動抓取三大法人買賣超
- **Excel 評分** - Composite/EPS/RS/SMR Rating
- **yfinance** - 股價與財務數據
- **投信投顧公會** - 基金持股變動

## 🛠 技術架構

```
後端 (Data)     → Python (FinMind, yfinance, pandas)
前端 (UI)       → Vue 3, Tailwind CSS, Chart.js
自動化 (CI/CD)  → GitHub Actions (每日 16:30 更新)
部署            → GitHub Pages (零成本)
```

## 💻 本地運行

```bash
# 1. 安裝依賴
pip install -r requirements.txt

# 2. 生成資料
python3 export_canslim.py
python3 compress_data.py

# 3. 啟動網頁
cd docs && python3 -m http.server 8000

# 4. 瀏覽
http://localhost:8000
```

## 📊 回測分析

```bash
python3 backtest.py
```

產生 CANSLIM 策略回測報告，包含：
- 分數分布統計
- 各指標通過率
- 法人持續買超股票

## 📁 檔案結構

```
tw-canslim-web/
├── docs/                    # GitHub Pages 部署目錄
│   ├── index.html           # 前端主頁面
│   ├── app.js               # Vue 應用程式
│   ├── screener.js          # 條件選股模組
│   └── data.json.gz         # 壓縮後的資料檔 (92% 壓縮率)
├── export_canslim.py        # CANSLIM 分析引擎
├── finmind_processor.py     # FinMind API 處理器
├── excel_processor.py       # Excel 資料處理器
├── backtest.py              # 策略回測模組
├── compress_data.py         # JSON 壓縮工具
└── .github/workflows/       # GitHub Actions 自動化
```

## 🤖 自動化更新

GitHub Actions 於每個交易日 16:30 (UTC+8) 自動執行：
1. 抓取 FinMind 最新法人買賣超
2. 計算最新 CANSLIM 指標
3. 壓縮資料檔 (92% 壓縮率)
4. 自動推送到 GitHub Pages

## 📈 效能數據

| 項目 | 數值 |
|------|------|
| 覆蓋股票數 | 1,500+ 檔 |
| 資料更新頻率 | 每日 |
| 前端載入時間 | < 2 秒 (壓縮後) |
| 壓縮率 | 92% (1MB → 49KB) |
| 單元測試 | 22/22 通過 |

---

*免責聲明：本工具僅供研究參考，不構成任何投資建議。投資有風險，入市需謹慎。*
