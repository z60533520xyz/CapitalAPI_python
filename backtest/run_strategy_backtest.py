import logging
import sys
import os
import pandas as pd
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backtest.engine import BacktestEngine

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def run_single_backtest(strategy_type: int, strategy_name: str, symbol: str, cycle: str, 
                        start_date_str: str, end_date_str: str, 
                        config: dict, capital: float, contract_size: float):
    print(f"\n{'='*60}")
    print(f"回測: {strategy_name} (ID: {strategy_type}) {symbol} {cycle}")
    print(f"{ '='*60}")
    
    engine = BacktestEngine(initial_capital=capital)
    analyzer = engine.run_backtest(strategy_type, symbol, cycle, start_date_str, end_date_str, config, contract_size)

    if analyzer:
        analyzer.print_report()
        metrics = analyzer.get_metrics()
        
        pnl = metrics.get('Total Net Profit', 0)
        dd = metrics.get('Max Drawdown (%)', 0) * capital / 100
        dd = abs(dd)
        trades = metrics.get('Total Trades', 0)
        
        print(f"\n--- 關鍵指標檢核 ---")
        print(f"總獲利: ${pnl:.2f}")
        print(f"最大回撤: ${dd:.2f}")
        print(f"交易次數: {trades}")
        
        if analyzer.trades:
            output_dir = "outputs"
            os.makedirs(output_dir, exist_ok=True)
            path = os.path.join(output_dir, f"trades_{strategy_name}_{symbol}_{cycle}.csv")
            pd.DataFrame(analyzer.trades).to_csv(path, index=False)
            print(f"交易記錄: {path}")

if __name__ == "__main__":
    start_date = "2025-03-25"
    end_date = "2025-12-24"
    
    # CL Daily Range Reversal (60m)
    # 參數：
    # rangeThreshold: 0.9 (接近 1.0 時準備反轉)
    # stopBuffer: 0.3 (若突破到 1.2~1.3 代表趨勢強，認賠)
    # profitTarget: 0.4 (回調 $400 即停利)
    cl_config = {
        'rangeThreshold': 0.9,
        'stopBuffer': 0.3,
        'profitTarget': 0.4,
        'rsiPeriod': 14,
        'tradeQuantity': 1
    }
    
    # 這裡我們也順便測一下 NQ 是否也適用此邏輯 (NQ range 大約 200點?)
    # 但先專注於 CL
    run_single_backtest(27, "DailyRangeReversal", "CL0000", "60m", start_date, end_date, cl_config, 100000, 1000)
    
    # NQ 測試 (假設 NQ range 為 200點)
    nq_config = {
        'rangeThreshold': 180.0,
        'stopBuffer': 50.0,
        'profitTarget': 80.0,
        'rsiPeriod': 14,
        'tradeQuantity': 1
    }
    run_single_backtest(27, "DailyRangeReversal", "NQ0000", "60m", start_date, end_date, nq_config, 100000, 20)