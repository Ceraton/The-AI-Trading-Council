import asyncio
from .base_strategy import BaseStrategy
from typing import Dict, Any, Optional
from utils.logger import setup_logger
import pandas as pd
import numpy as np
from utils.vesper_math import v_sma, v_rsi # Vesper Core

class TrendAgent(BaseStrategy):
    """Focussed exclusively on trend following indicators (EMA, MACD)."""
    def __init__(self):
        super().__init__("TrendAgent")
        self.logger = setup_logger(self.name)
        self.history = []

    async def on_tick(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return None

    async def on_candle(self, candle: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        self.history.append(candle['close'])
        if len(self.history) < 26: return None # Need 26 for MACD
        
        # Vesper Acceleration
        data = np.array(self.history)
        
        # Using SMA as proxy for EMA in Vesper v1 for speed (or implement v_ema later)
        # For now, sticking to SMA speedup as per benchmark
        sma8 = v_sma(data, 8)[-1]
        sma21 = v_sma(data, 21)[-1]
        
        side = 'hold'
        confidence = 0.5
        if sma8 > sma21: 
            side = 'buy'
            confidence = 0.7
        elif sma8 < sma21: 
            side = 'sell'
            confidence = 0.7
            
        return {'vote': side, 'confidence': confidence, 'agent': self.name}

class OscillatorAgent(BaseStrategy):
    """Focussed exclusively on mean reversion indicators (RSI)."""
    def __init__(self):
        super().__init__("OscillatorAgent")
        self.logger = setup_logger(self.name)
        self.history = []

    async def on_tick(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return None

    async def on_candle(self, candle: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        self.history.append(candle['close'])
        if len(self.history) < 15: return None
        
        # Vesper Acceleration
        data = np.array(self.history)
        rsi_series = v_rsi(data, 14)
        rsi = rsi_series[-1]
        
        side = 'hold'
        confidence = 0.5
        if rsi < 30: 
            side = 'buy'
            confidence = 0.8 # Oversold
        elif rsi > 70: 
            side = 'sell'
            confidence = 0.8 # Overbought
            
        return {'vote': side, 'confidence': confidence, 'agent': self.name}

class VolumeAgent(BaseStrategy):
    """Focussed exclusively on volume confirmation (Price/Volume Divergence)."""
    def __init__(self):
        super().__init__("VolumeAgent")
        self.logger = setup_logger(self.name)
        self.history = []

    async def on_tick(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return None

    async def on_candle(self, candle: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        v = candle['volume']
        c = candle['close']
        self.history.append({'close': c, 'volume': v})
        if len(self.history) < 5: return None
        
        # Check if price is rising on increasing volume
        recent = self.history[-5:]
        price_up = recent[-1]['close'] > recent[0]['close']
        vol_up = recent[-1]['volume'] > np.mean([x['volume'] for x in recent])
        
        side = 'hold'
        confidence = 0.5
        if price_up and vol_up: 
            side = 'buy'
            confidence = 0.6
        elif not price_up and vol_up:
            side = 'sell'
            confidence = 0.6
            
        return {'vote': side, 'confidence': confidence, 'agent': self.name}
