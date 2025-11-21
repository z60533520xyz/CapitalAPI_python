# 週期K線資料更新器使用說明

## 功能說明

這個程式用於從 `captial_kline` 表（分鐘K線）生成並更新 `captial_kline_cycle` 表（週期K線）。

## 支援的週期類型

根據資料表定義，支援以下9種週期：

1. **Cycle = 1**: 1分鐘K線
2. **Cycle = 2**: 5分鐘K線
3. **Cycle = 3**: 15分鐘K線
4. **Cycle = 4**: 30分鐘K線
5. **Cycle = 5**: 60分鐘K線
6. **Cycle = 6**: 日K線
7. **Cycle = 7**: 週K線
8. **Cycle = 8**: 月K線
9. **Cycle = 9**: 2小時K線

## 程式架構

### CycleDataUpdater 類別

主要的更新器類別，包含以下方法:

#### 初始化
```python
updater = CycleDataUpdater(config_path='config.ini')
```

#### 更新單一商品
```python
# 更新特定商品的所有週期K線（最近30天）
updater.update_all_cycles_for_product(code='TX00', exchange='TAIFEX', days=30)
```

#### 更新所有啟用商品
```python
# 更新 captial_chart 表中所有 enable=1 的商品
updater.update_all_enabled_products(days=30)
```

## 使用方式

### 1. 確認設定檔

確保 `config.ini` 檔案存在且包含資料庫設定:

```ini
[DATABASE]
host = localhost
user = your_username
password = your_password
database = your_database
charset = utf8mb4
```

### 2. 執行程式

#### 方式一：直接執行（更新所有商品）
```bash
python cycle_data_updater.py
```

#### 方式二：在其他程式中使用
```python
from cycle_data_updater import CycleDataUpdater

# 建立更新器
updater = CycleDataUpdater()

# 更新特定商品
updater.update_all_cycles_for_product('TX00', 'TAIFEX', days=30)

# 或更新所有啟用商品
updater.update_all_enabled_products(days=30)
```

## 資料處理邏輯

### 1分鐘K線 (Cycle=1)
- 直接從 `captial_kline` 表複製資料

### N分鐘K線 (Cycle=2,3,4,5,9)
- 將分鐘K線按時間週期分組
- 每個週期內：
  - Open: 第一根K線的開盤價
  - High: 所有K線的最高價
  - Low: 所有K線的最低價
  - Close: 最後一根K線的收盤價
  - Volume: 所有K線的成交量總和

### 日K線 (Cycle=6)
- 按日期分組
- 台灣期貨 (TAIFEX): 使用 13:45 作為日K線時間
- 其他交易所: 使用當日最後一筆時間

### 週K線 (Cycle=7)
- 先生成日K線
- 按週分組（週一到週日）
- 使用週一作為該週的代表時間

### 月K線 (Cycle=8)
- 按月份分組
- 使用每月1日作為該月的代表時間

## 資料庫操作

程式使用 `INSERT ... ON DUPLICATE KEY UPDATE` 語法，確保：
- 新資料會被插入
- 已存在的資料會被更新
- 主鍵衝突時自動更新價格和成交量

## 日誌記錄

程式會將執行過程記錄到：
- 控制台輸出
- `cycle_updater.log` 檔案

日誌包含：
- 每個商品的處理狀態
- 每個週期的資料筆數
- 錯誤訊息

## 注意事項

1. **資料來源**: 程式從 `captial_kline` 表讀取分鐘K線資料
2. **時間範圍**: 預設更新最近30天的資料，可透過 `days` 參數調整
3. **交易所支援**: 
   - TAIFEX (台灣期貨交易所): 特殊交易時間處理
   - 其他交易所: 通用時間處理
4. **效能**: 建議在非交易時段執行，避免影響即時資料更新

## 整合建議

### 與 futures_data_updater.py 整合

可以在 `futures_data_updater.py` 完成分鐘K線更新後，自動執行週期K線更新：

```python
# 在 futures_data_updater.py 的適當位置加入
from cycle_data_updater import CycleDataUpdater

# 完成分鐘K線更新後
cycle_updater = CycleDataUpdater()
cycle_updater.update_all_enabled_products(days=1)  # 只更新當天
```

### 定時任務

建議設定定時任務，例如每天收盤後執行：
- Windows: 使用工作排程器
- Linux: 使用 cron

```bash
# 每天 15:00 執行
0 15 * * * cd /path/to/capital_python && python cycle_data_updater.py
```

## 錯誤處理

程式包含完整的錯誤處理機制：
- 資料庫連線失敗會記錄錯誤並繼續處理其他商品
- 單一商品處理失敗不會影響其他商品
- 所有錯誤都會記錄到日誌檔案

## 範例輸出

```
2025-11-21 11:00:00 - root - INFO - 設定檔載入成功。
2025-11-21 11:00:01 - root - INFO - 共找到 5 個啟用的商品
2025-11-21 11:00:01 - root - INFO - 開始更新 TX00 (TAIFEX) 的週期K線資料...
2025-11-21 11:00:02 - root - INFO - 取得 TX00 (TAIFEX) 共 43200 筆分鐘K線資料
2025-11-21 11:00:02 - root - INFO - 生成週期 1 的K線...
2025-11-21 11:00:03 - root - INFO - 成功寫入 43200 筆週期K線資料
2025-11-21 11:00:03 - root - INFO - 週期 1 完成，共 43200 筆資料
...
2025-11-21 11:05:00 - root - INFO - 所有商品週期K線更新完成
```
