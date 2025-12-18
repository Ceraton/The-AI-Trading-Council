from .base_strategy import BaseStrategy
from typing import Dict, Any, Optional, List
import pandas as pd
import numpy as np
from utils.logger import setup_logger

class SMAStrategy(BaseStrategy):
    def __init__(self, short_window: int = 10, long_window: int = 50):
        super().__init__("SMAStrategy")
        self.short_window = short_window
        self.long_window = long_window
        self.prices: List[float] = []
        self.logger = setup_logger(self.name)

    async def on_tick(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        # SMA strategy primarily works on candles/history, but can track real-time price
        return None

    async def on_candle(self, candle: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Expects candle data: {'close': float, ...}
        """
        close_price = candle.get('close')
        if close_price is None:
            return None

        self.prices.append(close_price)
        
        # Keep only necessary history
        if len(self.prices) > self.long_window + 1:
            self.prices.pop(0)

        if len(self.prices) < self.long_window:
            return None

        # Calculate SMAs
        df = pd.DataFrame({'close': self.prices})
        df['short_sma'] = df['close'].rolling(window=self.short_window).mean()
        df['long_sma'] = df['close'].rolling(window=self.long_window).mean()

        short_sma = df['short_sma'].iloc[-1]
        long_sma = df['long_sma'].iloc[-1]
        prev_short_sma = df['short_sma'].iloc[-2]
        prev_long_sma = df['long_sma'].iloc[-2]

        # Check for crossover
        # Bullish Crossover: Short crosses above Long
        if prev_short_sma <= prev_long_sma and short_sma > long_sma:
            self.logger.info(f"BUY Signal: Short SMA ({short_sma:.2f}) crossed above Long SMA ({long_sma:.2f})")
            return {'side': 'buy', 'price': close_price}
        
        # Bearish Crossover: Short crosses below Long
        elif prev_short_sma >= prev_long_sma and short_sma < long_sma:
            self.logger.info(f"SELL Signal: Short SMA ({short_sma:.2f}) crossed below Long SMA ({long_sma:.2f})")
            return {'side': 'sell', 'price': close_price}

        return None
