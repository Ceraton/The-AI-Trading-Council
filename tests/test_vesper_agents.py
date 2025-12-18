import asyncio
import numpy as np
import pandas as pd
from strategy.technical_sub_agents import TrendAgent, OscillatorAgent
from termcolor import colored

async def test_vesper_agents():
    print(colored("STARTING VESPER AGENTS VERIFICATION...", "cyan"))
    
    # Setup Agents
    trend = TrendAgent()
    osc = OscillatorAgent()
    
    # 1. Generate Trending Data (Bullish) to trigger TrendAgent
    # Create an uptrend where EMA8 > EMA21
    print("\n[Scenario 1: Bullish Trend]")
    x = np.linspace(0, 50, 60)
    prices = 100 + x + np.random.normal(0, 1, 60)
    
    # Feed candles
    last_signal_trend = None
    for i, p in enumerate(prices):
        candle = {'close': p, 'volume': 1000}
        sig = await trend.on_candle(candle)
        if sig: last_signal_trend = sig
        
        # Checking Oscillator too
        await osc.on_candle(candle)

    if last_signal_trend and last_signal_trend['vote'] == 'buy':
        print(colored(f"TrendAgent correctly identified UPTREND: {last_signal_trend}", "green"))
    else:
        print(colored(f"TrendAgent FAILED to identify uptrend. Last: {last_signal_trend}", "red"))

    # 2. Generate Oscillating Data (Overbought) to trigger OscillatorAgent
    # Sine wave
    print("\n[Scenario 2: Overbought Sine Wave]")
    # Reset Oscillator history? Ideally yes, but agents are persistent.
    # We'll just feed enough new data to flush the buffer (window 14)
    x = np.linspace(0, 20, 30)
    # Sine wave peaking at 180 (Overbought?)
    # RSI calc requires diffs. Sharp rise = high RSI.
    prices_sine = 100 + 10 * x # Steep linear rise => High RSI
    
    last_signal_osc = None
    for p in prices_sine:
        candle = {'close': p, 'volume': 1000}
        sig = await osc.on_candle(candle)
        if sig: last_signal_osc = sig

    # Expect SELL signal or at least overbought confidence
    if last_signal_osc and last_signal_osc.get('vote') == 'sell':
         print(colored(f"OscillatorAgent correctly identified OVERBOUGHT (High RSI): {last_signal_osc}", "green"))
    elif last_signal_osc and last_signal_osc.get('confidence') > 0.5:
         # Depending on RSI logic, might be just high confidence
         print(colored(f"OscillatorAgent Signal: {last_signal_osc} (Check if reasonable)", "yellow"))
    else:
         print(colored(f"OscillatorAgent FAILED. Last: {last_signal_osc}", "red"))

    print(colored("\nVESPER VERIFICATION COMPLETE", "cyan"))

if __name__ == "__main__":
    asyncio.run(test_vesper_agents())
