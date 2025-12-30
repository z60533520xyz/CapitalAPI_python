import sys
import os
import logging
from datetime import datetime

# 添加專案根目錄到 sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategy.ml_strategy import MLStrategy
from backtest.engine import BacktestEngine
from common.db_utils import DatabaseManager

# 設定日誌
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

import warnings
warnings.filterwarnings('ignore')

def run_analysis():
    print("開始執行 ML 策略回測分析...")
    
    # 1. 設定參數
    symbol = 'CL0000'
    cycle = 9 # 2小時K線
    days = 365
    contract_size = 1000 # 輕原油合約規格 (每點 1000 美元)
    initial_capital = 100000.0 # 初始資金 10萬美元
    
    # 2. 獲取資料
    print(f"載入 {symbol} 最近 {days} 天資料...")
    db = DatabaseManager()
    df = db.fetch_kline_data(symbol, cycle, days)
    
    if df.empty:
        print("錯誤: 無資料")
        return
        
    print(f"成功載入 {len(df)} 筆 K 線資料")
    print(f"資料區間: {df.iloc[0]['date']} 到 {df.iloc[-1]['date']}")
    
    # 3. 初始化策略 (啟用 backtest_mode)
    # 注意: 這裡使用較低的閾值 0.5 進行測試，實際交易建議使用 0.6/0.4
    strategy = MLStrategy(strategy_id="ML_Analysis", config={
        'backtest_mode': True,
        'long_threshold': 0.5, 
        'short_threshold': 0.5,
        'stop_loss_pct': 0.01 # 1% 止損
    })
    strategy.on_init()
    
    if not strategy.feature_names:
        print("錯誤: 策略未載入特徵名稱，請先訓練模型")
        return
        
    # 4. 初始化引擎
    engine = BacktestEngine(initial_capital=initial_capital)
    
    # 5. 執行回測
    print("開始回測模擬...")
    analyzer = engine.run(strategy, df, contract_size)
    
    # 6. 印出報告
    analyzer.print_report()

if __name__ == "__main__":
    run_analysis()
