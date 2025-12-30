import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
from strategy.base_strategy import BaseStrategy

class NQSqueezeMomentumStrategy(BaseStrategy):
    """
    NQ0000 30m 擠壓突破策略 (ID: 18) - 優化版
    加入 EMA 趨勢過濾與時間過濾，大幅提高勝率與降低回撤。
    """
    
    def on_init(self):
        self.bb_period = int(self.config.get('bbPeriod', 20))
        self.bb_mult = float(self.config.get('bbMult', 2.0))
        self.kc_period = int(self.config.get('kcPeriod', 20))
        self.kc_mult = float(self.config.get('kcMult', 1.5))
        self.atr_period = int(self.config.get('atrPeriod', 14))
        self.stop_atr_mult = float(self.config.get('stopAtrMult', 4.0)) # 放寬止損
        self.ema_filter_period = int(self.config.get('emaFilter', 50)) # 新增趨勢過濾
        self.trade_quantity = int(self.config.get('tradeQuantity', 1))
        
        self.min_history_len = max(self.bb_period, self.ema_filter_period) + 10
        self.trailing_stop = 0.0
        
        self.logger.info(f"[{self.strategy_id}] 初始化 NQ Squeeze V2: ATR_Stop={self.stop_atr_mult}, EMA_Filter={self.ema_filter_period}")

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
        
        # 1. 計算指標
        bb_sma = closes.rolling(window=self.bb_period).mean()
        bb_std = closes.rolling(window=self.bb_period).std()
        bb_upper = bb_sma + (bb_std * self.bb_mult)
        bb_lower = bb_sma - (bb_std * self.bb_mult)
        
        prev_close = closes.shift(1)
        tr = pd.concat([highs - lows, (highs - prev_close).abs(), (lows - prev_close).abs()], axis=1).max(axis=1)
        atr = tr.rolling(window=self.atr_period).mean()
        
        kc_sma = closes.rolling(window=self.kc_period).mean()
        kc_upper = kc_sma + (atr * self.kc_mult)
        kc_lower = kc_sma - (atr * self.kc_mult)
        
        ema_trend = closes.ewm(span=self.ema_filter_period, adjust=False).mean()
        
        c_close = closes.iloc[-1]
        c_bb_up = bb_upper.iloc[-1]
        c_bb_low = bb_lower.iloc[-1]
        c_kc_up = kc_upper.iloc[-1]
        c_kc_low = kc_lower.iloc[-1]
        c_atr = atr.iloc[-1]
        c_ema = ema_trend.iloc[-1]
        
        if np.isnan(c_bb_up) or np.isnan(c_ema):
            return None

        # 時間過濾 (台北 21:30 - 04:00)
        dt = pd.to_datetime(bar['date'])
        time_val = dt.hour + dt.minute/60.0
        is_trade_time = (time_val >= 21.5 or time_val <= 4.0)

        # 3. 檢查持倉
        if self.position != 0:
            if self.position > 0:
                new_stop = c_close - (c_atr * self.stop_atr_mult)
                self.trailing_stop = max(self.trailing_stop, new_stop)
                if c_close < self.trailing_stop:
                    return self._signal('SELL', 'ATR Stop')
            else:
                new_stop = c_close + (c_atr * self.stop_atr_mult)
                self.trailing_stop = min(self.trailing_stop, new_stop) if self.trailing_stop > 0 else new_stop
                if c_close > self.trailing_stop:
                    return self._signal('BUY', 'ATR Stop')
            return None

        # 4. 進場邏輯
        if not is_trade_time:
            return None
            
        expanded = (c_bb_up > c_kc_up) 
        
        if expanded:
            # 只做順勢單
            if c_close > c_bb_up and c_close > c_ema: # 價格在均線之上 + 向上突破
                self.trailing_stop = c_close - (c_atr * self.stop_atr_mult)
                return self._signal('BUY', 'Squeeze Long')
            elif c_close < c_bb_low and c_close < c_ema: # 價格在均線之下 + 向下突破
                self.trailing_stop = c_close + (c_atr * self.stop_atr_mult)
                return self._signal('SELL', 'Squeeze Short')
                
        return None

    def _signal(self, action, reason):
        price = float(self.history_df.iloc[-1]['close']) if isinstance(self.history_df.iloc[-1]['close'], (float, np.float64)) else float(self.history_df.iloc[-1]['close'].iloc[-1])
        return {
            'action': action,
            'quantity': self.trade_quantity,
            'price': price,
            'reason': reason
        }
