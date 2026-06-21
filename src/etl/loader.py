import re
import sqlite3
from pathlib import Path
from typing import Union
import pandas as pd

def normalize_year(year: Union[str, int]) -> int:
    if pd.isna(year):
        return None
    if isinstance(year, int):
        if year < 100:
            return 2000 + year if year < 50 else 1900 + year
        return year
    year_str = str(year).strip().upper()
    if not year_str:
        return None
    range_match = re.search(r'(\d{2,4})\s*-\s*(\d{2,4})', year_str)
    if range_match:
        end_year = int(range_match.group(2))
        return 2000 + end_year if end_year < 50 else (1900 + end_year if end_year < 100 else end_year)
    digits_match = re.findall(r'\d+', year_str)
    if not digits_match:
        return None
    extracted = int(digits_match[-1])
    if extracted < 100:
        return 2000 + extracted if extracted < 50 else 1900 + extracted
    return extracted

def normalize_ticker(ticker: str) -> str:
    if pd.isna(ticker) or not str(ticker).strip():
        return None
    ticker = str(ticker).strip().upper()
    suffixes = [".NS", ".BO", ":IN", ".IS", " IN", " BO", " NS"]
    for suffix in suffixes:
        if ticker.endswith(suffix):
            ticker = ticker[:-len(suffix)].strip()
            break
    return ticker if ticker else None

def load_excel(file_path: Union[str, Path]) -> pd.DataFrame:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Not found: {file_path}")
        
    df0 = pd.read_excel(path, nrows=1)
    if 'unnamed' in str(df0.columns).lower() or '|' in str(df0.columns):
        df = pd.read_excel(path, header=1)
    else:
        df = pd.read_excel(path)
        
    df.columns = [str(c).strip().lower().replace(" ", "_").replace("\n", "_").replace(".", "") for c in df.columns]
    return df

def create_database(base_dir: Path):
    db_path = base_dir / "data" / "database.sqlite"
    # wipe existing DB if any to ensure clean state
    if db_path.exists():
        db_path.unlink()
        
    schema_path = base_dir / "src" / "etl" / "schema.sql"
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    
    with open(schema_path, 'r') as f:
        schema_sql = f.read()
    conn.executescript(schema_sql)
    return conn

