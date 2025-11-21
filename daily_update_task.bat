@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo [排程任務] 開始執行每日更新
echo 時間: %date% %time%
echo ========================================

:: 執行整合更新程式 (不需互動)
:: 程式會根據週期類型自動調整資料範圍（分鐘K用7天，日K用60天，週K用180天，月K用365天）
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
