import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
from strategy.base_strategy import BaseStrategy

class SimpleBBBreakoutNQ(BaseStrategy):
    """
    簡化版布林帶突破策略，專為 NQ0000 設計
    修正了多個同名欄位可能導致的 Series 歧義錯誤。
    """
    
    def on_init(self):
        """初始化策略參數"""
        self.bb_period = int(self.config.get('bbPeriod', 20))
        self.bb_multiplier = float(self.config.get('bbMultiplier', 1.5))
        self.stop_loss_pct = float(self.config.get('stopLossPercent', 0.01))
        self.take_profit_pct = float(self.config.get('takeProfitPercent', 0.02))
        self.trade_quantity = int(self.config.get('tradeQuantity', 1))
        
        self.logger.info(f"[{self.strategy_id}] 初始化簡化布林帶突破策略: BB_Period={self.bb_period}, BB_Mult={self.bb_multiplier}")
        self.min_history_len = self.bb_period
        
    def on_bar(self, bar: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """K線更新邏輯"""
        df = self.history_df
        if df.empty or len(df) < self.min_history_len:
            return None
            
        # 強制轉換欄位名稱為小寫
        temp_df = df.copy()
        temp_df.columns = [c.lower() for c in temp_df.columns]
        
        # 處理可能重複的 close 欄位
        closes_data = temp_df['close']
        if isinstance(closes_data, pd.DataFrame):
            # 如果有重複欄位，取最後一個（通常是最新更新的）
            closes = closes_data.iloc[:, -1].astype(np.float64)
        else:
            closes = closes_data.astype(np.float64)
            
        # 計算最後一筆布林帶數值
        ma_series = closes.rolling(window=self.bb_period).mean()
        std_series = closes.rolling(window=self.bb_period).std()
        
        ma = ma_series.iloc[-1]
        std = std_series.iloc[-1]
        
        if np.isnan(ma) or np.isnan(std):
            return None
            
        current_bb_upper = ma + (std * self.bb_multiplier)
        current_bb_lower = ma - (std * self.bb_multiplier)
        current_close = float(bar.get('close') or bar.get('Close'))
        
        # 偵錯模式
        if self.config.get('debug', False):
            buy_signal = current_close > current_bb_upper
            sell_signal = current_close < current_bb_lower
            if buy_signal or sell_signal:
                self.logger.debug(f"[{bar['date']}] Close: {current_close:.2f}, Upper: {current_bb_upper:.2f}, Lower: {current_bb_lower:.2f}, BUY: {buy_signal}, SELL: {sell_signal}")

        # 檢查持倉
        if self.position != 0:
            entry_price = self.avg_cost
            pnl_pct = (current_close - entry_price) / entry_price if self.position > 0 else (entry_price - current_close) / entry_price
            
            if self.take_profit_pct > 0 and pnl_pct >= self.take_profit_pct:
                return self._create_signal('SELL' if self.position > 0 else 'BUY', abs(self.position), current_close, "Take Profit")
            if self.stop_loss_pct > 0 and pnl_pct <= -self.stop_loss_pct:
                return self._create_signal('SELL' if self.position > 0 else 'BUY', abs(self.position), current_close, "Stop Loss")
            return None

        # 進場邏輯
        if current_close > current_bb_upper:
            return self._create_signal('BUY', self.trade_quantity, current_close, 'BB Breakout Buy')
        elif current_close < current_bb_lower:
            return self._create_signal('SELL', self.trade_quantity, current_close, 'BB Breakout Sell')
            
        return None

    def _create_signal(self, action, qty, price, reason):
        return {'action': action, 'quantity': qty, 'price': price, 'reason': reason}