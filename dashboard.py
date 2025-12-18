import streamlit as st
import pandas as pd
import json
import numpy as np
import os
import time
from datetime import timedelta, datetime
import plotly.express as px
from streamlit_lightweight_charts import renderLightweightCharts
from st_aggrid import AgGrid, GridOptionsBuilder
import plotly.graph_objects as go
import sys
import traceback
import asyncio
import psutil
import hashlib
import extra_streamlit_components as stx

from dotenv import load_dotenv
load_dotenv()
import subprocess
import signal
import uuid
from backtesting.backtest_engine import BacktestEngine, CouncilStrategy
from strategy.meta_strategy import MetaStrategy
from strategy.technical_sub_agents import TrendAgent, OscillatorAgent, VolumeAgent
from strategy.analyst_agent import AnalystAgent
from strategy.onchain_agent import OnChainAgent
from strategy.chronos_agent import ChronosAgent
from strategy.timegpt_agent import TimeGPTAgent

# GLOBAL ERROR HANDLER
try:
    st.set_page_config(
        page_title="AI Crypto Bot - Cockpit",
        page_icon="🤖",
        layout="wide",
        initial_sidebar_state="expanded",
        menu_items={
            'Get Help': 'https://github.com/yourrepo/issues',
            'Report a bug': "https://github.com/yourrepo/issues",
            'About': "AI Crypto Trading Bot v2.0 (Cockpit Edition)"
        }
    )

    # --- COOKIE MANAGER ---
    cookie_manager = stx.CookieManager()

    # --- SECURITY: AUTHENTICATION LAYER ---
    def check_password():
        """Returns True if the user had the correct password."""
        
        # 0. Check if password is required
        env_password = os.getenv("DASHBOARD_PASSWORD")
        if not env_password:
            # No password configured -> Auto-Connect
            st.session_state["password_correct"] = True
            return True

        # 1. Check for persistent cookie first (Synchronous read via st.context)
        expected_token = hashlib.sha256(env_password.encode()).hexdigest()
        
        if "auth_token" in st.context.cookies:
            if st.context.cookies["auth_token"] == expected_token:
                st.session_state["password_correct"] = True
                return True

        def password_entered():
            """Checks whether a password entered by the user is correct."""
            entered_pw = st.session_state.get("password")
            if entered_pw == env_password:
                st.session_state["password_correct"] = True
                
                # If "Remember Me" is checked, set the persistent cookie
                if st.session_state.get("remember_me"):
                    cookie_manager.set("auth_token", expected_token, key="set_cookie_auth")
                
                if "password" in st.session_state:
                    del st.session_state["password"]  # don't store password
                # Log security event
                with open("logs/security.log", "a") as f:
                    f.write(f"[{datetime.now().isoformat()}] SUCCESS: User logged in\n")
            else:
                st.session_state["password_correct"] = False
                if "password" in st.session_state:
                    del st.session_state["password"]
                with open("logs/security.log", "a") as f:
                    f.write(f"[{datetime.now().isoformat()}] FAILED: Incorrect password attempt\n")

        if "password_correct" not in st.session_state:
            # First run, show input for password.
            st.title("🔐 Secure Access Required")
            st.text_input(
                "Password", type="password", on_change=password_entered, key="password"
            )
            st.checkbox("Remember this connection (30 days)", key="remember_me", value=True)
            return False
        elif not st.session_state["password_correct"]:
            # Password not correct, show input + error.
            st.title("🔐 Secure Access Required")
            st.text_input(
                "Password", type="password", on_change=password_entered, key="password"
            )
            st.checkbox("Remember this connection (30 days)", key="remember_me", value=True)
            st.error("😕 Password incorrect")
            return False
        else:
            # Password correct.
            return True

    if not check_password():
        st.stop()  # Do not continue if not authenticated

    # --- CSS OVERRIDES (COCKPIT STYLE) ---
    # --- GLOBAL STATE INIT ---
    if 'view_mode_state' not in st.session_state: st.session_state['view_mode_state'] = "Live"
    view_mode = st.session_state['view_mode_state']

    # --- THEME INJECTION (SAFETY THEMES) ---
    # Live = Red/Black (Matrix), Paper = Blue/Cyan (Blueprint), Shadow = Purple
    theme_color = "#ff4b4b" if view_mode == "Live" else "#00d4ff" if view_mode == "Paper" else "#9052ff"
    
    st.markdown(f"""
    <style>
        /* Compact Top Bar Metrics */
        div[data-testid="metric-container"] {{
            background-color: #1E1E1E;
            border: 1px solid {theme_color}; /* Theme Color Border */
            padding: 10px;
            border-radius: 5px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        }}
        label[data-testid="stMetricLabel"] {{ font-size: 0.8rem; color: #888; }}
        div[data-testid="stMetricValue"] {{ font-size: 1.2rem; color: #eee; }}
        div[data-testid="stMetricDelta"] {{ font-size: 0.8rem; }}
        /* Reduce whitespace */
        .block-container {{ padding-top: 2rem; padding-bottom: 2rem; }}
        
        /* HEADER BADGE */
        .mode-badge {{
            padding: 5px 10px;
            border-radius: 4px;
            background-color: {theme_color};
            color: black;
            font-weight: bold;
            text-transform: uppercase;
            font-size: 0.8em;
            display: inline-block;
            margin-bottom: 10px;
        }}
    </style>
    """, unsafe_allow_html=True)

    # --- AUTO-REFRESH LOGIC MOVED TO BOTTOM ---


    # Import logger utils
    from utils.log_rotator import rotate_logs
    from utils.logger import setup_logger

    # Setup Dashboard Logger (Appends to bot.log so actions show in "Live Logs")
    # Setup Dashboard Logger
    dash_logger = setup_logger("Dashboard")
    
    # --- HELPER FUNCTIONS ---
    def is_bot_running():
        """Checks if the bot process is actually running."""
        PID_FILE = "bot_pid.txt"
        if os.path.exists(PID_FILE):
            try:
                with open(PID_FILE, 'r') as f: content = f.read().strip()
                if not content: return None
                pid = int(content)
                if psutil.pid_exists(pid):
                    try:
                        p = psutil.Process(pid)
                        if 'python' in p.name().lower(): return pid
                    except (psutil.NoSuchProcess, psutil.AccessDenied): pass
                try: os.remove(PID_FILE)
                except: pass
                return None
            except: return None
        return None

    def get_bot_mode(pid):
        """Returns 'Paper' or 'Live' based on process arguments."""
        try:
            p = psutil.Process(pid)
            if '--paper' in p.cmdline(): return "Paper"
            return "Live"
        except: return "Unknown"

    def safe_read_json(filepath, retries=3, default=None):
        """Atomic-like read with retries to handle race conditions."""
        if default is None: default = {}
        if not os.path.exists(filepath): return default
        
        for i in range(retries):
            try:
                with open(filepath, 'r') as f:
                    content = f.read().strip()
                    if not content: return default
                    return json.loads(content)
            except (json.JSONDecodeError, IOError):
                time.sleep(0.05)
                continue
            except Exception:
                return default
        return default

    def generate_council_insight(votes, regime):
        """Synthesizes agent votes into a human-readable summary (Mock LLM Reasoning)."""
        if not votes: return "The Council is currently in recess. No active deliberation."
        
        buys = [v['agent'] for v in votes if v.get('vote') == 'buy']
        sells = [v['agent'] for v in votes if v.get('vote') == 'sell']
        
        insight = f"**{regime}TIME CONSTITUTION ENFORCED.** " if regime == "WAR" else ""
        
        if len(buys) > 0 and len(sells) == 0:
            insight += f"The Council reached a high-conviction **BUY** verdict led by {', '.join(buys)}."
        elif len(sells) > 0 and len(buys) == 0:
            insight += f"The Council reached a high-conviction **SELL** verdict led by {', '.join(sells)}."
        elif len(buys) > 0 and len(sells) > 0:
            insight += f"The Council is **DIVIDED**. {', '.join(buys)} advocate for a BUY, while {', '.join(sells)} signal a SELL. Caution is advised."
        else:
            insight += "The Council maintains a **WAIT AND WATCH** stance. Consensus points to a lack of clear market direction."
            
        return insight

    # --- TENSORBOARD HELPERS ---
    def get_tensorboard_process():
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = proc.info.get('cmdline')
                if cmdline and 'tensorboard' in ' '.join(cmdline).lower():
                    return proc
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return None

    def start_tensorboard():
        logdir = os.path.join(os.getcwd(), "logs", "tensorboard")
        if not os.path.exists(logdir):
            os.makedirs(logdir)
        # Use python -m tensorboard.main to ensure cross-platform compatibility
        subprocess.Popen([sys.executable, "-m", "tensorboard.main", "--logdir", logdir, "--port", "6006"], 
                         creationflags=subprocess.CREATE_NEW_CONSOLE)
    
    # --- LOAD CONFIG & DATA (GLOBAL) ---
    from config import (
        STATUS_FILE_LIVE, STATUS_FILE_PAPER,
        TRADE_HISTORY_LIVE, TRADE_HISTORY_PAPER,
        PORTFOLIO_HISTORY_LIVE, PORTFOLIO_HISTORY_PAPER,
        HEARTBEAT_TIMEOUT, DATA_DIR, 
        SETTINGS_FILE, TOP_10_CRYPTO, COMMANDS_FILE,
        MAX_DRAWDOWN_PCT, MAX_POSITION_SIZE_PCT, MAX_SLIPPAGE_PCT, STOP_LOSS_PCT, TAKE_PROFIT_PCT
    )
    


    # --- CONFIG & DATA ---
    
    STATUS_FILE = None
    TRADE_FILE = None
    PORTFOLIO_FILE = None

    if view_mode == "Paper":
        STATUS_FILE = STATUS_FILE_PAPER
        TRADE_FILE = TRADE_HISTORY_PAPER
        PORTFOLIO_FILE = PORTFOLIO_HISTORY_PAPER
    elif view_mode == "Live":
        STATUS_FILE = STATUS_FILE_LIVE
        TRADE_FILE = TRADE_HISTORY_LIVE
        PORTFOLIO_FILE = PORTFOLIO_HISTORY_LIVE
    else:
        STATUS_FILE = STATUS_FILE_PAPER 
        TRADE_FILE = TRADE_HISTORY_PAPER
        PORTFOLIO_FILE = PORTFOLIO_HISTORY_PAPER

    status_data = {}
    if STATUS_FILE:
        status_data = safe_read_json(STATUS_FILE)

    # Process ID check for cleanup
    PID_FILE = "bot_pid.txt"
    current_pid = is_bot_running()

    # --- MODE MISMATCH WARNING ---
    if current_pid:
        running_mode = get_bot_mode(current_pid)
        if view_mode != "Shadow (Comparison)":
            if running_mode == "Paper" and view_mode == "Live":
                st.warning("⚠️ **Mode Mismatch**: You are viewing **Live** data, but the bot is running in **Paper** mode. Switch View Mode to 'Paper' to see active status.", icon="⚠️")
            elif running_mode == "Live" and view_mode == "Paper":
                 st.warning("⚠️ **Mode Mismatch**: You are viewing **Paper** data, but the bot is running in **Live** mode. Switch View Mode to 'Live' to see active status.", icon="⚠️")


    # --- GHOST DATA CLEANUP ---
    if not current_pid:
        try:
            clean_status = {
                'last_update': datetime.now().isoformat(),
                'active_pairs': [], 'strategies': [], 'uptime_seconds': 0,
                'portfolio_value': 10000.0, 'initial_capital': 10000, 'paper_trading': True
            }
            if STATUS_FILE_PAPER:
                with open(STATUS_FILE_PAPER, 'w') as f: json.dump(clean_status, f)
            if STATUS_FILE_LIVE:
                with open(STATUS_FILE_LIVE, 'w') as f: json.dump(clean_status, f)
            status_data = clean_status
        except: pass

    st.title("🤖 AI Crypto Trading Bot Dashboard")

    st.sidebar.title("🧭 Navigation")
    
    # Define Navigation Options
    NAV_DASHBOARD = "Dashboard"
    NAV_GRAPHS = "Graphs"
    NAV_LOGS = "Live Logs"
    NAV_AI_LAB = "🧠 AI Research Lab"
    NAV_BACKTEST = "🧪 Digital Twin (Lab)"
    NAV_OPTIONS = "Options"
    
    nav = st.sidebar.radio("Go to", [NAV_DASHBOARD, NAV_GRAPHS, NAV_LOGS, NAV_AI_LAB, NAV_BACKTEST, NAV_OPTIONS])
    
    if st.sidebar.button("🔓 Logout"):
        st.session_state["password_correct"] = False
        # Clear persistent cookie
        cookie_manager.delete("auth_token")
        
        with open("logs/security.log", "a") as f:
            f.write(f"[{datetime.now().isoformat()}] SUCCESS: User logged out\n")
        st.rerun()

    st.sidebar.divider()
    
    # Global Controls
    # Load active pairs for dropdown
    active_pairs_list = ["ALL"]
    
    # --- LOAD WATCHLIST (FOR DROPDOWN) ---
    USER_WATCHLIST_FILE = "user_watchlist.json"
    user_watchlist = []
    if os.path.exists(USER_WATCHLIST_FILE):
        try:
            with open(USER_WATCHLIST_FILE, 'r') as f: user_watchlist = json.load(f)
        except: pass
        
    # 1. Add Top 10 by default
    active_pairs_list += TOP_10_CRYPTO
    
    # 2. Add Watchlist pairs
    for p in user_watchlist:
        if p not in active_pairs_list:
            active_pairs_list.append(p)
    
    # 3. Add any additional active pairs from status_data
    if 'active_pairs' in status_data:
        for p in status_data['active_pairs']:
            pair_name = p[1]
            if pair_name not in active_pairs_list:
                active_pairs_list.append(pair_name)
        
    selected_pair = st.sidebar.selectbox("Selected Pair", active_pairs_list, index=0)

    # --- WATCHLIST MANAGER UI (MOVED) ---
    with st.sidebar.expander("📋 Watchlist Manager", expanded=False):
        # Input
        new_pair = st.text_input("Add Pair (e.g. DOT/USD)", placeholder="SYM/USD")
        
        if st.button("➕ Add Pair"): 
            if new_pair and '/' in new_pair:
                 sym = new_pair.upper().strip()
                 if sym not in user_watchlist:
                     user_watchlist.append(sym)
                     # Save
                     with open(USER_WATCHLIST_FILE, 'w') as f: json.dump(user_watchlist, f)
                     
                     # Send Command
                     cmd = {"action": "ADD_PAIR", "symbol": sym}
                     try:
                         # Atomic read-update-write
                         existing_cmds = []
                         if os.path.exists(COMMANDS_FILE):
                             try:
                                 with open(COMMANDS_FILE, 'r') as f: existing_cmds = json.load(f)
                             except: pass
                         existing_cmds.append(cmd)
                         with open(COMMANDS_FILE, 'w') as f: json.dump(existing_cmds, f)
                         st.success(f"Sent ADD {sym}")
                         time.sleep(1) # feedback
                         st.rerun()
                     except Exception as e:
                         st.error(f"Cmd Failed: {e}")
                 else:
                     st.warning("Already in watchlist")
            else:
                 st.error("Invalid format")

        st.caption("Current Watchlist:")
        to_remove = []
        for w_sym in user_watchlist:
            c1, c2 = st.columns([3, 1])
            c1.write(f"🔹 {w_sym}")
            if c2.button("🗑️", key=f"rm_{w_sym}"):
                to_remove.append(w_sym)
                
        if to_remove:
            for rm_sym in to_remove:
                 if rm_sym in user_watchlist:
                     user_watchlist.remove(rm_sym)
                     # Send Remove Command
                     cmd = {"action": "REMOVE_PAIR", "symbol": rm_sym}
                     try:
                         existing_cmds = []
                         if os.path.exists(COMMANDS_FILE):
                             try:
                                 with open(COMMANDS_FILE, 'r') as f: existing_cmds = json.load(f)
                             except: pass
                         existing_cmds.append(cmd)
                         with open(COMMANDS_FILE, 'w') as f: json.dump(existing_cmds, f)
                     except: pass
                     
            with open(USER_WATCHLIST_FILE, 'w') as f: json.dump(user_watchlist, f)
            st.rerun()
    
    # --- IPC HEARTBEAT & PID WATCHDOG (Sidebar) ---
    st.sidebar.markdown(f'<div class="mode-badge">{view_mode.upper()} MODE</div>', unsafe_allow_html=True)
    
    # 1. Heartbeat check
    last_update = status_data.get('timestamp', 0)
    if last_update:
        age = time.time() - last_update
        if age < 30: st.sidebar.markdown("🟢 **System Online**")
        elif age < 60: st.sidebar.markdown("🟠 **Stale Data**")
        else: st.sidebar.markdown("🔴 **DISCONNECTED**")
    
    # 2. PID Watchdog (GP3)
    if current_pid:
        try:
            p = psutil.Process(current_pid)
            cpu = p.cpu_percent(interval=None)
            ram = p.memory_info().rss / (1024 * 1024) # MB
            st.sidebar.markdown(f"""
            **Bot Health (PID: {current_pid})**
            - CPU Usage: `{cpu:.1f}%`
            - RAM Usage: `{ram:.1f} MB`
            """)
        except:
            st.sidebar.warning("Bot process lost.")

    # Global Refresh Rate
    refresh_rate = st.sidebar.slider("Refresh (s)", 2, 60, 10, key="global_refresh_slider")
    
    st.sidebar.divider()

    # --- OPERATIONAL CONTROLS (Manual Override) ---
    st.sidebar.markdown("### ⚠️ Operational Controls")
    
    from config import COMMANDS_FILE
    import uuid
    
    col_op1, col_op2 = st.sidebar.columns(2)
    with col_op1:
        if st.button("🟢 Force BUY", key="side_force_buy"):
            cmd = {
                "id": str(uuid.uuid4()),
                "action": "FORCE_BUY",
                "symbol": selected_pair,
                "timestamp": time.time()
            }
            current_cmds = safe_read_json(COMMANDS_FILE, default=[])
            current_cmds.append(cmd)
            with open(COMMANDS_FILE, 'w') as f:
                json.dump(current_cmds, f)
            st.sidebar.success(f"Sent BUY for {selected_pair}")
            st.toast(f"Command Queued: FORCE_BUY {selected_pair}", icon="✅")

    with col_op2:
        if st.button("🔴 Force SELL", key="side_force_sell"):
            cmd = {
                "id": str(uuid.uuid4()),
                "action": "FORCE_SELL",
                "symbol": selected_pair,
                "timestamp": time.time()
            }
            current_cmds = safe_read_json(COMMANDS_FILE, default=[])
            current_cmds.append(cmd)
            with open(COMMANDS_FILE, 'w') as f:
                json.dump(current_cmds, f)
            st.sidebar.success(f"Sent SELL for {selected_pair}")
            st.toast(f"Command Queued: FORCE_SELL {selected_pair}", icon="✅")

    if st.sidebar.button("🚨 PANIC: SELL ALL", type="primary", key="side_panic"):
        cmd = {
            "id": str(uuid.uuid4()),
            "action": "PANIC_SELL_ALL",
            "timestamp": time.time()
        }
        current_cmds = safe_read_json(COMMANDS_FILE, default=[])
        current_cmds.append(cmd)
        with open(COMMANDS_FILE, 'w') as f:
            json.dump(current_cmds, f)
        st.sidebar.error("PANIC SIGNAL SENT!")
        st.toast("Panic command sent!", icon="🚨")


    # --- PROCESS CONTROL ---
    import subprocess
    import signal
    import psutil

    LOG_FILE = os.path.join("logs", "bot_stdout.log") # Redirecting to stdout log for now or keep bot.log
    # LOG_FILE is used by sidecar, ensure consistency
    LOG_FILE = os.path.join("logs", "bot.log")

    # --- SIDECAR SERVER (Port 8502) ---
    import http.server
    import socketserver
    import threading

    @st.cache_resource
    def start_sidecar_server():
        """Starts a background HTTP server to serve JSON status files to the frontend."""
        PORT = 9000
        
        class CORSRequestHandler(http.server.SimpleHTTPRequestHandler):
            def log_message(self, format, *args):
                pass # Silence logs
                
            def do_POST(self):
                if self.path == '/shutdown':
                    def kill_me():
                        print("Sidecar server shutting down...")
                        httpd.shutdown()
                    threading.Thread(target=kill_me).start()
                    self.send_response(200)
                    self.end_headers()
                else:
                    self.send_error(404)
                
            def do_GET(self):
                if self.path == '/logs':
                    self.send_response(200)
                    self.send_header('Content-type', 'text/plain')
                    self.end_headers()
                    # Read last 50 lines of logs
                    log_content = ""
                    if os.path.exists(LOG_FILE):
                        try:
                            # Efficient tail reading
                            with open(LOG_FILE, 'r', errors='ignore') as f:
                                # Simple and robust: Read all lines and slice last 50.
                                # Windows file locking can be tricky, simple read is usually safer than seek operations on active files.
                                lines = f.readlines()
                                log_content = "".join(lines[-50:])
                        except Exception as e:
                            log_content = f"Error reading logs: {e}"
                    else:
                        log_content = "Log file not found."
                    
                    self.wfile.write(log_content.encode('utf-8'))
                else:
                    super().do_GET()

            def end_headers(self):
                self.send_header('Access-Control-Allow-Origin', '*')
                super().end_headers()
        
        class QuietTCPServer(socketserver.TCPServer):
            def handle_error(self, request, client_address):
                # Suppress output for connection resets/aborts (WinError 10053/10054)
                import sys
                exc_type, exc_value, _ = sys.exc_info()
                if isinstance(exc_value, ConnectionAbortedError) or isinstance(exc_value, ConnectionResetError):
                    return # Ignore benign browser disconnects
                super().handle_error(request, client_address)

        def run_server():
            try:
                # Allow reuse address to prevent 'Address already in use' on reload
                socketserver.TCPServer.allow_reuse_address = True
                global httpd
                with QuietTCPServer(("", PORT), CORSRequestHandler) as server:
                    httpd = server
                    server.serve_forever()
            except OSError as e:
                # Port likely already in use by us from previous run
                print(f"Sidecar server port {PORT} busy (likely already running): {e}")

        # DYNAMIC PORT SELECTION
        # If 8502 is busy (zombie thread), try next ports up to 8510
        final_port = PORT
        
        import socket
        import urllib.request
        
        def is_port_in_use(port):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                return s.connect_ex(('localhost', port)) == 0

        # Try to grab a port
        for p in range(PORT, PORT + 10):
            if not is_port_in_use(p):
                final_port = p
                break
            else:
                # If port is in use, try to shutdown if it supports it
                try:
                    print(f"Port {p} in use. Attempting graceful shutdown...")
                    req = urllib.request.Request(f"http://localhost:{p}/shutdown", method="POST")
                    with urllib.request.urlopen(req, timeout=1) as response:
                        pass
                    time.sleep(0.5)
                    if not is_port_in_use(p):
                        final_port = p
                        break
                except:
                    # If shutdown fails (e.g. 403 Forbidden because old server doesn't support it),
                    # just move to next port
                    pass
        
        def run_server(port):
            try:
                socketserver.TCPServer.allow_reuse_address = True
                global httpd
                # Bind to specific port
                with socketserver.TCPServer(("", port), CORSRequestHandler) as server:
                    httpd = server
                    server.serve_forever()
            except OSError as e:
                print(f"Error starting server on {port}: {e}")

        t = threading.Thread(target=run_server, args=(final_port,), daemon=True)
        t.start()
        
        return final_port

    sidecar_port = start_sidecar_server()
    # ----------------------------------



    # --- PROCESS HEALTH CHECK ---


    # --- SMART LOG ROTATION ---
    if 'log_rotated' not in st.session_state:
        # Only rotate if Bot is fully OFFLINE to prevent wiping active logs
        # And only once per session
        bot_pid = is_bot_running()
        if not bot_pid:
            try:
                rotate_logs()
                dash_logger.info("--- NEW DASHBOARD SESSION: Logs Rotated ---")
            except Exception as e:
                print(f"Log Rotation Skipped: {e}")
        else:
            dash_logger.info("--- NEW DASHBOARD SESSION: Connecting to Running Bot ---")
            
        st.session_state['log_rotated'] = True
    # --------------------------

    current_pid = is_bot_running()
    
    # Defaults needed early for metrics & startup
    paper_capital = 10000.0
    paper_watchlist = "BTC/USD, ETH/USD, SOL/USD, LUNC/USD"
    paper_holdings = ""
    
    # GHOST DATA PREVENTION
    # If bot is NOT running, we must ensure we don't display stale file data.
    # We overwrite the loaded status_data with "Offline" templates if pid is None.
    if not current_pid:
        status_data = {
            'last_update': datetime.now().isoformat(),
            'active_pairs': [],
            'strategies': [],
            'uptime_seconds': 0,
            'portfolio_value': 10000.0,  # Correctly matches initial capital for 0 PnL
            'initial_capital': 10000, # Prevents div/0 or weird PnL
            'paper_trading': True # Default safely to True if unknown
        }

    # STARTUP CLEANUP (User Request)
    # "If the bot is already active but the Start Bot hasn't been pressed then to close the bot."
    # We use session_state to track if this tab has "seen" the bot before.
    if 'init_done' not in st.session_state:
        st.session_state['init_done'] = True
        
        # AGGRESSIVE ZOMBIE HUNT
        # If the user sees "Time Active: 12h", there is a ghost process running main.py 
        # that doesn't match the PID file (or PID file is missing).
        # We must scan ALL python processes for "main.py".
        zombies_found = 0
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    # Check if it's python and running main.py
                    if 'python' in proc.info['name'].lower():
                        cmdline = proc.info['cmdline'] or []
                        if any('main.py' in arg for arg in cmdline):
                            # FOUND A ZOMBIE
                            pid = proc.info['pid']
                            # Don't kill self (dashboard.py) - though dashboard runs via streamlit run dashboard.py
                            # main.py is the bot.
                            print(f"Terminating Zombie Bot: {pid}")
                            proc.terminate()
                            zombies_found += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass
        except Exception as e:
            print(f"Zombie Hunt Failed: {e}")

        if zombies_found > 0 or current_pid:
             if os.path.exists(PID_FILE):
                try: os.remove(PID_FILE)
                except: pass
             current_pid = None
             st.toast(f"🧹 Cleaned up {zombies_found} zombie bot process(es).", icon="💀")
             time.sleep(1)
             st.rerun()

    # Execution Mode Config
    
    # Strategy Selector (Only if Council is OFF, though we let user pick preference anyway)
    STRATEGY_OPTIONS = ["SMA", "RSI", "MACD", "EMA", "KELTNER", "COMBINED", "ML"]
    # We need to save this preference so main.py can pick it up. 
    # main.py reads env var 'STRATEGY_TYPE' or defaults. 
    # We can write to a settings file or set env var in the subprocess call.
    # Let's save it to runtime_settings.json or similar, but main.py reads env vars at startup.
    # Easier: Pass it as an argument or restart bot on change.
    
    # --- MAIN PAGE RENDERING ---



    if nav == NAV_AI_LAB:
        st.header("🧠 AI Research Lab: Neural Forge")
        
        ai_tab1, ai_tab2 = st.tabs(["🎛️ AI Controls (Training & Tuning)", "📊 TensorBoard (Insight)"])
        
        with ai_tab1:
            st.subheader("🏋️ AI Model Training")
            st.caption("Customize and launch Reinforcement Learning training sessions.")
            
            c1, c2 = st.columns(2)
            with c1:
                train_symbol = st.selectbox("Training Symbol", ["ALL TOP 10"] + TOP_10_CRYPTO, index=0, key="lab_train_symbol")
                train_timeframe = st.selectbox("Data Timeframe", ["1m", "5m", "15m", "1h", "4h", "1d"], index=3, key="lab_train_tf")
            with c2:
                train_timesteps = st.number_input("Timesteps", min_value=1000, max_value=2000000, value=50000, step=1000, key="lab_train_steps")
                train_reward = st.radio("Optimization Goal", ["Profit Maximization (Sharpe)", "Prediction Accuracy"], index=0, key="lab_train_goal")
            
            c3, c4 = st.columns(2)
            with c3:
                train_wf = st.checkbox("Enable Walk-Forward Validation (Time-Traveler)", value=True, key="lab_train_wf", help="Splits data into sequential windows (e.g. 2021, 2022, 2023) to train and test separately. Prevents the AI from 'memorizing the future'. Essential for testing robustness.")
                train_resume = st.checkbox("Resume from Existing Model", value=False, key="lab_train_resume")
                
                selected_model = "ppo_model_latest"
                if train_resume:
                    MODELS_DIR = os.path.join(os.getcwd(), "models")
                    available_models = []
                    if os.path.exists(MODELS_DIR):
                        available_models = [f[:-4] for f in os.listdir(MODELS_DIR) if f.endswith(".zip")]
                    
                    if available_models:
                        default_idx = available_models.index("ppo_model_latest") if "ppo_model_latest" in available_models else 0
                        selected_model = st.selectbox("🎯 Target Model", available_models, index=default_idx)
                    else:
                        st.caption("⚠️ No models found in `models/` directory.")
                else:
                    selected_model = st.text_input("✨ Name Your Creation", value="ppo_model_custom", key="lab_new_model_name")

            with c4:
                train_envs = st.slider("Parallel Environments (Speed Demon)", 1, 8, 4, key="lab_train_envs")

            if st.button("🚀 IGNITE TRAINING", type="primary", width="stretch"):
                try:
                    reward_mode = 'accuracy' if train_reward == "Prediction Accuracy" else 'profit'
                    sym_param = "ALL" if train_symbol == "ALL TOP 10" else train_symbol
                    
                    cmd = [sys.executable, "train.py", 
                           "--symbol", sym_param,
                           "--timeframe", train_timeframe,
                           "--timesteps", str(train_timesteps),
                           "--reward", reward_mode,
                           "--n-envs", str(train_envs),
                           "--model-name", selected_model]
                    
                    if train_wf: cmd.append("--walk-forward")
                    if train_resume: cmd.append("--resume")
                    
                    subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
                    st.success(f"🔥 Training ignited for {train_symbol}! Target: {selected_model}")
                except Exception as e:
                    st.error(f"Ignition failure: {e}")

            st.divider()
            st.subheader("🧪 Hyperparameter Auto-Tuner (Optuna)")
            st.caption("Bayesian search for the perfect AI settings. Recommended after significant market shifts.")
            
            if st.button("🧬 Start Auto-Tuner", width="stretch"):
                try:
                    subprocess.Popen([sys.executable, "tune.py"], creationflags=subprocess.CREATE_NEW_CONSOLE)
                    st.info("🧬 Genetic/Bayesian tuning started in background. Check terminal for results.")
                except Exception as e:
                    st.error(f"Tuner failed: {e}")

        with ai_tab2:
            st.subheader("📊 TensorBoard: Live Neural Feedback")
            
            tb_proc = get_tensorboard_process()
            
            if tb_proc:
                st.write(f"🟢 **TensorBoard Active** (PID: {tb_proc.pid})")
                if st.button("🛑 Stop TensorBoard"):
                    tb_proc.terminate()
                    st.rerun()
                
                st.markdown("---")
                # Iframe for TensorBoard
                st.components.v1.iframe("http://localhost:6006", height=800, scrolling=True)
            else:
                st.warning("⚪ TensorBoard is offline.")
                if st.button("🚀 Launch TensorBoard"):
                    start_tensorboard()
                    st.info("Launching TensorBoard... Please wait a few seconds and refresh this tab.")
                    time.sleep(3)
                    st.rerun()
                
                st.caption("TensorBoard provides visual graphs of Loss, Reward, and Policy Entropy during AI training.")

    elif nav == NAV_OPTIONS:
        st.header("⚙️ System Options & Data Management")
        
        # --- TRAINING INTERFACE ---


        st.divider()

        st.divider()

        # --- WALLET CONNECTIONS (MANAGER) ---
        with st.expander("👛 Wallet Connections", expanded=False):
            st.caption("Configure API Keys for specific exchanges. Credentials are saved locally to .env.")
            
            def update_env_var(key, value):
                """Helper to update .env file safely."""
                if not value: return # Don't save empty
                
                env_path = ".env"
                lines = []
                if os.path.exists(env_path):
                    with open(env_path, 'r') as f:
                        lines = f.readlines()
                
                key_found = False
                new_lines = []
                for line in lines:
                    if line.startswith(f"{key}="):
                        new_lines.append(f"{key}={value}\n")
                        key_found = True
                    else:
                        new_lines.append(line)
                
                if not key_found:
                    if new_lines and not new_lines[-1].endswith('\n'):
                        new_lines[-1] += '\n'
                    new_lines.append(f"{key}={value}\n")
                
                with open(env_path, 'w') as f:
                    f.writelines(new_lines)
                
                # Reload for current session to reflect changes
                os.environ[key] = value

            # TABS
            wt1, wt2, wt3, wt4, wt5 = st.tabs(["Kraken", "Coinbase", "Gemini", "Binance.US", "Custom"])
            
            # --- KRAKEN ---
            with wt1:
                st.markdown("##### 🐙 Kraken Configuration")
                k_key_set = "KRAKEN_API_KEY" in os.environ and len(os.environ["KRAKEN_API_KEY"]) > 5
                st.info(f"Status: {'✅ Configured' if k_key_set else '❌ Not Configured'}")
                
                nk_key = st.text_input("API Key", type="password", key="inp_kraken_key")
                nk_sec = st.text_input("API Secret", type="password", key="inp_kraken_sec")
                
                if st.button("💾 Save Kraken Credentials"):
                    if nk_key and nk_sec:
                        update_env_var("KRAKEN_API_KEY", nk_key)
                        update_env_var("KRAKEN_SECRET", nk_sec)
                        st.success("Kraken credentials saved!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("Please enter both Key and Secret.")

            # --- COINBASE ---
            with wt2:
                st.markdown("##### 🔵 Coinbase Configuration")
                c_key_set = "COINBASE_API_KEY" in os.environ and len(os.environ["COINBASE_API_KEY"]) > 5
                st.info(f"Status: {'✅ Configured' if c_key_set else '❌ Not Configured'}")
                
                nc_key = st.text_input("API Key (Name)", type="password", key="inp_cb_key")
                nc_sec = st.text_input("API Secret (Private Key)", type="password", key="inp_cb_sec")
                
                if st.button("💾 Save Coinbase Credentials"):
                    if nc_key and nc_sec:
                        update_env_var("COINBASE_API_KEY", nc_key)
                        update_env_var("COINBASE_SECRET", nc_sec)
                        st.success("Coinbase credentials saved!")
                        time.sleep(1)
                        st.rerun()

            # --- GEMINI ---
            with wt3:
                st.markdown("##### ♊ Gemini Configuration")
                g_key_set = "GEMINI_API_KEY" in os.environ and len(os.environ["GEMINI_API_KEY"]) > 5
                st.info(f"Status: {'✅ Configured' if g_key_set else '❌ Not Configured'}")
                
                ng_key = st.text_input("API Key", type="password", key="inp_gem_key")
                ng_sec = st.text_input("API Secret", type="password", key="inp_gem_sec")
                
                if st.button("💾 Save Gemini Credentials"):
                    if ng_key and ng_sec:
                        update_env_var("GEMINI_API_KEY", ng_key)
                        update_env_var("GEMINI_SECRET", ng_sec)
                        st.success("Gemini credentials saved!")
                        time.sleep(1)
                        st.rerun()

            # --- BINANCE.US ---
            with wt4:
                st.markdown("##### 🇺🇸 Binance.US Configuration")
                b_key_set = "BINANCEUS_API_KEY" in os.environ and len(os.environ["BINANCEUS_API_KEY"]) > 5
                st.info(f"Status: {'✅ Configured' if b_key_set else '❌ Not Configured'}")
                
                nb_key = st.text_input("API Key", type="password", key="inp_bin_key")
                nb_sec = st.text_input("API Secret", type="password", key="inp_bin_sec")
                
                if st.button("💾 Save Binance.US Credentials"):
                    if nb_key and nb_sec:
                        update_env_var("BINANCEUS_API_KEY", nb_key)
                        update_env_var("BINANCEUS_SECRET", nb_sec)
                        st.success("Binance.US credentials saved!")
                        time.sleep(1)
                        st.rerun()

            # --- CUSTOM ---
            with wt5:
                st.markdown("##### 🌐 Custom Exchange (CCXT)")
                cust_set = "CUSTOM_API_KEY" in os.environ and len(os.environ["CUSTOM_API_KEY"]) > 5
                st.info(f"Status: {'✅ Configured' if cust_set else '❌ Not Configured'}")
                
                cust_id = st.text_input("Exchange ID (e.g. 'kucoin', 'okx')", key="inp_cust_id")
                cust_key = st.text_input("API Key", type="password", key="inp_cust_key")
                cust_sec = st.text_input("API Secret", type="password", key="inp_cust_sec")
                
                if st.button("💾 Save Custom Credentials"):
                    if cust_id and cust_key and cust_sec:
                        update_env_var("CUSTOM_EXCHANGE_ID", cust_id)
                        update_env_var("CUSTOM_API_KEY", cust_key)
                        update_env_var("CUSTOM_SECRET", cust_sec)
                        st.success(f"{cust_id} credentials saved!")
                        time.sleep(1)
                        st.rerun()

        st.divider()

        # --- HITL: DYNAMIC TUNING ---
        tuning_help = "Dynamic Tuning: Adjust real-time risk parameters affecting the bot's trading behavior. Changes take effect on the next evaluation cycle."
        st.markdown(f"""
        <div style="display: flex; align-items: center; margin-bottom: 10px;">
            <h3 style="margin: 0; padding: 0;">🎛️ Dynamic Tuning</h3>
            <span title="{tuning_help}" style="margin-left: 10px; cursor: help; font-size: 1.2rem; opacity: 0.8;">ℹ️</span>
        </div>
        """, unsafe_allow_html=True)
        
        # Load current settings from file or defaults
        current_settings = {
            'MAX_DRAWDOWN_PCT': MAX_DRAWDOWN_PCT,
            'MAX_POSITION_SIZE_PCT': MAX_POSITION_SIZE_PCT,
            'MAX_SLIPPAGE_PCT': MAX_SLIPPAGE_PCT,
            'STOP_LOSS_PCT': STOP_LOSS_PCT,
            'TAKE_PROFIT_PCT': TAKE_PROFIT_PCT
        }
        
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, 'r') as f:
                    saved_settings = json.load(f)
                    current_settings.update(saved_settings)
            except: pass
        
        # Sliders (Moved from sidebar)
        new_drawdown = st.slider("Max Drawdown", 0.01, 0.50, float(current_settings['MAX_DRAWDOWN_PCT']), key="opt_drawdown")
        new_pos_size = st.slider("Max Position Size", 0.01, 0.20, float(current_settings['MAX_POSITION_SIZE_PCT']), key="opt_pos_size")
        new_stop_loss = st.slider("Stop Loss", 0.01, 0.20, float(current_settings['STOP_LOSS_PCT']), key="opt_stop_loss")
        new_take_profit = st.slider("Take Profit", 0.01, 0.50, float(current_settings['TAKE_PROFIT_PCT']), key="opt_take_profit")
        
        # Save if changed
        updated_settings = {
            'MAX_DRAWDOWN_PCT': new_drawdown,
            'MAX_POSITION_SIZE_PCT': new_pos_size,
            'MAX_SLIPPAGE_PCT': current_settings['MAX_SLIPPAGE_PCT'], 
            'STOP_LOSS_PCT': new_stop_loss,
            'TAKE_PROFIT_PCT': new_take_profit
        }
        
        if updated_settings != current_settings:
            try:
                # Update current_settings with the new values before saving
                current_settings.update(updated_settings)
                with open(SETTINGS_FILE, 'w') as f:
                    json.dump(current_settings, f)
                st.success("Tuning parameters updated!")
            except Exception as e:
                st.error(f"Save failed: {e}")

        st.divider()

        # 2. DANGER ZONE
        # 2. DANGER ZONE
        with st.expander("🚨 Danger Zone (Data Cleanup)", expanded=True):
            c1, c2, c3 = st.columns(3)
            
            # COLUMN 1: MODEL MANAGEMENT
            with c1:
                st.markdown("#### 🧠 Manage Models")
                st.caption("Delete old model checkpoints.")
                
                model_dirs = ["models", "saved_models"]
                model_files = []
                for d in model_dirs:
                    if os.path.exists(d):
                        for f in os.listdir(d):
                            if f.endswith('.zip'):
                                model_files.append(os.path.join(d, f))
                
                if model_files:
                    selected_models = st.multiselect("Select Models", model_files)
                    if st.button("🗑️ Delete Models", type="secondary"):
                        if selected_models:
                            deleted_count = 0
                            for m_path in selected_models:
                                try:
                                    os.remove(m_path)
                                    deleted_count += 1
                                except Exception as e:
                                    st.error(f"Error: {e}")
                            
                            if deleted_count > 0:
                                st.success(f"Deleted {deleted_count} models.")
                                time.sleep(1)
                                st.rerun()
                else:
                    st.info("No saved models found.")

            # COLUMN 2: TRADE HISTORY
            with c2:
                st.markdown("#### recent trades")
                st.caption("Clears local trade history CSV.")
                if st.button("🗑️ Clear History"):
                    try:
                        if TRADE_FILE and os.path.exists(TRADE_FILE):
                            os.remove(TRADE_FILE)
                            st.success("Trade history cleared.")
                        else:
                            st.warning("No history file.")
                    except Exception as e:
                        st.error(f"Error: {e}")

            # COLUMN 3: WATCHLIST
            with c3:
                st.markdown("#### Watchlist")
                st.caption("Resets watchlist to default.")
                if st.button("🗑️ Reset Watchlist"):
                    try:
                        if os.path.exists(USER_WATCHLIST_FILE):
                            os.remove(USER_WATCHLIST_FILE)
                            st.success("Watchlist reset.")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.warning("Already empty.")
                    except Exception as e:
                        st.error(f"Error: {e}")


    elif nav == NAV_BACKTEST:
        st.header("🧪 Digital Twin: Backtest Lab")
        st.write("Stress-test your Council configurations against historical crashes and synthetic scenarios.")
        
        col_setup, col_results = st.columns([1, 2])
        
        with col_setup:
            st.subheader("🧬 Council Drafter")
            selected_agents = st.multiselect("Active Agents", 
                                           ["Trend", "Oscillator", "Volume", "Analyst", "OnChain", "Chronos", "TimeGPT"],
                                           default=["Trend", "Oscillator", "Volume", "Chronos"])
            
            st.subheader("⚖️ Meritocracy Tuning")
            weights = {}
            for agent in selected_agents:
                weights[agent] = st.slider(f"{agent} Weight", 0.1, 2.0, 1.0, key=f"bt_weight_{agent}")
            
            st.subheader("📉 Scenario Studio")
            scenario_files = os.listdir('data_storage/scenarios') if os.path.exists('data_storage/scenarios') else []
            selected_scenario = st.selectbox("Historical Scenario", scenario_files)
            
            bt_capital = st.number_input("Starting Capital ($)", value=10000.0)
            
            if st.button("🚀 IGNITE BACKTEST", type="primary", width="stretch"):
                # 1. Instantiate Agents
                agent_instances = []
                if "Trend" in selected_agents: agent_instances.append(TrendAgent())
                if "Oscillator" in selected_agents: agent_instances.append(OscillatorAgent())
                if "Volume" in selected_agents: agent_instances.append(VolumeAgent())
                if "Analyst" in selected_agents: agent_instances.append(AnalystAgent())
                if "OnChain" in selected_agents: agent_instances.append(OnChainAgent())
                if "Chronos" in selected_agents: agent_instances.append(ChronosAgent())
                if "TimeGPT" in selected_agents: agent_instances.append(TimeGPTAgent())
                
                # 2. Setup MetaStrategy
                meta = MetaStrategy(agent_instances, voting_method='weighted')
                # Apply custom weights manually (mapping from UI to agent names)
                name_map = {"Trend": "TrendAgent", "Oscillator": "OscillatorAgent", "Volume": "VolumeAgent", 
                            "Analyst": "AnalystAgent", "OnChain": "OnChainAgent", "Chronos": "ChronosAgent",
                            "TimeGPT": "TimeGPTAgent"}
                for label, weight in weights.items():
                    agent_name = name_map.get(label)
                    if agent_name in meta.agent_weights:
                        meta.agent_weights[agent_name] = weight
                
                # 3. Load Scenario Data
                df_scenario = pd.read_csv(os.path.join('data_storage/scenarios', selected_scenario))
                df_scenario['timestamp'] = pd.to_datetime(df_scenario['timestamp'])
                
                # 4. Run Backtest
                engine = BacktestEngine(start_cash=bt_capital)
                engine.run(df_scenario, strategy_class=CouncilStrategy, meta_strategy=meta)
                st.session_state['bt_results'] = engine.get_metrics()
                st.session_state['bt_df_results'] = df_scenario # In real app, we'd capture equity curve
                st.success("Backtest Complete!")

        with col_results:
            st.subheader("📊 Performance Forensic")
            if 'bt_results' in st.session_state:
                res = st.session_state['bt_results']
                c1, c2, c3 = st.columns(3)
                c1.metric("Final Value", f"${res['final_value']:,.2f}")
                c2.metric("ROI", f"{res['roi']:.2%}")
                c3.metric("Max Drawdown", f"{res['max_drawdown']:.2%}")
                
                # Visual (Mock Equity Curve for now based on ROI)
                # In a real version, we'd extract the curve from cerebro
                st.info("Visual Equity Curve generation in progress (Institutional Era Beta)")
                
                st.subheader("🎖️ Decision Density")
                st.caption("Distribution of agent consensus during the scenario.")
                # Radar chart or similar would go here
            else:
                st.info("Configure and ignite a backtest to see results.")

    elif nav == NAV_DASHBOARD:
        col_header, col_mode = st.columns([3, 1])
        with col_header:
            st.header("🛸 Mission Control")
        with col_mode:
            # View Mode Selector (Live/Paper/Shadow)
            current_mode = st.session_state.get('view_mode_state', 'Live')
            new_mode = st.radio("View Mode", ["Live", "Paper", "Shadow (Comparison)"], 
                               index=["Live", "Paper", "Shadow (Comparison)"].index(current_mode),
                               horizontal=True, key="view_mode_selector", label_visibility="collapsed")
            if new_mode != current_mode:
                st.session_state['view_mode_state'] = new_mode
                st.rerun()
        
        # 1. HUD (Metrics)
        @st.fragment(run_every=5) # Update every 5s independent of main loop
        def render_live_hud(filepath):
            # Re-read data for live updates
            local_data = safe_read_json(filepath)
            
            val_usd = local_data.get('portfolio_value', 0.0)
            init_cap = local_data.get('initial_capital', 10000.0)
            pnl = val_usd - init_cap
            pnl_pct = (pnl / init_cap) * 100 if init_cap > 0 else 0.0
            active_count = len(local_data.get('active_pairs', []))
            
            # Latency
            vitals = local_data.get('vitals', {})
            avg_lat = 0
            if vitals:
                latencies = [m.get('avg_latency', 0) for m in vitals.values()]
                if latencies: avg_lat = sum(latencies) / len(latencies)
                
            hud1, hud2, hud3, hud4 = st.columns(4)
            with hud1: st.metric("Portfolio Value", f"${val_usd:,.2f}", f"${pnl:,.2f}")
            with hud2: st.metric("Unrealized PnL", f"{pnl_pct:.2f}%", f"${pnl:.2f}")
            with hud3: st.metric("Active Positions", f"{active_count}", "Strategies Active")
            with hud4: st.metric("System Latency", f"{avg_lat:.0f}ms", f"{avg_lat - 100:.0f}ms", delta_color="inverse")

            # --- MARTIAL LAW BADGE ---
            # Try to get regime for the first active pair or global
            council_dicts = local_data.get('council_data', {})
            current_regime = "PEACE"
            if council_dicts:
                # Use the first available regime status
                first_key = list(council_dicts.keys())[0]
                current_regime = council_dicts[first_key].get('regime', 'PEACE')
            
            regime_color = "#00cc96" if current_regime == "PEACE" else "#ff4b4b"
            st.markdown(f"""
                <div style='text-align: right; margin-top: -65px; margin-bottom: 25px;'>
                    <span style='background-color: {regime_color}; color: white; padding: 6px 18px; border-radius: 25px; font-weight: bold; border: 3px solid #1E1E1E; box-shadow: 0 4px 10px rgba(0,0,0,0.5);'>
                        ⚖️ {current_regime}TIME CONSTITUTION
                    </span>
                </div>
            """, unsafe_allow_html=True)
        
        # Call the fragment
        if STATUS_FILE:
            render_live_hud(STATUS_FILE)
        else:
            st.warning("Status file not selected.")
        
        st.divider()
    
        # 2. MAIN CONTENT
        @st.fragment(run_every=refresh_rate)
        def render_dashboard_content(status_file, selected_pair):
            # Refresh Data
            local_data = safe_read_json(status_file)
            
            if view_mode == "Shadow (Comparison)":
                st.subheader("⚖️ Shadow Mode / A/B Test")
                col1, col2 = st.columns(2)
                
                # Load Data
                pt_live = pd.DataFrame(); pt_paper = pd.DataFrame()
                if os.path.exists(PORTFOLIO_HISTORY_LIVE): pt_live = pd.read_csv(PORTFOLIO_HISTORY_LIVE)
                if os.path.exists(PORTFOLIO_HISTORY_PAPER): pt_paper = pd.read_csv(PORTFOLIO_HISTORY_PAPER)
                
                with col1:
                    st.caption("⚡ Live Bot")
                    if not pt_live.empty:
                        st.metric("Live Equity", f"${pt_live['TotalValueUSD'].iloc[-1]:,.2f}")
                    else: st.info("No Live Data")
                    
                with col2:
                    st.caption("🎭 Paper/Shadow Bot")
                    if not pt_paper.empty:
                        st.metric("Paper Equity", f"${pt_paper['TotalValueUSD'].iloc[-1]:,.2f}")
                    else: st.info("No Paper Data")
                    
                # Comparison Chart
                if not pt_live.empty: pt_live['Source'] = 'Live'
                if not pt_paper.empty: pt_paper['Source'] = 'Paper'
                combined = pd.concat([pt_live, pt_paper])
                if not combined.empty:
                    fig_comp = px.line(combined, x='Timestamp', y='TotalValueUSD', color='Source', title='Equity Comparison')
                    st.plotly_chart(fig_comp, width='stretch')
                    
            else:
                # Standard View: Council Only
                display_pair = selected_pair
                if display_pair == "ALL":
                    # Try to find the first real pair from council_data or use BTC/USD
                    council_data = local_data.get('council_data', {})
                    if council_data:
                        display_pair = list(council_data.keys())[0]
                    else:
                        display_pair = "BTC/USD"
                else:
                    council_data = local_data.get('council_data', {})

                st.subheader(f"🤖 The Council of AIs: {display_pair}", help="An ensemble of specialized AI agents (Trend, Sentiment, On-Chain) that vote on trades. Consensus is required for action.")
                
                # Mock for UI Demo if empty
                if not council_data and not is_bot_running():
                    # Generate deterministic mock perception based on selected pair
                    seed = int(hashlib.md5(display_pair.encode()).hexdigest(), 16) % 100
                    rng = np.random.default_rng(seed)
                    
                    mock_agents = ["Trend", "Oscillator", "Volume", "Analyst", "OnChain", "Chronos", "TimeGPT", "NewtonAgent"]
                    mock_votes = []
                    mock_weights = {}
                    
                    for agent in mock_agents:
                        v_val = rng.random()
                        vote = "buy" if v_val > 0.6 else "sell" if v_val < 0.4 else "hold"
                        conf = rng.uniform(0.4, 0.9)
                        weight = rng.uniform(0.7, 1.3)
                        
                        reasoning = {"reason": ""}
                        if agent == "NewtonAgent":
                            # Mock random z_score (mostly quiet, occasionally spikes)
                            mock_z = rng.gamma(1.0, 1.0) # Skewed distribution
                            reasoning['z_score'] = float(mock_z)
                            if mock_z > 3.0: 
                                vote = 'buy'
                                conf = 0.95
                                
                        mock_votes.append({"agent": agent, "vote": vote, "confidence": conf, "reasoning": reasoning})
                        mock_weights[agent] = weight
                        
                    council_data = {display_pair: {
                        "votes": mock_votes,
                        "agent_weights": mock_weights,
                        "regime": "WAR" if rng.random() > 0.7 else "PEACE"
                    }}
                
                selected_council = council_data.get(display_pair, {})
                target_votes = selected_council.get('votes', [])
                
                c_radar, col_details = st.columns([1, 1])
                
                buy_pressure = 0; sell_pressure = 0 # Track globally for consensus meter
                
                with c_radar:
                    radar_help = "Consensus Radar: Visualizes the conviction strength of each agent (Confidence × Influence). Larger areas indicate stronger collective agreement."
                    st.markdown(f"""
                    <div style="display: flex; align-items: center; margin-bottom: 10px;">
                        <h4 style="margin: 0; padding: 0;">📡 Consensus Radar</h4>
                        <span title="{radar_help}" style="margin-left: 10px; cursor: help; font-size: 1.0rem; opacity: 0.8;">ℹ️</span>
                    </div>
                    """, unsafe_allow_html=True)
                    if target_votes:
                        categories = []; values = []
                        agent_weights = selected_council.get('agent_weights', {})
                        
                        for v in target_votes:
                            agent_name = v['agent']
                            weight = agent_weights.get(agent_name, 1.0)
                            
                            categories.append(agent_name)
                            score = v['confidence'] * weight
                            values.append(score)
                            
                            if v.get('vote') == 'buy': buy_pressure += score
                            elif v.get('vote') == 'sell': sell_pressure += score

                        # Draw Radar
                        fig_radar = go.Figure(data=go.Scatterpolar(
                          r=values, theta=categories, fill='toself', 
                          line_color='#2962ff'
                        ))
                        fig_radar.update_layout(
                          polar=dict(radialaxis=dict(visible=True, range=[0, 1.5])),
                          showlegend=False, height=300, margin=dict(l=30, r=30, t=10, b=10),
                          paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)'
                        )
                        st.plotly_chart(fig_radar, width="stretch")
                        
                        st.divider()
                        
                        # --- LEFT COLUMN CONTENT (Ruling + Consensus Meter) ---
                        # --- LEFT COLUMN CONTENT (Ruling + Consensus Meter) ---
                        ruling_help = "Supreme Court Ruling: The final verdict generated by the Council of AIs based on the majority vote and regime context (War/Peace)."
                        st.markdown(f"""
                        <div style="display: flex; align-items: center; margin-bottom: 10px;">
                            <h3 style="margin: 0; padding: 0;">🏛️ Supreme Court Ruling</h3>
                            <span title="{ruling_help}" style="margin-left: 10px; cursor: help; font-size: 1.2rem; opacity: 0.8;">ℹ️</span>
                        </div>
                        """, unsafe_allow_html=True)
                        regime = selected_council.get('regime', 'PEACE')
                        st.info(generate_council_insight(target_votes, regime))
                        
                        st.divider()
                        st.divider()
                        consensus_help = "Weighted Consensus: A normalized score (0-100%) reflecting the net conviction of the Council. High values indicate strong Buy pressure, low values indicate Sell pressure."
                        st.markdown(f"""
                        <div style="display: flex; align-items: center; margin-bottom: 10px;">
                            <h3 style="margin: 0; padding: 0;">⚖️ Weighted Consensus</h3>
                            <span title="{consensus_help}" style="margin-left: 10px; cursor: help; font-size: 1.2rem; opacity: 0.8;">ℹ️</span>
                        </div>
                        """, unsafe_allow_html=True)
                        if target_votes:
                            net_score = buy_pressure - sell_pressure
                            max_score = 3.0
                            normalized = max(0.0, min(1.0, (net_score + max_score) / (2 * max_score)))
                            st.progress(normalized)
                            st.caption(f"Bearish 🐻 {'&nbsp;'*5} Neutral 😐 {'&nbsp;'*5} Bullish 🚀")
                        else:
                            st.info("Waiting for Council votes...")
                    else:
                        st.info("Waiting for Council votes...")

                # --- NEWTON ELASTICITY GAUGE ---
                with col_details:
                    st.subheader("📏 Elasticity (Distance from Mean)", help="**Blue Bar:** Current Z-Score (Distance from 200 EMA Mean). \n\n**Red Line (4.0):** Impact Zone Threshold. If crossed (Zone > 4σ), the Newton Agent wakes up to execute a Knife Catch.")
                    # Extract z_score from NewtonAgent reasoning if available
                    z_score = 0.0
                    if target_votes:
                        newton_vote = next((v for v in target_votes if v['agent'] == 'NewtonAgent'), None)
                        if newton_vote and 'reasoning' in newton_vote:
                            z_score = newton_vote['reasoning'].get('z_score', 0.0)
                    
                    # If z_score is 0, we might want to calculate it if we had data,
                    # but for now let's just show what the agent sees.
                    
                    fig_gauge = go.Figure(go.Indicator(
                        mode = "gauge+number",
                        value = z_score,
                        domain = {'x': [0, 1], 'y': [0, 1]},
                        title = {'text': "σ Distance", 'font': {'size': 24}},
                        gauge = {
                            'axis': {'range': [0, 6], 'tickwidth': 1, 'tickcolor': "darkblue"},
                            'bar': {'color': "#2962ff" if z_score < 4 else "#ef553b"},
                            'bgcolor': "white",
                            'borderwidth': 2,
                            'bordercolor': "gray",
                            'steps': [
                                {'range': [0, 2], 'color': 'rgba(0, 255, 0, 0.3)'},
                                {'range': [2, 4], 'color': 'rgba(255, 255, 0, 0.3)'},
                                {'range': [4, 6], 'color': 'rgba(255, 0, 0, 0.3)'}],
                            'threshold': {
                                'line': {'color': "red", 'width': 4},
                                'thickness': 0.75,
                                'value': 4.0}}))
                    
                    fig_gauge.update_layout(height=250, margin=dict(l=20, r=20, t=50, b=20),
                                           paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                    st.plotly_chart(fig_gauge, width="stretch")
                    
                    if z_score >= 4.0:
                        st.error("🚨 **IMPACT ZONE DETECTED**: Price is >4σ from Mean. Newton Protocol Engaged.")

                        theme_color = "#00cc96" if buy_pressure > sell_pressure else "#ef553b"
                        fig_radar = go.Figure(data=go.Scatterpolar(
                          r=values, theta=categories, fill='toself', line_color=theme_color
                        ))
                        fig_radar.update_layout(
                          polar=dict(radialaxis=dict(visible=True, range=[0, 1.5])),
                          showlegend=False, height=350, margin=dict(l=40, r=40, t=20, b=20),
                          paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)'
                        )
                        st.plotly_chart(fig_radar, width='stretch')
                    else:
                        st.info("No active deliberation for this pair.")

                with col_details:
                    # --- RIGHT COLUMN CONTENT (Gauge + Scorecard + Badges) ---
                    # 1. Existing Gauge (Code for Gauge is above in original file, we are just appending to the block after it closes? No, 'with col_details:' was used for Gauge earlier. 
                    # Wait, the Gauge code lines 1274-1324 were ALREADY inside 'with col_details:'. 
                    # The previous edit replaced the EMPTY 'with col_details:' at line 1326 (which was redundant/empty) with 'st.empty()'.
                    # I should REPLACE that st.empty() with the new content.
                    
                    st.divider()
                    st.divider()
                    
                    # Custom Header with HTML Tooltip (avoiding st.help conflict)
                    header_help = "Meritocracy System: Agents earn voting power (Influence) based on their historical accuracy.\n\n- >1.0x: Outperforming (Trusted)\n- <1.0x: Underperforming (Probation)\n- Weight: Multiplier applied to their vote confidence."
                    header_help_safe = header_help.replace('"', '&quot;').replace('\n', '&#10;')
                    
                    st.markdown(f"""
                        <div style="display: flex; align-items: center; margin-bottom: 10px;">
                            <h3 style="margin: 0; padding: 0;">🎖️ Agent Merit Scorecard</h3>
                            <span title="{header_help_safe}" style="margin-left: 10px; cursor: help; font-size: 1.2rem; opacity: 0.8;">ℹ️</span>
                        </div>
                    """, unsafe_allow_html=True)
                    
                    # Agent Descriptions
                    AGENT_DESC = {
                        "Trend": "Follows long-term market direction using interacting SMAs/EMAs.",
                        "Oscillator": "Detects overbought/oversold conditions (RSI, Stochastic) to predict reversals.",
                        "Volume": "Analyzes buying/selling pressure to confirm price movements.",
                        "Analyst": "Uses pattern recognition and support/resistance levels.",
                        "OnChain": "Monitors blockchain activity (Whale movements, Exchange flows).",
                        "Chronos": "Deep Learning model trained on historical time-series patterns.",
                        "TimeGPT": "Generative AI forecasting model for time-series.",
                        "NewtonAgent": "Physics-based model measuring price velocity and mean reversion elasticity."
                    }

                    agent_weights = selected_council.get('agent_weights', {})
                    if agent_weights:
                        for agent, weight in agent_weights.items():
                            badge_color = "#00cc96" if weight >= 1.0 else "#ff9800" if weight > 0.5 else "#ff4b4b"
                            
                            # Find reasoning
                            reasoning = "Passive."
                            if target_votes:
                                vote_rec = next((v for v in target_votes if v['agent'] == agent), None)
                                if vote_rec and 'reasoning' in vote_rec:
                                    r_raw = vote_rec['reasoning']
                                    if isinstance(r_raw, dict):
                                        reasoning = r_raw.get('reason', 'Analysis available.')
                                    else:
                                        reasoning = str(r_raw)

                            # Prepare Tooltip (HTML Title Attribute - No Markdown)
                            desc = AGENT_DESC.get(agent, 'Specialized Trading Agent')
                            
                            if reasoning and reasoning.strip():
                                tooltip_text = f"{agent}: {desc}\n\n{reasoning}"
                            else:
                                tooltip_text = f"{agent}: {desc}"
                            
                            # ROBUST SANITIZATION
                            # 1. Escape quotes
                            # 2. Escape newlines for HTML attribute
                            tooltip_safe = tooltip_text.replace('&', '&amp;').replace('"', '&quot;').replace("'", '&apos;').replace('\n', '&#10;')
                            
                            st.markdown(f"""
                            <div style='display: flex; justify-content: space-between; align-items: center; background: #262730; padding: 8px 15px; border-radius: 8px; margin-bottom: 5px; border-left: 5px solid {badge_color};'>
                                <div style='display: flex; align-items: center;'>
                                    <span style='font-weight: bold; color: #ffffff;'>{agent}</span>
                                    <span title="{tooltip_safe}" style='cursor: help; margin-left: 8px; font-size: 0.8em; opacity: 0.7;'>ℹ️</span>
                                </div>
                                <span style='background: {badge_color}; padding: 2px 10px; border-radius: 12px; color: white; font-size: 0.8rem;'>
                                    Influence: {weight:.2f}x
                                </span>
                            </div>
                            """, unsafe_allow_html=True)
                    else:
                        st.caption("Awaiting meritocracy calibration...")

            st.divider()
            st.divider()
            signals_help = "Agent Signals: Individual vote signals from each agent in the Council. Influence-weighted breakdown of the decision."
            st.markdown(f"""
            <div style="display: flex; align-items: center; margin-bottom: 10px;">
                <h3 style="margin: 0; padding: 0;">🚦 Agent Signals</h3>
                <span title="{signals_help}" style="margin-left: 10px; cursor: help; font-size: 1.2rem; opacity: 0.8;">ℹ️</span>
            </div>
            """, unsafe_allow_html=True)
            if target_votes:
                # Full width layout allows for more columns
                cols = st.columns(4) 
                for idx, v in enumerate(target_votes):
                    with cols[idx % 4]:
                        typ = v.get('vote', 'hold').lower()
                        color = "#00cc96" if typ == 'buy' else "#ef553b" if typ == 'sell' else "#b0b3b8" 
                        st.markdown(f'<div style="border: 1px solid {color}; border-radius: 5px; padding: 5px; background: #262730; font-size: 0.7em; margin-bottom: 5px;"><strong style="color: #ddd;">{v.get("agent")}</strong><br><span style="color: {color}; font-size: 1.1em; font-weight: bold;">{typ.upper()}</span><br><span style="color: #aaa;">{v.get("confidence",0):.0%}</span></div>', unsafe_allow_html=True)

    
            # 3. RECENT ACTIVITY
            st.divider()
            st.subheader("📋 Recent Trades / Order Book")
            df_trades = pd.DataFrame()
            if TRADE_FILE and os.path.exists(TRADE_FILE):
                try: df_trades = pd.read_csv(TRADE_FILE)
                except: pass
            if not df_trades.empty:
                gb = GridOptionsBuilder.from_dataframe(df_trades)
                gb.configure_pagination(paginationAutoPageSize=False, paginationPageSize=10)
                gb.configure_column("Timestamp", sort="desc")
                AgGrid(df_trades, gridOptions=gb.build(), height=300, theme="balham", key=f"trade_grid_{selected_pair}")
            else:
                st.info("No active trades found in history.")
    
        # Execute fragment
        if STATUS_FILE:
            render_dashboard_content(STATUS_FILE, selected_pair)

