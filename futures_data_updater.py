import comtypes.client
import comtypes.gen.SKCOMLib as sk
import time
import pandas as pd
from datetime import datetime, timedelta
import os
import pymysql
import configparser
import logging
import tkinter as tk

# 區域：日誌配置
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    handlers=[logging.StreamHandler(), logging.FileHandler('updater.log', 'a', 'utf-8')])

class FuturesDataUpdater:
    def __init__(self, root, config_path='config.ini'):
        self.root = root
        self._load_config(config_path)
        
        self.skC, self.skQ, self.skOSQ, self.skO, self.skR = None, None, None, None, None
        
        # 狀態標誌
        self.domestic_connected = False
        self.overseas_connected = False
        self.domestic_product_list = []
        self.overseas_product_list = []
        self.kline_data = {} # 鍵: product_id
        
        # 佇列 (為簡化單執行緒操作，使用列表實作)
        self.domestic_products_received = False
        self.overseas_products_received = False
        self.pending_kline_requests = []
        
        self._initialize_com_objects()
        self._initialize_database()
        
        # 啟動流程
        self.root.after(1000, self.step_1_login)

    def _load_config(self, config_path):
        config = configparser.ConfigParser()
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"設定檔 '{config_path}' 不存在。")
        config.read(config_path, encoding='utf-8')
        
        self.user_id = config['CAPITAL']['user_id']
        self.password = config['CAPITAL']['password']
        self.db_config = dict(config['DATABASE'])
        logging.info("設定檔載入成功。")

    def _initialize_com_objects(self):
        try:
            self.skC = comtypes.client.CreateObject(sk.SKCenterLib, interface=sk.ISKCenterLib)
            self.skQ = comtypes.client.CreateObject(sk.SKQuoteLib, interface=sk.ISKQuoteLib)
            self.skOSQ = comtypes.client.CreateObject(sk.SKOSQuoteLib, interface=sk.ISKOSQuoteLib)
            self.skO = comtypes.client.CreateObject(sk.SKOrderLib, interface=sk.ISKOrderLib)
            self.skR = comtypes.client.CreateObject(sk.SKReplyLib, interface=sk.ISKReplyLib)

            # 建立事件處理器
            self.reply_events = SKReplyEvents()
            self.quote_events = SKQuoteEvents(self)
            self.osquote_events = SKOSQuoteEvents(self)
            self.order_events = SKOrderEvents(self)

            # 註冊事件
            self.reply_connection = comtypes.client.GetEvents(self.skR, self.reply_events)
            self.quote_connection = comtypes.client.GetEvents(self.skQ, self.quote_events)
            self.osquote_connection = comtypes.client.GetEvents(self.skOSQ, self.osquote_events)
            self.order_connection = comtypes.client.GetEvents(self.skO, self.order_events)

            logging.info("COM 物件及事件處理器初始化成功。")
        except Exception as e:
            logging.error(f"初始化 COM 物件時發生錯誤: {e}")
            raise

    def _initialize_database(self):
        try:
            with pymysql.connect(**self.db_config) as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS domestic_futures (
                            product_id VARCHAR(20) PRIMARY KEY,
                            name VARCHAR(50),
                            exchange VARCHAR(10)
                        );
                    """)
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS overseas_futures (
                            product_id VARCHAR(20) PRIMARY KEY,
                            name VARCHAR(100),
                            exchange VARCHAR(20)
                        );
                    """)
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS daily_kline (
                            product_id VARCHAR(20),
                            date DATE,
                            open DECIMAL(12, 5),
                            high DECIMAL(12, 5),
                            low DECIMAL(12, 5),
                            close DECIMAL(12, 5),
                            volume BIGINT,
                            PRIMARY KEY (product_id, date)
                        );
                    """)
                conn.commit()
            logging.info("資料庫及資料表確認/建立成功。")
        except Exception as e:
            logging.error(f"初始化資料庫時發生錯誤: {e}")
            raise

    # --- 步驟函數 ---

    def _inspect_capital_chart_schema(self):
        try:
            with pymysql.connect(**self.db_config) as conn:
                with conn.cursor() as cursor:
                    cursor.execute("DESCRIBE capital_chart")
                    columns = cursor.fetchall()
                    logging.info(f"capital_chart schema: {columns}")
        except Exception as e:
            logging.error(f"無法讀取 capital_chart 結構: {e}")

    def step_1_login(self):
        self._inspect_capital_chart_schema()
        logging.info("=== 步驟 1: 登入 ===")
        nCode = self.skC.SKCenterLib_Login(self.user_id, self.password)
        if nCode != 0 and nCode != 2003:
            logging.error(f"登入失敗, 代碼: {nCode}")
            self.root.quit()
            return
        logging.info(f"登入指令已發送, 代碼: {nCode}")
        
        # 初始化下單元件
        nCode = self.skO.SKOrderLib_Initialize()
        logging.info(f"下單物件初始化: {nCode}")
        
        self.root.after(1000, self.step_2_connect_domestic)

    def step_2_connect_domestic(self):
        logging.info("=== 步驟 2: 連接國內報價伺服器 ===")
        nCode = self.skQ.SKQuoteLib_EnterMonitorLONG()
        if nCode != 0:
            logging.error(f"國內連線失敗: {nCode}")
            self.root.quit()
            return
        
        self.wait_start_time = time.time()
        self.check_domestic_connection()

    def check_domestic_connection(self):
        if self.domestic_connected:
            logging.info("✅ 國內報價連線及商品載入完成!")
            self.root.after(1000, self.step_3_connect_overseas)
        elif time.time() - self.wait_start_time > 60:
            logging.error("❌ 國內報價連線超時")
            # 嘗試繼續執行?
            self.root.after(1000, self.step_3_connect_overseas)
        else:
            self.root.after(1000, self.check_domestic_connection)

    def step_3_connect_overseas(self):
        logging.info("=== 步驟 3: 連接海外報價伺服器 ===")
        nCode = self.skOSQ.SKOSQuoteLib_EnterMonitorLONG()
        if nCode != 0:
            logging.error(f"海外連線失敗: {nCode}")
            self.root.quit()
            return
        
        self.wait_start_time = time.time()
        self.check_overseas_connection()

    def check_overseas_connection(self):
        if self.overseas_connected:
            logging.info("✅ 海外報價連線及商品載入完成!")
            # 跳過步驟 3.5，因為通用代碼可配合 K 線類型 0 使用
            self.root.after(1000, self.step_4_load_targets)
        elif time.time() - self.wait_start_time > 120: # 延長超時
            logging.error("❌ 海外報價連線超時")
            self.root.after(1000, self.step_4_load_targets)
        else:
            self.root.after(1000, self.check_overseas_connection)

    def step_4_load_targets(self):
        logging.info("=== 步驟 4: 讀取目標商品 (captial_chart) ===")
        try:
            with pymysql.connect(**self.db_config) as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT code, exchange FROM captial_chart WHERE enable = 1")
                    rows = cursor.fetchall()
                    
            if not rows:
                logging.warning("captial_chart 表中沒有啟用的商品。")
                self.root.quit()
                return

            logging.info(f"共讀取到 {len(rows)} 個目標商品。")
            
            for row in rows:
                code, exchange = row
                code = code.strip()
                exchange = exchange.strip()
                
                is_overseas = (exchange != 'TAIFEX')
                
                # 用戶要求暫時跳過國內商品
                if not is_overseas:
                    logging.info(f"跳過國內商品: {code}")
                    continue

                # API 請求格式:
                # 國內: code (例如 TX00)
                # 海外: exchange,code (例如 CME,ES0000)
                request_id = code
                
                if is_overseas:
                     request_id = f"{exchange},{code}"
                
                self.pending_kline_requests.append({
                    'id': request_id, 
                    'code': code, 
                    'exchange': exchange, 
                    'is_overseas': is_overseas
                })
            
            self.root.after(1000, self.step_5_process_kline_requests)
            
        except Exception as e:
            logging.error(f"讀取 captial_chart 失敗: {e}")
            self.root.quit()

    def step_5_process_kline_requests(self):
        if not self.pending_kline_requests:
            logging.info("=== 所有作業完成 ===")
            self.root.quit()
            return

        req = self.pending_kline_requests.pop(0)
        self.current_request = req 
        self.current_kline_id = req['id'] 
        self.kline_received = False
        
        logging.info(f"請求 K線: {req['exchange']} - {req['code']}")
        
        if req['is_overseas']:
            # 嘗試格式 1: 使用步驟 4 準備的 ID (可能包含映射合約)
            request_id = req['id']
            logging.info(f"嘗試海外 K線請求: {request_id}")
            nCode = self.skOSQ.SKOSQuoteLib_RequestKLine(request_id, 0)
            
            if nCode == 1042:
                logging.warning(f"格式 {request_id} 失敗 (1042)，嘗試只傳代碼...")
                # 嘗試格式 2: 僅使用代碼 (使用可能已映射的代碼)
                # 如果 request_id 是 交易所,代碼 格式，需提取代碼部分
                if ',' in request_id:
                    code_only = request_id.split(',')[1]
                else:
                    code_only = req['code'] # 退回使用原始代碼
                
                request_id = code_only
                logging.info(f"嘗試海外 K線請求: {request_id}")
                nCode = self.skOSQ.SKOSQuoteLib_RequestKLine(request_id, 0)
                
            if nCode == 1042 and req['exchange'] != 'CME':
                 # 嘗試格式 3: 強制使用 CME (許多期貨通用)
                request_id = f"CME,{req['code']}"
                logging.info(f"嘗試海外 K線請求: {request_id}")
                nCode = self.skOSQ.SKOSQuoteLib_RequestKLine(request_id, 0)
        else:
            nCode = self.skQ.SKQuoteLib_RequestKLine(req['id'], 4, 1)
            
        if nCode != 0:
            logging.error(f"請求 K線失敗: {nCode}")
            self.root.after(100, self.step_5_process_kline_requests)
        else:
            self.wait_start_time = time.time()
            self.check_kline_data()

    def check_kline_data(self):
        if self.kline_received:
            # logging.info(f"✅ 收到 K線數據: {self.current_kline_id}") # 為提升效能已移除
            self.root.after(500, self.step_5_process_kline_requests) 
        elif time.time() - self.wait_start_time > 60: # 延長大數據量的超時時間
            logging.warning(f"等待 K線數據超時: {self.current_kline_id}")
            self.root.after(100, self.step_5_process_kline_requests)
        else:
            self.root.after(200, self.check_kline_data)

    def _save_kline_to_db(self, df):
        if df.empty: return
        try:
            with pymysql.connect(**self.db_config) as conn:
                with conn.cursor() as cursor:
                    # 資料表: captial_kline
                    # 欄位: date, code, volume, open, high, low, close, exchange
                    sql = """
                        INSERT INTO captial_kline 
                        (`date`, `code`, `volume`, `open`, `high`, `low`, `close`, `exchange`) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE 
                        `volume`=VALUES(`volume`), `open`=VALUES(`open`), `high`=VALUES(`high`), 
                        `low`=VALUES(`low`), `close`=VALUES(`close`)
                    """
                    data_tuples = [tuple(x) for x in df.to_numpy()]
                    cursor.executemany(sql, data_tuples)
                conn.commit()
            # logging.info(f"儲存 {len(df)} 筆 K線至 captial_kline") # 為提升效能已移除
        except Exception as e:
            logging.error(f"DB Error: {e}")

    def _parse_kline(self, kline_str, code, exchange):
        if not kline_str: return pd.DataFrame()
        data = []
        for line in kline_str.strip().split(';'):
            if line:
                parts = line.split(',')
                # 格式: 日期,開盤,最高,最低,收盤,成交量
                if len(parts) == 6:
                    try:
                        # 日期格式可能不同？根據日誌假設為 YYYY/MM/DD
                        date_str = parts[0].strip()
                        # 將 2025/11/20 轉換為 2025-11-20
                        date_obj = datetime.strptime(date_str, '%Y/%m/%d')
                        
                        data.append({
                            'date': date_obj.strftime('%Y-%m-%d'),
                            'code': code,
                            'volume': int(parts[5]),
                            'open': float(parts[1]),
                            'high': float(parts[2]),
                            'low': float(parts[3]),
                            'close': float(parts[4]),
                            'exchange': exchange
                        })
                    except (ValueError, IndexError):
                        pass
        return pd.DataFrame(data)

# --- 事件處理器 ---

class SKReplyEvents:
    def OnReplyMessage(self, bstrUserID, bstrMessages):
        logging.info(f"[SKReplyLib] {bstrUserID}: {bstrMessages}")
        return -1

class SKQuoteEvents:
    def __init__(self, app):
        self.app = app

    def OnConnection(self, nKind, nCode):
        logging.info(f"[SKQuoteLib] OnConnection: nKind={nKind}, nCode={nCode}")
        if nKind in [3001, 3003]: 
            self.app.domestic_connected = True

    def OnNotifyStockList(self, sMarketNo, bstrStockData):
        pass # 不再使用

    def OnNotifyKLineData(self, bstrStockNo, bstrData):
        # logging.info(f"[SKQuoteLib] 收到 K線: {bstrStockNo}") # 為提升效能已移除
        if bstrStockNo == self.app.current_kline_id:
            self.app.kline_received = True
            df = self.app._parse_kline(bstrData, self.app.current_request['code'], self.app.current_request['exchange'])
            self.app._save_kline_to_db(df)

class SKOSQuoteEvents:
    def __init__(self, app):
        self.app = app

    def OnConnect(self, nCode, nSocketCode):
        logging.info(f"[SKOSQuoteLib] OnConnect: nCode={nCode}")
        if nCode in [3001, 3003]:
            self.app.overseas_connected = True

    def OnKLineData(self, bstrStockNo, bstrData):
        # logging.info(f"[SKOSQuoteLib] 收到海外 K線: {bstrStockNo}") # 為提升效能已移除
        self.app.kline_received = True
        df = self.app._parse_kline(bstrData, self.app.current_request['code'], self.app.current_request['exchange'])
        self.app._save_kline_to_db(df)


class SKOrderEvents:
    def __init__(self, app):
        self.app = app
    def OnOverseaFuture(self, bstrData):
        self.app.overseas_products.append(bstrData)


def main():
    root = tk.Tk()
    root.withdraw() # 隱藏主視窗
    
    try:
        app = FuturesDataUpdater(root)
        root.mainloop()
    except Exception as e:
        logging.critical(f"Error: {e}")

if __name__ == "__main__":
    main()
