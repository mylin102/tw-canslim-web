#!/usr/bin/env python3
"""
增量交易系統工作流程
整合 CANSLIM 資料更新與增量計算
"""

import os
import sys
import json
import logging
from datetime import datetime

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_dependencies():
    """檢查必要依賴"""
    try:
        import pandas
        import yfinance
        import numpy
        logger.info("✅ 必要依賴已安裝")
        return True
    except ImportError as e:
        logger.error(f"❌ 缺少依賴: {e}")
        logger.info("請執行: pip install pandas yfinance numpy")
        return False

def run_canslim_update():
    """執行 CANSLIM 資料更新"""
    logger.info("步驟 1: 執行 CANSLIM 資料更新...")
    
    try:
        # 嘗試執行 export_canslim.py
        import subprocess
        result = subprocess.run(
            [sys.executable, "export_canslim.py"],
            capture_output=True,
            text=True,
            timeout=600  # 10分鐘超時
        )
        
        if result.returncode == 0:
            logger.info("✅ CANSLIM 資料更新完成")
            return True
        else:
            logger.error(f"❌ CANSLIM 更新失敗: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"❌ 執行 CANSLIM 更新時發生錯誤: {e}")
        return False

def run_incremental_calculation():
    """執行增量計算"""
    logger.info("步驟 2: 執行增量計算...")
    
    try:
        # 檢查增量計算模組是否存在
        try:
            from update_state import IncrementalEngine
            from fetch_today_data import TodayDataFetcher
        except ImportError:
            logger.error("❌ 增量計算模組未找到")
            return False
        
        # 建立增量引擎
        engine = IncrementalEngine()
        
        # 檢查狀態檔案
        state_file = "docs/state.json"
        if not os.path.exists(state_file):
            logger.warning("⚠️  狀態檔案不存在，建立初始狀態")
            # 這裡可以呼叫建立初始狀態的函數
            # 但為了簡單起見，我們先跳過
            return False
        
        # 執行增量更新
        success = engine.run_incremental_update()
        
        if success:
            logger.info("✅ 增量計算完成")
            return True
        else:
            logger.error("❌ 增量計算失敗")
            return False
            
    except Exception as e:
        logger.error(f"❌ 增量計算錯誤: {e}")
        return False

def create_stock_index():
    """建立股票索引"""
    logger.info("步驟 3: 建立股票索引...")
    
    try:
        # 檢查股票索引模組是否存在
        try:
            from create_stock_index import create_stock_index_with_rs
        except ImportError:
            logger.error("❌ 股票索引模組未找到")
            return False
        
        # 建立股票索引
        success = create_stock_index_with_rs()
        
        if success:
            logger.info("✅ 股票索引建立完成")
            return True
        else:
            logger.error("❌ 股票索引建立失敗")
            return False
            
    except Exception as e:
        logger.error(f"❌ 股票索引錯誤: {e}")
        return False

def verify_results():
    """驗證結果"""
    logger.info("步驟 4: 驗證結果...")
    
    required_files = [
        "docs/data.json",
        "docs/data_light.json",
        "docs/signals.json",
        "docs/ranking.json",
        "docs/stock_index.json"
    ]
    
    all_exist = True
    for file_path in required_files:
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                if 'signals' in data:
                    count = len(data['signals'])
                    logger.info(f"✅ {file_path}: {count} 個訊號")
                elif 'ranking' in data:
                    count = len(data['ranking'])
                    logger.info(f"✅ {file_path}: {count} 筆排名")
                else:
                    size = os.path.getsize(file_path)
                    logger.info(f"✅ {file_path} ({size:,} bytes)")
                    
            except Exception as e:
                logger.error(f"❌ {file_path} 讀取失敗: {e}")
                all_exist = False
        else:
            logger.error(f"❌ {file_path} 不存在")
            all_exist = False
    
    return all_exist

def main():
    """主函數"""
    logger.info("🚀 開始增量交易系統工作流程")
    logger.info(f"開始時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 檢查依賴
    if not check_dependencies():
        return False
    
    # 執行工作流程
    steps = [
        ("CANSLIM 資料更新", run_canslim_update),
        ("增量計算", run_incremental_calculation),
        ("股票索引建立", create_stock_index),
        ("結果驗證", verify_results)
    ]
    
    all_success = True
    for step_name, step_func in steps:
        logger.info(f"--- 執行: {step_name} ---")
        success = step_func()
        
        if success:
            logger.info(f"✅ {step_name} 成功")
        else:
            logger.error(f"❌ {step_name} 失敗")
            all_success = False
            
        logger.info("")
    
    # 總結
    if all_success:
        logger.info("🎉 所有步驟完成！")
        logger.info(f"完成時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 顯示系統狀態
        logger.info("\n📊 系統狀態:")
        logger.info("  1. CANSLIM 資料: ✅ 已更新")
        logger.info("  2. 增量計算: ✅ 已完成")
        logger.info("  3. 交易訊號: ✅ 已產生")
        logger.info("  4. RS 排名: ✅ 已更新")
        logger.info("  5. 股票索引: ✅ 已建立")
        
    else:
        logger.error("⚠️  部分步驟失敗，請檢查日誌")
    
    return all_success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)