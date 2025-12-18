from typing import Dict, Any, Tuple
from utils.logger import setup_logger

class AristotleValidator:
    """
    Aristotle: 'The Syllogistic Validator'.
    Acts as the 'Rational Conscience' of the bot. 
    While the AI (Plato/Socrates) relies on probabilities, this Validator relies on immutable laws.
    If a trade violates these laws, it is rejected or adjusted instantly.
    """
    def __init__(self):
        self.logger = setup_logger("AristotleValidator")

    def validate_trade(self, signal: Dict[str, Any], context: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Applies Aristotelian Syllogistic Logic to a trade.
        
        Syllogism Example:
        - Premise 1 (Major): No trade shall exceed 5% risk of total equity.
        - Premise 2 (Minor): The proposed trade has a Stop Loss distance of 10%.
        - Conclusion: Therefore, the position size must be halved.
        
        Returns: (is_valid, reason, adjusted_signal)
        """
        adjusted_signal = signal.copy()
        warnings = []
        
        # --- 1. THE MAJOR PREMISE: Risk Thresholds ---
        max_risk_pct = context.get('max_position_size_pct', 0.05)
        proposed_size_pct = signal.get('size_pct', 0.1) # Default to 10% if not specified
        
        # --- 2. THE MINOR PREMISE: Specific Trade Risk ---
        # If the size is too large, we don't just reject, we find the 'Golden Mean'.
        if proposed_size_pct > max_risk_pct:
            adjusted_size = max_risk_pct
            msg = f"Vice of Excess (Rashness) detected. Adjusting size from {proposed_size_pct:.2%} to {adjusted_size:.2%}"
            self.logger.warning(f"🏛️ ARISTOTLE: {msg}")
            warnings.append(msg)
            adjusted_signal['size_pct'] = adjusted_size
        
        # --- 3. VOLATILITY PREMISE (The Vice of Excess) ---
        volatility = context.get('volatility', 0)
        vol_threshold = context.get('volatility_threshold', 0.015) # 1.5% volatility = Wartime/Excess
        regime = context.get('regime', 'PEACE')
        
        if regime == 'WAR' and signal.get('confidence', 0) < 0.8:
            # EXCEPTION: Knife Catching requires Courage
            if signal.get('strategy') == 'Knife Catch':
                 if proposed_size_pct <= 0.005: # Virtue of Temperance (Small Size)
                     self.logger.info("🏛️ ARISTOTLE: Virtue of Courage: Allowing high-volatility trade due to Temperance (Size <= 0.5%).")
                 else:
                     return False, "Vice of Excess: Knife Catching requires Small Size (<0.5%) during extreme volatility.", adjusted_signal
            else:
                return False, "Vice of Excess: Extreme volatility requires High Confidence Consensus (>0.8).", adjusted_signal

        # --- 4. LIQUIDITY PREMISE (The Vice of Deficiency) ---
        liquidity_impact = context.get('liquidity_impact', 0)
        max_slippage = context.get('max_slippage_pct', 0.02)
        
        if liquidity_impact > max_slippage:
             # If liquidity is dead, it's a deficiency of opportunity
             return False, f"Vice of Deficiency: Liquidity impact ({liquidity_impact:.2%}) exceeds rational limits.", adjusted_signal

        final_reason = "The Golden Mean: Trade follows rational logic."
        if warnings:
            final_reason += " Warnings: " + "; ".join(warnings)

        return True, final_reason, adjusted_signal

    def get_philosophical_error(self, code: str) -> str:
        """Translates technical errors into Aristotelian wisdom."""
        mappings = {
            "RISK_EXCEEDED": "Vice of Excess: You seek the rewards of the gods without the humility of a mortal.",
            "NO_LIQUIDITY": "Vice of Deficiency: Even the swiftest ship cannot sail in a dried-up harbor.",
            "HIGH_VOLATILITY": "Vice of Excess: The storm is too fierce; for now, the cave is our temple.",
            "LOW_CONFIDENCE": "Socratic Ignorance: To trade without certainty is to claim knowledge where none exists."
        }
        return mappings.get(code, "Reason has failed to find a path.")
