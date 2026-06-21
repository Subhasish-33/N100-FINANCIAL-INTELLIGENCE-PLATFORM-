import os
import pandas as pd
from pathlib import Path
from src.etl.loader import load_excel

def validate_data():
    base_dir = Path(__file__).parent.parent.parent
    raw_dir = base_dir / "data" / "raw"
    output_dir = base_dir / "output"
    output_dir.mkdir(exist_ok=True)
    
    failures = []
    
    def log_failure(rule_id, severity, file_name, row_id, desc):
        failures.append({
            "rule_id": rule_id,
            "severity": severity,
            "file_name": file_name,
            "row_identifier": row_id,
            "description": desc
        })

    # Load Data
    try:
        companies_df = load_excel(raw_dir / "companies.xlsx")
        pnl_df = load_excel(raw_dir / "profitandloss.xlsx")
        bs_df = load_excel(raw_dir / "balancesheet.xlsx")
        cf_df = load_excel(raw_dir / "cashflow.xlsx")
    except Exception as e:
        print(f"Error loading files: {e}")
        return
        
    # Standardize names for validation
    companies_df.rename(columns={'id': 'ticker'}, inplace=True)
    pnl_df.rename(columns={'company_id': 'ticker'}, inplace=True)
    bs_df.rename(columns={'company_id': 'ticker'}, inplace=True)
    cf_df.rename(columns={'company_id': 'ticker'}, inplace=True)

    companies_df['ticker'] = companies_df['ticker'].astype(str).str.strip()
    pnl_df['ticker'] = pnl_df['ticker'].astype(str).str.strip()
    bs_df['ticker'] = bs_df['ticker'].astype(str).str.strip()
    cf_df['ticker'] = cf_df['ticker'].astype(str).str.strip()

    # CRITICAL RULES
    
    # DQ-01: companies.xlsx - Ticker unique and non-null
    null_tickers = companies_df[companies_df['ticker'].isnull() | (companies_df['ticker'] == '') | (companies_df['ticker'] == 'nan')]
    for _, row in null_tickers.iterrows():
        log_failure("DQ-01", "CRITICAL", "companies.xlsx", "N/A", "Ticker is null or empty")
        
    dup_tickers = companies_df[companies_df.duplicated(subset=['ticker'], keep=False)]
    for _, row in dup_tickers.iterrows():
        log_failure("DQ-01", "CRITICAL", "companies.xlsx", row.get('ticker', 'N/A'), "Duplicate ticker found")

    # Helper for PK validation
    def validate_pk(df, file_name, rule_id):
        if 'ticker' not in df.columns or 'year' not in df.columns:
            return
        null_pk = df[df['ticker'].isnull() | (df['ticker'] == '') | (df['ticker'] == 'nan') | df['year'].isnull()]
        for _, row in null_pk.iterrows():
            log_failure(rule_id, "CRITICAL", file_name, f"Index: {_}", "Ticker or Year is null")
            
        dups = df[df.duplicated(subset=['ticker', 'year'], keep=False)]
        for _, row in dups.iterrows():
            log_failure(rule_id, "CRITICAL", file_name, f"{row['ticker']}-{row['year']}", "Duplicate Ticker and Year combination")

    # DQ-02 to DQ-04
    validate_pk(pnl_df, "profitandloss.xlsx", "DQ-02")
    validate_pk(bs_df, "balancesheet.xlsx", "DQ-03")
    validate_pk(cf_df, "cashflow.xlsx", "DQ-04")
    
    valid_tickers = set(companies_df['ticker'].dropna())

    # Helper for FK validation
    def validate_fk(df, file_name, rule_id):
        if 'ticker' not in df.columns:
            return
        invalid_fks = df[~df['ticker'].isin(valid_tickers) & df['ticker'].notnull() & (df['ticker'] != '') & (df['ticker'] != 'nan')]
        for _, row in invalid_fks.iterrows():
            log_failure(rule_id, "CRITICAL", file_name, f"{row['ticker']}-{row.get('year', '')}", f"Ticker {row['ticker']} not found in companies.xlsx")

    # DQ-05 to DQ-07
    validate_fk(pnl_df, "profitandloss.xlsx", "DQ-05")
    validate_fk(bs_df, "balancesheet.xlsx", "DQ-06")
    validate_fk(cf_df, "cashflow.xlsx", "DQ-07")

    # DQ-08: Critical numeric fields cannot be null
    if 'sales' in pnl_df.columns:
        null_sales = pnl_df[pnl_df['sales'].isnull()]
        for _, row in null_sales.iterrows():
            log_failure("DQ-08", "CRITICAL", "profitandloss.xlsx", f"{row.get('ticker', '')}-{row.get('year', '')}", "Sales field is null")
            
    if 'total_assets' in bs_df.columns:
        null_assets = bs_df[bs_df['total_assets'].isnull()]
        for _, row in null_assets.iterrows():
            log_failure("DQ-08", "CRITICAL", "balancesheet.xlsx", f"{row.get('ticker', '')}-{row.get('year', '')}", "Total Assets field is null")

    # WARNING RULES
    
    # DQ-09: Balance Sheet Equation (Assets = Liabilities)
    if 'total_assets' in bs_df.columns and 'total_liabilities' in bs_df.columns:
        # Some tables might have 'equity_capital' and 'reserves' instead of total equity
        # Usually total_liabilities in screener includes equity
        bs_df['diff'] = abs(pd.to_numeric(bs_df['total_assets'], errors='coerce').fillna(0) - pd.to_numeric(bs_df['total_liabilities'], errors='coerce').fillna(0))
        unbalanced = bs_df[bs_df['diff'] > 1.0] # Allow small floating point tolerance
        for _, row in unbalanced.iterrows():
             log_failure("DQ-09", "WARNING", "balancesheet.xlsx", f"{row.get('ticker', '')}-{row.get('year', '')}", f"Total Assets ({row.get('total_assets')}) != Total Liabilities ({row.get('total_liabilities')})")

    # DQ-10: Sales >= 0
    if 'sales' in pnl_df.columns:
        pnl_df['sales_num'] = pd.to_numeric(pnl_df['sales'], errors='coerce')
        neg_sales = pnl_df[pnl_df['sales_num'] < 0]
        for _, row in neg_sales.iterrows():
             log_failure("DQ-10", "WARNING", "profitandloss.xlsx", f"{row.get('ticker', '')}-{row.get('year', '')}", f"Sales is negative: {row.get('sales')}")

    # DQ-11: OPM calculation check
    if 'operating_profit' in pnl_df.columns and 'sales' in pnl_df.columns and 'opm_percentage' in pnl_df.columns:
        for _, row in pnl_df.iterrows():
            s = pd.to_numeric(row['sales'], errors='coerce')
            op = pd.to_numeric(row['operating_profit'], errors='coerce')
            opm = pd.to_numeric(row['opm_percentage'], errors='coerce')
            if pd.notnull(s) and pd.notnull(op) and s != 0:
                expected_opm = (op / s) * 100
                actual_opm = opm if pd.notnull(opm) else 0
                if abs(expected_opm - actual_opm) > 5.0: # 5% tolerance
                    log_failure("DQ-11", "WARNING", "profitandloss.xlsx", f"{row.get('ticker', '')}-{row.get('year', '')}", f"OPM discrepancy. Actual: {actual_opm}, Expected: {expected_opm:.2f}")

    # DQ-12: Cash >= 0
    cash_col = [c for c in bs_df.columns if 'cash' in c.lower() or 'asset' in c.lower()]
    # actually there is no cash column explicitly in BS, just other_asset or total_assets.
    if 'other_asset' in bs_df.columns:
        neg_cash = bs_df[pd.to_numeric(bs_df['other_asset'], errors='coerce') < 0]
        for _, row in neg_cash.iterrows():
             log_failure("DQ-12", "WARNING", "balancesheet.xlsx", f"{row.get('ticker', '')}-{row.get('year', '')}", f"Other assets is negative: {row.get('other_asset')}")

    # DQ-13: Borrowings >= 0
    if 'borrowings' in bs_df.columns:
        neg_borrow = bs_df[pd.to_numeric(bs_df['borrowings'], errors='coerce') < 0]
        for _, row in neg_borrow.iterrows():
             log_failure("DQ-13", "WARNING", "balancesheet.xlsx", f"{row.get('ticker', '')}-{row.get('year', '')}", f"Borrowings is negative: {row.get('borrowings')}")

    # DQ-14: Tax % between 0 and 50
    if 'tax_percentage' in pnl_df.columns:
        tax = pd.to_numeric(pnl_df['tax_percentage'], errors='coerce')
        invalid_tax = pnl_df[(tax < 0) | (tax > 50)]
        for _, row in invalid_tax.iterrows():
             log_failure("DQ-14", "WARNING", "profitandloss.xlsx", f"{row.get('ticker', '')}-{row.get('year', '')}", f"Tax percent out of bounds [0, 50]: {row.get('tax_percentage')}")

    # DQ-15: Depreciation not negative
    if 'depreciation' in pnl_df.columns:
        neg_dep = pnl_df[pd.to_numeric(pnl_df['depreciation'], errors='coerce') < 0]
        for _, row in neg_dep.iterrows():
             log_failure("DQ-15", "WARNING", "profitandloss.xlsx", f"{row.get('ticker', '')}-{row.get('year', '')}", f"Depreciation is negative: {row.get('depreciation')}")

    # DQ-16: Cash Flow Consistency (Net CF ~ Operating + Investing + Financing)
    req_cf_cols = ['operating_activity', 'investing_activity', 'financing_activity', 'net_cash_flow']
    if all(c in cf_df.columns for c in req_cf_cols):
        for _, row in cf_df.iterrows():
            o = pd.to_numeric(row['operating_activity'], errors='coerce') or 0
            i = pd.to_numeric(row['investing_activity'], errors='coerce') or 0
            f = pd.to_numeric(row['financing_activity'], errors='coerce') or 0
            n = pd.to_numeric(row['net_cash_flow'], errors='coerce') or 0
            calc_net = o + i + f
            if abs(n - calc_net) > 2.0: # Tolerance
                log_failure("DQ-16", "WARNING", "cashflow.xlsx", f"{row.get('ticker', '')}-{row.get('year', '')}", f"Net Cash Flow mismatch. Actual: {n}, Calc: {calc_net}")

    failures_df = pd.DataFrame(failures)
    out_file = output_dir / "validation_failures.csv"
    if failures_df.empty:
        failures_df = pd.DataFrame(columns=["rule_id", "severity", "file_name", "row_identifier", "description"])
    failures_df.to_csv(out_file, index=False)
    print(f"Validation complete. {len(failures)} failures found. Logged to {out_file}")

if __name__ == "__main__":
    validate_data()
