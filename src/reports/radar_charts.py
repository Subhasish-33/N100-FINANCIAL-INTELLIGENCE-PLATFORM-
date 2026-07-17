"""
src/reports/radar_charts.py
Generates polar/radar chart PNGs for each company — comparing the company's
metrics against its peer group average (or the Nifty 100 average for
companies without a peer group).

Output: reports/radar_charts/{ticker}_radar.png  (92 files)
"""

import sqlite3
import logging
from pathlib import Path

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")  # Non-interactive backend for PNG generation
import matplotlib.pyplot as plt

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent.parent
DB_PATH = BASE_DIR / "data" / "database.sqlite"
OUTPUT_DIR = BASE_DIR / "reports" / "radar_charts"

# 8 axes for the radar chart (subset of the 10 peer metrics)
RADAR_AXES = [
    {"label": "ROE", "column": "return_on_equity_pct"},
    {"label": "ROCE", "column": "roce_percentage"},
    {"label": "NPM", "column": "net_profit_margin_pct"},
    {"label": "D/E\n(inverted)", "column": "debt_to_equity", "invert": True},
    {"label": "FCF", "column": "free_cash_flow_cr"},
    {"label": "PAT CAGR\n5yr", "column": "pat_cagr_5yr"},
    {"label": "Rev CAGR\n5yr", "column": "revenue_cagr_5yr"},
    {"label": "Composite\nScore", "column": "composite_quality_score"},
]


def _load_universe(year: int = 2024) -> pd.DataFrame:
    """Load all companies with their financial ratios and peer group info."""
    metric_cols = ", ".join([f"fr.{ax['column']}" for ax in RADAR_AXES])

    query = f"""
        SELECT
            c.ticker,
            c.company_name,
            pg.peer_group_name,
            {metric_cols}
        FROM companies c
        LEFT JOIN financial_ratios fr ON c.ticker = fr.ticker AND fr.year = :year
        LEFT JOIN peer_groups pg ON c.ticker = pg.ticker
        ORDER BY c.ticker
    """
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql(query, conn, params={"year": year})
    conn.close()

    # Force numeric
    for ax in RADAR_AXES:
        col = ax["column"]
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def _normalize_values(values: np.ndarray, reference_values: np.ndarray) -> tuple:
    """
    Normalize both company and reference values to a 0–1 scale using
    the combined min/max range. Returns (norm_company, norm_reference).
    """
    combined = np.concatenate([values, reference_values])
    # Replace NaN with 0 for normalization purposes
    combined_clean = np.where(np.isnan(combined), 0, combined)
    values_clean = np.where(np.isnan(values), 0, values)
    ref_clean = np.where(np.isnan(reference_values), 0, reference_values)

    v_min = np.nanmin(combined_clean)
    v_max = np.nanmax(combined_clean)

    if v_max == v_min:
        return np.full_like(values_clean, 0.5, dtype=float), np.full_like(ref_clean, 0.5, dtype=float)

    norm_co = (values_clean - v_min) / (v_max - v_min)
    norm_ref = (ref_clean - v_min) / (v_max - v_min)
    return norm_co, norm_ref


def _generate_radar_chart(
    ticker: str,
    company_name: str,
    company_values: np.ndarray,
    reference_values: np.ndarray,
    reference_label: str,
    output_path: Path,
) -> None:
    """Generate and save a single radar chart PNG."""
    labels = [ax["label"] for ax in RADAR_AXES]
    num_axes = len(labels)

    # Compute angles for each axis
    angles = np.linspace(0, 2 * np.pi, num_axes, endpoint=False).tolist()
    angles += angles[:1]  # Close the polygon

    # Normalize values
    norm_co, norm_ref = _normalize_values(company_values, reference_values)

    # Close the polygons
    co_plot = np.append(norm_co, norm_co[0])
    ref_plot = np.append(norm_ref, norm_ref[0])

    # Create figure
    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True))

    # Plot company polygon (filled)
    ax.fill(angles, co_plot, alpha=0.25, color="#2563EB")
    ax.plot(angles, co_plot, color="#2563EB", linewidth=2.0, label=company_name)

    # Plot reference polygon (dashed outline)
    ax.plot(
        angles, ref_plot,
        color="#DC2626", linewidth=1.8, linestyle="--",
        label=reference_label,
    )

    # Configure axes
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels, fontsize=10)
    ax.set_yticklabels([])  # Hide radial tick labels for cleanliness
    ax.set_ylim(0, 1.05)

    # Title and legend
    ax.set_title(
        f"{company_name}\nvs {reference_label}",
        fontsize=13, fontweight="bold", pad=25,
    )
    ax.legend(loc="upper right", bbox_to_anchor=(1.25, 1.1), fontsize=9)

    plt.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def generate_all_radar_charts(year: int = 2024) -> int:
    """
    Generate radar chart PNGs for all 92 companies.
    - Peer-grouped companies: compared against their peer group average.
    - Ungrouped companies: compared against the Nifty 100 average.

    Returns the number of charts generated.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    df = _load_universe(year)

    if df.empty:
        logger.warning("No data found — aborting radar chart generation.")
        return 0

    metric_columns = [ax["column"] for ax in RADAR_AXES]

    # Precompute Nifty 100 average for ungrouped companies
    nifty_avg = np.array([df[col].mean() for col in metric_columns])

    # Invert D/E for display (higher = better in radar)
    de_col_idx = next(i for i, ax in enumerate(RADAR_AXES) if ax.get("invert"))

    # Invert Nifty avg D/E
    if not np.isnan(nifty_avg[de_col_idx]) and nifty_avg[de_col_idx] != 0:
        nifty_avg[de_col_idx] = 1.0 / nifty_avg[de_col_idx]

    # Precompute peer group averages
    peer_groups = df.dropna(subset=["peer_group_name"]).groupby("peer_group_name")
    peer_averages = {}
    for group_name, group_df in peer_groups:
        avg = np.array([group_df[col].mean() for col in metric_columns])
        # Invert D/E average
        if not np.isnan(avg[de_col_idx]) and avg[de_col_idx] != 0:
            avg[de_col_idx] = 1.0 / avg[de_col_idx]
        peer_averages[group_name] = avg

    count = 0
    for _, row in df.iterrows():
        ticker = row["ticker"]
        company_name = row["company_name"]
        peer_group = row["peer_group_name"]

        # Extract company values
        company_values = np.array([
            row[col] if pd.notna(row[col]) else np.nan
            for col in metric_columns
        ])

        # Invert D/E for the company
        if not np.isnan(company_values[de_col_idx]) and company_values[de_col_idx] != 0:
            company_values[de_col_idx] = 1.0 / company_values[de_col_idx]
        elif np.isnan(company_values[de_col_idx]):
            company_values[de_col_idx] = 0.0

        # Choose reference
        if pd.notna(peer_group) and peer_group in peer_averages:
            reference_values = peer_averages[peer_group]
            reference_label = f"{peer_group} Average"
        else:
            reference_values = nifty_avg.copy()
            reference_label = "Nifty 100 Average"

        output_path = OUTPUT_DIR / f"{ticker}_radar.png"
        _generate_radar_chart(
            ticker, company_name,
            company_values, reference_values,
            reference_label, output_path,
        )
        count += 1

    logger.info(f"Generated {count} radar chart PNGs in {OUTPUT_DIR}")
    return count


if __name__ == "__main__":
    generate_all_radar_charts(2024)
