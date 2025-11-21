@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo [排程任務] 開始執行每日更新
echo 時間: %date% %time%
echo ========================================

:: 執行整合更新程式 (不需互動)
:: --days=1 表示只更新最近 1 天的週期K線 (可根據需求調整)
python integrated_updater.py --days=1 >> daily_task.log 2>&1

if %ERRORLEVEL% EQU 0 (
    echo [成功] 更新完成
) else (
    echo [失敗] 更新發生錯誤，請檢查 daily_task.log
)

echo ========================================
echo [排程任務] 結束
echo 時間: %date% %time%
echo ========================================
