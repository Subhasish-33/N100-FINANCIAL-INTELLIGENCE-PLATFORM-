import csv
import os
import sqlite3
import logging
from pathlib import Path
from collections import defaultdict
from src.analytics.cashflow_kpis import (
    compute_fcf,
    compute_cfo_quality_score,
    compute_capex_intensity,
    compute_fcf_conversion_rate,
    classify_capital_allocation
)

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def generate_capital_allocation_report(output_path: str = "output/capital_allocation.csv"):
    """
    Computes Cash Flow KPIs and generates capital_allocation.csv report.
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    base_dir = Path(__file__).parent.parent.parent
    db_path = base_dir / "data" / "database.sqlite"

    if not db_path.exists():
        logger.error(f"Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Query all company-years from financial_ratios and LEFT JOIN cash_flow and profit_and_loss
    query = """
        SELECT 
            fr.ticker, fr.year, 
            cf.operating_activity, cf.investing_activity, cf.financing_activity,
            pl.net_profit, pl.sales, pl.operating_profit
        FROM financial_ratios fr
        LEFT JOIN cash_flow cf ON fr.ticker = cf.ticker AND fr.year = cf.year
        LEFT JOIN profit_and_loss pl ON fr.ticker = pl.ticker AND fr.year = pl.year
        ORDER BY fr.ticker, fr.year ASC
    """
    cursor.execute(query)
    rows = cursor.fetchall()
    
    # Group by ticker for multi-year calculations (like 5-year CFO Quality)
    company_data = defaultdict(list)
    for r in rows:
        company_data[r['ticker']].append(r)
        
    fr_updates = []
    analysis_updates = []
    csv_rows = []
    
    for ticker, records in company_data.items():
        # Get up to last 5 years for CFO quality
        recent_records = records[-5:]
        cfo_list = [(r['operating_activity'] or 0.0) for r in recent_records]
        pat_list = [(r['net_profit'] or 0.0) for r in recent_records]
        
        cfo_quality = compute_cfo_quality_score(cfo_list, pat_list)
        
        # Update analysis table with CFO Quality Score
        analysis_updates.append((cfo_quality, ticker))
        
        for r in records:
            year = r['year']
            cfo = r['operating_activity'] or 0.0
            cfi = r['investing_activity'] or 0.0
            cff = r['financing_activity'] or 0.0
            sales = r['sales'] or 0.0
            op_profit = r['operating_profit'] or 0.0
            
            # FCF
            fcf = compute_fcf(cfo, cfi)
            
            # CapEx Intensity
            capex_res = compute_capex_intensity(cfi, sales)
            capex_val = capex_res[0] if capex_res else None
            capex_label = capex_res[1] if capex_res else None
            
            # FCF Conversion
            fcf_conv = compute_fcf_conversion_rate(fcf, op_profit)
            
            fr_updates.append((fcf, capex_val, capex_label, fcf_conv, ticker, year))
            
            # Classification for CSV
            cfo_sign = '+' if cfo >= 0 else '-'
            cfi_sign = '+' if cfi >= 0 else '-'
            cff_sign = '+' if cff >= 0 else '-'
            
            pattern_label = classify_capital_allocation(cfo, cfi, cff, cfo_quality)
            
            csv_rows.append([ticker, year, cfo_sign, cfi_sign, cff_sign, pattern_label])
            
    # Update DB
    fr_query = """
        UPDATE financial_ratios
        SET free_cash_flow = ?, capex_intensity = ?, capex_intensity_label = ?, fcf_conversion_rate = ?
        WHERE ticker = ? AND year = ?
    """
    cursor.executemany(fr_query, fr_updates)
    
    an_query = """
        UPDATE analysis
        SET cfo_quality_score_5yr_avg = ?
        WHERE ticker = ?
    """
    cursor.executemany(an_query, analysis_updates)
    
    conn.commit()
    conn.close()
    logger.info("Successfully updated financial_ratios and analysis with Cash Flow KPIs")

    # Generate CSV
    with open(output_path, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['company_id', 'year', 'cfo_sign', 'cfi_sign', 'cff_sign', 'pattern_label'])
        writer.writerows(csv_rows)
        
    logger.info(f"Successfully generated capital allocation report at {output_path}")

if __name__ == "__main__":
    generate_capital_allocation_report()
