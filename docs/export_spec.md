可以，這一層其實很值得正式文件化。
我幫你整理成一份可以直接放進 repo 的 integration rule / data contract 規格，偏工程導向，讓兩個 repo 長期可維護。

⸻

:::writing{variant=“standard” id=“84217”}

📘 External Alpha Integration Rule

tw-canslim-web ↔ tw-trading-unified

⸻

1. 🎯 目的

建立一個穩定、可版本化的資料交換機制，使：
   •   tw-canslim-web 成為 Daily Alpha Provider
   •   tw-trading-unified 成為 Execution Consumer

並確保：
   •   不因 schema 變動導致系統崩潰
   •   不因網路或 GitHub 問題影響交易
   •   可追溯與可除錯

⸻

2. 🧱 架構設計

tw-canslim-web
  └─ GitHub Actions (daily batch)
       └─ data/leaders.json

tw-trading-unified
  └─ external_alpha_provider
       └─ fetch from GitHub Raw
       └─ store in local cache
       └─ used in decision layer


⸻

3. 📦 資料格式 (Data Contract)

3.1 leaders.json

{
  "schema_version": 1,
  "date": "2026-04-19",
  "generated_at": "2026-04-19T06:30:00+08:00",
  "universe": [
    {
      "symbol": "2330",
      "name": "台積電",
      "rs_rating": 92,
      "i_rating": 88,
      "breakout_score": 0.81,
      "volume_score": 0.73,
      "composite_score": 0.87,
      "industry_rank": 4,
      "tags": ["leader", "breakout_candidate"]
    }
  ]
}


⸻

3.2 欄位定義

欄位	型別	說明
schema_version	int	資料版本
date	str	YYYY-MM-DD
generated_at	str	ISO timestamp
symbol	str	股票代碼
rs_rating	int	相對強度
i_rating	int	機構認同
breakout_score	float	突破機率
composite_score	float	綜合評分
tags	list[str]	策略分類


⸻

4. 🔄 資料更新規則

Canslim (Producer)
   •   每日產出一次（建議盤後或開盤前）
   •   覆寫 data/leaders.json
   •   保持 schema 向下相容
   •   schema 變更時必須更新 schema_version

⸻

Trading (Consumer)

啟動流程
	1.	嘗試下載 GitHub Raw
	2.	成功 → 寫入本地 cache
	3.	失敗 → 使用舊 cache
	4.	不可因下載失敗中止交易

⸻

Cache 路徑

cache/external_alpha/latest.json
cache/external_alpha/leaders_YYYY-MM-DD.json


⸻

5. 🧠 使用規則 (Decision Layer)

5.1 Universe Filter

if symbol not in leaders:
    skip_trade()


⸻

5.2 Edge Modifier

edge += leader_bias[symbol]


⸻

5.3 Position Sizing

position_size *= (1 + composite_score * 0.2)


⸻

6. ⚠️ 安全與容錯

6.1 必須遵守
   •   不可直接依賴 GitHub 即時資料
   •   必須使用本地 cache
   •   JSON parsing failure → fallback
   •   缺欄位 → 使用 default value

⸻

6.2 禁止行為

# ❌ 不允許
requests.get(...).json() 直接進 decision


⸻

7. 🔐 Schema Evolution 規則

向下相容策略

if "breakout_score" not in row:
    row["breakout_score"] = 0.5


⸻

版本檢查

if schema_version > SUPPORTED_VERSION:
    log_warning("schema too new")
    degrade_mode()


⸻

8. ⏱️ 更新頻率

類型	頻率
Canslim Output	每日
Trading Fetch	啟動時 / 每日一次
Cache 使用	即時


⸻

9. 🧪 測試要求

必須通過：
   •   JSON schema validation
   •   Missing field tolerance
   •   Network failure fallback
   •   Duplicate symbol handling

⸻

10. 📌 設計原則

原則 1

External Alpha = Soft Signal

原則 2

不可覆蓋核心 decision logic

原則 3

不可影響系統穩定性

原則 4

可隨時 disable（feature flag）

⸻

11. 🚀 未來擴展

可新增：
   •   breakout_candidates.json
   •   industry_rank.json
   •   market_breadth.json

但需遵守：
   •   獨立 schema
   •   version 控制
   •   不影響現有 consumer

⸻

12. 🧭 一句話總結

Canslim 提供「每日優勢分布」，Trading 負責「即時執行」，兩者透過穩定的資料契約解耦。
:::

⸻

這份可以直接丟進：

tw-trading-unified/docs/external_alpha.md

或

tw-canslim-web/docs/export_spec.md

下一步把這份 spec 對應成：
   •   leaders.json 產生程式
   •   external_alpha_provider.py
   •   trading decision 接入點
