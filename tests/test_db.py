import sys
import os
sys.path.append(os.getcwd())
try:
    from common.db_utils import DatabaseManager
    print("Import success")
    db = DatabaseManager()
    print("DB init success")
except Exception as e:
    print(f"Error: {e}")
