@echo off
chcp 65001 >nul
:: Switch to project root
cd /d "%~dp0.."

echo ========================================
echo [Schedule Task] Starting Daily Update
echo Time: %date% %time%
echo ========================================

:: Execute integrated updater (days=1 for daily maintenance)
python data_etl/integrated_updater.py --days=1 >> log/daily_task.log 2>&1

if %ERRORLEVEL% EQU 0 (
    echo [Success] Update completed.
) else (
    echo [Failed] Errors occurred, check log/daily_task.log
)

echo ========================================
echo [Schedule Task] Finished
echo ========================================