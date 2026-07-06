"""
tests/screener/test_engine.py
Unit tests for the core screener engine filter logic.
"""

import pandas as pd
import pytest
from src.screener.engine import apply_filters, load_screener_universe, run_screener


YEAR = 2024


# ─── Fixtures ───────────────────────────────────────────────────

@pytest.fixture(scope="module")
def universe():
    return load_screener_universe(YEAR)


# ─── Universe Sanity Tests ──────────────────────────────────────

def test_universe_loads_92_companies(universe):
    assert len(universe) == 92, f"Expected 92 companies, got {len(universe)}"


def test_universe_has_required_columns(universe):
    required = [
        "ticker", "company_name", "sector_name",
        "return_on_equity_pct", "debt_to_equity", "free_cash_flow_cr",
        "revenue_cagr_5yr", "revenue_cagr_3yr", "pat_cagr_5yr",
        "operating_profit_margin_pct", "interest_coverage", "icr_label",
        "pe_ratio", "pb_ratio", "dividend_yield_pct", "market_cap_crore",
        "sales", "net_profit", "composite_quality_score",
    ]
    for col in required:
        assert col in universe.columns, f"Missing column: {col}"


# ─── Filter Logic Tests ─────────────────────────────────────────

def test_roe_min_filter(universe):
    """All returned companies should have ROE >= threshold."""
    threshold = 20.0
    result = apply_filters(universe, {"roe_min": threshold})
    roe_vals = result["return_on_equity_pct"].dropna()
    assert (roe_vals >= threshold).all(), "Some companies failed ROE min filter"


def test_de_max_filter(universe):
    """Non-Financials companies should all have D/E <= threshold."""
    threshold = 1.0
    result = apply_filters(universe, {"de_max": threshold})
    non_fin = result[result["sector_name"] != "Financials"]
    de_vals = non_fin["debt_to_equity"].dropna()
    assert (de_vals <= threshold).all(), "Non-Financials company exceeded D/E threshold"


def test_de_max_financials_exemption(universe):
    """Financials companies should always pass the D/E filter, regardless of D/E value."""
    # Set a very strict D/E max — Financials should still appear
    result = apply_filters(universe, {"de_max": 0.0})
    financials = result[result["sector_name"] == "Financials"]
    # We should have at least some Financials in the result
    assert len(financials) > 0, "Financials companies should be exempt from D/E filter"


def test_icr_debt_free_always_passes(universe):
    """Companies with icr_label='Debt Free' should pass any ICR threshold."""
    result = apply_filters(universe, {"icr_min": 999999.0})  # impossibly high threshold
    # Only Debt Free companies should survive
    for _, row in result.iterrows():
        assert row["icr_label"] == "Debt Free", (
            f"{row['ticker']} passed ICR filter with label '{row['icr_label']}'"
        )


def test_fcf_min_filter(universe):
    """All returned companies should have FCF >= 0."""
    result = apply_filters(universe, {"fcf_min": 0.0})
    fcf_vals = result["free_cash_flow_cr"].dropna()
    assert (fcf_vals >= 0.0).all(), "Some companies have negative FCF after filter"


def test_multiple_filters_intersect(universe):
    """Combining filters should return subset of each individual filter."""
    result_single = apply_filters(universe, {"roe_min": 15.0})
    result_combined = apply_filters(universe, {"roe_min": 15.0, "de_max": 1.0})
    assert len(result_combined) <= len(result_single), (
        "Combined filters should return same or fewer results than single filter"
    )


def test_filters_return_sorted_by_quality(universe):
    """Results should be sorted with 'High' quality companies first."""
    result = run_screener({"roe_min": 10.0}, year=YEAR)
    if len(result) > 1 and "composite_quality_score" in result.columns:
        scores = result["composite_quality_score"].dropna().tolist()
        # High should come before Moderate/Low
        first_low_idx = next(
            (i for i, s in enumerate(scores) if s in ("Moderate", "Low", None)), len(scores)
        )
        first_high_after_low = next(
            (i for i, s in enumerate(scores) if i > first_low_idx and s == "High"), None
        )
        assert first_high_after_low is None, "High quality companies should be sorted before Moderate/Low"


def test_unknown_metric_key_skipped(universe):
    """Unknown metric keys should be skipped without error."""
    # Should not raise
    result = apply_filters(universe, {"unknown_metric_xyz": 10.0})
    assert len(result) == len(universe)


def test_run_screener_returns_dataframe():
    result = run_screener({"roe_min": 15.0}, year=YEAR)
    assert isinstance(result, pd.DataFrame)
    assert len(result) > 0
