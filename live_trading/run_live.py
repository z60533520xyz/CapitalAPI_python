import logging
import sys
import os
import time
from typing import List

# 獲取專案根目錄
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# 導入通用模組
from common.db_utils import DatabaseManager
from strategy.factory import StrategyFactory
from common.discord_notify import DiscordNotifier

# 導入實盤模組
try:
    from live_trading.trader import LiveTrader
    from live_trading.monitor import MarketMonitor
except ImportError:
    from trader import LiveTrader
    from monitor import MarketMonitor

# 設定 logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(ROOT_DIR, "log/live_trading.log"), encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("RunLive")

def main():
    db = DatabaseManager()
    discord = DiscordNotifier()
    
    # 1. 讀取啟用策略
    logger.info("讀取實盤策略配置...")
    active_strategies_df = db.get_active_strategies()
    
    if active_strategies_df.empty:
        logger.warning("沒有啟用的策略，程式結束")
        return

    # 2. 初始化監控器
    monitor = MarketMonitor(interval=5)
    trader_count = 0

    for _, row in active_strategies_df.iterrows():
        try:
            config = row.to_dict()
            strategy_type = int(config['strategy_type'])
            strategy_id = f"{config['code']}_{config['cycle']}_{strategy_type}"
            
            # 3. 建立策略與 Trader
            strategy = StrategyFactory.get_strategy(strategy_type, strategy_id, config)
            trader = LiveTrader(strategy, config)
            
            # 4. 向監控器訂閱 K 線更新
            # 注意：monitor 內部使用 cycle (int), config['cycle'] 已經是從 DB 讀出的 ID
            monitor.subscribe(config['code'], int(config['cycle']), trader.on_new_bar)
            
            trader_count += 1
            logger.info(f"已部署並訂閱: {strategy_id} ({config['target_symbol']})")
            
        except Exception as e:
            logger.error(f"載入策略失敗: {e}")
            import traceback
            traceback.print_exc()

    if trader_count == 0:
        logger.error("沒有成功載入任何 Trader")
        return

    # 5. 啟動監控 (這是一個阻塞呼叫，內部有 while True)
    discord.send(f"🚀 實盤監控系統啟動！已部署 {trader_count} 組策略。")
    
    try:
        monitor.start()
    except KeyboardInterrupt:
        logger.info("使用者停止程式")
        discord.send("🛑 實盤監控系統已手動停止。")
    except Exception as e:
        logger.error(f"監控系統崩潰: {e}")
        discord.send(f"⚠️ 系統發生錯誤並停止: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    main()