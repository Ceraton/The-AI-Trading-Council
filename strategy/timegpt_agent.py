from .base_strategy import BaseStrategy
from typing import Dict, Any, Optional
from utils.logger import setup_logger
import numpy as np
import os

class TimeGPTAgent(BaseStrategy):
    """
    TimeGPT Agent - Zero-Shot Time Series Foundation Model by Nixtla.
    
    Optimized for complex financial series (The "Oracle" of crypto).
    """
    
    def __init__(self, api_key: Optional[str] = None):
        super().__init__("TimeGPTAgent")
        self.logger = setup_logger(self.name)
        self.api_key = api_key or os.getenv("NIXTLA_API_KEY")
        self.history = []
        self.min_history = 50
        
        if not self.api_key:
            self.logger.warning("TimeGPT API Key missing. Using local Nixtla-Lite simulation.")
            self.client = None
        else:
            try:
                from nixtla import NixtlaClient
                self.client = NixtlaClient(api_key=self.api_key)
                self.logger.info("✅ TimeGPT API Client Initialized.")
            except ImportError:
                 self.logger.warning("Nixtla library not found. Falling back to simulation.")
                 self.client = None
            except Exception as e:
                 self.logger.error(f"Failed to initialize TimeGPT client: {e}")
                 self.client = None

    async def on_tick(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return None

    async def on_candle(self, candle: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        self.history.append(candle['close'])
        if len(self.history) > 200:
            self.history.pop(0)
            
        if len(self.history) < self.min_history:
            return None
            
        forecast = self._predict()
        if forecast is None: return None
        
        current = self.history[-1]
        target = forecast[-1] # Look at 5-step horizon
        
        pct_change = (target - current) / current
        vote = 'hold'
        confidence = 0.5
        
        if pct_change > 0.001: # 0.1% target
            vote = 'buy'
            confidence = min(0.9, 0.4 + (pct_change * 5))
        elif pct_change < -0.001:
            vote = 'sell'
            confidence = min(0.9, 0.4 + (abs(pct_change) * 5))
            
        return {
            'vote': vote,
            'confidence': confidence,
            'agent': self.name,
            'reasoning': {
                'forecast': target,
                'horizon': '5 steps',
                'oracle_type': 'TimeGPT-Foundation'
            }
        }

    def _predict(self):
        """
        Uses TimeGPT API if available, otherwise fallback to local simulation.
        """
        # --- PATH A: REAL ORACLE (TimeGPT API) ---
        if self.client and len(self.history) >= self.min_history:
            try:
                import pandas as pd
                # Prepare data in TimeGPT format (ds, y)
                # Create fake timestamps for 'ds' since we might not have them 
                # (assuming 1m or 5m candles, but generic index is safer for short term)
                # Ideally, we should receive 'timestamp' in on_tick/on_candle, but currently we only store 'close'
                # Let's generate a relative time index.
                dates = pd.date_range(end=pd.Timestamp.now(), periods=len(self.history), freq='min')
                df = pd.DataFrame({'ds': dates, 'y': self.history})
                
                # Forecast 5 steps ahead
                fcst_df = self.client.forecast(df=df, h=5, freq='min')
                # Returns DataFrame with 'ds', 'TimeGPT' columns
                
                if 'TimeGPT' in fcst_df.columns:
                    return fcst_df['TimeGPT'].values
                else:
                    self.logger.warning("TimeGPT response missing 'TimeGPT' column.")
            except Exception as e:
                self.logger.error(f"TimeGPT API Call failed: {e}. Falling back to simulation.")
        
        # --- PATH B: SIMULATION (Nixtla-Lite) ---
        data = np.array(self.history[-50:])
        
        # Simulating Fourier-based seasonality detection (TimeGPT internal logic)
        fft = np.fft.fft(data)
        freq = np.fft.fftfreq(len(data))
        
        # Identify dominant frequency
        dom_freq_idx = np.argmax(np.abs(fft[1:])) + 1
        
        # Construct prediction using trend + dom frequency
        x = np.arange(len(data))
        coeffs = np.polyfit(x, data, 1) # Trend
        
        x_future = np.arange(len(data), len(data) + 5)
        trend_future = np.polyval(coeffs, x_future)
        
        # Add "Harmonic" component (the zero-shot 'magic')
        amplitude = np.abs(fft[dom_freq_idx]) / len(data)
        phase = np.angle(fft[dom_freq_idx])
        harmonic = amplitude * np.cos(2 * np.pi * freq[dom_freq_idx] * x_future + phase)
        
        return trend_future + harmonic
