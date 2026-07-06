import pytest
from src.analytics.cashflow_kpis import (
    compute_fcf,
    compute_cfo_quality_score,
    compute_capex_intensity,
    compute_fcf_conversion_rate,
    classify_capital_allocation
)

def test_compute_fcf():
    assert compute_fcf(100.0, -20.0) == 80.0
    assert compute_fcf(50.0, -60.0) == -10.0

def test_cfo_quality_score():
    assert compute_cfo_quality_score([100, 150, 100], [80, 100, 120]) == "High Quality"
    assert compute_cfo_quality_score([50, 50], [100, 100]) == "Moderate"
    assert compute_cfo_quality_score([30, 40], [100, 100]) == "Accrual Risk"
    assert compute_cfo_quality_score([100], [0]) is None

def test_capex_intensity():
    assert compute_capex_intensity(-20, 1000) == (2.0, "Asset Light")
    assert compute_capex_intensity(-50, 1000) == (5.0, "Moderate")
    assert compute_capex_intensity(-100, 1000) == (10.0, "Capital Intensive")
    assert compute_capex_intensity(-100, 0) is None

def test_fcf_conversion_rate():
    assert compute_fcf_conversion_rate(80, 100) == 80.0
    assert compute_fcf_conversion_rate(80, 0) is None

def test_classify_capital_allocation():
    assert classify_capital_allocation(10, -10, -10, "Moderate") == "Reinvestor"
    assert classify_capital_allocation(10, -10, -10, "High Quality") == "Shareholder Returns"
    assert classify_capital_allocation(10, 10, -10) == "Liquidating Assets"
    assert classify_capital_allocation(-10, 10, 10) == "Distress Signal"
    assert classify_capital_allocation(-10, -10, 10) == "Growth Funded by Debt"
    assert classify_capital_allocation(10, 10, 10) == "Cash Accumulator"
    assert classify_capital_allocation(-10, -10, -10) == "Pre-Revenue"
    assert classify_capital_allocation(10, -10, 10) == "Mixed"
    assert classify_capital_allocation(-10, 10, -10) == "Unknown"
