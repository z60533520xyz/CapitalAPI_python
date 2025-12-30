@echo off
:: Switch to the project root directory (one level up from this script)
cd /d "%~dp0.."

echo =====================================================
echo   Capital Python Live Trading Monitor
echo   Start Time: %date% %time%
echo   Working Dir: %cd%
echo =====================================================

:: 1. Update database configuration
echo [1/2] Checking and updating database configuration...
python setup_live_db.py

:: 2. Start the live trading monitor
echo [2/2] Starting main monitoring program...
python live_trading/run_live.py

echo =====================================================
echo   Program has stopped.
echo =====================================================
pause