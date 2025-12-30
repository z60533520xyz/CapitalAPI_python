import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
from strategy.base_strategy import BaseStrategy

class CLInsideBarStrategy(BaseStrategy):
    """
    CL0000 60m Inside Bar 突破策略 (ID: 22)
    特點：價格行為交易，極窄止損換取高爆發。
    """
    
    def on_init(self):
        self.ema_period = int(self.config.get('emaPeriod', 50))
        self.trade_quantity = int(self.config.get('tradeQuantity', 1))
        
        self.min_history_len = self.ema_period + 10
        self.pending_order = None # 用於紀錄掛單 (Breakout Level, Stop Loss)
        
        self.logger.info(f"[{self.strategy_id}] 初始化 CL InsideBar")

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
        ema = closes.ewm(span=self.ema_period, adjust=False).mean()
        
        c_close = closes.iloc[-1]
        c_high = highs.iloc[-1]
        c_low = lows.iloc[-1]
        c_ema = ema.iloc[-1]
        
        p_high = highs.iloc[-2]
        p_low = lows.iloc[-2]
        
        if np.isnan(c_ema): return None

        # 1. 檢查持倉出場
        if self.position != 0:
            # 此策略為波段突破，這裡簡化為固定移動止損
            # 這裡簡單用 EMA 作為動態止損線
            if self.position > 0 and c_close < c_ema:
                return self._signal('SELL', 'EMA Trail Stop')
            elif self.position < 0 and c_close > c_ema:
                return self._signal('BUY', 'EMA Trail Stop')
            return None

        # 2. 進場邏輯 (Inside Bar)
        # 定義：當前 K 線的高低點 完全在 前一根 K 線的高低點之內
        is_inside_bar = c_high < p_high and c_low > p_low
        
        if is_inside_bar:
            # 順勢突破邏輯
            # 多頭：價格 > EMA，且出現 Inside Bar -> 等待突破 Mother Bar 高點
            if c_close > c_ema:
                # 這裡為了回測方便，我們假設如果下一根 K 線突破了 p_high 就進場
                # 在實盤中這應該是一個 Stop 單，但在回測 loop 中我們無法掛單
                # 所以我們標記這個狀態，看下一根 bar 的開盤或高點是否觸發
                self.pending_order = {
                    'side': 'BUY',
                    'trigger': p_high,
                    'stop': p_low # 止損設在 Mother Bar 低點 (極窄)
                }
            # 空頭
            elif c_close < c_ema:
                self.pending_order = {
                    'side': 'SELL',
                    'trigger': p_low,
                    'stop': p_high # 止損設在 Mother Bar 高點
                }
        
        # 3. 檢查掛單是否觸發 (模擬)
        if self.pending_order:
            trigger = self.pending_order['trigger']
            stop = self.pending_order['stop']
            side = self.pending_order['side']
            
            # 檢查當前 K 線是否觸發了 上一根 Inside Bar 設定的突破點
            # 嚴格來說，這應該在 Inside Bar 的 *下一根* 判斷
            # 由於 on_bar 是 K 線收盤才呼叫，所以我們實際上是在判斷 "剛結束的這根 K 線" 有沒有突破
            # 但 Inside Bar 是 "剛結束的這根"，所以掛單是給 "下一根" 用的
            
            # 修正邏輯：我們把 pending_order 存到 self，下一根 bar 進來時檢查
            # 但這裡簡化：如果當前是 Inside Bar，我們立即發出訊號？不行，還沒突破
            pass # 等待下一根
            
        # 4. 實際進場檢查 (檢查上一根是否留下了 Pending Order)
        # 注意：這個變數需要跨 bar 保存，但在 BaseStrategy 中 self 會一直存在
        # 簡單起見，我們改用 "上一根是 Inside Bar" 的判斷
        
        prev_is_inside = (highs.iloc[-2] < highs.iloc[-3]) and (lows.iloc[-2] > lows.iloc[-3])
        if prev_is_inside and self.position == 0:
            mother_high = highs.iloc[-3]
            mother_low = lows.iloc[-3]
            p_close_val = closes.iloc[-2] # Inside Bar 的收盤
            
            # 模擬突破：如果當前 K 線的高點超過 Mother High
            if c_close > c_ema and c_high > mother_high:
                 return self._signal('BUY', 'Inside Bar Breakout')
            elif c_close < c_ema and c_low < mother_low:
                 return self._signal('SELL', 'Inside Bar Breakout')

        return None

    def _signal(self, action, reason):
        price = float(self.history_df.iloc[-1]['close']) if isinstance(self.history_df.iloc[-1]['close'], (float, np.float64)) else float(self.history_df.iloc[-1]['close'].iloc[-1])
        return {
            'action': action,
            'quantity': self.trade_quantity,
            'price': price,
            'reason': reason
        }
