"""
src/screener/data_quality.py
Data quality checks and validation for the Nifty 100 Screener.
"""

import sqlite3
import yaml
import logging
from pathlib import Path
import pandas as pd

logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "screener_config.yaml"
DB_PATH = Path(__file__).parent.parent.parent / "data" / "database.sqlite"
OUTPUT_DIR = Path(__file__).parent.parent.parent / "output"

def load_screener_metrics():
    """Load the core metric columns from the screener configuration."""
    if not CONFIG_PATH.exists():
        logger.warning("Config not found, falling back to empty metrics.")
        return []
    
    with open(CONFIG_PATH, "r") as f:
        config = yaml.safe_load(f)
        
    metrics = config.get("metrics", {})
    return [m["column"] for m in metrics.values()]

def check_null_coverage(year: int, db_path: Path = DB_PATH) -> pd.DataFrame:
    """
    Check the percentage of missing (NULL) values for all core screener metrics
    and the composite_quality_score for a given year.
    Returns a DataFrame with columns: ['metric', 'missing_count', 'total_count', 'missing_pct', 'status']
    """
    metrics_to_check = load_screener_metrics()
    if "composite_quality_score" not in metrics_to_check:
        metrics_to_check.append("composite_quality_score")
        
    # We join financial_ratios, market_data, and profit_and_loss to get all possible metrics
    query = f"""
    SELECT 
        fr.*, 
        md.pe_ratio, md.pb_ratio, md.dividend_yield_pct, md.market_cap_crore,
        pl.net_profit, pl.sales
    FROM companies c
    JOIN financial_ratios fr ON c.ticker = fr.ticker AND fr.year = {year}
    LEFT JOIN market_data md ON c.ticker = md.ticker AND md.year = {year}
    LEFT JOIN profit_and_loss pl ON c.ticker = pl.ticker AND pl.year = {year}
    """
    
    try:
        with sqlite3.connect(db_path) as conn:
            df = pd.read_sql_query(query, conn)
    except sqlite3.OperationalError as e:
        logger.error(f"Error reading from database: {e}")
        return pd.DataFrame()
        
    results = []
    total_count = len(df)
    
    if total_count == 0:
        logger.warning(f"No data found for year {year}")
        return pd.DataFrame()
        
    for metric in metrics_to_check:
        if metric in df.columns:
            missing = int(df[metric].isna().sum())
            missing_pct = round((missing / total_count) * 100, 2)
            status = "FAIL (>15% missing)" if missing_pct > 15 else "PASS"
            
            results.append({
                "metric": metric,
                "missing_count": missing,
                "total_count": total_count,
                "missing_pct": missing_pct,
                "status": status
            })
        else:
            results.append({
                "metric": metric,
                "missing_count": total_count,
                "total_count": total_count,
                "missing_pct": 100.0,
                "status": "FAIL (Column not found)"
            })
            
    return pd.DataFrame(results)

def check_range_validity(year: int, db_path: Path = DB_PATH) -> pd.DataFrame:
    """
    Check for impossible or extreme values in the dataset for a given year.
    Returns a DataFrame of validation warnings.
    """
    query = f"""
    SELECT 
        c.ticker as symbol,
        fr.composite_quality_score,
        md.pe_ratio,
        fr.return_on_equity_pct
    FROM companies c
    JOIN financial_ratios fr ON c.ticker = fr.ticker AND fr.year = {year}
    LEFT JOIN market_data md ON c.ticker = md.ticker AND md.year = {year}
    """
    
    with sqlite3.connect(db_path) as conn:
        df = pd.read_sql_query(query, conn)
        
    warnings = []
    
    for _, row in df.iterrows():
        sym = row["symbol"]
        cqs = row["composite_quality_score"]
        pe = row["pe_ratio"]
        
        # Composite score bounds check
        try:
            cqs_val = float(cqs) if pd.notna(cqs) and cqs != "" else None
        except ValueError:
            cqs_val = None
            
        if cqs_val is not None and (cqs_val < 0.0 or cqs_val > 100.0):
            warnings.append({
                "symbol": sym,
                "check": "composite_quality_score bounds",
                "value": cqs,
                "message": "Score outside [0, 100] range"
            })
            
        # PE ratio checks
        if pd.notna(pe) and pe < 0:
             warnings.append({
                "symbol": sym,
                "check": "negative pe_ratio",
                "value": pe,
                "message": "P/E ratio cannot be negative in this dataset (should be null or >0)"
            })
            
    return pd.DataFrame(warnings)

def check_market_data_presence(year: int, db_path: Path = DB_PATH) -> pd.DataFrame:
    """
    Ensure every company in financial_ratios has market_data.
    """
    query = f"""
    SELECT 
        fr.ticker as symbol_fr,
        md.ticker as symbol_md
    FROM financial_ratios fr
    LEFT JOIN market_data md ON fr.ticker = md.ticker AND md.year = fr.year
    WHERE fr.year = {year}
    """
    with sqlite3.connect(db_path) as conn:
        df = pd.read_sql_query(query, conn)
        
    missing = df[df['symbol_md'].isna()]['symbol_fr'].tolist()
    
    if not missing:
        return pd.DataFrame([{"check": "Market Data completeness", "status": "PASS", "missing_symbols": "None"}])
    else:
        return pd.DataFrame([{
            "check": "Market Data completeness", 
            "status": "FAIL", 
            "missing_symbols": ", ".join(missing)
        }])

def generate_data_quality_report(year: int, db_path: Path = DB_PATH, output_path: Path = None):
    """
    Run all checks and export a combined report to CSV.
    """
    if output_path is None:
        output_path = OUTPUT_DIR / "data_quality_report.csv"
        
    OUTPUT_DIR.mkdir(exist_ok=True)
    
    null_df = check_null_coverage(year, db_path)
    range_df = check_range_validity(year, db_path)
    market_df = check_market_data_presence(year, db_path)
    
    with open(output_path, "w") as f:
        f.write(f"--- DATA QUALITY REPORT FOR YEAR {year} ---\n\n")
        
        f.write("1. NULL COVERAGE\n")
        if not null_df.empty:
            null_df.to_csv(f, index=False)
        else:
            f.write("No data.\n")
            
        f.write("\n2. RANGE VALIDITY WARNINGS\n")
        if not range_df.empty:
            range_df.to_csv(f, index=False)
        else:
            f.write("PASS: No out-of-bounds or extreme values detected.\n")
            
        f.write("\n3. MARKET DATA PRESENCE\n")
        market_df.to_csv(f, index=False)
        
    logger.info(f"Data quality report saved to {output_path}")

if __name__ == "__main__":
    generate_data_quality_report(2024)
