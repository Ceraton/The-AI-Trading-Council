import backtrader as bt

class KeltnerStrategy(bt.Strategy):
    params = (
        ('period', 20),
        ('devfactor', 1.5),
    )

    def log(self, txt, dt=None):
        dt = dt or self.datas[0].datetime.date(0)
        print(f'{dt.isoformat()}, {txt}')

    def __init__(self):
        # ATR is needed for Keltner Channels. 
        # Keltner = EMA(Close) +/- devfactor * ATR
        self.atr = bt.indicators.ATR(self.datas[0], period=self.params.period)
        self.ema = bt.indicators.EMA(self.datas[0], period=self.params.period)
        
        self.upper = self.ema + self.params.devfactor * self.atr
        self.lower = self.ema - self.params.devfactor * self.atr

    def next(self):
        if not self.position:
            # Buy if close > upper (Trend Following) or Close < Lower (Reversion)?
            # Standard implementation: Trend following breakout
            if self.datas[0].close[0] > self.upper[0]:
                self.log(f'BUY CREATE (Keltner Breakout)')
                self.buy()
        else:
            # Sell if close crosses back below EMA (Trailing stop style) or Lower band
            if self.datas[0].close[0] < self.ema[0]:
                self.log(f'SELL CREATE (Keltner Exit)')
                self.sell()
