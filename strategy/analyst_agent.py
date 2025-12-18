from .base_strategy import BaseStrategy
from typing import Dict, Any, Optional, List
from utils.logger import setup_logger
import random
import feedparser
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import asyncio

class AnalystAgent(BaseStrategy):
    """
    Analyst Agent - Real Sentiment Analysis (RSS + VADER)
    
    This agent analyzes market sentiment from real crypto news RSS feeds.
    It uses VADER (Valence Aware Dictionary and sEntiment Reasoner) to score headlines.
    
    Sources:
    - CoinDesk
    - Cointelegraph
    - CryptoSlate
    """
    
    def __init__(self):
        super().__init__("AnalystAgent")
        self.logger = setup_logger(self.name)
        self.sentiment_score = 50  # Neutral baseline (0-100 scale)
        self.confidence = 0.5
        self.analyzer = SentimentIntensityAnalyzer()
        
        # RSS Feeds
        self.feeds = [
            "https://cointelegraph.com/rss",
            "https://www.coindesk.com/arc/outboundfeeds/rss/",
            "https://cryptoslate.com/feed/"
        ]
        
        self.last_analysis_time = 0
        self.analysis_interval = 300  # Analyze every 5 minutes
        self.latest_headlines = []
        
        # Filter Lists
        self.watchlist = set()
        self.top_coins = {
            "BTC", "BITCOIN", 
            "ETH", "ETHEREUM", 
            "SOL", "SOLANA", 
            "XRP", "RIPPLE", 
            "BNB", "BINANCE", 
            "DOGE", "DOGECOIN", 
            "ADA", "CARDANO", 
            "AVAX", "AVALANCHE", 
            "DOT", "POLKADOT", 
            "MATIC", "POLYGON"
        }
        
        # Common Aliases for Ticker expansion
        self.aliases = {
            "BTC": ["BITCOIN"],
            "ETH": ["ETHEREUM", "ETHER"],
            "SOL": ["SOLANA"],
            "XRP": ["RIPPLE"],
            "DOGE": ["DOGECOIN"],
            "ADA": ["CARDANO"],
            "AVAX": ["AVALANCHE"],
            "DOT": ["POLKADOT"],
            "MATIC": ["POLYGON"],
            "SHIB": ["SHIBA", "INU"],
            "LUNC": ["LUNA", "TERRA"],
            "LINK": ["CHAINLINK"],
            "UNI": ["UNISWAP"],
            "LTC": ["LITECOIN"]
        }
    
    def update_watchlist(self, symbols: List[str]):
        """
        Updates the watchlist of coins to search for.
        Expects symbols like 'BTC/USD', 'LUNC/USD'.
        Automatically expands to known aliases.
        """
        new_set = set()
        for s in symbols:
            # Extract base symbol (e.g., BTC from BTC/USD)
            base = s.split('/')[0].upper()
            new_set.add(base)
            
            # Add Aliases
            if base in self.aliases:
                for alias in self.aliases[base]:
                    new_set.add(alias)
            
        self.watchlist = new_set
        self.logger.info(f"Analyst Watchlist Updated (with aliases): {self.watchlist}")

    async def on_tick(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return None
    
    async def on_candle(self, candle: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Analyzes sentiment and returns trading signal.
        Refreshes sentiment analysis if interval has passed.
        """
        import time
        current_time = time.time()
        
        # Refresh sentiment if needed
        if current_time - self.last_analysis_time > self.analysis_interval:
            await self._refresh_sentiment()
            self.last_analysis_time = current_time
        
        close_price = candle.get('close', 0)
        
        # Generate signal based on sentiment
        signal = None
        reasoning = {
            'sentiment_score': self.sentiment_score,
            'confidence': self.confidence,
            'source': 'rss_vader',
            'top_headlines': self.latest_headlines[:3],
            'filters': list(self.watchlist.union(self.top_coins))
        }
        
        # Thresholds: >60 Bullish, <40 Bearish
        if self.sentiment_score > 60:
            # Bullish sentiment
            self.logger.info(f"Analyst: BULLISH sentiment ({self.sentiment_score:.1f}/100)")
            signal = {
                'side': 'buy',
                'price': close_price,
                'reasoning': reasoning,
                'agent': 'analyst',
                'vote': 'buy',
                'confidence': self.confidence
            }
        elif self.sentiment_score < 40:
            # Bearish sentiment
            self.logger.info(f"Analyst: BEARISH sentiment ({self.sentiment_score:.1f}/100)")
            signal = {
                'side': 'sell',
                'price': close_price,
                'reasoning': reasoning,
                'agent': 'analyst',
                'vote': 'sell',
                'confidence': self.confidence
            }
        else:
            # Neutral - return hold vote
            signal = {
                'side': 'hold',
                'price': close_price,
                'reasoning': reasoning,
                'agent': 'analyst',
                'vote': 'hold',
                'confidence': self.confidence
            }
            
        return signal
    
    async def _refresh_sentiment(self):
        """
        Fetches RSS feeds and calculates average sentiment.
        Filters headlines based on Watchlist + Top 10.
        """
        self.logger.info("Fetching crypto news...")
        all_headlines = []
        
        # 1. Fetch Headlines
        for url in self.feeds:
            try:
                feed = feedparser.parse(url)
                if feed.entries:
                    # Get top 10 from each feed to ensure some coverage
                    for entry in feed.entries[:10]:
                        all_headlines.append(entry.title)
            except Exception as e:
                self.logger.error(f"Failed to fetch {url}: {e}")
        
        if not all_headlines:
            self.logger.warning("No news found, keeping previous sentiment.")
            return

        # 2. Filter & Analyze Sentiment
        total_score = 0
        count = 0
        scored_headlines = []
        
        # Combine filters
        # If watchlist is empty (e.g. startup), default to just Top 10 to avoid silence
        active_filters = self.watchlist.union(self.top_coins)
        
        for title in all_headlines:
            # Check if relevant (Regex for safety)
            title_upper = title.upper()
            is_relevant = False
            
            import re
            for keyword in active_filters:
                # Escape keyword just in case
                escaped = re.escape(keyword)
                # Word boundary check: \bKEYWORD\b
                if re.search(r'\b' + escaped + r'\b', title_upper):
                    is_relevant = True
                    break
            
            if not is_relevant:
                continue

            # VADER returns compound score -1 to 1
            vs = self.analyzer.polarity_scores(title)
            compound = vs['compound']
            
            # Normalize to 0-100
            # -1 -> 0, 0 -> 50, 1 -> 100
            normalized = (compound + 1) * 50
            
            total_score += normalized
            count += 1
            scored_headlines.append((title, normalized))
        
        # Result logic
        if count > 0:
            self.sentiment_score = total_score / count
            
            # Confidence Logic
            deviation = abs(self.sentiment_score - 50)
            self.confidence = 0.5 + (deviation / 100) # Base 0.5, max 1.0
            
            # Store sorted headlines (most impactful first)
            scored_headlines.sort(key=lambda x: abs(x[1] - 50), reverse=True)
            self.latest_headlines = [f"{h[0]} ({h[1]:.0f})" for h in scored_headlines]
            
            self.logger.info(f"Analyzed {count} relevant headlines. New Sentiment: {self.sentiment_score:.1f}")
        else:
            # No relevant news found - revert to Neutral with low confidence
            self.logger.info(f"No headlines matched filters {list(active_filters)[:5]}...")
            self.sentiment_score = 50
            self.confidence = 0.3
    
    def get_sentiment_breakdown(self) -> Dict[str, Any]:
        """
        Returns detailed sentiment breakdown for dashboard.
        """
        return {
            'overall_score': self.sentiment_score,
            'confidence': self.confidence,
            'headline_count': len(self.latest_headlines),
            'top_headlines': self.latest_headlines[:5]
        }
