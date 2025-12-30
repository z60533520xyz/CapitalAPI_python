import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
from strategy.base_strategy import BaseStrategy

class DailyRangeReversalStrategy(BaseStrategy):
    """
    CL0000 日內區間反轉策略 (ID: 27)
    
    邏輯：基於使用者觀察 CL 日內波動約 $1.0 的特性。
    當價格偏離當日開盤價接近 $1.0 時，進行反向操作。
    """
    
    def on_init(self):
        self.range_threshold = float(self.config.get('rangeThreshold', 0.9)) # 觸發反轉的距離 (例如 0.9)
        self.stop_buffer = float(self.config.get('stopBuffer', 0.3))         # 停損緩衝 (例如 1.0 + 0.3 = 1.3 停損)
        self.profit_target = float(self.config.get('profitTarget', 0.4))     # 獲利目標 (回調 0.4)
        self.rsi_period = int(self.config.get('rsiPeriod', 14))
        self.trade_quantity = int(self.config.get('tradeQuantity', 1))
        
        self.min_history_len = self.rsi_period + 10
        self.daily_open_price = None
        self.current_date = None
        self.entry_price = 0.0
        
        self.logger.info(f"[{self.strategy_id}] 初始化 CL Range Fade: Range={self.range_threshold}, Stop=Range+{self.stop_buffer}")

    def on_bar(self, bar: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        df = self.history_df
        if df.empty or len(df) < self.min_history_len:
            return None
            
        # 1. 取得當前 K 線資訊
        # bar['date'] 格式通常為 'YYYY-MM-DD HH:MM:SS'
        # 我們需要偵測日期變更來重置 Daily Open
        bar_date = pd.to_datetime(bar['date']).date()
        c_open = float(bar['open'])
        c_close = float(bar['close'])
        
        # 每日開盤重置
        if self.current_date != bar_date:
            self.current_date = bar_date
            self.daily_open_price = c_open # 將當日第一根 K 的 Open 視為當日開盤價
            # 日期變更時，若有持倉建議強平 (當沖策略不留倉)，但在回測框架簡單起見先不強制
            
        if self.daily_open_price is None:
            return None

        # 2. 計算 RSI (輔助濾網)
        closes = df['close'].astype(float)
        delta = closes.diff()
        gain = (delta.where(delta > 0, 0)).fillna(0)
        loss = (-delta.where(delta < 0, 0)).fillna(0)
        avg_gain = gain.rolling(window=self.rsi_period).mean()
        avg_loss = loss.rolling(window=self.rsi_period).mean()
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        c_rsi = rsi.iloc[-1]
        
        if np.isnan(c_rsi): return None

        # 3. 計算與開盤價的距離
        dist = c_close - self.daily_open_price
        
        # 4. 檢查持倉與出場
        if self.position != 0:
            if self.position > 0: # 做多中
                # 停損：價格跌破 (開盤 - 1.0 - 緩衝)
                stop_price = self.daily_open_price - self.range_threshold - self.stop_buffer
                # 停利：價格回升到進場點 + 目標
                target_price = self.entry_price + self.profit_target
                
                if c_close <= stop_price:
                    return self._signal('SELL', 'Range Breakout Stop') # 趨勢太強，認賠
                if c_close >= target_price:
                    return self._signal('SELL', 'Range Revert TP')
                    
            elif self.position < 0: # 做空中
                # 停損：價格突破 (開盤 + 1.0 + 緩衝)
                stop_price = self.daily_open_price + self.range_threshold + self.stop_buffer
                # 停利
                target_price = self.entry_price - self.profit_target
                
                if c_close >= stop_price:
                    return self._signal('BUY', 'Range Breakout Stop')
                if c_close <= target_price:
                    return self._signal('BUY', 'Range Revert TP')
            
            # 日內強平：如果接近收盤 (例如 04:45)，強制平倉 (這裡簡化，不實作複雜時間判斷)
            return None

        # 5. 進場邏輯 (逆勢)
        # 做空：價格 > 開盤 + 0.9 且 RSI 超買 (>65)
        if dist > self.range_threshold and c_rsi > 65:
            self.entry_price = c_close
            return self._signal('SELL', 'Fade High')
            
        # 做多：價格 < 開盤 - 0.9 且 RSI 超賣 (<35)
        elif dist < -self.range_threshold and c_rsi < 35:
            self.entry_price = c_close
            return self._signal('BUY', 'Fade Low')
            
        return None

    def _signal(self, action, reason):
        price = float(self.history_df.iloc[-1]['close']) if isinstance(self.history_df.iloc[-1]['close'], (float, np.float64)) else float(self.history_df.iloc[-1]['close'].iloc[-1])
        return {
            'action': action,
            'quantity': self.trade_quantity,
            'price': price,
            'reason': reason
        }
