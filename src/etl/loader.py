import re
import sqlite3
from pathlib import Path
from typing import Optional, Union
import pandas as pd


# ---------------------------------------------------------------------------
# Public normalisation helpers (raise ValueError on bad input)
# ---------------------------------------------------------------------------

def normalize_year(year: Union[str, int]) -> int:
    """Return a 4-digit calendar year from various representations.

    Accepts int (2023, 23, 99), str ("2023", "FY23", "CY2023",
    "2022-23", "22-23", " 2023 ") and raises ValueError for anything
    that cannot be parsed.
    """
    # NaN float – the only non-str/int we silently skip
    if isinstance(year, float):
        if pd.isna(year):
            raise ValueError(f"Cannot normalize NaN year value")
        year = int(year)

    if isinstance(year, int):
        if year < 100:
            return 2000 + year if year < 50 else 1900 + year
        return year

    year_str = str(year).strip().upper()
    if not year_str:
        raise ValueError("Cannot normalize empty year string")

    # Range format: "2022-23" / "22-23" / "2022-2023"
    range_match = re.search(r'(\d{2,4})\s*-\s*(\d{2,4})', year_str)
    if range_match:
        end_year = int(range_match.group(2))
        return 2000 + end_year if end_year < 50 else (1900 + end_year if end_year < 100 else end_year)

    digits_match = re.findall(r'\d+', year_str)
    if not digits_match:
        raise ValueError(f"Cannot parse year from: '{year}'")

    extracted = int(digits_match[-1])
    if extracted < 100:
        return 2000 + extracted if extracted < 50 else 1900 + extracted
    return extracted


def normalize_ticker(ticker: str) -> str:
    """Return a clean, upper-case NSE ticker symbol.

    Strips exchange suffixes (.NS, .BO, :IN, .IS, ' IN', ' BO', ' NS').
    Raises ValueError for non-string input, empty/whitespace-only strings,
    or values that reduce to nothing after suffix removal.
    """
    if not isinstance(ticker, str):
        raise ValueError(
            f"ticker must be a str, got {type(ticker).__name__!r}: {ticker!r}"
        )
    stripped = ticker.strip()
    if not stripped:
        raise ValueError(f"ticker cannot be empty or whitespace-only: {ticker!r}")

    upper = stripped.upper()
    suffixes = [".NS", ".BO", ":IN", ".IS", " IN", " BO", " NS"]
    for suffix in suffixes:
        if upper.endswith(suffix):
            upper = upper[: -len(suffix)].strip()
            break

    if not upper:
        raise ValueError(
            f"ticker '{ticker}' has no meaningful content after suffix removal"
        )
    return upper


# ---------------------------------------------------------------------------
# Internal safe wrappers (used by load_all_data apply() calls)
# ---------------------------------------------------------------------------

def _safe_normalize_ticker(ticker) -> Optional[str]:
    """For ETL pipeline use: returns None on any error instead of raising."""
    try:
        return normalize_ticker(ticker)
    except (ValueError, TypeError):
        return None


def _safe_normalize_year(year) -> Optional[int]:
    """For ETL pipeline use: returns None on any error instead of raising."""
    try:
        return normalize_year(year)
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Excel loader
# ---------------------------------------------------------------------------

