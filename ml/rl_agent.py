from stable_baselines3 import PPO, DQN
from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize, SubprocVecEnv
from ml.trading_env import TradingEnv
import pandas as pd
import os


from stable_baselines3.common.callbacks import BaseCallback

# Export for external use
MODELS_DIR = os.path.join(os.getcwd(), 'models')
if not os.path.exists(MODELS_DIR):
    os.makedirs(MODELS_DIR)

class SocratesCallback(BaseCallback):
    """
    Socrates: 'I know that I know nothing.'
    Adversarial Entropy Regularization: Increases entropy penalty if the model
    exhibits 'Hubris' (high confidence on losing trades).
    """
    def __init__(self, verbose=0):
        super(SocratesCallback, self).__init__(verbose)
        self.base_ent_coef = 0.01
        
    def _on_step(self) -> bool:
        # Check recent rewards (simplified hubris detection)
        # In a real implementation, we would inspect the action distribution
        # but for this environment, we can tie it to the Reward variance.
        rewards = self.locals.get("rewards")
        if rewards is not None:
            # If the model is getting negative rewards, we nudge entropy UP
            # to force more exploration/humility
            avg_reward = sum(rewards) / len(rewards)
            if avg_reward < 0:
                # Nudge entropy up to discourage over-confidence in failing strategies
                new_ent = min(0.1, self.model.ent_coef + 0.001)
                self.model.ent_coef = new_ent
            else:
                # Slowly return to base confidence
                self.model.ent_coef = max(self.base_ent_coef, self.model.ent_coef - 0.0005)
        return True

class RLAgent:
    def __init__(self, df: pd.DataFrame, algorithm='PPO', fee_rate=0.004, reward_mode='profit', resume=False, model_path="ppo_model", n_envs=1, socratic=False, is_oracle=False, **kwargs):
        # 1. Create Vetorized Env
        def make_env():
            if is_oracle:
                from ml.oracle_env import OracleEnv
                return OracleEnv(df, fee_rate=fee_rate, reward_mode=reward_mode)
            else:
                return TradingEnv(df, fee_rate=fee_rate, reward_mode=reward_mode)
            
        self.socratic_callback = SocratesCallback() if socratic else None
        
        if n_envs > 1:
            # Multi-core training
            self.venv = SubprocVecEnv([make_env for _ in range(n_envs)])
        else:
            self.venv = DummyVecEnv([make_env])
        
        # 2. Normalize Env (Critical for PPO stability)
        # norm_obs=True: Normalizes inputs (features)
        # norm_reward=True: Normalizes rewards (stabilizes value_loss)
        self.env = VecNormalize(self.venv, norm_obs=True, norm_reward=True, clip_obs=10.)
        
        
        # Resume Logic/Load
        self.model_path = os.path.join(MODELS_DIR, model_path)
        stats_path = os.path.join(MODELS_DIR, "vec_normalize.pkl")
        
        if resume and os.path.exists(self.model_path + ".zip") and os.path.exists(stats_path):
             print(f"RESUMING training from {self.model_path}...")
             
             # Load Environment Stats
             self.env = VecNormalize.load(stats_path, self.venv)
             # Re-clip to ensure safety
             self.env.clip_obs = 10.
             self.env.training = True # Important ensuring it updates
             
             # Load Model
             if algorithm == 'PPO':
                 self.model = PPO.load(self.model_path, env=self.env, verbose=1, **kwargs)
             elif algorithm == 'DQN':
                 self.model = DQN.load(self.model_path, env=self.env, verbose=1, **kwargs)
        else:
            if resume:
                 print(f"Warning: Resume requested but {self.model_path} not found. Starting fresh.")
            
            # Default fresh start
            # Add TensorBoard logging path to kwargs
            if 'tensorboard_log' not in kwargs:
                kwargs['tensorboard_log'] = os.path.join("logs", "tensorboard")
            if 'verbose' not in kwargs:
                kwargs['verbose'] = 1
            
            if algorithm == 'PPO':
                self.model = PPO('MlpPolicy', self.env, **kwargs)
            elif algorithm == 'DQN':
                self.model = DQN('MlpPolicy', self.env, **kwargs)
            else:
                raise ValueError("Algorithm must be PPO or DQN")

    def train(self, total_timesteps=10000, callbacks=None):
        print(f"Training agent for {total_timesteps} timesteps...")
        
        # Check for Socrates mode in callbacks
        if callbacks is None: callbacks = []
        if hasattr(self, 'socratic_callback') and self.socratic_callback:
            callbacks.append(self.socratic_callback)
            
        self.model.learn(total_timesteps=total_timesteps, callback=callbacks)
        print("Training complete.")

    def save(self, filename):
        path = os.path.join(MODELS_DIR, filename)
        self.model.save(path)
        
        # Save Normalization Statistics
        stats_path = os.path.join(MODELS_DIR, "vec_normalize.pkl")
        self.env.save(stats_path)
        print(f"Model saved to {path}, Stats to {stats_path}")

    def load(self, filename):
        path = os.path.join(MODELS_DIR, filename)
        if os.path.exists(path + ".zip"):
             # SB3 loads with class method usually, but instance method exists too depending on version
             # Better to re-instantiate or load via class
             pass
        # Simplified for now
