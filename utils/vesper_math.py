import numpy as np
from typing import Tuple, Union

"""
VESPER CORE: High-Performance Vectorized Financial Math Kernel
--------------------------------------------------------------
Replaces iterative Python loops with optimized NumPy vector operations.
Target Speedup: 100x vs standard lists.
"""

def v_sma(data: np.ndarray, window: int) -> np.ndarray:
    """
    Vectorized Simple Moving Average.
    """
    if len(data) < window:
        return np.full_like(data, np.nan)
        
    weights = np.ones(window) / window
    # Use convolution for fast SMA
    sma = np.convolve(data, weights, mode='valid')
    
    # Pad beginning with NaNs to match original length
    padding = np.full(window - 1, np.nan)
    return np.concatenate((padding, sma))

def v_std_dev(data: np.ndarray, window: int) -> np.ndarray:
    """
    Vectorized Rolling Standard Deviation.
    """
    if len(data) < window:
        return np.full_like(data, np.nan)
        
    # E[X^2] - (E[X])^2
    avg_sq = v_sma(data ** 2, window)
    sq_avg = v_sma(data, window) ** 2
    
    variance = avg_sq - sq_avg
    # Clip negative variance due to floating point precision
    variance = np.maximum(variance, 0)
    
    return np.sqrt(variance)

def v_bollinger(data: np.ndarray, window: int, num_std: float = 2.0) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Vectorized Bollinger Bands.
    Returns: (Upper, Middle, Lower)
    """
    mid = v_sma(data, window)
    std = v_std_dev(data, window)
    
    upper = mid + (std * num_std)
    lower = mid - (std * num_std)
    
    return upper, mid, lower

def v_rsi(data: np.ndarray, window: int = 14) -> np.ndarray:
    """
    Vectorized Relative Strength Index (RSI).
    """
    delta = np.diff(data)
    # Pad delta to match data length (diff reduces length by 1)
    delta = np.concatenate(([0], delta))
    
    gains = np.maximum(delta, 0)
    losses = -np.minimum(delta, 0)
    
    # Calculate initial averages
    # Note: RSI typically uses Wilder's Smoothing, but SMA is often used for approximation in HFT
    # For strict compliance we can implement Wilder's loop later or use EMA approximation
    # Here we use standard SMA for pure vectorization speed
    
    avg_gain = v_sma(gains, window)
    avg_loss = v_sma(losses, window)
    
    rs = np.divide(avg_gain, avg_loss, out=np.zeros_like(avg_gain), where=avg_loss!=0)
    rsi = 100 - (100 / (1 + rs))
    
    # Handle division by zero (perfect score)
    rsi[avg_loss == 0] = 100
    rsi[avg_gain == 0] = 0
    
    return rsi

def v_keltner(high: np.ndarray, low: np.ndarray, close: np.ndarray, window: int = 20, atr_mult: float = 2.0) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Vectorized Keltner Channels.
    """
    # 1. Typical Price or EMA(Close)? Standard is EMA, using SMA here for Vesper v1
    # mid = v_sma(close, window) 
    
    # Using EMA approximation via convolution is hard, sticking to SMA for base
    mid_line = v_sma(close, window)
    
    # 2. True Range
    # TR = max(High-Low, abs(High-PrevClose), abs(Low-PrevClose))
    # Vectorized TR requires shifting arrays
    
    shift_close = np.roll(close, 1)
    shift_close[0] = close[0] # Pad first
    
    tr1 = high - low
    tr2 = np.abs(high - shift_close)
    tr3 = np.abs(low - shift_close)
    
    tr = np.maximum(np.maximum(tr1, tr2), tr3)
    atr = v_sma(tr, window) # Using SMA of TR for ATR
    
    upper = mid_line + (atr * atr_mult)
    lower = mid_line - (atr * atr_mult)
    
    return upper, mid_line, lower
