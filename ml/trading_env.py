import gymnasium as gym
from gymnasium import spaces
import numpy as np
import pandas as pd
from typing import Optional

class TradingEnv(gym.Env):
    """
    A crypto trading environment for Reinforcement Learning.
    """
    metadata = {'render_modes': ['human']}

    def __init__(self, df: pd.DataFrame, initial_balance: float = 10000.0, fee_rate: float = 0.004, reward_mode: str = 'profit'):
        super(TradingEnv, self).__init__()
        # Drop non-numeric columns (like timestamp) for observation
        self.df = df.select_dtypes(include=[np.number])
        self.original_df = df # Keep original for rendering or other needs if necessary
        
        self.initial_balance = initial_balance
        self.fee_rate = fee_rate
        self.reward_mode = reward_mode
        
        # Actions: 0=Hold, 1=Buy, 2=Sell
        self.action_space = spaces.Discrete(3)
        
        # Observations: [Balance, Holdings, ...Features]
        self.observation_space = spaces.Box(
            low=0, high=1, shape=(len(self.df.columns) + 2,), dtype=np.float32
        )

        self.current_step = 0
        self.balance = initial_balance
        self.holdings = 0.0
        self.net_worth = initial_balance
        self.max_net_worth = initial_balance # for High Water Mark bonus
        self.returns_history = []
        self.steps_since_trade = 0

    def reset(self, seed: Optional[int] = None, options: Optional[dict] = None):
        super().reset(seed=seed)
        self.current_step = 0
        self.balance = self.initial_balance
        self.holdings = 0.0
        self.net_worth = self.initial_balance
        self.returns_history = []
        self.steps_since_trade = 0
        return self._next_observation(), {}

    def _next_observation(self):
        # Frame the observation
        obs = np.array([self.balance, self.holdings] + self.df.iloc[self.current_step].tolist())
        return obs.astype(np.float32)

    def step(self, action):
        current_price = self.df.iloc[self.current_step]['close']
        
        # Safety check for bad data
        if pd.isna(current_price) or current_price <= 0:
            current_price = self.df.iloc[self.current_step-1]['close'] if self.current_step > 0 else 1.0

        # Fee Rate (e.g., 0.6% for Coinbase Taker)
        # This penalizes the agent for over-trading
        # fee_rate = 0.006 used to be hardcoded, now using self.fee_rate

        # Execute Action
        if action == 1: # Buy
            # Buy with 10% of balance (simplified)
            amount = (self.balance * 0.1) / current_price
            cost = amount * current_price
            fee = cost * self.fee_rate
            
            if self.balance >= (cost + fee):
                self.balance -= (cost + fee)
                self.holdings += amount
                
        elif action == 2: # Sell
             # Sell all
             sale_value = self.holdings * current_price
             fee = sale_value * self.fee_rate
             
             self.balance += (sale_value - fee)
             self.holdings = 0

        self.current_step += 1
        done = self.current_step >= len(self.df) - 1

        # Calculate Reward (Change in Net Worth)
        new_net_worth = self.balance + (self.holdings * current_price)
        pct_change = ((new_net_worth - self.net_worth) / self.net_worth) * 100 if self.net_worth > 0 else 0
        self.returns_history.append(pct_change)
        
        # 1. Base Profit Reward
        reward = pct_change
        
        # 2. High Water Mark Bonus
        if new_net_worth > self.max_net_worth:
            reward += 1.0 
            self.max_net_worth = new_net_worth
            
        # 3. Trading Fee Penalty (Double impact to discourage churn)
        if action != 0:
            reward -= (self.fee_rate * 2) # Penalize the cost of trading
            self.steps_since_trade = 0
        else:
            self.steps_since_trade += 1

        # 4. Inaction Penalty (Discourage sitting in cash forever)
        if self.steps_since_trade > 100: # After 100 candles of doing nothing
            reward -= 0.01

        # 5. Volatility / Risk-Adjustment (Sharpe-ish)
        if len(self.returns_history) > 20: # Use rolling window for stability
            recent_returns = self.returns_history[-20:]
            volatility = np.std(recent_returns)
            if volatility > 2.0: # High volatility penalty
                reward -= (volatility * 0.1)
                
        # --- REWARD MODE: ACCURACY ---
        if self.reward_mode == 'accuracy':
            next_price = self.df.iloc[self.current_step]['close'] if self.current_step < len(self.df) else current_price
            price_change = next_price - current_price
            
            is_correct = False
            if action == 1 and price_change > 0: is_correct = True
            elif action == 2 and price_change < 0: is_correct = True
            
            if action != 0:
                reward = 1.0 if is_correct else -1.0
            else:
                reward = -0.05 # Small penalty for holding in accuracy mode

        # --- REWARD MODE: MOMENTUM (Heraclitus) ---
        elif self.reward_mode == 'momentum':
            # Reward following the recent trend
            ema_short = self.df.iloc[self.current_step].get('ema_20', current_price)
            ema_long = self.df.iloc[self.current_step].get('ema_50', current_price)
            trend_up = ema_short > ema_long
            
            if action == 1: # Buy in uptrend
                reward = 1.0 if trend_up else -0.5
            elif action == 2: # Sell in downtrend
                reward = 1.0 if not trend_up else -0.5
            else:
                reward = 0.0

        # --- REWARD MODE: MEAN REVERSION (Parmenides) ---
        elif self.reward_mode == 'mean_reversion':
            # Reward buying dips and selling rips
            rsi = self.df.iloc[self.current_step].get('rsi_14', 50)
            oversold = rsi < 30
            overbought = rsi > 70
            
            if action == 1: # Buy when oversold
                reward = 1.5 if oversold else -0.8
            elif action == 2: # Sell when overbought
                reward = 1.5 if overbought else -0.8
            else:
                reward = 0.0
                
        # Clip reward
        reward = np.clip(reward, -10, 10)
        
        if np.isnan(reward) or np.isinf(reward):
            reward = 0.0

        self.net_worth = new_net_worth
        
        obs = self._next_observation()
        obs = np.nan_to_num(obs)

        return obs, reward, done, False, {}

    def render(self):
        print(f'Step: {self.current_step}, Net Worth: {self.net_worth}')
