---
description: 如何設定 Windows 工作排程器以每日自動執行期貨數據更新
---

# 設定每日自動執行期貨數據更新

本指南將引導您使用 Windows 內建的「工作排程器 (Task Scheduler)」來設定每日自動執行 `futures_data_updater.py` 腳本。

## 前置準備

確保您已經有了 `run_updater.bat` 檔案，位於 `c:\Users\user\source\repos\CapitalAPI_python\run_updater.bat`。這個批次檔會負責切換目錄並執行 Python 腳本。

## 設定步驟

1.  **開啟工作排程器**
    *   按 `Win + R` 鍵，輸入 `taskschd.msc`，然後按 Enter。
    *   或者在開始選單搜尋「工作排程器」或「Task Scheduler」。

2.  **建立基本工作**
    *   在右側的「動作 (Actions)」面板中，點擊「建立基本工作... (Create Basic Task...)」。

3.  **命名工作**
    *   **名稱 (Name)**: 輸入容易識別的名稱，例如 `CapitalAPI Futures Updater`。
    *   **描述 (Description)**: (選填) 例如「每日更新國內外期貨 K 線數據」。
    *   點擊「下一步 (Next)」。

4.  **設定觸發程序 (Trigger)**
    *   選擇「每天 (Daily)」。
    *   點擊「下一步 (Next)」。
    *   設定您希望開始執行的時間 (例如早上 08:00 或收盤後 15:00)。
    *   設定「每隔 1 天發生」。
    *   點擊「下一步 (Next)」。

5.  **設定動作 (Action)**
    *   選擇「啟動程式 (Start a program)」。
    *   點擊「下一步 (Next)」。

6.  **設定程式/指令碼**
    *   **程式或指令碼 (Program/script)**: 點擊「瀏覽 (Browse)」，選擇剛剛建立的批次檔：
        `c:\Users\user\source\repos\CapitalAPI_python\run_updater.bat`
    *   **開始位置 (Start in)**: (選填) 由於 `run_updater.bat` 已經設定為自動切換到檔案所在目錄，此欄位可以留空。
        *但為了保險起見，您仍可以填入腳本所在的資料夾路徑：*
        `c:\Users\user\source\repos\CapitalAPI_python\`
    *   點擊「下一步 (Next)」。

7.  **完成**
    *   檢查摘要資訊是否正確。
    *   點擊「完成 (Finish)」。

## 測試工作

1.  在工作排程器中間的列表中，找到您剛剛建立的工作 `CapitalAPI Futures Updater`。
2.  右鍵點擊該工作，選擇「執行 (Run)」。
3.  您應該會看到一個黑色的命令提示字元視窗彈出，顯示腳本正在執行。
4.  檢查 `updater.log` 或資料庫以確認數據是否成功更新。

## 注意事項

*   **電腦必須開啟**: 電腦必須處於開機狀態，排程才會執行。
*   **登入狀態**: 預設情況下，只有在您登入 Windows 時才會執行。如果您希望在未登入時也能執行，可以在工作屬性中勾選「不論使用者登入與否均執行 (Run whether user is logged on or not)」，但這可能需要輸入密碼，且 GUI 介面 (Tkinter) 可能無法顯示 (但腳本邏輯仍會執行)。由於我們的腳本依賴 GUI 迴圈來處理 COM 事件，**建議保持登入狀態執行**，或者確保在「設定」分頁中勾選「如果排程錯過開始時間，盡快執行工作」。
