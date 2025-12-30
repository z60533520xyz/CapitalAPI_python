import pandas as pd
from typing import Dict, Any
from strategy.base_strategy import BaseStrategy
from common.indicators import calculate_indicators

class SqueezeBreakoutOptimizedStrategy(BaseStrategy):
    """
    擠壓突破優化策略 (對應 C# ID 12)
    """
    def __init__(self, strategy_id: str, config: Dict[str, Any]):
        super().__init__(strategy_id, config)
        self.stop_loss_pct = float(config.get('stopLossPercent', 0.01))
        self.take_profit_pct = float(config.get('takeProfitPercent', 0.02))
        self.trailing_stop_pct = float(config.get('trailingStopPercent', 0.005))
        
        # 參數
        self.bb_period = int(config.get('bbPeriod', 20))
        self.bb_multiplier = float(config.get('bbMultiplier', 2.0))
        self.kc_period = int(config.get('kcPeriod', 20))
        self.kc_multiplier = float(config.get('kcMultiplier', 2.0))
        
        self.history_df = pd.DataFrame()
        self.min_history_len = max(self.bb_period, self.kc_period) + 10
        
        # 記錄進場後的最高/最低價 (用於移動停利)
        self.highest_high = 0.0
        self.lowest_low = float('inf')

    def on_init(self):
        self.logger.info(f"策略 {self.strategy_id} 初始化完成")

    def on_bar(self, bar: Dict[str, Any]) -> Dict[str, Any]:
        self.update_history(bar)
        
        if len(self.history_df) < self.min_history_len:
            return None
            
        # 計算指標
        df = self.history_df.copy()
        df = calculate_indicators(df, 
                                  bb_period=self.bb_period, 
                                  kc_period=self.kc_period, 
                                  kc_multiplier=self.kc_multiplier)
        
        # 確保在計算指標後仍有足夠的數據
        if len(df) < 2:
            return None
            
        current_bar = df.iloc[-1]
        prev_bar = df.iloc[-2]
        close = current_bar['Close']
        high = current_bar['High']
        low = current_bar['Low']
        
        # 擠壓條件 (前一根 K 線)
        squeeze_on = (prev_bar['BB_Upper'] < prev_bar['KC_Upper']) and \
                     (prev_bar['BB_Lower'] > prev_bar['KC_Lower'])
                     
        if self.config.get('debug', False) and squeeze_on:
             print(f"[{bar['date']}] Squeeze ON! BB: {prev_bar['BB_Upper']:.2f}/{prev_bar['BB_Lower']:.2f}, KC: {prev_bar['KC_Upper']:.2f}/{prev_bar['KC_Lower']:.2f}")

        # 買入/賣出訊號
        buy_signal = squeeze_on and (close > current_bar['KC_Upper'])
        sell_signal = squeeze_on and (close < current_bar['KC_Lower'])
        
        # 檢查持倉狀態
        if self.position != 0:
            entry_price = self.avg_cost
            pnl_pct = 0
            
            # 更新最高/最低價
            if self.position > 0:
                self.highest_high = max(self.highest_high, high)
                pnl_pct = (close - entry_price) / entry_price
            else:
                self.lowest_low = min(self.lowest_low, low)
                pnl_pct = (entry_price - close) / entry_price
            
            # 1. 停利
            if self.take_profit_pct > 0 and pnl_pct >= self.take_profit_pct:
                return self._create_signal('SELL' if self.position > 0 else 'BUY', abs(self.position), close, "Take Profit")
                
            # 2. 停損
            if self.stop_loss_pct > 0 and pnl_pct <= -self.stop_loss_pct:
                return self._create_signal('SELL' if self.position > 0 else 'BUY', abs(self.position), close, "Stop Loss")
                
            # 3. 移動停利
            if self.trailing_stop_pct > 0:
                if self.position > 0:
                    trailing_stop_price = self.highest_high * (1 - self.trailing_stop_pct)
                    if low <= trailing_stop_price:
                        return self._create_signal('SELL', abs(self.position), trailing_stop_price, "Trailing Stop")
                else:
                    trailing_stop_price = self.lowest_low * (1 + self.trailing_stop_pct)
                    if high >= trailing_stop_price:
                        return self._create_signal('BUY', abs(self.position), trailing_stop_price, "Trailing Stop")
            
            # 4. 反手訊號
            if self.position > 0 and sell_signal:
                return self._create_signal('SELL', abs(self.position) * 2, close, "Reverse to Short")
            elif self.position < 0 and buy_signal:
                return self._create_signal('BUY', abs(self.position) * 2, close, "Reverse to Long")
                
        else:
            # 無持倉，檢查進場
            if buy_signal:
                return self._create_signal('BUY', 1, close, "Strategy Buy")
            elif sell_signal:
                return self._create_signal('SELL', 1, close, "Strategy Sell")
                
        return None

    def on_fill(self, trade_report: Dict[str, Any]):
        """成交回報，重置狀態"""
        super().on_fill(trade_report)
        # 重置最高/最低價
        if self.position > 0:
            self.highest_high = trade_report['price']
            self.lowest_low = float('inf')
        elif self.position < 0:
            self.highest_high = 0.0
            self.lowest_low = trade_report['price']
        else:
            self.highest_high = 0.0
            self.lowest_low = float('inf')

    def update_history(self, bar: Dict[str, Any]):
        """更新歷史 DataFrame"""
        new_row = pd.DataFrame([bar])
        self.history_df = pd.concat([self.history_df, new_row], ignore_index=True)
        if len(self.history_df) > 200:
            self.history_df = self.history_df.iloc[-200:]

    def _create_signal(self, action, qty, price, reason):
        return {
            'action': action,
            'quantity': qty,
            'price': price,
            'reason': reason
        }
