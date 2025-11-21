@echo off
:: 切換到批次檔所在的目錄 (相對路徑)
:: %~dp0 代表批次檔所在的磁碟機和路徑
cd /d "%~dp0"

:: 執行 Python 腳本
:: 如果您的 Python 環境需要特定路徑或虛擬環境，請在此修改
python futures_data_updater.py

:: 腳本執行完畢後保持視窗開啟 10 秒 (可選，方便查看日誌)
timeout /t 10
