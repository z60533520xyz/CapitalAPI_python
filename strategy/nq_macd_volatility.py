import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
from strategy.base_strategy import BaseStrategy

class NQMacdVolatilityStrategy(BaseStrategy):
    """
    NQ0000 30m MACD 波動率自適應策略 (ID: 21)
    特點：利用 MACD 判斷趨勢，強制 1:2.5 盈虧比，嚴格控制單筆虧損。
    """
    
    def on_init(self):
        self.fast_period = int(self.config.get('fastPeriod', 12))
        self.slow_period = int(self.config.get('slowPeriod', 26))
        self.signal_period = int(self.config.get('signalPeriod', 9))
        self.ema_trend = int(self.config.get('emaTrend', 200))
        self.atr_period = int(self.config.get('atrPeriod', 14))
        
        # 風控參數
        self.risk_reward_ratio = float(self.config.get('rrRatio', 2.5)) # 賺賠比 2.5
        self.stop_atr_mult = float(self.config.get('stopAtrMult', 1.5)) # 止損 1.5 ATR (較緊)
        self.trade_quantity = int(self.config.get('tradeQuantity', 1))
        
        self.min_history_len = self.ema_trend + 20
        self.entry_price = 0.0
        self.sl_price = 0.0
        self.tp_price = 0.0
        
        self.logger.info(f"[{self.strategy_id}] 初始化 NQ MACD策略: RR={self.risk_reward_ratio}, Stop={self.stop_atr_mult}ATR")

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
        
        # 1. 計算 MACD
        exp1 = closes.ewm(span=self.fast_period, adjust=False).mean()
        exp2 = closes.ewm(span=self.slow_period, adjust=False).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=self.signal_period, adjust=False).mean()
        hist = macd - signal
        
        # 2. 計算 EMA 200 (趨勢濾網)
        ema200 = closes.ewm(span=self.ema_trend, adjust=False).mean()
        
        # 3. 計算 ATR
        prev_close = closes.shift(1)
        tr = pd.concat([highs - lows, (highs - prev_close).abs(), (lows - prev_close).abs()], axis=1).max(axis=1)
        atr = tr.rolling(window=self.atr_period).mean()
        
        # 當前數值
        c_close = closes.iloc[-1]
        c_macd = macd.iloc[-1]
        c_signal = signal.iloc[-1]
        c_ema = ema200.iloc[-1]
        c_atr = atr.iloc[-1]
        
        p_macd = macd.iloc[-2]
        p_signal = signal.iloc[-2]
        
        if np.isnan(c_ema) or np.isnan(c_atr):
            return None

        # 4. 檢查持倉與出場 (嚴格執行 TP/SL)
        if self.position != 0:
            if self.position > 0:
                if c_close <= self.sl_price:
                    return self._signal('SELL', 'Stop Loss')
                if c_close >= self.tp_price:
                    return self._signal('SELL', 'Take Profit')
            elif self.position < 0:
                if c_close >= self.sl_price:
                    return self._signal('BUY', 'Stop Loss')
                if c_close <= self.tp_price:
                    return self._signal('BUY', 'Take Profit')
            return None

        # 時間過濾 (21:30 - 03:00)
        dt = pd.to_datetime(bar['date'])
        time_val = dt.hour + dt.minute/60.0
        is_trade_time = (time_val >= 21.5 or time_val <= 3.0)
        
        if not is_trade_time:
            return None

        # 5. 進場邏輯
        # 多頭：價格 > EMA200 且 MACD 黃金交叉
        if c_close > c_ema and p_macd < p_signal and c_macd > c_signal:
            stop_dist = c_atr * self.stop_atr_mult
            
            # 風控：如果止損距離太大(波動過大)，放棄交易以保護本金
            if stop_dist > 150: # NQ 150點 = $3000 風險 (可調整)
                return None
                
            self.entry_price = c_close
            self.sl_price = c_close - stop_dist
            self.tp_price = c_close + (stop_dist * self.risk_reward_ratio)
            return self._signal('BUY', 'MACD Long')
            
        # 空頭：價格 < EMA200 且 MACD 死亡交叉
        elif c_close < c_ema and p_macd > p_signal and c_macd < c_signal:
            stop_dist = c_atr * self.stop_atr_mult
            
            if stop_dist > 150:
                return None
                
            self.entry_price = c_close
            self.sl_price = c_close + stop_dist
            self.tp_price = c_close - (stop_dist * self.risk_reward_ratio)
            return self._signal('SELL', 'MACD Short')
            
        return None

    def _signal(self, action, reason):
        price = float(self.history_df.iloc[-1]['close']) if isinstance(self.history_df.iloc[-1]['close'], (float, np.float64)) else float(self.history_df.iloc[-1]['close'].iloc[-1])
        return {
            'action': action,
            'quantity': self.trade_quantity,
            'price': price,
            'reason': reason
        }
