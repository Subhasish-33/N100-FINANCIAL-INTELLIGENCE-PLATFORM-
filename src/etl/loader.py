import re
from pathlib import Path
from typing import Union

import pandas as pd


def normalize_year(year: Union[str, int]) -> int:
    """
    Normalizes various financial year formats to a standard integer end year.
    Examples:
    "2023" -> 2023
    2023 -> 2023
    "FY23" -> 2023
    "FY 2023" -> 2023
    "2022-23" -> 2023
    "2022-2023" -> 2023
    "23" -> 2023
    "CY23" -> 2023
    """
    if isinstance(year, int):
        if year < 100:
            return 2000 + year if year < 50 else 1900 + year
        return year

    if not isinstance(year, str):
        year_str = str(year)
    else:
        year_str = year
        
    year_str = year_str.strip().upper()
    if not year_str:
        raise ValueError(f"Invalid year format: {year}")
    
    # Range formats like "2022-23", "2022-2023", "22-23"
    range_match = re.search(r'(\d{2,4})\s*-\s*(\d{2,4})', year_str)
    if range_match:
        end_year_str = range_match.group(2)
        end_year = int(end_year_str)
        if end_year < 100:
            # Assume 2000s for two-digit years < 50
            return 2000 + end_year if end_year < 50 else 1900 + end_year
        return end_year
        
    # Extract the last sequence of digits
    digits_match = re.findall(r'\d+', year_str)
    if not digits_match:
        raise ValueError(f"Invalid year format: {year}")
        
    extracted = int(digits_match[-1])
    if extracted < 100:
        return 2000 + extracted if extracted < 50 else 1900 + extracted
    return extracted


def normalize_ticker(ticker: str) -> str:
    """
    Normalizes a stock ticker by stripping whitespaces, uppercasing,
    and removing exchange suffixes.
    Examples:
    "RELIANCE.NS" -> "RELIANCE"
    " TCS " -> "TCS"
    "HDFCBANK.BO" -> "HDFCBANK"
    "INFY:IN" -> "INFY"
    """
    if ticker is None or not isinstance(ticker, str) or not str(ticker).strip():
        raise ValueError(f"Invalid ticker: {ticker}")
        
    ticker = str(ticker).strip().upper()
    
    # Common exchange suffixes
    suffixes = [".NS", ".BO", ":IN", ".IS", " IN", " BO", " NS"]
    
    for suffix in suffixes:
        if ticker.endswith(suffix):
            ticker = ticker[:-len(suffix)].strip()
            break
            
    if not ticker:
        raise ValueError("Ticker became empty after normalization")
        
    return ticker


def load_excel(file_path: Union[str, Path], sheet_name: Union[str, int, None] = 0) -> pd.DataFrame:
    """
    Loads an Excel file into a Pandas DataFrame and normalizes column names.
    """
    path = Path(file_path)
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"Excel file not found at: {file_path}")
        
    try:
        df = pd.read_excel(path, sheet_name=sheet_name)
    except Exception as e:
        raise ValueError(f"Failed to read Excel file {file_path}: {e}")
        
    # Normalize column names: strip spaces, lowercase, replace spaces with underscores
    df.columns = [
        str(col).strip().lower().replace(" ", "_").replace("\n", "_").replace(".", "")
        for col in df.columns
    ]
    
    return df
