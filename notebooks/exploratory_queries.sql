-- =============================================================================
-- Nifty 100 Financial Intelligence Platform
-- Exploratory Queries  |  Day 07  |  Sprint Wrap-Up
-- Database: nifty100.db
-- =============================================================================


-- ---------------------------------------------------------------------------
-- Q-01  Company universe: count by sector
-- Goal : Confirm 10 sectors are loaded and show distribution
-- ---------------------------------------------------------------------------
SELECT
    s.sector_name,
    COUNT(c.ticker) AS company_count
FROM sectors s
LEFT JOIN companies c ON c.sector_id = s.sector_id
GROUP BY s.sector_name
ORDER BY company_count DESC;


-- ---------------------------------------------------------------------------
-- Q-02  Top 10 companies by latest-year revenue (sales)
-- Goal : Identify revenue leaders across the Nifty 100
-- ---------------------------------------------------------------------------
SELECT
    p.ticker,
    c.company_name,
    s.sector_name,
    p.year,
    ROUND(p.sales, 2) AS sales_cr
FROM profit_and_loss p
JOIN companies c ON c.ticker = p.ticker
LEFT JOIN sectors s ON s.sector_id = c.sector_id
WHERE p.year = (SELECT MAX(year) FROM profit_and_loss)
ORDER BY p.sales DESC
LIMIT 10;


-- ---------------------------------------------------------------------------
-- Q-03  Top 10 companies by most-recent market capitalisation
-- Goal : Rank Nifty 100 companies by market size
-- ---------------------------------------------------------------------------
SELECT
    m.ticker,
    c.company_name,
    s.sector_name,
    m.year,
    ROUND(m.market_cap, 2) AS market_cap_cr
FROM market_cap m
JOIN companies c ON c.ticker = m.ticker
LEFT JOIN sectors s ON s.sector_id = c.sector_id
WHERE m.year = (SELECT MAX(year) FROM market_cap)
ORDER BY m.market_cap DESC
LIMIT 10;


-- ---------------------------------------------------------------------------
-- Q-04  5-year revenue CAGR for each company (FY2019 → FY2024)
-- Goal : Surface high-growth compounders
-- ---------------------------------------------------------------------------
SELECT
    base.ticker,
    c.company_name,
    s.sector_name,
    ROUND(base.sales, 2)   AS sales_fy19,
    ROUND(latest.sales, 2) AS sales_fy24,
    ROUND(
        (POWER(CAST(latest.sales AS REAL) / NULLIF(base.sales, 0), 1.0 / 5) - 1) * 100,
        2
    ) AS revenue_cagr_pct
FROM profit_and_loss base
JOIN profit_and_loss latest ON latest.ticker = base.ticker AND latest.year = 2024
JOIN companies c ON c.ticker = base.ticker
LEFT JOIN sectors s ON s.sector_id = c.sector_id
WHERE base.year = 2019
  AND base.sales  > 0
  AND latest.sales > 0
ORDER BY revenue_cagr_pct DESC
LIMIT 15;


-- ---------------------------------------------------------------------------
-- Q-05  Profitability league: ROE vs ROCE (latest year)
-- Goal : Find quality companies with high return on capital
-- ---------------------------------------------------------------------------
SELECT
    r.ticker,
    c.company_name,
    s.sector_name,
    r.year,
    ROUND(r.roe_percentage, 2)  AS roe_pct,
    ROUND(r.roce_percentage, 2) AS roce_pct,
    ROUND(r.roe_percentage - r.roce_percentage, 2) AS spread_pct
FROM financial_ratios r
JOIN companies c ON c.ticker = r.ticker
LEFT JOIN sectors s ON s.sector_id = c.sector_id
WHERE r.year = (SELECT MAX(year) FROM financial_ratios)
  AND r.roe_percentage IS NOT NULL
  AND r.roce_percentage IS NOT NULL
ORDER BY r.roe_percentage DESC
LIMIT 15;


-- ---------------------------------------------------------------------------
-- Q-06  Debt analysis: borrowings-to-equity ratio (latest year)
-- Goal : Identify over-leveraged vs debt-free companies
-- ---------------------------------------------------------------------------
SELECT
    b.ticker,
    c.company_name,
    s.sector_name,
    b.year,
    ROUND(b.borrowings, 2)     AS borrowings_cr,
    ROUND(b.equity_capital + COALESCE(b.reserves, 0), 2) AS net_worth_cr,
    ROUND(
        b.borrowings / NULLIF(b.equity_capital + COALESCE(b.reserves, 0), 0),
        2
    ) AS debt_to_equity
