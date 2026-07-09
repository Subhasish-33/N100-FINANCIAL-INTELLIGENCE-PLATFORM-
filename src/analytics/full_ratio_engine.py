import sqlite3
import logging
import math
from pathlib import Path
from collections import defaultdict

# Import all calculation functions
from src.analytics.ratios import (
    calculate_net_profit_margin,
    calculate_opm,
    calculate_roe,
    calculate_roce,
    calculate_roa,
    calculate_debt_to_equity,
    evaluate_high_leverage,
    calculate_icr,
    get_icr_label,
    evaluate_icr_warning,
    calculate_net_debt,
    calculate_asset_turnover
)
from src.analytics.cagr import compute_cagr
from src.analytics.cashflow_kpis import (
    compute_fcf,
    compute_cfo_quality_score,
    compute_capex_intensity,
    compute_fcf_conversion_rate
)

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def run_full_engine():
    base_dir = Path(__file__).parent.parent.parent
    db_path = base_dir / "data" / "database.sqlite"

    if not db_path.exists():
        logger.error(f"Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Generate all years from min to max across all data
    cursor.execute("""
        SELECT MIN(year) as min_y, MAX(year) as max_y FROM (
            SELECT year FROM profit_and_loss
            UNION SELECT year FROM balance_sheet
            UNION SELECT year FROM cash_flow
            UNION SELECT year FROM financial_ratios
        )
    """)
    year_bounds = cursor.fetchone()
    min_year, max_year = 2013, 2024
    if year_bounds['min_y'] and year_bounds['max_y']:
        min_year = year_bounds['min_y']
        max_year = year_bounds['max_y']

    # We will generate a cartesian product of ALL companies and ALL years
    # Since sqlite doesn't have generate_series by default in all builds, we can just do it in python
    cursor.execute("SELECT ticker, sector_id FROM companies")
    all_companies = cursor.fetchall()

    cursor.execute("SELECT sector_id, sector_name FROM sectors")
    sectors = {r['sector_id']: r['sector_name'] for r in cursor.fetchall()}

    # Fetch all data into dicts for O(1) lookup
    def fetch_table(table):
        cursor.execute(f"SELECT * FROM {table}")
        res = {}
        for r in cursor.fetchall():
            res[(r['ticker'], r['year'])] = dict(r)
        return res

    pl_data = fetch_table('profit_and_loss')
    bs_data = fetch_table('balance_sheet')
    cf_data = fetch_table('cash_flow')
    fr_data = fetch_table('financial_ratios')

    def _get_fcf_for_record(r):
        cfo_val = r['cf'].get('operating_activity')
        cfi_val = r['cf'].get('investing_activity')
        if cfo_val is not None and cfi_val is not None:
            return compute_fcf(cfo_val, cfi_val)
        return None

    inserts = []
    
    for c in all_companies:
        ticker = c['ticker']
        sector_name = sectors.get(c['sector_id'], "")
        
        # We need historical data across years to compute 5-year CAGRs
        # So we iterate sequentially
        records = []
        for y in range(min_year, max_year + 1):
            pl_rec = pl_data.get((ticker, y), {})
            bs_rec = bs_data.get((ticker, y), {})
            cf_rec = cf_data.get((ticker, y), {})
            fr_rec = fr_data.get((ticker, y), {})
            
            merged = {
                'year': y,
                'pl': pl_rec,
                'bs': bs_rec,
                'cf': cf_rec,
                'fr': fr_rec
            }
            records.append(merged)
            
        for i, r in enumerate(records):
            year = r['year']
            pl = r['pl']
            bs = r['bs']
            cf = r['cf']
            fr = r['fr']
            
            # P&L
            net_profit = pl.get('net_profit')
            sales = pl.get('sales')
            op = pl.get('operating_profit')
            interest = pl.get('interest')
            other_income = pl.get('other_income')
            eps = pl.get('eps')
            dividend_payout = pl.get('dividend_payout')
            
            ebit = None
            if op is not None and other_income is not None:
                ebit = op + other_income
            elif op is not None:
                ebit = op
                
            # Balance Sheet
            equity = bs.get('equity_capital')
            reserves = bs.get('reserves')
            borrowings = bs.get('borrowings')
            total_assets = bs.get('total_assets')
            investments = bs.get('investments')
            
            # Cash Flow
            cfo = cf.get('operating_activity')
            cfi = cf.get('investing_activity')
            cff = cf.get('financing_activity')
            
            # --- Calculations ---
            npm = calculate_net_profit_margin(net_profit, sales) if net_profit is not None and sales is not None else None
            opm = calculate_opm(op, sales) if op is not None and sales is not None else None
            roe = calculate_roe(net_profit, equity, reserves) if net_profit is not None and equity is not None else None
            de = calculate_debt_to_equity(borrowings, equity, reserves) if borrowings is not None and equity is not None else None
            
            # Day 13 Carve-out logic: if Financials, suppress warning
            high_leverage = False
            if de is not None:
                high_leverage = evaluate_high_leverage(de, sector_name)
                if sector_name == "Financials":
                    high_leverage = False
                    
            icr = calculate_icr(op, other_income, interest) if op is not None and interest is not None else None
            asset_to = calculate_asset_turnover(sales, total_assets) if sales is not None and total_assets is not None else None
            fcf = compute_fcf(cfo or 0, cfi or 0) if cfo is not None and cfi is not None else None
            
            capex_res = compute_capex_intensity(cfi or 0, sales or 0) if cfi is not None and sales is not None else None
            capex_val = capex_res[0] if capex_res else None
            capex_cr = abs(cfi) if cfi is not None else None
            
            # Additional KPI columns for Day 12
            bvps = None
            if equity is not None and reserves is not None:
                bvps = equity + reserves
                
            div_payout_ratio = dividend_payout
            total_debt_cr = borrowings
            cash_from_operations_cr = cfo
            
            # Rolling 5-Year & 3-Year CAGR
            rev_cagr_5yr, pat_cagr_5yr, eps_cagr_5yr = None, None, None
            rev_cagr_3yr = None
            if i >= 5:
                start_record = records[i-5]
                start_sales = start_record['pl'].get('sales')
                if start_sales is not None and sales is not None:
                    rev_cagr_5yr, _ = compute_cagr(start_sales, sales, 5)
                    
                start_pat = start_record['pl'].get('net_profit')
                if start_pat is not None and net_profit is not None:
                    pat_cagr_5yr, _ = compute_cagr(start_pat, net_profit, 5)
                    
                start_eps = start_record['pl'].get('eps')
                if start_eps is not None and eps is not None:
                    eps_cagr_5yr, _ = compute_cagr(start_eps, eps, 5)
            if i >= 3:
                start_3 = records[i-3]
                start_sales_3 = start_3['pl'].get('sales')
                if start_sales_3 is not None and sales is not None:
                    rev_cagr_3yr, _ = compute_cagr(start_sales_3, sales, 3)

            # FCF CAGR 5yr
            fcf_cagr_5yr = None
            if i >= 5:
                start_record = records[i-5]
                start_fcf = _get_fcf_for_record(start_record)
                if start_fcf is not None and fcf is not None:
                    cagr_val, flag = compute_cagr(start_fcf, fcf, 5)
                    if flag == "NORMAL":
                        fcf_cagr_5yr = cagr_val
                    elif flag == "DECLINE_TO_LOSS":
                        fcf_cagr_5yr = -50.0
                    elif flag == "TURNAROUND":
                        fcf_cagr_5yr = 50.0
                    elif flag == "BOTH_NEGATIVE":
                        fcf_cagr_5yr = -20.0

            # CFO / PAT ratio
            cfo_pat_ratio = None
            if cfo is not None and net_profit is not None and net_profit != 0:
                cfo_pat_ratio = cfo / net_profit
                
            # Composite Quality Score (5-yr avg CFO/PAT)
            comp_score = None
            if i >= 4:
                recent = records[i-4:i+1]
                if all(r['cf'].get('operating_activity') is not None for r in recent) and all(r['pl'].get('net_profit') is not None for r in recent):
                    cfo_list = [r['cf']['operating_activity'] for r in recent]
                    pat_list = [r['pl']['net_profit'] for r in recent]
                    comp_score = compute_cfo_quality_score(cfo_list, pat_list)
                    
            # Use existing values if available for old columns
            roce_percentage = fr.get('roce_percentage')
            debtor_days = fr.get('debtor_days')
            inventory_days = fr.get('inventory_days')
            days_payable = fr.get('days_payable')
            cash_conversion_cycle = fr.get('cash_conversion_cycle')
            working_capital_days = fr.get('working_capital_days')
            roa_percentage = fr.get('roa_percentage')
            icr_label = fr.get('icr_label')
            icr_warning_flag = fr.get('icr_warning_flag')
            net_debt = fr.get('net_debt')
            capex_intensity_label = fr.get('capex_intensity_label')
            fcf_conversion_rate = fr.get('fcf_conversion_rate')

            inserts.append((
                ticker, year,
                roce_percentage, debtor_days, inventory_days, days_payable, cash_conversion_cycle, working_capital_days, roa_percentage, high_leverage, icr_label, icr_warning_flag, net_debt, capex_intensity_label, fcf_conversion_rate,
                npm, opm, roe, de, icr, asset_to, fcf, capex_cr, eps, bvps, div_payout_ratio, total_debt_cr, cash_from_operations_cr,
                rev_cagr_3yr, rev_cagr_5yr, pat_cagr_5yr, eps_cagr_5yr, fcf_cagr_5yr, cfo_pat_ratio, comp_score
            ))
            
    insert_sql = """
        INSERT OR REPLACE INTO financial_ratios (
            ticker, year,
            roce_percentage, debtor_days, inventory_days, days_payable, cash_conversion_cycle, working_capital_days, roa_percentage, high_leverage_flag, icr_label, icr_warning_flag, net_debt, capex_intensity_label, fcf_conversion_rate,
            net_profit_margin_pct, operating_profit_margin_pct, return_on_equity_pct, debt_to_equity, interest_coverage, asset_turnover, free_cash_flow_cr, capex_cr, earnings_per_share, book_value_per_share, dividend_payout_ratio_pct, total_debt_cr, cash_from_operations_cr,
            revenue_cagr_3yr, revenue_cagr_5yr, pat_cagr_5yr, eps_cagr_5yr, fcf_cagr_5yr, cfo_pat_ratio, composite_quality_score
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """
    cursor.executemany(insert_sql, inserts)
    conn.commit()
    
    cursor.execute("SELECT COUNT(*) as cnt FROM financial_ratios")
    row_count = cursor.fetchone()['cnt']
    logger.info(f"Successfully inserted/updated {len(inserts)} rows. Total in DB: {row_count}")
    assert row_count >= 1100, f"Expected at least 1100 rows, got {row_count}"
    
    conn.close()

if __name__ == "__main__":
    run_full_engine()
