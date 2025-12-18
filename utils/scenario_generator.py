import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta

def generate_scenario(name, start_price, days, crash_start_day, drop_pct, volatility=0.02):
    """
    Generates a synthetic price crash scenario.
    """
    dates = [datetime(2022, 1, 1) + timedelta(days=i) for i in range(days)]
    prices = [start_price]
    
    for i in range(1, days):
        change = np.random.normal(0, volatility)
        
        # Apply crash logic
        if i >= crash_start_day and i < crash_start_day + 5: # 5 day crash
            change -= (drop_pct / 5)
            
        new_price = prices[-1] * (1 + change)
        prices.append(new_price)
        
    df = pd.DataFrame({
        'timestamp': dates,
        'open': prices,
        'high': [p * 1.01 for p in prices],
        'low': [p * 0.99 for p in prices],
        'close': prices,
        'volume': [1000 + np.random.randint(0, 5000) for _ in prices]
    })
    
    os.makedirs('data_storage/scenarios', exist_ok=True)
    filepath = f'data_storage/scenarios/{name}.csv'
    df.to_csv(filepath, index=False)
    print(f"Scenario {name} saved to {filepath}")

if __name__ == "__main__":
    # 1. FTX Scenario: -30% drop
    generate_scenario("ftx_collapse", 20000, 30, 10, 0.30)
    
    # 2. Luna Scenario: -99% drop (Extreme stress test)
    generate_scenario("luna_meltdown", 80, 20, 5, 0.99, volatility=0.1)
    
    # 3. Flash Crash: -15% in a short window
    generate_scenario("flash_crash", 50000, 15, 7, 0.15)
