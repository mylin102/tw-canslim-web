"""
Excel data processor for CANSLIM analysis.
Reads financial data from Excel files and integrates with CANSLIM engine.
"""

import os
import logging
import json
import pandas as pd
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class ExcelDataProcessor:
    """Process Excel files to extract CANSLIM-related data."""
    
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self.fundamental_data_file = None
        self.health_check_file = None
        self._find_excel_files()
    
    def _find_excel_files(self):
        """Find Excel files in the base directory."""
        for file in os.listdir(self.base_dir):
            if file.endswith('.xlsm') or file.endswith('.xlsx'):
                if '基本面數據' in file or '基本面' in file:
                    self.fundamental_data_file = os.path.join(self.base_dir, file)
                    logger.info(f"Found fundamental data file: {file}")
                elif '健診' in file or '健诊' in file:
                    self.health_check_file = os.path.join(self.base_dir, file)
                    logger.info(f"Found health check file: {file}")
        
        # If multiple health check files exist, use the newest one
        if self.health_check_file:
            logger.info(f"Using health check file: {os.path.basename(self.health_check_file)}")
    
    def load_fundamental_data(self) -> Optional[Dict]:
        """
        Load fundamental data from Excel file.
        Returns dict with stock symbols as keys and financial metrics as values.
        """
        if not self.fundamental_data_file or not os.path.exists(self.fundamental_data_file):
            logger.warning("Fundamental data file not found")
            return None
        
        try:
            # Read 基本面數據 sheet
            df = pd.read_excel(
                self.fundamental_data_file,
                sheet_name='基本面數據',
                header=0
            )
            
            logger.info(f"Loaded fundamental data: {len(df)} rows")
            
            # Parse the data structure
            # The file has: Year, EPS, Growth Rate, Stock Code, Quarter, EPS, Growth Rate, etc.
            result = {}
            
            # Extract stock code (usually in column D)
            if len(df.columns) > 3 and df.iloc[0, 3] is not None:
                stock_code = str(df.iloc[0, 3]).strip()
                
                # Extract annual EPS and growth rates
                annual_data = []
                for i in range(len(df)):
                    year = df.iloc[i, 0]  # Column A: Year
                    eps = df.iloc[i, 1]   # Column B: EPS
                    growth = df.iloc[i, 2] if len(df.columns) > 2 else None  # Column C: Growth Rate
                    
                    if pd.notna(year) and pd.notna(eps):
                        annual_data.append({
                            'year': int(year),
                            'eps': float(eps),
                            'growth_rate': float(growth) if pd.notna(growth) else None
                        })
                
                result[stock_code] = {
                    'annual_data': annual_data,
                    'stock_code': stock_code
                }
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to load fundamental data: {e}")
            return None
    
    def load_health_check_data(self) -> Optional[Dict[str, Dict]]:
        """
        Load health check data from Excel file.
        Returns dict with stock symbols as keys and CANSLIM ratings as values.
        """
        if not self.health_check_file or not os.path.exists(self.health_check_file):
            logger.warning("Health check file not found")
            return None
        
        try:
            result = {}
            
            # Read Sheet1 (main stock list)
            df_main = pd.read_excel(
                self.health_check_file,
                sheet_name='Sheet1',
                header=None
            )
            
            # Parse stock codes and names
            for _, row in df_main.iterrows():
                try:
                    # Handle different formats of stock codes
                    raw_code = row[0]
                    if pd.isna(raw_code):
                        continue
                    
                    # Convert to string and clean up
                    stock_code = str(raw_code).strip()
                    
                    # Remove decimal if present (e.g., "2330.0" -> "2330")
                    if '.' in stock_code:
                        stock_code = stock_code.split('.')[0]
                    
                    # Validate it's a 4-digit stock code
                    if not stock_code.isdigit() or len(stock_code) != 4:
                        continue
                    
                    stock_name = str(row[1]).strip() if pd.notna(row[1]) else ''
                    
                    result[stock_code] = {
                        'name': stock_name,
                        'composite_rating': None,
                        'eps_rating': None,
                        'rs_rating': None,
                        'smr_rating': None
                    }
                except Exception as e:
                    logger.debug(f"Skipping row with invalid data: {e}")
                    continue
            
            # Read Composite Rating sheet if exists
            if 'Composite Rating' in pd.ExcelFile(self.health_check_file).sheet_names:
                try:
                    df_cr = pd.read_excel(
                        self.health_check_file,
                        sheet_name='Composite Rating',
                        header=0
                    )
                    
                    # Parse composite ratings
                    # New format (60409): 代號, 名稱, Composite Rating
                    # Old format (60313): 代號, 代號, 名稱, Composite Rating, ...
                    for _, row in df_cr.iterrows():
                        try:
                            # Skip rows with no data
                            if pd.isna(row.iloc[0]):
                                continue
                            
                            # Handle different column positions
                            raw_code = str(row.iloc[0]).strip()
                            
                            # Find the rating column (usually column index 2 or 3)
                            rating = None
                            for col_idx in range(2, min(5, len(row))):
                                if pd.notna(row.iloc[col_idx]):
                                    val = row.iloc[col_idx]
                                    if isinstance(val, (int, float)) and 0 <= val <= 100:
                                        rating = val
                                        break
                            
                            if '.' in raw_code:
                                raw_code = raw_code.split('.')[0]
                            
                            if not raw_code.isdigit() or len(raw_code) != 4:
                                continue
                            
                            stock_code = raw_code
                            
                            if stock_code in result:
                                result[stock_code]['composite_rating'] = float(rating) if rating else None
                        except Exception as e:
                            logger.debug(f"Skipping Composite Rating row: {e}")
                            continue
                except Exception as e:
                    logger.warning(f"Failed to read Composite Rating sheet: {e}")
            
            # Read EPS Rating sheet
            if 'EPS Rating' in pd.ExcelFile(self.health_check_file).sheet_names:
                try:
                    df_eps = pd.read_excel(
                        self.health_check_file,
                        sheet_name='EPS Rating',
                        header=None
                    )
                    
                    # New format (60409): 股票代號, EPS Rating
                    # Old format (60313): 股票代號, 股票代號, 收盤, EPS Rating
                    for _, row in df_eps.iterrows():
                        try:
                            if pd.isna(row.iloc[0]):
                                continue
                            
                            raw_code = str(row.iloc[0]).strip()
                            
                            # Find the rating column
                            rating = None
                            for col_idx in range(1, min(5, len(row))):
                                if pd.notna(row.iloc[col_idx]):
                                    val = row.iloc[col_idx]
                                    if isinstance(val, (int, float)) and 0 <= val <= 100:
                                        rating = val
                                        break
                            
                            if '.' in raw_code:
                                raw_code = raw_code.split('.')[0]
                            
                            if not raw_code.isdigit() or len(raw_code) != 4:
                                continue
                            
                            stock_code = raw_code
                            
                            if stock_code in result:
                                result[stock_code]['eps_rating'] = float(rating) if rating else None
                        except Exception as e:
                            logger.debug(f"Skipping EPS Rating row: {e}")
                            continue
                except Exception as e:
                    logger.warning(f"Failed to read EPS Rating sheet: {e}")
            
            # Read RS Rating sheet
            if 'RS Rating' in pd.ExcelFile(self.health_check_file).sheet_names:
                try:
                    df_rs = pd.read_excel(
                        self.health_check_file,
                        sheet_name='RS Rating',
                        header=None
                    )
                    
                    # New format (60409): 股票代號, RS Rating
                    # Old format (60313): 股票代號, 股票代號, 股票名稱, RS Rating, ...
                    for _, row in df_rs.iterrows():
                        try:
                            if pd.isna(row.iloc[0]):
                                continue
                            
                            raw_code = str(row.iloc[0]).strip()
                            
                            # Find the rating column
                            rating = None
                            for col_idx in range(1, min(5, len(row))):
                                if pd.notna(row.iloc[col_idx]):
                                    val = row.iloc[col_idx]
                                    if isinstance(val, (int, float)) and 0 <= val <= 100:
                                        rating = val
                                        break
                            
                            if '.' in raw_code:
                                raw_code = raw_code.split('.')[0]
                            
                            if not raw_code.isdigit() or len(raw_code) != 4:
                                continue
                            
                            stock_code = raw_code
                            
                            if stock_code in result:
                                result[stock_code]['rs_rating'] = float(rating) if rating else None
                        except Exception as e:
                            logger.debug(f"Skipping RS Rating row: {e}")
                            continue
                except Exception as e:
                    logger.warning(f"Failed to read RS Rating sheet: {e}")
            
            # Read SMR Rating sheet
            if 'SMR Rating' in pd.ExcelFile(self.health_check_file).sheet_names:
                try:
                    df_smr = pd.read_excel(
                        self.health_check_file,
                        sheet_name='SMR Rating',
                        header=0
                    )
                    
                    # New format (60409): 商品, 股票代號, SMR Rating
                    # Old format (60313): 代碼, 商品, 股票代號, SMR Rating
                    for _, row in df_smr.iterrows():
                        try:
                            if pd.isna(row.iloc[0]):
                                continue
                            
                            # Try to find stock code in first 2 columns
                            stock_code = None
                            rating = None
                            
                            for col_idx in range(min(3, len(row))):
                                val = str(row.iloc[col_idx]).strip()
                                if '.' in val:
                                    val = val.split('.')[0]
                                
                                # Check if it's a 4-digit code
                                if val.isdigit() and len(val) == 4:
                                    stock_code = val
                                    continue
                                
                                # Check if it's a rating (A+, A, B, etc.)
                                if val in ['A+', 'A', 'A-', 'B+', 'B', 'B-', 'C+', 'C', 'C-', 'D', 'E']:
                                    rating = val
                            
                            # If we still have the old format with .TW
                            if not stock_code and pd.notna(row.iloc[0]):
                                raw_code = str(row.iloc[0]).strip()
                                if '.TW' in raw_code:
                                    stock_code = raw_code.replace('.TW', '')
                                    if len(row) > 3:
                                        rating = str(row.iloc[3]).strip()
                            
                            if not stock_code or len(stock_code) != 4:
                                continue
                            
                            if stock_code in result:
                                result[stock_code]['smr_rating'] = rating
                        except Exception as e:
                            logger.debug(f"Skipping SMR Rating row: {e}")
                            continue
                except Exception as e:
                    logger.warning(f"Failed to read SMR Rating sheet: {e}")
            
            logger.info(f"Loaded health check data for {len(result)} stocks")
            return result
            
        except Exception as e:
            logger.error(f"Failed to load health check data: {e}")
            return None
    
    def get_stock_financial_history(self, stock_code: str) -> Optional[List[Dict]]:
        """Get historical financial data for a specific stock."""
        fundamental_data = self.load_fundamental_data()
        
        if not fundamental_data or stock_code not in fundamental_data:
            return None
        
        stock_data = fundamental_data[stock_code]
        return stock_data.get('annual_data', [])
    
    def get_stock_ratings(self, stock_code: str) -> Optional[Dict]:
        """Get CANSLIM ratings for a specific stock."""
        health_data = self.load_health_check_data()
        
        if not health_data or stock_code not in health_data:
            return None
        
        return health_data[stock_code]
    
    def load_fund_holdings_data(self) -> Optional[Dict[str, Dict]]:
        """
        Load fund holdings data from Excel file.
        Returns dict with stock symbols as keys and fund holding changes as values.
        """
        if not self.health_check_file or not os.path.exists(self.health_check_file):
            logger.warning("Health check file not found")
            return None
        
        try:
            # Check if 基金持有檔數 sheet exists
            excel_file = pd.ExcelFile(self.health_check_file)
            if '基金持有檔數' not in excel_file.sheet_names:
                logger.warning("基金持有檔數 sheet not found")
                return None
            
            # Read 基金持有檔數 sheet
            df = pd.read_excel(
                self.health_check_file,
                sheet_name='基金持有檔數',
                header=0
            )
            
            result = {}
            
            # Parse fund holdings data
            # Format: 股票名稱, 股票名稱, 漲跌, 漲跌幅, 本月投信基金持股檔數, 上月投信基金持股檔數
            for _, row in df.iterrows():
                try:
                    if pd.isna(row.iloc[0]):
                        continue
                    
                    # Extract stock code
                    raw_code = str(row.iloc[0]).strip()
                    if '.' in raw_code:
                        raw_code = raw_code.split('.')[0]
                    
                    if not raw_code.isdigit() or len(raw_code) != 4:
                        continue
                    
                    stock_code = raw_code
                    
                    # Extract fund holding data
                    current_month = None
                    previous_month = None
                    change = None
                    change_pct = None
                    
                    if len(row) > 4 and pd.notna(row.iloc[4]):
                        current_month = int(row.iloc[4])
                    
                    if len(row) > 5 and pd.notna(row.iloc[5]):
                        previous_month = int(row.iloc[5])
                    
                    if current_month is not None and previous_month is not None:
                        change = current_month - previous_month
                        if previous_month > 0:
                            change_pct = round((change / previous_month) * 100, 2)
                    
                    result[stock_code] = {
                        'current_month': current_month,
                        'previous_month': previous_month,
                        'change': change,
                        'change_pct': change_pct
                    }
                except Exception as e:
                    logger.debug(f"Skipping fund holdings row: {e}")
                    continue
            
            logger.info(f"Loaded fund holdings data for {len(result)} stocks")
            return result
            
        except Exception as e:
            logger.error(f"Failed to load fund holdings data: {e}")
            return None
    
    def load_industry_data(self) -> Optional[Dict[str, Dict]]:
        """
        Load industry classification data.
        Returns dict with stock symbols as keys and industry info as values.
        """
        result = {}
        
        # 首先嘗試從Excel檔案加載
        excel_result = self._load_industry_from_excel()
        if excel_result:
            result.update(excel_result)
            logger.info(f"Loaded industry data from Excel for {len(excel_result)} stocks")
        
        # 然後嘗試從本地快取加載，補充Excel中沒有的股票
        cache_result = self._load_industry_from_cache()
        if cache_result:
            # 只添加Excel中沒有的股票
            added_count = 0
            for stock_code, data in cache_result.items():
                if stock_code not in result:
                    result[stock_code] = data
                    added_count += 1
            
            if added_count > 0:
                logger.info(f"Added {added_count} stocks from cache (total: {len(result)})")
        
        # 如果仍然沒有數據，從FinMind API獲取
        if not result:
            api_result = self._load_industry_from_finmind()
            if api_result:
                result.update(api_result)
                self._save_industry_to_cache(api_result)
                logger.info(f"Loaded industry data from FinMind API for {len(api_result)} stocks")
        
        if result:
            logger.info(f"Total industry data: {len(result)} stocks")
            return result
        
        logger.warning("Failed to load industry data from any source")
        return None
    
    def _load_industry_from_excel(self) -> Optional[Dict[str, Dict]]:
        """Load industry data from Excel file."""
        if not self.health_check_file or not os.path.exists(self.health_check_file):
            return None
        
        try:
            result = {}
            
            if '上市櫃產業名單' not in pd.ExcelFile(self.health_check_file).sheet_names:
                return None
            
            df = pd.read_excel(
                self.health_check_file,
                sheet_name='上市櫃產業名單',
                header=None
            )
            
            # First row: alternating rating (A+, B, C...) and industry name (上市水泥, 上市食品...)
            # Industry names are at odd indices (1, 3, 5, 7...)
            industry_names = {}
            for col_idx in range(0, len(df.iloc[0]), 2):
                if col_idx + 1 < len(df.iloc[0]) and pd.notna(df.iloc[0].iloc[col_idx + 1]):
                    industry_names[col_idx] = str(df.iloc[0].iloc[col_idx + 1]).strip()
            
            # Process stock rows
            for row_idx in range(1, len(df)):
                row = df.iloc[row_idx]
                for col_idx in range(0, len(row), 2):
                    if col_idx < len(row) and pd.notna(row.iloc[col_idx]):
                        stock_code = str(int(row.iloc[col_idx])).strip()
                        stock_name = str(row.iloc[col_idx + 1]).strip() if col_idx + 1 < len(row) and pd.notna(row.iloc[col_idx + 1]) else ''
                        industry = industry_names.get(col_idx, '未知')
                        
                        result[stock_code] = {
                            'name': stock_name,
                            'industry': industry
                        }
            
            return result if result else None
            
        except Exception as e:
            logger.debug(f"Failed to load industry data from Excel: {e}")
            return None
    
    def _load_industry_from_cache(self) -> Optional[Dict[str, Dict]]:
        """Load industry data from local cache file."""
        # 嘗試加載簡化快取檔案
        simplified_cache_file = os.path.join(self.base_dir, 'industry_cache_simplified.json')
        if os.path.exists(simplified_cache_file):
            try:
                with open(simplified_cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # 檢查快取是否過期（超過30天）
                if 'timestamp' in data:
                    cache_time = datetime.fromisoformat(data['timestamp'])
                    if (datetime.now() - cache_time).days > 30:
                        logger.info("Industry cache is older than 30 days, will refresh")
                        return None
                
                # 轉換簡化格式為完整格式
                industry_mapping = data.get('industry_mapping', {})
                result = {}
                for stock_code, industry in industry_mapping.items():
                    result[stock_code] = {
                        'name': '',  # 簡化版本不包含股票名稱
                        'industry': industry
                    }
                
                logger.info(f"Loaded industry data from simplified cache: {len(result)} stocks")
                return result
            except Exception as e:
                logger.debug(f"Failed to load simplified cache: {e}")
        
        # 如果簡化快取不存在，嘗試加載完整快取
        cache_file = os.path.join(self.base_dir, 'industry_cache.json')
        if not os.path.exists(cache_file):
            return None
        
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 檢查快取是否過期（超過30天）
            if 'timestamp' in data:
                cache_time = datetime.fromisoformat(data['timestamp'])
                if (datetime.now() - cache_time).days > 30:
                    logger.info("Industry cache is older than 30 days, will refresh")
                    return None
            
            return data.get('industry_data', {})
        except Exception as e:
            logger.debug(f"Failed to load industry cache: {e}")
            return None
    
    def _save_industry_to_cache(self, industry_data: Dict[str, Dict]) -> None:
        """Save industry data to local cache file."""
        cache_file = os.path.join(self.base_dir, 'industry_cache.json')
        try:
            data = {
                'timestamp': datetime.now().isoformat(),
                'industry_data': industry_data
            }
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"Saved industry data to cache: {cache_file}")
        except Exception as e:
            logger.error(f"Failed to save industry cache: {e}")
    
    def _load_industry_from_finmind(self) -> Optional[Dict[str, Dict]]:
        """Load industry data from FinMind API."""
        try:
            # 從環境變數讀取FinMind token
            import os
            from dotenv import load_dotenv
            
            load_dotenv()
            finmind_token = os.getenv('FINMIND_TOKEN')
            
            if not finmind_token:
                logger.warning("FINMIND_TOKEN not found in environment variables")
                return None
            
            # 呼叫FinMind API
            import requests
            
            url = "https://api.finmindtrade.com/api/v4/data"
            headers = {"Authorization": f"Bearer {finmind_token}"}
            params = {
                "dataset": "TaiwanStockInfo",
            }
            
            response = requests.get(url, headers=headers, params=params, timeout=30)
            
            if response.status_code != 200:
                logger.error(f"FinMind API error: {response.status_code} - {response.text[:200]}")
                return None
            
            data = response.json()
            if data.get('status') != 200:
                logger.error(f"FinMind API returned error: {data}")
                return None
            
            stocks = data.get('data', [])
            if not stocks:
                logger.warning("FinMind API returned empty data")
                return None
            
            # 處理API數據
            result = {}
            for stock in stocks:
                stock_id = stock.get('stock_id', '').strip()
                if not stock_id or len(stock_id) != 4:
                    continue
                
                stock_name = stock.get('stock_name', '').strip()
                industry_category = stock.get('industry_category', '').strip()
                
                # 簡化產業分類名稱
                if industry_category:
                    # 移除冗長的後綴
                    if '指數股票型基金' in industry_category:
                        industry_category = 'ETF'
                    elif '受益證券' in industry_category:
                        industry_category = 'REITs'
                
                result[stock_id] = {
                    'name': stock_name,
                    'industry': industry_category or '未知'
                }
            
            logger.info(f"Retrieved {len(result)} stocks from FinMind API")
            return result if result else None
            
        except Exception as e:
            logger.error(f"Failed to load industry data from FinMind: {e}")
            return None
    
    def get_industry_strength(self) -> Optional[List[Dict]]:
        """
        Get industry strength ranking.
        Returns list of top 30 industries sorted by rank.
        """
        if not self.health_check_file or not os.path.exists(self.health_check_file):
            return None
        
        try:
            if 'Group Rank' not in pd.ExcelFile(self.health_check_file).sheet_names:
                return None
            
            df = pd.read_excel(
                self.health_check_file,
                sheet_name='Group Rank',
                header=None
            )
            
            result = []
            for _, row in df.iterrows():
                if pd.notna(row.iloc[0]) and pd.notna(row.iloc[1]):
                    try:
                        rank = int(row.iloc[0])
                        industry = str(row.iloc[1]).strip()
                        strength = float(row.iloc[2]) if pd.notna(row.iloc[2]) else 0
                        
                        result.append({
                            'rank': rank,
                            'industry': industry,
                            'strength': strength
                        })
                    except:
                        pass
            
            result.sort(key=lambda x: x['rank'])
            return result[:30]
            
        except Exception as e:
            logger.error(f"Failed to load industry strength: {e}")
            return None
