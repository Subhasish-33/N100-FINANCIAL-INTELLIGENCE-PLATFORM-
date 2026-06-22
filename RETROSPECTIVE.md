# Sprint Retrospective — Day 07
**Date:** 22 June 2026  
**Sprint:** Week 1 · Days 1–7 · ETL Foundation & Data Quality  
**Project:** Nifty 100 Financial Intelligence Platform

---

## 🏁 Sprint Goal
Build a production-quality SQLite ETL pipeline that ingests 12 raw Excel files
for 92 Nifty 100 companies, validates data quality across 16 rules, and delivers
a clean, query-ready `nifty100.db` with zero CRITICAL violations.

---

## ✅ Definition of Done — Exit Criteria Results

| Criterion | Target | Actual | Status |
|---|---|---|---|
| `SELECT COUNT(*) FROM companies` | = 92 | 92 | ✅ |
| `PRAGMA foreign_key_check` | 0 rows | 0 rows | ✅ |
| `load_audit.csv` CRITICAL rejections | 0 | 0 | ✅ |
| ETL unit tests passing | 35+ | **36 / 36** | ✅ |
| Manual spot-check (5 companies) | correct values | Verified | ✅ |
| Sprint review signed off | — | Done | ✅ |

---

## 📦 Deliverables Shipped

| Deliverable | Location | Notes |
|---|---|---|
| Populated database | `data/nifty100.db` | 792 KB · 12 tables · 10 sectors |
| Per-table audit log | `output/load_audit.csv` | 12 tables loaded |
| DQ violations report | `output/validation_failures.csv` | CRITICAL: 0 · WARNING: present |
| ETL source code | `src/etl/loader.py`, `validator.py`, `quality_review.py` | All documented |
| SQLite schema | `db/schema.sql` | 12 tables with FK constraints |
| Unit test suite | `tests/etl/test_loader.py` | 36 tests, 0 failures |
| Exploratory queries | `notebooks/exploratory_queries.sql` | 10 business queries |

---

## 📊 Database Summary

| Table | Rows Loaded |
|---|---|
| sectors | 10 |
| companies | 92 |
| profit_and_loss | 1,072 |
| balance_sheet | 1,058 |
| cash_flow | 1,056 |
| financial_ratios | 1,041 |
| market_cap | 552 |
| stock_prices | 5,520 |
| peer_groups | 56 |
| documents | 1,457 |
| analysis | 16 |
| pros_and_cons | 14 |
| **Total** | **11,944** |

---

## 🔍 DQ Rules Implemented (16 Rules)

| Rule | Severity | Description |
|---|---|---|
| DQ-01 | CRITICAL | Ticker uniqueness & non-null (companies) |
| DQ-02 | CRITICAL | (ticker, year) PK uniqueness — P&L |
| DQ-03 | CRITICAL | (ticker, year) PK uniqueness — Balance Sheet |
| DQ-04 | CRITICAL | (ticker, year) PK uniqueness — Cash Flow |
| DQ-05 | CRITICAL | FK integrity — P&L tickers in companies |
| DQ-06 | CRITICAL | FK integrity — Balance Sheet tickers |
| DQ-07 | CRITICAL | FK integrity — Cash Flow tickers |
| DQ-08 | CRITICAL | Sales & Total Assets cannot be null |
| DQ-09 | WARNING | Balance Sheet equation: Assets ≈ Liabilities |
| DQ-10 | WARNING | Sales ≥ 0 |
| DQ-11 | WARNING | OPM cross-check: (Operating Profit / Sales) × 100 |
| DQ-12 | WARNING | Other assets not negative |
| DQ-13 | WARNING | Borrowings not negative |
| DQ-14 | WARNING | Tax % in [0, 50] range |
| DQ-15 | WARNING | Depreciation not negative |
| DQ-16 | WARNING | Cash Flow consistency: Operating + Investing + Financing ≈ Net CF |

---

## 🟢 What Went Well

- **Schema design was solid from Day 4** — zero FK violations at the end of Day 7 
  with no schema changes needed.
- **Modular ETL (`process_and_load`)** made it trivial to add new tables — all 12
  files loaded in a single pipeline with one reusable function.
- **Normaliser robustness** — handling 6 ticker suffix patterns (`.NS`, `.BO`, `:IN`,
  `.IS`, ` IN`, ` BO`) and 7 year formats (`FY23`, `CY2023`, `2022-23`, etc.)
  eliminated 100% of format mismatches.
- **Validator pre-run** on Day 3 surfaced DQ issues early, so Day 4–5 loading was
  clean rather than iterative.

---

## 🟡 What Was Challenging

- **Excel multi-row headers** — several source files had a blank first row and real
  headers on row 1. The auto-detect (`nrows=1` peek) worked but required careful
  unit-test design around single vs. double `read_excel` calls. Resolved by
  refactoring to a single read with column-name inspection.
- **Ticker suffix diversity** — the `sectors.xlsx` used a different `company_id`
  column than other files, requiring a rename before the merge join.
- **`normalize_ticker` / `normalize_year` contract** — internal ETL pipeline used
  `.apply()` + `.dropna()` which expected `None` on bad input, while unit tests
  expected `ValueError`. Resolved cleanly with `_safe_*` internal wrappers.

---

## 🔴 What Could Be Improved

- **`load_audit.csv` should track rejections per table**, not just loaded rows.
  Adding a `rows_rejected` column would make it a true audit trail.
- **`validation_failures.csv` is re-generated on every run** without timestamps —
  versioned output files (e.g., `validation_failures_20260622.csv`) would help
  track DQ trend over time.
- **No incremental loading** — the ETL wipes and reloads the full DB on every run.
  Day 8+ analytics layer will need change-data-capture or upsert logic.
- **Missing data in `analysis` table** (only 16 rows for 92 companies) indicates
  the `analysis.xlsx` source file is incomplete and needs enrichment.

---

## 🚀 Risks & Carry-Forwards to Day 8

| Risk | Mitigation |
|---|---|
| `analysis.xlsx` sparse data | Flag for data enrichment in next sprint |
| WARNING DQ violations (BS balance, OPM) | Acceptable for financial data from screener; document known tolerances |
| No test for `load_all_data()` integration | Add integration test in Day 8 analytics sprint |
| `nifty100.db` not gitignored | Add to `.gitignore` if DB size grows beyond 10 MB |

---

## 📌 Day 8 Preview — Analytics Engine

- Build `src/analytics/` module: ratios engine, CAGR calculator, peer comparison
- Expose REST API via `src/api/` (FastAPI)
- Connect `src/dashboard/` for interactive Streamlit/Dash UI
- Populate `src/nlp/` for natural-language query layer

---

*Retrospective authored: 22 June 2026 · Sprint 1 complete*
