
import json
import os

LOCAL_PATH = "docs/data_local.json"
REMOTE_PATH = "docs/data_remote.json"
OUTPUT_PATH = "docs/data.json"

def fuse_data():
    if not os.path.exists(LOCAL_PATH) or not os.path.exists(REMOTE_PATH):
        print("❌ 找不到本地或遠端備份檔案。")
        return

    with open(LOCAL_PATH, 'r', encoding='utf-8') as f:
        local_data = json.load(f)
    
    with open(REMOTE_PATH, 'r', encoding='utf-8') as f:
        remote_data = json.load(f)

    # 以 Local 的 metadata 為基準 (最後更新時間)
    merged_data = local_data.copy()
    
    local_stocks = local_data.get("stocks", {})
    remote_stocks = remote_data.get("stocks", {})
    
    # 合併個股資料
    # 策略：Remote 有但 Local 沒有的，補進去。
    new_count = 0
    for sym, data in remote_stocks.items():
        if sym not in local_stocks:
            local_stocks[sym] = data
            new_count += 1
    
    merged_data["stocks"] = local_stocks
    
    # 重新計算產業強度（因為標的變多了）
    # (可選，這裡我們先保留 Local 計算好的 26 個產業，或直接存檔)
    
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(merged_data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 合併完成！")
    print(f"   - Local 原始數量: {len(local_data.get('stocks', {}))}")
    print(f"   - 從 Server 補回數量: {new_count}")
    print(f"   - 最終總數量: {len(local_stocks)}")

if __name__ == "__main__":
    fuse_data()
