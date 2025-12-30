# 3. 數據處理與更新指南 (Data ETL)

本指南詳細說明 `data_etl` 模組的功能與使用方法，此模組是整個量化交易系統的數據基礎。

## 3.1 核心功能

`data_etl` 模組的主要職責是從群益 API 獲取原始 K 線數據，經過處理後存入資料庫，共分為兩大步驟：

1.  **獲取分鐘 K 線**: 從 API 下載最精細的 1 分鐘 K 線資料，並存入 `captial_kline` 資料表。
2.  **生成週期 K 線**: 以分鐘 K 線為基礎，合成所有其他需要的時間週期 (如 5分, 30分, 日線, 週線等)，並存入 `captial_kline_cycle` 資料表。

## 3.2 核心腳本介紹

`data_etl` 資料夾內包含三個主要腳本：

*   `futures_data_updater.py`:
    *   **功能**: 負責執行第一步，從 API 下載指定商品的 **分鐘 K 線**。
    *   **核心**: 處理與群益 API 的所有互動。

*   `cycle_data_updater.py`:
    *   **功能**: 負責執行第二步，從 `captial_kline` 讀取分鐘數據，生成所有 **週期 K 線**。
    *   **核心**: 包含各種時間週期的轉換邏輯。

*   `integrated_updater.py`:
    *   **功能**: 整合上述兩個腳本，提供一站式的更新服務。它可以依序執行分鐘 K 線更新和週期 K 線生成。
    *   **建議**: 在自動化排程任務中，應優先使用此腳本。

## 3.3 快速使用指南

以下為最常見的使用情境與指令。請在專案根目錄下執行。

### 情境一：執行完整的每日更新

這是最推薦的日常操作，會自動更新分鐘線和所有週期線。

```bash
python data_etl/integrated_updater.py
```
*   您也可以使用 `--days=N` 參數來指定要回補的天數，例如 `python data_etl/integrated_updater.py --days=7`。

### 情境二：僅生成週期 K 線

如果您已手動更新分鐘 K 線，或只想重新生成週期數據。

```bash
python data_etl/integrated_updater.py --skip-futures
```

### 情境三：手動執行各別更新腳本

主要用於測試或特殊目的。

```bash
# 1. 更新分鐘 K 線 (會跳出 GUI 視窗)
python data_etl/futures_data_updater.py

# 2. 在分鐘線更新後，手動生成週期 K 線
python data_etl/cycle_data_updater.py
```

## 3.4 週期生成邏輯

`cycle_data_updater.py` 會從分鐘 K 線 (`Cycle=1`) 生成以下週期數據：

| Cycle ID | 週期名稱 | 生成邏輯 |
|:---:|:---|:---|
| 2 | 5分鐘 | 每 5 根 1分 K 合併 |
| 3 | 15分鐘 | 每 15 根 1分 K 合併 |
| 4 | 30分鐘 | 每 30 根 1分 K 合併 |
| 5 | 60分鐘 | 每 60 根 1分 K 合併 |
| 9 | 2小時 | 每 120 根 1分 K 合併 |
| 6 | 日K線 | 按交易日分組，並以特定時間為準 (e.g., 台指期 13:45) |
| 7 | 週K線 | 由日 K 線按週分組 (週一至週日) |
| 8 | 月K線 | 由日 K 線按月分組 |

**合併規則**:
- **Open**: 週期內第一根 K 線的開盤價。
- **High**: 週期內所有 K 線的最高價。
- **Low**: 週期內所有 K 線的最低價。
- **Close**: 週期內最後一根 K 線的收盤價。
- **Volume**: 週期內所有 K 線的成交量總和。

## 3.5 資料庫操作

### 寫入機制
*   腳本使用 `INSERT ... ON DUPLICATE KEY UPDATE` 語法來寫入資料庫。
*   這能確保：
    *   如果 K 線紀錄不存在，則新增。
    *   如果 K 線紀錄已存在 (根據主鍵 `date`, `exchange`, `code`, `Cycle`)，則更新。
*   此機制保證了數據的幂等性，重複執行更新不會造成數據錯誤或重複。

### 常用查詢範例

```sql
-- 1. 查詢特定商品的最新 60 分鐘 K 線
SELECT 
    DATE_FORMAT(`date`, '%Y-%m-%d %H:%i') as time,
    open, high, low, close, volume
FROM captial_kline_cycle
WHERE code = 'TX00' AND exchange = 'TAIFEX' AND Cycle = 5 -- Cycle 5 代表 60m
ORDER BY `date` DESC
LIMIT 100;

-- 2. 統計各商品、各週期的資料筆數與時間範圍
SELECT 
    code,
    exchange,
    Cycle,
    COUNT(*) as count,
    MIN(`date`) as first_date,
    MAX(`date`) as last_date
FROM captial_kline_cycle
GROUP BY code, exchange, Cycle
ORDER BY code, Cycle;

-- 3. 檢查哪些已啟用的商品缺少了某些週期的資料
SELECT DISTINCT c.code, c.exchange
FROM captial_chart c
LEFT JOIN (
    SELECT DISTINCT code, exchange, COUNT(DISTINCT Cycle) as cycle_count
    FROM captial_kline_cycle
    GROUP BY code, exchange
) AS sub ON c.code = sub.code AND c.exchange = sub.exchange
WHERE c.enable = 1 AND (sub.cycle_count IS NULL OR sub.cycle_count < 9);
```

## 3.6 日誌與除錯

*   **日誌檔案**: 所有 `data_etl` 模組的執行日誌都會被記錄在 `log/` 資料夾下 (例如 `daily_task.log`, `cycle_updater.log`)。當更新發生問題時，請第一時間檢查這些日誌檔案。
*   **常見問題**:
    *   **Q: 為什麼商品沒有數據？**
        A: 請檢查：(1) `captial_chart` 表中該商品的 `enable` 是否為 `1`。(2) `config.ini` 中的帳號密碼是否正確。(3) 群益 API 是否正常登入。
    *   **Q: 可以在交易時段執行嗎？**
        A: 可以，但建議在非主要交易時段 (如午盤、收盤後) 執行，並縮短更新天數 (`--days=1`)，以避免對系統造成不必要的負擔。
