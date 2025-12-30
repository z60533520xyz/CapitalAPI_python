# 2. 環境安裝與設定指南

本文件將引導您從零開始，完整設定此量化交易專案的執行環境。

## 2.1 系統需求

*   **作業系統**: Windows 10 / 11 (因為群益 API 僅支援 Windows)。
*   **Python 版本**: 3.8 或以上 (建議使用 3.10+)。
*   **資料庫**: MySQL 或相容的資料庫 (例如 MariaDB)。

## 2.2 環境建置步驟

### 步驟 1: 安裝 Python

如果您尚未安裝 Python：

1.  前往 [Python 官網下載頁面](https://www.python.org/downloads/)。
2.  下載最新的 Windows Installer (x64 版本)。
3.  **重要**: 在安裝過程中，請務必勾選 **"Add Python.exe to PATH"** 選項。

安裝後，開啟命令提示字元 (cmd) 或 PowerShell 並輸入 `python --version` 來驗證。

### 步驟 2: 安裝群益 API 元件

確保您已經從群益官方獲取並安裝了 API 元件。安裝後，請根據其說明文件註冊 COM 元件，這是本專案能與 API 溝通的基礎。

### 步驟 3: 下載專案並安裝依賴

1.  透過 Git 或下載 Zip 檔取得本專案原始碼。
2.  進入專案根目錄，並執行以下指令安裝所有必要的 Python 套件：

    ```bash
    pip install -r requirements.txt
    ```
    這會安裝 `pandas`, `pymysql`, `comtypes`, `pywin32` 等核心依賴。

### 步驟 4: 設定資料庫

本專案需要使用 MySQL 資料庫來儲存 K 線及交易相關資料。

1.  **建立資料庫**: 請先在您的 MySQL 中建立一個新的資料庫 (database)，例如 `capital_quant`。
2.  **建立資料表**: 專案的正常運作需要以下資料表，**您必須手動建立它們**。請在專案中尋找 `.sql` 結構定義檔，或參考 `data_etl` 和 `common/db_utils.py` 中的程式碼來推斷欄位結構。
    *   `captial_kline`: 存放原始分鐘 K 線。
    *   `captial_kline_cycle`: 存放所有週期的 K 線 (例如 5分、60分、日線等)。
    *   `captial_chart`: 用於設定要追蹤的商品。
    *   `captial_chart_strategy`: 設定商品要套用的策略。
    *   `captial_trade_history`: 儲存歷史交易紀錄。
    *   `captial_trade_option`: 交易選項設定。

### 步驟 5: 設定專案連線資訊

複製或重新命名 `config.ini.template` (如果有的話) 為 `config.ini`，並填寫您的個人資訊。檔案應包含以下區塊：

```ini
[CAPITAL]
user_id = 您的群益登入帳號
password = 您的群益登入密碼

[DATABASE]
host = localhost
port = 3306
user = root
password = 您的資料庫密碼
database = capital_quant  # 您在步驟 4-1 建立的資料庫名稱
charset = utf8mb4
```

## 2.3 執行測試

完成以上所有設定後，您可以執行以下指令來測試環境是否配置成功：

1.  **測試單一數據更新**:
    在專案根目錄下執行，此指令會嘗試更新期貨分鐘 K 線數據。

    ```bash
    python data_etl/futures_data_updater.py
    ```
    如果程式執行且日誌中顯示數據儲存成功，代表基本設定無誤。

2.  **測試完整更新流程**:
    執行位於 `scripts` 資料夾中的批次檔，這會模擬每日的自動化更新任務。

    ```bash
    .\scripts\daily_update_task.bat
    ```
    此腳本會呼叫 `integrated_updater.py`，執行分鐘 K 線更新與週期 K 線生成。請檢查 `log/daily_task.log` 確認執行結果。

## 2.4 常見問題

*   **Q: 執行時出現 `ModuleNotFoundError: No module named 'pythoncom'`**
    A: `pywin32` 套件未正確安裝。請嘗試 `pip uninstall pywin32` 後再重新 `pip install pywin32`。

*   **Q: 登入失敗，錯誤碼 2017 或 `Class not registered`**
    A: 這代表 COM 元件有問題。請確認群益 API 已正確安裝並註冊。您可能需要以系統管理員身分執行其註冊腳本 (`.bat`)。
