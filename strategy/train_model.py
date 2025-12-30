import sys
import os
import logging
import pandas as pd
import numpy as np
import joblib
from datetime import datetime
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.metrics import accuracy_score, classification_report
from sklearn.feature_selection import SelectKBest, f_classif

# 添加專案根目錄到 sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.db_utils import DatabaseManager
from common.indicators import calculate_indicators

# 設定日誌
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def create_label(df, threshold=0.007):
    """
    產生目標標籤 (三分類)
    
    Args:
        df: 包含 Close 欄位的 DataFrame
        threshold: 漲跌閾值 (預設 0.7%)
        
    Returns:
        df: 加入 Label 欄位的 DataFrame
            1: Long (上漲超過 threshold)
            -1: Short (下跌超過 threshold)
            0: Neutral (其他)
    """
    future_price = df['close'].shift(-1)
    price_change_ratio = future_price / df['close']
    
    conditions = [
        (price_change_ratio > 1 + threshold),
        (price_change_ratio < 1 - threshold)
    ]
    choices = [1, -1]
    df['Label'] = np.select(conditions, choices, default=0)
    return df

def train_pipeline(symbol='CL0000', cycle=9, days=365, use_grid_search=False):
    """
    完整的模型訓練流程
    
    Args:
        symbol: 商品代碼
        cycle: 週期代碼
        days: 抓取天數
        use_grid_search: 是否使用 GridSearchCV (會花較長時間)
    """
    logging.info("="*60)
    logging.info(f"開始訓練流程")
    logging.info(f"商品: {symbol}, 週期: {cycle}, 天數: {days}")
    logging.info("="*60)
    
    # 1. 獲取資料
    logging.info("\n[步驟 1/10] 從資料庫載入資料...")
    db = DatabaseManager()
    df = db.fetch_kline_data(symbol, cycle, days)
    
    if df.empty:
        logging.error("無資料可供訓練，請確認資料庫中是否有資料")
        return
        
    logging.info(f"成功載入 {len(df)} 筆原始 K 線資料")
    logging.info(f"時間範圍: {df['date'].min()} ~ {df['date'].max()}")
    
    # 2. 計算技術指標
    logging.info("\n[步驟 2/10] 計算技術指標...")
    try:
        df = calculate_indicators(df)
    except Exception as e:
        logging.error(f"計算指標時發生錯誤: {e}")
        import traceback
        traceback.print_exc()
        return
        
    original_len = len(df)
    df = df.dropna()
    logging.info(f"指標計算完成，移除 NaN 後剩餘 {len(df)} 筆 (移除 {original_len - len(df)} 筆)")
    
    # 3. 產生標籤
    logging.info("\n[步驟 3/10] 產生目標標籤...")
    df = create_label(df, threshold=0.007)
    df = df.dropna(subset=['Label'])
    
    label_dist = df['Label'].value_counts()
    logging.info(f"標籤分佈:\n{label_dist}")
    logging.info(f"有效訓練資料: {len(df)} 筆")
    
    # 4. 準備特徵與標籤
    logging.info("\n[步驟 4/10] 準備特徵矩陣...")
    # 排除非特徵欄位
    exclude_cols = ['date', 'Label', 'open', 'high', 'low', 'close', 'volume', 
                    'Open', 'High', 'Low', 'Close', 'Volume', 'Date']
    feature_cols = [c for c in df.columns if c not in exclude_cols]
    
    # 只保留數值型特徵
    X = df[feature_cols].select_dtypes(include=[np.number])
    y = df['Label']
    
    feature_cols = X.columns.tolist()
    logging.info(f"特徵數量: {len(feature_cols)}")
    
    # 5. 分割資料 (時間序列，不打亂)
    logging.info("\n[步驟 5/10] 分割訓練集與測試集...")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, shuffle=False
    )
    logging.info(f"訓練集: {len(X_train)} 筆, 測試集: {len(X_test)} 筆")
    
    # 6. 特徵標準化
    logging.info("\n[步驟 6/10] 特徵標準化...")
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # 7. 特徵選擇
    logging.info("\n[步驟 7/10] 特徵選擇...")
    k = min(90, X_train.shape[1])
    selector = SelectKBest(f_classif, k=k)
    X_train_selected = selector.fit_transform(X_train_scaled, y_train)
    X_test_selected = selector.transform(X_test_scaled)
    
    selected_indices = selector.get_support(indices=True)
    selected_features = [feature_cols[i] for i in selected_indices]
    logging.info(f"從 {len(feature_cols)} 個特徵中選擇 {k} 個最佳特徵")
    logging.info(f"前 10 個重要特徵: {selected_features[:10]}")
    
    # 8. 訓練模型
    logging.info("\n[步驟 8/10] 訓練模型...")
    
    if use_grid_search:
        logging.info("使用 GridSearchCV 進行超參數調優 (這可能需要較長時間)...")
        param_grid = {
            'n_estimators': [100, 200],
            'max_depth': [10, 20],
            'min_samples_leaf': [2, 4],
            'max_features': ['sqrt', 'log2']
        }
        
        rf = RandomForestClassifier(random_state=42, class_weight='balanced')
        grid_search = GridSearchCV(rf, param_grid, cv=3, scoring='accuracy', n_jobs=-1, verbose=1)
        grid_search.fit(X_train_selected, y_train)
        
        model = grid_search.best_estimator_
        logging.info(f"最佳參數: {grid_search.best_params_}")
    else:
        logging.info("使用預設參數訓練 RandomForest...")
        model = RandomForestClassifier(
            n_estimators=100, 
            max_depth=10, 
            min_samples_leaf=2,
            class_weight='balanced', 
            random_state=42
        )
        model.fit(X_train_selected, y_train)
    
    # 9. 評估模型
    logging.info("\n[步驟 9/10] 評估模型...")
    y_pred = model.predict(X_test_selected)
    acc = accuracy_score(y_test, y_pred)
    
    logging.info(f"\n測試集準確率: {acc:.4f}")
    logging.info("\n分類報告:")
    logging.info("\n" + classification_report(y_test, y_pred, 
                                              target_names=['Short', 'Neutral', 'Long']))
    
    # 特徵重要性
    importances = model.feature_importances_
    feature_importance_df = pd.DataFrame({
        'Feature': selected_features,
        'Importance': importances
    }).sort_values(by='Importance', ascending=False)
    
    logging.info("\n前 10 個最重要特徵:")
    logging.info("\n" + feature_importance_df.head(10).to_string(index=False))
    
    # 10. 儲存模型
    logging.info("\n[步驟 10/10] 儲存模型...")
    models_dir = 'models'
    if not os.path.exists(models_dir):
        os.makedirs(models_dir)
        
    joblib.dump(model, os.path.join(models_dir, 'model.pkl'))
    joblib.dump(scaler, os.path.join(models_dir, 'scaler.pkl'))
    joblib.dump(selector, os.path.join(models_dir, 'selector.pkl'))
    joblib.dump(feature_cols, os.path.join(models_dir, 'feature_names.pkl'))
    
    logging.info(f"模型已儲存至 {models_dir}/ 資料夾")
    logging.info(f"  - model.pkl: 訓練好的 RandomForest 模型")
    logging.info(f"  - scaler.pkl: StandardScaler")
    logging.info(f"  - selector.pkl: SelectKBest 特徵選擇器")
    logging.info(f"  - feature_names.pkl: 原始特徵名稱列表")
    
    logging.info("\n" + "="*60)
    logging.info("訓練完成！")
    logging.info("="*60)

if __name__ == "__main__":
    # 可以透過命令列參數自訂
    import argparse
    parser = argparse.ArgumentParser(description='訓練 ML 交易模型')
    parser.add_argument('--symbol', type=str, default='CL0000', help='商品代碼')
    parser.add_argument('--cycle', type=int, default=9, help='週期代碼')
    parser.add_argument('--days', type=int, default=365, help='抓取天數')
    parser.add_argument('--grid-search', action='store_true', help='使用 GridSearchCV')
    
    args = parser.parse_args()
    
    train_pipeline(
        symbol=args.symbol,
        cycle=args.cycle,
        days=args.days,
        use_grid_search=args.grid_search
    )
