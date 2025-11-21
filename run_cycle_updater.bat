@echo off
chcp 65001 >nul
echo ========================================
echo 週期K線更新器
echo ========================================
echo.
echo 請選擇執行模式:
echo 1. 測試模式（互動式測試）
echo 2. 更新當天週期K線
echo 3. 更新最近7天週期K線
echo 4. 更新最近30天週期K線
echo 5. 整合更新（分鐘K線 + 週期K線）
echo 0. 離開
echo.
set /p choice=請輸入選項 (0-5): 

if "%choice%"=="1" (
    echo.
    echo 啟動測試模式...
    python test_cycle_updater.py
) else if "%choice%"=="2" (
    echo.
    echo 更新當天週期K線...
    python cycle_data_updater.py
) else if "%choice%"=="3" (
    echo.
    echo 更新最近7天週期K線...
    python -c "from cycle_data_updater import CycleDataUpdater; updater = CycleDataUpdater(); updater.update_all_enabled_products(days=7)"
) else if "%choice%"=="4" (
    echo.
    echo 更新最近30天週期K線...
    python -c "from cycle_data_updater import CycleDataUpdater; updater = CycleDataUpdater(); updater.update_all_enabled_products(days=30)"
) else if "%choice%"=="5" (
    echo.
    echo 整合更新（分鐘K線 + 週期K線）...
    python integrated_updater.py
) else if "%choice%"=="0" (
    echo.
    echo 再見！
    exit /b 0
) else (
    echo.
    echo 無效的選項！
    pause
    exit /b 1
)

echo.
echo ========================================
echo 執行完成！
echo ========================================
pause
