import pandas as pd
import pytest
import sys
import os
from datetime import datetime

# 將專案根目錄添加到 sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backtest.engine import BacktestEngine
from backtest.analyzer import BacktestAnalyzer

@pytest.fixture
def mock_db_data(monkeypatch):
    """
    使用 monkeypatch 模擬 DatabaseManager 的 fetch_data_flex 方法，
    使其返回一個固定的 DataFrame，避免測試時實際連接資料庫。
    """
    # 創建一個比 max_history_len (50) 更長的數據集
    data = {
        'Date': pd.to_datetime(pd.date_range(start='2023-01-01', periods=100, freq='D')),
        'Open': [100 + i for i in range(100)],
        'High': [102 + i for i in range(100)],
        'Low': [99 + i for i in range(100)],
        'Close': [101 + i for i in range(100)],
        'Volume': [1000 + i * 10 for i in range(100)]
    }
    mock_df = pd.DataFrame(data).set_index('Date')

    def mock_fetch_data(*args, **kwargs):
        return mock_df

    # 使用 monkeypatch 替換原始方法
    monkeypatch.setattr('common.db_utils.DatabaseManager.fetch_data_flex', mock_fetch_data)
    
    return mock_df

def test_backtest_engine_integration(mock_db_data):
    """
    測試 BacktestEngine 的整合功能：
    - 是否能成功初始化。
    - 是否能調用 run_backtest 執行回測。
    - 是否能處理模擬的數據。
    - 是否能返回有效的分析結果。
    """
    # 1. 初始化引擎
    engine = BacktestEngine(initial_capital=100000.0)

    # 2. 定義回測參數
    # 使用 DailyRangeReversalStrategy (ID 8)，因為它的邏輯相對簡單
    strategy_type = 8
    strategy_config = {
        'ma_period': 10,
        'reversal_threshold': 0.01,
        'max_history_len': 50  # 確保小於 mock_db_data 的長度
    }
    
    # 3. 執行回測
    # 由於 fetch_data_flex 已被模擬，這裡不會真的去連資料庫
    analyzer = engine.run_backtest(
        strategy_type=strategy_type,
        symbol='TEST001',
        cycle='1d',
        start_date='2023-01-01',
        end_date='2023-03-31',
        strategy_config=strategy_config,
        contract_size=1.0
    )

    # 4. 驗證結果
    assert analyzer is not None, "回測分析器不應為 None"
    assert isinstance(analyzer, BacktestAnalyzer), "返回的物件應為 BacktestAnalyzer 類型"

    metrics = analyzer.get_metrics()
    assert isinstance(metrics, dict), "分析指標應為字典"

    # 如果沒有交易，指標字典會是空的，這在整合測試中是可以接受的。
    # 我們關心的是整個流程是否能順利跑完。
    if not metrics:
        print("\n整合測試回測成功，但未產生任何交易。")
    else:
        assert 'Total Net Profit' in metrics, "分析指標應包含 'Total Net Profit'"
        assert isinstance(metrics.get('Total Trades'), int), "總交易次數應為整數"
        assert isinstance(metrics.get('Final Equity'), float), "最終資本應為浮點數"
        print(f"\n整合測試回測結果: 共 {metrics['Total Trades']} 筆交易，最終淨利 ${metrics['Total Net Profit']:.2f}")

