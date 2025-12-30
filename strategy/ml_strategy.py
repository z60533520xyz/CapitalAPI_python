from .base_strategy import BaseStrategy
from common.indicators import calculate_indicators
import pandas as pd
import numpy as np
import joblib
import os
from typing import Dict, Any, Optional, List

class MLStrategy(BaseStrategy):
    """
    機器學習策略 (Machine Learning Strategy)
    
    此策略載入預訓練的 Scikit-Learn 模型 (如 RandomForest, XGBoost 等)，
    並根據即時計算的技術指標進行預測。
    
    必要配置 (config):
    - model_path: 模型檔案路徑 (.pkl)
    - scaler_path: 標準化器檔案路徑 (.pkl)
    - feature_names: 特徵名稱列表 (必須與訓練時完全一致)
    - long_threshold: 做多機率閾值 (預設 0.6)
    - short_threshold: 做空機率閾值 (預設 0.4)
    """
    
    def on_init(self):
        """初始化：載入模型與參數"""
        self.model_path = self.config.get('model_path', 'models/model.pkl')
        self.scaler_path = self.config.get('scaler_path', 'models/scaler.pkl')
        self.selector_path = self.config.get('selector_path', 'models/selector.pkl')
        self.feature_names_path = self.config.get('feature_names_path', 'models/feature_names.pkl')
        
        self.long_threshold = self.config.get('long_threshold', 0.6)
        self.short_threshold = self.config.get('short_threshold', 0.4)
        
        self.model = None
        self.scaler = None
        self.selector = None
        self.feature_names = []
        
        try:
            if os.path.exists(self.model_path):
                self.model = joblib.load(self.model_path)
                self.logger.info(f"[{self.strategy_id}] 成功載入模型: {self.model_path}")
            else:
                self.logger.warning(f"[{self.strategy_id}] 找不到模型檔案: {self.model_path}")
                
            if os.path.exists(self.scaler_path):
                self.scaler = joblib.load(self.scaler_path)
                self.logger.info(f"[{self.strategy_id}] 成功載入 Scaler: {self.scaler_path}")
                
            if os.path.exists(self.selector_path):
                self.selector = joblib.load(self.selector_path)
                self.logger.info(f"[{self.strategy_id}] 成功載入 Selector: {self.selector_path}")
                
            if os.path.exists(self.feature_names_path):
                self.feature_names = joblib.load(self.feature_names_path)
                self.logger.info(f"[{self.strategy_id}] 成功載入特徵名稱: {len(self.feature_names)} 個特徵")
                
        except Exception as e:
            self.logger.error(f"[{self.strategy_id}] 初始化失敗: {e}")

    def on_bar(self, bar: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """K線更新邏輯"""
        # 1. 更新歷史資料
        self.update_bar(bar)
        
        # 2. 檢查模型是否就緒
        if self.model is None:
            return None
            
        # 3. 檢查資料量 (至少需要足夠計算最長週期的指標，例如 EMA_200)
        if len(self.klines) < 205: 
            return None
            
        # 4. 準備資料與計算指標
        try:
            # 優化：回測模式下，如果 bar 中已包含預計算的特徵，則直接使用
            if self.config.get('backtest_mode', False) and 'features' in bar:
                X = bar['features']
            else:
                df = self.get_history_df()
                
                # 計算所有技術指標 (包含衍生特徵)
                df_indicators = calculate_indicators(df)
                
                # 5. 提取特徵向量 (Feature Vector)
                # 必須確保特徵順序與訓練時一致
                if not self.feature_names:
                    self.logger.warning(f"[{self.strategy_id}] 未設定 feature_names，無法進行預測")
                    return None
                    
                # 檢查缺少的特徵
                missing_features = [f for f in self.feature_names if f not in df_indicators.columns]
                if missing_features:
                    self.logger.warning(f"[{self.strategy_id}] 缺少特徵: {missing_features[:5]}...")
                    return None
                    
                # 取最後一筆資料進行預測
                X = df_indicators[self.feature_names].iloc[[-1]]
            
            # 6. 預處理 (Scaler & Selector)
            if self.scaler:
                X = self.scaler.transform(X)
            if self.selector:
                X = self.selector.transform(X)
                
            # 7. 模型預測
            # 假設模型是 Classifier，輸出機率
            probs = self.model.predict_proba(X)[0]
            classes = self.model.classes_
            
            # 映射類別與機率 (假設類別為: 1=Long, -1=Short, 0=Neutral)
            prob_map = {c: p for c, p in zip(classes, probs)}
            prob_long = prob_map.get(1, 0.0)
            prob_short = prob_map.get(-1, 0.0)
            
            # Debug: 印出機率
            # self.logger.info(f"[{bar['date']}] Long: {prob_long:.2f}, Short: {prob_short:.2f}")
            
            # 8. 產生訊號
            signal = None
            current_price = bar['close']
            
            # 檢查止損
            if self.position != 0:
                entry_price = self.avg_cost
                # 避免除以零
                if entry_price > 0:
                    pnl_pct = 0
                    if self.position > 0:
                        pnl_pct = (current_price - entry_price) / entry_price
                    else:
                        pnl_pct = (entry_price - current_price) / entry_price
                        
                    stop_loss_pct = self.config.get('stop_loss_pct', 0.02) # 預設 2% 止損
                    
                    if pnl_pct < -stop_loss_pct:
                        # self.logger.info(f"[{bar['date']}] 觸發止損: {pnl_pct:.2%}")
                        return {
                            'action': 'SELL' if self.position > 0 else 'BUY',
                            'quantity': abs(self.position),
                            'price': current_price,
                            'reason': 'Stop Loss'
                        }

            if prob_long > self.long_threshold:
                if self.position <= 0:
                    signal = {
                        'action': 'BUY',
                        'quantity': 1,
                        'price': current_price,
                        'reason': f'ML Long (Prob: {prob_long:.2f})'
                    }
            elif prob_short > self.short_threshold:
                if self.position >= 0:
                    signal = {
                        'action': 'SELL',
                        'quantity': 1,
                        'price': current_price,
                        'reason': f'ML Short (Prob: {prob_short:.2f})'
                    }
                    
            return signal
            
        except Exception as e:
            self.logger.error(f"[{self.strategy_id}] 預測過程發生錯誤: {e}")
            return None
