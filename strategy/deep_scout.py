from typing import Tuple, Dict, Any, Optional
from data.exchange_client import ExchangeClient
from strategy.analyst_agent import AnalystAgent
import asyncio

class DeepScout:
    """
    Deep Scout - Market Scanner Module
    
    Conducts on-demand analysis of a specific asset by combining:
    1. Real-time Market Data (Price, Volume)
    2. Targeted Sentiment Analysis (RSS Feeds)
    """
    
    def __init__(self):
        pass

    async def analyze(self, symbol: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Runs a full scout mission on the target symbol.
        Returns (price_data, sentiment_data).
        """
        # 1. Fetch Market Data
        # We instantiate a temporary client for this request
        client = ExchangeClient('kraken') 
        ticker_sym = f"{symbol}/USD"
        
        price_data = {}
        target_pair = ticker_sym
        
        try:
            # Try USD pair first
            ticker = await client.fetch_ticker(ticker_sym)
        except:
            # Try USDT pair fallback
            try:
                target_pair = f"{symbol}/USDT"
                ticker = await client.fetch_ticker(target_pair)
            except:
                ticker = None
        
        if ticker:
            price_data = {
                'price': ticker.get('last'),
                'vol': ticker.get('baseVolume'),
                'change': ticker.get('percentage')
            }
            
        await client.close()
        
        # 2. Analyze Sentiment
        agent = AnalystAgent()
        
        # FORCE FOCUS: Clear default top_coins so we ONLY analyze the target symbol
        agent.top_coins = set() 
        
        # Update watchlist to force this symbol to be relevant
        # Use the base symbol (e.g. DOGE) via update_watchlist logic
        agent.update_watchlist([target_pair])
        
        # Trigger explicit refresh
        await agent._refresh_sentiment()
        
        sentiment_data = agent.get_sentiment_breakdown()
        
        return price_data, sentiment_data
