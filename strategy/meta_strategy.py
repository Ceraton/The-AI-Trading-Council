from .base_strategy import BaseStrategy
from .bollinger_strategy import BollingerStrategy
from .technical_sub_agents import TrendAgent, OscillatorAgent, VolumeAgent
from .analyst_agent import AnalystAgent
from .onchain_agent import OnChainAgent
from .chronos_agent import ChronosAgent
from .timegpt_agent import TimeGPTAgent
from typing import Dict, Any, Optional, List
from utils.logger import setup_logger
import json
import os
from datetime import datetime

AGENT_PERF_FILE = os.path.join("data", "agent_perf.json")

class MetaStrategy(BaseStrategy):
    """
    Meta-Strategy - The "Supreme Court" of the Council of AIs
    
    Coordinates multiple specialized agents and implements voting logic.
    Each agent votes (buy/sell/hold) and the meta-strategy decides final action.
    
    Voting Mechanisms:
    1. Majority Vote - Simple majority wins
    2. Weighted Vote - Agents weighted by historical accuracy
    3. Veto System - Any agent can veto with high confidence
    4. Confidence Threshold - Only execute if consensus confidence > threshold
    """
    
    def __init__(self, agents: List[BaseStrategy], voting_method: str = 'weighted'):
        super().__init__("MetaStrategy")
        self.logger = setup_logger(self.name)
        self.agents = agents
        self.voting_method = voting_method
        
        # Track agent performance for weighted voting
        self.agent_weights = {agent.name: 1.0 for agent in agents}
        self.min_confidence = 0.6  # Minimum consensus confidence to execute
        
        # Meritocracy Implementation
        self._load_weights()
        self.vote_history = [] # For Shadow Tracking
        self.shadow_depth = 5   # Number of candles to wait before evaluation
        
        # Regime Detection Implementation (Martial Law)
        self.price_history = []
        self.regime_window = 14
        self.volatility_threshold = 0.015 # 1.5% volatility = Wartime
        self.current_regime = "PEACE"
        
        self.logger.info(f"Initialized MetaStrategy with {len(agents)} agents: {[a.name for a in agents]}")

    def _load_weights(self):
        """Loads weights from persistent storage."""
        if os.path.exists(AGENT_PERF_FILE):
            try:
                with open(AGENT_PERF_FILE, 'r') as f:
                    saved_data = json.load(f)
                    for agent_name, weight in saved_data.get('weights', {}).items():
                        if agent_name in self.agent_weights:
                            self.agent_weights[agent_name] = weight
                self.logger.info(f"Loaded persistent agent weights from {AGENT_PERF_FILE}")
            except Exception as e:
                self.logger.error(f"Failed to load weights: {e}")

    def _save_weights(self):
        """Saves current weights to persistent storage."""
        try:
            os.makedirs("data", exist_ok=True)
            data = {
                'timestamp': datetime.now().isoformat(),
                'weights': self.agent_weights
            }
            with open(AGENT_PERF_FILE, 'w') as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            self.logger.error(f"Failed to save weights: {e}")
    
    async def on_tick(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return None
    
    async def on_candle(self, candle: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Collects votes from all agents and makes final decision.
        """
        # --- SHADOW TRACKING: Evaluation ---
        current_price = candle['close']
        self._evaluate_shadow_votes(current_price)
        
        # --- REGIME DETECTION ---
        self.price_history.append(current_price)
        if len(self.price_history) > self.regime_window:
            self.price_history.pop(0)
        self._detect_regime()

        # Collect votes from all agents
        votes = []
        for agent in self.agents:
            try:
                signal = await agent.on_candle(candle)
                if signal:
                    vote_entry = {
                        'agent': agent.name,
                        'vote': signal.get('vote', signal.get('side', 'hold')),
                        'confidence': signal.get('confidence', 0.5),
                        'strategy': signal.get('strategy'),
                        'price': signal.get('price'),
                        'reasoning': signal.get('reasoning', {})
                    }
                    votes.append(vote_entry)
            except Exception as e:
                self.logger.error(f"Agent {agent.name} failed: {e}")
        
        if not votes:
            return None
            
        # --- SHADOW TRACKING: Recording ---
        # We record EVERY vote to evaluate it later, regardless of if we trade.
        self.vote_history.append({
            'timestamp': candle.get('timestamp', datetime.now().timestamp()),
            'price_at_vote': current_price,
            'votes': votes,
            'ttl': self.shadow_depth
        })
        
        # Apply voting mechanism
        decision = self._apply_voting(votes, candle)
        
        if decision:
            self.logger.info(f"Council Decision: {decision['side'].upper()} "
                           f"(Confidence: {decision['confidence']:.2f}, "
                           f"Votes: {decision['vote_breakdown']})")
        
        return decision

    def _evaluate_shadow_votes(self, current_price: float):
        """Processes shadow history to update agent merits."""
        remaining_history = []
        for entry in self.vote_history:
            entry['ttl'] -= 1
            if entry['ttl'] <= 0:
                # Evaluate!
                price_then = entry['price_at_vote']
                price_change_pct = (current_price - price_then) / price_then
                
                for v in entry['votes']:
                    agent_name = v['agent']
                    vote = v['vote']
                    
                    # Score logic
                    success = False
                    if vote == 'buy' and price_change_pct > 0.002: success = True
                    elif vote == 'sell' and price_change_pct < -0.002: success = True
                    elif vote == 'hold' and abs(price_change_pct) < 0.002: success = True
                    
                    score = 1.0 if success else 0.0
                    self.update_agent_weight(agent_name, score) # EMA update
                
                # After updating weights, persist
                self._save_weights()
            else:
                remaining_history.append(entry)
        
        self.vote_history = remaining_history
    
    def _apply_voting(self, votes: List[Dict], candle: Dict) -> Optional[Dict[str, Any]]:
        """
        Applies the selected voting mechanism, adjusted for regime.
        """
        # ADJUSTMENT FOR MARTIAL LAW
        if self.current_regime == "WAR":
            # Wartime: We override and use something stricter
            # e.g., only execute if we have high consensus
            old_threshold = self.min_confidence
            self.min_confidence = 0.8 # Tighten requirements
            result = self._weighted_vote(votes, candle)
            self.min_confidence = old_threshold # Reset
            
            if result:
                 result['regime'] = "WAR"
                 self.logger.warning(f"MARTIAL LAW TRADE: Consensus reached in high vol condition.")
            return result

        if self.voting_method == 'majority':
            return self._majority_vote(votes, candle)
        elif self.voting_method == 'weighted':
            return self._weighted_vote(votes, candle)
        elif self.voting_method == 'veto':
            return self._veto_vote(votes, candle)
        else:
            return self._weighted_vote(votes, candle)  # Default

    def _detect_regime(self):
        """Calculates volatility and sets PEACETIME or MARTIAL LAW status."""
        if len(self.price_history) < self.regime_window:
            return

        # Calculate standard deviation as a proxy for volatility
        import numpy as np
        prices = np.array(self.price_history)
        volatility = np.std(prices) / np.mean(prices)
        
        if volatility > self.volatility_threshold:
            if self.current_regime != "WAR":
                self.logger.warning(f"🚨 REGIME SHIFT: Entering MARTIAL LAW (Vol: {volatility:.2%})")
                self.current_regime = "WAR"
        else:
            if self.current_regime == "WAR":
                self.logger.info(f"🕊️ REGIME SHIFT: Returning to PEACETIME (Vol: {volatility:.2%})")
                self.current_regime = "PEACE"
    
    def _majority_vote(self, votes: List[Dict], candle: Dict) -> Optional[Dict[str, Any]]:
        """
        Simple majority wins. Ties default to HOLD.
        """
        vote_counts = {'buy': 0, 'sell': 0, 'hold': 0}
        
        for vote in votes:
            vote_counts[vote['vote']] += 1
        
        # Find winner
        winner = max(vote_counts, key=vote_counts.get)
        
        # Calculate average confidence
        avg_confidence = sum(v['confidence'] for v in votes) / len(votes)
        
        # Only execute if confidence meets threshold
        if winner == 'hold' or avg_confidence < self.min_confidence:
            return None
        
        return {
            'side': winner,
            'price': candle['close'],
            'confidence': avg_confidence,
            'vote_breakdown': vote_counts,
            'voting_method': 'majority',
            'agent_votes': votes,
            'strategy': next((v.get('strategy') for v in votes if v['vote'] == winner and v.get('strategy')), None)
        }
    
    def _weighted_vote(self, votes: List[Dict], candle: Dict) -> Optional[Dict[str, Any]]:
        """
        Weighted vote based on agent historical performance.
        """
        weighted_scores = {'buy': 0.0, 'sell': 0.0, 'hold': 0.0}
        
        for vote in votes:
            agent_name = vote['agent']
            weight = self.agent_weights.get(agent_name, 1.0)
            confidence = vote['confidence']
            
            # Score = weight * confidence
            weighted_scores[vote['vote']] += weight * confidence
        
        # Find winner
        winner = max(weighted_scores, key=weighted_scores.get)
        total_weight = sum(weighted_scores.values())
        
        # Normalize confidence
        winner_confidence = weighted_scores[winner] / total_weight if total_weight > 0 else 0
        
        # Only execute if confidence meets threshold
        if winner == 'hold' or winner_confidence < self.min_confidence:
            return None
        
        return {
            'side': winner,
            'price': candle['close'],
            'confidence': winner_confidence,
            'vote_breakdown': {k: round(v, 2) for k, v in weighted_scores.items()},
            'voting_method': 'weighted',
            'agent_votes': votes,
            'strategy': next((v.get('strategy') for v in votes if v['vote'] == winner and v.get('strategy')), None)
        }
    
    def _veto_vote(self, votes: List[Dict], candle: Dict) -> Optional[Dict[str, Any]]:
        """
        Any agent with high confidence (>0.8) can veto.
        Otherwise, uses weighted voting.
        """
        # Check for vetos
        for vote in votes:
            if vote['confidence'] > 0.8 and vote['vote'] == 'hold':
                self.logger.warning(f"VETO by {vote['agent']} (confidence: {vote['confidence']})")
                return None
        
        # No veto - proceed with weighted vote
        return self._weighted_vote(votes, candle)
    
    def update_agent_weight(self, agent_name: str, performance_score: float):
        """
        Updates agent weight based on performance.
        
        Performance score: 0.0 (worst) to 1.0 (best)
        """
        # Exponential moving average
        alpha = 0.3
        current_weight = self.agent_weights.get(agent_name, 1.0)
        new_weight = alpha * performance_score + (1 - alpha) * current_weight
        
        self.agent_weights[agent_name] = max(0.1, min(2.0, new_weight))  # Clamp to [0.1, 2.0]
        
        self.logger.info(f"Updated {agent_name} weight: {new_weight:.2f}")
