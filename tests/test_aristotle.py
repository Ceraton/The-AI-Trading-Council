import unittest
import sys
import os

# Ensure project root is in path
sys.path.append(os.getcwd())

from risk.risk_manager import RiskManager
from risk.aristotle_validator import AristotleValidator

class TestAristotle(unittest.TestCase):
    def setUp(self):
        # Reset defaults for predictability
        self.rm = RiskManager(
            max_position_size_pct=0.05,
            max_slippage_pct=0.02,
            max_drawdown_pct=0.30 # Increased to avoid kill switch during drawdown tests
        )
        self.rm.update_balance(10000.0) # Initial Balance
        
    def test_rashness_adjustment(self):
        """Test that Aristotle reduces position size to the Golden Mean."""
        signal = {'side': 'buy', 'size_pct': 0.10, 'confidence': 0.9}
        context = {
            'max_position_size_pct': 0.05,
            'regime': 'PEACE',
            'volatility': 0.001
        }
        is_rational, reason, adjusted = self.rm.aristotle.validate_trade(signal, context)
        
        self.assertTrue(is_rational)
        self.assertEqual(adjusted['size_pct'], 0.05)
        self.assertIn("Rashness", reason)

    def test_wartime_consensus_rejection(self):
        """Test that high volatility (WAR) requires higher confidence."""
        # Low confidence signal in WAR regime
        signal = {'side': 'buy', 'confidence': 0.6, 'regime': 'WAR'}
        is_valid = self.rm.validate_trade(signal, 10000.0, 50000.0)
        self.assertFalse(is_valid)
        
        # High confidence signal in WAR regime
        signal_v2 = {'side': 'buy', 'confidence': 0.85, 'regime': 'WAR'}
        is_valid_v2 = self.rm.validate_trade(signal_v2, 10000.0, 50000.0)
        self.assertTrue(is_valid_v2)

    def test_teleology_acorn_preservation(self):
        """Test that 'Acorn' stage (drawdown) triggers stricter capital preservation."""
        self.rm.update_balance(9000.0) # 10% drawdown -> ACORN
        
        # Low confidence trade rejected in ACORN
        signal = {'side': 'buy', 'confidence': 0.6}
        is_valid = self.rm.validate_trade(signal, 9000.0, 50000.0)
        self.assertFalse(is_valid)
        
        # High confidence trade allowed in ACORN
        signal_v2 = {'side': 'buy', 'confidence': 0.75}
        is_valid_v2 = self.rm.validate_trade(signal_v2, 9000.0, 50000.0)
        self.assertTrue(is_valid_v2)

    def test_vice_of_deficiency(self):
        """Test liquidity rejection."""
        signal = {'side': 'buy', 'confidence': 0.9}
        # Signal with high liquidity impact (3%) > limit (2%)
        signal['liquidity_impact'] = 0.03
        
        is_valid = self.rm.validate_trade(signal, 10000.0, 50000.0)
        self.assertFalse(is_valid)

if __name__ == '__main__':
    unittest.main()