# --- TAB: GRAPHS ---
    elif nav == NAV_GRAPHS:
        st.header(f"📈 Price Action: {selected_pair}")
        
        # --- GRAPH CONTROLS ---
        c_controls = st.container()
        c1, c2, c3 = c_controls.columns([1, 2, 2])
        
        with c1:
            auto_refresh_graph = st.checkbox("🔄 Auto-Refresh (1m)", value=False, key="gr_autorefresh")
            
        with c2:
            tf_label = st.radio("Timeframe", ["1m", "1h", "1d"], index=1, horizontal=True, key="gr_tf")
            tf_map = {"1m": "min", "1h": "h", "1d": "D"}
            freq_code = tf_map[tf_label]
            
        with c3:
            date_range_sel = st.date_input("Date Range (Optional)", [], key="gr_dates")

        # --- CHART LAYERS IMPLEMENTATION (GP3) ---
        col_chart, col_layers = st.columns([3, 1])
        
        with col_layers:
            st.markdown("### Layers")
            show_candles = st.checkbox("Price Candles (OHLC)", value=True, key="gr_show_candles")
            show_signals = st.checkbox("🤖 AI Signals (Votes)", value=True, key="gr_show_signals")
            show_execs = st.checkbox("✅ Executions (Risk Approved)", value=True, key="gr_show_execs")
            
        with col_chart:
            # Mock Data Generation for Demo (Synthetic OHLC)
            # Determine Frequency and Range
            if len(date_range_sel) == 2:
                # User selected start and end
                start_d, end_d = date_range_sel
                dates = pd.date_range(start=start_d, end=end_d, freq=freq_code)
            else:
                # Default: Last 100 periods
                dates = pd.date_range(end=datetime.now(), periods=100, freq=freq_code)
            
            # Base Price Mapping
            price_map = {
                "BTC": 45000, "ETH": 2500, "BNB": 350, "SOL": 100,
                "XRP": 0.6, "ADA": 0.5, "AVAX": 40, "DOT": 8,
                "LINK": 15, "DOGE": 0.08, "XTZ": 0.43
            }
            symbol_key = selected_pair.split('/')[0] if '/' in selected_pair else "BTC"
            base_price = price_map.get(symbol_key, 100)
            
            # Generate Random Walk Candles
            ohlc_data = []
            curr_price = base_price
            
            markers = []
            
            for i, dt in enumerate(dates):
                change = np.random.randn() * (base_price * 0.005)
                close = curr_price + change
                open_ = curr_price
                high = max(open_, close) + (np.random.random() * (base_price * 0.002))
                low = min(open_, close) - (np.random.random() * (base_price * 0.002))
                
                # Format for Lightweight Charts
                # Time must be distinct string (YYYY-MM-DD or unix timestamp)
                # Using Unix Timestamp for intraday
                t_unix = int(dt.timestamp())
                
                ohlc_data.append({
                    "time": t_unix,
                    "open": open_,
                    "high": high,
                    "low": low,
                    "close": close
                })
                
                # Generate Mock Markers
                if show_signals and i % 15 == 0:
                    sign = "buy" if np.random.random() > 0.5 else "sell"
                    color = "#2196F3" if sign == 'buy' else "#E91E63"
                    shape = "arrowUp" if sign == 'buy' else "arrowDown"
                    markers.append({
                        "time": t_unix,
                        "position": "aboveBar" if sign == 'sell' else "belowBar",
                        "color": color,
                        "shape": shape,
                        "text": f"AI {sign.upper()}"
                    })
                
                if show_execs and i % 25 == 0:
                    markers.append({
                        "time": t_unix,
                        "position": "inBar",
                        "color": "#00E676",
                        "shape": "circle",
                        "text": "EXEC"
                    })

                curr_price = close
            
            # --- RENDER TRADINGVIEW CHART ---
            chartOptions = {
                "layout": {
                    "textColor": '#d1d4dc',
                    "background": {
                        "type": 'solid',
                        "color": 'transparent'
                    }
                },
                "grid": {
                    "vertLines": {"color": "rgba(42, 46, 57, 0)"},
                    "horzLines": {"color": "rgba(42, 46, 57, 0.6)"}
                },
                "crosshair": {
                    "mode": 0
                },
                "rightPriceScale": {
                    "borderColor": "rgba(197, 203, 206, 0.8)"
                },
                "timeScale": {
                    "borderColor": "rgba(197, 203, 206, 0.8)",
                    "timeVisible": True
                }
            }
            
            series = [{
                "type": 'Candlestick',
                "data": ohlc_data,
                "options": {
                    "upColor": '#26a69a',
                    "downColor": '#ef5350',
                    "borderVisible": False,
                    "wickUpColor": '#26a69a',
                    "wickDownColor": '#ef5350'
                },
                "markers": markers 
            }]
            
            # Using key to force re-render on pair change
            renderLightweightCharts([
                {
                    "chart": chartOptions,
                    "series": series
                }
            ], key=f"tv_chart_{selected_pair}")
            
        st.divider()
        # --- CONSENSUS TIMELINE (GP3) ---
        st.subheader("🕵️ Temporal Forensics: Agent Conviction", help="A synchronized timeline showing how agent confidence evolves over time. Useful for spotting leading vs lagging indicators.")
        
        # Mock Timeline Data
        n_points = len(dates)
        try:
            df_timeline = pd.DataFrame({
                'Timestamp': dates,
                'Technical': np.sin(np.linspace(0, 10, n_points)) * 0.5 + 0.2,
                'Sentiment': np.cos(np.linspace(0, 8, n_points)) * 0.4 - 0.1,
                'On-Chain': np.random.randn(n_points).cumsum() * 0.05
            })
        except ValueError as e:
            # Fallback for length mismatch
            print(f"DEBUG: Length Mismatch. Dates: {len(dates)}, Points: {n_points}")
            df_timeline = pd.DataFrame({'Timestamp': dates})
        
        fig_timeline = px.line(df_timeline, x='Timestamp', y=['Technical', 'Sentiment', 'On-Chain'],
                              title="Agent Confidence History (-1.0 to +1.0)",
                              color_discrete_map={
                                  'Technical': '#2962ff',
                                  'Sentiment': '#9c27b0',
                                  'On-Chain': '#ff9800'
                              })
        fig_timeline.update_layout(height=300, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
                                  yaxis_title="Conviction", xaxis_title=None)
        st.plotly_chart(fig_timeline, width='stretch')
        
        st.caption("Synchronized forensic view enabled. Monitor agent lag and conviction shifts.")
        
        # Auto-Refresh Trigger
        if auto_refresh_graph:
            time.sleep(60)
            st.rerun()
    
    # --- TAB: LOGS ---
    elif nav == NAV_LOGS:
        st.header("📜 Live Terminal")
        st.subheader("System Output")
        # --- SMART LOG FILTER (GP3) ---
        col_filter, col_search = st.columns([1, 2])
        with col_filter:
            log_source = st.selectbox("Source Filter", ["All", "Risk_Manager", "AI_Council", "Meta_Strategy", "Critical_Errors"], key="log_source_filter")
        with col_search:
            log_search = st.text_input("Search Logs", "", placeholder="Enter keyword...", key="log_search_input")
    
        @st.fragment(run_every=refresh_rate)
        def render_live_logs(source, search):
            log_lines = []
            if os.path.exists(LOG_FILE):
                try:
                    with open(LOG_FILE, 'r', errors='ignore') as f:
                        f.seek(0, os.SEEK_END)
                        # Read larger chunk for filtering
                        f.seek(max(0, f.tell() - 32000)) 
                        log_lines = f.readlines()
                except: pass
                
            # --- SECRET MASKING ---
            def mask_secrets(text):
                import re
                # Mask typical API keys (long alphanumeric strings)
                # This matches strings like 'apiKey': 'xxxx...'
                patterns = [
                    (r"['\"]api[_-]?key['\"]\s*:\s*['\"]([^'\"]+)['\"]", r"'apiKey': '********'"),
                    (r"['\"]secret['\"]\s*:\s*['\"]([^'\"]+)['\"]", r"'secret': '********'"),
                    (r"['\"]TELEGRAM_BOT_TOKEN['\"]\s*:\s*['\"]([^'\"]+)['\"]", r"'TELEGRAM_BOT_TOKEN': '********'")
                ]
                for pattern, replacement in patterns:
                    text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
                return text

            # Apply Filters
            import re
            filtered = []
            source_pattern = ""
            if source == "Risk_Manager": source_pattern = r"\[RISK_MANAGER\]"
            elif source == "AI_Council": source_pattern = r"\[AI_COUNCIL\]|\[AGENT\]"
            elif source == "Meta_Strategy": source_pattern = r"\[META_STRATEGY\]"
            elif source == "Critical_Errors": source_pattern = r"ERROR|CRITICAL|EXCEPTION"
            
            for line in log_lines:
                if source_pattern and not re.search(source_pattern, line, re.IGNORECASE):
                    continue
                if search and search.lower() not in line.lower():
                    continue
                filtered.append(mask_secrets(line))
                
            # Display tail
            output = "".join(filtered[-50:])
            st.code(output if output else "No matching logs found.", language="text")
            
        render_live_logs(log_source, log_search)




except Exception as e:
    # Log and Show Error
    error_msg = f"DASHBOARD CRITICAL FAILURE: {str(e)}\n{traceback.format_exc()}"
    print(error_msg)
    with open("logs/dashboard_error.log", "w", encoding="utf-8") as f:
        f.write(error_msg)
    st.error("critical error loading dashboard. check logs/dashboard_error.log")
    st.stop()
