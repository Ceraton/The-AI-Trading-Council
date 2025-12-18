import optuna
import asyncio
import os
import pandas as pd
from train import fetch_training_data
from ml.rl_agent import RLAgent
from data.data_storage import load_historical_data
from ml.feature_engineer import FeatureEngineer
from utils.logger import setup_logger

logger = setup_logger("AutoTuner")

def objective(trial, symbols, timeframe):
    # 1. Suggest Hyperparameters
    learning_rate = trial.suggest_float("learning_rate", 1e-6, 1e-4, log=True)
    ent_coef = trial.suggest_float("ent_coef", 0.001, 0.1, log=True)
    batch_size = trial.suggest_categorical("batch_size", [32, 64, 128])
    n_steps = trial.suggest_categorical("n_steps", [1024, 2048, 4096])

    # 2. Setup Data (Use a single walk-forward split for tuning speed)
    data_path = "data_storage/combined_training_data.csv"
    if not os.path.exists(data_path):
        # Fetch if missing
        asyncio.run(fetch_training_data(symbols, timeframe, limit=5000))
    
    df = load_historical_data(os.path.basename(data_path))
    fe = FeatureEngineer()
    df = fe.add_technical_indicators(df)
    
    split = int(len(df) * 0.8)
    train_df = df.iloc[:split]
    val_df = df.iloc[split:]

    # 3. Train
    model_path = f"tuning_trial_{trial.number}"
    agent = RLAgent(
        train_df, 
        learning_rate=learning_rate, 
        ent_coef=ent_coef, 
        batch_size=batch_size, 
        n_steps=n_steps,
        model_path=model_path,
        verbose=0 # Quiet during tuning
    )
    
    agent.train(total_timesteps=10000)
    
    # 4. Evaluate (Validation Reward)
    total_reward = 0
    obs = agent.env.reset()
    for _ in range(len(val_df) - 1):
        action, _ = agent.model.predict(obs, deterministic=True)
        obs, reward, done, info = agent.env.step(action)
        total_reward += reward[0]
        if done[0]: break
        
    return total_reward

if __name__ == "__main__":
    study = optuna.create_study(direction="maximize")
    study.optimize(lambda t: objective(t, ["BTC/USD"], "1h"), n_trials=20)
    
    logger.info("Tuning Complete!")
    logger.info(f"Best Params: {study.best_params}")
    logger.info(f"Best Reward: {study.best_value}")
    
    # Save best params
    import json
    with open("best_hyperparams.json", "w") as f:
        json.dump(study.best_params, f)
