import os

# Trading Modes
PAPER_TRADING_ENV_VAR = 'PAPER_TRADING'

# File Paths (Versioned to avoid conflicts with zombie processes)
DATA_DIR = 'data_storage'
STATUS_FILE_LIVE = 'data/live_status_v2.json'
STATUS_FILE_PAPER = 'data/paper_status_v2.json'
SETTINGS_FILE = 'data/runtime_settings.json'
COMMANDS_FILE = 'data/commands.json'
WHALE_ALERTS_FILE = 'data/whale_alerts.csv'

TRADE_HISTORY_LIVE = 'data/trade_history.csv'
TRADE_HISTORY_PAPER = 'data/paper_trade_history.csv'

PORTFOLIO_HISTORY_LIVE = 'data/portfolio_history.csv'
PORTFOLIO_HISTORY_PAPER = 'data/paper_portfolio_history.csv'

# Settings
DEFAULT_PAPER_CAPITAL = 10000.0
DEFAULT_WATCHLIST_PAPER = ['BTC/USD', 'ETH/USD', 'SOL/USD', 'LUNC/USD']
TOP_10_CRYPTO = ["BTC/USD", "ETH/USD", "SOL/USD", "BNB/USD", "XRP/USD", "ADA/USD", "AVAX/USD", "DOGE/USD", "DOT/USD", "LINK/USD"]
DEFAULT_SYMBOL = 'BTC/USD'
DEFAULT_TIMEFRAME = '1m'

# Intervals
MAIN_LOOP_DELAY = 60
PORTFOLIO_LOG_INTERVAL = 1800  # 30 minutes
YEARLY_DATA_INTERVAL = 1800   # 30 minutes
HEARTBEAT_TIMEOUT = 120       # 2 minutes (Dashboard)

# Execution
MIN_TRADE_INTERVAL = 1.0      # Seconds between trades per pair

# Risk Management
MAX_DRAWDOWN_PCT = 0.10
MAX_POSITION_SIZE_PCT = 0.05
MAX_SLIPPAGE_PCT = 0.02
STOP_LOSS_PCT = 0.05
TAKE_PROFIT_PCT = 0.10
