import pandas as pd
import numpy as np
import logging
from typing import List, Dict

class BacktestAnalyzer:
    """
    回測績效分析器
    """
    def __init__(self, initial_capital: float = 1000000.0):
        self.initial_capital = initial_capital
        self.trades: List[Dict] = []
        self.equity_curve: List[Dict] = []
        
    def add_trade(self, trade: Dict):
        """記錄一筆交易"""
        self.trades.append(trade)
        
    def update_equity(self, date, equity):
        """更新權益曲線"""
        self.equity_curve.append({'date': date, 'equity': equity})
        
    def get_metrics(self) -> Dict:
        """計算並返回績效指標"""
        if not self.trades:
            return {}
            
        df_trades = pd.DataFrame(self.trades)
        df_equity = pd.DataFrame(self.equity_curve)
        
        if df_equity.empty:
            return {}
            
        df_equity['date'] = pd.to_datetime(df_equity['date'])
        df_equity.set_index('date', inplace=True)
        
        # 1. 基本損益指標
        total_pnl = df_trades['pnl'].sum()
        total_trades = len(df_trades)
        winning_trades = len(df_trades[df_trades['pnl'] > 0])
        losing_trades = len(df_trades[df_trades['pnl'] <= 0])
        win_rate = winning_trades / total_trades if total_trades > 0 else 0
        
        avg_win = df_trades[df_trades['pnl'] > 0]['pnl'].mean() if winning_trades > 0 else 0
        avg_loss = df_trades[df_trades['pnl'] <= 0]['pnl'].mean() if losing_trades > 0 else 0
        profit_factor = abs(df_trades[df_trades['pnl'] > 0]['pnl'].sum() / df_trades[df_trades['pnl'] <= 0]['pnl'].sum()) if losing_trades > 0 else float('inf')
        
        # 2. 回撤 (Drawdown)
        df_equity['peak'] = df_equity['equity'].cummax()
        df_equity['drawdown'] = (df_equity['equity'] - df_equity['peak']) / df_equity['peak']
        max_drawdown = df_equity['drawdown'].min()
        
        # 3. 夏普比率 (Sharpe Ratio) - 簡化版 (假設無風險利率為0)
        df_equity['returns'] = df_equity['equity'].pct_change()
        daily_returns = df_equity['returns'].mean()
        daily_std = df_equity['returns'].std()
        
        # 假設是 2小時K線，一年約 1250 根 (視交易時間而定)，這裡簡單假設年化因子
        # 如果 equity curve 是逐筆更新的，這裡的 Sharpe 可能不準確，最好是轉為日權益
        sharpe_ratio = (daily_returns / daily_std) * np.sqrt(252) if daily_std != 0 else 0
        
        return {
            'Initial Capital': self.initial_capital,
            'Final Equity': self.equity_curve[-1]['equity'],
            'Total Return (%)': (self.equity_curve[-1]['equity'] - self.initial_capital) / self.initial_capital * 100,
            'Total Net Profit': total_pnl,
            'Total Trades': total_trades,
            'Win Rate (%)': win_rate * 100,
            'Profit Factor': profit_factor,
            'Avg Win': avg_win,
            'Avg Loss': avg_loss,
            'Max Drawdown (%)': max_drawdown * 100,
            'Sharpe Ratio': sharpe_ratio
        }
        
    def print_report(self):
        """印出績效報告"""
        metrics = self.get_metrics()
        if not metrics:
            print("無交易記錄")
            return
            
        print("\n" + "="*40)
        print("       回測績效報告 (Backtest Report)")
        print("="*40)
        print(f"初始資金: {metrics['Initial Capital']:,.2f}")
        print(f"最終權益: {metrics['Final Equity']:,.2f}")
        print(f"總報酬率: {metrics['Total Return (%)']:.2f}%")
        print(f"總淨利  : {metrics['Total Net Profit']:,.2f}")
        print("-" * 40)
        print(f"總交易次數: {metrics['Total Trades']}")
        print(f"勝率      : {metrics['Win Rate (%)']:.2f}%")
        print(f"獲利因子  : {metrics['Profit Factor']:.2f}")
        print(f"平均獲利  : {metrics['Avg Win']:,.2f}")
        print(f"平均虧損  : {metrics['Avg Loss']:,.2f}")
        print("-" * 40)
        print(f"最大回撤  : {metrics['Max Drawdown (%)']:.2f}%")
        print(f"夏普比率  : {metrics['Sharpe Ratio']:.2f}")
        print("="*40 + "\n")
