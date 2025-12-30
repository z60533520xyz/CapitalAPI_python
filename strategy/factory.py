import logging
from typing import Dict, Any
from strategy.base_strategy import BaseStrategy
from strategy.ml_strategy import MLStrategy
from strategy.macd_bollinger import MacdBollingerStrategy
from strategy.bollinger_keltner import BollingerKeltnerStrategy
from strategy.daily_range_reversal import DailyRangeReversalStrategy # ID 27
from strategy.squeeze_breakout import SqueezeBreakoutOptimizedStrategy
from strategy.cl_volatility_expansion_strategy import CLVolatilityExpansionStrategy
from strategy.cl_ma_crossover_strategy import CLMACrossoverStrategy
from strategy.simple_bb_breakout_nq import SimpleBBBreakoutNQ
from strategy.nq_trend_momentum_atr_strategy import NQTrendMomentumATRStrategy
from strategy.cl_rsi_pullback import CLRsiPullbackStrategy
from strategy.nq_squeeze_strategy import NQSqueezeMomentumStrategy
from strategy.nq_supertrend_strategy import NQSuperTrendStrategy
from strategy.cl_keltner_reversal import CLKeltnerReversalStrategy
from strategy.nq_macd_volatility import NQMacdVolatilityStrategy
from strategy.cl_inside_bar import CLInsideBarStrategy
from strategy.tx_trend_squeeze import TXTrendSqueezeStrategy
from strategy.tx_5m_scalping import TX5mScalpingStrategy
from strategy.nq_5m_scalping import NQ5mScalpingStrategy
from strategy.cl_5m_scalping import CL5mScalpingStrategy

class StrategyFactory:
    
    @staticmethod
    def get_strategy(strategy_type: int, strategy_id: str, config: Dict[str, Any]) -> BaseStrategy:
        logger = logging.getLogger("StrategyFactory")
        
        if strategy_type == 0 or strategy_type == 1:
            return MacdBollingerStrategy(strategy_id, config)
        elif strategy_type == 2:
            return BollingerKeltnerStrategy(strategy_id, config)
        elif strategy_type == 8: # Use ID 8 or 27 for this strategy
            return DailyRangeReversalStrategy(strategy_id, config)
        elif strategy_type == 12:
            return SqueezeBreakoutOptimizedStrategy(strategy_id, config)
        elif strategy_type == 13:
            return CLVolatilityExpansionStrategy(strategy_id, config)
        elif strategy_type == 14:
            return CLMACrossoverStrategy(strategy_id, config)
        elif strategy_type == 15:
            return NQTrendMomentumATRStrategy(strategy_id, config)
        elif strategy_type == 16:
            return SimpleBBBreakoutNQ(strategy_id, config)
        elif strategy_type == 17:
            return CLRsiPullbackStrategy(strategy_id, config)
        elif strategy_type == 18:
            return NQSqueezeMomentumStrategy(strategy_id, config)
        elif strategy_type == 19:
            return NQSuperTrendStrategy(strategy_id, config)
        elif strategy_type == 20:
            return CLKeltnerReversalStrategy(strategy_id, config)
        elif strategy_type == 21:
            return NQMacdVolatilityStrategy(strategy_id, config)
        elif strategy_type == 22:
            return CLInsideBarStrategy(strategy_id, config)
        elif strategy_type == 23:
            return TXTrendSqueezeStrategy(strategy_id, config)
        elif strategy_type == 24:
            return TX5mScalpingStrategy(strategy_id, config)
        elif strategy_type == 25:
            return NQ5mScalpingStrategy(strategy_id, config)
        elif strategy_type == 26:
            return CL5mScalpingStrategy(strategy_id, config)
        elif strategy_type == 27: # Daily Range Reversal
            logger.info(f"創建 DailyRangeReversalStrategy (ID: {strategy_id})")
            return DailyRangeReversalStrategy(strategy_id, config)
        elif strategy_type == 99:
            return MLStrategy(strategy_id, config)
            
        logger.warning(f"策略類型 {strategy_type} 尚未移植，使用 MLStrategy 代替")
        return MLStrategy(strategy_id, config)