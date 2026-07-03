from typing import Optional, Tuple

# Flags
DECLINE_TO_LOSS = "DECLINE_TO_LOSS"
TURNAROUND = "TURNAROUND"
BOTH_NEGATIVE = "BOTH_NEGATIVE"
ZERO_BASE = "ZERO_BASE"
INSUFFICIENT = "INSUFFICIENT"
NORMAL = "NORMAL"

def compute_cagr(start_val: float, end_val: float, years: int) -> Tuple[Optional[float], str]:
    """
    Computes the Compound Annual Growth Rate (CAGR) and returns a flag.
    Formula: ((end/start)^(1/n) - 1) * 100
    
    Returns:
        A tuple of (CAGR value, Flag)
    """
    if years <= 0:
        return None, INSUFFICIENT
    
    if start_val == 0:
        return None, ZERO_BASE
        
    if start_val > 0 and end_val > 0:
        cagr = ((end_val / start_val) ** (1 / years) - 1) * 100
        return cagr, NORMAL
        
    if start_val > 0 and end_val <= 0:
        return None, DECLINE_TO_LOSS
        
    if start_val < 0 and end_val > 0:
        return None, TURNAROUND
        
    if start_val < 0 and end_val <= 0:
        return None, BOTH_NEGATIVE
        
    return None, INSUFFICIENT
