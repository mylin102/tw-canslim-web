#!/usr/bin/env python3
"""
強化版CANSLIM I指標計算
使用投信買賣超趨勢作為機構認同度指標
"""

import os
import sys
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging

# 設置日誌
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class InstitutionalSponsorshipAnalyzer:
    """機構認同度分析器"""
    
    def __init__(self, finmind_token: Optional[str] = None):
        self.finmind_token = finmind_token or os.getenv('FINMIND_TOKEN')
        self.base_url = "https://api.finmindtrade.com/api/v4/data"
        
    def get_institutional_data(self, stock_id: str, days: int = 120) -> Optional[pd.DataFrame]:
        """從FinMind獲取三大法人買賣超數據"""
        try:
            import requests
            
            # 計算開始日期
            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            
            params = {
                "dataset": "TaiwanStockInstitutionalInvestorsBuySell",
                "data_id": stock_id,
                "start_date": start_date,
                "end_date": end_date,
            }
            
            if self.finmind_token:
                headers = {"Authorization": f"Bearer {self.finmind_token}"}
                response = requests.get(self.base_url, headers=headers, params=params, timeout=30)
            else:
                response = requests.get(self.base_url, params=params, timeout=30)
            
            if response.status_code != 200:
                logger.error(f"API錯誤 {response.status_code}: {response.text[:200]}")
                return None
            
            data = response.json()
            if data.get('status') != 200:
                logger.error(f"FinMind API返回錯誤: {data}")
                return None
            
            df = pd.DataFrame(data.get('data', []))
            if df.empty:
                logger.warning(f"股票 {stock_id} 無法人買賣超數據")
                return None
            
            # 轉換日期和數值
            df['date'] = pd.to_datetime(df['date'])
            numeric_cols = ['buy', 'sell']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
            # 計算淨買超
            df['net'] = df['buy'] - df['sell']
            
            # 映射法人名稱到中文
            name_mapping = {
                'Foreign_Investor': '外資',
                'Investment_Trust': '投信',
                'Dealer_Hedging': '自營商(避險)',
                'Dealer_self': '自營商(自行買賣)',
                'Foreign_Dealer_Self': '外資自營商'
            }
            df['name_cn'] = df['name'].map(name_mapping)
            
            # 按日期排序
            df = df.sort_values('date')
            
            return df
            
        except Exception as e:
            logger.error(f"獲取法人數據失敗 {stock_id}: {e}")
            return None
    
    def calculate_i_score(self, df: pd.DataFrame) -> Dict:
        """計算強化版CANSLIM I指標分數"""
        if df is None or df.empty:
            return {
                'score': 0,
                'trust_consecutive_days': 0,
                'trust_20d_cumulative': 0,
                'foreign_sync': 0,
                'details': {}
            }
        
        try:
            # 分離投信和外資數據
            trust_df = df[df['name_cn'] == '投信'].copy()
            foreign_df = df[df['name_cn'] == '外資'].copy()
            
            if trust_df.empty:
                return {
                    'score': 0,
                    'trust_consecutive_days': 0,
                    'trust_20d_cumulative': 0,
                    'foreign_sync': 0,
                    'details': {}
                }
            
            # 計算投信連續買超天數
            trust_df['net'] = trust_df['buy'] - trust_df['sell']
            trust_df['is_buy'] = (trust_df['net'] > 0).astype(int)
            
            # 計算連續買超天數
            trust_df['consecutive_buy'] = trust_df['is_buy'].groupby(
                (trust_df['is_buy'] == 0).cumsum()
            ).cumsum()
            
            # 計算20日累積買超
            trust_df['20d_cumulative'] = trust_df['net'].rolling(20, min_periods=1).sum()
            
            # 計算外資同步買超
            if not foreign_df.empty:
                foreign_df['net'] = foreign_df['buy'] - foreign_df['sell']
                # 合併數據計算同步性
                merged = pd.merge(
                    trust_df[['date', 'net']].rename(columns={'net': 'trust_net'}),
                    foreign_df[['date', 'net']].rename(columns={'net': 'foreign_net'}),
                    on='date',
                    how='inner'
                )
                if not merged.empty:
                    # 計算最近20天同步買超的比例
                    recent = merged.tail(20)
                    sync_days = ((recent['trust_net'] > 0) & (recent['foreign_net'] > 0)).sum()
                    foreign_sync = sync_days / len(recent) if len(recent) > 0 else 0
                else:
                    foreign_sync = 0
            else:
                foreign_sync = 0
            
            # 獲取最新數據
            latest = trust_df.iloc[-1]
            
            # 正規化分數
            consecutive_days = min(latest['consecutive_buy'], 20)  # 上限20天
            cumulative_20d = latest['20d_cumulative']
            
            # 正規化到0-1範圍
            norm_consecutive = consecutive_days / 20  # 0-1
            norm_cumulative = self._normalize_cumulative(cumulative_20d)
            
            # 計算最終分數 (0-100)
            score = (
                norm_consecutive * 40 +  # 連續買超天數權重40%
                norm_cumulative * 40 +   # 20日累積買超權重40%
                foreign_sync * 20        # 外資同步權重20%
            )
            
            return {
                'score': round(score, 1),
                'trust_consecutive_days': int(consecutive_days),
                'trust_20d_cumulative': int(cumulative_20d),
                'foreign_sync': round(foreign_sync * 100, 1),  # 百分比
                'details': {
                    'last_date': latest['date'].strftime('%Y-%m-%d'),
                    'last_net': int(latest['net']),
                    'data_points': len(trust_df)
                }
            }
            
        except Exception as e:
            logger.error(f"計算I指標分數失敗: {e}")
            return {
                'score': 0,
                'trust_consecutive_days': 0,
                'trust_20d_cumulative': 0,
                'foreign_sync': 0,
                'details': {}
            }
    
    def _normalize_cumulative(self, cumulative: float) -> float:
        """正規化20日累積買超到0-1範圍"""
        # 根據經驗值，20日累積買超超過10000張為滿分
        max_value = 10000
        normalized = min(abs(cumulative) / max_value, 1.0)
        
        # 如果是賣超，分數較低
        if cumulative < 0:
            normalized *= 0.3  # 賣超最多只能得30%分數
        
        return normalized
    
    def analyze_stock(self, stock_id: str) -> Dict:
        """分析單一股票的機構認同度"""
        logger.info(f"分析股票 {stock_id} 的機構認同度...")
        
        # 獲取數據
        df = self.get_institutional_data(stock_id)
        
        # 計算分數
        result = self.calculate_i_score(df)
        
        # 評估等級
        score = result['score']
        if score >= 80:
            grade = 'A+'
            description = '機構強力認同'
        elif score >= 60:
            grade = 'A'
            description = '機構積極買進'
        elif score >= 40:
            grade = 'B'
            description = '機構溫和買進'
        elif score >= 20:
            grade = 'C'
            description = '機構觀望'
        else:
            grade = 'D'
            description = '機構賣出'
        
        result.update({
            'stock_id': stock_id,
            'grade': grade,
            'description': description,
            'analysis_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        
        logger.info(f"股票 {stock_id} I指標分數: {score} ({grade})")
        
        return result

def test_analyzer():
    """測試分析器"""
    print("=== 測試強化版CANSLIM I指標 ===")
    
    analyzer = InstitutionalSponsorshipAnalyzer()
    
    # 測試幾支知名股票
    test_stocks = ['2330', '2317', '2454', '2303', '2308']
    
    results = []
    for stock in test_stocks:
        result = analyzer.analyze_stock(stock)
        results.append(result)
        
        print(f"\n股票 {stock}:")
        print(f"  分數: {result['score']} ({result['grade']}) - {result['description']}")
        print(f"  投信連續買超: {result['trust_consecutive_days']} 天")
        print(f"  20日累積買超: {result['trust_20d_cumulative']:,} 張")
        print(f"  外資同步: {result['foreign_sync']}%")
    
    # 保存結果
    output_file = 'institutional_analysis.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 分析完成，結果已保存到 {output_file}")
    
    return results

if __name__ == "__main__":
    print("開始計算強化版CANSLIM I指標...")
    test_analyzer()