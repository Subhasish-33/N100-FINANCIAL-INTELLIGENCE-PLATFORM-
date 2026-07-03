import pytest
from src.analytics.cagr import (
    compute_cagr,
    DECLINE_TO_LOSS,
    TURNAROUND,
    BOTH_NEGATIVE,
    ZERO_BASE,
    INSUFFICIENT,
    NORMAL
)

def test_normal_cagr_3_years():
    # start=100, end=133.1, years=3 -> 10% CAGR
    val, flag = compute_cagr(100.0, 133.1, 3)
    assert flag == NORMAL
    assert pytest.approx(val, 0.01) == 10.0

def test_normal_cagr_5_years():
    # start=100, end=161.051, years=5 -> 10% CAGR
    val, flag = compute_cagr(100.0, 161.051, 5)
    assert flag == NORMAL
    assert pytest.approx(val, 0.01) == 10.0

def test_normal_cagr_10_years():
    # start=100, end=259.374, years=10 -> 10% CAGR
    val, flag = compute_cagr(100.0, 259.374, 10)
    assert flag == NORMAL
    assert pytest.approx(val, 0.01) == 10.0

def test_decline_to_loss():
    # start=100, end=-50
    val, flag = compute_cagr(100.0, -50.0, 5)
    assert val is None
    assert flag == DECLINE_TO_LOSS

def test_decline_to_zero():
    # start=100, end=0 -> also decline to loss
    val, flag = compute_cagr(100.0, 0.0, 5)
    assert val is None
    assert flag == DECLINE_TO_LOSS

def test_turnaround():
    # start=-50, end=100
    val, flag = compute_cagr(-50.0, 100.0, 5)
    assert val is None
    assert flag == TURNAROUND

def test_both_negative():
    # start=-50, end=-100
    val, flag = compute_cagr(-50.0, -100.0, 5)
    assert val is None
    assert flag == BOTH_NEGATIVE

def test_both_negative_improving():
    # start=-100, end=-50
    val, flag = compute_cagr(-100.0, -50.0, 5)
    assert val is None
    assert flag == BOTH_NEGATIVE

def test_zero_base():
    # start=0, end=100
    val, flag = compute_cagr(0.0, 100.0, 5)
    assert val is None
    assert flag == ZERO_BASE

def test_insufficient_data():
    # years=0
    val, flag = compute_cagr(100.0, 110.0, 0)
    assert val is None
    assert flag == INSUFFICIENT
