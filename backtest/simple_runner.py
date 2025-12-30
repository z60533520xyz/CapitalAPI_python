# backtest/simple_runner.py
import logging
from datetime import datetime, timedelta
from backtest.engine import BacktestEngine

def setup_logging():
    """配置日誌記錄"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler("log/backtest_run.log"),
            logging.StreamHandler()
        ]
    )

def main():
    """主函數：執行一個簡單的回測"""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    # 1. 初始化回測引擎
    engine = BacktestEngine(initial_capital=100000.0)
    
    # 2. 定義回測參數
    # 使用 12 作為 SqueezeBreakoutOptimizedStrategy 的 ID
    strategy_type = 12
    symbol = 'CL0000'
    cycle = '30m'
    start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
    end_date = datetime.now().strftime('%Y-%m-%d')
    
    # 策略特定參數 (從 strategy/squeeze_breakout.py 的 __init__ 中得知)
    strategy_config = {
        'stopLossPercent': 0.01,
        'takeProfitPercent': 0.015,
        'trailingStopPercent': 0.008,
        'bbPeriod': 20,
        'kcPeriod': 20,
        'kc_multiplier': 2.0
    }
    
    # 從 stock_ml_py/config.py 中獲取 CL0000 的合約規格
    contract_size = 1000.0
    
    try:
        # 3. 執行回測
        analyzer = engine.run_backtest(
            strategy_type=strategy_type,
            symbol=symbol,
            cycle=cycle,
            start_date=start_date,
            end_date=end_date,
            strategy_config=strategy_config,
            contract_size=contract_size
        )
        
        # 4. 顯示結果
        if analyzer:
            logger.info("--- 回測績效報告 ---")
            performance_report = analyzer.get_performance_report()
            for key, value in performance_report.items():
                logger.info(f"{key:<25}: {value}")
                
            # 也可以選擇繪製圖表
            # analyzer.plot_equity_curve()
            
    except Exception as e:
        logger.error(f"回測過程中發生未預期錯誤: {e}", exc_info=True)

if __name__ == "__main__":
    main()