"""
tests/screener/test_composite.py
Tests for the Day 17 Composite Score calculations and styled Excel exports.
"""

import os
import openpyxl
import pandas as pd
import pytest
from src.analytics.composite_score import calculate_composite_quality_scores, load_ratios_for_scoring
from src.screener.engine import generate_screener_output, EXPORT_COLUMNS

YEAR = 2024


def test_composite_score_calculation():
    """Verify that calculated composite quality scores are correct and strictly in the [0, 100] range."""
    df_scores = calculate_composite_quality_scores(YEAR)
    assert not df_scores.empty
    assert "composite_score" in df_scores.columns
    
    scores = df_scores["composite_score"].dropna()
    assert (scores >= 0).all()
    assert (scores <= 100).all()
    
    # INDIGO or ASIANPAINT should be among the top quality companies
    top_companies = df_scores.sort_values("composite_score", ascending=False).head(5)["ticker"].tolist()
    assert any(x in top_companies for x in ["INDIGO", "ASIANPAINT", "HAL", "TRENT"]), (
        f"Top quality companies didn't match expected leaders, got {top_companies}"
    )


def test_excel_color_coding():
    """Verify the generated Excel spreadsheet sheets exist, have 22 KPI columns, and correct cell highlighting."""
    output_file = "output/screener_output.xlsx"
    if os.path.exists(output_file):
        os.remove(output_file)
        
    generate_screener_output(YEAR, output_file)
    assert os.path.exists(output_file)
    
    wb = openpyxl.load_workbook(output_file)
    sheet_name = "Quality Compounder"
    assert sheet_name in wb.sheetnames
    
    ws = wb[sheet_name]
    headers = [cell.value for cell in ws[1]]
    
    # Assert number of columns exported matches EXPORT_COLUMNS
    assert len(headers) == len(EXPORT_COLUMNS)
    assert "composite_quality_score" in headers
    
    # Assert D/E column is highlighted based on the de_max filter (< 1.0)
    de_idx = headers.index("debt_to_equity") + 1
    sector_idx = headers.index("sector_name") + 1
    
    for row_idx in range(2, ws.max_row + 1):
        cell = ws.cell(row=row_idx, column=de_idx)
        val = cell.value
        sector_val = ws.cell(row=row_idx, column=sector_idx).value
        
        if sector_val == "Financials":
            # Financials are exempt, so they should be highlighted green
            # (or left white if exempt, but our logic colors them green since they pass)
            assert cell.fill.fill_type == "solid"
            assert cell.fill.start_color.rgb in ("00C6EFCE", "C6EFCE")
        else:
            if val is not None:
                passed = float(val) <= 1.0
                if passed:
                    assert cell.fill.fill_type == "solid"
                    assert cell.fill.start_color.rgb in ("00C6EFCE", "C6EFCE")
                else:
                    assert cell.fill.fill_type == "solid"
                    assert cell.fill.start_color.rgb in ("00FFC7CE", "FFC7CE")

    # Assert ROE column is highlighted based on roe_min filter (> 15.0)
    roe_idx = headers.index("return_on_equity_pct") + 1
    for row_idx in range(2, ws.max_row + 1):
        cell = ws.cell(row=row_idx, column=roe_idx)
        val = cell.value
        if val is not None:
            passed = float(val) >= 15.0
            if passed:
                assert cell.fill.fill_type == "solid"
                assert cell.fill.start_color.rgb in ("00C6EFCE", "C6EFCE")
            else:
                assert cell.fill.fill_type == "solid"
                assert cell.fill.start_color.rgb in ("00FFC7CE", "FFC7CE")
