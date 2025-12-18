import asyncio
import numpy as np
from strategy.timegpt_agent import TimeGPTAgent
from strategy.chronos_agent import ChronosAgent

async def test_oracles():
    print("STARTING Testing Oracle Agents (TimeGPT + Chronos)...")
    
    # 1. Initialize Agents
    # TimeGPT will default to simulation if no API key
    timegpt = TimeGPTAgent(api_key=None) 
    # Chronos will use fallback simulation (we don't want to download 500MB here)
    chronos = ChronosAgent(model_size='tiny')
    
    # 2. Generate Synthetic "Bullish" Data
    # Use a clear upward sine wave + trend to trigger "Buy" signals
    print("Generating synthetic data...")
    history = []
    for i in range(100):
        # Linear trend + sine wave
        price = 100 + (i * 0.1) + np.sin(i * 0.2) * 2
        candle = {'close': price, 'volume': 100, 'timestamp': i}
        history.append(candle)
        
        # Feed history
        await timegpt.on_candle(candle)
        await chronos.on_candle(candle)
        
    print(f"Data generated. Last price: {history[-1]['close']:.2f}")
    
    # 3. Check for Signals
    print("\n🔮 Querying Oracles...")
    
    signal_gpt = await timegpt.on_candle(history[-1])
    if signal_gpt:
        print(f"✅ TimeGPT Signal: {signal_gpt['vote']} (Conf: {signal_gpt['confidence']:.2f})")
        print(f"   Reasoning: {signal_gpt['reasoning']}")
    else:
        print("❌ TimeGPT Silent (Unexpected for strong trend)")
        
    signal_chronos = await chronos.on_candle(history[-1])
    if signal_chronos:
        print(f"✅ Chronos Signal: {signal_chronos['vote']} (Conf: {signal_chronos['confidence']:.2f})")
        print(f"   Reasoning: {signal_chronos['reasoning']}")
    else:
        print("❌ Chronos Silent (Unexpected for strong trend)")
        
if __name__ == "__main__":
    asyncio.run(test_oracles())
