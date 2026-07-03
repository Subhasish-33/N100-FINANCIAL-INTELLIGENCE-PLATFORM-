import csv
import os
import random
from src.analytics.cash_flow import classify_capital_allocation

def generate_dummy_capital_allocation_report(output_path: str = "output/capital_allocation.csv"):
    """
    Generates a sample capital_allocation.csv file as requested for Day 11.
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    companies = [f"COMP_{i:03d}" for i in range(1, 11)]
    years = [2021, 2022, 2023]
    
    with open(output_path, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['company_id', 'year', 'cfo_sign', 'cfi_sign', 'cff_sign', 'pattern_label'])
        
        for comp in companies:
            for year in years:
                cfo = random.choice([-100.0, 100.0])
                cfi = random.choice([-100.0, 100.0])
                cff = random.choice([-100.0, 100.0])
                
                cfo_sign = '+' if cfo >= 0 else '-'
                cfi_sign = '+' if cfi >= 0 else '-'
                cff_sign = '+' if cff >= 0 else '-'
                
                # Mock CFO quality for Shareholder Returns/Reinvestor split
                cfo_quality = random.choice(["High Quality", "Moderate", "Accrual Risk"]) if cfo_sign == '+' else None
                
                pattern_label = classify_capital_allocation(cfo, cfi, cff, cfo_quality)
                
                writer.writerow([comp, year, cfo_sign, cfi_sign, cff_sign, pattern_label])

if __name__ == "__main__":
    generate_dummy_capital_allocation_report()
    print(f"Successfully generated capital allocation report at output/capital_allocation.csv")
