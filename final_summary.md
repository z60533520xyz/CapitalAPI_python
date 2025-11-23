# 專案完成總結：Capital Python K-Line Updater

## ✅ 已完成目標

### 1. 解決 Capital API 錯誤 2017
- **問題**：API 初始化失敗，錯誤代碼 2017。
- **解決**：
  - 修正 `futures_data_updater.py`，將視窗操作從 `withdraw()` (隱藏) 改為 `iconify()` (最小化)。
  - 建立 `init_com.py` 修復 COM 元件註冊問題，直接載入 DLL 繞過註冊表錯誤。

### 2. 優化週期 K 線生成 (`cycle_data_updater.py`)
- **智能增量更新**：
  - **初次執行**：自動偵測無資料，回溯所有歷史（最多10年）。
  - **日常執行**：僅更新未完成的週期（如當前週、當前月），大幅提升效能。
- **跨日交易處理**：
  - 正確處理台灣期貨（15:00 起始）和海外期貨（18:00 起始）的交易日歸屬。
  - 確保日 K 線的開高低收數據準確。
- **資料完整性過濾**：
  - 自動過濾掉資料不足的週期（如只有1天資料的週K）。
  - 標準：日K需15筆分鐘資料，週K需3個交易日，月K需10個交易日。
- **效能與可視化**：
  - 實作 **批次讀取** (SSCursor) 與 **批次寫入**，避免記憶體溢出。
  - **演算法優化**：週期 K 線生成改為直接遍歷原始資料 (O(N))，不再遍歷時間軸，大幅提升速度並修正進度顯示（分母為實際資料筆數）。
  - 添加詳細的 **進度顯示**，清楚掌握執行狀態。

### 3. 自動化排程
- **整合腳本**：`integrated_updater.py` 串聯了分鐘資料下載與週期 K 線生成。
- **批次檔**：`daily_update_task.bat` 可直接用於 Windows 排程工作。

## 🚀 如何執行

### 1. 日常自動更新
將 `daily_update_task.bat` 加入 Windows 排程工作（Task Scheduler），建議設定在每日收盤後（例如 06:00 或 14:00）執行。

### 2. 手動執行完整更新
若要立即執行一次完整更新，請在終端機執行：
```bash
daily_update_task.bat
```

### 3. 僅重新生成週期 K 線
若分鐘資料已存在，只想重新計算週期 K 線：
```bash
python cycle_data_updater.py
```

## 📂 檔案說明
- `futures_data_updater.py`: 下載分鐘 K 線（需 Capital API）。
- `cycle_data_updater.py`: 計算並寫入各週期 K 線。
- `integrated_updater.py`: 主控程式，依序執行上述兩者。
- `init_com.py`: 環境修復工具。
- `INSTALL.md`: 詳細安裝與設定指南。
