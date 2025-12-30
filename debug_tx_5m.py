import pandas as pd
from common.db_utils import DatabaseManager

symbol = "TX00"
start_date = "2025-03-25"
end_date = "2025-12-24"
cycle = "5m"

db = DatabaseManager()
df = db.fetch_data_flex(symbol, cycle=cycle, start_date=start_date, end_date=end_date)

if not df.empty:
    print(f"{symbol} {cycle} 資料筆數: {len(df)}")
    print(df.head())
    print(df.tail())
else:
    print(f"找不到 {symbol} {cycle} 資料")
