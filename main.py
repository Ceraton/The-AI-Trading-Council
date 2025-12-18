import argparse
import asyncio
import os
import sys
import json
import signal
from datetime import datetime, timedelta
from dotenv import load_dotenv
from data.exchange_client import ExchangeClient
from strategy.sma_strategy import SMAStrategy
from strategy.rsi_strategy import RSIStrategy
from strategy.macd_strategy import MACDStrategy
from strategy.ema_strategy import EMAStrategy
from strategy.keltner_strategy import KeltnerStrategy
from strategy.combined_strategy import CombinedStrategy
from strategy.ml_strategy import MLStrategy 
from execution.order_executor import OrderExecutor
from execution.paper_wallet import PaperWallet
from risk.risk_manager import RiskManager
from utils.logger import setup_logger
from data.trade_recorder import TradeRecorder 
from data.data_storage import DataStorage
from utils.telegram_bot import TelegramBot


load_dotenv()





class TelegramStateProvider:
    def __init__(self, trading_pairs, paper_wallet, risk_manager, is_paper, logger):
        self.trading_pairs = trading_pairs
        self.paper_wallet = paper_wallet
        self.risk_manager = risk_manager
        self.is_paper = is_paper
        self.logger = logger

    def get_status_summary(self):
        summary = "📊 *Bot Status Report*\n"
        mode = "📝 PAPER" if self.is_paper else "💰 LIVE"
        summary += f"Mode: {mode}\n"
        
        for tp in self.trading_pairs:
            symbol = tp['symbol']
            regime = tp.get('regime', 'N/A')
            weights = tp.get('agent_weights', {})
            weight_str = ", ".join([f"{k[:3]}:{v:.1f}" for k,v in weights.items()])
            summary += f"\n*{symbol}*\nRegime: {regime}\nMerit: {weight_str}\n"
        
        if self.is_paper and self.paper_wallet:
            val = self.paper_wallet.get_total_value(1.0) # Dummy price for base
            summary += f"\n*Portfolio Value:* ${val:.2f}"
            
        return summary

    async def panic_sell_all(self):
        self.logger.warning("TELEGRAM: Initiating Global Panic Sell!")
        try:
            # We'll use the commands.json as the bridge
            from config import COMMANDS_FILE
            cmds = []
            for tp in self.trading_pairs:
                cmds.append({"action": "SELL", "symbol": tp['symbol']})
            
            # Read existing first to avoid overwrite race (basic)
            existing = []
            if os.path.exists(COMMANDS_FILE):
                try:
                    with open(COMMANDS_FILE, 'r') as f: existing = json.load(f)
                except: pass
            
            existing.extend(cmds)
            
            with open(COMMANDS_FILE, 'w') as f:
                json.dump(existing, f)
            return True
        except Exception as e:
            self.logger.error(f"Telegram Panic failed: {e}")
            return False

    def get_top10_prices(self):
        from config import TOP_10_CRYPTO
        summary = "🪙 *Market Snapshot (Top 10)*\n"
        summary += "Fetch live data via Dashboard."
        return summary
    
async def process_commands(cmd_file, clients, trading_pairs, risk_manager, paper_wallet, logger, is_paper, slippage, fee, create_strategy_fn):
    """
    Check for external commands (ADD_PAIR, REMOVE_PAIR) from dashboard/telegram.
    """
    if not os.path.exists(cmd_file):
        return

    try:
        with open(cmd_file, 'r') as f:
             commands = json.load(f)
        
        # Clear file immediately (consume commands)
        with open(cmd_file, 'w') as f:
             json.dump([], f)
             
        if not commands: return

        logger.info(f"📨 Processing {len(commands)} external commands...")

        for cmd in commands:
            action = cmd.get('action')
            symbol = cmd.get('symbol')

            if action == 'ADD_PAIR':
                # Check if already active
                if any(t['symbol'] == symbol for t in trading_pairs):
                    logger.info(f"Command ignored: {symbol} already active.")
                    continue
                
                logger.info(f"➕ Adding new pair: {symbol}")
                
                # Find suitable client (Kraken supports most, fallback to Coinbase)
                # For simplicity, try the first client or a specific valid one
                # Ideally we check fetch_ticker support
                target_client = None
                for c in clients:
                    try:
                        ticker = await c.fetch_ticker(symbol)
                        if ticker:
                            target_client = c
                            break
                    except: continue
                
                if target_client:
                    trading_pairs.append({
                        'client': target_client,
                        'symbol': symbol,
                        'executor': OrderExecutor(target_client, paper_wallet=paper_wallet if is_paper else None,
                                                  slippage_pct=slippage if is_paper else 0.0, 
                                                  fee_pct=fee if is_paper else 0.0),
                        'strategy': create_strategy_fn()
                    })
                    logger.info(f"✅ Successfully added {symbol} on {target_client.exchange_id}")
                else:
                    logger.warning(f"❌ Could not add {symbol}: No exchange client supports it or API error.")

            elif action == 'REMOVE_PAIR':
                # Remove from trading_pairs
                initial_len = len(trading_pairs)
                trading_pairs[:] = [t for t in trading_pairs if t['symbol'] != symbol]
                if len(trading_pairs) < initial_len:
                    logger.info(f"❌ Removed pair: {symbol}")
                else:
                    logger.info(f"Command ignored: {symbol} not found.")

    except Exception as e:
        logger.error(f"Command processing error: {e}")

