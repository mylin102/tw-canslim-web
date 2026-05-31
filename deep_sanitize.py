import json
import os

def deep_sanitize(file_path):
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return
    
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    stocks = data.get('stocks', {})
    cleaned_stocks_count = 0
    total_removed_records = 0
    
    # 定義假資料指紋 (組合比單一數值更準確)
    fake_fingerprints = [
        {"f": 1000, "t": 500, "d": 200},
        {"f": 800, "t": 400, "s": 150},  # 註：有些欄位可能是 d 或 s，這裡統一比對數值
        {"f": 1200, "t": 600, "d": 250},
        {"f": 800, "t": 400, "d": 150},
    ]

    for symbol, stock in stocks.items():
        if 'institutional' in stock and isinstance(stock['institutional'], list):
            original_len = len(stock['institutional'])
            
            new_institutional = []
            for record in stock['institutional']:
                f_val = record.get('foreign_net')
                t_val = record.get('trust_net')
                d_val = record.get('dealer_net')
                
                is_fake = False
                for fp in fake_fingerprints:
                    if f_val == fp.get('f') and t_val == fp.get('t'):
                        # 如果外資和投信都中，基本就是假的
                        is_fake = True
                        break
                
                if not is_fake:
                    new_institutional.append(record)
                else:
                    total_removed_records += 1
            
            if len(new_institutional) < original_len:
                stock['institutional'] = new_institutional
                cleaned_stocks_count += 1
                # 強制重置最後成功時間，讓系統重新抓取正確資料
                stock['last_succeeded_at'] = ""

    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"🧹 {file_path}:")
    print(f"   - 清理了 {cleaned_stocks_count} 檔股票")
    print(f"   - 總共移除了 {total_removed_records} 筆假紀錄")

if __name__ == "__main__":
    deep_sanitize('docs/data.json')
    deep_sanitize('docs/data_base.json')
