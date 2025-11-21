# 週期K線更新器 - 快速參考

## 檔案說明

| 檔案 | 說明 |
|------|------|
| `cycle_data_updater.py` | 主程式：週期K線資料更新器 |
| `test_cycle_updater.py` | 測試腳本：互動式測試工具 |
| `integrated_updater.py` | 整合腳本：自動執行分鐘K線+週期K線更新 |
| `README_cycle_updater.md` | 詳細說明文件 |
| `QUICK_REFERENCE.md` | 本檔案：快速參考 |

## 快速開始

### 1. 測試單一商品

```bash
python test_cycle_updater.py
# 選擇選項 1，輸入商品代碼和交易所
```

### 2. 更新所有商品（當天）

```bash
python cycle_data_updater.py
```

### 3. 更新所有商品（指定天數）

```python
from cycle_data_updater import CycleDataUpdater

updater = CycleDataUpdater()
updater.update_all_enabled_products(days=30)  # 更新最近30天
```

### 4. 整合更新（分鐘K線 + 週期K線）

```bash
# 只更新週期K線（跳過分鐘K線）
python integrated_updater.py --skip-futures

# 更新最近7天的週期K線
python integrated_updater.py --skip-futures --days=7
```

## 常用命令

### 查看日誌

```bash
# Windows
type cycle_updater.log

# Linux/Mac
tail -f cycle_updater.log
```

### 定時執行（Windows 工作排程器）

1. 開啟「工作排程器」
2. 建立基本工作
3. 觸發程序：每天 15:00（收盤後）
4. 動作：啟動程式
   - 程式：`python.exe`
   - 引數：`C:\Users\user\source\repos\capital_python\integrated_updater.py --skip-futures`
   - 起始位置：`C:\Users\user\source\repos\capital_python`

### 定時執行（Linux cron）

```bash
# 編輯 crontab
crontab -e

# 加入以下行（每天 15:00 執行）
0 15 * * * cd /path/to/capital_python && python integrated_updater.py --skip-futures
```

## 資料庫查詢範例

### 查看週期K線資料

```sql
-- 查看特定商品的所有週期資料
SELECT 
    DATE_FORMAT(`date`, '%Y-%m-%d %H:%i') as time,
    Cycle,
    CASE Cycle
        WHEN 1 THEN '1分'
        WHEN 2 THEN '5分'
        WHEN 3 THEN '15分'
        WHEN 4 THEN '30分'
        WHEN 5 THEN '60分'
        WHEN 6 THEN '日'
        WHEN 7 THEN '週'
        WHEN 8 THEN '月'
        WHEN 9 THEN '2小時'
    END as cycle_name,
    open, high, low, close, volume
FROM captial_kline_cycle
WHERE code = 'TX00' AND exchange = 'TAIFEX'
ORDER BY Cycle, `date` DESC
LIMIT 100;

-- 統計各週期的資料筆數
SELECT 
    code,
    exchange,
    Cycle,
    COUNT(*) as count,
    MIN(`date`) as first_date,
    MAX(`date`) as last_date
FROM captial_kline_cycle
WHERE exchange = 'TAIFEX'
GROUP BY code, exchange, Cycle
ORDER BY code, Cycle;

-- 檢查是否有缺失的週期
SELECT DISTINCT code, exchange
FROM captial_kline_cycle
WHERE code IN (
    SELECT code FROM captial_chart WHERE enable = 1
)
GROUP BY code, exchange
HAVING COUNT(DISTINCT Cycle) < 9;
```

## 週期對照表

| Cycle | 名稱 | 說明 |
|-------|------|------|
| 1 | 1分鐘 | 與 captial_kline 相同 |
| 2 | 5分鐘 | 每5根1分K合併 |
| 3 | 15分鐘 | 每15根1分K合併 |
| 4 | 30分鐘 | 每30根1分K合併 |
| 5 | 60分鐘 | 每60根1分K合併 |
| 6 | 日K線 | 按日期分組 |
| 7 | 週K線 | 按週分組（週一~週日） |
| 8 | 月K線 | 按月分組 |
| 9 | 2小時 | 每120根1分K合併 |

## 常見問題

### Q1: 為什麼某些商品沒有週期資料？

**A:** 檢查以下項目：
1. `captial_chart` 表中該商品的 `enable` 是否為 1
2. `captial_kline` 表中是否有該商品的分鐘K線資料
3. 查看 `cycle_updater.log` 是否有錯誤訊息

### Q2: 如何只更新特定週期？

**A:** 修改程式碼：

```python
from cycle_data_updater import CycleDataUpdater

updater = CycleDataUpdater()
minute_klines = updater.get_minute_klines('TX00', 'TAIFEX', days=7)

# 只生成並更新日K線 (Cycle=6)
daily_klines = updater.generate_cycle_klines(minute_klines, 6)
updater.upsert_cycle_klines(daily_klines)
```

### Q3: 更新需要多久時間？

**A:** 取決於：
- 商品數量
- 更新天數
- 資料庫效能

參考時間：
- 單一商品（7天）：約 5-10 秒
- 10個商品（7天）：約 1-2 分鐘
- 所有商品（30天）：約 5-10 分鐘

### Q4: 如何驗證資料正確性？

**A:** 使用測試腳本：

```bash
python test_cycle_updater.py
# 選擇選項 2（測試週期生成邏輯）
```

這會顯示各週期的資料筆數和範例資料，可以手動驗證。

### Q5: 可以在交易時段執行嗎？

**A:** 可以，但建議：
- 使用較小的 `days` 參數（例如 1-3 天）
- 避免在開盤和收盤時段執行
- 最佳執行時間：收盤後（15:00-16:00）

## 效能優化建議

### 1. 批次更新

```python
# 不建議：每個商品都連線一次
for code, exchange in products:
    updater = CycleDataUpdater()
    updater.update_all_cycles_for_product(code, exchange)

# 建議：重複使用同一個 updater
updater = CycleDataUpdater()
for code, exchange in products:
    updater.update_all_cycles_for_product(code, exchange)
```

### 2. 限制更新範圍

```python
# 日常更新：只更新當天或最近2-3天
updater.update_all_enabled_products(days=1)

# 完整更新：每週或每月執行一次
updater.update_all_enabled_products(days=30)
```

### 3. 資料庫索引

確保以下索引存在：

```sql
-- 已在建表時定義
PRIMARY KEY (`date`, `exchange`, `code`, `Cycle`)
INDEX `IX_captial_kline_cycle_exchange_code` (`exchange`, `code`)
```

## 聯絡資訊

如有問題或建議，請查看：
- 詳細說明：`README_cycle_updater.md`
- 日誌檔案：`cycle_updater.log`
- 原始碼：`cycle_data_updater.py`
