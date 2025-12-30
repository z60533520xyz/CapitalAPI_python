import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
from strategy.base_strategy import BaseStrategy

class CL5mScalpingStrategy(BaseStrategy):
    """
    CL0000 5m RSI 極限反轉策略 (ID: 26)
    利用 RSI(7) 超賣/超買進場，回歸中軸出場。
    """
    
    def on_init(self):
        self.rsi_period = int(self.config.get('rsiPeriod', 7))
        self.rsi_buy = float(self.config.get('rsiBuy', 20))
        self.rsi_sell = float(self.config.get('rsiSell', 80))
        self.trade_quantity = int(self.config.get('tradeQuantity', 1))
        
        self.min_history_len = self.rsi_period + 20
        self.entry_price = 0.0
        
        self.logger.info(f"[{self.strategy_id}] 初始化 CL 5m Scalp: RSI=({self.rsi_buy}/{self.rsi_sell})")

    def on_bar(self, bar: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        df = self.history_df
        if df.empty or len(df) < self.min_history_len:
            return None
            
        temp_df = df.copy()
        temp_df.columns = [c.lower() for c in temp_df.columns]
        
        def get_series(name):
            data = temp_df[name]
            return (data.iloc[:, -1] if isinstance(data, pd.DataFrame) else data).astype(np.float64)

        closes = get_series('close')
        
        # 1. 計算 RSI
        delta = closes.diff()
        gain = (delta.where(delta > 0, 0)).fillna(0)
        loss = (-delta.where(delta < 0, 0)).fillna(0)
        avg_gain = gain.rolling(window=self.rsi_period).mean()
        avg_loss = loss.rolling(window=self.rsi_period).mean()
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        c_rsi = rsi.iloc[-1]
        c_close = closes.iloc[-1]
        
        if np.isnan(c_rsi): return None

        # 2. 檢查持倉
        if self.position != 0:
            # 硬止損 (保護) - 例如 0.4 點 ($400)
            sl_dist = 0.4
            if self.position > 0:
                if c_close <= self.entry_price - sl_dist:
                    return self._signal('SELL', 'Hard Stop')
                if c_rsi >= 50: # 回歸中軸
                    return self._signal('SELL', 'RSI Mean')
            elif self.position < 0:
                if c_close >= self.entry_price + sl_dist:
                    return self._signal('BUY', 'Hard Stop')
                if c_rsi <= 50: # 回歸中軸
                    return self._signal('BUY', 'RSI Mean')
            return None

        # 3. 進場邏輯
        if c_rsi < self.rsi_buy:
            self.entry_price = c_close
            return self._signal('BUY', 'RSI Oversold')
        elif c_rsi > self.rsi_sell:
            self.entry_price = c_close
            return self._signal('SELL', 'RSI Overbought')
            
        return None

    def _signal(self, action, reason):
        price = float(self.history_df.iloc[-1]['close']) if isinstance(self.history_df.iloc[-1]['close'], (float, np.float64)) else float(self.history_df.iloc[-1]['close'].iloc[-1])
        return {
            'action': action,
            'quantity': self.trade_quantity,
            'price': price,
            'reason': reason
        }
