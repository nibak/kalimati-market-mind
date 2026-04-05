#!/usr/bin/env python3
"""
Entry point for the Kalimati Market Data ETL pipeline.

Run from the project root:
    python run_etl.py
"""

import sys
from pathlib import Path
from app.db.database import init_db
from app.etl.loader import load_all

DATA_DIR = Path("documents")

if __name__ == "__main__":
    if not DATA_DIR.exists() or not any(DATA_DIR.glob("*.xlsx")):
        print("Error: No data files found in 'documents/'.")
        print("  Place yearly Excel files there and re-run.")
        sys.exit(1)

    print("Initializing database...")
    init_db()
    print("Running ETL pipeline...")
    load_all(str(DATA_DIR))
    print("\nDone! Launch the dashboard with:")
    print("    streamlit run app/dashboard/Home.py")
