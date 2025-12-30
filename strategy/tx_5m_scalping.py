import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
from strategy.base_strategy import BaseStrategy

class TX5mScalpingStrategy(BaseStrategy):
    """
    TX00 5m 逆勢剝頭皮策略 (ID: 24)
    利用布林帶與 RSI 捕捉極短線反轉。
    """
    
    def on_init(self):
        self.bb_period = int(self.config.get('bbPeriod', 20))
        self.bb_mult = float(self.config.get('bbMult', 2.0))
        self.rsi_period = int(self.config.get('rsiPeriod', 14))
        self.rsi_buy = float(self.config.get('rsiBuy', 30))
        self.rsi_sell = float(self.config.get('rsiSell', 70))
        self.stop_loss_points = float(self.config.get('stopLossPoints', 30.0)) # 固定點數止損
        self.trade_quantity = int(self.config.get('tradeQuantity', 1))
        
        self.min_history_len = self.bb_period + 20
        self.entry_price = 0.0
        
        self.logger.info(f"[{self.strategy_id}] 初始化 TX 5m Scalp: BB=({self.bb_period},{self.bb_mult}), RSI=({self.rsi_buy}/{self.rsi_sell})")

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
        
        # 1. 計算 BB
        bb_sma = closes.rolling(window=self.bb_period).mean()
        bb_std = closes.rolling(window=self.bb_period).std()
        bb_upper = bb_sma + (bb_std * self.bb_mult)
        bb_lower = bb_sma - (bb_std * self.bb_mult)
        
        # 2. 計算 RSI
        delta = closes.diff()
        gain = (delta.where(delta > 0, 0)).fillna(0)
        loss = (-delta.where(delta < 0, 0)).fillna(0)
        avg_gain = gain.rolling(window=self.rsi_period).mean()
        avg_loss = loss.rolling(window=self.rsi_period).mean()
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        # 數值
        c_close = closes.iloc[-1]
        c_bb_up = bb_upper.iloc[-1]
        c_bb_low = bb_lower.iloc[-1]
        c_bb_mid = bb_sma.iloc[-1]
        c_rsi = rsi.iloc[-1]
        
        if np.isnan(c_bb_up) or np.isnan(c_rsi): return None

        # 3. 檢查持倉
        if self.position != 0:
            if self.position > 0:
                # 止損
                if c_close <= self.entry_price - self.stop_loss_points:
                    return self._signal('SELL', 'Fixed Stop')
                # 獲利 (回歸中軌)
                if c_close >= c_bb_mid:
                    return self._signal('SELL', 'Touch Mean (TP)')
                    
            elif self.position < 0:
                # 止損
                if c_close >= self.entry_price + self.stop_loss_points:
                    return self._signal('BUY', 'Fixed Stop')
                # 獲利 (回歸中軌)
                if c_close <= c_bb_mid:
                    return self._signal('BUY', 'Touch Mean (TP)')
            return None

        # 4. 進場邏輯
        # 做多：跌破下軌 + RSI 超賣
        if c_close < c_bb_low and c_rsi < self.rsi_buy:
            self.entry_price = c_close
            return self._signal('BUY', 'Scalp Long')
            
        # 做空：突破上軌 + RSI 超買
        elif c_close > c_bb_up and c_rsi > self.rsi_sell:
            self.entry_price = c_close
            return self._signal('SELL', 'Scalp Short')
            
        return None

    def _signal(self, action, reason):
        price = float(self.history_df.iloc[-1]['close']) if isinstance(self.history_df.iloc[-1]['close'], (float, np.float64)) else float(self.history_df.iloc[-1]['close'].iloc[-1])
        return {
            'action': action,
            'quantity': self.trade_quantity,
            'price': price,
            'reason': reason
        }
