import pandas as pd
from common.db_utils import DatabaseManager

symbols = ["NQ0000", "CL0000"]
start_date = "2025-03-25"
end_date = "2025-12-24"
cycle = "5m"

db = DatabaseManager()

for symbol in symbols:
    df = db.fetch_data_flex(symbol, cycle=cycle, start_date=start_date, end_date=end_date)
    if not df.empty:
        print(f"[{symbol} {cycle}] 資料確認: {len(df)} 筆")
        print(df.tail(3))
    else:
        print(f"[{symbol} {cycle}] 無資料")
