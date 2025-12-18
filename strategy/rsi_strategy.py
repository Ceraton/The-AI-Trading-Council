import backtrader as bt

class RSIStrategy(bt.Strategy):
    params = (
        ('period', 14),
        ('upper', 70),
        ('lower', 30),
    )

    def log(self, txt, dt=None):
        dt = dt or self.datas[0].datetime.date(0)
        print(f'{dt.isoformat()}, {txt}')

    def __init__(self):
        self.rsi = bt.indicators.RSI(
            self.datas[0], period=self.params.period
        )

    def next(self):
        # self.log(f'RSI: {self.rsi[0]:.2f}')

        if not self.position:
            if self.rsi[0] < self.params.lower:
                self.log(f'BUY CREATE (RSI {self.rsi[0]:.2f})')
                self.buy()
        else:
            if self.rsi[0] > self.params.upper:
                self.log(f'SELL CREATE (RSI {self.rsi[0]:.2f})')
                self.sell()
