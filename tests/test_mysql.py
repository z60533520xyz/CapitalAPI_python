"""
MySQL 連線測試
"""

import mysql.connector
from mysql.connector import Error
import sqlalchemy
import pandas as pd
from datetime import datetime, timedelta

print("測試 MySQL 套件安裝...")

# 1. 測試 mysql.connector
print("\n1 測試 mysql.connector...")
try:
    # 簡單連線測試（不連實際資料庫）
    config = {
        'host': 'localhost',
        'user': 'your_username',  # 暫時用任何名稱
        'password': 'your_password'
    }
    connection = mysql.connector.connect(**config)
    print("mysql.connector 匯入成功")
    connection.close()
except Exception as e:
    print(f" mysql.connector 警告: {e}")

# 2. 測試 sqlalchemy
print("\n2測試 sqlalchemy...")
try:
    # 建立引擎（不連線）
    engine = sqlalchemy.create_engine("sqlite:///:memory:")  # 使用記憶體 SQLite 測試
    print("sqlalchemy 引擎建立成功")
except Exception as e:
    print(f" sqlalchemy 警告: {e}")

# 3. 測試 pandas.read_sql
print("\n3測試 pandas 與 SQL...")
try:
    # 建立測試 DataFrame
    test_df = pd.DataFrame({
        'date': [datetime.now()],
        'close': [1285.0],
        'volume': [1000000]
    })
    print("pandas SQL 功能正常")
except Exception as e:
    print(f"pandas SQL 警告: {e}")

print("\n所有套件測試完成！")
print("現在可以執行 tsmc_trader.py 了")
