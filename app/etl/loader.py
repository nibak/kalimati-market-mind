"""
Loader: orchestrates the full ETL pipeline.

For each Excel file found in *data_dir*:
  1. Extracts raw DataFrames via extractor.extract_year()
  2. Transforms them via transformer functions
  3. Inserts records into SQLite (idempotent — uses INSERT OR IGNORE)
"""

import os
import re
import sqlite3
import traceback
from pathlib import Path

import pandas as pd

from app.db.database import get_connection
from app.etl.extractor import extract_year
from app.etl.transformer import (
    transform_price,
    transform_volume_month,
    transform_volume_source,
)
from app.utils.commodity_mapper import get_or_create_commodity


# ---------------------------------------------------------------------------
# Individual table loaders
# ---------------------------------------------------------------------------

def _load_prices(conn: sqlite3.Connection, df: pd.DataFrame) -> int:
    """Insert price records; return count of rows attempted.

    SQLite's UNIQUE constraint treats NULL != NULL, so annual rows
    (month=NULL) would not be de-duplicated by INSERT OR IGNORE.
    We therefore perform an explicit existence check for those rows.
    Monthly rows (month IS NOT NULL) use INSERT OR IGNORE normally.
    """
    cursor = conn.cursor()
    count = 0
    for _, row in df.iterrows():
        commodity_id = get_or_create_commodity(conn, row["commodity_name"])
        if commodity_id is None:
            continue

        is_annual = row["month"] is None or (
            isinstance(row["month"], float) and pd.isna(row["month"])
        )
        month_val = None if is_annual else int(row["month"])

        if is_annual:
            # Manual duplicate check: skip if already present
            exists = cursor.execute(
                """
                SELECT 1 FROM prices
                WHERE commodity_id = ? AND year_bs = ? AND month IS NULL
                """,
                (commodity_id, int(row["year_bs"])),
            ).fetchone()
            if exists:
                continue
            cursor.execute(
                """
                INSERT INTO prices
                    (commodity_id, year_bs, month, min_price, max_price, avg_price)
                VALUES (?, ?, NULL, ?, ?, ?)
                """,
                (
                    commodity_id,
                    int(row["year_bs"]),
                    row["min_price"],
                    row["max_price"],
                    row["avg_price"],
                ),
            )
        else:
            cursor.execute(
                """
                INSERT OR IGNORE INTO prices
                    (commodity_id, year_bs, month, min_price, max_price, avg_price)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    commodity_id,
                    int(row["year_bs"]),
                    month_val,
                    row["min_price"],
                    row["max_price"],
                    row["avg_price"],
                ),
            )
        count += 1
    conn.commit()
    return count


def _load_volume_month(conn: sqlite3.Connection, df: pd.DataFrame) -> int:
    """Insert volume-by-month records; return count of rows attempted."""
    cursor = conn.cursor()
    count = 0
    for _, row in df.iterrows():
        commodity_id = get_or_create_commodity(conn, row["commodity_name"])
        if commodity_id is None:
            continue
        cursor.execute(
            """
            INSERT OR IGNORE INTO volume_by_month
                (commodity_id, year_bs, month, volume_kg)
            VALUES (?, ?, ?, ?)
            """,
            (
                commodity_id,
                int(row["year_bs"]),
                int(row["month"]),
                row["volume_kg"],
            ),
        )
        count += 1
    conn.commit()
    return count


def _load_volume_source(conn: sqlite3.Connection, df: pd.DataFrame) -> int:
    """Insert volume-by-source records; return count of rows attempted."""
    cursor = conn.cursor()
    count = 0
    for _, row in df.iterrows():
        commodity_id = get_or_create_commodity(conn, row["commodity_name"])
        if commodity_id is None:
            continue
        cursor.execute(
            """
            INSERT OR IGNORE INTO volume_by_source
                (commodity_id, year_bs, source, volume_kg)
            VALUES (?, ?, ?, ?)
            """,
            (
                commodity_id,
                int(row["year_bs"]),
                str(row["source"]),
                row["volume_kg"],
            ),
        )
        count += 1
    conn.commit()
    return count


# ---------------------------------------------------------------------------
# Main ETL entry point
# ---------------------------------------------------------------------------

def load_all(data_dir: str) -> None:
    """
    Run the full ETL pipeline over all Excel files in *data_dir*.

    *data_dir* is resolved relative to the current working directory when
    it is not absolute, so running ``python run_etl.py`` from the project
    root works correctly.
    """
    data_path = Path(data_dir)
    if not data_path.is_absolute():
        data_path = Path.cwd() / data_path

    if not data_path.exists():
        raise FileNotFoundError(f"Data directory not found: {data_path}")

    # Find all yearly Excel files
    xlsx_files = sorted(data_path.glob("YearlyReport*.xlsx"))
    if not xlsx_files:
        print(f"WARNING: No YearlyReport*.xlsx files found in {data_path}")
        return

    conn = get_connection()

    for xlsx_path in xlsx_files:
        # Extract year from filename, e.g. YearlyReport2060.xlsx -> 2060
        match = re.search(r"(\d{4})", xlsx_path.stem)
        if not match:
            print(f"  SKIP: cannot parse year from {xlsx_path.name}")
            continue

        year = int(match.group(1))
        print(f"\nProcessing year {year} ({xlsx_path.name}) ...")

        try:
            # --- Extract ---
            raw = extract_year(str(xlsx_path), year)

            # --- Transform ---
            price_df = transform_price(raw["price"], year)
            vol_month_df = transform_volume_month(raw["volume_month"], year)
            vol_source_df = transform_volume_source(raw["volume_source"], year)

            # --- Load ---
            p_count = _load_prices(conn, price_df)
            vm_count = _load_volume_month(conn, vol_month_df)
            vs_count = _load_volume_source(conn, vol_source_df)

            print(
                f"  Loaded: {p_count} price rows, "
                f"{vm_count} volume-month rows, "
                f"{vs_count} volume-source rows"
            )

        except Exception as exc:
            print(f"  WARNING: Failed to process {xlsx_path.name}: {exc}")
            traceback.print_exc()
            continue

    conn.close()
    print("\nETL pipeline complete.")
