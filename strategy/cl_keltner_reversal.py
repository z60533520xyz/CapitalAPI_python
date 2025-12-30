import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
from strategy.base_strategy import BaseStrategy

class CLKeltnerReversalStrategy(BaseStrategy):
    """
    CL0000 30m 肯特納通道反轉策略 (ID: 20)
    目標：抓取極端乖離後的均值回歸。
    """
    
    def on_init(self):
        self.kc_period = int(self.config.get('kcPeriod', 20))
        self.kc_mult = float(self.config.get('kcMult', 2.2)) # 較寬，確認極端
        self.atr_period = int(self.config.get('atrPeriod', 14))
        self.stop_atr_mult = float(self.config.get('stopAtrMult', 1.0)) # 極窄止損
        self.trade_quantity = int(self.config.get('tradeQuantity', 1))
        
        self.min_history_len = self.kc_period + 20
        self.trailing_stop = 0.0
        
        self.logger.info(f"[{self.strategy_id}] 初始化 CL Keltner Reversal: KC={self.kc_mult}, Stop={self.stop_atr_mult}")

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
        
        # 1. 計算 KC
        prev_close = closes.shift(1)
        tr = pd.concat([highs - lows, (highs - prev_close).abs(), (lows - prev_close).abs()], axis=1).max(axis=1)
        atr = tr.rolling(window=self.atr_period).mean()
        
        kc_sma = closes.rolling(window=self.kc_period).mean()
        kc_upper = kc_sma + (atr * self.kc_mult)
        kc_lower = kc_sma - (atr * self.kc_mult)
        
        # 當前與前一根
        c_close = closes.iloc[-1]
        c_high = highs.iloc[-1]
        c_low = lows.iloc[-1]
        c_atr = atr.iloc[-1]
        c_upper = kc_upper.iloc[-1]
        c_lower = kc_lower.iloc[-1]
        
        p_close = closes.iloc[-2]
        p_upper = kc_upper.iloc[-2]
        p_lower = kc_lower.iloc[-2]
        
        if np.isnan(c_upper): return None

        # 2. 檢查持倉
        if self.position != 0:
            # 硬止損
            if self.position > 0 and c_close < self.trailing_stop:
                return self._signal('SELL', 'Hard Stop')
            elif self.position < 0 and c_close > self.trailing_stop:
                return self._signal('BUY', 'Hard Stop')
                
            # 回歸中軸停利 (SMA)
            c_sma = kc_sma.iloc[-1]
            if self.position > 0 and c_close >= c_sma:
                return self._signal('SELL', 'Touch Mean (TP)')
            elif self.position < 0 and c_close <= c_sma:
                return self._signal('BUY', 'Touch Mean (TP)')
            return None

        # 3. 進場邏輯 (反轉)
        # 做空：前一根收在通道外，當前根收回通道內
        if p_close > p_upper and c_close < c_upper:
            self.trailing_stop = c_high + (c_atr * 0.5) # 止損設在當前K線高點上方一點點
            return self._signal('SELL', 'Reversion Short')
            
        # 做多：前一根收在通道外，當前根收回通道內
        if p_close < p_lower and c_close > c_lower:
            self.trailing_stop = c_low - (c_atr * 0.5) # 止損設在當前K線低點下方一點點
            return self._signal('BUY', 'Reversion Long')
            
        return None

    def _signal(self, action, reason):
        price = float(self.history_df.iloc[-1]['close']) if isinstance(self.history_df.iloc[-1]['close'], (float, np.float64)) else float(self.history_df.iloc[-1]['close'].iloc[-1])
        return {
            'action': action,
            'quantity': self.trade_quantity,
            'price': price,
            'reason': reason
        }
