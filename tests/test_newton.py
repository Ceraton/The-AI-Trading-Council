import asyncio
import pandas as pd
import numpy as np
from strategy.newton_agent import NewtonAgent
from execution.order_executor import OrderExecutor
from execution.paper_wallet import PaperWallet

async def test_newton_impact():
    print("STARTING Testing Newton Protocol: Impact Zone Detection...")
    
    agent = NewtonAgent(sigma_threshold=4.0, velocity_threshold=0.03)
    wallet = PaperWallet(initial_capital=10000)
    executor = OrderExecutor(exchange_client=None, paper_wallet=wallet)
    
    # 1. Generate 200 candles of "Peacetime" data
    history = []
    base_price = 100.0
    for i in range(200):
        price = base_price + np.random.normal(0, 0.1)
        history.append({'close': price, 'volume': 100})
        await agent.on_candle(history[-1])
        
    print(f"Peacetime complete. Last price: {history[-1]['close']:.2f}")
    
    # 2. TRIGGER THE CRASH: "The Falling Knife"
    # Velocity: >3% drop in 5 mins
    # Climax: >5x volume
    crash_price = base_price * 0.95 # 5% drop
    crash_volume = 1000 # 10x average
    
    crash_candle = {'close': crash_price, 'volume': crash_volume, 'timestamp': 123456789}
    signal = await agent.on_candle(crash_candle)
    
    if signal and signal.get('strategy') == 'Knife Catch':
        print(f"SUCCESS: Newton Agent triggered IMPACT ZONE! Signal: {signal['vote']} @ confidence {signal['confidence']}")
        print(f"  Reasoning: {signal['reasoning']}")
        
        # 3. Test Ladder Execution
        print("\nTesting Limit Ladder Execution...")
        total_amount = 1.0 # 1 unit of asset
        rungs = await executor.execute_ladder_order(signal, "BTC/USD", total_amount)
        
        if rungs and len(rungs) == 3:
            print(f"SUCCESS: Limit Ladder executed with {len(rungs)} rungs.")
            for i, rung in enumerate(rungs):
                print(f"  Rung {i+1}: {rung['amount']} @ ${rung['price']:.2f}")
            
            print(f"\nFinal Wallet Balance: {wallet.get_all_balances()}")
        else:
            print("❌ FAILURE: Ladder execution failed or returned unexpected number of rungs.")
    else:
        print("❌ FAILURE: Newton Agent failed to trigger during crash simulation.")

if __name__ == "__main__":
    asyncio.run(test_newton_impact())
