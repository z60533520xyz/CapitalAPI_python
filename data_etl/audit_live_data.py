import pandas as pd
import os
import sys
from datetime import datetime
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.db_utils import DatabaseManager, SYMBOLS_CONFIG

def audit_data(symbol: str, cycle: str = "60m"):
    """
    比對實盤紀錄的 CSV 與資料庫歷史資料
    """
    # 1. 讀取實盤 CSV
    audit_file = f"logs/audit/live_kline_{symbol}.csv"
    if not os.path.exists(audit_file):
        print(f"找不到稽核檔案: {audit_file}")
        return

    print(f"讀取實盤紀錄: {audit_file}")
    live_df = pd.read_csv(audit_file)
    live_df['Date'] = pd.to_datetime(live_df['Date'])
    
    if live_df.empty:
        print("實盤紀錄為空")
        return

    # 取得時間範圍
    start_date = live_df['Date'].min().strftime('%Y-%m-%d')
    end_date = live_df['Date'].max().strftime('%Y-%m-%d')
    
    print(f"稽核區間: {start_date} ~ {end_date}")

    # 2. 讀取資料庫歷史資料
    db = DatabaseManager()
    db_df = db.fetch_data_flex(symbol, cycle=cycle, start_date=start_date, end_date=end_date)
    
    if db_df.empty:
        print("資料庫查無對應歷史資料")
        return

    # 3. 合併比對
    # db_df 的 index 是 Date，reset_index 以便合併
    db_df = db_df.reset_index()
    
    # 重新命名欄位以便區分
    live_df = live_df.rename(columns={'Close': 'Live_Close', 'Volume': 'Live_Vol'})
    db_df = db_df.rename(columns={'Close': 'DB_Close', 'Volume': 'DB_Vol'})
    
    # 只比對收盤價與成交量 (Open/High/Low 也可比對，但 Close 最重要)
    merged = pd.merge(live_df[['Date', 'Live_Close', 'Live_Vol']], 
                      db_df[['Date', 'DB_Close', 'DB_Vol']], 
                      on='Date', how='inner')
    
    if merged.empty:
        print("時間戳記完全無法對應 (可能是時區問題或秒數差異)")
        return

    # 計算差異
    merged['Diff_Close'] = merged['Live_Close'] - merged['DB_Close']
    merged['Diff_Vol'] = merged['Live_Vol'] - merged['DB_Vol']
    
    # 篩選出有差異的資料 (允許極小誤差)
    diff_records = merged[ (merged['Diff_Close'].abs() > 0.0001) | (merged['Diff_Vol'].abs() > 1) ]
    
    print(f"\n--- 比對結果 ({symbol}) ---")
    print(f"總比對筆數: {len(merged)}")
    print(f"完全一致筆數: {len(merged) - len(diff_records)}")
    print(f"差異筆數: {len(diff_records)}")
    
    if not diff_records.empty:
        print("\n差異明細 (前 10 筆):")
        print(diff_records.head(10))
    else:
        print("\n恭喜！實盤數據與歷史資料完全一致。")

if __name__ == "__main__":
    # 範例：稽核 NQ0000 (需先有實盤跑過的 CSV) 
    audit_data("NQ0000", "60m")
    # audit_data("CL0000", "60m")
