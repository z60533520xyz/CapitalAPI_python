import pandas as pd
from typing import Dict, Any
from strategy.base_strategy import BaseStrategy
# from common.indicators import calculate_indicators # Removed, replaced by custom function
import numpy as np
import talib as ta

# Helper function for strategy-specific indicators
def _calculate_strategy_specific_indicators(df, bb_period, bb_multiplier, kc_period, kc_multiplier):
    """
    僅計算策略所需的布林帶和肯特納通道，優化性能。
    """
    df_copy = df.copy() # Operate on a copy to prevent SettingWithCopyWarning
    
    # Ensure columns are numeric and handle potential lower case
    for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
        if col not in df_copy.columns and col.lower() in df_copy.columns:
            df_copy[col] = df_copy[col.lower()]
        if col in df_copy.columns:
            df_copy[col] = pd.to_numeric(df_copy[col], errors='coerce')
    
    # Ensure float64 for TA-Lib
    float_cols = ['Open', 'High', 'Low', 'Close']
    for col in float_cols:
        if col in df_copy.columns:
            df_copy[col] = df_copy[col].astype(np.float64)

    df_copy = df_copy.dropna(subset=['Close'])
    if df_copy.empty:
        return df_copy

    # 布林通道 (Bollinger Bands)
    df_copy['BB_Middle'] = df_copy['Close'].rolling(window=bb_period, min_periods=1).mean()
    bb_std = df_copy['Close'].rolling(window=bb_period, min_periods=1).std()
    df_copy['BB_Upper'] = df_copy['BB_Middle'] + (bb_std * bb_multiplier)
    df_copy['BB_Lower'] = df_copy['BB_Middle'] - (bb_std * bb_multiplier)

    # ATR (用於 Keltner Channels)
    df_copy['ATR'] = ta.ATR(df_copy['High'].values, df_copy['Low'].values, df_copy['Close'].values, timeperiod=bb_period) # Use bb_period as timeperiod for ATR
    df_copy['ATR'] = df_copy['ATR'].fillna(df_copy['ATR'].mean()) # Fill NaN with mean or another suitable value

    # Keltner Channels (KC)
    df_copy['KC_Middle'] = df_copy['Close'].ewm(span=kc_period, adjust=False).mean()
    df_copy['KC_Upper'] = df_copy['KC_Middle'] + (df_copy['ATR'] * kc_multiplier)
    df_copy['KC_Lower'] = df_copy['KC_Middle'] - (df_copy['ATR'] * kc_multiplier)

    return df_copy

