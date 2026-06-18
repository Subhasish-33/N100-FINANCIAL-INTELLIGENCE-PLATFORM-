import pytest
import pandas as pd
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.etl.loader import normalize_year, normalize_ticker, load_excel


class TestNormalizeYear:
    def test_standard_int(self):
        assert normalize_year(2023) == 2023

    def test_two_digit_int_2000s(self):
        assert normalize_year(23) == 2023

    def test_two_digit_int_1900s(self):
        assert normalize_year(99) == 1999

    def test_standard_str(self):
        assert normalize_year("2023") == 2023

    def test_two_digit_str_2000s(self):
        assert normalize_year("23") == 2023

    def test_two_digit_str_1900s(self):
        assert normalize_year("99") == 1999

    def test_fy_prefix_two_digit(self):
        assert normalize_year("FY23") == 2023

    def test_fy_prefix_four_digit(self):
        assert normalize_year("FY 2023") == 2023

    def test_range_format_short_end(self):
        assert normalize_year("2022-23") == 2023

    def test_range_format_long_end(self):
        assert normalize_year("2022-2023") == 2023

    def test_range_format_short_both(self):
        assert normalize_year("22-23") == 2023

    def test_cy_prefix(self):
        assert normalize_year("CY23") == 2023

    def test_whitespace_padding(self):
        assert normalize_year("  2023  ") == 2023

    def test_zero_int(self):
        assert normalize_year(0) == 2000

    def test_invalid_string(self):
        with pytest.raises(ValueError):
            normalize_year("abc")

    def test_empty_string(self):
        with pytest.raises(ValueError):
            normalize_year("")


class TestNormalizeTicker:
    def test_ns_suffix(self):
        assert normalize_ticker("RELIANCE.NS") == "RELIANCE"

    def test_bo_suffix(self):
        assert normalize_ticker("RELIANCE.BO") == "RELIANCE"

    def test_colon_in_suffix(self):
        assert normalize_ticker("RELIANCE:IN") == "RELIANCE"

    def test_is_suffix(self):
        assert normalize_ticker("RELIANCE.IS") == "RELIANCE"

    def test_space_in_suffix(self):
        assert normalize_ticker("RELIANCE IN") == "RELIANCE"

    def test_space_bo_suffix(self):
        assert normalize_ticker("RELIANCE BO") == "RELIANCE"

    def test_space_ns_suffix(self):
        assert normalize_ticker("RELIANCE NS") == "RELIANCE"

    def test_whitespace_padding(self):
        assert normalize_ticker("  RELIANCE  ") == "RELIANCE"

    def test_lowercase(self):
        assert normalize_ticker("reliance.ns") == "RELIANCE"

    def test_no_suffix(self):
        assert normalize_ticker("TCS") == "TCS"

    def test_none_input(self):
        with pytest.raises(ValueError):
            normalize_ticker(None)

    def test_empty_string(self):
        with pytest.raises(ValueError):
            normalize_ticker("")

    def test_whitespace_string(self):
        with pytest.raises(ValueError):
            normalize_ticker("   ")

    def test_only_suffix(self):
        with pytest.raises(ValueError):
            normalize_ticker(".NS")

    def test_invalid_type(self):
        with pytest.raises(ValueError):
            normalize_ticker(123)


class TestLoadExcel:
    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            load_excel("non_existent_file.xlsx")

    @patch('src.etl.loader.Path.exists')
    @patch('src.etl.loader.Path.is_file')
    @patch('src.etl.loader.pd.read_excel')
    def test_invalid_file_format(self, mock_read_excel, mock_is_file, mock_exists):
        mock_exists.return_value = True
        mock_is_file.return_value = True
        mock_read_excel.side_effect = Exception("Format error")
        
        with pytest.raises(ValueError, match="Failed to read Excel file"):
            load_excel("dummy.xlsx")

    @patch('src.etl.loader.Path.exists')
    @patch('src.etl.loader.Path.is_file')
    @patch('src.etl.loader.pd.read_excel')
    def test_column_normalization(self, mock_read_excel, mock_is_file, mock_exists):
        mock_exists.return_value = True
        mock_is_file.return_value = True
        
        # Create a mock DataFrame with messy column names
        mock_df = pd.DataFrame(columns=[
            "Some Col", 
            " Another Col ", 
            "col.name", 
            "col\nname", 
            "Already_good"
        ])
        mock_read_excel.return_value = mock_df
        
        df = load_excel("dummy.xlsx")
        
        expected_columns = [
            "some_col",
            "another_col",
            "colname",
            "col_name",
            "already_good"
        ]
        assert list(df.columns) == expected_columns

    @patch('src.etl.loader.Path.exists')
    @patch('src.etl.loader.Path.is_file')
    @patch('src.etl.loader.pd.read_excel')
    def test_sheet_name_default(self, mock_read_excel, mock_is_file, mock_exists):
        mock_exists.return_value = True
        mock_is_file.return_value = True
        mock_read_excel.return_value = pd.DataFrame()
        
        load_excel("dummy.xlsx")
        mock_read_excel.assert_called_once_with(Path("dummy.xlsx"), sheet_name=0)

    @patch('src.etl.loader.Path.exists')
    @patch('src.etl.loader.Path.is_file')
    @patch('src.etl.loader.pd.read_excel')
    def test_sheet_name_custom(self, mock_read_excel, mock_is_file, mock_exists):
        mock_exists.return_value = True
        mock_is_file.return_value = True
        mock_read_excel.return_value = pd.DataFrame()
        
        load_excel("dummy.xlsx", sheet_name="Data")
        mock_read_excel.assert_called_once_with(Path("dummy.xlsx"), sheet_name="Data")
