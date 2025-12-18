from .base_strategy import BaseStrategy
from typing import Dict, Any, Optional, List
import pandas as pd
import numpy as np
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import VecNormalize, DummyVecEnv
from ml.feature_engineer import FeatureEngineer
from ml.trading_env import TradingEnv
from utils.logger import setup_logger
import os

class MLStrategy(BaseStrategy):
    def __init__(self, model_path='models/ppo_model', analyst_agent=None, onchain_agent=None):
        super().__init__("MLStrategy")
        self.logger = setup_logger(self.name)
        self.fe = FeatureEngineer()
        self.data_buffer: List[Dict] = []
        self.min_history = 50
        self.analyst_agent = analyst_agent
        self.onchain_agent = onchain_agent
        
        path = os.path.join(os.getcwd(), model_path)
        stats_path = os.path.join(os.getcwd(), 'models', 'vec_normalize.pkl')
        
        # Load Normalization Stats
        self.norm_env = None
        if os.path.exists(stats_path):
            try:
                # We need a dummy env to load stats into. 
                # Create a minimal valid TradingEnv to satisfy checks
                features = ['open', 'high', 'low', 'close', 'volume', 
                           'RSI', 'MACD_12_26_9', 'MACDh_12_26_9', 'MACDs_12_26_9',
                           'BBL_20_2.0', 'BBM_20_2.0', 'BBU_20_2.0', 'BBB_20_2.0', 'BBP_20_2.0',
                           'ATR', 'EMA_50', 'ADX_14', 'DMP_14', 'DMN_14', 'padding']
                
                dummy_data = {col: [100.0]*5 for col in features} 
                dummy_df = pd.DataFrame(dummy_data)
                env_maker = lambda: TradingEnv(dummy_df)
                
                self.norm_env = VecNormalize.load(stats_path, DummyVecEnv([env_maker]))
                self.norm_env.training = False 
                self.norm_env.norm_reward = False
                self.logger.info("Loaded Normalization Statistics.")
            except Exception as e:
                self.logger.error(f"Failed to load normalization stats: {e}")

        if os.path.exists(path + ".zip"):
            self.model = PPO.load(path)
            self.logger.info(f"Loaded ML model from {path}")
        else:
            self.logger.error(f"Model not found at {path}")
            self.model = None

    async def on_tick(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return None

    async def on_candle(self, candle: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        self.data_buffer.append(candle)
        if len(self.data_buffer) > 100: 
            self.data_buffer.pop(0)
            
        if len(self.data_buffer) < self.min_history:
            return None

        if not self.model:
            return None

        # Prepare Data
        df = pd.DataFrame(self.data_buffer)
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        df = self.fe.add_technical_indicators(df)
        df = self.fe.scale_data(df, ['open', 'high', 'low', 'close', 'volume', 'RSI', 'ATR'])
        
        if df.empty:
            return None

        # Filter strictly numeric columns
        df_numeric = df.select_dtypes(include=[np.number])

        # Get latest state
        if df_numeric.empty:
             return None
             
        current_features = df_numeric.iloc[-1].tolist()
        
        # Construct observation (Mocking balance)
        obs = np.array([10000.0, 0.0] + current_features).astype(np.float32)
        
        # Normalize Observation
        if self.norm_env:
            obs = self.norm_env.normalize_obs(obs)
        
        try:
            action, _states = self.model.predict(obs, deterministic=True)
            
            # Action Map: 0=Hold, 1=Buy, 2=Sell
            close_price = candle['close']
            
            # Extract key indicators for Reasoning
            last_row = df.iloc[-1]
            reasoning = {
                'RSI': float(last_row.get('RSI', 0)),
                'MACD': float(last_row.get('MACD_12_26_9', 0)),
                'ADX': float(last_row.get('ADX_14', 0)),
                'EMA_50': float(last_row.get('EMA_50', 0)),
                'Close': float(close_price),
                'ML_Action': int(action)
            }

            # --- HEURISTIC FUSION (The "Council" Logic inside the Strategy) ---
            sentiment_score = 50
            whale_signal = 'neutral'
            
            if self.analyst_agent:
                sentiment_score = self.analyst_agent.sentiment_score
                reasoning['Sentiment'] = sentiment_score
                
            if self.onchain_agent:
                # We can't await here easily if this wasn't async, but it is async!
                # However, onchain agent might not store state individually per candle.
                # Ideally, onchain agent runs in background and stores state.
                # For now, we assume onchain agent has a method to get latest summary or we blindly trust its last log.
                # To keep it simple, we just look at what the OnChain agent Object has, assuming it updates itself.
                # Actually, main.py loop runs agents sequentially. 
                # Let's assume neutral if we can't easily query.
                pass

            # FUSION RULES
            final_side = None
            
            if action == 1: # ML BUY
                # Veto if Sentiment is very bearish (<40)
                if sentiment_score < 40:
                    self.logger.info(f"ML BUY signal VETOED by Sentiment ({sentiment_score:.1f})")
                    final_side = 'hold' 
                    reasoning['Veto'] = 'Sentiment Bearish'
                else:
                    final_side = 'buy'
                    self.logger.info(f"ML BUY confirmed (Sentiment {sentiment_score:.1f})")

            elif action == 2: # ML SELL
                # Veto if Sentiment is very bullish (>60) ? Maybe not, take profit.
                # Let's say we sell unless Sentiment is Euphoric (>80)
                if sentiment_score > 80:
                    self.logger.info(f"ML SELL signal VETOED by Euphoria ({sentiment_score:.1f})")
                    final_side = 'hold'
                    reasoning['Veto'] = 'Sentiment Euphoric'
                else:
                    final_side = 'sell'
                    self.logger.info(f"ML SELL confirmed")
            
            if final_side and final_side != 'hold':
                return {'side': final_side, 'price': close_price, 'reasoning': reasoning}
            
        except Exception as e:
            self.logger.error(f"Prediction error: {e}")
            import traceback
            traceback.print_exc()
            
        return None
