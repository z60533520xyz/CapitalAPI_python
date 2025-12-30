# start_live.ps1
# 這個腳本會無限循環執行實盤交易程式，確保它在崩潰後自動重啟

$env:PYTHONIOENCODING="utf-8"

while ($true) {
    Write-Host "正在啟動實盤交易引擎 (Live Trading Engine)..." -ForegroundColor Green
    
    try {
        # 執行 Python 腳本
        python live_trading/run_live.py
    }
    catch {
        Write-Host "發生錯誤: $_" -ForegroundColor Red
    }

    Write-Host "程式已停止。將在 5 秒後自動重啟..." -ForegroundColor Yellow
    Start-Sleep -Seconds 5
}
