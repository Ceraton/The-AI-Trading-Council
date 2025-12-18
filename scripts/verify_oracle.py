import asyncio
from strategy.chronos_agent import ChronosAgent
from strategy.timegpt_agent import TimeGPTAgent
import numpy as np

async def verify_oracle():
    print("🔮 Verifying Oracle Agents (Foundation Models)...")
    
    # Generate some fake price data (uptrend)
    prices = np.linspace(100, 110, 60).tolist()
    
    chronos = ChronosAgent()
    tgpt = TimeGPTAgent()
    
    # Feed history
    for p in prices:
        c_tick = {'close': p}
        await chronos.on_candle(c_tick)
        await tgpt.on_candle(c_tick)
        
    # Get last signals
    last_candle = {'close': prices[-1]}
    c_signal = await chronos.on_candle(last_candle)
    t_signal = await tgpt.on_candle(last_candle)
    
    print(f"Chronos Signal: {c_signal}")
    print(f"TimeGPT Signal: {t_signal}")
    
    if c_signal and t_signal:
        print("✅ Oracle Agents Are Prophesying correctly.")
    else:
        print("❌ Oracle Signal Failure (Check history depth).")

if __name__ == "__main__":
    asyncio.run(verify_oracle())
