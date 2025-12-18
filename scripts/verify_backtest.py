import asyncio
import pandas as pd
from backtesting.backtest_engine import BacktestEngine, CouncilStrategy
from strategy.meta_strategy import MetaStrategy
from strategy.technical_sub_agents import TrendAgent, OscillatorAgent, VolumeAgent

async def verify_backtest():
    print("🧪 Verifying Digital Twin Engine (Council Backtest)...")
    
    # 1. Setup Council
    agents = [TrendAgent(), OscillatorAgent(), VolumeAgent()]
    meta = MetaStrategy(agents, voting_method='weighted')
    
    # 2. Load Scenario
    df = pd.read_csv('data_storage/scenarios/ftx_collapse.csv')
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # 3. Run Engine
    engine = BacktestEngine(start_cash=10000.0)
    engine.run(df, strategy_class=CouncilStrategy, meta_strategy=meta)
    
    # 4. Check Metrics
    metrics = engine.get_metrics()
    print(f"Backtest Metrics: {metrics}")
    
    if metrics['final_value'] > 0:
        print("✅ Backtest Engine is Operational.")
    else:
        print("❌ Backtest Engine Failure.")

if __name__ == "__main__":
    asyncio.run(verify_backtest())
