from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class BaseStrategy(ABC):
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    async def on_tick(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Called when new market data is received.
        Should return a trade signal (Dict) or None.
        """
        pass

    @abstractmethod
    async def on_candle(self, candle: Dict[str, Any]) -> Optional[Dict[str, Any]]:
         """
         Called when a new candle is closed.
         """
         pass
