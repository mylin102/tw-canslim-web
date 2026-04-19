# 🇹🇼 台股 CANSLIM 戰情室 (tw-canslim-web)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![GitHub Stars](https://img.shields.io/github/stars/mylin102/tw-canslim-web.svg)](https://github.com/mylin102/tw-canslim-web/stargazers)
[![GitHub Forks](https://img.shields.io/github/forks/mylin102/tw-canslim-web.svg)](https://github.com/mylin102/tw-canslim-web/network)

基於 **CANSLIM** 選股系統開發的輕量化台股分析戰情室。本工具自動掃描全台股 1,500+ 檔標的，透過量化模型篩選出同時具備強勁基本面與技術面動能的潛力股。

## 🚀 立即體驗

**[點此進入戰情室 Demo 連結](https://mylin102.github.io/tw-canslim-web/)**

---

## 📸 介面預覽

![戰情室介面截圖](https://via.placeholder.com/800x450?text=CANSLIM+Dashboard+Preview)
*(註：建議上傳實際操作截圖以增加吸引力)*

---

## 📖 CANSLIM 在台股的量化定義

本專案將 William J. O'Neil 的經典選股系統轉化為具體的程式碼邏輯，針對台灣市場特性進行優化：

### **C** - Current Quarterly Earnings (當季獲利)
*   **量化指標：** 最近一季 EPS 成長率 ≥ 25% (YoY)。
*   **台股特色：** 考慮到台灣產業週期性，系統會自動偵測「轉虧為盈」的轉折股（Turnaround candidates）。

### **A** - Annual Earnings Increase (年度獲利)
*   **量化指標：** 最近一年度 EPS 成長率 ≥ 25% (YoY)。
*   **進階篩選：** 結合股東權益報酬率 (ROE) ≥ 17% 作為選股加分項。

### **N** - New Products, Management, Highs (新契機/新高)
*   **量化指標：** 股價處於 52 週新高的 90% 區間內，或近期突破 60 日壓力線。
*   **核心理念：** 買入正在創新高的股票，而非尋找跌深的低點。

### **S** - Supply and Demand (供給與需求)
*   **量化指標：** 當日成交量 ≥ 5 日平均成交量的 150%。
*   **台股特色：** 追蹤量價配合，篩選出有大戶進場跡象的股票。

### **L** - Leader or Laggard (強勢股或落後股)
*   **量化指標：** 曼斯菲爾德相對強度 (Mansfield RS) > 0。
*   **計算方式：** 比較個股與大盤 (TAIEX) 的半年相對報酬率，確保資金效率最大化。

### **I** - Institutional Sponsorship (法人追蹤)
*   **量化指標：** 近 3 日三大法人（外資、投信、自營商）累計買超。
*   **核心理念：** 跟隨法人的腳步，尋找有「聰明錢」背書的標的。

### **M** - Market Direction (市場趨勢)
*   **量化指標：** 大盤 (TAIEX) 多空排列。
*   **策略建議：** 只有在大盤處於多頭或反彈格局時，才積極執行選股策略。

---

## ✨ 核心技術特色

- **純前端渲染：** 所有的篩選與排序邏輯均在瀏覽器端完成，載入極快。
- **高倍率資料壓縮：** 透過 Gzip 壓縮將 1.5MB 的 JSON 資料瘦身至 40KB，節省流量且載入無感。
- **自動化更新流水線：** 每日透過 Python 腳本抓取最新報價、財報與法人籌碼，並自動推送到 GitHub Pages。
- **ETF 相容：** 系統可自動識別並標記 ETF，方便區分個股與市場指數。

---

## 🛠️ 開發與貢獻

### 環境需求
- Python 3.10+
- Node.js (僅用於前端預覽)

### 安裝步驟
1.  **克隆倉庫：**
    ```bash
    git clone https://github.com/mylin102/tw-canslim-web.git
    cd tw-canslim-web
    ```
2.  **安裝 Python 依賴：**
    ```bash
    pip install -r requirements.txt
    ```
3.  **執行資料更新 (需設定相關 API Key)：**
    ```bash
    python export_canslim.py
    ```

---

## ⚖️ 免責聲明與授權

### 授權協定
本專案採用 **[MIT License](LICENSE)** 授權。

### 投資風險提示
本工具僅供學術研究與量化分析參考，**不構成任何投資建議**。選股模型歷史表現不代表未來收益，投資人應獨立評估風險並審慎操作。

---

## 🙌 支援作者

如果你覺得這個工具有幫助，歡迎點個 **Star** 🌟 或 **Fork** 🍴！
如果有任何改進建議，歡迎提交 Issue 或 Pull Request。
