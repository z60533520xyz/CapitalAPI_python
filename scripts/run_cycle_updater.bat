@echo off
chcp 65001 >nul
:: Switch to project root
cd /d "%~dp0.."

echo ========================================
echo   Cycle K-Line Data Updater
echo ========================================
echo.
echo Please select execution mode:
echo 1. Test Mode (Interactive)
echo 2. Update Today's Cycle Data
echo 3. Update Last 7 Days
echo 4. Update Last 30 Days
echo 5. Full Update (Minutes + Cycles)
echo 0. Exit
echo.
set /p choice=Enter choice (0-5): 

if "%choice%"=="1" (
    echo Starting test mode...
    python data_etl/debug_data.py
) else if "%choice%"=="2" (
    echo Updating today's data...
    python data_etl/cycle_data_updater.py
) else if "%choice%"=="3" (
    echo Updating last 7 days...
    python -c "from data_etl.cycle_data_updater import CycleDataUpdater; updater = CycleDataUpdater(); updater.update_all_enabled_products(days=7)"
) else if "%choice%"=="4" (
    echo Updating last 30 days...
    python -c "from data_etl.cycle_data_updater import CycleDataUpdater; updater = CycleDataUpdater(); updater.update_all_enabled_products(days=30)"
) else if "%choice%"=="5" (
    echo Full integration update...
    python data_etl/integrated_updater.py
) else if "%choice%"=="0" (
    exit /b 0
) else (
    echo Invalid choice!
    pause
    exit /b 1
)

echo.
echo ========================================
echo   Execution Finished!
echo ========================================
pause