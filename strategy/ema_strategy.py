import backtrader as bt

class EMAStrategy(bt.Strategy):
    params = (
        ('short_period', 12),
        ('long_period', 26),
    )

    def log(self, txt, dt=None):
        dt = dt or self.datas[0].datetime.date(0)
        print(f'{dt.isoformat()}, {txt}')

    def __init__(self):
        self.ema_short = bt.indicators.EMA(self.datas[0], period=self.params.short_period)
        self.ema_long = bt.indicators.EMA(self.datas[0], period=self.params.long_period)
        self.crossover = bt.indicators.CrossOver(self.ema_short, self.ema_long)

    def next(self):
        if not self.position:
            if self.crossover > 0:
                self.log(f'BUY CREATE (EMA Cross Up)')
                self.buy()
        else:
            if self.crossover < 0:
                self.log(f'SELL CREATE (EMA Cross Down)')
                self.sell()