def load_excel(file_path: Union[str, Path], sheet_name: Union[int, str] = 0) -> pd.DataFrame:
    """Load a single sheet from an Excel file and normalise column names.

    Args:
        file_path: Path to the .xlsx file.
        sheet_name: Sheet index (int) or sheet name (str). Defaults to 0.

    Returns:
        DataFrame with lower-snake-case column names.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file cannot be read as Excel.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Excel file not found: {file_path}")

    try:
        df = pd.read_excel(path, sheet_name=sheet_name)
    except Exception as exc:
        raise ValueError(f"Failed to read Excel file '{file_path}': {exc}") from exc

    # Auto-detect secondary header row: if columns look unnamed or pipe-delimited
    col_str = str(list(df.columns)).lower()
    if "unnamed" in col_str or "|" in col_str:
        if not df.empty:
            df.columns = df.iloc[0]
            df = df.drop(index=0).reset_index(drop=True)

    df.columns = [
        str(c).strip().lower()
        .replace(" ", "_")
        .replace("\n", "_")
        .replace(".", "")
        for c in df.columns
    ]
    return df


# ---------------------------------------------------------------------------
# Database creation
# ---------------------------------------------------------------------------

def create_database(base_dir: Path):
    db_path = base_dir / "data" / "database.sqlite"
    # Wipe existing DB if any to ensure clean state
    if db_path.exists():
        db_path.unlink()

    schema_path = base_dir / "src" / "etl" / "schema.sql"
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")

    with open(schema_path, 'r') as f:
        schema_sql = f.read()
    conn.executescript(schema_sql)
    return conn


# ---------------------------------------------------------------------------
# Full ETL pipeline
# ---------------------------------------------------------------------------

def load_all_data():
    base_dir = Path(__file__).parent.parent.parent
    raw_dir = base_dir / "data" / "raw"
    supp_dir = base_dir / "data" / "supporting"
    out_dir = base_dir / "output"
    out_dir.mkdir(exist_ok=True)

    conn = create_database(base_dir)
    audit_log = []

    # 1. Load sectors (extract unique sectors)
    sectors_df = load_excel(supp_dir / "sectors.xlsx")
    unique_sectors = sectors_df['broad_sector'].dropna().unique()
    sector_mapping = {sec: idx + 1 for idx, sec in enumerate(unique_sectors)}

    sectors_data = pd.DataFrame(
        [{"sector_id": v, "sector_name": k} for k, v in sector_mapping.items()]
    )
    sectors_data.to_sql("sectors", conn, if_exists="append", index=False)
    audit_log.append({"table_name": "sectors", "rows_loaded": len(sectors_data)})

    # 2. Load companies
    companies_df = load_excel(raw_dir / "companies.xlsx")
    companies_df.rename(columns={'id': 'ticker'}, inplace=True)
    companies_df['ticker'] = companies_df['ticker'].apply(_safe_normalize_ticker)
    companies_df = companies_df.dropna(subset=['ticker'])
    companies_df.drop_duplicates(subset=['ticker'], inplace=True)

    sectors_df.rename(columns={'company_id': 'ticker'}, inplace=True)
    sectors_df['ticker'] = sectors_df['ticker'].apply(_safe_normalize_ticker)
    sectors_df['sector_id'] = sectors_df['broad_sector'].map(sector_mapping)

    comp_merged = pd.merge(
        companies_df,
        sectors_df[['ticker', 'sector_id']].drop_duplicates('ticker'),
        on='ticker', how='left'
    )
    company_cols = [
        'ticker', 'company_name', 'company_logo', 'about_company',
        'website', 'nse_profile', 'bse_profile', 'sector_id'
    ]
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
            df['ticker'] = df['ticker'].apply(_safe_normalize_ticker)
            df = df.dropna(subset=['ticker'])
            df = df[df['ticker'].isin(valid_tickers)]

        if 'year' in df.columns:
            df['year'] = df['year'].apply(_safe_normalize_year)
            df = df.dropna(subset=['year'])

        if pk_cols:
            df.drop_duplicates(subset=pk_cols, inplace=True)

        for col in columns:
            if col not in df.columns:
                df[col] = None
        df[columns].to_sql(table_name, conn, if_exists="append", index=False)
        audit_log.append({"table_name": table_name, "rows_loaded": len(df)})

    # P&L
    process_and_load(
        raw_dir / "profitandloss.xlsx", "profit_and_loss",
        ['ticker', 'year', 'sales', 'expenses', 'operating_profit', 'opm_percentage',
         'other_income', 'interest', 'depreciation', 'profit_before_tax',
         'tax_percentage', 'net_profit', 'eps', 'dividend_payout'],
        ['ticker', 'year']
    )

    # Balance Sheet
    process_and_load(
        raw_dir / "balancesheet.xlsx", "balance_sheet",
        ['ticker', 'year', 'equity_capital', 'reserves', 'borrowings',
         'other_liabilities', 'total_liabilities', 'fixed_assets', 'cwip',
         'investments', 'other_asset', 'total_assets'],
        ['ticker', 'year']
    )

    # Cash Flow
    process_and_load(
        raw_dir / "cashflow.xlsx", "cash_flow",
        ['ticker', 'year', 'operating_activity', 'investing_activity',
         'financing_activity', 'net_cash_flow'],
        ['ticker', 'year']
    )

    # Financial Ratios
    process_and_load(
        supp_dir / "financial_ratios.xlsx", "financial_ratios",
        ['ticker', 'year', 'roce_percentage', 'roe_percentage', 'debtor_days',
         'inventory_days', 'days_payable', 'cash_conversion_cycle', 'working_capital_days'],
        ['ticker', 'year']
    )

    # Market Cap
    process_and_load(
        supp_dir / "market_cap.xlsx", "market_cap",
        ['ticker', 'year', 'market_cap'],
        ['ticker', 'year']
    )

    # Stock Prices
    process_and_load(
        supp_dir / "stock_prices.xlsx", "stock_prices",
        ['ticker', 'date', 'open', 'high', 'low', 'close', 'volume'],
        ['ticker', 'date']
    )

    # Peer Groups
    process_and_load(
        supp_dir / "peer_groups.xlsx", "peer_groups",
        ['peer_group_name', 'ticker']
    )

    # Documents
    process_and_load(
        raw_dir / "documents.xlsx", "documents",
        ['ticker', 'year', 'title', 'document_type', 'url']
    )

    # Analysis
    process_and_load(
        raw_dir / "analysis.xlsx", "analysis",
        ['ticker', 'compounded_sales_growth', 'compounded_profit_growth',
         'stock_price_cagr', 'roe']
    )

    # Pros and Cons
    process_and_load(
        raw_dir / "prosandcons.xlsx", "pros_and_cons",
        ['ticker', 'pros', 'cons']
    )

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
