import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Day 08 - Profitability Ratios

def calculate_net_profit_margin(net_profit: Optional[float], sales: Optional[float]) -> Optional[float]:
    if not sales or sales == 0 or net_profit is None:
        return None
    return (net_profit / sales) * 100

def calculate_opm(operating_profit: Optional[float], sales: Optional[float]) -> Optional[float]:
    if not sales or sales == 0 or operating_profit is None:
        return None
    return (operating_profit / sales) * 100

def cross_check_opm(computed_opm: Optional[float], expected_opm: Optional[float], ticker: str, year: int) -> None:
    if computed_opm is not None and expected_opm is not None:
        if abs(computed_opm - expected_opm) > 1.0:
            logger.warning(
                f"OPM mismatch for {ticker} in {year}: computed {computed_opm:.2f}%, expected {expected_opm:.2f}%"
            )

def calculate_roe(net_profit: Optional[float], equity_capital: Optional[float], reserves: Optional[float]) -> Optional[float]:
    if net_profit is None:
        return None
    denominator = (equity_capital or 0) + (reserves or 0)
    if denominator <= 0:
        return None
    return (net_profit / denominator) * 100

def calculate_roce(ebit: Optional[float], equity_capital: Optional[float], reserves: Optional[float], borrowings: Optional[float]) -> Optional[float]:
    if ebit is None:
        return None
    denominator = (equity_capital or 0) + (reserves or 0) + (borrowings or 0)
    if denominator == 0:
        return None
    return (ebit / denominator) * 100

def calculate_roa(net_profit: Optional[float], total_assets: Optional[float]) -> Optional[float]:
    if not total_assets or total_assets == 0 or net_profit is None:
        return None
    return (net_profit / total_assets) * 100


