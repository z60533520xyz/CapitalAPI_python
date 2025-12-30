import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
from strategy.base_strategy import BaseStrategy

class TXTrendSqueezeStrategy(BaseStrategy):
    """
    TX00 60m 肯特納通道突破策略 (ID: 23) - 修改版
    
    邏輯：
    1. 趨勢確認：ADX > 20
    2. 進場：突破 Keltner Channel 上緣/下緣
    3. 出場：跌破/突破 中軌 (EMA)
    """
    
    def on_init(self):
        self.kc_period = int(self.config.get('kcPeriod', 20))
        self.kc_mult = float(self.config.get('kcMult', 1.5))
        self.atr_period = int(self.config.get('atrPeriod', 14))
        self.adx_period = int(self.config.get('adxPeriod', 14))
        self.trade_quantity = int(self.config.get('tradeQuantity', 1))
        
        self.min_history_len = max(self.kc_period, self.adx_period) + 20
        self.trailing_stop = 0.0
        
        self.logger.info(f"[{self.strategy_id}] 初始化 TX Keltner: KC={self.kc_mult}, ADX={self.adx_period}")

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
        
        kc_ema = closes.ewm(span=self.kc_period, adjust=False).mean()
        kc_upper = kc_ema + (atr * self.kc_mult)
        kc_lower = kc_ema - (atr * self.kc_mult)
        
        # 2. 計算 ADX
        up = highs - highs.shift(1)
        down = lows.shift(1) - lows
        plus_dm = np.where((up > down) & (up > 0), up, 0.0)
        minus_dm = np.where((down > up) & (down > 0), down, 0.0)
        
        tr_adx = tr.rolling(window=self.adx_period).mean()
        plus_di = 100 * (pd.Series(plus_dm).rolling(window=self.adx_period).mean() / tr_adx)
        minus_di = 100 * (pd.Series(minus_dm).rolling(window=self.adx_period).mean() / tr_adx)
        dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
        adx = dx.rolling(window=self.adx_period).mean()
        
        # 數值
        c_close = closes.iloc[-1]
        c_upper = kc_upper.iloc[-1]
        c_lower = kc_lower.iloc[-1]
        c_ema = kc_ema.iloc[-1]
        c_adx = adx.iloc[-1]
        
        p_close = closes.iloc[-2]
        p_upper = kc_upper.iloc[-2]
        p_lower = kc_lower.iloc[-2]
        
        if np.isnan(c_adx) or np.isnan(c_upper): return None

        # 3. 檢查持倉
        if self.position != 0:
            # 中軌出場
            if self.position > 0 and c_close < c_ema:
                return self._signal('SELL', 'Touch Mean')
            elif self.position < 0 and c_close > c_ema:
                return self._signal('BUY', 'Touch Mean')
            return None

        # 4. 進場邏輯
        # 趨勢強度濾網
        if c_adx < 20: return None
        
        # 突破進場
        if c_close > c_upper and p_close <= p_upper:
            return self._signal('BUY', 'KC Breakout')
        elif c_close < c_lower and p_close >= p_lower:
            return self._signal('SELL', 'KC Breakout')
            
        return None

    def _signal(self, action, reason):
        price = float(self.history_df.iloc[-1]['close']) if isinstance(self.history_df.iloc[-1]['close'], (float, np.float64)) else float(self.history_df.iloc[-1]['close'].iloc[-1])
        return {
            'action': action,
            'quantity': self.trade_quantity,
            'price': price,
            'reason': reason
        }