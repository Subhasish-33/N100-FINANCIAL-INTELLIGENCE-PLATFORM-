import pandas as pd
import sqlite3
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def run_cross_check():
    base_dir = Path(__file__).parent.parent.parent
    db_path = base_dir / "data" / "database.sqlite"
    companies_path = base_dir / "data" / "raw" / "companies.xlsx"
    out_log = base_dir / "output" / "ratio_edge_cases.log"

    if not db_path.exists() or not companies_path.exists():
        logger.error("Missing required files.")
        return

    from src.etl.loader import load_excel

    # Load raw expected data
    companies_df = load_excel(companies_path)
    if 'id' in companies_df.columns:
        companies_df.rename(columns={'id': 'ticker'}, inplace=True)
    elif 'company_id' in companies_df.columns:
        companies_df.rename(columns={'company_id': 'ticker'}, inplace=True)
    
    companies_df['ticker'] = companies_df['ticker'].astype(str).str.strip().str.upper().str.replace(r'\.NS$', '', regex=True)

    # We need roce_percentage and roe_percentage
    if 'roce_percentage' not in companies_df.columns or 'roe_percentage' not in companies_df.columns:
        logger.error("Missing ROCE/ROE in companies.xlsx")
        return

    conn = sqlite3.connect(db_path)
    # Fetch latest computed values from database
    query = """
        SELECT ticker, return_on_equity_pct, roce_percentage as computed_roce
        FROM financial_ratios
        WHERE year = 2024
    """
    db_df = pd.read_sql(query, conn)
    conn.close()

    merged = pd.merge(companies_df[['ticker', 'roce_percentage', 'roe_percentage']], db_df, on='ticker', how='inner')

    out_log.parent.mkdir(parents=True, exist_ok=True)
    
    with open(out_log, "w") as f:
        f.write("Ratio Edge Cases Log\n")
        f.write("====================\n\n")

        for _, row in merged.iterrows():
            ticker = row['ticker']
            source_roce = row['roce_percentage']
            computed_roce = row['computed_roce']
            source_roe = row['roe_percentage']
            computed_roe = row['return_on_equity_pct']

            # Check ROCE
            if pd.notna(source_roce) and pd.notna(computed_roce):
                diff_roce = abs(source_roce - computed_roce)
                if diff_roce > 5.0:
                    category = "Formula Discrepancy (e.g. EBIT vs PBT)"
                    f.write(f"[{ticker}] ROCE Anomaly: Source={source_roce:.2f}, Computed={computed_roce:.2f}, Diff={diff_roce:.2f} -> Category: {category}\n")

            # Check ROE
            if pd.notna(source_roe) and pd.notna(computed_roe):
                # source_roe is sometimes provided as fraction instead of pct e.g. TCS 0.52 instead of 52
                diff_roe = abs(source_roe - computed_roe)
                if diff_roe > 5.0:
                    category = "Formula Discrepancy"
                    if source_roe < 2.0 and computed_roe > 10.0:
                        category = "Data Source Issue (fraction vs pct)"
                    elif diff_roe > 50.0:
                        category = "Version Difference or Data Source Issue"
                    f.write(f"[{ticker}] ROE Anomaly: Source={source_roe:.2f}, Computed={computed_roe:.2f}, Diff={diff_roe:.2f} -> Category: {category}\n")

    logger.info(f"Cross check completed. See {out_log}")

if __name__ == "__main__":
    run_cross_check()
