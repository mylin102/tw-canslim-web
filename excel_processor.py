"""
Excel data processor for CANSLIM analysis.
Reads financial data from Excel files and integrates with CANSLIM engine.
"""

import os
import logging
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
