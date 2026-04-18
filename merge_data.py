#!/usr/bin/env python3
"""
將 data_base.json 的內容整合到 data.json 中
解決 FinMind 每日限額問題，使用現有的完整數據
"""

import json
import os
from datetime import datetime

def merge_data_files():
    # 路徑設定
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_base_path = os.path.join(base_dir, "docs", "data_base.json")
    data_path = os.path.join(base_dir, "docs", "data.json")
    
    print(f"讀取 data_base.json...")
    with open(data_base_path, 'r', encoding='utf-8') as f:
        data_base = json.load(f)
    
    print(f"data_base.json 有 {len(data_base.get('stocks', {}))} 檔股票")
    
    # 創建新的 data.json 結構
    # 保留 data_base.json 的所有股票數據
    # 更新最後更新時間為現在
    merged_data = {
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "stocks": data_base.get("stocks", {}),
        "industry_strength": data_base.get("industry_strength", [])
    }
    
    print(f"合併後有 {len(merged_data['stocks'])} 檔股票")
    
    # 保存到 data.json
    with open(data_path, 'w', encoding='utf-8') as f:
        json.dump(merged_data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 已將 data_base.json 整合到 data.json")
    print(f"   最後更新: {merged_data['last_updated']}")
    print(f"   股票數量: {len(merged_data['stocks'])}")
    
    # 驗證一些關鍵股票是否存在
    key_stocks = ["2330", "2303", "2317", "0050", "0056"]
    print(f"\n驗證關鍵股票:")
    for stock in key_stocks:
        if stock in merged_data['stocks']:
            stock_info = merged_data['stocks'][stock]
            print(f"  {stock} {stock_info.get('name', 'N/A')}: CANSLIM 分數 {stock_info.get('canslim', {}).get('score', 'N/A')}")
        else:
            print(f"  {stock}: 未找到")

if __name__ == "__main__":
    merge_data_files()