"""
tests/screener/test_data_quality.py
Tests for data quality checks.
"""

import pytest
import pandas as pd
from unittest.mock import patch
from src.screener.data_quality import check_null_coverage, check_range_validity, check_market_data_presence

def test_check_null_coverage():
    # Mock data to simulate database result
    mock_df = pd.DataFrame({
        'return_on_equity_pct': [10.0, None, 15.0, 20.0],
        'debt_to_equity': [1.0, 0.5, None, None], # 50% missing
        'composite_quality_score': [80.0, 90.0, 50.0, 100.0]
    })
    
    with patch('src.screener.data_quality.pd.read_sql_query', return_value=mock_df):
        with patch('src.screener.data_quality.load_screener_metrics', return_value=['return_on_equity_pct', 'debt_to_equity']):
            result = check_null_coverage(2024, db_path='dummy.db')
            
            # Check length: 2 config metrics + 1 composite_quality_score = 3
            assert len(result) == 3
            
            roe_row = result[result['metric'] == 'return_on_equity_pct'].iloc[0]
            assert roe_row['missing_count'] == 1
            assert roe_row['missing_pct'] == 25.0
            assert "FAIL" in roe_row['status'] # 25% > 15%
            
            de_row = result[result['metric'] == 'debt_to_equity'].iloc[0]
            assert de_row['missing_count'] == 2
            assert de_row['missing_pct'] == 50.0
            assert "FAIL" in de_row['status']
            
            cqs_row = result[result['metric'] == 'composite_quality_score'].iloc[0]
            assert cqs_row['missing_count'] == 0
            assert cqs_row['missing_pct'] == 0.0
            assert "PASS" == cqs_row['status']

def test_check_range_validity():
    mock_df = pd.DataFrame({
        'symbol': ['A', 'B', 'C', 'D'],
        'composite_quality_score': [50.0, -10.0, 105.0, None], # B and C out of bounds
        'pe_ratio': [20.0, 15.0, -5.0, None], # C out of bounds
        'return_on_equity_pct': [15.0, 20.0, 25.0, 30.0]
    })
    
    with patch('src.screener.data_quality.pd.read_sql_query', return_value=mock_df):
        result = check_range_validity(2024, db_path='dummy.db')
        
        assert len(result) == 3 # 2 for CQS bounds, 1 for PE bounds
        
        cqs_errors = result[result['check'] == 'composite_quality_score bounds']
        assert len(cqs_errors) == 2
        assert set(cqs_errors['symbol'].tolist()) == {'B', 'C'}
        
        pe_errors = result[result['check'] == 'negative pe_ratio']
        assert len(pe_errors) == 1
        assert pe_errors.iloc[0]['symbol'] == 'C'

def test_check_market_data_presence():
    mock_df_fail = pd.DataFrame({
        'symbol_fr': ['A', 'B', 'C'],
        'symbol_md': ['A', None, 'C']
    })
    
    with patch('src.screener.data_quality.pd.read_sql_query', return_value=mock_df_fail):
        result_fail = check_market_data_presence(2024, db_path='dummy.db')
        assert result_fail.iloc[0]['status'] == 'FAIL'
        assert result_fail.iloc[0]['missing_symbols'] == 'B'
        
    mock_df_pass = pd.DataFrame({
        'symbol_fr': ['A', 'B', 'C'],
        'symbol_md': ['A', 'B', 'C']
    })
    
    with patch('src.screener.data_quality.pd.read_sql_query', return_value=mock_df_pass):
        result_pass = check_market_data_presence(2024, db_path='dummy.db')
        assert result_pass.iloc[0]['status'] == 'PASS'
        assert result_pass.iloc[0]['missing_symbols'] == 'None'
