"""
tests/analytics/test_peer.py
Unit tests for the peer percentile ranking engine.
"""

import pytest
import sqlite3
from pathlib import Path

import pandas as pd
import numpy as np

from src.analytics.peer import (
    load_peer_group_data,
    compute_percentile_ranks,
    get_peer_percentiles,
    run_peer_engine,
    DB_PATH,
    PEER_METRICS,
)

YEAR = 2024


# ─── Data Loading ─────────────────────────────────────────────────

def test_load_peer_group_data_returns_56_companies():
    """Peer group data should contain 56 companies across 11 groups."""
    df = load_peer_group_data(YEAR)
    assert len(df) == 56, f"Expected 56 rows, got {len(df)}"
    assert df["peer_group_name"].nunique() == 11


# ─── Percentile Rank Bounds ───────────────────────────────────────

def test_percentile_ranks_between_0_and_1():
    """All computed percentile values must be in [0.0, 1.0]."""
    df = load_peer_group_data(YEAR)
    pct = compute_percentile_ranks(df)

    valid = pct.dropna(subset=["percentile_rank"])
    assert (valid["percentile_rank"] >= 0.0).all(), "Found percentile_rank < 0"
    assert (valid["percentile_rank"] <= 1.0).all(), "Found percentile_rank > 1"


# ─── D/E Inversion ───────────────────────────────────────────────

def test_de_inversion():
    """Within any peer group, lower D/E should produce higher percentile rank."""
    df = load_peer_group_data(YEAR)
    pct = compute_percentile_ranks(df)

    de_ranks = pct[pct["metric"] == "D/E"].dropna(subset=["raw_value", "percentile_rank"])

    # Pick the group with the most members for a meaningful test
    group_counts = de_ranks.groupby("peer_group_name").size()
    if group_counts.empty:
        pytest.skip("No D/E data available for inversion test")

    largest_group = group_counts.idxmax()
    group = de_ranks[de_ranks["peer_group_name"] == largest_group].sort_values("raw_value")

    if len(group) < 2:
        pytest.skip("Need at least 2 companies for D/E inversion test")

    # The company with the lowest D/E should have the highest (or equal) percentile
    lowest_de_pctile = group.iloc[0]["percentile_rank"]
    highest_de_pctile = group.iloc[-1]["percentile_rank"]
    assert lowest_de_pctile >= highest_de_pctile, (
        f"D/E inversion failed: lowest D/E has rank {lowest_de_pctile}, "
        f"highest D/E has rank {highest_de_pctile}"
    )


# ─── Debt Free ICR ───────────────────────────────────────────────

def test_debt_free_icr_gets_top_rank():
    """Companies with icr_label='Debt Free' must get percentile = 1.0 for Interest Coverage."""
    df = load_peer_group_data(YEAR)
    debt_free_tickers = df[df["icr_label"] == "Debt Free"]["ticker"].tolist()

    if not debt_free_tickers:
        pytest.skip("No Debt Free companies found in peer groups")

    pct = compute_percentile_ranks(df)
    icr_ranks = pct[
        (pct["metric"] == "Interest Coverage") &
        (pct["ticker"].isin(debt_free_tickers))
    ]

    for _, row in icr_ranks.iterrows():
        assert row["percentile_rank"] == 1.0, (
            f"Debt Free company {row['ticker']} has ICR percentile "
            f"{row['percentile_rank']} instead of 1.0"
        )


# ─── 11 Peer Groups Populated ────────────────────────────────────

def test_11_peer_groups_populated():
    """The peer_percentiles table must have records for all 11 groups."""
    conn = sqlite3.connect(DB_PATH)
    result = pd.read_sql(
        "SELECT DISTINCT peer_group_name FROM peer_percentiles WHERE year = ?",
        conn,
        params=(YEAR,),
    )
    conn.close()
    assert len(result) == 11, f"Expected 11 groups, got {len(result)}"


# ─── No Peer Group Handling ───────────────────────────────────────

def test_no_peer_group_returns_none():
    """Companies not in any peer group should return None from get_peer_percentiles."""
    # Find a ticker NOT in peer_groups
    conn = sqlite3.connect(DB_PATH)
    result = pd.read_sql(
        """
        SELECT c.ticker FROM companies c
        WHERE c.ticker NOT IN (SELECT DISTINCT ticker FROM peer_groups)
        LIMIT 1
        """,
        conn,
    )
    conn.close()

    if result.empty:
        pytest.skip("All companies have peer groups (unexpected)")

    orphan_ticker = result.iloc[0]["ticker"]
    pct = get_peer_percentiles(orphan_ticker, YEAR)
    assert pct is None, f"Expected None for ungrouped ticker {orphan_ticker}, got DataFrame"


# ─── IT Services Spot Check ──────────────────────────────────────

def test_it_services_highest_roe_has_top_rank():
    """Within IT Services, the company with the highest ROE should have the top ROE percentile."""
    df = load_peer_group_data(YEAR)
    it_df = df[df["peer_group_name"] == "IT Services"].dropna(subset=["return_on_equity_pct"])

    if it_df.empty:
        pytest.skip("No IT Services ROE data")

    top_roe_ticker = it_df.loc[it_df["return_on_equity_pct"].idxmax(), "ticker"]

    pct = compute_percentile_ranks(df)
    it_roe = pct[
        (pct["peer_group_name"] == "IT Services") &
        (pct["metric"] == "ROE")
    ]

    top_ranked = it_roe.loc[it_roe["percentile_rank"].idxmax(), "ticker"]
    assert top_ranked == top_roe_ticker, (
        f"Expected {top_roe_ticker} to have top ROE rank, got {top_ranked}"
    )


# ─── FMCG Spot Check ─────────────────────────────────────────────

def test_fmcg_group_has_7_companies():
    """FMCG peer group should have exactly 7 companies with percentile records."""
    conn = sqlite3.connect(DB_PATH)
    result = pd.read_sql(
        """
        SELECT COUNT(DISTINCT ticker) as cnt
        FROM peer_percentiles
        WHERE peer_group_name = 'FMCG' AND year = ?
        """,
        conn,
        params=(YEAR,),
    )
    conn.close()
    assert result.iloc[0]["cnt"] == 7, f"Expected 7 FMCG companies, got {result.iloc[0]['cnt']}"
