"""
src/screener/screener_cli.py
Command-line interface for the Nifty 100 Financial Screener.
"""

import argparse
import sys
import logging
from pathlib import Path

# Setup simple logging to console
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

from src.screener.engine import run_preset, run_all_presets, run_screener, _load_config, generate_screener_output

def setup_parser():
    parser = argparse.ArgumentParser(
        description="Nifty 100 Financial Screener CLI",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--preset", type=str, help="Run a specific preset screener (e.g., quality_compounder)")
    group.add_argument("--all", action="store_true", help="Run all preset screeners")
    group.add_argument("--custom", action="store_true", help="Run a custom screener with specific filter flags")
    
    parser.add_argument("--year", type=int, default=2024, help="Financial year to run the screener against")
    parser.add_argument("--save", action="store_true", help="Save the output to output/screener_output.xlsx")
    
    # Dynamically add custom filter arguments from config
    config = _load_config()
    metrics = config.get("metrics", {})
    
    custom_group = parser.add_argument_group("Custom Filters (Requires --custom)")
    for metric_name, meta in metrics.items():
        custom_group.add_argument(f"--{metric_name}", type=float, help=f"Filter for {meta.get('label', metric_name)}")
        
    return parser

def print_results(results, title="Screener Results"):
    """Pretty print the screener results to the console."""
    logger.info(f"\n{'='*50}")
    logger.info(f"{title}")
    logger.info(f"{'='*50}")
    
    if results.empty:
        logger.info("No companies met the criteria.")
        return
        
    # Print in a readable format
    for idx, row in results.iterrows():
        name = row.get("company_name", row.get("ticker", "Unknown"))
        cqs = row.get("composite_quality_score", "N/A")
        try:
            cqs_str = f"{float(cqs):.1f}" if pd.notna(cqs) else "N/A"
        except:
            cqs_str = "N/A"
        logger.info(f"- {name} ({row.get('ticker', 'Unknown')}) | CQS: {cqs_str}")
        
    logger.info(f"\nTotal: {len(results)} companies found.")

def main():
    parser = setup_parser()
    args = parser.parse_args()
    
    config = _load_config()
    
    if args.preset:
        if args.preset not in config.get("presets", {}):
            logger.error(f"Error: Preset '{args.preset}' not found. Available presets:")
            for p in config.get("presets", {}).keys():
                logger.error(f"  - {p}")
            sys.exit(1)
            
        logger.info(f"Running preset: {args.preset} for year {args.year}...")
        df = run_preset(args.preset, args.year)
        
        if not args.save:
            print_results(df, title=f"Preset: {args.preset}")
            
    elif args.all:
        logger.info(f"Running all presets for year {args.year}...")
        if not args.save:
            logger.warning("Running all presets without --save will only print results to console.")
            for preset_name in config.get("presets", {}).keys():
                df = run_preset(preset_name, args.year)
                print_results(df, title=f"Preset: {preset_name}")
                
    elif args.custom:
        # Build filters dictionary from passed arguments
        filters = {}
        metrics = config.get("metrics", {})
        
        for metric_name in metrics.keys():
            val = getattr(args, metric_name, None)
            if val is not None:
                filters[metric_name] = val
                
        if not filters:
            logger.error("Error: --custom requires at least one custom filter flag (e.g., --roe_min 15)")
            sys.exit(1)
            
        logger.info(f"Running custom screener for year {args.year} with filters: {filters}")
        df = run_screener(filters, args.year)
        
        if not args.save:
            print_results(df, title="Custom Screener Results")
            
    # Handle saving for all modes
    if args.save:
        output_path = Path(__file__).parent.parent.parent / "output" / "screener_output.xlsx"
        output_path.parent.mkdir(exist_ok=True)
        
        if args.all:
            # We already have a generate_screener_output function that handles all presets
            logger.info("Generating full screener output Excel file...")
            generate_screener_output(args.year, str(output_path))
        else:
            # We just save the single DataFrame using pandas directly
            # This is simpler than hacking the existing generate_screener_output for one sheet
            import pandas as pd
            with pd.ExcelWriter(str(output_path), engine='openpyxl') as writer:
                sheet_name = args.preset if args.preset else "Custom_Screener"
                df.to_excel(writer, sheet_name=sheet_name[:31], index=False)
            logger.info(f"Saved results to {output_path}")

if __name__ == "__main__":
    import pandas as pd  # needed for print_results
    main()
