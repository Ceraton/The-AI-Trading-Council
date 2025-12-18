from ml.trading_env import TradingEnv
import numpy as np

class OracleEnv(TradingEnv):
    """
    Plato: 'The Realm of Forms'.
    A 'cheating' environment where the observation includes the NEXT price.
    The goal is for the agent to see the 'Perfect Form' of the trade.
    """
    def _next_observation(self):
        # Base observation
        obs = super()._next_observation()
        
        # Add 'Hindsight' (The future price change)
        next_step = min(self.current_step + 1, len(self.df) - 1)
        future_price = self.df.iloc[next_step]['close']
        current_price = self.df.iloc[self.current_step]['close']
        
        # Normalize the future info
        future_change = (future_price - current_price) / current_price if current_price > 0 else 0
        
        # Append to observation
        oracle_obs = np.append(obs, [future_change])
        return oracle_obs.astype(np.float32)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Update observation space for the extra future field
        low = np.append(self.observation_space.low, [-10.0])
        high = np.append(self.observation_space.high, [10.0])
        self.observation_space = type(self.observation_space)(
            low=low.astype(np.float32), 
            high=high.astype(np.float32), 
            shape=(len(low),), 
            dtype=np.float32
        )
