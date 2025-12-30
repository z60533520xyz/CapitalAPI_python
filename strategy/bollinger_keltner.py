import pandas as pd
from typing import Dict, Any
from strategy.base_strategy import BaseStrategy
from common.indicators import calculate_indicators

class BollingerKeltnerStrategy(BaseStrategy):
    """
    布林通道 + 肯納特通道策略 (對應 C# ID 2)
    """
    def __init__(self, strategy_id: str, config: Dict[str, Any]):
        super().__init__(strategy_id, config)
        self.stop_loss_pct = float(config.get('stopLossPercent', 0.01))
        self.take_profit_pct = float(config.get('takeProfitPercent', 0.02))
        
        # 參數
        self.bb_period = int(config.get('bbPeriod', 20))
        self.bb_multiplier = float(config.get('bbMultiplier', 2.0))
        self.kc_period = int(config.get('kcPeriod', 20))
        self.kc_multiplier = float(config.get('kcMultiplier', 2.0))
        
        self.history_df = pd.DataFrame()
        self.min_history_len = max(self.bb_period, self.kc_period) + 10

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
        
        current_bar = df.iloc[-1]
        close = current_bar['Close']
        
        # 買入條件: 收盤價突破布林上軌和 KC 上軌
        buy_signal = (close > current_bar['BB_Upper']) and (close > current_bar['KC_Upper'])
        
        # 賣出條件: 收盤價跌破布林下軌和 KC 下軌
        sell_signal = (close < current_bar['BB_Lower']) and (close < current_bar['KC_Lower'])
        
        # 檢查持倉狀態
        if self.position != 0:
            entry_price = self.avg_cost
            pnl_pct = 0
            if entry_price > 0:
                if self.position > 0:
                    pnl_pct = (close - entry_price) / entry_price
                else:
                    pnl_pct = (entry_price - close) / entry_price
            
            # 停利
            if self.take_profit_pct > 0 and pnl_pct >= self.take_profit_pct:
                return self._create_signal('SELL' if self.position > 0 else 'BUY', abs(self.position), close, "Take Profit")
                
            # 停損
            if self.stop_loss_pct > 0 and pnl_pct <= -self.stop_loss_pct:
                return self._create_signal('SELL' if self.position > 0 else 'BUY', abs(self.position), close, "Stop Loss")
                
            # 反手訊號
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
