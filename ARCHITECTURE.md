# 🏗️ System Architecture

This document details the internal design of the AI Crypto Trading Bot.

## 🏛️ High-Level Design

The system operates on a **Multi-Agent Consensus Model**. Instead of a single algorithm deciding trades, a "Council" of specialized agents proposes actions, and a "Meta-Strategy" aggregates these votes.

```mermaid
graph TD
    Data[Market Data / APIs] --> Chartist[Chartist Agent (ML / PPO)]
    Data --> Analyst[Analyst Agent (Sentiment)]
    Data --> OnChain[On-Chain Agent (Whale activity)]
    
    subgraph Fractal Council
        Trend[Trend Agent]
        Osc[Oscillator Agent]
        Vol[Volume Agent]
    end
    
    Chartist -->|Vote| Meta[Meta-Strategy (Supreme Court)]
    Analyst -->|Vote + Veto| Meta
    OnChain -->|Vote + Veto| Meta
    Trend -->|Vote| Meta
    Osc -->|Vote| Meta
    Vol -->|Vote| Meta
    
    Meta -->|Dynamic Weights| Merit[Meritocracy Layer]
    Merit -->|Weighted Consensus| LLM[LLM Reasoning Clerk]
    LLM -->|Final Signal| Risk[Risk Manager]
    
    Risk -->|Approved Order| Executor[Order Executor]
    Executor -->|API Call| Exchange[(Exchange)]
```

---

## 🧩 Core Components

### 1. The Council (Agents)
Located in `strategy/`.
*   **Chartist Agent (ML)**: The primary neural brain. Uses a PPO (Reinforcement Learning) model trained on multi-symbol price action.
*   **Fractal Council (Technical Sub-Agents)**: 
    *   **Trend Agent**: Focuses on EMA/MACD momentum.
    *   **Oscillator Agent**: Focuses on RSI mean reversion.
    *   **Volume Agent**: Focuses on Price/Volume confirmation.
*   **Analyst Agent**: Scrapes RSS feeds and uses VADER sentiment analysis. Provides a "Veto" if sentiment prevents a technical buy.
*   **On-Chain Agent**: Monitors blockchain RPCs for large token transfers and whale movements.

### 2. Meta-Strategy (The Supreme Court)
Located in `strategy/meta_strategy.py`.
*   **Persistent Meritocracy**: Tracks agent performance in `data/agent_perf.json`. Successes increase an agent's "Merit" weight (up to 2.0x), while failures reduce it (down to 0.1x). 
*   **Martial Law Protocol (Regime Detection)**: Automatically senses market volatility (ATR).
    *   *Peacetime*: Normal weighted voting.
    *   *Martial Law*: Requirement for consensus tightens significantly to prevent "Whipsaw" losses during crashes.
*   **LLM Reasoning Clerk**: Synthesizes the deliberation of all agents into a human-readable summary, explaining the logic behind every signal.

### 3. Risk Manager
Located in `risk/risk_manager.py`.
*   The final gatekeeper before execution.
*   **Functions**:
    *   Calculates Position Size (Kelly Criterion or % of Portfolio).
    *   Checks Daily Max Loss.
    *   Ensures Balance sufficiency.

### 4. Data Layer
Located in `data/`.
*   **ExchangeClient**: Wrapper around `ccxt` for uniform API access (Kraken, Coinbase).
*   **DataStorage**: Manages CSV logging for backtesting and analytics.
*   **BlockchainMonitor**: `web3.py` interface for raw blockchain data.

---

## 🖥️ 'Cockpit' Dashboard Interface (`dashboard.py`)

The user interface has been refactored into a modular **Tab-Based System** to separate concerns and improve usability.

| Tab | Functionality |
| :--- | :--- |
| **Dashboard** | Main HUD with **Market Constitution** (Regime) and **Agent Merit Scorecard**. |
| **Graphs** | Multi-layer charts with AI Signals (Robot Heads) and execution points. |
| **🧠 AI Research Lab** | The "Neural Forge": Launch training sessions, run Bayesian Tuning, and monitor live TensorBoard graphs. |
| **Live Logs** | Filterable streaming logs with source category detection. |
| **Bot Controller** | Operational controls, **Active Model Selector** (pick any .zip brain), and Panic controls. |
| **Options** | Dynamic HITL tuning for risk limits and exchange connectivity. |

### Inter-Process Communication (IPC)
The Dashboard serves as a "Read-Only" monitor that can issue asynchronous commands. It does **not** run the trading loop.

1.  **Bot -> Dashboard** (Status Files):
    *   `live_status_v2.json`: Active Live Bot state.
    *   `paper_status_v2.json`: Paper Trading simulation state.
    *   *Updates every loop (~10s).*

2.  **Dashboard -> Bot** (Command Injection):
    *   `data/commands.json`: Queue for manual overrides (e.g., `PANIC_SELL_ALL`).
    *   `bot_pid.txt`: Tracks the active Bot Process ID for lifecycle management.

---

## 🧪 Paper Trading Engine (Simulation)

A high-fidelity simulation environment wraps the execution layer to mimic real-world conditions without risking capital.

*   **Virtual Wallet**: Managed by `execution/paper_wallet.py` (persisted to `paper_wallet.json`).
*   **Latency Simulation**: Random 50ms - 200ms delay injected before order confirmation (`execution/order_executor.py`).
*   **Cost Modeling**:
    *   **Slippage**: +/- 0.1% (configurable) impact on execution price.
    *   **Fees**: 0.1% (configurable) Maker/Taker fee deduction.

---

## 📁 Directory Structure Details

| Directory | Description |
| :--- | :--- |
| `backtesting/` | (Legacy) Old backtesting scripts. |
| `data/` | API wrappers, command queues, and IPC status files. |
| `execution/` | **Order Executor** (Live & Paper) and **Paper Wallet** logic. |
| `logs/` | Runtime logs (`bot.log`, `paper.log`) & Training metrics. |
| `ml/` | AI Model configurations (PPO/A2C) and Environment wrappers. |
| `models/` | Serialized model weights (`.zip`, `.h5`). |
| `risk/` | Risk management logic (Kelly Criterion, Drawdown limits). |
| `strategy/` | **The Council**: Individual Agent logic (Chartist, Sentiment, On-Chain) and Meta-Strategy. |
| `utils/` | Shared libraries (Logger, Math, Helpers). |
