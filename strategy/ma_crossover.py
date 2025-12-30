from .base_strategy import BaseStrategy
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional

class MACrossoverStrategy(BaseStrategy):
    """
    簡單移動平均線交叉策略 (範例)
    
    邏輯：
    - 黃金交叉 (快線向上突破慢線) -> 做多
    - 死亡交叉 (快線向下突破慢線) -> 做空
    """
    
    def on_init(self):
        """初始化參數"""
        self.fast_window = self.config.get('fast_window', 10)
        self.slow_window = self.config.get('slow_window', 50)
        self.logger.info(f"[{self.strategy_id}] 初始化 MA 策略: 快線={self.fast_window}, 慢線={self.slow_window}")
        
    def on_bar(self, bar: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """K線更新邏輯"""
        # 1. 更新歷史資料緩存
        self.update_bar(bar)
        
        # 2. 檢查資料量是否足夠
        if len(self.klines) < self.slow_window + 1:
            return None
            
        # 3. 計算指標 (這裡為了示範簡單直接用 pandas，實盤建議優化效能)
        df = self.get_history_df()
        # 確保 close 是數值型別
        closes = pd.to_numeric(df['close'])
        
        # 計算當前與前一根的 MA
        ma_fast = closes.rolling(window=self.fast_window).mean()
        ma_slow = closes.rolling(window=self.slow_window).mean()
        
        curr_fast = ma_fast.iloc[-1]
        curr_slow = ma_slow.iloc[-1]
        prev_fast = ma_fast.iloc[-2]
        prev_slow = ma_slow.iloc[-2]
        
        current_price = bar['close']
        
        # 4. 產生訊號
        signal = None
        
        # 黃金交叉
        if prev_fast <= prev_slow and curr_fast > curr_slow:
            self.logger.info(f"[{self.strategy_id}] 黃金交叉! ({prev_fast:.2f}->{curr_fast:.2f} vs {prev_slow:.2f}->{curr_slow:.2f})")
            
            # 如果目前是空手或持有空單，則做多
            if self.position <= 0:
                # 如果有空單，先平倉再開多 (翻單)，或者只平倉
                # 這裡示範簡單邏輯：目標倉位變為 +1
                qty = 1 + abs(self.position) 
                signal = {
                    'action': 'BUY',
                    'quantity': 1, # 這裡簡化為每次交易 1 口
                    'price': current_price,
                    'reason': 'Golden Cross'
                }
                
        # 死亡交叉
        elif prev_fast >= prev_slow and curr_fast < curr_slow:
            self.logger.info(f"[{self.strategy_id}] 死亡交叉! ({prev_fast:.2f}->{curr_fast:.2f} vs {prev_slow:.2f}->{curr_slow:.2f})")
            
            # 如果目前是空手或持有多單，則做空
            if self.position >= 0:
                signal = {
                    'action': 'SELL',
                    'quantity': 1,
                    'price': current_price,
                    'reason': 'Death Cross'
                }
                
        return signal
