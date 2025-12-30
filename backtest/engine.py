import pandas as pd
import logging
from typing import Dict, Any, List, Optional

# 從專案的不同模組導入所需組件
from strategy.base_strategy import BaseStrategy
from strategy.factory import StrategyFactory
from backtest.analyzer import BacktestAnalyzer
from common.db_utils import DatabaseManager
from common.indicators import calculate_indicators

class BacktestEngine:
    """
    回測引擎
    負責獲取數據、創建策略、執行回測、模擬撮合及追蹤權益。
    """
    def __init__(self, initial_capital: float = 1000000.0):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.position = 0
        self.avg_cost = 0.0
        self.analyzer = BacktestAnalyzer(initial_capital)
        self.logger = logging.getLogger("BacktestEngine")

    def run_backtest(self, strategy_type: int, symbol: str, cycle: str, start_date: str, end_date: str, 
                     strategy_config: Dict[str, Any], contract_size: float = 1.0):
        """
        高級別的回測執行方法 (協調器)。
        
        Args:
            strategy_type (int): 策略類型 ID (用於工廠創建).
            symbol (str): 交易的商品代碼.
            cycle (str): K線週期.
            start_date (str): 回測開始日期 ('YYYY-MM-DD').
            end_date (str): 回測結束日期 ('YYYY-MM-DD').
            strategy_config (Dict): 策略所需的特定參數.
            contract_size (float): 合約規格 (每點價值).
        
        Returns:
            BacktestAnalyzer: 包含回測結果的分析器實例.
        """
        self.logger.info(f"--- 開始執行回測 ---")
        self.logger.info(f"策略類型: {strategy_type}, 商品: {symbol}, 週期: {cycle}")
        self.logger.info(f"時間範圍: {start_date} to {end_date}")

        # 1. 獲取數據
        db_manager = DatabaseManager()
        df = db_manager.fetch_data_flex(symbol=symbol, cycle=cycle, start_date=start_date, end_date=end_date)
        if df.empty:
            self.logger.error("從資料庫獲取數據失敗或無數據，回測中止。")
            return None
        # 重設索引以便遍歷
        df = df.reset_index()

        # 2. 創建策略實例
        strategy_id = f"{symbol}_{cycle}_{strategy_type}"
        strategy = StrategyFactory.get_strategy(strategy_type, strategy_id, strategy_config)
        if not strategy:
            self.logger.error(f"無法創建策略類型 {strategy_type}，回測中止。")
            return None

        # 3. 執行核心回測迴圈
        return self._run_loop(strategy, df, contract_size)

    def _run_loop(self, strategy: BaseStrategy, df: pd.DataFrame, contract_size: float):
        """
        核心回測迴圈 (舊的 run 方法重構而來)。
        """
        self.logger.info(f"核心迴圈開始: {len(df)} 總筆數, 合約規格: {contract_size}")
        
        # 1. 數據預熱 (Warm-up)
        # 獲取策略需要的最小歷史長度
        warm_up_size = getattr(strategy, 'max_history_len', 200)
        
        if len(df) < warm_up_size:
            self.logger.error(f"數據總量 ({len(df)}) 小於所需預熱長度 ({warm_up_size})，無法進行回測。")
            return None
            
        history_df = df.iloc[:warm_up_size]
        backtest_df = df.iloc[warm_up_size:]
        
        # 使用 to_dict('records') 將 DataFrame 轉為 List[Dict] 以符合 BaseStrategy 接口
        strategy.load_history(history_df.to_dict('records'))
        strategy.on_init() # 執行策略的初始化
        self.logger.info(f"策略預熱完成，使用 {len(history_df)} 筆數據。")

        # 2. 遍歷回測數據
        for _, row in backtest_df.iterrows():
            current_price = row['Close']
            date = row['Date']
            
            bar = {
                'date': date, 'open': row['Open'], 'high': row['High'], 
                'low': row['Low'], 'close': current_price, 'volume': row['Volume']
            }
            
            # 更新策略的K線緩存 (注意：BaseStrategy 中的 on_bar 之前應該由引擎調用)
            # 這裡的實現假設 BaseStrategy 的 on_bar 內部會自己管理或我們在此傳入df
            # SqueezeBreakoutOptimizedStrategy 有自己的 history_df 管理，所以我們只需調用 on_bar
            # 但為了與 BaseStrategy 接口一致，我們應該先更新緩存
            strategy.update_bar(bar)

            # 呼叫策略核心邏輯
            signal = strategy.on_bar(bar)
            
            # 執行訊號
            if signal:
                self._execute_order(strategy, signal, date, contract_size)
                
            # 更新每日權益
            equity = self._calculate_equity(current_price, contract_size)
            self.analyzer.update_equity(date, equity)
            
        # 3. 回測結束，強制平倉
        if self.position != 0:
            last_row = df.iloc[-1]
            last_price = last_row['Close']
            last_date = last_row['Date']
            self.logger.info(f"回測結束，以最終價 {last_price} 強制平倉 {self.position} 部位。")
            
            action = 'SELL' if self.position > 0 else 'BUY'
            self._execute_order(strategy, {'action': action, 'quantity': abs(self.position), 'price': last_price}, last_date, contract_size)
            
            # 更新最終權益
            self.analyzer.update_equity(last_date, self._calculate_equity(last_price, contract_size))
            
        self.logger.info("--- 回測結束 ---")
        return self.analyzer
        
    def _execute_order(self, strategy: BaseStrategy, signal: Dict, date: Any, contract_size: float):
        """執行訂單並更新倉位與現金"""
        action = signal['action']
        qty = int(signal.get('quantity', 0))
        price = float(signal.get('price', 0))
        
        if qty == 0 or price == 0: return

        direction = 1 if action == 'BUY' else -1
        trade_qty = qty * direction
        
        # 處理平倉和反手
        if (self.position > 0 and direction < 0) or (self.position < 0 and direction > 0):
            pnl = 0
            # 確保平倉數量不超過現有倉位
            closed_qty = min(abs(self.position), qty)
            if self.position > 0: # 平多單
                pnl = (price - self.avg_cost) * closed_qty * contract_size
            else: # 平空單
                pnl = (self.avg_cost - price) * closed_qty * contract_size
            
            self.cash += pnl
            self.analyzer.add_trade({'date': date, 'action': action, 'price': price, 'qty': closed_qty, 'pnl': pnl})
            
            self.position += (closed_qty * direction) # 更新倉位
            trade_qty -= (closed_qty * direction) # 減去已平倉的數量

        # 處理開倉
        if abs(trade_qty) > 0:
            total_cost = (self.avg_cost * abs(self.position)) + (price * abs(trade_qty))
            self.position += trade_qty
            self.avg_cost = total_cost / abs(self.position) if self.position != 0 else 0

        # 通知策略成交
        strategy.on_fill({'action': action, 'price': price, 'quantity': qty, 'time': date})
        strategy.position = self.position
        strategy.avg_cost = self.avg_cost
            
    def _calculate_equity(self, current_price: float, contract_size: float) -> float:
        """計算當前權益 (現金 + 未實現損益)"""
        unrealized_pnl = 0.0
        if self.position != 0:
            if self.position > 0:
                unrealized_pnl = (current_price - self.avg_cost) * self.position * contract_size
            else:
                unrealized_pnl = (self.avg_cost - current_price) * abs(self.position) * contract_size
        return self.cash + unrealized_pnl
