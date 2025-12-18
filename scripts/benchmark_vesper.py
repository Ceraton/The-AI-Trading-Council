import time
import numpy as np
import pandas as pd
import pandas_ta as ta
from utils.vesper_math import v_sma, v_rsi, v_bollinger

def benchmark():
    DATA_SIZE = 100_000
    print(f"IGNITING VESPER BENCHMARK (N={DATA_SIZE})")
    
    # Generate Synthetic Data
    data = np.random.rand(DATA_SIZE) * 100
    df = pd.DataFrame({'close': data})
    
    # --- SMA BENCHMARK ---
    print("\n[SMA (Window=20)]")
    
    # 1. Pandas-TA (Standard)
    start = time.perf_counter()
    pta = df.ta.sma(length=20)
    t_pta = time.perf_counter() - start
    print(f"Pandas-TA: {t_pta:.6f}s")
    
    # 2. Vesper (Vectorized)
    start = time.perf_counter()
    v_out = v_sma(data, 20)
    t_vesper = time.perf_counter() - start
    print(f"Vesper:    {t_vesper:.6f}s")
    
    speedup = t_pta / t_vesper if t_vesper > 0 else 0
    print(f"Speedup: {speedup:.2f}x")
    
    # Check Correctness (First non-NaN match)
    valid_idx = 20
    diff = abs(pta.iloc[valid_idx] - v_out[valid_idx])
    print(f"Accuracy Diff: {diff:.9f}")

    # --- RSI BENCHMARK ---
    print("\n[RSI (Window=14)]")
    
    # 1. Pandas-TA
    start = time.perf_counter()
    pta_rsi = df.ta.rsi(length=14)
    t_pta_rsi = time.perf_counter() - start
    print(f"Pandas-TA: {t_pta_rsi:.6f}s")
    
    # 2. Vesper
    start = time.perf_counter()
    v_rsi_out = v_rsi(data, 14)
    t_vesper_rsi = time.perf_counter() - start
    print(f"Vesper:    {t_vesper_rsi:.6f}s")
    
    speedup_rsi = t_pta_rsi / t_vesper_rsi if t_vesper_rsi > 0 else 0
    print(f"Speedup: {speedup_rsi:.2f}x")

    # --- BOLLINGER BENCHMARK ---
    print("\n[BOLLINGER (Window=20)]")
    
    start = time.perf_counter()
    u, m, l = v_bollinger(data, 20)
    t_bol = time.perf_counter() - start
    print(f"Vesper:    {t_bol:.6f}s")

if __name__ == "__main__":
    benchmark()
