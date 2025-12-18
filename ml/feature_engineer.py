import pandas as pd
import pandas_ta as ta
from typing import List
from sklearn.preprocessing import StandardScaler # Changed from MinMaxScaler
from utils.logger import setup_logger
from utils.vesper_math import v_rsi, v_bollinger

class FeatureEngineer:
    def __init__(self):
        self.logger = setup_logger("FeatureEngineer")
        self.scaler = StandardScaler() # Standard scaling (mean=0, std=1) is better for PPO

    def add_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Adds technical indicators to the DataFrame using pandas-ta.
        Expected columns: open, high, low, close, volume
        """
        if df.empty:
            self.logger.warning("Empty DataFrame provided to FeatureEngineer.")
            return df

        # Ensure we have enough data (some indicators need period=14 etc)
        if len(df) < 50:
             self.logger.warning(f"Not enough data for indicators. Rows: {len(df)}")
             return df

        # Use Vesper Core for speed (vectorized NumPy math)
        closes = df['close'].values
        
        # RSI (Vesper Optimized)
        df['RSI'] = v_rsi(closes, window=14)
        
        # EMA (Pandas-TA C-optimization since v_ema is not implemented)
        df['EMA_50'] = df.ta.ema(length=50)
        
        # Bollinger Bands (Vesper Optimized)
        upper, mid, lower = v_bollinger(closes, window=20, num_std=2.0)
        df['BBM_20_2.0'] = mid
        df['BBU_20_2.0'] = upper
        df['BBL_20_2.0'] = lower

        # Remaining complex indicators still use Pandas-TA for now
        # MACD
        macd = df.ta.macd(fast=12, slow=26, signal=9)
        if macd is not None:
            df = pd.concat([df, macd], axis=1)

        # ATR (Volatility)
        df['ATR'] = df.ta.atr(length=14)
        
        # ADX (Trend Strength)
        adx = df.ta.adx(length=14)
        if adx is not None:
             df = pd.concat([df, adx], axis=1) # Adds ADX_14, DMP_14, DMN_14

        # Drop NaNs created by indicators
        df.dropna(inplace=True)
        
        self.logger.info(f"Vesper Core: Features added (Optimized). Shape: {df.shape}")
        return df

    def scale_data(self, df: pd.DataFrame, columns: List[str]) -> pd.DataFrame:
        """
        Scales valid numeric columns between 0 and 1.
        """
        if not columns:
            return df
        
        # Check if columns exist
        valid_cols = [c for c in columns if c in df.columns]
        if not valid_cols:
             return df
        
        df[valid_cols] = self.scaler.fit_transform(df[valid_cols])
        return df
