# 🧠 AI Training Manual: The Neural Forge

![Framework](https://img.shields.io/badge/Framework-Stable_Baselines3-blue)
![Optimization](https://img.shields.io/badge/Tuner-Optuna-orange)
![Visualization](https://img.shields.io/badge/Monitor-TensorBoard-orange)

This guide explains how to train, tune, and deploy high-performance Reinforcement Learning models for the AI Crypto Trading Bot.

---

## 🏛️ Phase 1: Hyperparameter Tuning (`tune.py`)
Before running a full training session, use the **Auto-Tuner** to find the optimal neural network settings for your target symbol.

> [!IMPORTANT]
> **Do not skip this step.** Default PPO hyperparameters are rarely optimal for volatile crypto markets.

- **Purpose**: Uses Bayesian Optimization (Optuna) to minimize loss and maximize reward.
- **Run Command**:
  ```bash
  python tune.py
  ```
- **Output**: Generates `data/best_hyperparams.json`. The `train.py` script will automatically load this file if it exists.

---

## 🏋️ Phase 2: Model Training (`train.py`)
Once you have your hyperparameters, you can launch the primary training pipeline.

```bash
python train.py --symbol BTC/USD --timesteps 100000 --n-envs 4 --walk-forward
```

> [!TIP]
> Use `--walk-forward` to enable rolling-window validation. This trains on period A and tests on period B, significantly reducing the risk of overfitting.

#### 🚩 Key CLI Arguments
| Argument | Description | Recommendation |
| :--- | :--- | :--- |
| `--symbol` | Trading pair (e.g., `BTC/USD`, `ETH/USD`). | Use `ALL TOP 10` for broad market training. |
| `--timesteps` | Total training steps. | `50,000` for testing, `500,000+` for production. |
| `--n-envs` | Number of parallel CPU cores. | Set to your CPU core count (e.g., `4` or `8`). |
| `--resume` | Loads an existing model to continue training. | Use with `--model-name`. |

---

## 📈 Phase 3: Monitoring with TensorBoard
TensorBoard provides deep insights into the AI's learning process.

> [!NOTE]
> You can view TensorBoard directly inside the Dashboard under the "AI Research Lab" tab.

**Metrics to watch:**
- **`rollout/ep_rew_mean`**: Should trend **upward**. This is the average profit per episode.
- **`train/value_loss`**: Should stabilize at a **low value**. High volatility here means the AI is confused.
- **`train/entropy_loss`**: Indicates randomness. It should **decrease** over time as the AI becomes more confident.

---

## 🚀 Phase 4: Deployment
Once training is complete, your model is saved as a `.zip` in the `models/` directory.

1. Go to the **"Bot Controller"** tab.
2. In the **"🧠 Active AI Model"** dropdown, select your new model.
3. Start the bot. The **Chartist Agent** will now use this brain to generate signals.

---

## ⚠️ Safety Protocols & Best Practices

> [!WARNING]
> **Overfitting Risk**: If your model performs perfectly in backtesting (e.g., >500% APY) but fails in live trading, it has likely memorized the noise.

*   **Generalist Training**: Training on `ALL TOP 10` creates a robust model that understands market-wide correlations.
*   **Incremental Learning**: Use `--resume` on a 1-hour model with 5-minute data to "fine-tune" the AI for lower timeframes.
*   **Paper First**: Always run a new model in **Paper Mode** for at least 48 hours before trusting it with real capital.
