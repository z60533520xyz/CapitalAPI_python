import pandas as pd
import numpy as np
import talib as ta
from typing import Optional, List

# 忽略 SettingWithCopyWarning
pd.options.mode.chained_assignment = None

def calculate_indicators(df, 
                         macd_fast=12, macd_slow=26, macd_signal=9, 
                         bb_period=20, bb_multiplier=2.0, ma_periods=[5, 10, 20],
                         kc_period=20, kc_multiplier=2.0,
                         atr_period=14, # ATR period can be passed
                         indicators_to_calculate: Optional[List[str]] = None): # 新增參數
    """
    計算技術指標，可選擇性計算指定指標。
    
    Args:
        df: 包含 Open, High, Low, Close, Volume 的 DataFrame
        indicators_to_calculate (Optional[List[str]]): 要計算的指標列表，例如 ['BB', 'KC', 'EMA']. 
                                                       如果為 None 或空列表，則計算所有指標。
    Returns:
        包含所有計算指標的 DataFrame
    """
    if df is None or df.empty:
        raise ValueError("DataFrame 為空，無法計算指標")
    
    df = df.copy()
    
    # 將所有指標名稱轉為大寫，方便比對
    if indicators_to_calculate:
        indicators_to_calculate = [ind.upper() for ind in indicators_to_calculate]
    else:
        indicators_to_calculate = [] # 確保它是一個列表
    
    # 預設行為：如果未指定指標，則計算所有指標
    calculate_all = not indicators_to_calculate or len(indicators_to_calculate) == 0

    # 確保欄位名稱正確並轉為數值
    for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
        if col not in df.columns and col.lower() in df.columns:
            df[col] = df[col.lower()]
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    # 確保傳遞給 TA-Lib 的數據是 float64
    float_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
    for col in float_cols:
        if col in df.columns:
            df[col] = df[col].astype(np.float64)
    
    df = df.dropna(subset=['Close']).copy()
    df = df[df['Close'] > 0].copy()
    
    # 初始化一個列表來追蹤實際計算了哪些指標的列，用於最終的缺失值處理
    calculated_indicator_cols = []

    # ========== OHLC 特徵 ==========
    if calculate_all or 'OHLC_RATIO' in indicators_to_calculate:
        df['O_H_Ratio'] = df['Open'] / df['High']
        df['O_L_Ratio'] = df['Open'] / df['Low']
        df['O_C_Ratio'] = df['Open'] / df['Close']
        df['C_H_Ratio'] = df['Close'] / df['High']
        df['C_L_Ratio'] = df['Close'] / df['Low']
        df['H_L_Ratio'] = df['High'] / df['Low']
        calculated_indicator_cols.extend(['O_H_Ratio', 'O_L_Ratio', 'O_C_Ratio', 'C_H_Ratio', 'C_L_Ratio', 'H_L_Ratio'])

    # ========== MACD 指標 ==========
    if calculate_all or 'MACD' in indicators_to_calculate:
        df['EMA_Fast'] = df['Close'].ewm(span=macd_fast, adjust=False).mean()
        df['EMA_Slow'] = df['Close'].ewm(span=macd_slow, adjust=False).mean()
        df['MACD'] = df['EMA_Fast'] - df['EMA_Slow']
        df['MACD_Signal'] = df['MACD'].ewm(span=macd_signal, adjust=False).mean()
        calculated_indicator_cols.extend(['EMA_Fast', 'EMA_Slow', 'MACD', 'MACD_Signal'])
        
        # MACD 衍生特徵
        df['MACD_Close_Ratio'] = df['MACD'] / df['Close']
        df['MACD_Signal_Close_Ratio'] = df['MACD_Signal'] / df['Close']
        df['MACD_Hist_Close_Ratio'] = (df['MACD'] - df['MACD_Signal']) / df['Close']
        calculated_indicator_cols.extend(['MACD_Close_Ratio', 'MACD_Signal_Close_Ratio', 'MACD_Hist_Close_Ratio'])
        
        # MACD 相對位置 (0-1 歸一化)
        df['MACD_Ratio'] = np.where(
            df['Close'] != 0,
            (df['MACD'] - df['MACD'].rolling(20).min()) / 
            (df['MACD'].rolling(20).max() - df['MACD'].rolling(20).min()),
            0.5
        )
        df['MACD_Ratio'] = df['MACD_Ratio'].fillna(0.5).clip(0, 1)
        calculated_indicator_cols.append('MACD_Ratio')
        
        # MACD 動能 (當前值 vs 前一值)
        df['MACD_Momentum'] = df['MACD'] / df['MACD'].shift(1)
        df['MACD_Momentum'] = df['MACD_Momentum'].fillna(1.0)
        calculated_indicator_cols.append('MACD_Momentum')
    
    # ========== 布林通道 (Bollinger Bands) ==========
    # BB 必須在 KC 之前計算，因為 BB_Width_Ratio 可能被 SqueezeBreakout 使用
    if calculate_all or 'BB' in indicators_to_calculate or 'SQUEEZE' in indicators_to_calculate:
        df['BB_Middle'] = df['Close'].rolling(window=bb_period, min_periods=1).mean()
        bb_std = df['Close'].rolling(window=bb_period, min_periods=1).std()
        df['BB_Upper'] = df['BB_Middle'] + (bb_std * bb_multiplier) 
        df['BB_Lower'] = df['BB_Middle'] - (bb_std * bb_multiplier) 
        calculated_indicator_cols.extend(['BB_Middle', 'BB_Upper', 'BB_Lower'])
        
        bb_range = df['BB_Upper'] - df['BB_Lower'] 

        # 價格在布林通道中的位置
        df['BB_Position'] = np.where(
            bb_range != 0, 
            (df['Close'] - df['BB_Lower']) / bb_range, 
            0.5
        )
        df['BB_Position'] = df['BB_Position'].clip(0, 1)
        calculated_indicator_cols.append('BB_Position')
        
        # 通道寬度比率
        df['BB_Width_Ratio'] = bb_range / df['Close']
        calculated_indicator_cols.append('BB_Width_Ratio')
        
        # 通道與收盤價比率
        df['BB_Upper_Close_Ratio'] = df['BB_Upper'] / df['Close']
        df['BB_Lower_Close_Ratio'] = df['BB_Lower'] / df['Close']
        df['BB_Middle_Close_Ratio'] = df['BB_Middle'] / df['Close']
        calculated_indicator_cols.extend(['BB_Upper_Close_Ratio', 'BB_Lower_Close_Ratio', 'BB_Middle_Close_Ratio'])
        
        # 擠壓指標 (Squeeze) - 獨立判斷，但依賴 BB
        if calculate_all or 'SQUEEZE' in indicators_to_calculate:
            bb_width_ma = df['BB_Width_Ratio'].rolling(bb_period).mean() # Use bb_period for consistency
            df['BB_Squeeze'] = np.where(
                bb_width_ma != 0,
                df['BB_Width_Ratio'] / bb_width_ma,
                1.0
            )
            df['BB_Squeeze'] = df['BB_Squeeze'].fillna(1.0).clip(0.5, 2.0)
            calculated_indicator_cols.append('BB_Squeeze')
        
        # 突破強度 (超過上軌/下軌的幅度)
        df['BB_Breakout_Strength'] = np.where(
            df['BB_Position'] > 0.8, (df['Close'] - df['BB_Upper']) / df['Close'],
            np.where(
                df['BB_Position'] < 0.2, (df['BB_Lower'] - df['Close']) / df['Close'],
                0
            )
        )
        calculated_indicator_cols.append('BB_Breakout_Strength')
    
    # ========== 移動平均線 (MA) ========== 
    # 此處的 MA 不應與 EMA 混淆
    if calculate_all or 'MA' in indicators_to_calculate: 
        for period in ma_periods:
            df[f'MA{period}'] = df['Close'].rolling(window=period, min_periods=1).mean()
            calculated_indicator_cols.append(f'MA{period}')
        
        # 均線比率特徵
        if 5 in ma_periods and 10 in ma_periods:
            df['MA5_MA10_Ratio'] = df['MA5'] / df['MA10'].replace(0, np.nan)
        if 10 in ma_periods and 20 in ma_periods:
            df['MA10_MA20_Ratio'] = df['MA10'] / df['MA20'].replace(0, np.nan)
        if 5 in ma_periods:
            df['Close_MA5_Ratio'] = df['Close'] / df['MA5'].replace(0, np.nan)
            df['MA5_Close_Ratio'] = df['MA5'] / df['Close']
        if 10 in ma_periods:
            df['MA10_Close_Ratio'] = df['MA10'] / df['Close']
        if 20 in ma_periods:
            df['MA20_Close_Ratio'] = df['MA20'] / df['Close']
        calculated_indicator_cols.extend([col for col in ['MA5_MA10_Ratio', 'MA10_MA20_Ratio', 'Close_MA5_Ratio', 'MA5_Close_Ratio', 'MA10_Close_Ratio', 'MA20_Close_Ratio'] if col in df.columns])

    # ========== RSI 計算 ========== 
    if calculate_all or 'RSI' in indicators_to_calculate:
        df['RSI'] = ta.RSI(df['Close'].values, timeperiod=atr_period) # 使用 atr_period 作為 timeperiod
        df['RSI'] = df['RSI'].fillna(50)
        calculated_indicator_cols.append('RSI')

    # ========== ATR 計算 ========== 
    if calculate_all or 'ATR' in indicators_to_calculate or 'KC' in indicators_to_calculate:
        df['ATR'] = ta.ATR(df['High'].values, df['Low'].values, df['Close'].values, timeperiod=atr_period)
        df['ATR'] = df['ATR'].fillna(df['ATR'].mean())
        calculated_indicator_cols.append('ATR')

    # ========== Keltner Channels (KC) 計算 ==========
    if calculate_all or 'KC' in indicators_to_calculate:
        # KC 依賴 ATR，如果 ATR 未計算，先計算 ATR
        if 'ATR' not in df.columns: # 重新檢查，因為上面可能已經計算過了
             df['ATR'] = ta.ATR(df['High'].values, df['Low'].values, df['Close'].values, timeperiod=atr_period)
             df['ATR'] = df['ATR'].fillna(df['ATR'].mean())
             calculated_indicator_cols.append('ATR') # Add ATR to calculated_indicator_cols if not already there
        
        df['KC_Middle'] = df['Close'].ewm(span=kc_period, adjust=False).mean()
        df['KC_Upper'] = df['KC_Middle'] + (df['ATR'] * kc_multiplier)
        df['KC_Lower'] = df['KC_Middle'] - (df['ATR'] * kc_multiplier)
        calculated_indicator_cols.extend(['KC_Middle', 'KC_Upper', 'KC_Lower'])

    # ========== Stochastic Oscillator (STOCH) 計算 ==========
    if calculate_all or 'STOCH' in indicators_to_calculate:
        df['STOCH_K'], df['STOCH_D'] = ta.STOCH(df['High'].values, df['Low'].values, df['Close'].values, 
                                            fastk_period=14, slowk_period=3, slowd_period=3)
        df['STOCH_K'] = df['STOCH_K'].fillna(50).clip(0, 100)
        df['STOCH_D'] = df['STOCH_D'].fillna(50).clip(0, 100)
        calculated_indicator_cols.extend(['STOCH_K', 'STOCH_D'])

    # ========== ADX ========== 
    if calculate_all or 'ADX' in indicators_to_calculate:
        df['ADX'] = ta.ADX(df['High'].values, df['Low'].values, df['Close'].values, timeperiod=atr_period) # 使用 atr_period
        df['ADX'] = df['ADX'].fillna(20).clip(0, 100)
        df['PDI'] = ta.PLUS_DI(df['High'].values, df['Low'].values, df['Close'].values, timeperiod=atr_period) # 使用 atr_period
        df['PDI'] = df['PDI'].fillna(20).clip(0, 100)
        df['MDI'] = ta.MINUS_DI(df['High'].values, df['Low'].values, df['Close'].values, timeperiod=atr_period) # 使用 atr_period
        df['MDI'] = df['MDI'].fillna(20).clip(0, 100)
        calculated_indicator_cols.extend(['ADX', 'PDI', 'MDI'])

    # ========== Volume Indicators ==========
    if (calculate_all or 'VOLUME_INDICATORS' in indicators_to_calculate) and 'Volume' in df.columns:
        df['VMA_20'] = df['Volume'].rolling(window=20, min_periods=1).mean()
        df['Volume_VMA_Ratio'] = df['Volume'] / df['VMA_20']
        df['Volume_VMA_Ratio'] = df['Volume_VMA_Ratio'].fillna(1.0)
        calculated_indicator_cols.extend(['VMA_20', 'Volume_VMA_Ratio'])
    
    # ========== Donchian Channels (DC) 計算 ==========
    if calculate_all or 'DC' in indicators_to_calculate:
        dc_period = 20 # 硬編碼，可能需要參數化
        df['DC_Upper'] = df['High'].rolling(window=dc_period, min_periods=1).max()
        df['DC_Lower'] = df['Low'].rolling(window=dc_period, min_periods=1).min()
        df['DC_Middle'] = (df['DC_Upper'] + df['DC_Lower']) / 2
        calculated_indicator_cols.extend(['DC_Upper', 'DC_Lower', 'DC_Middle'])
    
    # ========== Pin Bar (吞噬形態) 檢測 ==========
    if calculate_all or 'PIN_BAR' in indicators_to_calculate:
        # 計算 K 線實體大小
        df['Body'] = abs(df['Close'] - df['Open'])
        # 計算 K 線總範圍
        df['Range'] = df['High'] - df['Low']
        
        # 計算上下影線長度
        df['Upper_Wick'] = df['High'] - df[['Open', 'Close']].max(axis=1)
        df['Lower_Wick'] = df[['Open', 'Close']].min(axis=1) - df['Low']
        
        # 定義 Pin Bar 的條件
        body_ratio_threshold = 0.3 # 實體小於總範圍的 30%
        long_wick_ratio_threshold = 0.6 # 長影線大於總範圍的 60%
        short_wick_ratio_threshold = 0.1 # 短影線小於總範圍的 10%

        # 看漲吞噬形態 (Bullish Pin Bar)
        df['Bullish_Pin_Bar'] = (df['Body'] < df['Range'] * body_ratio_threshold) & \
                                (df['Lower_Wick'] > df['Range'] * long_wick_ratio_threshold) & \
                                (df['Upper_Wick'] < df['Range'] * short_wick_ratio_threshold) & \
                                (df['Close'] > df['Open'])
        
        # 看跌吞噬形態 (Bearish Pin Bar)
        df['Bearish_Pin_Bar'] = (df['Body'] < df['Range'] * body_ratio_threshold) & \
                                (df['Upper_Wick'] > df['Range'] * long_wick_ratio_threshold) & \
                                (df['Lower_Wick'] < df['Range'] * short_wick_ratio_threshold) & \
                                (df['Close'] < df['Open'])
        calculated_indicator_cols.extend(['Body', 'Range', 'Upper_Wick', 'Lower_Wick', 'Bullish_Pin_Bar', 'Bearish_Pin_Bar'])
    
    # ========== 額外的 EMA 計算 (用於特徵工程，但可選擇性計算) ==========
    # 'EMA' 標識所有額外 EMA，'EMA_X' 標識特定 EMA
    ema_periods_to_calculate = [10, 20, 25, 30, 35, 40, 45, 50, 200]
    for period in ema_periods_to_calculate:
        col_name = f'EMA_{period}'
        if calculate_all or 'EMA' in indicators_to_calculate or col_name.upper() in indicators_to_calculate:
            df[col_name] = df['Close'].ewm(span=period, adjust=False).mean()
            calculated_indicator_cols.append(col_name)

    # ========== ML 專用衍生特徵 ==========
    if calculate_all or 'ML_FEATURES' in indicators_to_calculate:
        # 趨勢特徵 (EMA50 vs EMA200)
        if 'EMA_50' in df.columns and 'EMA_200' in df.columns: # 這些必須先計算
            df['trend_ema'] = np.where(df['EMA_50'] > df['EMA_200'], 1, -1)
            calculated_indicator_cols.append('trend_ema')
            
        # 動能特徵 (MACD Power)
        if 'MACD' in df.columns and 'MACD_Signal' in df.columns and 'Close' in df.columns: # 這些必須先計算
            df['macd_power'] = (df['MACD'] - df['MACD_Signal']) / df['Close'] * 1000
            calculated_indicator_cols.append('macd_power')
            
        # 價格位置特徵 (距離 EMA200 的百分比)
        if 'Close' in df.columns and 'EMA_200' in df.columns: # EMA_200 必須先計算
            df['price_dist_ema200'] = (df['Close'] - df['EMA_200']) / df['EMA_200'] * 100
            calculated_indicator_cols.append('price_dist_ema200')

    # ========== 缺失值處理 ========== 
    # 只對實際計算過的指標列進行 ffill().fillna(0)，避免影響原始 OHLC 或未計算的列
    # 確保只處理存在於 DataFrame 中的列
    final_cols_to_process = [col for col in set(calculated_indicator_cols) if col in df.columns]
    for col in final_cols_to_process:
        df[col] = df[col].ffill().fillna(0) # 確保策略邏輯不會遇到 NaN

    # ========== 最終處理：移除無窮大與過大的值 ==========
    df = df.replace([np.inf, -np.inf], np.nan)
    
    return df