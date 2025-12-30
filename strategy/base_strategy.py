from abc import ABC, abstractmethod
import logging
from typing import Dict, Any, Optional, List
import pandas as pd

class BaseStrategy(ABC):
    """
    策略基礎抽象類別 (Abstract Base Class)
    
    所有策略都應繼承此類別，並實作核心方法。
    設計目標是讓同一份策略代碼能同時用於回測 (Backtest) 與實盤 (Live Trading)。
    """
    
    def __init__(self, strategy_id: str, config: Dict[str, Any] = None):
        """
        建構子
        
        Args:
            strategy_id: 策略唯一識別碼
            config: 策略參數設定 (dict)
        """
        self.strategy_id = strategy_id
        self.config = config or {}
        self.logger = logging.getLogger(f"Strategy_{strategy_id}")
        
        # 交易狀態 (由執行層維護並同步給策略)
        self.position = 0        # 當前倉位 (正數多單，負數空單)
        self.avg_cost = 0.0      # 持倉成本
        self.realized_pnl = 0.0  # 已實現損益
        self.unrealized_pnl = 0.0 # 未實現損益
        
        # 歷史資料緩存 (用於計算指標)
        self.history_df: pd.DataFrame = pd.DataFrame() # Use DataFrame directly
        self.max_history_len = self.config.get('max_history_len', 1000)

    @abstractmethod
    def on_init(self):
        """
        策略初始化
        在此載入模型、設定參數、預計算指標等。
        如果是實盤，這裡會從資料庫預載入歷史資料。
        """
        pass

    @abstractmethod
    def on_bar(self, bar: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        K線更新事件 (核心邏輯)
        
        Args:
            bar: K線資料，包含 date, open, high, low, close, volume 等欄位
            
        Returns:
            signal: 交易訊號 (可選)，格式自定義，通常包含 action, price, quantity 等
                    例如: {'action': 'BUY', 'price': 16800, 'quantity': 1, 'order_type': 'MARKET'}
                    若無動作則返回 None
        """
        pass
        
    def on_tick(self, tick: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Tick更新事件 (選用)
        適合高頻策略或需要精確停損停利的策略
        """
        pass
        
    def on_order_status(self, order: Dict[str, Any]):
        """
        委託狀態更新 (選用)
        當委託單狀態改變 (Pending -> Submitted -> Filled/Cancelled) 時觸發
        """
        pass
        
    def on_fill(self, trade: Dict[str, Any]):
        """
        成交回報事件
        當策略發出的委託成交時觸發。
        在此更新策略內部的持倉狀態 (雖然執行層也會維護，但策略層可能需要即時知道)。
        
        Args:
            trade: 成交資訊，包含 price, quantity, action, time 等
        """
        qty = trade.get('quantity', 0)
        price = trade.get('price', 0.0)
        action = trade.get('action') # 'BUY' or 'SELL'
        
        self.logger.info(f"[{self.strategy_id}] 收到成交回報: {action} {qty} @ {price}")
        
        # 簡單的持倉更新邏輯 (僅供參考，實際邏輯可能更複雜)
        if action == 'BUY':
            self.position += qty
        elif action == 'SELL':
            self.position -= qty
            
    def load_history(self, klines: List[Dict]):
        """
        載入歷史資料 (熱機用)
        
        Args:
            klines: 歷史K線列表
        """
        if klines:
            self.history_df = pd.DataFrame(klines) # Convert list of dicts to DataFrame once
            # The 'Date' column comes from db_utils.fetch_data_flex (after reset_index)
            # Rename it to 'date' (lowercase) for internal consistency
            if 'Date' in self.history_df.columns:
                self.history_df.rename(columns={'Date': 'date'}, inplace=True)
            self.history_df['date'] = pd.to_datetime(self.history_df['date']) # Ensure 'date' is datetime
            self.history_df = self.history_df.set_index('date') # Set 'date' as index
            self.history_df = self.history_df.iloc[-self.max_history_len:] # Prune to max_history_len
            self.logger.info(f"[{self.strategy_id}] 已載入 {len(self.history_df)} 筆歷史資料")
        else:
            self.history_df = pd.DataFrame()
            self.logger.info(f"[{self.strategy_id}] 未載入歷史資料")
        
    def update_bar(self, bar: Dict[str, Any]):
        """
        更新 K 線緩存
        通常由執行層在呼叫 on_bar 之前調用
        """
        new_bar_df = pd.DataFrame([bar])
        new_bar_df['date'] = pd.to_datetime(new_bar_df['date'])
        new_bar_df = new_bar_df.set_index('date')
        
        self.history_df = pd.concat([self.history_df, new_bar_df])
        if len(self.history_df) > self.max_history_len:
            self.history_df = self.history_df.iloc[-self.max_history_len:]
            
    def get_history_df(self) -> pd.DataFrame:
        """
        取得歷史資料的 DataFrame 格式 (方便計算指標)
        """
        return self.history_df
