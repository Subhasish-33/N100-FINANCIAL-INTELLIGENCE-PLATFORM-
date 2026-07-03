from typing import Optional, Tuple, List

def compute_fcf(operating_activity: float, investing_activity: float) -> float:
    """
    Computes Free Cash Flow (FCF).
    Formula: operating_activity + investing_activity (investing is usually negative)
    """
    return operating_activity + investing_activity

def compute_cfo_quality_score(cfo_list: List[float], pat_list: List[float]) -> Optional[str]:
    """
    Computes CFO Quality Score based on the average CFO/PAT ratio over a period (e.g. 5 years).
    Uses sum(cfo)/sum(pat) to avoid division by zero in individual years.
    >1.0 = High Quality
    0.5-1.0 = Moderate
    <0.5 = Accrual Risk
    """
    total_pat = sum(pat_list)
    total_cfo = sum(cfo_list)
    
    if total_pat == 0:
        return None
        
    ratio = total_cfo / total_pat
    if ratio > 1.0:
        return "High Quality"
    elif ratio >= 0.5:
        return "Moderate"
    else:
        return "Accrual Risk"

def compute_capex_intensity(investing_activity: float, sales: float) -> Optional[Tuple[float, str]]:
    """
    Computes CapEx Intensity: abs(investing_activity) / sales * 100
    <3% = Asset Light
    3-8% = Moderate
    >8% = Capital Intensive
    """
    if sales == 0:
        return None
        
    intensity = (abs(investing_activity) / sales) * 100
    if intensity < 3.0:
        return intensity, "Asset Light"
    elif intensity <= 8.0:
        return intensity, "Moderate"
    else:
        return intensity, "Capital Intensive"

def compute_fcf_conversion_rate(fcf: float, operating_profit: float) -> Optional[float]:
    """
    FCF / operating_profit x 100
    """
    if operating_profit == 0:
        return None
    return (fcf / operating_profit) * 100

def classify_capital_allocation(cfo: float, cfi: float, cff: float, cfo_quality: Optional[str] = None) -> str:
    """
    Classifies capital allocation based on the signs of CFO, CFI, and CFF.
    """
    cfo_sign = '+' if cfo >= 0 else '-'
    cfi_sign = '+' if cfi >= 0 else '-'
    cff_sign = '+' if cff >= 0 else '-'
    
    pattern = (cfo_sign, cfi_sign, cff_sign)
    
    if pattern == ('+', '-', '-'):
        if cfo_quality == "High Quality":
            return "Shareholder Returns"
        return "Reinvestor"
    elif pattern == ('+', '+', '-'):
        return "Liquidating Assets"
    elif pattern == ('-', '+', '+'):
        return "Distress Signal"
    elif pattern == ('-', '-', '+'):
        return "Growth Funded by Debt"
    elif pattern == ('+', '+', '+'):
        return "Cash Accumulator"
    elif pattern == ('-', '-', '-'):
        return "Pre-Revenue"
    elif pattern == ('+', '-', '+'):
        return "Mixed"
    else:
        return "Unknown"
