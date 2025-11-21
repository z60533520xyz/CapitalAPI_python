# Capital Python K-Line Updater 安裝指南

本文件說明如何從零開始建置此專案的執行環境。

## 1. 系統需求

- **作業系統**: Windows 10 / 11 (因為 Capital API 僅支援 Windows)
- **Python 版本**: 3.8 或以上 (建議 3.10+)
- **群益 API (Capital API)**: 必須已安裝並註冊 COM 元件

## 2. 安裝 Python

如果您尚未安裝 Python：

1. 前往 [Python 官網下載頁面](https://www.python.org/downloads/)。
2. 下載最新的 Windows Installer (例如 Python 3.11.x)。
3. **重要**: 安裝時請務必勾選 **"Add Python.exe to PATH"** (將 Python 加入環境變數)。
4. 完成安裝。

驗證安裝：
開啟命令提示字元 (cmd) 或 PowerShell，輸入：
```bash
python --version
```
應顯示版本號，如 `Python 3.11.5`。

## 3. 安裝專案依賴套件

本專案依賴數個 Python 套件。請在專案目錄下執行以下指令：

### 方法 A: 使用 requirements.txt (推薦)

```bash
pip install -r requirements.txt
```

### 方法 B: 手動安裝

如果您想手動安裝，請執行：

```bash
pip install pandas pymysql comtypes pywin32
```

- `pandas`: 用於處理 K 線資料與時間序列。
- `pymysql`: 用於連接 MySQL 資料庫。
- `comtypes`: 用於與群益 API (COM 元件) 溝通。
- `pywin32`: 提供 `pythoncom` 模組，用於處理 COM 初始化與事件迴圈。

## 4. 設定 Capital API

確保您已安裝群益 API 元件 (通常由群益證券提供安裝檔)。
本專案使用以下 COM 元件：
- `SKCenterLib`
- `SKQuoteLib`
- `SKOSQuoteLib`
- `SKOrderLib`
- `SKReplyLib`

若執行時出現 `2017` 或 `Class not registered` 錯誤，請確認 API 是否正確安裝及註冊。

## 5. 設定資料庫連線

在專案目錄下確認 `config.ini` 檔案存在且內容正確。

**config.ini 範本:**

```ini
[CAPITAL]
user_id = 您的群益帳號
password = 您的群益密碼

[DATABASE]
host = localhost
port = 3306
user = root
password = 您的資料庫密碼
db = stocks_ml
charset = utf8mb4
```

## 6. 執行測試

安裝完成後，您可以執行以下指令測試環境：

**1. 測試 K 線更新 (手動執行):**
```bash
python futures_data_updater.py
```
若視窗最小化且日誌顯示 `✅ 批次儲存...`，代表成功。

**2. 測試完整流程 (包含週期生成):**
```bash
daily_update_task.bat
```
這會自動執行分鐘 K 線更新及週期 K 線生成。

## 7. 常見問題

**Q: 出現 `ModuleNotFoundError: No module named 'pythoncom'`?**
A: 請執行 `pip install pywin32`。

**Q: 出現 `ImportError: No module named 'comtypes'`?**
A: 請執行 `pip install comtypes`。

**Q: 登入失敗，錯誤碼 2017?**
A: 這通常是 COM 初始化問題。請確保使用最新版的 `futures_data_updater.py` (已包含 `pythoncom.CoInitialize` 和視窗最小化修正)。