FROM balance_sheet b
JOIN companies c ON c.ticker = b.ticker
LEFT JOIN sectors s ON s.sector_id = c.sector_id
WHERE b.year = (SELECT MAX(year) FROM balance_sheet)
  AND b.equity_capital IS NOT NULL
ORDER BY debt_to_equity DESC
LIMIT 15;


-- ---------------------------------------------------------------------------
-- Q-07  Cash-flow quality: Operating CF vs Net Profit (latest year)
-- Goal : Detect earnings quality – high OCF/profit ratio is healthy
-- ---------------------------------------------------------------------------
SELECT
    p.ticker,
    c.company_name,
    s.sector_name,
    p.year,
    ROUND(p.net_profit, 2)         AS net_profit_cr,
    ROUND(cf.operating_activity, 2) AS operating_cf_cr,
    ROUND(
        cf.operating_activity / NULLIF(p.net_profit, 0),
        2
    ) AS cf_to_profit_ratio
FROM profit_and_loss p
JOIN cash_flow cf ON cf.ticker = p.ticker AND cf.year = p.year
JOIN companies c ON c.ticker = p.ticker
LEFT JOIN sectors s ON s.sector_id = c.sector_id
WHERE p.year = (SELECT MAX(year) FROM profit_and_loss)
  AND p.net_profit IS NOT NULL
  AND cf.operating_activity IS NOT NULL
ORDER BY cf_to_profit_ratio DESC
LIMIT 15;


-- ---------------------------------------------------------------------------
-- Q-08  Working-capital efficiency: Cash Conversion Cycle (latest year)
-- Goal : Lower CCC = faster cash recovery; compare by sector
-- ---------------------------------------------------------------------------
SELECT
    s.sector_name,
    ROUND(AVG(r.debtor_days), 1)          AS avg_debtor_days,
    ROUND(AVG(r.inventory_days), 1)        AS avg_inventory_days,
    ROUND(AVG(r.days_payable), 1)          AS avg_days_payable,
    ROUND(AVG(r.cash_conversion_cycle), 1) AS avg_ccc
FROM financial_ratios r
JOIN companies c ON c.ticker = r.ticker
JOIN sectors s ON s.sector_id = c.sector_id
WHERE r.year = (SELECT MAX(year) FROM financial_ratios)
GROUP BY s.sector_name
ORDER BY avg_ccc ASC;


-- ---------------------------------------------------------------------------
-- Q-09  Stock price performance: 52-week high / low spread (latest year)
-- Goal : Gauge volatility and momentum for each stock
-- ---------------------------------------------------------------------------
SELECT
    sp.ticker,
    c.company_name,
    s.sector_name,
    ROUND(MAX(sp.high), 2)  AS week52_high,
    ROUND(MIN(sp.low),  2)  AS week52_low,
    ROUND(AVG(sp.close), 2) AS avg_close,
    ROUND(
        (MAX(sp.high) - MIN(sp.low)) / NULLIF(MIN(sp.low), 0) * 100,
        2
    ) AS range_pct
FROM stock_prices sp
JOIN companies c ON c.ticker = sp.ticker
LEFT JOIN sectors s ON s.sector_id = c.sector_id
WHERE sp.date >= DATE('now', '-365 days')
GROUP BY sp.ticker, c.company_name, s.sector_name
ORDER BY range_pct DESC
LIMIT 15;


-- ---------------------------------------------------------------------------
-- Q-10  Peer-group benchmarking: avg sales & net profit within each group
-- Goal : Show relative standing of companies inside their peer cluster
-- ---------------------------------------------------------------------------
SELECT
    pg.peer_group_name,
    pg.ticker,
    c.company_name,
    ROUND(p.sales, 2)       AS sales_cr,
    ROUND(p.net_profit, 2)  AS net_profit_cr,
    ROUND(AVG(p.sales)       OVER (PARTITION BY pg.peer_group_name), 2) AS peer_avg_sales_cr,
    ROUND(AVG(p.net_profit)  OVER (PARTITION BY pg.peer_group_name), 2) AS peer_avg_profit_cr,
    ROUND(
        (p.sales - AVG(p.sales) OVER (PARTITION BY pg.peer_group_name))
        / NULLIF(AVG(p.sales) OVER (PARTITION BY pg.peer_group_name), 0) * 100,
        1
    ) AS sales_vs_peer_avg_pct
FROM peer_groups pg
JOIN companies c ON c.ticker = pg.ticker
JOIN profit_and_loss p ON p.ticker = pg.ticker
    AND p.year = (SELECT MAX(year) FROM profit_and_loss)
ORDER BY pg.peer_group_name, p.sales DESC;
