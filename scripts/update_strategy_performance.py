import os
import re
import json
from datetime import datetime
from typing import Dict, Any, List

REPORT_FILE = "docs/strategy_top_performances.md"

def format_metrics_to_markdown(metrics: Dict[str, Any]) -> str:
    """將指標字典格式化為 Markdown 表格行"""
    params = {k: v for k, v in metrics.items() if k not in [
        'Initial Capital', 'Final Equity', 'Total Return (%)', 'Total Net Profit',
        'Total Trades', 'Win Rate (%)', 'Profit Factor', 'Avg Win', 'Avg Loss',
        'Max Drawdown (%)', 'Sharpe Ratio', 'Start Date', 'End Date', 'Record Date'
    ]}
    
    param_str = ", ".join([f"{k}={v}" for k, v in params.items()])
    
    return (
        f"| {metrics.get('Record Date', 'N/A')} "
        f"| {metrics.get('Total Net Profit', 0):,.2f} "
        f"| {metrics.get('Total Return (%)', 0):.2f}% "
        f"| {metrics.get('Max Drawdown (%)', 0):.2f}% "
        f"| {metrics.get('Win Rate (%)', 0):.2f}% "
        f"| {metrics.get('Profit Factor', 0):.2f} "
        f"| {metrics.get('Start Date', 'N/A')} - {metrics.get('End Date', 'N/A')} "
        f"| `{param_str}` |\n"
    )

def parse_markdown_table(table_str: str) -> List[Dict[str, Any]]:
    """從 Markdown 表格字串解析指標列表"""
    lines = table_str.strip().split('\n')
    if len(lines) < 3: # 需要標題行、分隔行和至少一行數據
        return []

    header = [h.strip() for h in lines[0].split('|') if h.strip()]
    data_rows = lines[2:] # 跳過標題和分隔行

    parsed_metrics = []
    for row in data_rows:
        values = [v.strip() for v in row.split('|') if v.strip()]
        if len(values) == len(header):
            metric = {}
            # 簡化解析，只取需要的數據，參數字串待後續解析
            metric['Record Date'] = values[0]
            metric['Total Net Profit'] = float(values[1].replace(',', '').replace('$', ''))
            metric['Total Return (%)'] = float(values[2].replace('%', ''))
            metric['Max Drawdown (%)'] = float(values[3].replace('%', ''))
            metric['Win Rate (%)'] = float(values[4].replace('%', ''))
            metric['Profit Factor'] = float(values[5])
            
            date_range = values[6].split(' - ')
            metric['Start Date'] = date_range[0].strip() if len(date_range) > 0 else 'N/A'
            metric['End Date'] = date_range[1].strip() if len(date_range) > 1 else 'N/A'
            
            # 解析參數字串
            param_str = values[7].strip('`')
            for p_kv in param_str.split(', '):
                if '=' in p_kv:
                    k, v = p_kv.split('=', 1)
                    # 嘗試將參數值轉換為數字類型
                    try:
                        metric[k.strip()] = int(v.strip())
                    except ValueError:
                        try:
                            metric[k.strip()] = float(v.strip())
                        except ValueError:
                            metric[k.strip()] = v.strip() # 保持為字串
            parsed_metrics.append(metric)
    return parsed_metrics

def update_strategy_performance_report(
    strategy_name: str, 
    new_metrics: Dict[str, Any],
    report_file: str = REPORT_FILE
):
    """
    更新或新增策略的最佳表現記錄。
    
    Args:
        strategy_name (str): 策略名稱 (e.g., "CLMACrossoverStrategy_Pure").
        new_metrics (Dict[str, Any]): 包含策略績效和參數的字典。
        report_file (str): 記錄檔案路徑。
    """
    os.makedirs(os.path.dirname(report_file), exist_ok=True)
    
    content = ""
    if os.path.exists(report_file):
        with open(report_file, "r", encoding="utf-8") as f:
            content = f.read()

    # 設置本次記錄日期
    new_metrics['Record Date'] = datetime.now().strftime('%Y-%m-%d %H:%M')

    strategy_section_pattern = r"(## 策略: {})
