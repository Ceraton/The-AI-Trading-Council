import backtrader as bt

class BollingerStrategy(bt.Strategy):
    params = (
        ('period', 20),
        ('devfactor', 2.0),
    )

    def log(self, txt, dt=None):
        dt = dt or self.datas[0].datetime.date(0)
        print(f'{dt.isoformat()}, {txt}')

    def __init__(self):
        self.boll = bt.indicators.BollingerBands(
            self.datas[0], period=self.params.period, devfactor=self.params.devfactor
        )

    def next(self):
        # Simply log the closing price
        # self.log(f'Close, {self.datas[0].close[0]}')

        if not self.position:
            # Buy if price touches lower band
            if self.datas[0].close[0] < self.boll.lines.bot[0]:
                self.log(f'BUY CREATE, {self.datas[0].close[0]:.2f}')
                self.buy()
        else:
            # Sell if price touches upper band
            if self.datas[0].close[0] > self.boll.lines.top[0]:
                self.log(f'SELL CREATE, {self.datas[0].close[0]:.2f}')
                self.sell()
