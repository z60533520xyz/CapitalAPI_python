import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
from strategy.base_strategy import BaseStrategy

class NQSuperTrendStrategy(BaseStrategy):
    """
    NQ0000 30m 超級趨勢狙擊策略 (ID: 19)
    目標：低回撤 (<5000)，高風報比 (>2.0)
    """
    
    def on_init(self):
        self.atr_period = int(self.config.get('atrPeriod', 10))
        self.multiplier = float(self.config.get('multiplier', 2.0)) # 緊密止損
        self.ema_period = int(self.config.get('emaPeriod', 200))
        self.trade_quantity = int(self.config.get('tradeQuantity', 1))
        
        # SuperTrend 狀態
        self.trend = 0 # 1 for Bull, -1 for Bear
        self.upper_band = 0.0
        self.lower_band = 0.0
        
        self.min_history_len = self.ema_period + 20
        self.logger.info(f"[{self.strategy_id}] 初始化 NQ SuperTrend: ATR={self.atr_period}, Mult={self.multiplier}")

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
        
        # 1. 計算 EMA
        ema = closes.ewm(span=self.ema_period, adjust=False).mean()
        
        # 2. 計算 ATR
        prev_close = closes.shift(1)
        tr = pd.concat([highs - lows, (highs - prev_close).abs(), (lows - prev_close).abs()], axis=1).max(axis=1)
        atr = tr.rolling(window=self.atr_period).mean()
        
        # 3. 計算 SuperTrend
        hl2 = (highs + lows) / 2
        
        # 為了避免重算整個 Series 導致效能問題，我們只計算最後幾根
        # 在此簡化，模擬逐根計算的邏輯
        c_close = closes.iloc[-1]
        c_atr = atr.iloc[-1]
        c_hl2 = hl2.iloc[-1]
        c_ema = ema.iloc[-1]
        
        if np.isnan(c_atr) or np.isnan(c_ema):
            return None

        # 計算當前的 Basic Bands
        basic_upper = c_hl2 + (self.multiplier * c_atr)
        basic_lower = c_hl2 - (self.multiplier * c_atr)
        
        # 初始化
        if self.upper_band == 0: self.upper_band = basic_upper
        if self.lower_band == 0: self.lower_band = basic_lower
        
        # 更新 Final Bands (遞迴邏輯)
        prev_close_val = closes.iloc[-2]
        
        if basic_upper < self.upper_band or prev_close_val > self.upper_band:
            self.upper_band = basic_upper
        
        if basic_lower > self.lower_band or prev_close_val < self.lower_band:
            self.lower_band = basic_lower
            
        # 判斷趨勢方向
        prev_trend = self.trend
        if c_close > self.upper_band:
            self.trend = 1
        elif c_close < self.lower_band:
            self.trend = -1
            
        # 4. 交易邏輯
        # 時間過濾: 台北 21:30 - 03:00 (美股核心時段)
        dt = pd.to_datetime(bar['date'])
        t_val = dt.hour + dt.minute/60.0
        is_active_time = (t_val >= 21.5 or t_val <= 3.0)
        
        # 平倉邏輯 (SuperTrend 轉向即平倉)
        if self.position > 0 and self.trend == -1:
            return self._signal('SELL', 'SuperTrend Flip Bear')
        elif self.position < 0 and self.trend == 1:
            return self._signal('BUY', 'SuperTrend Flip Bull')
            
        # 進場邏輯
        if is_active_time and self.position == 0:
            # 做多：SuperTrend 轉正 且 價格在 EMA 200 之上
            if self.trend == 1 and prev_trend == -1 and c_close > c_ema:
                return self._signal('BUY', 'SuperTrend Start Bull')
            # 做空：SuperTrend 轉負 且 價格在 EMA 200 之下
            elif self.trend == -1 and prev_trend == 1 and c_close < c_ema:
                return self._signal('SELL', 'SuperTrend Start Bear')
                
        return None

    def _signal(self, action, reason):
        price = float(self.history_df.iloc[-1]['close']) if isinstance(self.history_df.iloc[-1]['close'], (float, np.float64)) else float(self.history_df.iloc[-1]['close'].iloc[-1])
        return {
            'action': action,
            'quantity': self.trade_quantity,
            'price': price,
            'reason': reason
        }