def load_all_data():
    base_dir = Path(__file__).parent.parent.parent
    raw_dir = base_dir / "data" / "raw"
    supp_dir = base_dir / "data" / "supporting"
    out_dir = base_dir / "output"
    out_dir.mkdir(exist_ok=True)
    
    conn = create_database(base_dir)
    audit_log = []

    # 1. Load sectors (Extract unique sectors)
    sectors_df = load_excel(supp_dir / "sectors.xlsx")
    unique_sectors = sectors_df['broad_sector'].dropna().unique()
    sector_mapping = {sec: idx+1 for idx, sec in enumerate(unique_sectors)}
    
    sectors_data = pd.DataFrame([{"sector_id": v, "sector_name": k} for k, v in sector_mapping.items()])
    sectors_data.to_sql("sectors", conn, if_exists="append", index=False)
    audit_log.append({"table_name": "sectors", "rows_loaded": len(sectors_data)})
    
    # 2. Load companies
    companies_df = load_excel(raw_dir / "companies.xlsx")
    companies_df.rename(columns={'id': 'ticker'}, inplace=True)
    companies_df['ticker'] = companies_df['ticker'].apply(normalize_ticker)
    companies_df = companies_df.dropna(subset=['ticker'])
    companies_df.drop_duplicates(subset=['ticker'], inplace=True)
    
    sectors_df.rename(columns={'company_id': 'ticker'}, inplace=True)
    sectors_df['ticker'] = sectors_df['ticker'].apply(normalize_ticker)
    sectors_df['sector_id'] = sectors_df['broad_sector'].map(sector_mapping)
    
    comp_merged = pd.merge(companies_df, sectors_df[['ticker', 'sector_id']].drop_duplicates('ticker'), on='ticker', how='left')
    company_cols = ['ticker', 'company_name', 'company_logo', 'about_company', 'website', 'nse_profile', 'bse_profile', 'sector_id']
    for col in company_cols:
        if col not in comp_merged.columns:
            comp_merged[col] = None
            
    comp_merged[company_cols].to_sql("companies", conn, if_exists="append", index=False)
    audit_log.append({"table_name": "companies", "rows_loaded": len(comp_merged)})
    
    valid_tickers = set(comp_merged['ticker'])
    
    def process_and_load(df_path, table_name, columns, pk_cols=None):
        if not df_path.exists():
            return
        df = load_excel(df_path)
        if 'company_id' in df.columns:
            df.rename(columns={'company_id': 'ticker'}, inplace=True)
            
        if 'ticker' in df.columns:
            df['ticker'] = df['ticker'].apply(normalize_ticker)
            df = df.dropna(subset=['ticker'])
            df = df[df['ticker'].isin(valid_tickers)]
            
        if 'year' in df.columns:
            df['year'] = df['year'].apply(normalize_year)
            df = df.dropna(subset=['year'])
            
        if pk_cols:
            df.drop_duplicates(subset=pk_cols, inplace=True)
            
        for col in columns:
            if col not in df.columns:
                df[col] = None
        df[columns].to_sql(table_name, conn, if_exists="append", index=False)
        audit_log.append({"table_name": table_name, "rows_loaded": len(df)})

    # P&L
    process_and_load(raw_dir / "profitandloss.xlsx", "profit_and_loss",
                     ['ticker', 'year', 'sales', 'expenses', 'operating_profit', 'opm_percentage', 'other_income', 'interest', 'depreciation', 'profit_before_tax', 'tax_percentage', 'net_profit', 'eps', 'dividend_payout'],
                     ['ticker', 'year'])
                     
    # Balance Sheet
    process_and_load(raw_dir / "balancesheet.xlsx", "balance_sheet",
                     ['ticker', 'year', 'equity_capital', 'reserves', 'borrowings', 'other_liabilities', 'total_liabilities', 'fixed_assets', 'cwip', 'investments', 'other_asset', 'total_assets'],
                     ['ticker', 'year'])
                     
    # Cash Flow
    process_and_load(raw_dir / "cashflow.xlsx", "cash_flow",
                     ['ticker', 'year', 'operating_activity', 'investing_activity', 'financing_activity', 'net_cash_flow'],
                     ['ticker', 'year'])
                     
    # Financial Ratios
    process_and_load(supp_dir / "financial_ratios.xlsx", "financial_ratios",
                     ['ticker', 'year', 'roce_percentage', 'roe_percentage', 'debtor_days', 'inventory_days', 'days_payable', 'cash_conversion_cycle', 'working_capital_days'],
                     ['ticker', 'year'])
                     
    # Market Cap
    process_and_load(supp_dir / "market_cap.xlsx", "market_cap",
                     ['ticker', 'year', 'market_cap'],
                     ['ticker', 'year'])
                     
    # Stock Prices
    process_and_load(supp_dir / "stock_prices.xlsx", "stock_prices",
                     ['ticker', 'date', 'open', 'high', 'low', 'close', 'volume'],
                     ['ticker', 'date'])
                     
    # Peer Groups
    process_and_load(supp_dir / "peer_groups.xlsx", "peer_groups",
                     ['peer_group_name', 'ticker'])
                     
    # Documents
    process_and_load(raw_dir / "documents.xlsx", "documents",
                     ['ticker', 'year', 'title', 'document_type', 'url'])
                     
    # Analysis
    process_and_load(raw_dir / "analysis.xlsx", "analysis",
                     ['ticker', 'compounded_sales_growth', 'compounded_profit_growth', 'stock_price_cagr', 'roe'])
                     
    # Pros and Cons
    process_and_load(raw_dir / "prosandcons.xlsx", "pros_and_cons",
                     ['ticker', 'pros', 'cons'])
                     
    # Write Audit Log
    audit_df = pd.DataFrame(audit_log)
    audit_df.to_csv(out_dir / "load_audit.csv", index=False)
    
    # Check FK violations
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_key_check;")
    fk_violations = cursor.fetchall()
    
    if fk_violations:
        print(f"FOREIGN KEY VIOLATIONS DETECTED: {len(fk_violations)}")
        for v in fk_violations[:10]:
            print(v)
    else:
        print("FK check 0. Database loaded successfully.")
        
    conn.commit()
    conn.close()

if __name__ == "__main__":
    load_all_data()
