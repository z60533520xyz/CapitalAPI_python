# 1. 專案簡介與系統架構

## 1.1 系統總覽

本專案是一個基於群益 Capital API 的量化交易系統框架。其核心理念是將系統劃分為三個獨立但協同工作的層級：數據層、策略層與執行層，以實現高度模組化與可擴充性。

```mermaid
graph TD
    subgraph Data_Layer [數據層 (Data ETL)]
        A[Capital API] -->|下載歷史數據| B(原始數據)
        B -->|清洗/儲存/週期轉換| C[(MySQL 資料庫)]
    end

    subgraph Strategy_Layer [策略層 (Strategy Logic)]
        E[BaseStrategy (策略抽象基底類別)]
        F[Your_Strategy] -->|繼承| E
    end

    subgraph Execution_Layer [執行層 (Backtest & Live Trading)]
        C -->|提供歷史數據| H[回測引擎]
        H -->|1. 驅動策略| F
        H -->|2. 模擬下單| I[模擬券商]
        I -->|產生績效報告| J[分析模組]

        K[Capital API] -->|提供即時行情| L[實盤交易引擎]
        L -->|1. 驅動策略| F
        L -->|2. 真實下單| A
    end
```

## 1.2 核心模組概覽

本專案的目錄結構清晰地反映了其核心功能分層：

*   `data_etl/`: **數據工程層**。負責從 Capital API 下載歷史數據，進行清洗、轉換，並生成不同時間週期的 K 線資料，最終存儲於 MySQL 資料庫。這是所有策略研究與交易的基礎。
*   `strategy/`: **策略邏輯層**。存放所有交易策略的實現。每個策略都應繼承自 `base_strategy.py`，確保能同時被回測和實盤引擎調用。
*   `backtest/`: **回測功能層**。用於驗證策略在歷史數據上的表現。它會讀取資料庫中的數據，模擬交易過程並產出績效報告。
*   `live_trading/`: **實盤交易層**。負責連接即時行情，執行策略邏輯，並進行真實的下單交易。
*   `scripts/`: **輔助腳本**。提供方便的批次檔來執行日常任務，例如每日自動更新所有數據。
*   `docs/`: **專案文件**。存放您正在閱讀的這些說明文件。

## 1.3 專案目錄結構

以下為目前專案的實際目錄結構：

```
capital_python/
├── data_etl/              # 數據工程模組
│   ├── futures_data_updater.py  # 期貨分鐘 K 線更新器
│   ├── cycle_data_updater.py    # 週期 K 線生成器
│   └── integrated_updater.py    # 整合型更新腳本
│
├── strategy/              # 策略庫
│   ├── base_strategy.py       # 策略基礎類別
│   └── ...                    # 各式策略實作
│
├── backtest/              # 回測系統
│   ├── engine.py              # 回測主引擎
│   └── analyzer.py            # 績效分析模組
│
├── live_trading/          # 實盤系統
│   ├── trader.py              # 實盤主程式
│   └── monitor.py             # 帳戶監控
│
├── scripts/               # 自動化腳本
│   ├── daily_update_task.bat  # 每日數據更新任務
│   └── run_cycle_updater.bat  # 執行週期更新器
│
├── docs/                  # 專案文件
├── models/                # 機器學習模型
├── tests/                 # 測試代碼
├── config.ini             # 專案設定檔
└── entry_point.py         # 程式主入口
```
