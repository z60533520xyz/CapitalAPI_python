import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
from strategy.base_strategy import BaseStrategy

class NQ5mScalpingStrategy(BaseStrategy):
    """
    NQ0000 5m 動能突破策略 (ID: 25)
    利用 Donchian Channel (20) 突破進場，固定點數停利。
    """
    
    def on_init(self):
        self.channel_period = int(self.config.get('channelPeriod', 20))
        self.tp_points = float(self.config.get('tpPoints', 40.0))
        self.sl_points = float(self.config.get('slPoints', 30.0))
        self.trade_quantity = int(self.config.get('tradeQuantity', 1))
        
        self.min_history_len = self.channel_period + 5
        self.entry_price = 0.0
        
        self.logger.info(f"[{self.strategy_id}] 初始化 NQ 5m Scalp: DC={self.channel_period}, TP={self.tp_points}, SL={self.sl_points}")

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
        highs = get_series('high')
        lows = get_series('low')
        
        # 1. 計算唐奇安通道 (不包含當前 K 線，避免未來函數)
        # rolling max of previous N bars
        highs_shifted = highs.shift(1)
        lows_shifted = lows.shift(1)
        
        dc_upper = highs_shifted.rolling(window=self.channel_period).max()
        dc_lower = lows_shifted.rolling(window=self.channel_period).min()
        
        c_close = closes.iloc[-1]
        c_upper = dc_upper.iloc[-1]
        c_lower = dc_lower.iloc[-1]
        
        if np.isnan(c_upper): return None

        # 2. 檢查持倉與出場
        if self.position != 0:
            if self.position > 0:
                # 停利
                if c_close >= self.entry_price + self.tp_points:
                    return self._signal('SELL', 'Fixed TP')
                # 停損
                if c_close <= self.entry_price - self.sl_points:
                    return self._signal('SELL', 'Fixed SL')
            elif self.position < 0:
                # 停利
                if c_close <= self.entry_price - self.tp_points:
                    return self._signal('BUY', 'Fixed TP')
                # 停損
                if c_close >= self.entry_price + self.sl_points:
                    return self._signal('BUY', 'Fixed SL')
            return None

        # 3. 進場邏輯
        # 突破上軌
        if c_close > c_upper:
            self.entry_price = c_close
            return self._signal('BUY', 'Donchian Breakout')
        # 跌破下軌
        elif c_close < c_lower:
            self.entry_price = c_close
            return self._signal('SELL', 'Donchian Breakout')
            
        return None

    def _signal(self, action, reason):
        price = float(self.history_df.iloc[-1]['close']) if isinstance(self.history_df.iloc[-1]['close'], (float, np.float64)) else float(self.history_df.iloc[-1]['close'].iloc[-1])
        return {
            'action': action,
            'quantity': self.trade_quantity,
            'price': price,
            'reason': reason
        }
