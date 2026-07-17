"""
src/analytics/peer.py
Peer Percentile Ranking Engine — computes PERCENT_RANK for 10 metrics
within each of the 11 peer groups and writes results to the
peer_percentiles table in database.sqlite.
"""

import sqlite3
import logging
from pathlib import Path
from typing import Optional

import pandas as pd
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent.parent
DB_PATH = BASE_DIR / "data" / "database.sqlite"

# 10 metrics to rank, with direction and column name in financial_ratios
PEER_METRICS = {
    "ROE": {
        "column": "return_on_equity_pct",
        "direction": "higher_is_better",
    },
    "ROCE": {
        "column": "roce_percentage",
        "direction": "higher_is_better",
    },
    "Net Profit Margin": {
        "column": "net_profit_margin_pct",
        "direction": "higher_is_better",
    },
    "D/E": {
        "column": "debt_to_equity",
        "direction": "lower_is_better",  # inverted: 1 - PERCENT_RANK
    },
    "FCF": {
        "column": "free_cash_flow_cr",
        "direction": "higher_is_better",
    },
    "PAT CAGR 5yr": {
        "column": "pat_cagr_5yr",
        "direction": "higher_is_better",
    },
    "Revenue CAGR 5yr": {
        "column": "revenue_cagr_5yr",
        "direction": "higher_is_better",
    },
    "EPS CAGR 5yr": {
        "column": "eps_cagr_5yr",
        "direction": "higher_is_better",
    },
    "Interest Coverage": {
        "column": "interest_coverage",
        "direction": "higher_is_better",
    },
    "Asset Turnover": {
        "column": "asset_turnover",
        "direction": "higher_is_better",
    },
}


def load_peer_group_data(year: int = 2024, db_path: Path = DB_PATH) -> pd.DataFrame:
    """
    Load peer group membership joined with financial_ratios for the given year.
    Returns a DataFrame with peer_group_name, ticker, and all 10 metric columns.
    """
    metric_cols = ", ".join(
        [f"fr.{spec['column']}" for spec in PEER_METRICS.values()]
    )

    query = f"""
        SELECT
            pg.peer_group_name,
            pg.ticker,
            c.company_name,
            fr.icr_label,
            fr.composite_quality_score,
            {metric_cols}
        FROM peer_groups pg
        JOIN companies c ON pg.ticker = c.ticker
        LEFT JOIN financial_ratios fr ON pg.ticker = fr.ticker AND fr.year = :year
        ORDER BY pg.peer_group_name, pg.ticker
    """
    conn = sqlite3.connect(db_path)
    df = pd.read_sql(query, conn, params={"year": year})
    conn.close()

    # Force numeric types
    for spec in PEER_METRICS.values():
        col = spec["column"]
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if "composite_quality_score" in df.columns:
        df["composite_quality_score"] = pd.to_numeric(
            df["composite_quality_score"], errors="coerce"
        )

    logger.info(
        f"Loaded {len(df)} peer-grouped company records for year {year} "
        f"across {df['peer_group_name'].nunique()} groups"
    )
    return df


