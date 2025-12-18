import backtrader as bt

class MACDStrategy(bt.Strategy):
    params = (
        ('period_me1', 12),
        ('period_me2', 26),
        ('period_signal', 9),
    )

    def log(self, txt, dt=None):
        dt = dt or self.datas[0].datetime.date(0)
        print(f'{dt.isoformat()}, {txt}')

    def __init__(self):
        self.macd = bt.indicators.MACD(
            self.datas[0],
            period_me1=self.params.period_me1,
            period_me2=self.params.period_me2,
            period_signal=self.params.period_signal
        )
        self.crossover = bt.indicators.CrossOver(self.macd.macd, self.macd.signal)

    def next(self):
        if not self.position:
            # Buy if MACD crosses above Signal
            if self.crossover > 0:
                self.log(f'BUY CREATE (MACD X Signal)')
                self.buy()
        else:
            # Sell if MACD crosses below Signal
            if self.crossover < 0:
                self.log(f'SELL CREATE (MACD X Signal)')
                self.sell()
