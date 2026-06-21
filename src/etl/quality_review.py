import sqlite3
import random
from pathlib import Path

def main():
    base_dir = Path(__file__).parent.parent.parent
    db_path = base_dir / "data" / "database.sqlite"
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get all companies
    cursor.execute("SELECT ticker FROM companies")
    all_companies = [row[0] for row in cursor.fetchall()]
    
    # 1. 5 random companies coverage
    random_samples = random.sample(all_companies, 5)
    print("--- 5 RANDOM COMPANIES YEAR COVERAGE ---")
    for ticker in random_samples:
        cursor.execute("SELECT year FROM profit_and_loss WHERE ticker = ? ORDER BY year", (ticker,))
        pnl_years = [str(r[0]) for r in cursor.fetchall()]
        
        cursor.execute("SELECT year FROM balance_sheet WHERE ticker = ? ORDER BY year", (ticker,))
        bs_years = [str(r[0]) for r in cursor.fetchall()]
        
        cursor.execute("SELECT year FROM cash_flow WHERE ticker = ? ORDER BY year", (ticker,))
        cf_years = [str(r[0]) for r in cursor.fetchall()]
        
        print(f"[{ticker}]")
        print(f"  P&L : {', '.join(pnl_years) if pnl_years else 'None'}")
        print(f"  BS  : {', '.join(bs_years) if bs_years else 'None'}")
        print(f"  CF  : {', '.join(cf_years) if cf_years else 'None'}\n")
        
    # 2. Companies with < 5 years of data
    print("--- COMPANIES WITH < 5 YEARS DATA ---")
    query = """
        SELECT c.ticker, 
               COUNT(DISTINCT p.year) as pnl_count,
               COUNT(DISTINCT b.year) as bs_count,
               COUNT(DISTINCT cf.year) as cf_count
        FROM companies c
        LEFT JOIN profit_and_loss p ON c.ticker = p.ticker
        LEFT JOIN balance_sheet b ON c.ticker = b.ticker
        LEFT JOIN cash_flow cf ON c.ticker = cf.ticker
        GROUP BY c.ticker
        HAVING pnl_count < 5 OR bs_count < 5 OR cf_count < 5
    """
    cursor.execute(query)
    under_5 = cursor.fetchall()
    
    if under_5:
        for row in under_5:
            print(f"Ticker: {row[0]:<15} P&L: {row[1]:<3} BS: {row[2]:<3} CF: {row[3]:<3}")
    else:
        print("No companies found with less than 5 years of data.")
        
    conn.close()

if __name__ == "__main__":
    main()
