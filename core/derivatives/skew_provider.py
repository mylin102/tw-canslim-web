import os
import logging
import pandas as pd
from typing import Optional, Dict, Any
from datetime import datetime

try:
    from FinMind.data import DataLoader
except ImportError:
    DataLoader = None

logger = logging.getLogger(__name__)

class OptionSkewProvider:
    """
    Fetches raw option market data (TXO) for Skew calculation.
    """
    def __init__(self, api_token: str = None):
        self.api_token = api_token or os.environ.get('FINMIND_API_TOKEN')
        self.loader = DataLoader() if DataLoader else None
        if self.loader and self.api_token:
            self.loader.login_by_token(self.api_token)
            self.initialized = True
        else:
            self.initialized = False
            logger.warning("FinMind DataLoader or Token missing. Option data disabled.")

    def fetch_txo_market_snapshot(self) -> Optional[pd.DataFrame]:
        """
        Fetch current Taiwan Index Options (TXO) market data.
        Targeting the nearest monthly contract.
        """
        if not self.initialized:
            return None

        try:
            # 取得台指期選擇權即時/當日報價
            # TaiwanOptionTick / TaiwanOptionDaily
            today = datetime.now().strftime("%Y-%m-%d")
            
            # 這裡先抓取全市場的選擇權合約資訊，以便篩選近月
            # 注意：這裡使用 TaiwanOptionDaily 作為 EOD 戰情室的基礎
            df = self.loader.taiwan_option_daily(
                start_date=today,
                end_date=today
            )
            
            if df.empty:
                # 如果今日還沒收盤或沒資料，抓前一日
                from datetime import timedelta
                yesterday = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")
                df = self.loader.taiwan_option_daily(
                    start_date=yesterday,
                    end_date=today
                )

            if not df.empty:
                # 篩選台指期 (TXO)
                txo_df = df[df['Option_id'].str.startswith('TXO')]
                return txo_df
            
            return None
        except Exception as e:
            logger.error(f"Failed to fetch TXO data: {e}")
            return None

    def get_skew_context(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Processes raw DF into a context suitable for skew perception.
        """
        if df.empty:
            return {}
            
        # 簡單統計：目前市場上 Call 與 Put 的總成交量與未平倉量
        # 這只是基礎，進階 Skew 需計算 Vol Smile
        call_v = df[df['CallPut'] == 'Call']['Volume'].sum()
        put_v = df[df['CallPut'] == 'Put']['Volume'].sum()
        pcr = put_v / call_v if call_v > 0 else 0
        
        return {
            "pcr_volume": round(pcr, 2),
            "total_records": len(df),
            "as_of": df['date'].iloc[-1] if 'date' in df.columns else "Unknown"
        }
