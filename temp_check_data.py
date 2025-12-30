# temp_check_data.py
import sys
import os
import pandas as pd

# Add project root to the Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from common.db_utils import DatabaseManager

def check_data():
    """
    Connects to the database and checks for CL0000 data availability.
    """
    print("初始化資料庫連線...")
    db_manager = DatabaseManager()
    
    symbol = 'CL0000'
    cycle = '60m'
    start_date = '2025-01-01'
    end_date = '2025-12-25'
    
    print(f"正在查詢商品 {symbol} 在 {start_date} 到 {end_date} 期間的 {cycle} K線數據...")
    
    df = db_manager.fetch_data_flex(
        symbol=symbol,
        cycle=cycle,
        start_date=start_date,
        end_date=end_date,
        limit=999999  # Set a large limit to get all data in the range
    )
    
    if df.empty:
        print("查詢結果：找不到任何數據。")
        print("請先執行 `data_etl` 相關腳本來下載歷史數據。")
    else:
        print(f"查詢成功！共找到 {len(df)} 筆數據。")
        actual_start_date = df.index.min().strftime('%Y-%m-%d')
        actual_end_date = df.index.max().strftime('%Y-%m-%d')
        print(f"數據期間為： {actual_start_date} 到 {actual_end_date}")
        
        # Check for completeness
        date_range = pd.date_range(start=start_date, end=end_date, freq='B') # Business days
        trading_days_in_range = len(date_range)
        actual_trading_days = len(df.resample('D').count())
        
        print(f"指定範圍內約有 {trading_days_in_range} 個交易日。")
        print(f"數據庫中實際涵蓋 {actual_trading_days} 個交易日。")
        
        completeness_ratio = actual_trading_days / trading_days_in_range if trading_days_in_range > 0 else 0
        if completeness_ratio > 0.9:
            print("數據完整性良好。")
        else:
            print("警告：數據可能不完整，建議執行數據更新腳本。")

if __name__ == '__main__':
    check_data()