async def main():
    from config import (
        STATUS_FILE_LIVE, STATUS_FILE_PAPER,
        TRADE_HISTORY_LIVE, TRADE_HISTORY_PAPER,
        PORTFOLIO_HISTORY_LIVE, PORTFOLIO_HISTORY_PAPER,
        DEFAULT_PAPER_CAPITAL, DEFAULT_WATCHLIST_PAPER,
        DEFAULT_SYMBOL, DEFAULT_TIMEFRAME,
        PAPER_TRADING_ENV_VAR,
        SETTINGS_FILE, MAIN_LOOP_DELAY, COMMANDS_FILE 
    )

    # Parse Args
    parser = argparse.ArgumentParser()
    parser.add_argument('--paper', action='store_true', help="Run in Paper Trading Mode")
    parser.add_argument('--capital', type=float, default=DEFAULT_PAPER_CAPITAL, help="Initial Capital for Paper Mode")
    parser.add_argument('--council', action='store_true', help="Enable Council of AIs (Multi-Agent Mode)")
    parser.add_argument('--watchlist', nargs='*', help="List of symbols to trade (e.g. BTC/USD ETH/USD)")
    parser.add_argument('--holdings', type=str, help="JSON string of initial holdings (e.g. '{\"BTC\": 1.0}')")
    parser.add_argument('--slippage', type=float, default=0.0, help="Simulated slippage (%%)")
    parser.add_argument('--fee', type=float, default=0.0, help="Simulated exchange fee (%%)")
    parser.add_argument('--model-name', type=str, default='ppo_model', help="Name of the PPO model to load (from models/)")
    args = parser.parse_args()
    print(f"DEBUG: Args: {args}")

    # Determine Mode
    IS_PAPER = args.paper or os.getenv(PAPER_TRADING_ENV_VAR, 'False').lower() in ('true', '1', 't')
    
    # Adjust Filenames for Paper Mode
    status_file = STATUS_FILE_PAPER if IS_PAPER else STATUS_FILE_LIVE
    trade_file = TRADE_HISTORY_PAPER if IS_PAPER else TRADE_HISTORY_LIVE
    port_file = PORTFOLIO_HISTORY_PAPER if IS_PAPER else PORTFOLIO_HISTORY_LIVE
    
    logger = setup_logger("Main")
    if IS_PAPER:
        logger.info(f"🚀 STARTING IN PAPER TRADING MODE (Capital: ${args.capital})")
    else:
        logger.info("🚀 STARTING IN LIVE TRADING MODE")

    start_time = datetime.now()

    # --- Signal Handling for Graceful Shutdown ---
    def handle_exit(signum, frame):
        raise KeyboardInterrupt("Received Signal to Terminate")
    
    signal.signal(signal.SIGTERM, handle_exit)
    signal.signal(signal.SIGINT, handle_exit)
    # ---------------------------------------------

    # Configuration
    exchanges_to_load = ['kraken', 'coinbase']  # Using only Kraken (supports LUNC/USD)
    STRATEGY_TYPE = os.getenv('STRATEGY_TYPE', 'SMA').upper()

    clients = []
    
    # Initialize Clients
    for ex_id in exchanges_to_load:
        try:
            client = ExchangeClient(ex_id)
            clients.append(client)
        except Exception as e:
            logger.error(f"Failed to initialize {ex_id}: {e}")

    risk_manager = RiskManager()
    
    # Paper Wallet Init
    paper_wallet = None
    initial_holdings = {}
    if args.holdings:
        try:
             initial_holdings = json.loads(args.holdings)
        except Exception as e:
             logger.error(f"Failed to parse holdings JSON: {e}")

    if IS_PAPER:
        paper_wallet = PaperWallet(initial_capital=args.capital, initial_holdings=initial_holdings)
    
    recorder = TradeRecorder(filename=trade_file, portfolio_filename=port_file) 
    data_storage = DataStorage()
    
    # Helper to instantiate strategy
    def create_strategy():
        if args.council:
            # Council of AIs Mode
            from strategy.analyst_agent import AnalystAgent
            from strategy.onchain_agent import OnChainAgent
            from strategy.meta_strategy import MetaStrategy
            
            logger.info("🏛️ Initializing Council of AIs...")
            
            agents = []
            
            # Agent 2: Analyst (Sentiment Analysis)
            analyst = AnalystAgent()
            agents.append(analyst)
            logger.info("  ✓ Analyst Agent initialized")
            
            # Agent 3: OnChain (Whale Watching)
            onchain = OnChainAgent(network='ethereum')
            agents.append(onchain)
            
            # --- ORACLE EXPANSION ---
            from strategy.chronos_agent import ChronosAgent
            from strategy.timegpt_agent import TimeGPTAgent
            
            # Chronos (Foundational Model)
            chronos = ChronosAgent(model_size='tiny') # Use tiny for speed/CPU compatibility
            agents.append(chronos)
            
            # TimeGPT (Nixtla Oracle)
            # Will automatically fallback to simulation if API key is missing
            timegpt = TimeGPTAgent() 
            agents.append(timegpt)
            
            # --- FRACTAL COUNCIL (Technical Sub-Agents) ---
            from strategy.technical_sub_agents import TrendAgent, OscillatorAgent, VolumeAgent
            from strategy.newton_agent import NewtonAgent
            agents.append(TrendAgent())
            agents.append(OscillatorAgent())
            agents.append(VolumeAgent())
            agents.append(NewtonAgent())
            
            # Agent 1: Chartist (Technical Analysis + Fusion)
            model_file = f"{args.model_name}.zip"
            if STRATEGY_TYPE == 'ML' and os.path.exists(os.path.join(os.getcwd(), 'models', model_file)):
                # Pass peer agents for fusion
                agents.append(MLStrategy(model_path=f"models/{args.model_name}", analyst_agent=analyst, onchain_agent=onchain))
                logger.info(f"  ✓ Chartist Agent (ML: {args.model_name}) initialized")
            else:
                agents.append(SMAStrategy(short_window=5, long_window=20))
                logger.info("  ✓ Chartist Agent (SMA) initialized")
            logger.info("  ✓ OnChain Agent initialized")
            
            # Meta-Strategy (Supreme Court)
            meta = MetaStrategy(agents, voting_method='weighted')
            logger.info("  ✓ Meta-Strategy initialized (weighted voting)")
            logger.info(f"  📊 Council has {len(agents)} agents")
            
            return meta
        else:
            # Single Agent Mode (original behavior)
            if STRATEGY_TYPE == 'ML':
                model_file = f"{args.model_name}.zip"
                if os.path.exists(os.path.join(os.getcwd(), 'models', model_file)):
                    return MLStrategy(model_path=f"models/{args.model_name}")
                else:
                    logger.warning(f"ML Model {args.model_name} not found. Falling back to SMAStrategy.")
                    return SMAStrategy(short_window=5, long_window=20)
            elif STRATEGY_TYPE == 'RSI':
                return RSIStrategy()
            elif STRATEGY_TYPE == 'MACD':
                return MACDStrategy()
            elif STRATEGY_TYPE == 'EMA':
                return EMAStrategy()
            elif STRATEGY_TYPE == 'KELTNER':
                return KeltnerStrategy()
            elif STRATEGY_TYPE == 'COMBINED':
                return CombinedStrategy()
            
            # Default
            return SMAStrategy(short_window=5, long_window=20)

    trading_pairs = []

    try:
        # 1. Check Balances & Discover Assets on ALL exchanges
        # In Paper Mode, we simulate discovery based on what's in the PaperWallet + Default Watchlist.
        # Since PaperWallet starts empty (except USD), we might not find 'active' coins.
        # So for Paper Mode, we should force add a watchlist OR assume empty start.
        # Let's add default BTC/USD and ETH/USD to watch if in Paper Mode.
        
        if IS_PAPER:
            # Paper Mode Discovery
            # 1. Add symbols with non-zero balance in wallet
            # 2. Add defaults
            # For each exchange, add these
            # For each exchange, add these if supported
            # Paper Mode Discovery
            # 1. Add symbols with non-zero balance in wallet
            # 2. Add defaults OR items from args
            
            # Determine target list
            target_list = args.watchlist if args.watchlist else DEFAULT_WATCHLIST_PAPER
            
            # For each exchange, add these
            for client in clients:
                  for sym in target_list:
                       try:
                           # Verify support
                           ticker = await client.fetch_ticker(sym)
                           if ticker:
                               trading_pairs.append({
                                   'client': client,
                                   'symbol': sym,
                                   'executor': OrderExecutor(client, paper_wallet=paper_wallet,
                                                             slippage_pct=args.slippage, fee_pct=args.fee)
                               })
                               logger.info(f"Accepted {sym} on {client.exchange_id}")
                           else:
                               logger.warning(f"Skipping {sym} on {client.exchange_id} (Not Supported)")
                       except Exception as e:
                           logger.warning(f"Error checking {sym} on {client.exchange_id}: {e}")
            
            logger.info(f"Paper Mode: Watchlist processing complete.")

        else:

            for client in clients:
                ex_name = client.exchange_id
                logger.info(f"--- Checking {ex_name} ---")
                
                try:
                    balance = await client.get_balance()
                    total_balance = balance.get('total', {})
                    logger.info(f"Balance: {total_balance}")

                    held_assets = {k: v for k, v in total_balance.items() if v > 0}
                    
                    for asset, amount in held_assets.items():
                        if asset in ['USD', 'EUR', 'USDT', 'USDC']: 
                            continue
                        
                        # Check price and validity
                        symbol = f"{asset}/USD" # Assumption
                        ticker = await client.fetch_ticker(symbol)
                        
                        if ticker:
                            price = ticker.get('last')
                            val = amount * price if price else 0
                            
                            if val < 10.0:
                                logger.info(f"Skipping {asset}: Value (${val:.2f}) < $10.00")
                                continue

                            logger.info(f"Accepted {asset}: {amount} (${val:.2f}). Adding {symbol} to watchlist.")
                            
                            trading_pairs.append({
                                'client': client,
                                'symbol': symbol,
                                'executor': OrderExecutor(client),
                                'strategy': create_strategy()
                            })
                        else:
                            logger.warning(f"Could not verify {symbol} on {ex_name}. Skipping auto-add.")
                except Exception as e:
                    logger.error(f"Error checking balance on {ex_name}: {e}")

        # Ensure we have at least one thing to trade (Default)
        if not trading_pairs and clients:
            logger.info(f"No active assets found. Defaulting to {DEFAULT_SYMBOL} on {clients[0].exchange_id}")
            trading_pairs.append({
                'client': clients[0],
                'symbol': DEFAULT_SYMBOL,
                'client': clients[0],
                'symbol': DEFAULT_SYMBOL,
                'executor': OrderExecutor(clients[0], paper_wallet=paper_wallet if IS_PAPER else None,
                                          slippage_pct=args.slippage if IS_PAPER else 0.0, 
                                          fee_pct=args.fee if IS_PAPER else 0.0),
                'strategy': create_strategy()
            })
        
        logger.info(f"Active Trading Pairs: {[(t['client'].exchange_id, t['symbol']) for t in trading_pairs]}")

        # --- UPDATE ANALYST AGENTS WITH WATCHLIST ---
        if args.council:
            from strategy.analyst_agent import AnalystAgent
            from strategy.meta_strategy import MetaStrategy
            
            # Collect all active symbols
            active_symbols = [t['symbol'] for t in trading_pairs]
            logger.info(f"Updating Analyst Agents with watchlist: {active_symbols}")
            
            for task in trading_pairs:
                strat = task.get('strategy')
                if strat and isinstance(strat, MetaStrategy):
                    for agent in strat.agents:
                        if isinstance(agent, AnalystAgent):
                            agent.update_watchlist(active_symbols)
                        elif isinstance(agent, OnChainAgent):
                             agent.update_watchlist(active_symbols)

        # Initialize Recorder & Storage
        recorder = TradeRecorder()
        data_storage = DataStorage()
        
        # Timers
        last_portfolio_log = datetime.now() - timedelta(days=1) # Force immediate log
        last_yearly_fetch = datetime.min
        latest_portfolio_value = args.capital if IS_PAPER else 0.0
        
        # Reset Status File immediately to clear old uptime
        initial_status = {
            'last_update': datetime.now().isoformat(),
            'active_pairs': [],
            'strategies': [],
            'uptime_seconds': 0,
            'paper_trading': IS_PAPER
        }
        with open(status_file, 'w') as f:
            json.dump(initial_status, f)
            logger.info(f"Reset {status_file} for new session.")
            
        # Log mode
        mode_str = "PAPER TRADING" if IS_PAPER else "LIVE TRADING"
        logger.info(f"--- Mode: {mode_str} ---")

        # --- Initialize Telegram Bot (Expansion 5) ---
        state_provider = TelegramStateProvider(trading_pairs, paper_wallet, risk_manager, IS_PAPER, logger)
        tg_bot = TelegramBot(state_provider=state_provider)
        await tg_bot.start()

        # Main Loop
        while True:
            logger.info(f"❤️ Heartbeat: Scanning {len(trading_pairs)} active pairs...")
            
            for task in trading_pairs:
                client = task['client']
                symbol = task['symbol']
                executor = task['executor']
                
                # 1. Fetch Data
                ohlcv = await client.fetch_ohlcv(symbol, timeframe=DEFAULT_TIMEFRAME)
                if not ohlcv:
                    continue

                # Parse
                last_candle_data = ohlcv[-1]
                candle = {
                    'timestamp': last_candle_data[0],
                    'open': last_candle_data[1],
                    'high': last_candle_data[2],
                    'low': last_candle_data[3],
                    'close': last_candle_data[4],
                    'volume': last_candle_data[5]
                }

                # 2. Strategy
                if 'strategy' not in task:
                    task['strategy'] = create_strategy() # Use factory
                
                local_strategy = task['strategy']
                trade_signal = await local_strategy.on_candle(candle)

                # Capture Council Meta-Data for Dashboard (Post-Intelligence Upgrade)
                if hasattr(local_strategy, 'current_regime'):
                    curr_regime = local_strategy.current_regime
                    last_regime = task.get('last_regime', 'PEACE')
                    if curr_regime != last_regime:
                        asyncio.create_task(tg_bot.send_message(f"⚖️ *MARKET REGIME CHANGE* ⚖️\n{symbol}: {last_regime} ➡️ *{curr_regime}*"))
                    task['current_regime'] = curr_regime
                    task['last_regime'] = curr_regime
                
                if hasattr(local_strategy, 'agent_weights'):
                    task['agent_weights'] = local_strategy.agent_weights

                if trade_signal:
                    logger.info(f"Signal for {symbol}: {trade_signal}")
                    
                    # Capture reasoning for Dashboard
                    if 'reasoning' in trade_signal:
                        task['latest_reasoning'] = trade_signal['reasoning']
                        task['latest_signal_time'] = datetime.now().isoformat()
                        task['latest_signal_side'] = trade_signal['side']
                    
                    # Capture council votes if in multi-agent mode
                    if 'agent_votes' in trade_signal:
                        task['council_votes'] = trade_signal['agent_votes']
                        task['vote_breakdown'] = trade_signal.get('vote_breakdown', {})
                        task['voting_method'] = trade_signal.get('voting_method', 'unknown')
                    
                    # Identify Currencies
                    base_currency = symbol.split('/')[0]
                    quote_currency = symbol.split('/')[1]
                    
                    action_balance = 0.0
                    
                    if IS_PAPER:
                        if trade_signal['side'] == 'buy':
                            action_balance = paper_wallet.get_balance(quote_currency)
                        elif trade_signal['side'] == 'sell':
                            action_balance = paper_wallet.get_balance(base_currency)
                    else:
                        balance = await client.get_balance()
                        if trade_signal['side'] == 'buy':
                            action_balance = balance.get(quote_currency, {}).get('free', 0.0)
                        elif trade_signal['side'] == 'sell':
                            action_balance = balance.get(base_currency, {}).get('free', 0.0)
                        
                    ticker = await client.fetch_ticker(symbol)
                    current_price = ticker.get('last')

                    # Validate with CORRECT balance
                    if risk_manager.validate_trade(trade_signal, action_balance, current_price):
                        
                        # --- Expansion 6: Liquidity Awareness ---
                        order_book = await client.fetch_order_book(symbol)
                        impact = await client.get_price_impact(symbol, 1.0, trade_signal['side']) # Probe with small size
                        
                        # Calculate Amount with order book adjustment
                        amount = risk_manager.calculate_position_size(
                            action_balance, 
                            current_price, 
                            order_book=order_book, 
                            side=trade_signal['side']
                        )
                        
                        # Log liquidity findings
                        if order_book:
                            est_impact = await client.get_price_impact(symbol, amount, trade_signal['side'])
                            logger.info(f"🌊 DEEP WATER: Symbol: {symbol} | Amount: {amount:.4f} | Est Impact: {est_impact:.2%}")
                        # ---------------------------------------

                        # 4. Check Amount
                        if amount <= 0:
                            logger.info(f"Skipping trade for {symbol}: Calculated Amount is {amount}")
                            continue

                        # 5. Check Value
                        trade_value = amount * current_price
                        if trade_value < 1.0:
                             logger.info(f"Skipping trade for {symbol}: Value (${trade_value:.2f}) < $1.00")
                             continue
                        
                        # 6. Execute
                        if trade_signal.get('strategy') == 'Knife Catch':
                             logger.info(f"⚡ NEWTON PROTOCOL: Executing Limit Ladder for {symbol}")
                             order_result = await executor.execute_ladder_order(trade_signal, symbol, amount)
                             # ladder returns a list, execute_order returns a dict. 
                             # For logging purposes, we'll use the first rung or a synthetic aggregate.
                             if order_result: order_result = order_result[0] 
                        else:
                             order_result = await executor.execute_order(trade_signal, symbol, amount)
                        
                        if order_result:
                            # Expansion 5: Live Signal Alert
                            reason = trade_signal.get('reasoning', {}).get('action', 'Strategy Signal')
                            asyncio.create_task(tg_bot.send_message(
                                f"🚨 *TRADE EXECUTED* 🚨\n"
                                f"Symbol: *{symbol}*\n"
                                f"Side: *{trade_signal['side'].upper()}*\n"
                                f"Price: ${current_price:.2f}\n"
                                f"Amount: {amount:.4f}\n"
                                f"Reason: {reason}"
                            ))
                        
                        # mock result for now if executor doesn't return dict
                        if not order_result:
                            # If Paper Mode, execute_order returns dict if successful. 
                            # If Live Mode, it returns dict wrapper.
                            # If None, it failed.
                            logger.warning(f"Order failed for {symbol}")
                            continue

                        # 7. Log Trade
                        strategy_name = task['strategy'].name if hasattr(task['strategy'], 'name') else STRATEGY_TYPE
                        
                        recorder.log_trade(
                            symbol=symbol,
                            side=trade_signal['side'],
                            price=current_price,
                            amount=amount,
                            strategy_name=strategy_name,
                            exchange=client.exchange_id
                        )
            
            # --- Status Update for Dashboard ---
            try:
                # Aggregate Vitals
                vitals = {}
                for c in clients:
                    vitals[c.exchange_id] = {
                        'requests': c.metrics['requests'],
                        'errors': c.metrics['errors'],
                        'avg_latency': sum(c.metrics['latency_history']) / len(c.metrics['latency_history']) if c.metrics['latency_history'] else 0
                    }
                
                # Aggregate AI Insights
                ai_insights = {}
                council_data = {}
                
                for t in trading_pairs:
                    symbol = t['symbol']
                    
                    if 'latest_reasoning' in t:
                        ai_insights[symbol] = {
                            'reasoning': t['latest_reasoning'],
                            'time': t.get('latest_signal_time'),
                            'side': t.get('latest_signal_side')
                        }
                    
                    # Council voting data
                    if 'council_votes' in t:
                        council_data[symbol] = {
                            'votes': t['council_votes'],
                            'breakdown': t.get('vote_breakdown', {}),
                            'method': t.get('voting_method', 'unknown'),
                            'regime': t.get('current_regime', 'PEACE'),
                            'agent_weights': t.get('agent_weights', {})
                        }

                status_data = {
                    'last_update': datetime.now().isoformat(),
                    'active_pairs': [(t['client'].exchange_id, t['symbol']) for t in trading_pairs],
                    'strategies': [t.get('strategy').name if t.get('strategy') and hasattr(t.get('strategy'), 'name') else 'Unknown' for t in trading_pairs],
                    'uptime_seconds': int((datetime.now() - start_time).total_seconds()),
                    'paper_trading': IS_PAPER,
                    'vitals': vitals,
                    'ai_insights': ai_insights,
                    'council_mode': args.council,
                    'council_data': council_data,
                    'portfolio_value': latest_portfolio_value,
                    'initial_capital': args.capital
                }
                # Atomic Write
                temp_file = status_file + '.tmp'
                with open(temp_file, 'w') as f:
                    json.dump(status_data, f)
                
                os.replace(temp_file, status_file)
            except Exception as e:
                import traceback
                logger.error(f"Failed to write status file: {e}")
                logger.error(f"Traceback: {traceback.format_exc()}")
            # -----------------------------------

            # --- Process External Commands (Dynamic Pairs) ---
            await process_commands(COMMANDS_FILE, clients, trading_pairs, risk_manager, 
                                   paper_wallet, logger, IS_PAPER, args.slippage, args.fee, create_strategy)
            
            # --- Interval Updates (Graphs) ---
            now = datetime.now()
            
            # 1. Portfolio Snapshot (Every 5 mins)
            if (now - last_portfolio_log).total_seconds() >= 300:
                total_val = 0.0
                asset_details = {}
                
                if IS_PAPER:
                    # PAPER: Calculate from Wallet + Ticker
                    balances = paper_wallet.get_all_balances()
                    for asset, amount in balances.items():
                        if amount <= 0: continue
                        
                        if asset == 'USD':
                             total_val += amount
                             asset_details['USD'] = amount
                        else:
                             # Get Price
                             sym = f"{asset}/USD"
                             price = 0.0
                             # Try active pairs first
                             for t in trading_pairs:
                                 if t['symbol'] == sym:
                                     try:
                                         ticker = await t['client'].fetch_ticker(sym)
                                         price = ticker.get('last', 0)
                                         break
                                     except: pass
                             
                             if price == 0 and clients:
                                  try:
                                      ticker = await clients[0].fetch_ticker(sym)
                                      price = ticker.get('last', 0)
                                  except: pass
                             
                             val = amount * price
                             total_val += val
                             asset_details[sym] = val
                else:
                    # LIVE: Sum from Exchanges
                    usd_balance = 0.0
                    for client in clients:
                         try:
                             bal = await client.get_balance()
                             usd_balance += bal.get('USD', {}).get('free', 0)
                         except: pass
                    
                    total_val += usd_balance
                    asset_details['USD'] = usd_balance
                    
                    for t in trading_pairs:
                        client = t['client']
                        sym = t['symbol']
                        base = sym.split('/')[0]
                        try:
                            bal = await client.get_balance()
                            amt = bal.get(base, {}).get('free', 0)
                            ticker = await client.fetch_ticker(sym)
                            price = ticker.get('last', 0)
                            val = amt * price
                            total_val += val
                            asset_details[sym] = val
                        except: pass
                
                recorder.log_portfolio_snapshot(total_val, asset_details)
                last_portfolio_log = now
                latest_portfolio_value = total_val
                logger.info("Logged Portfolio Snapshot.")

            # 2. Yearly Data Fetch (Every 30 mins)
            if (now - last_yearly_fetch).total_seconds() >= 1800:
                 logger.info("Updating Yearly Data for graphs...")
                 try:
                     for t in trading_pairs:
                         await data_storage.update_yearly_data(t['client'], t['symbol'])
                         # Also update intraday for forensics (every 30 mins is fine)
                         await data_storage.update_intraday_data(t['client'], t['symbol'])
                     last_yearly_fetch = now
                     logger.info("Yearly & Intraday Data Update Complete.")
                 except Exception as e:
                    logger.error(f"Error in data update: {e}")
                
                
                 # --- MANUAL COMMAND PROCESSING ---
            try:
                if os.path.exists(COMMANDS_FILE):
                    with open(COMMANDS_FILE, 'r') as f:
                        commands = json.load(f)
                    
                    if commands:
                        logger.info(f"⚡ Processing {len(commands)} manual commands...")
                        
                        for cmd in commands:
                            action = cmd.get('action')
                            target_symbol = cmd.get('symbol')
                            
                            if action == 'PANIC_SELL_ALL':
                                logger.warning("🚨 PANIC MODE ACTIVATED: SELLING ALL ASSETS")
                                for t in trading_pairs:
                                    # Create artificial SELL signal
                                    executor = t['executor']
                                    sym = t['symbol']
                                    
                                    # Force Sell logic
                                    # We need current price
                                    current_price = 0
                                    try:
                                        ticker = await t['client'].fetch_ticker(sym)
                                        current_price = ticker.get('last')
                                    except: pass
                                    
                                    # Get balance to sell all
                                    # In a real panic, we just dump. Executor needs a valid amount though.
                                    # For Simplicity, we assume Executor handles "sell all" if we don't specify amount?
                                    # Or we calculate it here.
                                    base = sym.split('/')[0]
                                    amt_to_sell = 0
                                    if IS_PAPER:
                                        amt_to_sell = paper_wallet.get_balance(base)
                                    else:
                                        bal = await t['client'].get_balance()
                                        amt_to_sell = bal.get(base, {}).get('free', 0)
                                    
                                    if amt_to_sell > 0:
                                        panic_signal = {
                                            'side': 'sell',
                                            'price': current_price,
                                            'reasoning': {'action': 'PANIC_SELL_ALL'}
                                        }
                                        await executor.execute_order(panic_signal, sym, amt_to_sell)
                                        recorder.log_trade(sym, 'sell', current_price, amt_to_sell, 'PANIC', t['client'].exchange_id)
                                        
                            elif action in ['FORCE_BUY', 'FORCE_SELL']:
                                side = 'buy' if action == 'FORCE_BUY' else 'sell'
                                
                                # Find target task
                                target_task = None
                                for t in trading_pairs:
                                    if t['symbol'] == target_symbol:
                                        target_task = t
                                        break
                                
                                if target_task:
                                    executor = target_task['executor']
                                    client = target_task['client']
                                    
                                    # Fetch Price
                                    ticker = await client.fetch_ticker(target_symbol)
                                    current_price = ticker.get('last')
                                    
                                    # Calculate Amount (Default to Risk Manager defaults or max)
                                    # Since this is "Force", we should probably use the standard sizing logic 
                                    # but bypass the strategy signal check.
                                    
                                    # We need 'action_balance' logic again... 
                                    # Refactoring needed? For now, duplicate logic for safety isolation.
                                    
                                    quote = target_symbol.split('/')[1]
                                    base = target_symbol.split('/')[0]
                                    
                                    action_balance = 0.0
                                    if IS_PAPER:
                                        if side == 'buy': action_balance = paper_wallet.get_balance(quote)
                                        else: action_balance = paper_wallet.get_balance(base)
                                    else:
                                        bal = await client.get_balance()
                                        if side == 'buy': action_balance = bal.get(quote, {}).get('free', 0)
                                        else: action_balance = bal.get(base, {}).get('free', 0)
                                    
                                    amount = 0.0
                                    if side == 'buy':
                                        amount = risk_manager.calculate_position_size(action_balance, current_price)
                                    else:
                                        amount = action_balance # Sell all
                                        
                                    if amount > 0:
                                        manual_signal = {
                                            'side': action.lower(),
                                            'price': current_price,
                                            'reasoning': {'action': f'MANUAL_{action}'}
                                        }
                                        await executor.execute_order(manual_signal, target_symbol, amount)
                                        recorder.log_trade(target_symbol, side, current_price, amount, 'MANUAL', client.exchange_id)
                                        logger.info(f"Executed MANUAL {side} for {target_symbol}")
                                    else:
                                        logger.warning(f"Manual {side} failed: Insufficient balance ({action_balance})")
                                else:
                                    logger.warning(f"Target symbol {target_symbol} not found in active pairs.")
                                    
                        # Clear file
                        with open(COMMANDS_FILE, 'w') as f:
                            json.dump([], f)
                            
            except Exception as e:
                logger.error(f"Error processing manual commands: {e}")

            # Loop delay
            try:
                if os.path.exists(SETTINGS_FILE):
                    with open(SETTINGS_FILE, 'r') as f:
                        new_settings = json.load(f)
                    risk_manager.update_settings(new_settings)
            except Exception as e:
                logger.error(f"Failed to load runtime settings: {e}")

            await asyncio.sleep(MAIN_LOOP_DELAY)

    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
    except Exception as e:
        logger.critical(f"Critical error in main loop: {e}")
    finally:
        logger.info("Shutting down... Closing exchange connections.")
        for task in trading_pairs:
            try:
                await task['client'].close()
                logger.info(f"Closed connection to {task['client'].exchange_id}")
            except Exception as e:
                logger.error(f"Error closing {task['client'].exchange_id}: {e}")
        logger.info("Shutdown complete.")

if __name__ == "__main__":
    try:
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(main())
    except Exception as e:
        import traceback
        error_msg = f"CRITICAL FAILURE: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        with open("logs/startup_error.log", "w") as f:
            f.write(error_msg)
        sys.exit(1)
