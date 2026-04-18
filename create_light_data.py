#!/usr/bin/env python3
"""
創建一個精簡版的 data.json 用於測試
只保留前 100 檔股票
"""

import json
import os
from datetime import datetime

def create_lightweight_data():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_base_path = os.path.join(base_dir, "docs", "data_base.json")
    data_path = os.path.join(base_dir, "docs", "data_light.json")
    
    print("讀取 data_base.json...")
    with open(data_base_path, 'r', encoding='utf-8') as f:
        data_base = json.load(f)
    
    stocks = data_base.get('stocks', {})
    print(f"原始股票數量: {len(stocks)}")
    
    # 只取前 100 檔股票
    limited_stocks = dict(list(stocks.items())[:100])
    
    # 創建精簡版數據
    light_data = {
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "stocks": limited_stocks,
        "industry_strength": data_base.get("industry_strength", [])[:10]  # 只取前10個產業
    }
    
    print(f"精簡版股票數量: {len(light_data['stocks'])}")
    
    # 保存
    with open(data_path, 'w', encoding='utf-8') as f:
        json.dump(light_data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 精簡版數據已保存到 {data_path}")
    print(f"   大小: {os.path.getsize(data_path) / 1024:.1f}KB")
    
    return light_data

if __name__ == "__main__":
    create_lightweight_data()