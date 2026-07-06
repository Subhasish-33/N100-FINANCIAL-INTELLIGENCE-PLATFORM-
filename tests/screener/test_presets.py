"""
tests/screener/test_presets.py
Tests for the 6 preset screeners — business logic and result range validation.
"""

import pytest
import pandas as pd
from src.screener.engine import run_preset, run_all_presets

YEAR = 2024
ALL_PRESETS = [
    "quality_compounder",
    "value_pick",
    "growth_accelerator",
    "dividend_champion",
    "debt_free_blue_chip",
    "turnaround_watch",
]


# ─── Result Range Tests ──────────────────────────────────────────

@pytest.mark.parametrize("preset_name", ALL_PRESETS)
def test_preset_returns_between_1_and_92(preset_name):
    """Each preset must return at least 1 and at most 92 companies."""
    result = run_preset(preset_name, year=YEAR)
    assert isinstance(result, pd.DataFrame), f"{preset_name} did not return a DataFrame"
    assert 1 <= len(result) <= 92, (
        f"Preset '{preset_name}' returned {len(result)} companies — expected 1–92"
    )


# ─── Business Logic Tests ────────────────────────────────────────

def test_quality_compounder_roe_above_15():
    """All Quality Compounder results must have ROE > 15%."""
    result = run_preset("quality_compounder", year=YEAR)
    roe = result["return_on_equity_pct"].dropna()
    assert (roe >= 15.0).all(), "Quality Compounder has companies with ROE < 15%"


def test_quality_compounder_de_below_1_for_non_financials():
    """Quality Compounder: non-Financials must have D/E <= 1.0."""
    result = run_preset("quality_compounder", year=YEAR)
    non_fin = result[result["sector_name"] != "Financials"]
    de = non_fin["debt_to_equity"].dropna()
    assert (de <= 1.0).all(), "Quality Compounder: non-Financials have D/E > 1"


def test_quality_compounder_fcf_positive():
    """Quality Compounder: all companies must have FCF >= 0."""
    result = run_preset("quality_compounder", year=YEAR)
    fcf = result["free_cash_flow_cr"].dropna()
    assert (fcf >= 0.0).all(), "Quality Compounder has companies with negative FCF"


def test_growth_accelerator_pat_cagr():
    """Growth Accelerator: PAT CAGR 5yr must be > 20%."""
    result = run_preset("growth_accelerator", year=YEAR)
    pat = result["pat_cagr_5yr"].dropna()
    assert (pat >= 20.0).all(), "Growth Accelerator has companies with PAT CAGR < 20%"


def test_dividend_champion_yield_above_2():
    """Dividend Champion: dividend yield must be >= 2%."""
    result = run_preset("dividend_champion", year=YEAR)
    div = result["dividend_yield_pct"].dropna()
    assert (div >= 2.0).all(), "Dividend Champion has companies with Dividend Yield < 2%"


def test_dividend_champion_positive_fcf():
    """Dividend Champion: FCF must be positive."""
    result = run_preset("dividend_champion", year=YEAR)
    fcf = result["free_cash_flow_cr"].dropna()
    assert (fcf >= 0.0).all(), "Dividend Champion has companies with negative FCF"


def test_debt_free_blue_chip_near_zero_de():
    """Debt-Free Blue Chip: D/E must be < 0.1."""
    result = run_preset("debt_free_blue_chip", year=YEAR)
    non_fin = result[result["sector_name"] != "Financials"]
    de = non_fin["debt_to_equity"].dropna()
    assert (de <= 0.1).all(), "Debt-Free Blue Chip has companies with D/E > 0.1"


def test_debt_free_blue_chip_roe_above_12():
    """Debt-Free Blue Chip: ROE must be >= 12%."""
    result = run_preset("debt_free_blue_chip", year=YEAR)
    roe = result["return_on_equity_pct"].dropna()
    assert (roe >= 12.0).all(), "Debt-Free Blue Chip has companies with ROE < 12%"


def test_turnaround_watch_3yr_cagr():
    """Turnaround Watch: revenue CAGR 3yr must be > 10%."""
    result = run_preset("turnaround_watch", year=YEAR)
    cagr = result["revenue_cagr_3yr"].dropna()
    assert (cagr >= 10.0).all(), "Turnaround Watch has companies with Rev CAGR 3yr < 10%"


def test_run_all_presets_returns_all_six():
    """run_all_presets() should return exactly 6 keys."""
    results = run_all_presets(year=YEAR)
    assert len(results) == 6, f"Expected 6 presets, got {len(results)}"
    for name in ALL_PRESETS:
        assert name in results, f"Preset '{name}' missing from run_all_presets output"


def test_presets_are_subsets_of_universe():
    """Every preset result must contain only valid tickers from the 92-company universe."""
    from src.screener.engine import load_screener_universe
    universe = load_screener_universe(YEAR)
    valid_tickers = set(universe["ticker"])
    results = run_all_presets(year=YEAR)
    for preset_name, df in results.items():
        preset_tickers = set(df["ticker"])
        assert preset_tickers.issubset(valid_tickers), (
            f"Preset '{preset_name}' contains tickers not in universe: "
            f"{preset_tickers - valid_tickers}"
        )
