"""
整合更新腳本
先執行 futures_data_updater.py 更新分鐘K線
再執行 cycle_data_updater.py 更新週期K線
"""

import logging
import sys
from datetime import datetime

# 設定日誌
from logging.handlers import RotatingFileHandler
import os

# 確保 log 資料夾存在
log_dir = 'log'
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        RotatingFileHandler(os.path.join(log_dir, 'integrated_updater.log'), maxBytes=5*1024*1024, backupCount=3, encoding='utf-8')
    ]
)

def run_futures_updater():
    """執行期貨分鐘K線更新"""
    logging.info("=" * 60)
    logging.info("步驟 1: 開始更新期貨分鐘K線")
    logging.info("=" * 60)
    
    try:
        # 這裡需要根據實際情況調整
        # 如果 futures_data_updater.py 是獨立執行的 GUI 程式
        # 可能需要使用 subprocess 來執行
        
        import subprocess
        import os
        
        script_path = os.path.join(os.path.dirname(__file__), 'futures_data_updater.py')
        
        logging.info(f"執行腳本: {script_path}")
        
        # 注意: futures_data_updater.py 使用 tkinter，可能需要顯示視窗
        # 如果要在背景執行，需要修改原程式
        result = subprocess.run(
            ['python', script_path],
            capture_output=True,
            text=True,
            timeout=3600  # 1小時超時
        )
        
        if result.returncode == 0:
            logging.info("期貨分鐘K線更新完成")
            return True
        else:
            logging.error(f"期貨分鐘K線更新失敗: {result.stderr}")
            return False
            
    except Exception as e:
        logging.error(f"執行期貨更新程式時發生錯誤: {e}")
        return False

def run_cycle_updater(days=1):
    """執行週期K線更新"""
    logging.info("=" * 60)
    logging.info("步驟 2: 開始更新週期K線")
    logging.info("=" * 60)
    
    try:
        from cycle_data_updater import CycleDataUpdater
        
        updater = CycleDataUpdater()
        updater.update_all_enabled_products(days=days)
        
        logging.info("週期K線更新完成")
        return True
        
    except Exception as e:
        logging.error(f"執行週期更新程式時發生錯誤: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主程式"""
    start_time = datetime.now()
    logging.info("=" * 60)
    logging.info("整合更新程式開始執行")
    logging.info(f"開始時間: {start_time}")
    logging.info("=" * 60)
    
    # 解析命令列參數
    update_days = 1  # 預設只更新當天
    skip_futures = False  # 是否跳過期貨更新
    
    if len(sys.argv) > 1:
        for arg in sys.argv[1:]:
            if arg.startswith('--days='):
                update_days = int(arg.split('=')[1])
            elif arg == '--skip-futures':
                skip_futures = True
            elif arg == '--help':
                print("使用方式:")
                print("  python integrated_updater.py [選項]")
                print("\n選項:")
                print("  --days=N          更新最近N天的週期K線 (預設: 1)")
                print("  --skip-futures    跳過期貨分鐘K線更新，只更新週期K線")
                print("  --help            顯示此說明")
                return
    
    success = True
    
    # 步驟 1: 更新期貨分鐘K線 (如果不跳過)
    if not skip_futures:
        if not run_futures_updater():
            logging.warning("期貨分鐘K線更新失敗，但仍繼續執行週期K線更新")
            # 不設定 success = False，因為可能只是沒有新資料
    else:
        logging.info("已跳過期貨分鐘K線更新")
    
    # 步驟 2: 更新週期K線
    if not run_cycle_updater(days=update_days):
        success = False
    
    # 完成
    end_time = datetime.now()
    duration = end_time - start_time
    
    logging.info("=" * 60)
    if success:
        logging.info("整合更新程式執行完成")
    else:
        logging.error("整合更新程式執行時發生錯誤")
    logging.info(f"結束時間: {end_time}")
    logging.info(f"執行時間: {duration}")
    logging.info("=" * 60)
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
