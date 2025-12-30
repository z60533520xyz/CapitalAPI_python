import pandas as pd
from common.db_utils import DatabaseManager
from datetime import datetime

symbol = "NQ0000"
start_date = "2025-03-25"
end_date = "2025-12-24"
cycle = "30m"

db = DatabaseManager()
df = db.fetch_data_flex(symbol, cycle=cycle, start_date=start_date, end_date=end_date)

if not df.empty:
    print(f"NQ0000 {cycle} 資料筆數: {len(df)}")
    df['hour'] = df.index.hour
    print("小時分佈:")
    print(df['hour'].value_counts().sort_index())
else:
    print(f"找不到 NQ0000 {cycle} 資料")
