"""
Fetch LUNC/USD OHLCV data from Kraken
"""
import asyncio
import ccxt.async_support as ccxt

async def fetch_lunc_ohlcv():
    print("Fetching LUNC/USD from Kraken...")
    
    # Initialize Kraken exchange
    exchange = ccxt.kraken()
    
    try:
        # Load markets to see available symbols
        await exchange.load_markets()
        
        # Check if LUNC/USD exists
        symbol = 'LUNC/USD'
        if symbol in exchange.markets:
            print(f"✓ {symbol} is available on Kraken")
            
            # Fetch OHLCV data (last 100 candles, 1 hour timeframe)
            ohlcv = await exchange.fetch_ohlcv(symbol, timeframe='1h', limit=100)
            
            print(f"\nFetched {len(ohlcv)} candles")
            print("\nLatest 5 candles:")
            print("Timestamp                | Open      | High      | Low       | Close     | Volume")
            print("-" * 90)
            
            for candle in ohlcv[-5:]:
                timestamp = candle[0]
                open_price = candle[1]
                high = candle[2]
                low = candle[3]
                close = candle[4]
                volume = candle[5]
                
                from datetime import datetime
                dt = datetime.fromtimestamp(timestamp / 1000)
                
                print(f"{dt.strftime('%Y-%m-%d %H:%M:%S')} | ${open_price:.6f} | ${high:.6f} | ${low:.6f} | ${close:.6f} | {volume:,.0f}")
            
            # Current price
            ticker = await exchange.fetch_ticker(symbol)
            print(f"\nCurrent Price: ${ticker['last']:.6f}")
            print(f"24h Volume: {ticker['quoteVolume']:,.2f} USD")
            print(f"24h Change: {ticker['percentage']:.2f}%")
            
        else:
            print(f"✗ {symbol} is NOT available on Kraken")
            print("\nSearching for LUNC-related symbols...")
            
            lunc_symbols = [s for s in exchange.markets.keys() if 'LUNC' in s or 'LUNA' in s]
            if lunc_symbols:
                print(f"Found {len(lunc_symbols)} LUNC/LUNA symbols:")
                for s in lunc_symbols:
                    print(f"  - {s}")
            else:
                print("No LUNC symbols found on Kraken")
                
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await exchange.close()

if __name__ == "__main__":
    asyncio.run(fetch_lunc_ohlcv())
