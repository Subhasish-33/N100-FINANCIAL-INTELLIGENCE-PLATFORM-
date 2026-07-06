-- Screener Preview: High Quality, Low Leverage
-- Condition: ROE > 15% and Debt to Equity < 1
SELECT 
    ticker, 
    company_name, 
    return_on_equity_pct, 
    debt_to_equity 
FROM financial_ratios 
JOIN companies USING(ticker) 
WHERE return_on_equity_pct > 15 
  AND debt_to_equity < 1 
  AND year = 2024 
ORDER BY return_on_equity_pct DESC;
