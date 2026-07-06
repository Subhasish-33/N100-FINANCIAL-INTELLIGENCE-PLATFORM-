import sqlite3
import logging
from pathlib import Path
from src.analytics.cagr import compute_cagr

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def compute_and_store_cagr():
    base_dir = Path(__file__).parent.parent.parent
    db_path = base_dir / "data" / "database.sqlite"

    if not db_path.exists():
        logger.error(f"Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get all distinct tickers
    cursor.execute("SELECT DISTINCT ticker FROM profit_and_loss")
    tickers = [row['ticker'] for row in cursor.fetchall()]

    updates = []
    for ticker in tickers:
        # Get data ordered by year
        cursor.execute("""
            SELECT year, sales, net_profit, eps 
            FROM profit_and_loss 
            WHERE ticker = ? 
            ORDER BY year ASC
        """, (ticker,))
        records = cursor.fetchall()

        if not records:
            continue

        latest_record = records[-1]
        latest_year = latest_record['year']
        end_sales = latest_record['sales']
        end_pat = latest_record['net_profit']
        end_eps = latest_record['eps']

        metrics = {}
        for years in [3, 5, 10]:
            target_start_year = latest_year - years
            # Find the record for target_start_year
            start_record = next((r for r in records if r['year'] == target_start_year), None)

            if start_record:
                # Revenue
                rev_val, rev_flag = compute_cagr(start_record['sales'] or 0, end_sales or 0, years)
                # PAT
                pat_val, pat_flag = compute_cagr(start_record['net_profit'] or 0, end_pat or 0, years)
                # EPS
                eps_val, eps_flag = compute_cagr(start_record['eps'] or 0, end_eps or 0, years)
            else:
                rev_val, rev_flag = None, "INSUFFICIENT"
                pat_val, pat_flag = None, "INSUFFICIENT"
                eps_val, eps_flag = None, "INSUFFICIENT"

            metrics[f'rev_{years}yr'] = (rev_val, rev_flag)
            metrics[f'pat_{years}yr'] = (pat_val, pat_flag)
            metrics[f'eps_{years}yr'] = (eps_val, eps_flag)

        # Make sure the ticker exists in the analysis table
        cursor.execute("SELECT id FROM analysis WHERE ticker = ?", (ticker,))
        if not cursor.fetchone():
            cursor.execute("INSERT INTO analysis (ticker) VALUES (?)", (ticker,))

        # Prepare update tuple
        updates.append((
            metrics['rev_3yr'][0], metrics['rev_3yr'][1],
            metrics['rev_5yr'][0], metrics['rev_5yr'][1],
            metrics['rev_10yr'][0], metrics['rev_10yr'][1],
            metrics['pat_3yr'][0], metrics['pat_3yr'][1],
            metrics['pat_5yr'][0], metrics['pat_5yr'][1],
            metrics['pat_10yr'][0], metrics['pat_10yr'][1],
            metrics['eps_3yr'][0], metrics['eps_3yr'][1],
            metrics['eps_5yr'][0], metrics['eps_5yr'][1],
            metrics['eps_10yr'][0], metrics['eps_10yr'][1],
            ticker
        ))

    update_query = """
        UPDATE analysis
        SET
            revenue_cagr_3yr = ?, revenue_cagr_3yr_flag = ?,
            revenue_cagr_5yr = ?, revenue_cagr_5yr_flag = ?,
            revenue_cagr_10yr = ?, revenue_cagr_10yr_flag = ?,
            pat_cagr_3yr = ?, pat_cagr_3yr_flag = ?,
            pat_cagr_5yr = ?, pat_cagr_5yr_flag = ?,
            pat_cagr_10yr = ?, pat_cagr_10yr_flag = ?,
            eps_cagr_3yr = ?, eps_cagr_3yr_flag = ?,
            eps_cagr_5yr = ?, eps_cagr_5yr_flag = ?,
            eps_cagr_10yr = ?, eps_cagr_10yr_flag = ?
        WHERE ticker = ?
    """
    
    cursor.executemany(update_query, updates)
    conn.commit()
    logger.info(f"Successfully updated CAGR metrics for {len(updates)} companies in analysis table.")
    conn.close()

if __name__ == "__main__":
    compute_and_store_cagr()
