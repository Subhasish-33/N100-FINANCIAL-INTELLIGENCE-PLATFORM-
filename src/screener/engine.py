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
from openpyxl.styles import PatternFill, Font

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
            fr.roce_percentage,
            fr.net_profit_margin_pct,
            fr.operating_profit_margin_pct,
            fr.free_cash_flow_cr,
            fr.fcf_cagr_5yr,
            fr.cash_from_operations_cr,
            fr.cfo_pat_ratio,
            fr.revenue_cagr_5yr,
            fr.revenue_cagr_3yr,
            fr.pat_cagr_5yr,
            fr.eps_cagr_5yr,
            fr.debt_to_equity,
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


EXPORT_COLUMNS = [
    "ticker",
    "company_name",
    "sector_name",
    "composite_quality_score",
    "return_on_equity_pct",
    "roce_percentage",
    "net_profit_margin_pct",
    "operating_profit_margin_pct",
    "free_cash_flow_cr",
    "fcf_cagr_5yr",
    "cash_from_operations_cr",
    "sales",
    "net_profit",
    "cfo_pat_ratio",
    "revenue_cagr_5yr",
    "revenue_cagr_3yr",
    "pat_cagr_5yr",
    "debt_to_equity",
    "interest_coverage",
    "pe_ratio",
    "pb_ratio",
    "dividend_yield_pct"
]


def run_screener(filters: dict[str, Any], year: int = 2024) -> pd.DataFrame:
    """
    Load the screener universe, apply filters, return a sorted DataFrame
    with composite_quality_score column added.
    """
    df = load_screener_universe(year)
    filtered = apply_filters(df, filters, year)
    
    # Sort by numeric composite_quality_score desc, then by ROE desc
    filtered = filtered.copy()
    filtered["composite_quality_score"] = pd.to_numeric(filtered["composite_quality_score"], errors="coerce").fillna(0.0)
    filtered = filtered.sort_values(
        ["composite_quality_score", "return_on_equity_pct"],
        ascending=[False, False]
    ).reset_index(drop=True)
    
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
    """Generate screener_output.xlsx with one sheet per preset, styling cells based on thresholds."""
    results = run_all_presets(year)
    config = _load_config()
    presets_meta = config.get("presets", {})
    metric_config = config.get("metrics", {})

    output_path = BASE_DIR / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        for preset_name, df in results.items():
            # Select and reorder columns for export
            cols_to_export = [c for c in EXPORT_COLUMNS if c in df.columns]
            df_export = df[cols_to_export].copy()

            sheet_label = presets_meta[preset_name]["label"][:31]  # Excel sheet name max 31 chars
            df_export.to_excel(writer, sheet_name=sheet_label, index=False)
            
            # Apply cell styling
            sheet = writer.sheets[sheet_label]
            preset = presets_meta[preset_name]
            filters = preset.get("filters", {})
            
            # Build active filters mapping for this preset
            active_cols = {}
            for metric_key, threshold in filters.items():
                if metric_key in metric_config:
                    spec = metric_config[metric_key]
                    col = spec["column"]
                    direction = spec["direction"]
                    financials_exempt = spec.get("financials_de_exempt", False)
                    debt_free_inf = spec.get("debt_free_as_infinity", False)
                    
                    if col not in active_cols:
                        active_cols[col] = []
                    active_cols[col].append({
                        "threshold": threshold,
                        "direction": direction,
                        "financials_exempt": financials_exempt,
                        "debt_free_inf": debt_free_inf
                    })
            
            # Define cell highlighting styles
            green_fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
            green_font = Font(color="006100", bold=True)
            red_fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
            red_font = Font(color="9C0006")
            
            for col_idx, col_name in enumerate(cols_to_export, start=1):
                if col_name in active_cols:
                    for row_idx in range(2, sheet.max_row + 1):
                        df_idx = row_idx - 2
                        cell = sheet.cell(row=row_idx, column=col_idx)
                        val = cell.value
                        
                        # Lookup sector and icr_label from source DataFrame df
                        sector_val = df.loc[df_idx, "sector_name"] if "sector_name" in df.columns else None
                        icr_label_val = df.loc[df_idx, "icr_label"] if "icr_label" in df.columns else None
                        
                        passed = True
                        for f in active_cols[col_name]:
                            threshold = f["threshold"]
                            direction = f["direction"]
                            financials_exempt = f["financials_exempt"]
                            debt_free_inf = f["debt_free_inf"]
                            
                            # Check D/E sector exemption
                            if financials_exempt and sector_val == "Financials":
                                continue
                            # Check ICR debt free label exemption
                            if debt_free_inf and icr_label_val == "Debt Free":
                                continue
                                
                            if val is None or pd.isna(val):
                                passed = False
                                break
                            
                            try:
                                val_float = float(val)
                                thresh_float = float(threshold)
                                if direction == "min":
                                    if val_float < thresh_float:
                                        passed = False
                                        break
                                else: # max
                                    if val_float > thresh_float:
                                        passed = False
                                        break
                            except ValueError:
                                passed = False
                                break
                                
                        if passed:
                            cell.fill = green_fill
                            cell.font = green_font
                        else:
                            cell.fill = red_fill
                            cell.font = red_font
                            
            logger.info(f"  Sheet '{sheet_label}': {len(df)} companies")

    logger.info(f"screener_output.xlsx saved to {output_path}")


if __name__ == "__main__":
    generate_screener_output()
