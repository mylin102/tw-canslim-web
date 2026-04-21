# 📈 Alpha 信號整合與交易邏輯指南 (Trading Integration Guide)

本文件定義 `tw-trading-unified` 應如何消費由 `tw-canslim-web` 產出的 `data/leaders.json` 信號，並將其轉化為具體的進出場與部位管理動作。

---

## 1. 資料源與信號定義

### 1.1 來源
*   **路徑**: `data/leaders.json`
*   **格式**: JSON (Schema v1.1)
*   **更新頻率**: 每日台灣時間 18:30 前完成。

### 1.2 核心欄位說明
| 欄位 | 型別 | 意義 |
| :--- | :--- | :--- |
| `composite_score` | float | **綜合 Alpha 分數 (0.0-1.0)**。整合技術面 (CANSLIM 90%) 與 營收動能 (Revenue Alpha 10%)。 |
| `rs_rating` | int | 相對強度排名 (1-99)。愈高代表股價在市場中愈強勢。 |
| `tags` | list | **策略標籤**。用於觸發特定的子策略邏輯（詳見下表）。 |

### 1.3 標籤 (Tags) 字典
*   `leader`: 基礎標籤，代表該股進入 CANSLIM 核心監控名單。
*   `rev_acc`: **營收加速度**。當前 YoY 成長且增速優於前期，具備基本面轉折點特徵。
*   `rev_strong`: **強力營收**。YoY > 30% 且 MoM > 10%，代表業績進入爆發期。
*   `verified`: **人工核實**。該評分源自高品質 Excel 健診資料 (60420 版本)。
*   `breakout_candidate`: **突破預備**。技術面滿足 N 條件（股價創 52 週新高或帶量長紅）。

---

## 2. 交易決策邏輯 (Trading Logic)

### 2.1 進場過濾 (Entry Filter)
交易系統應實作 `UniverseFilter`，僅允許對出現在信號清單中的標的建立多頭部位。

*   **一般進場**: `symbol` 在 `universe` 中，且 `composite_score > 0.7`。
*   **Alpha 優先進場 (Aggressive)**: 
    *   若 `tags` 包含 `rev_acc` 或 `rev_strong`。
    *   即使技術指標（如 RSI/KD）未進入超賣區，只要股價回測 20MA 即可啟動佈局。
*   **人工加持 (High Confidence)**: 
    *   若 `tags` 包含 `verified`，視為勝率較高之標的。

### 2.2 動態部位縮放 (Position Sizing)
利用 `composite_score` 對每筆交易的 `Risk Per Trade` 進行動態調整。

| 分數區間 | 部位倍率 (Multiplier) | 動作 |
| :--- | :--- | :--- |
| `> 0.85` | **1.3x ~ 1.5x** | 強力加碼。特別是伴隨 `rev_acc` 時，應積極放大曝險。 |
| `0.65 - 0.85` | **1.0x** | 標準部位。 |
| `0.45 - 0.65` | **0.7x** | 減碼執行。基本面或技術面動能出現衰退。 |
| `< 0.45` | **0.0x (禁止進場)** | 僅觀察，不建立新倉。 |

### 2.3 出場與止盈規則 (Exit/Risk Management)
除了技術面停損（如 MA 跌破）外，應增加 **「基本面退潮」** 止損邏輯。

1.  **清單移除止損 (Membership Stop)**:
    *   若持股標的從 `leaders.json` 清單中**連續兩日消失**，代表該股已失去領頭羊地位。
    *   **應執行**: 於次日開盤減碼 50%，若一週內未重新回歸則出清。
2.  **分數轉弱止盈 (Decay Exit)**:
    *   若 `composite_score` 從高點（如 0.9）跌破 `0.6`。
    *   **應執行**: 啟動移動止盈 (Trailing Stop)，將停損點拉近至 5MA。
3.  **標籤失效 (Tag Loss)**:
    *   若 `rev_acc` 標籤消失，代表基本面增速放緩，不建議繼續持有多頭加碼部位。

---

## 3. 消費端實作範例 (Python/Pseudo)

```python
# tw-trading-unified/core/alpha_handler.py

def evaluate_alpha_multiplier(symbol, alpha_data):
    """
    計算基於 Alpha 信號的部位乘數
    """
    stock_signal = next((s for s in alpha_data['universe'] if s['symbol'] == symbol), None)
    
    if not stock_signal:
        return 0.0  # 核心清單外，不予進場
    
    score = stock_signal['composite_score']
    tags = stock_signal['tags']
    
    multiplier = 1.0
    
    # 根據分數調整
    if score > 0.85: multiplier = 1.3
    elif score < 0.5: multiplier = 0.7
    
    # 根據營收加速度額外加成
    if 'rev_acc' in tags:
        multiplier += 0.2
        
    # 人工驗證標籤提升信心
    if 'verified' in tags:
        multiplier += 0.1
        
    return min(multiplier, 1.5) # 上限 1.5x
```

---

## 4. 異常處理 (Fail-safe)
1.  **資料過期**: 若 `leaders.json` 中的 `date` 距離當前系統日期超過 3 個交易日，`tw-trading-unified` 應自動停止讀取 Alpha 乘數，回歸純技術面交易。
2.  **檔案缺失**: 抓取失敗時，應載入 `cache/latest_alpha.json` 並向管理員發出警告。
