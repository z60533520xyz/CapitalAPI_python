from common.db_utils import DatabaseManager
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SetupLiveDB")

def setup_live_strategies():
    db = DatabaseManager()
    engine = db.get_engine()
    
    if not engine:
        logger.error("無法連線資料庫")
        return

    with engine.connect() as conn:
        logger.info("1. 重置策略配置 (回復至原版穩健策略)...")
        conn.execute(text("UPDATE captial_chart SET enable = 0"))
        conn.execute(text("UPDATE captial_chart_strategy SET enable = 0"))
        conn.commit()

        # 定義原版穩健策略
        strategies = [
            {
                # NQ 策略: V8 (60m, ATR 4.0, 趨勢拉回)
                'symbol': 'NQ0000', 'exchange': 'CME', 'cycle_id': 5, # 60m
                'strategy_type': 15, # NQTrendMomentumATRStrategy
                'trade_qty': 1, 'contract_size': 20, 'stop_loss': 0.0, 
                'target': 'NQ'
            },
            {
                # CL 策略: MA Crossover (60m, 10/40)
                'symbol': 'CL0000', 'exchange': 'NYM', 'cycle_id': 5, # 60m
                'strategy_type': 14, # CLMACrossoverStrategy
                'trade_qty': 1, 'contract_size': 1000, 'stop_loss': 0.01,
                'target': 'CL'
            }
        ]

        logger.info("2. 寫入實盤配置...")
        for strat in strategies:
            # 1. 插入 captial_chart
            result = conn.execute(text("""
                INSERT INTO captial_chart (code, exchange, enable) 
                VALUES (:code, :exchange, 1)
            """), {
                'code': strat['symbol'], 'exchange': strat['exchange']
            })
            chart_id = result.lastrowid
            
            # 2. 插入 captial_chart_strategy (Cycle 大寫)
            conn.execute(text("""
                INSERT INTO captial_chart_strategy (chartId, strategy, Cycle, stopLossPercent, takeProfitPercent, trailingStopPercent, enable)
                VALUES (:chartId, :strategy, :cycle, :sl, 0, 0, 1)
            """), {
                'chartId': chart_id, 'strategy': strat['strategy_type'], 'cycle': strat['cycle_id'], 'sl': strat['stop_loss']
            })
            
            # 3. 更新或插入 captial_trade_option
            check = conn.execute(text("SELECT 1 FROM captial_trade_option WHERE code=:code AND exchange=:exchange"), 
                                 {'code': strat['symbol'], 'exchange': strat['exchange']}).scalar()
            
            if check:
                conn.execute(text("""
                    UPDATE captial_trade_option 
                    SET tradeQty=:qty, contractSize=:size, Target=:target, isFake=1 
                    WHERE code=:code AND exchange=:exchange
                """), {
                    'qty': strat['trade_qty'], 'size': strat['contract_size'], 'target': strat['target'], 
                    'code': strat['symbol'], 'exchange': strat['exchange']
                })
            else:
                conn.execute(text("""
                    INSERT INTO captial_trade_option (code, exchange, tradeQty, contractSize, Target, isFake, transferOrderOffsetDays, tickTrade, startCaptial, handlingFee, slidingPrice, domesticTradeType, overseaSpecialTradeType, overseaTradeType)
                    VALUES (:code, :exchange, :qty, :size, :target, 1, 0, 0, 0, 0, 0, 0, 0, 0)
                """), {
                    'code': strat['symbol'], 'exchange': strat['exchange'], 
                    'qty': strat['trade_qty'], 'size': strat['contract_size'], 'target': strat['target']
                })
            
            logger.info(f"已配置: {strat['symbol']} (Strategy ID: {strat['strategy_type']}) - 60m 穩健版")
            
        conn.commit()
        logger.info("實盤策略配置完成！")

if __name__ == "__main__":
    setup_live_strategies()