def compute_percentile_ranks(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Compute percentile ranks (0.0–1.0) for each metric within each peer group.

    Returns a long-format DataFrame with columns:
        ticker, peer_group_name, metric, raw_value, percentile_rank

    Special handling:
    - D/E: inverted so lower D/E → higher percentile rank.
    - Interest Coverage with icr_label='Debt Free': assigned percentile_rank = 1.0.
    - NULL metric values: assigned NaN percentile (excluded from ranking for that metric).
    """
    results = []

    for group_name, group_df in df.groupby("peer_group_name"):
        for metric_name, spec in PEER_METRICS.items():
            col = spec["column"]
            direction = spec["direction"]

            for _, row in group_df.iterrows():
                raw_value = row[col]
                ticker = row["ticker"]

                # Default: NaN for missing values
                if pd.isna(raw_value):
                    results.append({
                        "ticker": ticker,
                        "peer_group_name": group_name,
                        "metric": metric_name,
                        "raw_value": None,
                        "percentile_rank": None,
                    })
                    continue

                # Get all non-null values in this group for ranking
                group_values = group_df[col].dropna()

                if len(group_values) <= 1:
                    # Single company or all null — assign 1.0
                    pct_rank = 1.0
                else:
                    # Compute percent rank: fraction of values that are less than this value
                    rank = (group_values < raw_value).sum()
                    pct_rank = rank / (len(group_values) - 1)

                # Invert for lower-is-better metrics
                if direction == "lower_is_better":
                    pct_rank = 1.0 - pct_rank

                # Special case: Debt Free companies get top rank for Interest Coverage
                if metric_name == "Interest Coverage" and row.get("icr_label") == "Debt Free":
                    pct_rank = 1.0

                # Clamp to [0, 1]
                pct_rank = max(0.0, min(1.0, pct_rank))

                results.append({
                    "ticker": ticker,
                    "peer_group_name": group_name,
                    "metric": metric_name,
                    "raw_value": float(raw_value),
                    "percentile_rank": round(pct_rank, 4),
                })

    return pd.DataFrame(results)


def get_peer_percentiles(
    ticker: str, year: int = 2024, db_path: Path = DB_PATH
) -> Optional[pd.DataFrame]:
    """
    Retrieve precomputed percentile ranks for a specific company.
    Returns None with a log message if the company has no peer group.
    """
    conn = sqlite3.connect(db_path)

    # Check if company is in any peer group
    check = pd.read_sql(
        "SELECT COUNT(*) as cnt FROM peer_groups WHERE ticker = :ticker",
        conn,
        params={"ticker": ticker},
    )

    if check["cnt"].iloc[0] == 0:
        conn.close()
        logger.info(f"No peer group assigned for ticker '{ticker}'")
        return None

    df = pd.read_sql(
        """
        SELECT * FROM peer_percentiles
        WHERE ticker = :ticker AND year = :year
        ORDER BY metric
        """,
        conn,
        params={"ticker": ticker, "year": year},
    )
    conn.close()
    return df


def save_percentiles_to_db(
    percentiles_df: pd.DataFrame, year: int = 2024, db_path: Path = DB_PATH
) -> None:
    """Write computed percentile ranks to the peer_percentiles table."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Clear existing data for this year to allow re-runs
    cursor.execute("DELETE FROM peer_percentiles WHERE year = ?", (year,))

    records = []
    for _, row in percentiles_df.iterrows():
        records.append((
            row["ticker"],
            row["peer_group_name"],
            row["metric"],
            row["raw_value"] if pd.notna(row["raw_value"]) else None,
            row["percentile_rank"] if pd.notna(row["percentile_rank"]) else None,
            year,
        ))

    cursor.executemany(
        """
        INSERT INTO peer_percentiles
            (ticker, peer_group_name, metric, raw_value, percentile_rank, year)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        records,
    )
    conn.commit()
    conn.close()
    logger.info(
        f"Saved {len(records)} percentile records to peer_percentiles table for year {year}"
    )


def run_peer_engine(year: int = 2024, db_path: Path = DB_PATH) -> pd.DataFrame:
    """
    Full pipeline: load data → compute percentile ranks → save to DB.
    Returns the computed percentiles DataFrame.
    """
    df = load_peer_group_data(year, db_path)
    percentiles = compute_percentile_ranks(df)
    save_percentiles_to_db(percentiles, year, db_path)

    # Summary stats
    groups = percentiles["peer_group_name"].nunique()
    tickers = percentiles["ticker"].nunique()
    logger.info(
        f"Peer engine complete: {tickers} companies across {groups} groups, "
        f"{len(percentiles)} total percentile records"
    )
    return percentiles


if __name__ == "__main__":
    run_peer_engine(2024)
