#!/usr/bin/env python3
"""
創建一個中等大小的 data.json (500檔股票)
"""

import json
import os
from datetime import datetime

def create_medium_data():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_base_path = os.path.join(base_dir, "docs", "data_base.json")
    data_path = os.path.join(base_dir, "docs", "data.json")
    
    print("讀取 data_base.json...")
    with open(data_base_path, 'r', encoding='utf-8') as f:
        data_base = json.load(f)
    
    stocks = data_base.get('stocks', {})
    print(f"原始股票數量: {len(stocks)}")
    
    # 取前 500 檔股票
    # 確保包含重要的股票（台積電、鴻海等）
    important_stocks = ["2330", "2303", "2317", "0050", "0056", "00878", "2454", "2412", "2881", "2882"]
    
    # 先加入重要股票
    medium_stocks = {}
    for stock_id in important_stocks:
        if stock_id in stocks:
            medium_stocks[stock_id] = stocks[stock_id]
    
    # 再加入其他股票直到達到500檔
    for stock_id, stock_data in stocks.items():
        if stock_id not in medium_stocks and len(medium_stocks) < 500:
            medium_stocks[stock_id] = stock_data
    
    # 創建中等大小數據
    medium_data = {
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "stocks": medium_stocks,
        "industry_strength": data_base.get("industry_strength", [])
    }
    
    print(f"中等大小股票數量: {len(medium_data['stocks'])}")
    
    # 保存
    with open(data_path, 'w', encoding='utf-8') as f:
        json.dump(medium_data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 中等大小數據已保存到 {data_path}")
    print(f"   大小: {os.path.getsize(data_path) / 1024:.1f}KB")
    
    # 驗證重要股票是否存在
    print(f"\n驗證重要股票:")
    for stock_id in important_stocks:
        if stock_id in medium_data['stocks']:
            stock_info = medium_data['stocks'][stock_id]
            print(f"  {stock_id} {stock_info.get('name', 'N/A')}: CANSLIM 分數 {stock_info.get('canslim', {}).get('score', 'N/A')}")
        else:
            print(f"  {stock_id}: 未找到")
    
    return medium_data

if __name__ == "__main__":
    create_medium_data()