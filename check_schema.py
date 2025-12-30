from common.db_utils import DatabaseManager
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)

def check_columns():
    db = DatabaseManager()
    engine = db.get_engine()
    
    if not engine:
        return

    with engine.connect() as conn:
        print("Table: captial_trade_option")
        result = conn.execute(text("DESCRIBE captial_trade_option"))
        for row in result:
            print(row)

if __name__ == "__main__":
    check_columns()