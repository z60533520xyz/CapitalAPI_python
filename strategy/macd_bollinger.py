import pandas as pd
import numpy as np
from typing import Dict, Any, List
from strategy.base_strategy import BaseStrategy
from common.indicators import calculate_indicators

class MacdBollingerStrategy(BaseStrategy):
    """
    MACD + 布林通道策略 (對應 C# ID 0, 1)
    """
    def __init__(self, strategy_id: str, config: Dict[str, Any]):
        super().__init__(strategy_id, config)
        self.stop_loss_pct = config.get('stop_loss_pct', 0.01)
        self.take_profit_pct = config.get('take_profit_pct', 0.02)
        self.history_df = pd.DataFrame()
        self.min_history_len = 50 # 至少需要 50 根 K 線來計算指標

    def on_init(self):
        self.logger.info(f"策略 {self.strategy_id} 初始化完成")

    def on_bar(self, bar: Dict[str, Any]) -> Dict[str, Any]:
        # 1. 更新歷史資料
        self.update_history(bar)
        
        # 2. 檢查資料長度
        if len(self.history_df) < self.min_history_len:
            return None
            
        # 3. 計算指標
        df = self.history_df.copy()
        df = calculate_indicators(df)
        
        # 4. 取得最後 3 根 K 線
        # iloc[-1] 是最新 (Now), iloc[-2] 是前一根 (P), iloc[-3] 是前前一根 (PP)
        now = df.iloc[-1]
        p = df.iloc[-2]
        pp = df.iloc[-3]
        
        current_price = bar['close']
        signal = None
        
        # 5. 檢查持倉狀態與出場條件
        if self.position != 0:
            entry_price = self.avg_cost
            pnl_pct = 0
            if entry_price > 0:
                if self.position > 0:
                    pnl_pct = (current_price - entry_price) / entry_price
                else:
                    pnl_pct = (entry_price - current_price) / entry_price
            
            # 停利
            if self.take_profit_pct > 0 and pnl_pct >= self.take_profit_pct:
                return self._create_signal('SELL' if self.position > 0 else 'BUY', abs(self.position), current_price, "Take Profit")
                
            # 停損
            if self.stop_loss_pct > 0 and pnl_pct <= -self.stop_loss_pct:
                return self._create_signal('SELL' if self.position > 0 else 'BUY', abs(self.position), current_price, "Stop Loss")
                
            # 策略出場
            if self.position > 0: # 持有多單
                if self._stop_buy_strategy(now, p, pp):
                    return self._create_signal('SELL', abs(self.position), current_price, "Strategy Stop Buy")
                if self._sell_strategy(now, p, pp): # 反手
                    return self._create_signal('SELL', abs(self.position) * 2, current_price, "Reverse to Short") # 這裡簡化為平倉，實際可能需要反手
                    
            elif self.position < 0: # 持有賣單
                if self._stop_sell_strategy(now, p, pp):
                    return self._create_signal('BUY', abs(self.position), current_price, "Strategy Stop Sell")
                if self._buy_strategy(now, p, pp): # 反手
                    return self._create_signal('BUY', abs(self.position) * 2, current_price, "Reverse to Long")

        # 6. 檢查進場條件 (若無持倉)
        else:
            if self._buy_strategy(now, p, pp):
                return self._create_signal('BUY', 1, current_price, "Strategy Buy")
            elif self._sell_strategy(now, p, pp):
                return self._create_signal('SELL', 1, current_price, "Strategy Sell")
                
        return None

    def update_history(self, bar: Dict[str, Any]):
        """更新歷史 DataFrame"""
        new_row = pd.DataFrame([bar])
        self.history_df = pd.concat([self.history_df, new_row], ignore_index=True)
        # 保持一定長度以節省記憶體，但要足夠計算指標
        if len(self.history_df) > 200:
            self.history_df = self.history_df.iloc[-200:]

    def _create_signal(self, action, qty, price, reason):
        return {
            'action': action,
            'quantity': qty,
            'price': price,
            'reason': reason
        }

    # --- 策略邏輯 (對應 C#) ---

    def _buy_strategy(self, now, p, pp):
        # Now.Dif > P.Dif && P.Dif > PP.Dif
        # P.BBUB - P.PMa20 > Now.BBUB - Now.PMa20 (通道收縮?)
        
        cond1 = now['MACD'] > p['MACD']
        cond2 = p['MACD'] > pp['MACD']
        
        # P.BBUB - P.PMa20
        width_p = p['BB_Upper'] - p['BB_Middle']
        # Now.BBUB - Now.PMa20
        width_now = now['BB_Upper'] - now['BB_Middle']
        
        cond3 = width_p > width_now
        
        return cond1 and cond2 and cond3

    def _sell_strategy(self, now, p, pp):
        # Now.Dif < P.Dif && P.Dif < PP.Dif
        # P.PMa20 - P.BBLB > Now.PMa20 - Now.BBLB
        
        cond1 = now['MACD'] < p['MACD']
        cond2 = p['MACD'] < pp['MACD']
        
        width_p = p['BB_Middle'] - p['BB_Lower']
        width_now = now['BB_Middle'] - now['BB_Lower']
        
        cond3 = width_p > width_now
        
        return cond1 and cond2 and cond3

    def _stop_buy_strategy(self, now, p, pp):
        # (Now.Dif < P.Dif && P.Dif < PP.Dif) || Now.Close < P.ML
        # 假設 ML 為布林中軌 (BB_Middle)
        
        cond1 = (now['MACD'] < p['MACD']) and (p['MACD'] < pp['MACD'])
        cond2 = now['Close'] < p['BB_Middle']
        
        return cond1 or cond2

    def _stop_sell_strategy(self, now, p, pp):
        # (Now.Dif > P.Dif && P.Dif > PP.Dif) || Now.Close > P.MH
        # 假設 MH 為布林中軌 (BB_Middle)
        
        cond1 = (now['MACD'] > p['MACD']) and (p['MACD'] > pp['MACD'])
        cond2 = now['Close'] > p['BB_Middle']
        
        return cond1 or cond2
