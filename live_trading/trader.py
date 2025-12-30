import logging
import os
import csv
from datetime import datetime
from typing import Dict, Any
import pandas as pd
from common.db_utils import DatabaseManager
from common.discord_notify import DiscordNotifier

class LiveTrader:
    """
    實盤交易執行器
    負責接收策略訊號並執行交易 (模擬或實盤)
    """
    def __init__(self, strategy, config: Dict[str, Any]):
        self.strategy = strategy
        self.config = config
        self.is_paper_trading = config.get('isFake', True)
        self.db = DatabaseManager()
        self.code = config.get('code', 'Unknown')
        self.logger = logging.getLogger(f"LiveTrader_{self.code}")
        self.discord = DiscordNotifier()
        
        self.chart_id = config.get('chart_id', 0)
        self.strategy_id = config.get('strategy_config_id', 0)
        self.target = config.get('target_symbol', 'Unknown')
        self.trade_qty = config.get('tradeQty', 1)
        self.contract_size = config.get('contractSize', 1.0)
        
        # 準備稽核檔案路徑
        self.audit_dir = "logs/audit"
        os.makedirs(self.audit_dir, exist_ok=True)
        self.audit_file = os.path.join(self.audit_dir, f"live_kline_{self.code}.csv")
        self._init_audit_file()

    def _init_audit_file(self):
        """初始化稽核檔案 (寫入 Header)"""
        if not os.path.exists(self.audit_file):
            with open(self.audit_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['Date', 'Open', 'High', 'Low', 'Close', 'Volume'])

    def _record_audit_log(self, bar: Dict[str, Any]):
        """將實盤接收到的 K 棒寫入 CSV"""
        try:
            with open(self.audit_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    bar['date'], 
                    bar['open'], bar['high'], bar['low'], bar['close'], bar['volume']
                ])
        except Exception as e:
            self.logger.error(f"寫入稽核紀錄失敗: {e}")

    def on_signal(self, signal: Dict[str, Any]):
        """
        接收策略訊號
        """
        msg = f"【交易訊號】{self.code} - {signal.get('action')} @ {signal.get('price')} (Qty: {signal.get('quantity', self.trade_qty)})"
        self.logger.info(msg)
        self.discord.send(msg)
        
        if self.is_paper_trading:
            self._execute_paper_trade(signal)
        else:
            self._execute_live_trade(signal)
            
    def _execute_paper_trade(self, signal: Dict[str, Any]):
        """
        執行模擬交易 (寫入資料庫)
        """
        try:
            # 取得下一個 tradeId
            max_trade_id = self.db.get_max_trade_id(self.chart_id)
            next_trade_id = max_trade_id + 1
            
            action = signal.get('action')
            price = float(signal.get('price', 0))
            # 優先使用訊號中的數量，否則使用配置數量
            qty = int(signal.get('quantity', self.trade_qty))
            
            # 轉換買賣方向 (1=Buy, 0=Sell)
            b_s = 1 if action == 'BUY' else 0
            
            trade_record = {
                'chartId': self.chart_id,
                'tradeId': next_trade_id,
                'date': datetime.now(),
                'B_S': b_s,
                'price': price,
                'volume': qty,
                'isFake': 1, # 模擬單
                'Target': self.target,
                'isDeal': 1, # 模擬單視為立即成交
                'orderNo': f"SIM_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                'signal': 0, # 暫時為 0
                'high': price, # 暫時用成交價
                'low': price, # 暫時用成交價
                'strategyId': self.strategy_id
            }
            
            self.db.record_trade(trade_record)
            self.logger.info(f"模擬交易已記錄: {action} {qty} @ {price} (TradeID: {next_trade_id})")
            
            # 回報給策略 (模擬成交)
            fill_report = {
                'action': action,
                'price': price,
                'quantity': qty,
                'time': datetime.now()
            }
            self.strategy.on_fill(fill_report)
            
        except Exception as e:
            self.logger.error(f"模擬交易執行失敗: {e}")
            import traceback
            traceback.print_exc()
            
    def _execute_live_trade(self, signal: Dict[str, Any]):
        """
        執行實盤交易 (尚未實作)
        """
        self.logger.warning("實盤交易尚未實作，請使用模擬模式")

    def on_new_bar(self, bar_data: pd.Series):
        """
        當收到新 K 線時觸發
        """
        try:
            # 轉換為策略需要的字典格式
            bar = {
                'date': bar_data['date'],
                'open': float(bar_data['open']),
                'high': float(bar_data['high']),
                'low': float(bar_data['low']),
                'close': float(bar_data['close']),
                'volume': float(bar_data['volume'])
            }
            
            # 控制台即時輸出 (讓使用者看到)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {self.code} New Bar: {bar['date']} | C={bar['close']} | V={bar['volume']}")
            
            self.logger.info(f"處理新 K 線: {bar['date']} Close={bar['close']}")
            
            # 1. 記錄實盤數據快照 (Audit)
            self._record_audit_log(bar)
            
            # 2. 執行策略
            signal = self.strategy.on_bar(bar)
            
            if signal:
                self.on_signal(signal)
                
        except Exception as e:
            self.logger.error(f"處理 K 線失敗: {e}")
            import traceback
            traceback.print_exc()
