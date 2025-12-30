import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
from strategy.base_strategy import BaseStrategy

class CLRsiPullbackStrategy(BaseStrategy):
    """
    CL0000 30m RSI 極短線拉回策略 (ID: 17) - 優化版
    """
    
    def on_init(self):
        self.ema_period = int(self.config.get('emaPeriod', 80))
        self.rsi_period = int(self.config.get('rsiPeriod', 3))
        self.buy_threshold = float(self.config.get('buyThreshold', 15))
        self.sell_threshold = float(self.config.get('sellThreshold', 85))
        
        # 優化：放寬出場，讓利潤奔跑
        self.exit_long_rsi = float(self.config.get('exitLongRsi', 75)) # 70 -> 75
        self.exit_short_rsi = float(self.config.get('exitShortRsi', 25)) # 30 -> 25
        
        # 優化：稍微放寬停損
        self.stop_loss_pct = float(self.config.get('stopLossPercent', 0.01)) # 0.8% -> 1.0%
        self.trade_quantity = int(self.config.get('tradeQuantity', 1))
        
        self.min_history_len = self.ema_period + 20
        self.logger.info(f"[{self.strategy_id}] 初始化 CL RSI拉回 V2: RSI={self.rsi_period}")

    def on_bar(self, bar: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        df = self.history_df
        if df.empty or len(df) < self.min_history_len:
            return None
            
        temp_df = df.copy()
        temp_df.columns = [c.lower() for c in temp_df.columns]
        
        # 處理重複欄位
        closes_data = temp_df['close']
        closes = (closes_data.iloc[:, -1] if isinstance(closes_data, pd.DataFrame) else closes_data).astype(np.float64)
        
        # 1. 計算指標
        ema = closes.ewm(span=self.ema_period, adjust=False).mean()
        
        delta = closes.diff()
        gain = (delta.where(delta > 0, 0)).fillna(0)
        loss = (-delta.where(delta < 0, 0)).fillna(0)
        avg_gain = gain.rolling(window=self.rsi_period).mean()
        avg_loss = loss.rolling(window=self.rsi_period).mean()
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        curr_close = float(closes.iloc[-1])
        curr_ema = float(ema.iloc[-1])
        curr_rsi = float(rsi.iloc[-1])
        
        if np.isnan(curr_ema) or np.isnan(curr_rsi):
            return None

        # 2. 檢查持倉與出場
        if self.position != 0:
            entry_price = self.avg_cost
            
            if self.position > 0: # 多單
                if curr_close < entry_price * (1 - self.stop_loss_pct):
                    return self._signal('SELL', 'Stop Loss')
                if curr_rsi > self.exit_long_rsi:
                    return self._signal('SELL', 'RSI Profit')
                    
            elif self.position < 0: # 空單
                if curr_close > entry_price * (1 + self.stop_loss_pct):
                    return self._signal('BUY', 'Stop Loss')
                if curr_rsi < self.exit_short_rsi:
                    return self._signal('BUY', 'RSI Profit')
            return None

        # 3. 進場邏輯
        if curr_close > curr_ema and curr_rsi < self.buy_threshold:
            return self._signal('BUY', 'RSI Pullback Long')
            
        if curr_close < curr_ema and curr_rsi > self.sell_threshold:
            return self._signal('SELL', 'RSI Pullback Short')
            
        return None

    def _signal(self, action, reason):
        price = float(self.history_df.iloc[-1]['close']) if isinstance(self.history_df.iloc[-1]['close'], (float, np.float64)) else float(self.history_df.iloc[-1]['close'].iloc[-1])
        return {
            'action': action,
            'quantity': self.trade_quantity,
            'price': price,
            'reason': reason
        }
