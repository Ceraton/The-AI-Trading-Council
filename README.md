# 🤖 AI Crypto Trading Bot (Council of AIs Edition)

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-App-FF4B4B)
![Reinforcement Learning](https://img.shields.io/badge/AI-Reinforcement%20Learning-green)
![License](https://img.shields.io/badge/License-MIT-purple)
![Status](https://img.shields.io/badge/Status-Active-success)

**[📖 Architecture](ARCHITECTURE.md)** | **[🧠 AI Training](AI_TRAINING.md)** | **[🗺️ Roadmap](ROADMAP.md)** | **[📜 License](LICENSE.md)**

---

A sophisticated multi-agent algorithmic trading system that combines Reinforcement Learning, Sentiment Analysis, and On-Chain data. The system features a **"Supreme Court"** architecture where specialized AI agents vote on trade execution, overseen by a dynamic **Meritocracy** and **Risk Management** layer.

## 🌟 Key Features

### 🧠 The Council of AIs (Phase 2 Upgrades)
*   **Chartist Agent (ML)**: Core brain using PPO (Reinforcement Learning) models.
*   **Fractal Council**: Specialized technical sub-agents (**Trend, Oscillator, Volume**) for granular signal validation.
*   **Persistent Meritocracy**: Dynamic weighting system that rewards profitable agents and demotes underperformers.
*   **Martial Law (Regime Detection)**: Automatically tightens consensus requirements during high-volatility crashes.
*   **LLM Reasoning**: Synthesized logic summaries explaining the council's decision-making process.

### 🧪 Neural Forge (Training Pipeline Phase 3)
*   **Auto-Tuner (Optuna)**: Bayesian hyperparameter optimization for institutional-grade models.
*   **Time-Traveler (Walk-Forward)**: Rolling-window validation to prevent overfitting.
*   **Speed Demon**: Multi-core training via `SubprocVecEnv`.
*   **TensorBoard Integration**: Live visualization of training metrics and policy convergence.

### 📊 Advanced 'Cockpit' Dashboard
*   **AI Research Lab**: Manage training sessions, tune hyperparameters, and monitor TensorBoard directly.
*   **Active Model Selector**: Hot-swap between different trained `.zip` models in the Bot Controller.
*   **Market Constitution Badge**: Visual indicator of current market regime (Peace vs. Martial Law).
*   **Agent Merit Scorecard**: Live display of current agent influence and performance.

---

## 🚀 Installation

1.  **Clone the Repository**:
    ```bash
    git clone <repository-url>
    cd AI-Crypto-Trading-Bot
    ```

2.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Environment Configuration**:
    Create a `.env` file in the root directory with your Exchange Keys (API/Secret) and optional Web3 Provider URI.

---

## 🕹️ Usage

### 1. Training & Tuning
Before trading, you can train a model in the **AI Research Lab** tab or via CLI:
*   **Hyperparameter Tuning**: `python scripts/tune.py`
*   **Train Model**: `python train.py --symbol BTC/USD --timesteps 100000`

### 2. Run the Trading Bot
*   **Paper Trading**: `python main.py --paper --council`
*   **Live Trading**: `python main.py --council`
*   **Selective Model**: `python main.py --council --model-name ppo_model_latest`

### 3. Launch the Dashboard
```bash
streamlit run dashboard.py
```

---

## 📂 Project Structure

*   `main.py`: Entry point and agent coordinator.
*   `train.py`: Model training pipeline.
*   `dashboard.py`: Streamlit-based UI for monitoring and control.
*   `strategy/`: Contains **The Council** and **Meta-Strategy** logic.
*   `ml/`: RL environment and agent configurations.
*   `models/`: Saved `.zip` brains.
*   `data/`: Persistent performance logs and exchange wrappers.
*   `scripts/`: Helper tools (Tuner, Benchmarks, Verification).
*   `tests/`: Unit and integration tests.

---

## ⚠️ Disclaimer
> [!WARNING]
> **This software is a volatile experimental project.**
> Cryptocurrency trading involves significant risk. The authors are not responsible for financial losses.
