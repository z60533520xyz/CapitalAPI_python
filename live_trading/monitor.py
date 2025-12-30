import time
import logging
import pandas as pd
from typing import Dict, List, Callable
from datetime import datetime, timedelta
from sqlalchemy import text
from common.db_utils import DatabaseManager

class MarketMonitor:
    """
    市場行情監控器
    負責監控資料庫中的 K 線更新，並通知訂閱者
    """
    def __init__(self, interval: int = 5):
        self.interval = interval # 輪詢間隔 (秒)
        self.db = DatabaseManager()
        self.logger = logging.getLogger("MarketMonitor")
        self.subscribers: Dict[str, List[Callable]] = {} # key: f"{code}_{cycle}", value: [callback]
        self.last_dates: Dict[str, datetime] = {} # 記錄上一次讀取的 K 線時間
        self.running = False

    def subscribe(self, code: str, cycle: int, callback: Callable):
        """
        訂閱特定商品和週期的 K 線更新
        """
        key = f"{code}_{cycle}"
        if key not in self.subscribers:
            self.subscribers[key] = []
            # 初始化最後時間，避免一啟動就觸發舊資料
            self.last_dates[key] = self._get_latest_date(code, cycle)
            
        self.subscribers[key].append(callback)
        self.logger.info(f"已訂閱行情更新: {key}")

    def start(self):
        """
        開始監控迴圈
        """
        self.running = True
        self.logger.info(f"行情監控啟動，輪詢間隔: {self.interval} 秒")
        
        while self.running:
            try:
                self._check_updates()
            except Exception as e:
                self.logger.error(f"監控迴圈發生錯誤: {e}")
                import traceback
                traceback.print_exc()
                
            time.sleep(self.interval)

    def stop(self):
        self.running = False
        self.logger.info("行情監控停止")

    def _get_latest_date(self, code: str, cycle: int) -> datetime:
        """取得資料庫中最新的 K 線時間"""
        if not self.db.engine:
            self.db.connect()
            
        try:
            sql = text("SELECT MAX(date) FROM captial_kline_cycle WHERE code = :code AND Cycle = :cycle")
            with self.db.engine.connect() as conn:
                result = conn.execute(sql, {'code': code, 'cycle': cycle}).scalar()
                return result if result else datetime.min
        except Exception as e:
            self.logger.error(f"查詢最新時間失敗 ({code}, {cycle}): {e}")
            return datetime.min

    def _get_latest_bar(self, code: str, cycle: int) -> pd.Series:
        """取得最新的一筆 K 線資料"""
        if not self.db.engine:
            self.db.connect()
            
        try:
            sql = text("""
                SELECT * FROM captial_kline_cycle 
                WHERE code = :code AND Cycle = :cycle 
                ORDER BY date DESC LIMIT 1
            """)
            df = pd.read_sql(sql, self.db.engine, params={'code': code, 'cycle': cycle})
            if not df.empty:
                return df.iloc[0]
            return None
        except Exception as e:
            self.logger.error(f"查詢最新 K 線失敗 ({code}, {cycle}): {e}")
            return None

    def _check_updates(self):
        """檢查所有訂閱的商品是否有更新"""
        for key, callbacks in self.subscribers.items():
            code, cycle_str = key.split('_')
            cycle = int(cycle_str)
            
            latest_date = self._get_latest_date(code, cycle)
            last_known_date = self.last_dates.get(key, datetime.min)
            
            # 如果發現更新的時間 (且不是 datetime.min)
            if latest_date > last_known_date and latest_date != datetime.min:
                self.logger.info(f"發現新 K 線: {key} @ {latest_date}")
                
                # 獲取完整 K 線資料
                bar = self._get_latest_bar(code, cycle)
                if bar is not None:
                    # 通知所有訂閱者
                    for callback in callbacks:
                        try:
                            callback(bar)
                        except Exception as e:
                            self.logger.error(f"執行回調失敗 ({key}): {e}")
                            
                    # 更新最後時間
                    self.last_dates[key] = latest_date