class CLVolatilityExpansionStrategy(BaseStrategy):
    """
    CL0000 波動率擴張策略
    基於擠壓突破優化策略，針對原油期貨特性進行參數調整。
    """
    def __init__(self, strategy_id: str, config: Dict[str, Any]):
        super().__init__(strategy_id, config)
        self.stop_loss_pct = float(config.get('stopLossPercent', 0.02)) # Adjusted for CL0000
        self.take_profit_pct = float(config.get('takeProfitPercent', 0.035)) # Adjusted for CL0000
        self.trailing_stop_pct = float(config.get('trailingStopPercent', 0.015)) # Adjusted for CL0000
        
        # 參數
        self.bb_period = int(config.get('bbPeriod', 35))
        self.bb_multiplier = float(config.get('bbMultiplier', 1.7))
        self.kc_period = int(config.get('kcPeriod', 35))
        self.kc_multiplier = float(config.get('kcMultiplier', 1.4))
        
        self.history_df = pd.DataFrame()
        # min_history_len 現在將控制傳遞給 calculate_indicators 的歷史數據量
        # 確保有足夠的數據用於所有指標的最長週期 + 幾個額外的 K 線來處理 shift() 等操作
        self.min_history_len = max(self.bb_period, self.kc_period) + 10 # 額外增加一些緩衝
        
        # 記錄進場後的最高/最低價 (用於移動停利)
        self.highest_high = 0.0
        self.lowest_low = float('inf')

    def on_init(self):
        self.logger.info(f"策略 {self.strategy_id} 初始化完成")

    def on_bar(self, bar: Dict[str, Any]) -> Dict[str, Any]:
        self.update_history(bar)
        
        # 確保有足夠的歷史數據來計算指標
        if len(self.history_df) < self.min_history_len:
            return None
            
        # 計算指標 - 只在必要的歷史數據上進行計算
        # 複製以避免 SettingWithCopyWarning
        df = self.history_df.copy() 
        df = _calculate_strategy_specific_indicators(df, # Use our custom indicator function
                                  bb_period=self.bb_period, 
                                  bb_multiplier=self.bb_multiplier,
                                  kc_period=self.kc_period, 
                                  kc_multiplier=self.kc_multiplier)
        
        # 從計算後的 DataFrame 中獲取當前和前一個 K 線
        # 確保在計算指標後仍有足夠的數據
        if len(df) < 2: 
            return None
        current_bar = df.iloc[-1]
        
        # 從 df 中獲取 prev_bar，這會包含計算好的指標
        # 確保 prev_bar 存在，否則會發生 IndexError
        # if len(df) < 2: # This check is already done above.
        prev_bar = df.iloc[-2]

        close = current_bar['Close']
        high = current_bar['High']
        low = current_bar['Low']
        
        # 擠壓條件 (前一根 K 線)
        squeeze_on = (prev_bar['BB_Upper'] < prev_bar['KC_Upper']) and \
                     (prev_bar['BB_Lower'] > prev_bar['KC_Lower'])
                     
        if self.config.get('debug', False) and squeeze_on:
             self.logger.debug(f"[{bar['date']}] Squeeze ON! BB: {prev_bar['BB_Upper']:.2f}/{prev_bar['BB_Lower']:.2f}, KC: {prev_bar['KC_Upper']:.2f}/{prev_bar['KC_Lower']:.2f}")

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
                self.logger.debug(f"[{bar['date']}] Take Profit! PnL_Pct: {pnl_pct:.4f}")
                return self._create_signal('SELL' if self.position > 0 else 'BUY', abs(self.position), close, "Take Profit")
                
            # 2. 停損
            if self.stop_loss_pct > 0 and pnl_pct <= -self.stop_loss_pct:
                self.logger.debug(f"[{bar['date']}] Stop Loss! PnL_Pct: {pnl_pct:.4f}")
                return self._create_signal('SELL' if self.position > 0 else 'BUY', abs(self.position), close, "Stop Loss")
                
            # 3. 移動停利
            if self.trailing_stop_pct > 0:
                if self.position > 0:
                    trailing_stop_price = self.highest_high * (1 - self.trailing_stop_pct)
                    if low <= trailing_stop_price:
                        self.logger.debug(f"[{bar['date']}] Trailing Stop (Long) at {trailing_stop_price:.2f}")
                        return self._create_signal('SELL', abs(self.position), trailing_stop_price, "Trailing Stop")
                else:
                    trailing_stop_price = self.lowest_low * (1 + self.trailing_stop_pct)
                    if high >= trailing_stop_price:
                        self.logger.debug(f"[{bar['date']}] Trailing Stop (Short) at {trailing_stop_price:.2f}")
                        return self._create_signal('BUY', abs(self.position), trailing_stop_price, "Trailing Stop")
            
            # 4. 反手訊號
            if self.position > 0 and sell_signal:
                self.logger.debug(f"[{bar['date']}] Reverse to Short (Current: Long)")
                return self._create_signal('SELL', abs(self.position) * 2, close, "Reverse to Long")
            elif self.position < 0 and buy_signal:
                self.logger.debug(f"[{bar['date']}] Reverse to Long (Current: Short)")
                return self._create_signal('BUY', abs(self.position) * 2, close, "Reverse to Short")
                
        else:
            # 無持倉，檢查進場
            if buy_signal:
                self.logger.debug(f"[{bar['date']}] Strategy Buy Signal")
                return self._create_signal('BUY', 1, close, "Strategy Buy")
            elif sell_signal:
                self.logger.debug(f"[{bar['date']}] Strategy Sell Signal")
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
        if len(self.history_df) > 200: # Keep last 200 bars for indicator calculation
            self.history_df = self.history_df.iloc[-200:]

    def _create_signal(self, action, qty, price, reason):
        return {
            'action': action,
            'quantity': qty,
            'price': price,
            'reason': reason
        }
