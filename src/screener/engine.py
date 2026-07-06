"""
src/screener/engine.py
Core screener engine — loads universe, applies filters, runs presets.
"""

import sqlite3
import logging
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent.parent
DB_PATH = BASE_DIR / "data" / "database.sqlite"
CONFIG_PATH = BASE_DIR / "config" / "screener_config.yaml"


def _load_config() -> dict:
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)


def load_screener_universe(year: int = 2024) -> pd.DataFrame:
    """
    Build a flat screener universe DataFrame for the given year by LEFT JOINing
    financial_ratios, market_data, profit_and_loss, companies, and sectors.
    """
    conn = sqlite3.connect(DB_PATH)
    query = """
        SELECT
            c.ticker,
            c.company_name,
            s.sector_name,
            -- Financial Ratios
            fr.return_on_equity_pct,
            fr.debt_to_equity,
            fr.free_cash_flow_cr,
            fr.revenue_cagr_5yr,
            fr.revenue_cagr_3yr,
            fr.pat_cagr_5yr,
            fr.eps_cagr_5yr,
            fr.operating_profit_margin_pct,
            fr.interest_coverage,
            fr.icr_label,
            fr.asset_turnover,
            fr.dividend_payout_ratio_pct,
            fr.composite_quality_score,
            fr.high_leverage_flag,
            -- Market Data
            md.pe_ratio,
            md.pb_ratio,
            md.dividend_yield_pct,
            md.market_cap_crore,
            -- P&L
            pl.sales,
            pl.net_profit
        FROM companies c
        LEFT JOIN sectors s ON c.sector_id = s.sector_id
        LEFT JOIN financial_ratios fr ON c.ticker = fr.ticker AND fr.year = :year
        LEFT JOIN market_data md ON c.ticker = md.ticker AND md.year = :year
        LEFT JOIN profit_and_loss pl ON c.ticker = pl.ticker AND pl.year = :year
        ORDER BY c.ticker
    """
    df = pd.read_sql(query, conn, params={"year": year})
    conn.close()
    logger.info(f"Universe loaded: {len(df)} companies for year {year}")
    return df


def apply_filters(df: pd.DataFrame, filters: dict[str, Any], year: int = 2024) -> pd.DataFrame:
    """
    Apply a dict of {metric_key: threshold} to the universe DataFrame.
    Special handling:
      - de_max: Financials sector companies are exempt (always pass)
      - icr_min: rows with icr_label='Debt Free' always pass
      - de_declining_yoy: computed by comparing year vs year-1 in DB
    """
    config = _load_config()
    metric_config = config.get("metrics", {})
    result = df.copy()

    for metric_key, threshold in filters.items():
        # Special boolean flag — handled separately
        if metric_key == "de_declining_yoy":
            if threshold:
                result = _filter_de_declining_yoy(result, year)
            continue

        if metric_key not in metric_config:
            logger.warning(f"Unknown metric '{metric_key}' in filters — skipping")
            continue

        meta = metric_config[metric_key]
        col = meta["column"]
        direction = meta["direction"]
        financials_exempt = meta.get("financials_de_exempt", False)
        debt_free_inf = meta.get("debt_free_as_infinity", False)

        if col not in result.columns:
            logger.warning(f"Column '{col}' not found in universe — skipping filter '{metric_key}'")
            continue

        # Build boolean mask
        if direction == "min":
            mask = result[col] >= threshold
        else:  # max
            mask = result[col] <= threshold

        # ICR: Debt Free rows always pass (treat as infinity)
        if debt_free_inf and "icr_label" in result.columns:
            debt_free_mask = result["icr_label"] == "Debt Free"
            mask = mask | debt_free_mask

        # D/E: Financials sector companies are exempt from D/E filters
        if financials_exempt and "sector_name" in result.columns:
            financials_mask = result["sector_name"] == "Financials"
            mask = mask | financials_mask

        # Apply: for min/max filters, rows with null values for that column are excluded
        result = result[mask]

    return result


def _filter_de_declining_yoy(df: pd.DataFrame, year: int) -> pd.DataFrame:
    """Keep only companies where D/E in `year` < D/E in `year-1`."""
    conn = sqlite3.connect(DB_PATH)
    query = """
        SELECT a.ticker
        FROM financial_ratios a
        JOIN financial_ratios b ON a.ticker = b.ticker AND b.year = a.year - 1
        WHERE a.year = :year
          AND a.debt_to_equity IS NOT NULL
          AND b.debt_to_equity IS NOT NULL
          AND a.debt_to_equity < b.debt_to_equity
    """
    declining = pd.read_sql(query, conn, params={"year": year})
    conn.close()
    return df[df["ticker"].isin(declining["ticker"])]


def run_screener(filters: dict[str, Any], year: int = 2024) -> pd.DataFrame:
    """
    Load the screener universe, apply filters, return a sorted DataFrame
    with composite_quality_score column added.
    """
    df = load_screener_universe(year)
    filtered = apply_filters(df, filters, year)
    # Sort: High quality first, then by ROE desc
    quality_order = {"High": 0, "Moderate": 1, "Low": 2}
    filtered = filtered.copy()
    filtered["_quality_sort"] = filtered["composite_quality_score"].map(quality_order).fillna(3)
    filtered = filtered.sort_values(
        ["_quality_sort", "return_on_equity_pct"],
        ascending=[True, False]
    ).drop(columns=["_quality_sort"])
    filtered = filtered.reset_index(drop=True)
    logger.info(f"Screener returned {len(filtered)} companies")
    return filtered


def run_preset(preset_name: str, year: int = 2024) -> pd.DataFrame:
    """Load and run a named preset from screener_config.yaml."""
    config = _load_config()
    presets = config.get("presets", {})
    if preset_name not in presets:
        raise ValueError(f"Preset '{preset_name}' not found. Available: {list(presets.keys())}")
    preset = presets[preset_name]
    filters = preset.get("filters", {})
    logger.info(f"Running preset: {preset['label']}")
    return run_screener(filters, year)


def run_all_presets(year: int = 2024) -> dict[str, pd.DataFrame]:
    """Run all 6 presets and return a dict of {preset_name: DataFrame}."""
    config = _load_config()
    results = {}
    for preset_name in config.get("presets", {}):
        results[preset_name] = run_preset(preset_name, year)
    return results


def generate_screener_output(year: int = 2024, output_path: str = "output/screener_output.xlsx") -> None:
    """Generate screener_output.xlsx with one sheet per preset."""
    results = run_all_presets(year)
    config = _load_config()
    presets_meta = config.get("presets", {})

    output_path = BASE_DIR / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        for preset_name, df in results.items():
            sheet_label = presets_meta[preset_name]["label"][:31]  # Excel sheet name max 31 chars
            df.to_excel(writer, sheet_name=sheet_label, index=False)
            logger.info(f"  Sheet '{sheet_label}': {len(df)} companies")

    logger.info(f"screener_output.xlsx saved to {output_path}")


if __name__ == "__main__":
    generate_screener_output()
