import pymysql
import configparser
import logging
import os
from datetime import datetime, timedelta
from typing import List, Dict

# 日誌配置
from logging.handlers import RotatingFileHandler
import os

# 確保 log 資料夾存在
log_dir = 'log'
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        RotatingFileHandler(os.path.join(log_dir, 'cycle_updater.log'), maxBytes=5*1024*1024, backupCount=3, encoding='utf-8')
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
    
    def get_minute_klines(self, code: str, exchange: str, days: int = 30, batch_size: int = 50000) -> List[Dict]:
        """
        從 captial_kline 表批次取得1分鐘K線資料
        
        Args:
            code: 商品代碼
            exchange: 交易所
            days: 取得最近幾天的資料
            batch_size: 每批次讀取的筆數
            
        Returns:
            K線資料列表
        """
        try:
            # 先查詢總筆數
            with self.get_db_connection() as conn:
                with conn.cursor() as cursor:
                    start_date = datetime.now() - timedelta(days=days)
                    count_sql = """
                        SELECT COUNT(*) as total
                        FROM captial_kline
                        WHERE code = %s AND exchange = %s AND `date` >= %s
                    """
                    cursor.execute(count_sql, (code, exchange, start_date))
                    total = cursor.fetchone()[0]
            
            if total == 0:
                logging.info(f"{code} ({exchange}) 無分鐘K線資料")
                return []
            
            logging.info(f"準備讀取 {code} ({exchange}) 共 {total} 筆1分鐘K線資料（批次大小: {batch_size}）...")
            
            # 批次讀取資料
            results = []
            with self.get_db_connection() as conn:
                with conn.cursor(pymysql.cursors.SSCursor) as cursor:
                    sql = """
                        SELECT `date`, `code`, `exchange`, `volume`, `open`, `high`, `low`, `close`
                        FROM captial_kline
                        WHERE code = %s AND exchange = %s AND `date` >= %s
                        ORDER BY `date` ASC
                    """
                    cursor.execute(sql, (code, exchange, start_date))
                    
                    # 批次讀取
                    batch_count = 0
                    while True:
                        rows = cursor.fetchmany(batch_size)
                        if not rows:
                            break
                        
                        # 轉換為字典格式
                        for row in rows:
                            results.append({
                                'date': row[0],
                                'code': row[1],
                                'exchange': row[2],
                                'volume': row[3],
                                'open': row[4],
                                'high': row[5],
                                'low': row[6],
                                'close': row[7]
                            })
                        
                        batch_count += len(rows)
                        percentage = (batch_count / total) * 100
                        logging.info(f"  讀取進度: {batch_count}/{total} ({percentage:.1f}%)")
            
            logging.info(f"✓ 成功讀取 {len(results)} 筆1分鐘K線資料")
            return results
        except Exception as e:
            logging.error(f"取得1分鐘K線資料失敗: {e}")
            return []
    
    def get_last_cycle_kline_date(self, code: str, exchange: str, cycle: int):
        """
        查詢指定商品、交易所、週期的最後一筆K線日期
        
        Args:
            code: 商品代碼
            exchange: 交易所
            cycle: 週期類型
            
        Returns:
            最後一筆K線的日期，若無資料則返回 None
        """
        try:
            with self.get_db_connection() as conn:
                with conn.cursor() as cursor:
                    sql = """
                        SELECT MAX(`date`) as last_date
                        FROM captial_kline_cycle
                        WHERE code = %s AND exchange = %s AND Cycle = %s
                    """
                    cursor.execute(sql, (code, exchange, cycle))
                    result = cursor.fetchone()
                    return result[0] if result and result[0] else None
        except Exception as e:
            logging.error(f"查詢最後週期K線日期失敗: {e}")
            return None
    
    def get_earliest_minute_kline_date(self, code: str, exchange: str):
        """
        查詢指定商品、交易所的最早一筆分鐘K線日期
        
        Args:
            code: 商品代碼
            exchange: 交易所
            
        Returns:
            最早一筆K線的日期，若無資料則返回 None
        """
        try:
            with self.get_db_connection() as conn:
                with conn.cursor() as cursor:
                    sql = """
                        SELECT MIN(`date`) as earliest_date
                        FROM captial_kline
                        WHERE code = %s AND exchange = %s
                    """
                    cursor.execute(sql, (code, exchange))
                    result = cursor.fetchone()
                    return result[0] if result and result[0] else None
        except Exception as e:
            logging.error(f"查詢最早分鐘K線日期失敗: {e}")
            return None
    
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
        生成N分鐘K線 (優化版：直接遍歷資料)
        
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
        
        logging.info(f"  正在生成 {minutes} 分鐘K線 (共 {len(klines)} 筆原始資料)...")
        
        # 初始化
        current_cycle_klines = []
        # 設定第一個週期的結束時間
        current_cycle_end = self._round_time_to_cycle(klines[0]['date'], minutes, exchange)
        
        total = len(klines)
        
        for i, kline in enumerate(klines):
            # 如果當前K線在當前週期內 (注意：時間是對齊到週期結束時間)
            if kline['date'] <= current_cycle_end:
                current_cycle_klines.append(kline)
            else:
                # 結算上一個週期
                if current_cycle_klines:
                    result.append({
                        'date': current_cycle_end,
                        'code': code,
                        'exchange': exchange,
                        'cycle': cycle,
                        'volume': sum(k['volume'] for k in current_cycle_klines),
                        'open': current_cycle_klines[0]['open'],
                        'high': max(k['high'] for k in current_cycle_klines),
                        'low': min(k['low'] for k in current_cycle_klines),
                        'close': current_cycle_klines[-1]['close']
                    })
                
                # 開始新週期
                # 重新計算新週期的結束時間
                current_cycle_end = self._round_time_to_cycle(kline['date'], minutes, exchange)
                current_cycle_klines = [kline]
            
            # 進度顯示 (每5萬筆顯示一次)
            if (i + 1) % 50000 == 0:
                percentage = ((i + 1) / total) * 100
                logging.info(f"  生成進度: {i + 1}/{total} ({percentage:.1f}%)")
        
        # 處理最後一個週期
        if current_cycle_klines:
            result.append({
                'date': current_cycle_end,
                'code': code,
                'exchange': exchange,
                'cycle': cycle,
                'volume': sum(k['volume'] for k in current_cycle_klines),
                'open': current_cycle_klines[0]['open'],
                'high': max(k['high'] for k in current_cycle_klines),
                'low': min(k['low'] for k in current_cycle_klines),
                'close': current_cycle_klines[-1]['close']
            })
        
        return result
    
    def _round_time_to_cycle(self, dt: datetime, minutes: int, exchange: str) -> datetime:
        """
        將時間對齊到週期邊界 (返回週期的結束時間)
        
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
        
        # 對齊到週期 (向上取整)
        # 例如 5分K: 1分->5分, 4分->5分, 5分->5分, 6分->10分
        if minutes_diff > 0:
            aligned_minutes = ((minutes_diff - 1) // minutes + 1) * minutes
        else:
            # 處理負數時間差 (例如跨日或早於起始時間)
            aligned_minutes = ((minutes_diff - 1) // minutes + 1) * minutes
        
        return start_time + timedelta(minutes=aligned_minutes)
    
    def _generate_daily_klines(self, klines: List[Dict]) -> List[Dict]:
        """
        生成日K線
        
        重要：正確處理跨日交易
        - 台灣期貨（TAIFEX）：夜盤從 15:00 開始（跨日）
        - 海外期貨（CME, NYMEX 等）：從 18:00 開始（跨日）
        """
        if not klines:
            return []
        
        result = []
        exchange = klines[0]['exchange']
        code = klines[0]['code']
        
        # 定義交易日起始時間（小時）
        if exchange == 'TAIFEX':
            # 台灣期貨：夜盤從 15:00 開始
            session_start_hour = 15
        else:
            # 海外期貨：從 18:00 開始
            session_start_hour = 18
        
        # 按交易日分組
        logging.info(f"  正在按交易日分組 {len(klines)} 筆分鐘資料...")
        daily_groups = {}
        for i, kline in enumerate(klines):
            dt = kline['date']
            
            # 計算交易日期
            # 如果時間在起始時間之前，歸屬於前一個交易日
            if dt.hour < session_start_hour:
                trading_date = (dt - timedelta(days=1)).date()
            else:
                trading_date = dt.date()
            
            if trading_date not in daily_groups:
                daily_groups[trading_date] = []
            daily_groups[trading_date].append(kline)
            
            # 每處理5萬筆顯示一次進度
            if (i + 1) % 50000 == 0:
                percentage = ((i + 1) / len(klines)) * 100
                logging.info(f"  分組進度: {i + 1}/{len(klines)} ({percentage:.1f}%)")
        
        logging.info(f"  分組完成，共 {len(daily_groups)} 個交易日")
        
        # 生成日K線
        total_days = len(daily_groups)
        for idx, (date_key, day_klines) in enumerate(sorted(daily_groups.items()), 1):
            # 按時間排序（確保開盤和收盤正確）
            day_klines_sorted = sorted(day_klines, key=lambda x: x['date'])
            
            # 設定該日的代表時間
            if exchange == 'TAIFEX':
                # 台灣期貨使用隔日 13:45 作為日K線時間
                day_time = datetime.combine(date_key + timedelta(days=1), datetime.min.time()) + timedelta(hours=13, minutes=45)
            else:
                # 海外期貨使用該交易日的最後一筆時間
                day_time = day_klines_sorted[-1]['date']
            
            result.append({
                'date': day_time,
                'code': code,
                'exchange': exchange,
                'cycle': 6,
                'volume': sum(k['volume'] for k in day_klines_sorted),
                'open': day_klines_sorted[0]['open'],
                'high': max(k['high'] for k in day_klines_sorted),
                'low': min(k['low'] for k in day_klines_sorted),
                'close': day_klines_sorted[-1]['close']
            })
            
            # 每處理100個交易日顯示一次進度
            if idx % 100 == 0:
                percentage = (idx / total_days) * 100
                logging.info(f"  生成進度: {idx}/{total_days} ({percentage:.1f}%)")
        
        return result
    
    def _generate_weekly_klines(self, klines: List[Dict]) -> List[Dict]:
        """生成週K線"""
        if not klines:
            return []
        
        result = []
        exchange = klines[0]['exchange']
        code = klines[0]['code']
        
        # 按週分組（週一到週日）
        logging.info(f"  正在按週分組 {len(klines)} 筆分鐘資料...")
        weekly_groups = {}
        for i, kline in enumerate(klines):
            # 取得該日期所在週的週一日期
            week_start = kline['date'] - timedelta(days=kline['date'].weekday())
            week_key = week_start.date()
            
            if week_key not in weekly_groups:
                weekly_groups[week_key] = []
            weekly_groups[week_key].append(kline)
            
            # 每處理5萬筆顯示一次進度
            if (i + 1) % 50000 == 0:
                percentage = ((i + 1) / len(klines)) * 100
                logging.info(f"  分組進度: {i + 1}/{len(klines)} ({percentage:.1f}%)")
        
        logging.info(f"  分組完成，共 {len(weekly_groups)} 週")
        
        # 生成週K線
        for week_key, week_klines in sorted(weekly_groups.items()):
            # 設定該週的代表時間 (週一)
            week_time = datetime.combine(week_key, datetime.min.time())
            
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
        logging.info(f"  正在按月分組 {len(klines)} 筆分鐘資料...")
        monthly_groups = {}
        for i, kline in enumerate(klines):
            month_key = (kline['date'].year, kline['date'].month)
            if month_key not in monthly_groups:
                monthly_groups[month_key] = []
            monthly_groups[month_key].append(kline)
            
            # 每處理5萬筆顯示一次進度
            if (i + 1) % 50000 == 0:
                percentage = ((i + 1) / len(klines)) * 100
                logging.info(f"  分組進度: {i + 1}/{len(klines)} ({percentage:.1f}%)")
        
        logging.info(f"  分組完成，共 {len(monthly_groups)} 個月")
        
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
    
    def _filter_incomplete_cycles(self, cycle_klines: List[Dict], cycle: int, 
                                   min_requirement: int, minute_klines: List[Dict]) -> List[Dict]:
        """
        過濾掉不完整的週期（主要針對資料範圍起點）
        
        Args:
            cycle_klines: 已生成的週期K線
            cycle: 週期類型 (6=日K, 7=週K, 8=月K)
            min_requirement: 最小資料要求（日K為分鐘數，週K/月K為交易日數）
            minute_klines: 原始分鐘K線資料
            
        Returns:
            過濾後的週期K線
        """
        if not cycle_klines or cycle not in [6, 7, 8]:
            return cycle_klines
        
        result = []
        exchange = cycle_klines[0]['exchange']
        
        # 定義交易日起始時間
        if exchange == 'TAIFEX':
            session_start_hour = 15
        else:
            session_start_hour = 18
        
        for i, kline in enumerate(cycle_klines):
            if cycle == 6:
                # 日K線：檢查該交易日的分鐘資料筆數
                kline_date = kline['date']
                
                # 計算該交易日的範圍
                if exchange == 'TAIFEX':
                    # 台灣期貨：從前一天15:00到當天13:45
                    trading_start = kline_date - timedelta(days=1, hours=0, minutes=15) + timedelta(hours=15)
                    trading_end = kline_date
                else:
                    # 海外期貨：從前一天18:00到當天最後時間
                    trading_start = kline_date - timedelta(days=1) + timedelta(hours=18)
                    trading_end = kline_date + timedelta(hours=23, minutes=59)
                
                # 計算該交易日的分鐘資料筆數
                day_minute_count = sum(
                    1 for mk in minute_klines 
                    if trading_start <= mk['date'] <= trading_end
                )
                
                # 只保留資料充足的日K
                if day_minute_count >= min_requirement:
                    result.append(kline)
                else:
                    logging.debug(f"過濾不完整日K: {kline_date.date()}，僅 {day_minute_count} 筆分鐘資料")
            
            elif cycle == 7:
                # 週K線：檢查該週的交易日數
                # 計算該週包含的日期範圍（週一到週日）
                week_start = kline['date'] - timedelta(days=kline['date'].weekday())
                week_end = week_start + timedelta(days=6, hours=23, minutes=59)
                
                # 計算該週的交易日數（有分鐘資料的日期數）
                trading_dates = set()
                for mk in minute_klines:
                    if week_start <= mk['date'] <= week_end:
                        # 計算交易日期
                        if mk['date'].hour < session_start_hour:
                            trading_date = (mk['date'] - timedelta(days=1)).date()
                        else:
                            trading_date = mk['date'].date()
                        trading_dates.add(trading_date)
                
                # 只保留資料充足的週K
                if len(trading_dates) >= min_requirement:
                    result.append(kline)
                else:
                    logging.debug(f"過濾不完整週K: {kline['date'].date()}，僅 {len(trading_dates)} 個交易日")
            
            elif cycle == 8:
                # 月K線：檢查該月的交易日數
                year, month = kline['date'].year, kline['date'].month
                
                # 計算該月的交易日數
                trading_dates = set()
                for mk in minute_klines:
                    if mk['date'].year == year and mk['date'].month == month:
                        # 計算交易日期
                        if mk['date'].hour < session_start_hour:
                            trading_date = (mk['date'] - timedelta(days=1)).date()
                        else:
                            trading_date = mk['date'].date()
                        trading_dates.add(trading_date)
                
                # 只保留資料充足的月K
                if len(trading_dates) >= min_requirement:
                    result.append(kline)
                else:
                    logging.debug(f"過濾不完整月K: {year}-{month:02d}，僅 {len(trading_dates)} 個交易日")
        
        if len(result) < len(cycle_klines):
            logging.info(f"週期 {cycle} 過濾了 {len(cycle_klines) - len(result)} 筆不完整資料")
        
        return result
    
    def upsert_cycle_klines(self, cycle_klines: List[Dict], batch_size: int = 1000):
        """
        將週期K線資料批次寫入資料庫 (使用 UPSERT)
        
        Args:
            cycle_klines: 週期K線資料列表
            batch_size: 每批次寫入的筆數
        """
        if not cycle_klines:
            return
        
        total = len(cycle_klines)
        logging.info(f"準備寫入 {total} 筆週期K線資料（批次大小: {batch_size}）...")
        
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
                    
                    # 批次處理
                    for i in range(0, total, batch_size):
                        batch = cycle_klines[i:i + batch_size]
                        
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
                            for k in batch
                        ]
                        
                        cursor.executemany(sql, data_tuples)
                        conn.commit()
                        
                        # 顯示進度
                        progress = min(i + batch_size, total)
                        percentage = (progress / total) * 100
                        logging.info(f"  寫入進度: {progress}/{total} ({percentage:.1f}%)")
                
            logging.info(f"✓ 成功寫入 {total} 筆週期K線資料")
        except Exception as e:
            logging.error(f"寫入週期K線資料失敗: {e}")
    
    def update_all_cycles_for_product(self, code: str, exchange: str, days: int = 30):
        """
        更新單一商品的所有週期K線（智能增量更新）
        
        策略：
        - 初次執行（週期K表為空）：回溯所有歷史資料
        - 後續執行：僅更新未完成的週期（例如當前進行中的週、月）
        
        Args:
            code: 商品代碼
            exchange: 交易所
            days: 基準天數（僅在無法判斷時使用）
        """
        logging.info(f"開始更新 {code} ({exchange}) 的週期K線資料...")
        
        # 定義每個週期所需的最小天數（用於初次執行）
        cycle_days_map = {
            1: 7,      # 1分鐘K線：7天
            2: 7,      # 5分鐘K線：7天
            3: 7,      # 15分鐘K線：7天
            4: 7,      # 30分鐘K線：7天
            5: 7,      # 60分鐘K線：7天
            6: 90,     # 日K線：90天
            7: 180,    # 週K線：180天（約26週）
            8: 730,    # 月K線：730天（24個月，確保有足夠歷史）
            9: 14      # 2小時K線：14天
        }
        
        # 定義增量更新時的回溯天數（用於後續執行）
        incremental_days_map = {
            1: 2,      # 1分鐘K線：2天
            2: 2,      # 5分鐘K線：2天
            3: 2,      # 15分鐘K線：2天
            4: 2,      # 30分鐘K線：2天
            5: 2,      # 60分鐘K線：2天
            6: 5,      # 日K線：5天
            7: 14,     # 週K線：14天（確保覆蓋當前週）
            8: 45,     # 月K線：45天（確保覆蓋當前月）
            9: 3       # 2小時K線：3天
        }
        
        # 定義完整週期所需的最小資料筆數/交易日數
        min_data_requirements = {
            6: 15,     # 日K線：至少15筆分鐘資料（約1小時交易）
            7: 3,      # 週K線：至少3個交易日
            8: 10      # 月K線：至少10個交易日
        }
        
        # 生成並寫入各週期K線
        total_cycles = 9
        for cycle in range(1, 10):  # 1-9 個週期
            logging.info(f"\n{'='*60}")
            logging.info(f"處理週期 {cycle}/{total_cycles}")
            logging.info(f"{'='*60}")
            
            # 檢查該週期是否已有歷史資料
            last_cycle_date = self.get_last_cycle_kline_date(code, exchange, cycle)
            
            if last_cycle_date:
                # 有資料：增量更新模式
                required_days = incremental_days_map.get(cycle, days)
                logging.info(f"週期 {cycle} 增量更新（最後資料: {last_cycle_date.date()}，回溯 {required_days} 天）...")
            else:
                # 無資料：初次執行模式
                # 查詢 captial_kline 表中最早的資料時間
                earliest_date = self.get_earliest_minute_kline_date(code, exchange)
                
                if earliest_date:
                    # 計算從最早資料到現在的天數
                    total_days = (datetime.now() - earliest_date).days + 1
                    
                    # 使用實際的歷史範圍，但設定一個合理的上限（例如 3650 天 = 10 年）
                    required_days = min(total_days, 3650)
                    
                    logging.info(f"週期 {cycle} 初次生成（最早資料: {earliest_date.date()}，回溯 {required_days} 天，涵蓋所有歷史）...")
                else:
                    # 如果連分鐘K線都沒有，使用預設值
                    required_days = cycle_days_map.get(cycle, days)
                    logging.info(f"週期 {cycle} 初次生成（無歷史資料，使用預設 {required_days} 天）...")
            
            # 取得對應天數的分鐘K線資料
            minute_klines = self.get_minute_klines(code, exchange, required_days)
            
            if not minute_klines:
                logging.warning(f"{code} ({exchange}) 週期 {cycle} 沒有分鐘K線資料")
                continue
            
            # 生成週期K線
            logging.info(f"開始生成週期 {cycle} K線...")
            cycle_klines = self.generate_cycle_klines(minute_klines, cycle)
            logging.info(f"生成完成，共 {len(cycle_klines) if cycle_klines else 0} 筆週期K線")
            
            # 對於日K、週K、月K，過濾掉不完整的週期
            if cycle in min_data_requirements and cycle_klines:
                logging.info(f"開始過濾不完整週期（最小要求: {min_data_requirements[cycle]}）...")
                cycle_klines = self._filter_incomplete_cycles(
                    cycle_klines, 
                    cycle, 
                    min_data_requirements[cycle],
                    minute_klines
                )
            
            if cycle_klines:
                self.upsert_cycle_klines(cycle_klines)
                logging.info(f"✓ 週期 {cycle} 完成，共 {len(cycle_klines)} 筆資料")
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
