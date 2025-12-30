import sqlalchemy
from sqlalchemy import text
import configparser
import os
import logging
import pandas as pd
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

# 從 stock_ml_py/config.py 合併過來的設定
CYCLE_MAPPING = {
    '5m': 2, '15m': 3, '30m': 4, '60m': 5,
    '1d': 6, '1w': 7, '1M': 8, '2h': 9
}

SYMBOLS_CONFIG = {
    'CL0000': {'EXCHANGE': 'NYM', 'SYMBOL_DISPLAY': '輕原油 (CL)'},
    'NQ0000': {'EXCHANGE': 'CME', 'SYMBOL_DISPLAY': '納斯達克100指數期貨 (NQ)'},
    'YM0000': {'EXCHANGE': 'CBOT', 'SYMBOL_DISPLAY': '小道瓊指數期貨 (YM)'},
    'TX00': {'EXCHANGE': 'TAIFEX', 'SYMBOL_DISPLAY': '台股指數期貨 (TX)'},
    'ES0000': {'EXCHANGE': 'CME', 'SYMBOL_DISPLAY': 'S&P 500 指數期貨 (ES)'},
}


class DatabaseManager:
    """
    資料庫管理員
    負責建立資料庫連線與執行查詢
    """
    
    def __init__(self, config_path: str = 'config.ini'):
        self.config = configparser.ConfigParser()
        self.engine = None
        
        if os.path.exists(config_path):
            self.config.read(config_path, encoding='utf-8')
        else:
            parent_config = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.ini')
            if os.path.exists(parent_config):
                self.config.read(parent_config, encoding='utf-8')
            else:
                logging.warning(f"找不到設定檔: {config_path} 或 {parent_config}")

    def get_engine(self) -> Optional[sqlalchemy.engine.Engine]:
        """取得 SQLAlchemy Engine"""
        if self.engine is None:
            try:
                db_section = 'database' if 'database' in self.config else 'DATABASE'
                if db_section not in self.config:
                    logging.error("設定檔中缺少 [database] 或 [DATABASE] 區塊")
                    return None
                    
                db_config = self.config[db_section]
                port = db_config.get('port', '3306')
                
                connection_string = (
                    f"mysql+pymysql://{db_config['user']}:{db_config['password']}"
                    f"@{db_config['host']}:{port}/{db_config['database']}?charset=utf8mb4"
                )
                self.engine = sqlalchemy.create_engine(connection_string)
                logging.info("資料庫引擎初始化成功")
            except Exception as e:
                logging.error(f"建立資料庫引擎失敗: {e}")
                return None
        return self.engine
        
    def connect(self):
        """確保引擎已建立"""
        self.get_engine()

    def fetch_data_flex(self, symbol: str, cycle: str = "60m", period: str = "250d", 
                        start_date: Optional[str] = None, end_date: Optional[str] = None, 
                        limit: int = 10000) -> pd.DataFrame:
        """
        從 MySQL 彈性抓取資料 (整合自 stock_ml_py/db_utils.py)
        
        Args:
            symbol (str): 商品代碼, e.g., 'TX00'.
            cycle (str): 週期名稱, e.g., '60m', '1d'.
            period (str): 時間區間字串, e.g., '250d', '3mo', '1y'.
            start_date (str, optional): 開始日期 'YYYY-MM-DD'.
            end_date (str, optional): 結束日期 'YYYY-MM-DD'.
            limit (int): 最大筆數限制.
            
        Returns:
            pd.DataFrame: 包含 K 線資料的 DataFrame.
        """
        symbol_config = SYMBOLS_CONFIG.get(symbol)
        if not symbol_config:
            logging.error(f"無效的標的代碼: {symbol}")
            return pd.DataFrame()

        engine = self.get_engine()
        if engine is None:
            logging.error("資料庫連線失敗，無法抓取資料")
            return pd.DataFrame()
        
        try:
            cycle_code = CYCLE_MAPPING.get(cycle)
            if cycle_code is None:
                logging.error(f"無效的週期名稱: {cycle}")
                return pd.DataFrame()
            
            # 處理日期
            if start_date and end_date:
                start_dt = datetime.strptime(start_date, '%Y-%m-%d')
                end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            else:
                end_dt = datetime.now()
                period_lower = period.lower()
                days = 0
                if period_lower.endswith('mo'):
                    months = int(period_lower[:-2])
                    days = months * 30
                elif period_lower.endswith('w'):
                    days = int(period_lower[:-1]) * 7
                elif period_lower.endswith('y'):
                    days = int(period_lower[:-1]) * 365
                elif period_lower.endswith('d'):
                    days = int(period_lower[:-1])
                else:
                    days = 250 # 預設
                start_dt = end_dt - timedelta(days=days)

            logging.info(f"抓取 {symbol_config['SYMBOL_DISPLAY']} ({symbol}) {cycle} K線資料...")
            logging.info(f"時間範圍：{start_dt.strftime('%Y-%m-%d')} 到 {end_dt.strftime('%Y-%m-%d')}")

            query = text("""
                SELECT date as Date, open as Open, high as High, low as Low, close as Close, volume as Volume
                FROM captial_kline_cycle 
                WHERE code = :symbol_code AND exchange = :exchange AND Cycle = :cycle_code
                  AND date BETWEEN :start_date AND :end_date
                ORDER BY date ASC LIMIT :limit
            """)
            
            params = {
                'symbol_code': symbol, 
                'exchange': symbol_config['EXCHANGE'], 
                'cycle_code': cycle_code, 
                'start_date': start_dt, 
                'end_date': end_dt, 
                'limit': limit
            }
            
            df = pd.read_sql(query, engine, params=params)
            
            if df.empty:
                logging.warning(f"MySQL 查詢無資料")
                return pd.DataFrame()

            df['Date'] = pd.to_datetime(df['Date'])
            df.set_index('Date', inplace=True)
            return df
            
        except Exception as e:
            logging.error(f"MySQL 查詢失敗: {e}")
            return pd.DataFrame()

    def fetch_kline_data(self, symbol: str, cycle: int, days: int = 30) -> pd.DataFrame:
        """(舊版)抓取 K 線資料"""
        engine = self.get_engine()
        if not engine: return pd.DataFrame()
        query = text("SELECT date, open, high, low, close, volume FROM captial_kline_cycle WHERE code = :code AND Cycle = :cycle AND date >= DATE_SUB(NOW(), INTERVAL :days DAY) ORDER BY date ASC")
        try:
            return pd.read_sql(query, engine, params={'code': symbol, 'cycle': cycle, 'days': days})
        except Exception as e:
            logging.error(f"查詢資料失敗: {e}")
            return pd.DataFrame()

    def record_trade(self, trade_data: Dict[str, Any]):
        """寫入交易紀錄到 captial_trade_history"""
        if not self.engine: self.connect()
        try:
            sql = text("""
                INSERT INTO captial_trade_history (chartId, tradeId, date, B_S, price, volume, isFake, Target, isDeal, orderNo, `signal`, high, low, strategyId) 
                VALUES (:chartId, :tradeId, :date, :B_S, :price, :volume, :isFake, :Target, :isDeal, :orderNo, :signal, :high, :low, :strategyId)
            """)
            with self.engine.connect() as conn:
                conn.execute(sql, trade_data)
                conn.commit()
        except Exception as e:
            logging.error(f"寫入交易紀錄失敗: {e}")

    def get_max_trade_id(self, chart_id: int) -> int:
        """取得指定 chartId 的最大 tradeId"""
        if not self.engine: self.connect()
        try:
            sql = text("SELECT MAX(tradeId) FROM captial_trade_history WHERE chartId = :chartId")
            with self.engine.connect() as conn:
                result = conn.execute(sql, {'chartId': chart_id}).scalar()
                return result if result is not None else 0
        except Exception as e:
            logging.error(f"取得最大 tradeId 失敗: {e}")
            return 0

    def get_active_strategies(self) -> pd.DataFrame:
        """取得所有啟用的策略配置"""
        engine = self.get_engine()
        if not engine: return pd.DataFrame()
        query = text("""
            SELECT c.id as chart_id, c.code, c.exchange, s.id as strategy_config_id, s.strategy as strategy_type, s.Cycle as cycle,
                   s.stopLossPercent, s.takeProfitPercent, s.trailingStopPercent, o.isFake, o.tradeQty, o.contractSize, o.Target as target_symbol
            FROM captial_chart c JOIN captial_chart_strategy s ON c.id = s.chartId
            LEFT JOIN captial_trade_option o ON c.exchange = o.exchange AND c.code = o.code
            WHERE c.enable = 1 AND s.enable = 1
        """)
        try:
            return pd.read_sql(query, engine)
        except Exception as e:
            logging.error(f"查詢啟用策略失敗: {e}")
            return pd.DataFrame()

    def get_kline_data(self, symbol: str, cycle: int, start_date: datetime, end_date: datetime) -> pd.DataFrame:
        """取得 K 線資料"""
        engine = self.get_engine()
        if not engine: return pd.DataFrame()
        query = text("SELECT * FROM captial_kline_cycle WHERE code = :code AND Cycle = :cycle AND date >= :start_date AND date <= :end_date ORDER BY date ASC")
        try:
            return pd.read_sql(query, engine, params={'code': symbol, 'cycle': cycle, 'start_date': start_date, 'end_date': end_date})
        except Exception as e:
            logging.error(f"查詢 K 線失敗: {e}")
            return pd.DataFrame()

    def close(self):
        if self.engine: self.engine.dispose()
