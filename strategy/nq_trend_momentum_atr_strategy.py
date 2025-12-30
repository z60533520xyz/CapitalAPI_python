import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
from strategy.base_strategy import BaseStrategy

class NQTrendMomentumATRStrategy(BaseStrategy):
    """
    優化版 NQ0000 趨勢拉回策略 (ID: 15) - 實盤部署版
    參數：
    - FastEMA: 50
    - SlowEMA: 200
    - ATR Period: 14
    - ATR Multiplier: 4.0 (最佳化參數)
    - 時段: 台北時間 21:30 - 02:00
    """
    
    def on_init(self):
        """初始化策略參數"""
        self.fast_ema_period = int(self.config.get('fastEma', 50))
        self.slow_ema_period = int(self.config.get('slowEma', 200))
        self.atr_period = int(self.config.get('atrPeriod', 14))
        self.atr_multiplier = float(self.config.get('atrMultiplier', 4.0)) # 鎖定為 4.0
        self.trade_quantity = int(self.config.get('tradeQuantity', 1))
        
        self.min_history_len = self.slow_ema_period + 10
        self.trailing_stop_price = 0.0
        self.pullback_occurred = False
        
        self.logger.info(f"[{self.strategy_id}] 初始化 NQ 實盤策略: ATR_Mult={self.atr_multiplier}")

    def on_bar(self, bar: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """K線更新邏輯"""
        df = self.history_df
        if df.empty or len(df) < self.min_history_len:
            return None
            
        temp_df = df.copy()
        temp_df.columns = [c.lower() for c in temp_df.columns]
        
        def get_series(name):
            data = temp_df[name]
            return data.iloc[:, -1] if isinstance(data, pd.DataFrame) else data

        closes = get_series('close').astype(np.float64)
        highs = get_series('high').astype(np.float64)
        lows = get_series('low').astype(np.float64)
        
        ema_fast = closes.ewm(span=self.fast_ema_period, adjust=False).mean()
        ema_slow = closes.ewm(span=self.slow_ema_period, adjust=False).mean()
        
        tr = pd.concat([
            highs - lows,
            (highs - closes.shift(1)).abs(),
            (lows - closes.shift(1)).abs()
        ], axis=1).max(axis=1)
        atr = tr.rolling(window=self.atr_period).mean()
        
        c_close = closes.iloc[-1]
        c_low = lows.iloc[-1]
        c_high = highs.iloc[-1]
        c_ema_f = ema_fast.iloc[-1]
        c_ema_s = ema_slow.iloc[-1]
        c_atr = atr.iloc[-1]
        
        p_close = closes.iloc[-2]
        p_ema_f = ema_fast.iloc[-2]
        
        if np.isnan(c_ema_f) or np.isnan(c_ema_s) or np.isnan(c_atr):
            return None

        # --- 精確時間過濾 (台北時間 21:30 - 02:00) ---
        dt = pd.to_datetime(bar['date'])
        time_val = dt.hour + dt.minute/60.0
        # 允許開倉時段：21:30 ~ 02:00
        # 注意：持倉後的平倉邏輯不受此限，但新單進場受此限
        is_trade_time = (time_val >= 21.5 or time_val <= 2.0)

        # 檢查持倉
        if self.position != 0:
            self.pullback_occurred = False
            # 移動止損邏輯
            if self.position > 0:
                new_stop = c_close - (c_atr * self.atr_multiplier)
                self.trailing_stop_price = max(self.trailing_stop_price, new_stop)
                if c_close < self.trailing_stop_price:
                    return self._create_signal('SELL', abs(self.position), c_close, f"ATR Stop Long @ {self.trailing_stop_price:.2f}")
            else:
                new_stop = c_close + (c_atr * self.atr_multiplier)
                self.trailing_stop_price = min(self.trailing_stop_price, new_stop) if self.trailing_stop_price > 0 else new_stop
                if c_close > self.trailing_stop_price:
                    return self._create_signal('BUY', abs(self.position), c_close, f"ATR Stop Short @ {self.trailing_stop_price:.2f}")
            return None

        # 進場邏輯
        if not is_trade_time:
            self.pullback_occurred = False
            return None
            
        # 1. 多頭市場 (EMA 50 > EMA 200)
        if c_ema_f > c_ema_s:
            if c_low < c_ema_f: # 拉回
                self.pullback_occurred = True
            if self.pullback_occurred and c_close > c_ema_f and p_close <= p_ema_f:
                self.trailing_stop_price = c_close - (c_atr * self.atr_multiplier)
                self.pullback_occurred = False
                return self._create_signal('BUY', self.trade_quantity, c_close, 'Pullback Long')
                
        # 2. 空頭市場 (EMA 50 < EMA 200)
        elif c_ema_f < c_ema_s:
            if c_high > c_ema_f: # 反彈
                self.pullback_occurred = True
            if self.pullback_occurred and c_close < c_ema_f and p_close >= p_ema_f:
                self.trailing_stop_price = c_close + (c_atr * self.atr_multiplier)
                self.pullback_occurred = False
                return self._create_signal('SELL', self.trade_quantity, c_close, 'Pullback Short')
            
        return None

    def _create_signal(self, action, qty, price, reason):
        return {'action': action, 'quantity': qty, 'price': price, 'reason': reason}