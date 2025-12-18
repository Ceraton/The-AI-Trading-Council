import pandas as pd
import numpy as np
from .base_strategy import BaseStrategy
from typing import Dict, Any, Optional
from utils.logger import setup_logger
from utils.vesper_math import v_sma, v_std_dev, v_rsi # Vesper Core

class NewtonAgent(BaseStrategy):
    """
    Newton Agent: 'Action = Reaction'.
    Focussed on catching 'Falling Knives' using the Elasticity principle.
    Wakes up only during extreme 4-5 sigma crashes.
    """
    def __init__(self, sigma_threshold: float = 4.0, velocity_threshold: float = 0.03):
        super().__init__("NewtonAgent")
        self.logger = setup_logger(self.name)
        self.history = []
        self.sigma_threshold = sigma_threshold
        self.velocity_threshold = velocity_threshold # 3% crash in 5 mins
        self.min_history = 200 # Need 200 EMA context
        
    async def on_tick(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return None

    async def on_candle(self, candle: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        self.history.append(candle)
        if len(self.history) < self.min_history:
            return None
            
        df = pd.DataFrame(self.history)
        close_prices = df['close']
        volumes = df['volume']
        
        # 1. PHYSICS OF A CRASH: Standard Deviation (σ)
        data = df['close'].values
        volumes = df['volume'].values
        
        # Vesper: Vectorized Mean and Std Dev
        mean = v_sma(data, 20)[-1]
        std = v_std_dev(data, 20)[-1]
        z_score = abs(candle['close'] - mean) / std if std > 0 else 0
        
        # 2. VELOCITY: Price drops > 3% in last 5 candles (assuming 1m/5m timeframe)
        price_5m_ago = data[-6] if len(data) > 5 else data[0]
        velocity = (candle['close'] - price_5m_ago) / price_5m_ago
        
        # 3. EXTENSION: % below 200 EMA
        # Using SMA for Vesper Speedup (Approximation)
        ema200 = v_sma(data, 200)[-1]
        if np.isnan(ema200): ema200 = mean # Fallback if history < 200
        extension = (candle['close'] - ema200) / ema200
        
        # 4. EXHAUSTION: RSI < 15
        rsi_series = v_rsi(data, 14)
        rsi = rsi_series[-1]
        
        # 5. CLIMAX: Volume spike > 5x 20-candle average
        vol_avg = v_sma(volumes, 20)[-1]
        vol_spike = candle['volume'] / vol_avg if vol_avg > 0 else 0
        
        # --- KNIFE CATCH TRIGGER ---
        # "Wakes up only during crashes"
        is_crash = z_score >= self.sigma_threshold or velocity <= -self.velocity_threshold
        is_exhausted = rsi < 15 or extension < -0.05
        is_climax = vol_spike > 5.0
        
        if is_crash and is_exhausted and is_climax:
            self.logger.warning(f"🚨 NEWTON: IMPACT ZONE DETECTED! z-score: {z_score:.2f}, RSI: {rsi:.2f}, VolSpike: {vol_spike:.2f}")
            return {
                'vote': 'buy',
                'confidence': 0.9, # High conviction for anomalous bounce
                'agent': self.name,
                'price': candle['close'],
                'strategy': 'Knife Catch',
                'reasoning': {
                    'z_score': z_score,
                    'velocity': velocity,
                    'extension': extension,
                    'rsi': rsi,
                    'vol_spike': vol_spike
                }
            }
            
        return {'vote': 'hold', 'confidence': 0.5, 'agent': self.name}
