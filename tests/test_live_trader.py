import logging
import sys
import os

# 添加專案根目錄到 sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from strategy.ml_strategy import MLStrategy
from live_trading.trader import LiveTrader

logging.basicConfig(level=logging.INFO)

def test_live_trader():
    print("開始測試 LiveTrader (模擬下單)...")
    
    # 1. 初始化策略
    strategy = MLStrategy(strategy_id="Live_Test", config={})
    
    # 2. 初始化 Trader
    config = {
        'isFake': True,
        'code': 'CL0000',
        'chart_id': 1,
        'strategy_config_id': 1,
        'target_symbol': 'CL0000',
        'tradeQty': 1,
        'contractSize': 1000.0
    }
    trader = LiveTrader(strategy, config=config)
    
    # 3. 模擬訊號
    signal = {
        'action': 'BUY',
        'quantity': 1,
        'price': 70.5,
        'reason': 'Test Signal'
    }
    
    print(f"發送模擬訊號: {signal}")
    trader.on_signal(signal)
    
    print("測試完成，請檢查資料庫 captial_trade_history 表")

if __name__ == "__main__":
    test_live_trader()
