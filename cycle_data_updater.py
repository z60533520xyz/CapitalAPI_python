import pymysql
import configparser
import logging
import os
from datetime import datetime, timedelta
from typing import List, Dict

# 日誌配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('cycle_updater.log', 'a', 'utf-8')
    ]
)

class CycleDataUpdater:
    """週期K線資料更新器"""
    
    def __init__(self, config_path='config.ini'):
        self._load_config(config_path)
        
    def _load_config(self, config_path):
        """載入設定檔"""
        config = configparser.ConfigParser()
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"設定檔 '{config_path}' 不存在。")
        config.read(config_path, encoding='utf-8')
        
        self.db_config = dict(config['DATABASE'])
        logging.info("設定檔載入成功。")
    
    def get_db_connection(self):
        """取得資料庫連線"""
        return pymysql.connect(**self.db_config)
    
    def get_minute_klines(self, code: str, exchange: str, days: int = 30) -> List[Dict]:
        """
        從 captial_kline 表取得1分鐘K線資料
        
        Args:
            code: 商品代碼
            exchange: 交易所
            days: 取得最近幾天的資料
            
        Returns:
            K線資料列表
        """
        try:
            with self.get_db_connection() as conn:
                with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                    start_date = datetime.now() - timedelta(days=days)
                    sql = """
                        SELECT `date`, `code`, `exchange`, `volume`, `open`, `high`, `low`, `close`
                        FROM captial_kline
                        WHERE code = %s AND exchange = %s AND `date` >= %s
                        ORDER BY `date` ASC
                    """
                    cursor.execute(sql, (code, exchange, start_date))
                    results = cursor.fetchall()
                    logging.info(f"取得 {code} ({exchange}) 共 {len(results)} 筆1分鐘K線資料")
                    return results
        except Exception as e:
            logging.error(f"取得1分鐘K線資料失敗: {e}")
            return []
    
    def generate_cycle_klines(self, klines: List[Dict], cycle: int) -> List[Dict]:
        """
        根據分鐘K線生成週期K線
        
        Args:
            klines: 分鐘K線資料
            cycle: 週期類型 1.1分 2.5分 3.15分 4.30分 5.60分 6.日 7.周 8.月 9.2小時
            
        Returns:
            週期K線資料列表
        """
        if not klines:
            return []
        
        result = []
        
        if cycle == 1:
            # 1分鐘K線 - 直接轉換
            result = self._generate_1min_klines(klines)
        elif cycle == 2:
            # 5分鐘K線
            result = self._generate_nmin_klines(klines, 5)
        elif cycle == 3:
            # 15分鐘K線
            result = self._generate_nmin_klines(klines, 15)
        elif cycle == 4:
            # 30分鐘K線
            result = self._generate_nmin_klines(klines, 30)
        elif cycle == 5:
            # 60分鐘K線
            result = self._generate_nmin_klines(klines, 60)
        elif cycle == 6:
            # 日K線
            result = self._generate_daily_klines(klines)
        elif cycle == 7:
            # 週K線
            result = self._generate_weekly_klines(klines)
        elif cycle == 8:
            # 月K線
            result = self._generate_monthly_klines(klines)
        elif cycle == 9:
            # 2小時K線
            result = self._generate_nmin_klines(klines, 120)
        
        return result
    
    def _generate_1min_klines(self, klines: List[Dict]) -> List[Dict]:
        """生成1分鐘K線"""
        result = []
        for kline in klines:
            result.append({
                'date': kline['date'],
                'code': kline['code'],
                'exchange': kline['exchange'],
                'cycle': 1,
                'volume': kline['volume'],
                'open': kline['open'],
                'high': kline['high'],
                'low': kline['low'],
                'close': kline['close']
            })
        return result
    
    def _generate_nmin_klines(self, klines: List[Dict], minutes: int) -> List[Dict]:
        """
        生成N分鐘K線
        
        Args:
            klines: 分鐘K線資料
            minutes: 週期分鐘數
        """
        if not klines:
            return []
        
        result = []
        exchange = klines[0]['exchange']
        code = klines[0]['code']
        
        # 計算週期編號
        cycle_map = {5: 2, 15: 3, 30: 4, 60: 5, 120: 9}
        cycle = cycle_map.get(minutes, 1)
        
        # 取得時間範圍
        min_date = min(k['date'] for k in klines)
        max_date = max(k['date'] for k in klines)
        
        # 從第一個時間點開始，按週期遍歷
        current_time = self._round_time_to_cycle(min_date, minutes, exchange)
        
        while current_time <= max_date:
            # 取得該週期內的所有K線
            period_start = current_time - timedelta(minutes=minutes)
            period_klines = [
                k for k in klines 
                if period_start < k['date'] <= current_time
            ]
            
            if period_klines:
                # 合併該週期的K線
                result.append({
                    'date': current_time,
                    'code': code,
                    'exchange': exchange,
                    'cycle': cycle,
                    'volume': sum(k['volume'] for k in period_klines),
                    'open': period_klines[0]['open'],
                    'high': max(k['high'] for k in period_klines),
                    'low': min(k['low'] for k in period_klines),
                    'close': period_klines[-1]['close']
                })
            
            current_time += timedelta(minutes=minutes)
        
        return result
    
    def _round_time_to_cycle(self, dt: datetime, minutes: int, exchange: str) -> datetime:
        """
        將時間對齊到週期邊界
        
        Args:
            dt: 原始時間
            minutes: 週期分鐘數
            exchange: 交易所
        """
        # 取得日期部分
        date_part = dt.date()
        
        # 根據交易所調整起始時間
        if exchange == 'TAIFEX':
            # 台灣期貨交易時間 08:45-13:45, 15:00-05:00
            if dt.hour < 8 or (dt.hour == 8 and dt.minute < 45):
                start_time = datetime.combine(date_part, datetime.min.time()) + timedelta(hours=8, minutes=45)
            else:
                start_time = datetime.combine(date_part, datetime.min.time()) + timedelta(hours=8, minutes=45)
        else:
            # 其他交易所從整點開始
            start_time = datetime.combine(date_part, datetime.min.time())
        
        # 計算從起始時間到當前時間的分鐘數
        minutes_diff = int((dt - start_time).total_seconds() / 60)
        
        # 對齊到週期
        aligned_minutes = ((minutes_diff // minutes) + 1) * minutes
        
        return start_time + timedelta(minutes=aligned_minutes)
    
    def _generate_daily_klines(self, klines: List[Dict]) -> List[Dict]:
        """生成日K線"""
        if not klines:
            return []
        
        result = []
        exchange = klines[0]['exchange']
        code = klines[0]['code']
        
        # 按日期分組
        daily_groups = {}
        for kline in klines:
            date_key = kline['date'].date()
            if date_key not in daily_groups:
                daily_groups[date_key] = []
            daily_groups[date_key].append(kline)
        
        # 生成日K線
        for date_key, day_klines in sorted(daily_groups.items()):
            # 設定該日的代表時間
            if exchange == 'TAIFEX':
                # 台灣期貨使用 13:45 作為日K線時間
                day_time = datetime.combine(date_key, datetime.min.time()) + timedelta(hours=13, minutes=45)
            else:
                # 其他交易所使用當日最後一筆時間
                day_time = max(k['date'] for k in day_klines)
            
            result.append({
                'date': day_time,
                'code': code,
                'exchange': exchange,
                'cycle': 6,
                'volume': sum(k['volume'] for k in day_klines),
                'open': day_klines[0]['open'],
                'high': max(k['high'] for k in day_klines),
                'low': min(k['low'] for k in day_klines),
                'close': day_klines[-1]['close']
            })
        
        return result
    
    def _generate_weekly_klines(self, klines: List[Dict]) -> List[Dict]:
        """生成週K線"""
        if not klines:
            return []
        
        # 先生成日K線
        daily_klines = self._generate_daily_klines(klines)
        if not daily_klines:
            return []
        
        result = []
        exchange = daily_klines[0]['exchange']
        code = daily_klines[0]['code']
        
        # 按週分組 (週一到週日)
        weekly_groups = {}
        for kline in daily_klines:
            # 取得該日期所屬週的週一
            date = kline['date'].date()
            days_since_monday = date.weekday()
            monday = date - timedelta(days=days_since_monday)
            
            if monday not in weekly_groups:
                weekly_groups[monday] = []
            weekly_groups[monday].append(kline)
        
        # 生成週K線
        for monday, week_klines in sorted(weekly_groups.items()):
            # 設定該週的代表時間 (週一開盤時間)
            if exchange == 'TAIFEX':
                week_time = datetime.combine(monday, datetime.min.time()) + timedelta(hours=8, minutes=45)
            else:
                week_time = datetime.combine(monday, datetime.min.time())
            
            result.append({
                'date': week_time,
                'code': code,
                'exchange': exchange,
                'cycle': 7,
                'volume': sum(k['volume'] for k in week_klines),
                'open': week_klines[0]['open'],
                'high': max(k['high'] for k in week_klines),
                'low': min(k['low'] for k in week_klines),
                'close': week_klines[-1]['close']
            })
        
        return result
    
    def _generate_monthly_klines(self, klines: List[Dict]) -> List[Dict]:
        """生成月K線"""
        if not klines:
            return []
        
        result = []
        exchange = klines[0]['exchange']
        code = klines[0]['code']
        
        # 按月份分組
        monthly_groups = {}
        for kline in klines:
            month_key = (kline['date'].year, kline['date'].month)
            if month_key not in monthly_groups:
                monthly_groups[month_key] = []
            monthly_groups[month_key].append(kline)
        
        # 生成月K線
        for (year, month), month_klines in sorted(monthly_groups.items()):
            # 設定該月的代表時間 (月初第一天)
            month_time = datetime(year, month, 1)
            
            result.append({
                'date': month_time,
                'code': code,
                'exchange': exchange,
                'cycle': 8,
                'volume': sum(k['volume'] for k in month_klines),
                'open': month_klines[0]['open'],
                'high': max(k['high'] for k in month_klines),
                'low': min(k['low'] for k in month_klines),
                'close': month_klines[-1]['close']
            })
        
        return result
    
    def upsert_cycle_klines(self, cycle_klines: List[Dict]):
        """
        將週期K線資料寫入資料庫 (使用 UPSERT)
        
        Args:
            cycle_klines: 週期K線資料列表
        """
        if not cycle_klines:
            return
        
        try:
            with self.get_db_connection() as conn:
                with conn.cursor() as cursor:
                    sql = """
                        INSERT INTO captial_kline_cycle 
                        (`date`, `code`, `Cycle`, `volume`, `open`, `high`, `low`, `close`, `exchange`)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                        `volume` = VALUES(`volume`),
                        `open` = VALUES(`open`),
                        `high` = VALUES(`high`),
                        `low` = VALUES(`low`),
                        `close` = VALUES(`close`)
                    """
                    
                    data_tuples = [
                        (
                            k['date'],
                            k['code'],
                            k['cycle'],
                            k['volume'],
                            k['open'],
                            k['high'],
                            k['low'],
                            k['close'],
                            k['exchange']
                        )
                        for k in cycle_klines
                    ]
                    
                    cursor.executemany(sql, data_tuples)
                conn.commit()
                
            logging.info(f"成功寫入 {len(cycle_klines)} 筆週期K線資料")
        except Exception as e:
            logging.error(f"寫入週期K線資料失敗: {e}")
    
    def update_all_cycles_for_product(self, code: str, exchange: str, days: int = 30):
        """
        更新單一商品的所有週期K線
        
        Args:
            code: 商品代碼
            exchange: 交易所
            days: 基準天數（會根據週期類型自動調整）
        """
        logging.info(f"開始更新 {code} ({exchange}) 的週期K線資料...")
        
        # 定義每個週期所需的最小天數
        cycle_days_map = {
            1: 7,      # 1分鐘K線：7天
            2: 7,      # 5分鐘K線：7天
            3: 7,      # 15分鐘K線：7天
            4: 7,      # 30分鐘K線：7天
            5: 7,      # 60分鐘K線：7天
            6: 60,     # 日K線：60天
            7: 180,    # 週K線：180天（約26週）
            8: 365,    # 月K線：365天（12個月）
            9: 14      # 2小時K線：14天
        }
        
        # 生成並寫入各週期K線
        for cycle in range(1, 10):  # 1-9 個週期
            # 計算此週期所需的天數
            required_days = cycle_days_map.get(cycle, days)
            
            logging.info(f"生成週期 {cycle} 的K線（使用 {required_days} 天資料）...")
            
            # 取得對應天數的分鐘K線資料
            minute_klines = self.get_minute_klines(code, exchange, required_days)
            
            if not minute_klines:
                logging.warning(f"{code} ({exchange}) 週期 {cycle} 沒有分鐘K線資料")
                continue
            
            cycle_klines = self.generate_cycle_klines(minute_klines, cycle)
            
            if cycle_klines:
                self.upsert_cycle_klines(cycle_klines)
                logging.info(f"週期 {cycle} 完成，共 {len(cycle_klines)} 筆資料")
            else:
                logging.warning(f"週期 {cycle} 沒有資料")
        
        logging.info(f"{code} ({exchange}) 週期K線更新完成")
    
    def update_all_enabled_products(self, days: int = 30):
        """
        更新所有啟用商品的週期K線
        
        Args:
            days: 更新最近幾天的資料
        """
        try:
            with self.get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT code, exchange 
                        FROM captial_chart 
                        WHERE enable = 1
                    """)
                    products = cursor.fetchall()
            
            logging.info(f"共找到 {len(products)} 個啟用的商品")
            
            for product in products:
                code, exchange = product
                try:
                    self.update_all_cycles_for_product(code, exchange, days)
                except Exception as e:
                    logging.error(f"更新 {code} ({exchange}) 失敗: {e}")
                    continue
            
            logging.info("所有商品週期K線更新完成")
            
        except Exception as e:
            logging.error(f"取得商品列表失敗: {e}")


def main():
    """主程式"""
    try:
        updater = CycleDataUpdater()
        
        # 更新所有啟用商品的週期K線 (最近30天)
        updater.update_all_enabled_products(days=30)
        
        logging.info("週期K線更新程式執行完成")
        
    except Exception as e:
        logging.critical(f"程式執行錯誤: {e}")


if __name__ == "__main__":
    main()
