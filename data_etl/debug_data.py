"""檢查分鐘K線資料的詳細內容"""
from cycle_data_updater import CycleDataUpdater
import pymysql
import configparser

# 載入設定
config = configparser.ConfigParser()
config.read('config.ini', encoding='utf-8')
db_config = dict(config['DATABASE'])

print("=" * 80)
print("分鐘K線資料詳細檢查")
print("=" * 80)

# 直接查詢資料庫
conn = pymysql.connect(**db_config)
cursor = conn.cursor(pymysql.cursors.DictCursor)

# 查詢 TX00 最近7天的分鐘K線
print("\n【查詢 captial_kline 表】")
print("-" * 80)
cursor.execute("""
    SELECT `date`, code, exchange, volume, open, high, low, close
    FROM captial_kline
    WHERE code = 'TX00' AND exchange = 'TAIFEX'
    ORDER BY `date` DESC
    LIMIT 20
""")

klines = cursor.fetchall()
print(f"找到 {len(klines)} 筆資料（顯示前20筆）\n")

if klines:
    print(f"{'序號':<5} {'時間':<20} {'開':<10} {'高':<10} {'低':<10} {'收':<10} {'量':<10}")
    print("-" * 80)
    for i, k in enumerate(klines, 1):
        print(f"{i:<5} {str(k['date']):<20} {k['open']:<10.2f} {k['high']:<10.2f} "
              f"{k['low']:<10.2f} {k['close']:<10.2f} {k['volume']:<10}")
else:
    print("❌ 沒有資料")

# 檢查時間間隔
print("\n【時間間隔分析】")
print("-" * 80)
if len(klines) > 1:
    print(f"{'從':<20} {'到':<20} {'間隔':<20}")
    print("-" * 80)
    for i in range(len(klines)-1):
        time_diff = klines[i]['date'] - klines[i+1]['date']
        print(f"{str(klines[i+1]['date']):<20} {str(klines[i]['date']):<20} {str(time_diff):<20}")

# 檢查資料表結構
print("\n【captial_kline 表結構】")
print("-" * 80)
cursor.execute("DESCRIBE captial_kline")
columns = cursor.fetchall()
for col in columns:
    print(f"{col['Field']:<20} {col['Type']:<20} {col['Null']:<10} {col['Key']:<10}")

# 統計資料
print("\n【資料統計】")
print("-" * 80)
cursor.execute("""
    SELECT 
        code,
        exchange,
        COUNT(*) as total,
        MIN(`date`) as first_date,
        MAX(`date`) as last_date,
        DATE(MIN(`date`)) as first_day,
        DATE(MAX(`date`)) as last_day
    FROM captial_kline
    WHERE code = 'TX00' AND exchange = 'TAIFEX'
    GROUP BY code, exchange
""")

stats = cursor.fetchone()
if stats:
    print(f"商品: {stats['code']} ({stats['exchange']})")
    print(f"總筆數: {stats['total']}")
    print(f"最早時間: {stats['first_date']}")
    print(f"最晚時間: {stats['last_date']}")
    print(f"最早日期: {stats['first_day']}")
    print(f"最晚日期: {stats['last_day']}")
    
    # 計算天數
    if stats['first_day'] and stats['last_day']:
        days = (stats['last_day'] - stats['first_day']).days + 1
        print(f"涵蓋天數: {days} 天")
        if stats['total'] > 0:
            print(f"平均每天: {stats['total'] / days:.1f} 筆")

# 按日期統計
print("\n【按日期統計】")
print("-" * 80)
cursor.execute("""
    SELECT 
        DATE(`date`) as trade_date,
        COUNT(*) as count,
        MIN(`date`) as first_time,
        MAX(`date`) as last_time
    FROM captial_kline
    WHERE code = 'TX00' AND exchange = 'TAIFEX'
    GROUP BY DATE(`date`)
    ORDER BY trade_date DESC
    LIMIT 10
""")

daily_stats = cursor.fetchall()
if daily_stats:
    print(f"{'日期':<15} {'筆數':<10} {'第一筆時間':<20} {'最後一筆時間':<20}")
    print("-" * 80)
    for row in daily_stats:
        print(f"{str(row['trade_date']):<15} {row['count']:<10} "
              f"{str(row['first_time']):<20} {str(row['last_time']):<20}")

conn.close()

print("\n" + "=" * 80)
print("檢查完成")
print("=" * 80)
