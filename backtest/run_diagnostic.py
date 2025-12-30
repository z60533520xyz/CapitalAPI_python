import logging
import sys
import os
import pandas as pd
from datetime import datetime

# 添加專案根目錄到 sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.db_utils import DatabaseManager
from backtest.engine import BacktestEngine
from backtest.analyzer import BacktestAnalyzer
from strategy.factory import StrategyFactory

# 設定 logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def run_diagnostic(strategy_type: int, strategy_name: str, days: int = 60):
    print(f"\n{'='*50}")
    print(f"開始診斷回測: {strategy_name} (ID: {strategy_type})")
    print(f"{'='*50}")

    # 1. 載入資料
    db = DatabaseManager()
    symbol = "CL0000"
    cycle = 5 
    
    end_date = datetime.now()
    start_date = end_date - pd.Timedelta(days=days)
    
    print(f"正在載入 {symbol} (Cycle {cycle}) 過去 {days} 天的資料...")
    df = db.get_kline_data(symbol, cycle, start_date, end_date)
    
    if df.empty:
        print("錯誤: 載入資料失敗或資料為空")
        return

    print(f"載入完成: {len(df)} 筆 K 線資料")

    # 2. 初始化策略 (啟用 Debug)
    config = {
        'stopLossPercent': 0.01,
        'takeProfitPercent': 0.02,
        'trailingStopPercent': 0.005,
        'bbPeriod': 20,
        'bbMultiplier': 2.0,
        'kcPeriod': 20,
        'kcMultiplier': 1.5,
        'strategy_type': strategy_type,
        'debug': True # 啟用 Debug
    }
    
    strategy_id = f"Diag_{strategy_name}"
    strategy = StrategyFactory.get_strategy(strategy_type, strategy_id, config)
    strategy.on_init()

    # 3. 執行回測
    engine = BacktestEngine(initial_capital=100000)
    analyzer = engine.run(strategy, df)

    # 4. 輸出結果
    analyzer.print_report()
    
    if analyzer.trades:
        print("交易明細:")
        print(pd.DataFrame(analyzer.trades))
    else:
        print("無交易產生。請檢查 Debug 輸出。")

if __name__ == "__main__":
    # 診斷 ID 8
    run_diagnostic(8, "DailyRangeReversal")
    
    # 診斷 ID 12
    run_diagnostic(12, "SqueezeBreakoutOptimized")
