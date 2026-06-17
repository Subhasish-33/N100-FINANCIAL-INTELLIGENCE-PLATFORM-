# Nifty 100 Financial Intelligence Platform

A self-contained financial intelligence platform for fundamental analysis of Nifty 100 companies.

## Project Overview
This platform ingests raw financial statement data (Profit & Loss, Balance Sheet, Cash Flow) for 92 Nifty 100 constituents and transforms it into structured intelligence featuring:
- **Financial Ratio Engine**: Computation of 50+ key financial KPIs.
- **Investment Screener**: Multi-criteria stock screening with 15+ filters.
- **Financial Health Scoring**: Composite quality and risk rating model (0–100).
- **Intra-Sector Benchmarking & Peer Comparison**: Relative scoring across 11 sectors.
- **Automated Report Generation**: ReportLab PDF Tearsheets and Portfolio summary sheets.
- **Streamlit Interactive Dashboard**: Multi-page analyst-facing web interface.
- **FastAPI Endpoint Service**: 16 REST endpoints for querying data.

## Day 1 Progress
- Scaffolded project folder structure (`data/`, `src/`, `tests/`, `reports/`, `config/`).
- Created environment templates (`.env.template`, `.env`).
- Defined core package dependencies in `requirements.txt`.
- Set up local raw and supporting dataset directories.

## Setup Instructions

### 1. Initialize Virtual Environment
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Environment Configuration
Copy `.env.template` to `.env` and configure your database path:
```bash
cp .env.template .env
```