(.*?)(?=\n## |$|\Z)".format(re.escape(strategy_name))
    match = re.search(strategy_section_pattern, content, re.DOTALL)

    current_strategy_metrics: List[Dict[str, Any]] = []
    before_section = ""
    after_section = ""
    
    if match:
        # 提取現有區段內容和前後部分
        before_section = content[:match.start()]
        existing_section_content = match.group(2)
        after_section = content[match.end():]

        # 從現有區段內容中解析出 Markdown 表格
        table_match = re.search(r"\|.*\|\n\|---.*---\|\n((?:\|.*\|\n)*)", existing_section_content)
        if table_match:
            table_str = table_match.group(0) # 包含標題、分隔線和數據
            current_strategy_metrics = parse_markdown_table(table_str)
        
    # 添加新指標
    current_strategy_metrics.append(new_metrics)
    
    # 根據 'Total Net Profit' 排序，取前三名 (由高到低)
    current_strategy_metrics.sort(key=lambda x: x.get('Total Net Profit', 0), reverse=True)
    top_3_metrics = current_strategy_metrics[:3]

    # 生成新的策略區段內容
    new_section_content = f"## 策略: {strategy_name}\n\n"
    new_section_content += "| 記錄日期 | 總淨利 | 總報酬率 | 最大回撤 | 勝率 | 獲利因子 | 回測區間 | 參數 |\n"
    new_section_content += "|---|---|---|---|---|---|---|---|
"
    for metric in top_3_metrics:
        new_section_content += format_metrics_to_markdown(metric)
    new_section_content += "\n" # 在區段末尾添加一個空行

    if match:
        # 替換現有區段
        updated_content = before_section + new_section_content + after_section
    else:
        # 如果是新策略，則附加到文件末尾
        updated_content = content.strip() + "\n\n" + new_section_content

    with open(report_file, "w", encoding="utf-8") as f:
        f.write(updated_content.strip() + "\n")

if __name__ == "__main__":
    # 範例使用 (從 run_strategy_backtest.py 獲取的 metrics)
    # 這裡的 metrics 應該包含 strategy_config 中的參數
    example_metrics = {
        'Initial Capital': 100000.0,
        'Final Equity': 125450.62,
        'Total Return (%)': 25.45,
        'Total Net Profit': 25450.63,
        'Total Trades': 76,
        'Win Rate (%)': 28.95,
        'Profit Factor': 2.01,
        'Avg Win': 2297.27,
        'Avg Loss': -464.62,
        'Max Drawdown (%)': -10.14,
        'Sharpe Ratio': 0.40,
        'Start Date': '2025-03-25',
        'End Date': '2025-12-24',
        'fast_window': 20,
        'slow_window': 60,
        'stopLossPercent': 0.0075,
        'tradeQuantity': 1,
        'max_history_len': 70
    }
    
    # 手動執行時，確保先創建 docs 目錄
    os.makedirs("docs", exist_ok=True)
    update_strategy_performance_report("CLMACrossoverStrategy_Pure", example_metrics)
    print(f"策略 'CLMACrossoverStrategy_Pure' 的最佳表現已更新到 {REPORT_FILE}")

    # 第二次測試，模擬不同參數組合或更高利潤的結果
    example_metrics_2 = {
        'Initial Capital': 100000.0,
        'Final Equity': 130000.00,
        'Total Return (%)': 30.00,
        'Total Net Profit': 30000.00,
        'Total Trades': 80,
        'Win Rate (%)': 35.00,
        'Profit Factor': 2.50,
        'Avg Win': 2500.00,
        'Avg Loss': -400.00,
        'Max Drawdown (%)': -8.00,
        'Sharpe Ratio': 0.50,
        'Start Date': '2025-03-25',
        'End Date': '2025-12-24',
        'fast_window': 15,
        'slow_window': 50,
        'stopLossPercent': 0.005,
        'tradeQuantity': 2,
        'max_history_len': 60
    }
    update_strategy_performance_report("CLMACrossoverStrategy_Pure", example_metrics_2)
    print(f"策略 'CLMACrossoverStrategy_Pure' 的最佳表現已再次更新到 {REPORT_FILE}")

    # 第三次測試，模擬第三個結果
    example_metrics_3 = {
        'Initial Capital': 100000.0,
        'Final Equity': 128000.00,
        'Total Return (%)': 28.00,
        'Total Net Profit': 28000.00,
        'Total Trades': 78,
        'Win Rate (%)': 30.00,
        'Profit Factor': 2.10,
        'Avg Win': 2300.00,
        'Avg Loss': -450.00,
        'Max Drawdown (%)': -9.00,
        'Sharpe Ratio': 0.45,
        'Start Date': '2025-03-25',
        'End Date': '2025-12-24',
        'fast_window': 22,
        'slow_window': 65,
        'stopLossPercent': 0.008,
        'tradeQuantity': 1,
        'max_history_len': 75
    }
    update_strategy_performance_report("CLMACrossoverStrategy_Pure", example_metrics_3)
    print(f"策略 'CLMACrossoverStrategy_Pure' 的最佳表現已再次更新到 {REPORT_FILE}")

    # 第四次測試，模擬第四個結果，應該會取代掉最差的那個
    example_metrics_4 = {
        'Initial Capital': 100000.0,
        'Final Equity': 129000.00,
        'Total Return (%)': 29.00,
        'Total Net Profit': 29000.00, # 這個淨利比 25450.63 和 28000.00 都高
        'Total Trades': 77,
        'Win Rate (%)': 32.00,
        'Profit Factor': 2.30,
        'Avg Win': 2400.00,
        'Avg Loss': -420.00,
        'Max Drawdown (%)': -7.50,
        'Sharpe Ratio': 0.48,
        'Start Date': '2025-03-25',
        'End Date': '2025-12-24',
        'fast_window': 18,
        'slow_window': 55,
        'stopLossPercent': 0.006,
        'tradeQuantity': 1,
        'max_history_len': 65
    }
    update_strategy_performance_report("CLMACrossoverStrategy_Pure", example_metrics_4)
    print(f"策略 'CLMACrossoverStrategy_Pure' 的最佳表現已再次更新到 {REPORT_FILE}")
