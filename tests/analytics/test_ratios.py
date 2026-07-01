import pytest
import logging
from src.analytics.ratios import (
    calculate_net_profit_margin,
    calculate_opm,
    cross_check_opm,
    calculate_roe,
    calculate_roce,
    calculate_roa,
    calculate_debt_to_equity,
    evaluate_high_leverage,
    calculate_icr,
    get_icr_label,
    evaluate_icr_warning,
    calculate_net_debt,
    calculate_asset_turnover
)

# --- Day 08 Tests ---

def test_npm_normal_case():
    assert calculate_net_profit_margin(150, 1000) == 15.0

def test_npm_zero_denominator():
    assert calculate_net_profit_margin(150, 0) is None
    assert calculate_net_profit_margin(150, None) is None

def test_roe_negative_equity():
    assert calculate_roe(100, -500, 100) is None
    assert calculate_roe(100, -200, -300) is None

def test_opm_cross_check_mismatch(caplog):
    # This should log a warning since |15.5 - 12.0| > 1
    with caplog.at_level(logging.WARNING):
        cross_check_opm(15.5, 12.0, "RELIANCE", 2023)
    assert "OPM mismatch for RELIANCE in 2023: computed 15.50%, expected 12.00%" in caplog.text

def test_roe_normal():
    assert calculate_roe(100, 400, 100) == 20.0

def test_roce_normal():
    assert calculate_roce(200, 400, 100, 500) == 20.0

def test_roa_normal():
    assert calculate_roa(100, 1000) == 10.0

def test_roa_zero_denominator():
    assert calculate_roa(100, 0) is None


# --- Day 09 Tests ---

def test_de_debt_free():
    # If borrowings = 0, D/E should be 0.0 not None
    assert calculate_debt_to_equity(0, 1000, 500) == 0.0

def test_icr_zero_interest():
    assert calculate_icr(500, 100, 0) is None

def test_icr_label_debt_free():
    # When icr is None, the label should be 'Debt Free'
    assert get_icr_label(None) == "Debt Free"
    assert get_icr_label(5.0) is None

def test_high_de_flag_true():
    # D/E > 5 and not Financials
    assert evaluate_high_leverage(6.0, "Energy") is True

def test_high_de_flag_false_financials():
    # D/E > 5 but Financials
    assert evaluate_high_leverage(6.0, "Financials") is False

def test_icr_warning_flag():
    assert evaluate_icr_warning(1.2) is True
    assert evaluate_icr_warning(2.5) is False
    assert evaluate_icr_warning(None) is False

def test_de_normal():
    assert calculate_debt_to_equity(500, 500, 500) == 0.5
    assert calculate_debt_to_equity(500, 0, 0) is None # denominator 0

def test_asset_turnover():
    assert calculate_asset_turnover(1000, 500) == 2.0
    assert calculate_asset_turnover(1000, 0) is None
