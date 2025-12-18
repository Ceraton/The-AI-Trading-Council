
import pandas as pd
import numpy as np
import asyncio
from typing import List, Dict, Type
from strategy.base_strategy import BaseStrategy

class BacktestEngine:
    """
    Simulates strategy execution on historical data.
    """
    def __init__(self, initial_capital: float = 10000.0, commission: float = 0.001):
        self.initial_capital = initial_capital
        self.commission = commission
        
    async def run(self, df: pd.DataFrame, strategy: BaseStrategy) -> Dict:
        """
        Runs the backtest.
        Returns metrics dict including equity curve.
        """
        capital = self.initial_capital
        position_size = 0.0 # Amount of base asset
        avg_entry_price = 0.0
        
        equity_curve = [] # List of {'timestamp', 'equity'}
        trades = [] # List of trade dicts
        
        # Ensure DF is sorted
        df = df.sort_values('timestamp')
        
        for idx, row in df.iterrows():
            timestamp = row['timestamp']
            close = row['close']
            
            # Construct candle
            candle = {
                'timestamp': timestamp,
                'open': row['open'],
                'high': row['high'],
                'low': row['low'],
                'close': row['close'],
                'volume': row['volume']
            }
            
            # Get Signal
            # We await because on_candle is async
            signal = await strategy.on_candle(candle)
            
            current_equity = capital + (position_size * close)
            
            if signal:
                side = signal['side']
                price = signal.get('price', close)
                
                # Simple execution logic: All-in / All-out for simplicity in lab
                # Or fixed bet size? Let's do All-in/All-out to see max potential
                
                if side == 'buy' and position_size == 0:
                    # Buy
                    cost = capital * (1 - self.commission)
                    position_size = cost / price
                    capital = 0
                    avg_entry_price = price
                    
                    trades.append({
                        'timestamp': timestamp,
                        'side': 'buy',
                        'price': price,
                        'amount': position_size,
                        'value': position_size * price
                    })
                    
                elif side == 'sell' and position_size > 0:
                    # Sell
                    proceeds = (position_size * price) * (1 - self.commission)
                    # PnL logic
                    pnl = proceeds - (position_size * avg_entry_price)
                    pnl_pct = (pnl / (position_size * avg_entry_price)) * 100
                    
                    capital = proceeds
                    position_size = 0
                    
                    trades.append({
                        'timestamp': timestamp,
                        'side': 'sell',
                        'price': price,
                        'amount': position_size, # This is post-trade size (0)
                        'value': proceeds,
                        'pnl': pnl,
                        'pnl_pct': pnl_pct
                    })
                    
            equity_curve.append({
                'timestamp': timestamp,
                'equity': capital + (position_size * close),
                'price': close
            })
            
        # Metrics
        df_equity = pd.DataFrame(equity_curve)
        if df_equity.empty:
            return {'trades': [], 'equity': pd.DataFrame(), 'metrics': {}}
            
        final_equity = df_equity.iloc[-1]['equity']
        total_return_pct = ((final_equity - self.initial_capital) / self.initial_capital) * 100
        
        # Max Drawdown
        df_equity['max_equity'] = df_equity['equity'].cummax()
        df_equity['drawdown'] = (df_equity['equity'] - df_equity['max_equity']) / df_equity['max_equity']
        max_drawdown = df_equity['drawdown'].min()
        
        metrics = {
            'Initial Capital': self.initial_capital,
            'Final Equity': final_equity,
            'Total Return': total_return_pct,
            'Max Drawdown': max_drawdown * 100,
            'Trades': len(trades)
        }
        
        return {
            'trades': pd.DataFrame(trades),
            'equity': df_equity,
            'metrics': metrics
        }
