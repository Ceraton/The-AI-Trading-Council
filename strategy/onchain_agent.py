from .base_strategy import BaseStrategy
from typing import Dict, Any, Optional
from utils.logger import setup_logger
from data.blockchain_monitor import BlockchainMonitor

class OnChainAgent(BaseStrategy):
    """
    OnChain Agent - Blockchain Analysis
    
    Monitors whale wallets and large transfers to detect market movements
    before they impact exchange prices.
    
    Signals:
    - Whale moving TO exchange → BEARISH (potential sell)
    - Whale moving FROM exchange → BULLISH (accumulation)
    - Large transfers → Increased volatility expected
    """
    
    def __init__(self, network: str = 'ethereum'):
        super().__init__("OnChainAgent")
        self.logger = setup_logger(self.name)
        self.monitor = BlockchainMonitor(network)
        self.confidence_threshold = 0.6
        self.watchlist = []

    def update_watchlist(self, symbols: list):
        """Update watchlist for on-chain monitoring"""
        self.watchlist = symbols
        self.monitor.update_watchlist(symbols)
        self.logger.info(f"OnChain Watchlist Updated: {symbols}")
        
    async def on_tick(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return None
    
    async def on_candle(self, candle: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Analyzes on-chain activity and returns trading signal.
        """
        close_price = candle.get('close', 0)
        
        # Check whale activity
        # Note: In production, you'd extract the actual token symbol
        whale_data = await self.monitor.check_whale_activity('ETH')
        
        signal = None
        whale_signal = whale_data['whale_signal']
        confidence = whale_data['confidence']
        
        reasoning = {
            'whale_signal': whale_signal,
            'confidence': confidence,
            'large_transfers': whale_data['large_transfers'],
            'net_flow': whale_data['net_flow'],
            'details': whale_data['details']
        }
        
        if whale_signal == 'bullish' and confidence >= self.confidence_threshold:
            self.logger.info(f"OnChain: BULLISH signal (whales accumulating)")
            signal = {
                'side': 'buy',
                'price': close_price,
                'reasoning': reasoning,
                'agent': 'onchain',
                'vote': 'buy',
                'confidence': confidence
            }
        elif whale_signal == 'bearish' and confidence >= self.confidence_threshold:
            self.logger.info(f"OnChain: BEARISH signal (whales distributing)")
            signal = {
                'side': 'sell',
                'price': close_price,
                'reasoning': reasoning,
                'agent': 'onchain',
                'vote': 'sell',
                'confidence': confidence
            }
        else:
            # Neutral or low confidence
            signal = {
                'side': 'hold',
                'price': close_price,
                'reasoning': reasoning,
                'agent': 'onchain',
                'vote': 'hold',
                'confidence': confidence
            }
        
        return signal
    
    def get_whale_summary(self) -> Dict[str, Any]:
        """
        Returns summary of monitored whale wallets.
        """
        return {
            'network': self.monitor.network,
            'monitored_wallets': len(self.monitor.get_monitored_wallets()),
            'threshold_usd': self.monitor.transfer_threshold_usd
        }
