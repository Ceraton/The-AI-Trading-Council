import backtrader as bt

class CombinedStrategy(bt.Strategy):
    """
    Combines RSI, MACD, EMA, and Bollinger Bands.
    Conservative approach: Requires at least 3 positive signals to Buy.
    """
    params = (
        ('rsi_period', 14),
        ('ema_short', 12),
        ('ema_long', 26),
        ('bb_period', 20),
        ('bb_dev', 2.0),
    )

    def log(self, txt, dt=None):
        dt = dt or self.datas[0].datetime.date(0)
        print(f'{dt.isoformat()}, {txt}')

    def __init__(self):
        # 1. RSI
        self.rsi = bt.indicators.RSI(period=self.params.rsi_period)
        
        # 2. MACD
        self.macd = bt.indicators.MACD(period_me1=12, period_me2=26, period_signal=9)
        
        # 3. EMA
        self.ema_short = bt.indicators.EMA(period=self.params.ema_short)
        self.ema_long = bt.indicators.EMA(period=self.params.ema_long)
        
        # 4. Bollinger
        self.boll = bt.indicators.BollingerBands(period=self.params.bb_period, devfactor=self.params.bb_dev)

    def next(self):
        # Collect signals
        score = 0
        
        # RSI < 40 (Bullish-ish/Oversold territory)
        if self.rsi[0] < 40: score += 1
        
        # MACD > Signal (Bullish momentum)
        if self.macd.macd[0] > self.macd.signal[0]: score += 1
        
        # EMA Short > EMA Long (Bullish trend)
        if self.ema_short[0] > self.ema_long[0]: score += 1
        
        # Price near lower band (Reversion potential)
        if self.datas[0].close[0] < self.boll.lines.bot[0] * 1.01: score += 1

        if not self.position:
            # Conservative Entry
            if score >= 3:
                self.log(f'BUY CREATE (Score: {score})')
                self.buy()
        else:
            # Exit signals
            exit_score = 0
            if self.rsi[0] > 70: exit_score += 1
            if self.macd.macd[0] < self.macd.signal[0]: exit_score += 1
            if self.ema_short[0] < self.ema_long[0]: exit_score += 1
            if self.datas[0].close[0] > self.boll.lines.top[0]: exit_score += 1
            
            if exit_score >= 2:
                self.log(f'SELL CREATE (Exit Score: {exit_score})')
                self.sell()
