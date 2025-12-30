import argparse
import logging
import sys
import os

# 確保專案根目錄在 sys.path 中
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# ==============================================================================
# 提前進行日誌設定，以便所有模組都能使用
# ==============================================================================
def setup_logging(command: str):
    """根據執行的命令設定日誌"""
    log_dir = 'log'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    log_file = os.path.join(log_dir, f'{command}.log')
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, mode='a', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    logging.info(f"日誌設定完成，記錄至 {log_file}")

# ==============================================================================
# 策略設定
# ==============================================================================
STRATEGY_CONFIG = {
    "SqueezeBreakoutOptimized": {
        "strategy_type": 12,
        "contract_size": 1000,  # 輕原油合約規格
        "config": {
            'bbPeriod': 20,
            'bbMultiplier': 2.0,
            'kcPeriod': 20,
            'kcMultiplier': 1.5,
            'atrPeriod': 14,
            'atrMultiplier': 2.0,
            'stopLossMode': 'atr',
            'stopLossPercent': 0.015,
            'max_history_len': 200
        }
    },
    "DailyRangeReversal": {
        "strategy_type": 8,
        "contract_size": 20,  # NQ 合約規格
        "config": {
            'ma_period': 10,
            'reversal_threshold': 0.01,
            'max_history_len': 50
        }
    }
}


# ==============================================================================
# 命令處理函式
# ==============================================================================

def handle_update(args):
    """處理 'update' 命令"""
    setup_logging('update')
    logging.info(f"接收到 'update' 命令: days={args.days}, skip_min={args.skip_min}")
    
    try:
        from data_etl.integrated_updater import run_integrated_update
        logging.info("警告: 'update' 命令將嘗試執行 futures_data_updater.py，這可能會啟動一個 GUI 視窗。")
        run_integrated_update(days=args.days, skip_min=args.skip_min)
        logging.info("數據更新流程結束。")
    except Exception as e:
        logging.error(f"執行數據更新時發生錯誤: {e}", exc_info=True)


def handle_backtest(args):
    """處理 'backtest' 命令"""
    setup_logging('backtest')
    logging.info(f"接收到 'backtest' 命令: 策略='{args.strategy}', 商品='{args.symbol}', 週期='{args.cycle}'")

    strategy_preset = STRATEGY_CONFIG.get(args.strategy)
    if not strategy_preset:
        logging.error(f"找不到名為 '{args.strategy}' 的策略預設設定。")
        print(f"錯誤: 策略 '{args.strategy}' 不存在。可用策略: {', '.join(STRATEGY_CONFIG.keys())}")
        return

    try:
        from backtest.run_strategy_backtest import run_single_backtest
        
        run_single_backtest(
            strategy_type=strategy_preset['strategy_type'],
            strategy_name=args.strategy,
            symbol=args.symbol,
            cycle=args.cycle,
            days=args.days,
            config=strategy_preset['config'],
            capital=args.capital,
            contract_size=strategy_preset['contract_size']
        )
        logging.info("回測流程結束。")
    except Exception as e:
        logging.error(f"執行回測時發生錯誤: {e}", exc_info=True)



def handle_live(args):
    """處理 'live' 命令"""
    setup_logging('live')
    logging.info("接收到 'live' 命令...")
    logging.info("警告: 實盤交易模式啟動。請確保您的配置正確。")
    try:
        from live_trading.run_live import run_live_trading
        run_live_trading()
        logging.info("實盤交易流程結束。")
    except Exception as e:
        logging.error(f"執行實盤交易時發生錯誤: {e}", exc_info=True)

# ==============================================================================
# 主函式與 Argparse 設定
# ==============================================================================

def main():
    """主進入點函式"""
    parser = argparse.ArgumentParser(description="資本策略交易框架命令列介面")
    subparsers = parser.add_subparsers(dest='command', help='可用的命令', required=True)

    # --- 更新命令 (update) ---
    parser_update = subparsers.add_parser('update', help='啟動數據更新流程')
    parser_update.add_argument('--days', type=int, default=3, help='要回補的分鐘K棒天數')
    parser_update.add_argument('--skip-min', action='store_true', help='若設定，則跳過分鐘K線更新，只更新週期K線')
    parser_update.set_defaults(func=handle_update)

    # --- 回測命令 (backtest) ---
    parser_backtest = subparsers.add_parser('backtest', help='執行策略回測')
    parser_backtest.add_argument('-s', '--strategy', type=str, required=True, help='要回測的策略名稱 (例如 SqueezeBreakoutOptimized)')
    parser_backtest.add_argument('--symbol', type=str, default='CL0000', help='交易商品代碼')
    parser_backtest.add_argument('--cycle', type=str, default='30m', help='K線週期')
    parser_backtest.add_argument('--days', type=int, default=120, help='回測天數')
    parser_backtest.add_argument('--capital', type=float, default=100000, help='初始資金')
    parser_backtest.set_defaults(func=handle_backtest)

    # --- 實盤命令 (live) ---
    parser_live = subparsers.add_parser('live', help='啟動實盤交易模式')
    parser_live.set_defaults(func=handle_live)

    # 解析參數並執行對應的函式
    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
