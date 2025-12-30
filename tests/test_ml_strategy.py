import sys
import os
import logging

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from strategy.ml_strategy import MLStrategy
from common.db_utils import DatabaseManager
from common.indicators import calculate_indicators

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def test_ml_strategy():
    logging.info("開始測試 ML 策略...")
    
    # 1. 載入資料
    db = DatabaseManager()
    df = db.fetch_kline_data('CL0000', 9, 365) # 恢復為 365 天
    
    if df.empty:
        logging.error("無資料")
        return
        
    logging.info(f"載入 {len(df)} 筆資料")
    
    # 2. 初始化策略
    # 啟用 backtest_mode 加速回測
    strategy = MLStrategy(strategy_id="ML_Test", config={
        'backtest_mode': True,
        'long_threshold': 0.5,
        'short_threshold': 0.5
    })
    strategy.on_init()
    
    if not strategy.feature_names:
        logging.error("策略未載入特徵名稱，無法進行回測")
        return

    # 3. 預計算指標 (向量化加速)
    logging.info("預計算技術指標...")
    df_indicators = calculate_indicators(df)
    
    # 4. 模擬資料流
    signal_count = 0
    total_bars = len(df)
    
    logging.info("開始回測迴圈...")
    for i, row in df.iterrows():
        # 模擬策略的熱機檢查 (跳過前 205 筆)
        if i < 205:
            strategy.update_bar({
                'date': row['date'],
                'close': row['close']
            })
            continue
            
        bar = {
            'date': row['date'],
            'open': row['open'],
            'high': row['high'],
            'low': row['low'],
            'close': row['close'],
            'volume': row['volume']
        }
        
        # 注入預計算的特徵
        # 注意：這裡使用 iloc[[i]] 保持 DataFrame 格式
        bar['features'] = df_indicators.iloc[[i]][strategy.feature_names]
        
        signal = strategy.on_bar(bar)
        
        if signal:
            signal_count += 1
            logging.info(f"[{row['date']}] 訊號: {signal}")
            
            # 模擬成交
            trade = {
                'action': signal['action'],
                'price': signal['price'],
                'quantity': signal['quantity'],
                'time': row['date']
            }
            strategy.on_fill(trade)
            
    logging.info(f"測試完成，共觸發 {signal_count} 次訊號")

if __name__ == "__main__":
    test_ml_strategy()
