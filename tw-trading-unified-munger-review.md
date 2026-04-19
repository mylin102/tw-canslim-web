# tw-trading-unified — Munger Perspective Review

> 這份文件用芒格式框架審視 `tw-trading-unified`：先看怎麼死，再看值不值得做。

## 一句話結論

`tw-trading-unified` 對 **paper trading / research / replay** 很有價值，但對 **無人盯盤的真钱执行** 目前仍屬於 **Too Hard**。

它不是壞系統。它是個有經驗的人在真實交易傷口上，一邊修、一邊長出來的系統。這種系統通常比學院派更真，也更脆。

---

## 三筐分類法

### Yes

- paper trading
- 策略實驗
- replay 驗證
- 盤中監控與 dashboard
- 風險規則演練

### No

- 把 README 裡的功能密度，誤解成「已經能穩定 unattended 跑真钱」
- 因為功能很多，就以為 alpha 很強

### Too Hard

- 在沒有更強 CI、自動化 fail-safe、單一執行閘門之前，把它當作長期可擴張的真钱交易內核

---

## 我看到的優點

### 1. 它把交易問題當工程問題處理

這是對的。真正會讓交易系統死掉的，常常不是策略本身，而是：

- 重複下單
- position 狀態漂移
- 斷線重啟後重複開倉
- PnL 沒扣成本
- stop loss 用錯價格

repo 裡已經有明確針對這些問題的規則與測試，這很重要。

### 2. 它有事故驅動的測試文化

`RULES.md`、`docs/SDD.md`、`docs/V_MODEL_TEST_PLAN.md`、`tests/test_trading_bugs.py` 顯示這不是空談。

文件記錄的是已知死法，不是理想藍圖：

- 重複進場
- EXIT 不歸零
- BE 不夠 cover 手續費
- PnL 沒乘口數
- 夜盤跨日
- 重啟恢復失敗

這很好。真正成熟的交易工程，來自對屍體的記憶。

### 3. 有明確的 paper / dry-run 安全邊界

- `main.py --dry-run`
- config 中 `live_trading: false`
- margin check
- recovery guard
- position guard

方向是對的。

---

## 我看到的風險

### 1. 複雜度升太快

目前系統同時擁有：

- 8 個 futures 策略
- 多個 options mode
- ThetaGang
- QuantLib pricing
- dashboard 熱改 config
- 外部 supervisor
- shared session
- live / paper 雙軌

這就是典型的 **Lollapalooza**：很多看似合理的小風險疊在一起，最後變成非線性事故。

### 2. 規則很多，但機器強制不夠明顯

文件說：

- 每次部署前跑 `pytest`
- 跑 `py_compile`
- 跑 `main.py --dry-run`

但從 repo 結構看，這些紀律沒有明顯被 GitHub Actions 自動化強制。

Show me the incentive and I'll show you the outcome.

如果「必須做」沒有變成機器 gate，它就只是願望。

### 3. 執行與憑證管理仍偏個人駕駛艙

目前可見模式較接近：

- 本機 `.env`
- `load_dotenv`
- `autostart.sh`
- `tmux`
- `pkill`

這不是錯。這很實用。  
但這種形態的穩定性，往往仍然很依賴作者本人，而不是制度。

### 4. 系統最強的是防呆，不是 alpha 證明

它現在的工程價值，大於策略優勢的實證價值。

換句話說：

- 我看得到很多「避免做蠢事」的努力
- 但我還看不到足夠強的證據，證明它已經配得上 unattended real-money scaling

---

## 具體建議事項（按優先順序）

### 1. 先把 CI 變成鐵律

把下列流程做成 GitHub Actions：

- `python3 -m pytest tests/ -v`
- `python3 -m py_compile ...`
- `python3 main.py --dry-run`

原則：

- 沒過就不准 merge
- 讓規則變制度

### 2. Live 權限做成兩把鑰匙

不要只靠 config 的 `live_trading: true`。

建議至少需要同時滿足：

- config 開啟
- 額外環境變數或人工確認 flag

避免單一 YAML 手滑就送出真钱單。

### 3. 增加統一的下單前最後閘門

建立單一 `preflight_check()`，在真正送單前檢查：

- 市場是否開盤
- API 是否健康
- broker position / in-memory position 是否一致
- margin 是否足夠
- 價格是否合理
- 是否超過今日虧損上限
- 是否仍在 cooldown

任何一項不過，直接拒單。

### 4. 策略數量砍半

建議先只保留：

- 1 個趨勢策略
- 1 個盤整策略

其他全部放進 Too Hard 籃子。

策略多不等於 alpha 多。  
策略多通常只代表交互錯誤更多。

### 5. 再切乾淨 signal / risk / execution / persistence

明確分層：

- signal layer
- risk layer
- execution layer
- persistence layer

不要讓 monitor 一邊算信號，一邊寫 ledger，一邊改 position。

### 6. 做單一真相源稽核

每次：

- 啟動
- 下單後
- 出場後

自動比對三份狀態：

- in-memory position
- broker/API position
- ledger/log

只要不一致，立刻進 safe mode，不准開新倉。

### 7. 增加 kill switch

至少三種：

- 單日虧損超限
- 重複錯單 / 重複訊號
- API 健康檢查連續失敗

觸發後：

- 只允許平倉
- 禁止開新倉

好的交易系統，不只是會交易，而是知道何時停止。

### 8. 隔離回測參數與實盤參數

不要把回測最優參數直接推進 live config。

建立 promotion flow：

1. backtest pass
2. replay pass
3. paper pass
4. small-live pass

否則那不是策略開發。那叫過度擬合。

### 9. 清理 secrets 與部署方式

建議：

- production / paper 憑證分離
- dashboard 危險參數不可隨意改動
- live 參數改動需額外 gate

### 10. 維護一張錯誤表

不是報酬表。是 **事故表 / 愚蠢清單**。

每次事故記錄：

- 症狀
- 根因
- 損失
- 防呆規則
- 對應測試

這張表比大多數策略報告更值錢。

---

## 最後判斷

這個 repo **值得繼續做**。  
但下一步不應該是再加功能。

下一步應該是：

> 把它從「會交易的程式」變成「很難做蠢事的系統」。

前者看起來厲害。  
後者才配活著。
