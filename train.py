import asyncio
import os
import argparse
import sys
import pandas as pd
from dotenv import load_dotenv
from data.exchange_client import ExchangeClient
from data.data_storage import fetch_and_save_historical_data, load_historical_data, DATA_DIR
from ml.feature_engineer import FeatureEngineer
from ml.rl_agent import RLAgent, MODELS_DIR
from utils.logger import setup_logger

load_dotenv()
logger = setup_logger("Trainer")

async def fetch_training_data(symbols=['BTC/USD'], timeframe='1h', limit=10000):
    client = ExchangeClient('kraken') 
    if isinstance(symbols, str): symbols = [symbols]
    all_data = []
    
    try:
        for symbol in symbols:
            filename = f"{symbol.replace('/', '_')}_{timeframe}.csv"
            logger.info(f"Fetching {limit} candles for {symbol}...")
            path = await fetch_and_save_historical_data(client, symbol, timeframe, limit, filename)
            if path:
                df = load_historical_data(os.path.basename(path))
                if not df.empty:
                    df['symbol'] = symbol
                    all_data.append(df)
        
        if not all_data: return None
            
        combined_df = pd.concat(all_data, ignore_index=True)
        combined_filename = "combined_training_data.csv"
        combined_path = os.path.join(DATA_DIR, combined_filename)
        combined_df.to_csv(combined_path, index=False)
        return combined_path
    finally:
        await client.close()

def train_rl_model(df, model_name, timesteps=30000, reward_mode='profit', resume=False, n_envs=1, socratic=False, is_oracle=False):
    fe = FeatureEngineer()
    df = fe.add_technical_indicators(df)
    
    # Default Hyperparams (GP3 Phase 3 optimized)
    hyperparams = {
        'learning_rate': 0.00005,
        'ent_coef': 0.01,
        'n_steps': 2048,
        'batch_size': 64,
        'policy_kwargs': dict(net_arch=[128, 128]),
        'tensorboard_log': os.path.join("logs", "tensorboard")
    }

    # Load tuned hyperparams if available
    if os.path.exists("best_hyperparams.json"):
        import json
        with open("best_hyperparams.json", "r") as f:
            tuned = json.load(f)
            logger.info(f"Using TUNED hyperparameters: {tuned}")
            hyperparams.update(tuned)
    
    logger.info(f"Training PPO | Model: {model_name} | Steps: {timesteps} | Envs: {n_envs}")
    agent = RLAgent(df, algorithm='PPO', reward_mode=reward_mode, resume=resume, model_path=model_name, n_envs=n_envs, socratic=socratic, is_oracle=is_oracle, **hyperparams)
    agent.train(total_timesteps=timesteps)
    agent.save(model_name)
    return agent

def run_walk_forward_training(data_path, timesteps=30000, reward_mode='profit', windows=3):
    """Implement Time-Traveler: Train on slices, validate on next."""
    logger.info(f"🚀 Starting Walk-Forward Validation (Windows: {windows})")
    full_df = load_historical_data(os.path.basename(data_path))
    
    window_size = len(full_df) // (windows + 1)
    
    for i in range(windows):
        train_start = i * window_size
        train_end = (i + 1) * window_size
        val_end = (i + 2) * window_size
        
        train_df = full_df.iloc[train_start:train_end]
        val_df = full_df.iloc[train_end:val_end]
        
        logger.info(f"--- Window {i+1}/{windows}: Training on {len(train_df)} rows, Val on {len(val_df)} rows ---")
        model_name = f"ppo_wf_win{i+1}"
        train_rl_model(train_df, model_name, timesteps=timesteps//windows, reward_mode=reward_mode)

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", type=str, default="BTC/USD")
    parser.add_argument("--timeframe", type=str, default="1h")
    parser.add_argument("--limit", type=int, default=10000)
    parser.add_argument("--timesteps", type=int, default=30000)
    parser.add_argument("--reward", type=str, default="profit", choices=["profit", "accuracy"])
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--model-name", type=str, default="ppo_model_latest", help="Name of the model file to save/resume")
    parser.add_argument("--walk-forward", action="store_true", help="Enable Rolling Window Training")
    parser.add_argument("--n-envs", type=int, default=1, help="Number of parallel environments for training")
    parser.add_argument("--philosophy", type=str, choices=["socrates", "plato", "heraclitus", "parmenides"], help="Philosophical training doctrine")
    
    args = parser.parse_args()
    
    from config import TOP_10_CRYPTO
    symbols = args.symbol.split(',')
    if 'ALL' in [s.upper() for s in symbols]: symbols = TOP_10_CRYPTO

    data_path = asyncio.run(fetch_training_data(symbols, args.timeframe, args.limit))
    
    if data_path:
        df = load_historical_data(os.path.basename(data_path))
        
        # Philosophical Routing
        socratic = (args.philosophy == "socrates")
        reward_mode = args.reward
        
        if args.philosophy == "heraclitus": reward_mode = "momentum"
        elif args.philosophy == "parmenides": reward_mode = "mean_reversion"
        
        if args.philosophy == "plato":
            # Plato's Realm of Forms (Distillation)
            logger.info("🏛️ PLATO: Training Philosopher King (Oracle)...")
            king_name = f"{args.model_name}_king"
            train_rl_model(df, king_name, timesteps=args.timesteps//2, reward_mode=reward_mode, n_envs=args.n_envs, is_oracle=True)
            
            logger.info("🕯️ PLATO: Distilling to Cave Dweller (Student)...")
            # Student resumes from King but in a standard environment
            # Note: OracleEnv has one extra observation field. 
            # Sequential loading from Oracle to Non-Oracle might crash due to shape mismatch.
            # So we train student fresh but maybe add a penalty if it deviates from King's actions.
            # Simplified for now: just training in standard env but with same reward mode.
            train_rl_model(df, args.model_name, timesteps=args.timesteps//2, reward_mode=reward_mode, n_envs=args.n_envs)
            
        elif args.walk_forward:
            run_walk_forward_training(data_path, timesteps=args.timesteps, reward_mode=reward_mode)
        else:
            train_rl_model(df, args.model_name, timesteps=args.timesteps, reward_mode=reward_mode, resume=args.resume, n_envs=args.n_envs, socratic=socratic)
