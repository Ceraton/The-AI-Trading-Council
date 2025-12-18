from typing import Dict, Any
from utils.logger import setup_logger
from config import (
    MAX_DRAWDOWN_PCT, MAX_POSITION_SIZE_PCT, 
    MAX_SLIPPAGE_PCT, STOP_LOSS_PCT, TAKE_PROFIT_PCT
)
from risk.aristotle_validator import AristotleValidator

class TelosSelector:
    """
    Aristotle: 'Teleology' (Goal-Seeking Behavior).
    Determines the bot's purpose based on its life stage.
    """
    def __init__(self, initial_balance: float):
        self.initial_balance = initial_balance

    def get_telos(self, current_balance: float) -> str:
        if self.initial_balance == 0: return "ACORN"
        ratio = current_balance / self.initial_balance
        
        if ratio < 0.95:
            return "ACORN"     # Survival: Focus on capital preservation
        elif ratio < 1.15:
            return "SAPLING"   # Growth: Standard risk-taking
        else:
            return "OAK"       # Flourishing: Protect gains, lower risk

class RiskManager:
    def __init__(self, 
                 max_drawdown_pct: float = MAX_DRAWDOWN_PCT, 
                 max_position_size_pct: float = MAX_POSITION_SIZE_PCT,
                 max_slippage_pct: float = MAX_SLIPPAGE_PCT,
                 stop_loss_pct: float = STOP_LOSS_PCT,
                 take_profit_pct: float = TAKE_PROFIT_PCT):
        
        self.logger = setup_logger("RiskManager")
        self.max_drawdown_pct = max_drawdown_pct
        self.max_position_size_pct = max_position_size_pct
        self.max_slippage_pct = max_slippage_pct
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        
        self.initial_balance = None
        self.kill_switch_active = False
        self.aristotle = AristotleValidator()
        self.telos_selector = None # Initialized once balance is known

    def update_settings(self, settings: Dict[str, float]):
        """
        Dynamically updates risk parameters.
        """
        if 'MAX_DRAWDOWN_PCT' in settings:
            self.max_drawdown_pct = settings['MAX_DRAWDOWN_PCT']
        if 'MAX_POSITION_SIZE_PCT' in settings:
            self.max_position_size_pct = settings['MAX_POSITION_SIZE_PCT']
        if 'MAX_SLIPPAGE_PCT' in settings:
            self.max_slippage_pct = settings['MAX_SLIPPAGE_PCT']
        if 'STOP_LOSS_PCT' in settings:
            self.stop_loss_pct = settings['STOP_LOSS_PCT']
        if 'TAKE_PROFIT_PCT' in settings:
            self.take_profit_pct = settings['TAKE_PROFIT_PCT']
            
        self.logger.info(f"Updated Risk Settings: {settings}")

    def update_balance(self, current_balance: float):
        if self.initial_balance is None:
            self.initial_balance = current_balance
            self.telos_selector = TelosSelector(current_balance)
        
        drawdown = (self.initial_balance - current_balance) / self.initial_balance
        if drawdown >= self.max_drawdown_pct:
            self.logger.critical(f"KILL SWITCH ACTIVATED: Drawdown {drawdown:.2%} exceeds limit {self.max_drawdown_pct:.2%}")
            self.kill_switch_active = True

    def validate_trade(self, signal: Dict[str, Any], current_balance: float, current_price: float) -> bool:
        if self.kill_switch_active:
            self.logger.warning("Trade rejected: Kill Switch is ACTIVE.")
            return False

        # --- ARISTOTELIAN SYLLOGISM CHECK ---
        context = {
            'balance': current_balance,
            'max_position_size_pct': self.max_position_size_pct,
            'max_slippage_pct': self.max_slippage_pct,
            'regime': signal.get('regime', 'PEACE'),
            'volatility': signal.get('volatility', 0),
            'liquidity_impact': signal.get('liquidity_impact', 0)
        }
        
        is_rational, reason, adjusted_signal = self.aristotle.validate_trade(signal, context)
        
        if not is_rational:
            self.logger.warning(f"Trade rejected by Aristotle: {reason}")
            return False

        # Slippage Check (if signal price is available)
        signal_price = adjusted_signal.get('price')
        if signal_price:
            if not self.validate_slippage(signal_price, current_price):
                self.logger.warning(f"Trade rejected: Slippage too high. Signal: {signal_price}, Current: {current_price}")
                return False

        # Apply Teleology (Telos)
        if self.telos_selector:
            telos = self.telos_selector.get_telos(current_balance)
            self.logger.info(f"Current Telos: {telos}")
            if telos == "ACORN" and signal.get('confidence', 0) < 0.7:
                 self.logger.warning("ACORN STAGE: Rejecting trade due to low confidence for capital preservation.")
                 return False

        return True

    def validate_slippage(self, expected_price: float, current_price: float) -> bool:
        """
        Checks if the price has moved unfavorably beyond the max slippage percentage.
        """
        if expected_price == 0: return True
        
        diff_pct = abs(current_price - expected_price) / expected_price
        if diff_pct > self.max_slippage_pct:
            return False
        return True

    def calculate_position_size(self, current_balance: float, price: float, win_rate: float = 0.55, win_loss_ratio: float = 1.5, order_book: Dict = None, side: str = 'buy') -> float:
        """
        The 'Golden Mean' Sizer.
        Calculates position size using Kelly Criterion and adjusts for Liquidity.
        """
        if price <= 0: return 0.0
        
        # Aristotelian Adjustment: Adjust win_rate based on Telos
        telos = self.telos_selector.get_telos(current_balance) if self.telos_selector else "SAPLING"
        if telos == "ACORN":
            win_rate *= 0.9 # Be more pessimistic
        elif telos == "OAK":
            win_rate *= 0.95 # Protect the oak

        kelly_pct = self._calculate_kelly_fraction(win_rate, win_loss_ratio)
        
        # Safety: Apply fractional Kelly (e.g., Half-Kelly) to reduce volatility
        safe_kelly = kelly_pct * 0.5 
        
        # Cap at max_position_size_pct (Risk Rule)
        final_pct = min(safe_kelly, self.max_position_size_pct)
        # Ensure non-negative
        final_pct = max(0.0, final_pct)
        
        amount_to_risk = current_balance * final_pct
        base_amount = amount_to_risk / price

        # Expansion 6: Liquidity Adjustment
        if order_book:
            return self.adjust_for_liquidity(base_amount, order_book, side)
        
        return base_amount

    def adjust_for_liquidity(self, amount: float, order_book: Dict, side: str) -> float:
        """
        Downscales position size if the estimated slippage exceeds MAX_SLIPPAGE_PCT.
        """
        if amount <= 0: return 0.0
        
        levels = order_book['asks'] if side == 'buy' else order_book['bids']
        if not levels: return 0.0
        
        base_price = levels[0][0]
        max_allowed_impact = self.max_slippage_pct
        
        # Iterative downscaling (simplified)
        current_amount = amount
        for _ in range(5): # Max 5 attempts to find a safe size
            # Calculate impact for current_amount
            total_cost = 0.0
            rem = current_amount
            for p, v in levels:
                f = min(rem, v)
                total_cost += f * p
                rem -= f
                if rem <= 0: break
            
            avg_p = total_cost / (current_amount - rem) if (current_amount - rem) > 0 else base_price
            impact = abs(avg_p - base_price) / base_price
            
            if impact <= max_allowed_impact and rem <= 0:
                return current_amount
            
            # Reduce by 20% and try again
            current_amount *= 0.8
            
        return current_amount

    def _calculate_kelly_fraction(self, win_rate: float, win_loss_ratio: float) -> float:
        if win_loss_ratio == 0: return 0.0
        # Kelly Formula
        return win_rate - ((1 - win_rate) / win_loss_ratio)

    def check_exit_conditions(self, current_price: float, entry_price: float, side: str) -> str:
        """
        Checks if Stop-Loss or Take-Profit levels are hit.
        Returns: 'stop_loss', 'take_profit', or None
        """
        if side == 'buy':
            pct_change = (current_price - entry_price) / entry_price
            
            if pct_change <= -self.stop_loss_pct:
                return 'stop_loss'
            if pct_change >= self.take_profit_pct:
                return 'take_profit'
                
        elif side == 'sell': # Shorting (Future proofing)
            pct_change = (entry_price - current_price) / entry_price
            
            if pct_change <= -self.stop_loss_pct:
                return 'stop_loss'
            if pct_change >= self.take_profit_pct:
                return 'take_profit'
                
        return None
