from typing import List, Optional
from utils.logger import setup_logger

class EmpiricalObserver:
    """
    Aristotle: 'The Empirical Observer'.
    Compares the Model's 'Expected Accuracy' (Training) vs. 'Actual Accuracy' (Live).
    Aristotle lives in the present. If the Live Market (Reality) disagrees with the Model (Theory), 
    Aristotle overrides the Model or triggers recalibration.
    """
    def __init__(self, expected_accuracy: float = 0.55):
        self.logger = setup_logger("EmpiricalObserver")
        self.expected_accuracy = expected_accuracy
        self.trade_outcomes: List[bool] = []
        self.window_size = 10 # Last 10 trades as per Socrates.txt

    def record_outcome(self, profit: float):
        """Records if a trade was successful (profitable) or not."""
        success = profit > 0
        self.trade_outcomes.append(success)
        if len(self.trade_outcomes) > self.window_size:
            self.trade_outcomes.pop(0)
            
        self._check_calibration()

    def _check_calibration(self):
        """
        If 'Actual' drops 20% below 'Expected,' Aristotle declares the model 'Theoretically Flawed'.
        """
        if len(self.trade_outcomes) < self.window_size:
            return

        actual_accuracy = sum(self.trade_outcomes) / len(self.trade_outcomes)
        threshold = self.expected_accuracy * 0.8
        
        if actual_accuracy < threshold:
            self.logger.critical(
                f"🏛️ ARISTOTLE: THEORETICALLY FLAWED! "
                f"Reality ({actual_accuracy:.2%}) has diverged from Theory ({self.expected_accuracy:.2%}). "
                f"Recalibration is mandatory."
            )
            # In a full system, this might set a 'recalibrate' flag in bot_status.json
            return False
        
        self.logger.info(f"🏛️ EMPIRICISM: Model performance {actual_accuracy:.2%} is within rational bounds.")
        return True

    def get_status(self) -> str:
        if not self.trade_outcomes:
            return "Awaiting observations."
        acc = sum(self.trade_outcomes) / len(self.trade_outcomes)
        return f"Actual Accuracy: {acc:.2%} (Target: >{self.expected_accuracy*0.8:.2%})"
