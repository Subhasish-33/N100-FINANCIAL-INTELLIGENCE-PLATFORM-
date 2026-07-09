"""
src/analytics/composite_score.py
Sector-relative 0-100 Composite Quality Score calculator.
"""

import sqlite3
import logging
from pathlib import Path
import pandas as pd
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent.parent
DB_PATH = BASE_DIR / "data" / "database.sqlite"

# Metric weight mappings and directions
METRIC_SPECS = {
    "return_on_equity_pct": {"weight": 0.15, "direction": "higher_is_better"},
    "roce_percentage": {"weight": 0.10, "direction": "higher_is_better"},
    "net_profit_margin_pct": {"weight": 0.10, "direction": "higher_is_better"},
    "fcf_cagr_5yr": {"weight": 0.15, "direction": "higher_is_better"},
    "cfo_pat_ratio": {"weight": 0.10, "direction": "higher_is_better"},
    "free_cash_flow_cr": {"weight": 0.05, "direction": "binary_fcf_positive"},
    "revenue_cagr_5yr": {"weight": 0.10, "direction": "higher_is_better"},
    "pat_cagr_5yr": {"weight": 0.10, "direction": "higher_is_better"},
    "debt_to_equity": {"weight": 0.10, "direction": "lower_is_better"},
    "interest_coverage": {"weight": 0.05, "direction": "higher_is_better"},
}


def load_ratios_for_scoring(year: int = 2024) -> pd.DataFrame:
    """Load all companies and their financial ratios for the given year, including sector names."""
    conn = sqlite3.connect(DB_PATH)
    query = """
        SELECT
            fr.ticker,
            fr.year,
            s.sector_name AS broad_sector,
            fr.return_on_equity_pct,
            fr.roce_percentage,
            fr.net_profit_margin_pct,
            fr.fcf_cagr_5yr,
            fr.cfo_pat_ratio,
            fr.free_cash_flow_cr,
            fr.revenue_cagr_5yr,
            fr.pat_cagr_5yr,
            fr.debt_to_equity,
            fr.interest_coverage,
            fr.icr_label
        FROM financial_ratios fr
        JOIN companies c ON fr.ticker = c.ticker
        LEFT JOIN sectors s ON c.sector_id = s.sector_id
        WHERE fr.year = :year
    """
    df = pd.read_sql(query, conn, params={"year": year})
    conn.close()
    return df


def calculate_composite_quality_scores(year: int = 2024) -> pd.DataFrame:
    """
    Calculate 0-100 composite quality scores normalized within each broad_sector.
    Winsorises at P10/P90, handles Debt Free ICR, and writes back to DB.
    """
    df = load_ratios_for_scoring(year)
    if df.empty:
        logger.warning(f"No records found in database for year {year} to calculate composite scores.")
        return df

    # Create a copy for score calculation
    scored_df = df.copy()

    # Force cast to float to avoid object dtype issues
    for col in METRIC_SPECS.keys():
        scored_df[col] = pd.to_numeric(scored_df[col], errors='coerce')

    # Impute missing values with sector median (fallback to 0.0)
    for col in METRIC_SPECS.keys():
        scored_df[col] = scored_df.groupby("broad_sector")[col].transform(
            lambda x: x.fillna(x.median() if not x.isna().all() else 0.0)
        )
        scored_df[col] = scored_df[col].fillna(0.0)

    # Dictionary to keep intermediate scores
    component_scores = {}

    # Calculate winsorised and scaled scores for each metric
    for col, spec in METRIC_SPECS.items():
        direction = spec["direction"]
        
        if direction == "binary_fcf_positive":
            # Binary flag: FCF > 0 gets 100, FCF <= 0 gets 0
            scores = np.where(scored_df[col] > 0, 100.0, 0.0)
            component_scores[col] = scores.astype(float)
            continue

        # Group by sector and compute P10 and P90 as floats
        p10 = scored_df.groupby("broad_sector")[col].transform(lambda x: x.quantile(0.1)).astype(float)
        p90 = scored_df.groupby("broad_sector")[col].transform(lambda x: x.quantile(0.9)).astype(float)

        # Winsorise: cap values
        val_capped = np.clip(scored_df[col], p10, p90)

        # Scale to 0-100
        denom = p90 - p10
        # Avoid division by zero when P10 == P90
        safe_denom = np.where(denom == 0, 1.0, denom)

        if direction == "higher_is_better":
            scores = (val_capped - p10) / safe_denom * 100.0
            scores = np.where(denom == 0, 100.0, scores)
            
            # Special case for Interest Coverage: Debt Free label gets 100
            if col == "interest_coverage":
                scores = np.where(scored_df["icr_label"] == "Debt Free", 100.0, scores)
                
        elif direction == "lower_is_better":
            scores = (p90 - val_capped) / safe_denom * 100.0
            scores = np.where(denom == 0, 100.0, scores)
            
        component_scores[col] = scores.astype(float)

    # Compute weighted composite score
    total_score = np.zeros(len(scored_df))
    for col, spec in METRIC_SPECS.items():
        weight = spec["weight"]
        total_score += component_scores[col] * weight

    scored_df["composite_score"] = np.round(total_score, 2)

    # Save to database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    updates = []
    for _, row in scored_df.iterrows():
        updates.append((float(row["composite_score"]), row["ticker"], int(row["year"])))

    cursor.executemany(
        "UPDATE financial_ratios SET composite_quality_score = ? WHERE ticker = ? AND year = ?",
        updates
    )
    conn.commit()
    conn.close()
    
    logger.info(f"Successfully computed and updated composite scores for {len(scored_df)} companies in year {year}")
    return scored_df


if __name__ == "__main__":
    calculate_composite_quality_scores(2024)
