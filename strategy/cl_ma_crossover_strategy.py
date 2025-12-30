import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
from strategy.base_strategy import BaseStrategy

class CLMACrossoverStrategy(BaseStrategy):
    """
    CL0000 雙移動平均線交叉策略 (ID: 14)
    參數：Fast=10, Slow=40 (穩健型趨勢配置)
    """
    
    def on_init(self):
        """初始化參數"""
        self.fast_window = int(self.config.get('fast_window', 10)) # 改為 10
        self.slow_window = int(self.config.get('slow_window', 40)) # 改為 40
        self.stop_loss_pct = float(self.config.get('stopLossPercent', 0.01))
        self.trade_quantity = int(self.config.get('tradeQuantity', 1))
        
        self.logger.info(f"[{self.strategy_id}] 初始化 CLMA 策略: 快線={self.fast_window}, 慢線={self.slow_window}, 停損={self.stop_loss_pct*100}%")
        
    def on_bar(self, bar: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """K線更新邏輯"""
        if len(self.history_df) < self.slow_window + 1:
            return None
            
        df = self.history_df
        
        # 統一轉小寫以防萬一
        temp_df = df.copy()
        temp_df.columns = [c.lower() for c in temp_df.columns]
        
        # 處理重複欄位
        closes_data = temp_df['close']
        closes = (closes_data.iloc[:, -1] if isinstance(closes_data, pd.DataFrame) else closes_data).astype(float)
        
        ma_fast = closes.rolling(window=self.fast_window).mean()
        ma_slow = closes.rolling(window=self.slow_window).mean()
        
        curr_fast = ma_fast.iloc[-1]
        curr_slow = ma_slow.iloc[-1]
        prev_fast = ma_fast.iloc[-2]
        prev_slow = ma_slow.iloc[-2]
        
        current_price = float(bar['close'])
        high = float(bar['high'])
        low = float(bar['low'])
        
        # 檢查持倉狀態 (先處理停損)
        if self.position != 0:
            entry_price = self.avg_cost
            stop_price = 0.0
            if self.position > 0:
                stop_price = entry_price * (1 - self.stop_loss_pct)
                if low <= stop_price:
                    return {'action': 'SELL', 'quantity': abs(self.position), 'price': stop_price, 'reason': 'Stop Loss'}
            else:
                stop_price = entry_price * (1 + self.stop_loss_pct)
                if high >= stop_price:
                    return {'action': 'BUY', 'quantity': abs(self.position), 'price': stop_price, 'reason': 'Stop Loss'}
        
        # 產生進場/反手訊號
        signal = None
        
        # 黃金交叉
        if prev_fast <= prev_slow and curr_fast > curr_slow:
            if self.position <= 0:
                qty = self.trade_quantity + (abs(self.position) if self.position < 0 else 0)
                signal = {'action': 'BUY', 'quantity': qty, 'price': current_price, 'reason': 'Golden Cross'}
                
        # 死亡交叉
        elif prev_fast >= prev_slow and curr_fast < curr_slow:
            if self.position >= 0:
                qty = self.trade_quantity + (abs(self.position) if self.position > 0 else 0)
                signal = {'action': 'SELL', 'quantity': qty, 'price': current_price, 'reason': 'Death Cross'}
                
        return signal

    def on_fill(self, trade_report: Dict[str, Any]):
        super().on_fill(trade_report)