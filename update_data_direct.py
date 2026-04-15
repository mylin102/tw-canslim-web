#!/usr/bin/env python3
"""
直接更新 docs/data.json 為完整的數據
繞過 git 衝突問題
"""

import json
import os
from datetime import datetime

def update_data_json():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_base_path = os.path.join(base_dir, "docs", "data_base.json")
    data_path = os.path.join(base_dir, "docs", "data.json")
    
    print("讀取完整的 data_base.json...")
    with open(data_base_path, 'r', encoding='utf-8') as f:
        data_base = json.load(f)
    
    print(f"data_base.json 有 {len(data_base.get('stocks', {}))} 檔股票")
    
    # 創建更新後的數據
    updated_data = {
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "stocks": data_base.get("stocks", {}),
        "industry_strength": data_base.get("industry_strength", [])
    }
    
    print(f"更新後的 data.json 將有 {len(updated_data['stocks'])} 檔股票")
    
    # 保存
    with open(data_path, 'w', encoding='utf-8') as f:
        json.dump(updated_data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ data.json 已更新")
    print(f"   最後更新: {updated_data['last_updated']}")
    print(f"   股票數量: {len(updated_data['stocks'])}")
    
    return updated_data

if __name__ == "__main__":
    update_data_json()