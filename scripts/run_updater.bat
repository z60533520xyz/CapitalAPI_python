@echo off
:: Switch to project root
cd /d "%~dp0.."

echo Starting Futures Data Updater...
python data_etl/futures_data_updater.py

:: Keep window open for 10 seconds to check result
timeout /t 10