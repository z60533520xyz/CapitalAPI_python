import sys
import os
import logging
import pandas as pd
from sqlalchemy import text

# 添加專案根目錄到 sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.db_utils import DatabaseManager

logging.basicConfig(level=logging.INFO, format='%(message)s')

def check_db():
    db = DatabaseManager()
    engine = db.get_engine()
    
    if not engine:
        logging.error("無法連接資料庫")
        return
    
    try:
        with engine.connect() as conn:
            # 檢查總筆數
            result = conn.execute(text("SELECT COUNT(*) FROM captial_kline_cycle")).scalar()
            logging.info(f"captial_kline_cycle 總筆數: {result}")
            
            # 檢查各商品與週期的筆數
            logging.info("正在統計各商品與週期的資料分佈...")
            query = text("SELECT code, Cycle, COUNT(*) as count, MIN(date) as min_date, MAX(date) as max_date FROM captial_kline_cycle GROUP BY code, Cycle")
            df = pd.read_sql(query, conn)
            
            if df.empty:
                logging.info("沒有任何週期 K 線資料")
            else:
                logging.info("\n" + df.to_string())
                
    except Exception as e:
        logging.error(f"查詢失敗: {e}")

if __name__ == "__main__":
    check_db()
