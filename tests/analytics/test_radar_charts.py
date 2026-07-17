"""
tests/analytics/test_radar_charts.py
Unit tests for radar chart PNG generation.
"""

import pytest
from pathlib import Path

from src.reports.radar_charts import OUTPUT_DIR

EXPECTED_MIN_CHARTS = 56  # At least peer-grouped companies


# ─── File Creation ────────────────────────────────────────────────

def test_radar_chart_files_created():
    """At least 56 PNG files (peer-grouped companies) must exist in radar_charts/."""
    png_files = list(OUTPUT_DIR.glob("*.png"))
    assert len(png_files) >= EXPECTED_MIN_CHARTS, (
        f"Expected at least {EXPECTED_MIN_CHARTS} radar charts, found {len(png_files)}"
    )


def test_all_92_charts_generated():
    """All 92 companies should have radar chart PNGs."""
    png_files = list(OUTPUT_DIR.glob("*.png"))
    assert len(png_files) == 92, (
        f"Expected exactly 92 radar charts, found {len(png_files)}"
    )


# ─── Valid PNG ────────────────────────────────────────────────────

def test_radar_chart_is_valid_png():
    """Verify that the generated files are valid PNGs (check magic bytes)."""
    png_files = list(OUTPUT_DIR.glob("*.png"))
    assert len(png_files) > 0, "No PNG files found to validate"

    PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

    # Sample 5 files
    sample = png_files[:5]
    for path in sample:
        with open(path, "rb") as f:
            header = f.read(8)
        assert header == PNG_MAGIC, f"{path.name} does not have valid PNG header"


# ─── Ungrouped Company Chart ─────────────────────────────────────

def test_ungrouped_company_gets_chart():
    """A company without a peer group should still get a radar chart file."""
    import sqlite3
    from src.reports.radar_charts import DB_PATH

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT c.ticker FROM companies c
        WHERE c.ticker NOT IN (SELECT DISTINCT ticker FROM peer_groups)
        LIMIT 1
        """
    )
    row = cursor.fetchone()
    conn.close()

    if row is None:
        pytest.skip("All companies have peer groups")

    orphan_ticker = row[0]
    chart_path = OUTPUT_DIR / f"{orphan_ticker}_radar.png"
    assert chart_path.exists(), (
        f"Ungrouped company {orphan_ticker} is missing its radar chart at {chart_path}"
    )
