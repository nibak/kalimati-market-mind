"""
SQLite database connection and schema management for Kalimati Market Data.
DB path is resolved relative to the project root (two levels above this file).
"""

import sqlite3
import os
from pathlib import Path

# Resolve project root: app/db/database.py -> app/db -> app -> project_root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DB_PATH = PROJECT_ROOT / "data" / "kalimati.db"


def get_connection() -> sqlite3.Connection:
    """Return a SQLite connection to the Kalimati database."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def init_db() -> None:
    """Create all tables if they do not already exist."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS commodities (
            id   INTEGER PRIMARY KEY AUTOINCREMENT,
            name_en TEXT NOT NULL UNIQUE,
            category TEXT
        );

        CREATE TABLE IF NOT EXISTS prices (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            commodity_id INTEGER NOT NULL,
            year_bs      INTEGER NOT NULL,
            month        INTEGER,       -- 1-12; NULL = annual summary
            min_price    REAL,
            max_price    REAL,
            avg_price    REAL,
            FOREIGN KEY (commodity_id) REFERENCES commodities(id),
            UNIQUE(commodity_id, year_bs, month)
        );

        CREATE TABLE IF NOT EXISTS volume_by_month (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            commodity_id INTEGER NOT NULL,
            year_bs      INTEGER NOT NULL,
            month        INTEGER NOT NULL,   -- 1-12
            volume_kg    REAL,
            FOREIGN KEY (commodity_id) REFERENCES commodities(id),
            UNIQUE(commodity_id, year_bs, month)
        );

        CREATE TABLE IF NOT EXISTS volume_by_source (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            commodity_id INTEGER NOT NULL,
            year_bs      INTEGER NOT NULL,
            source       TEXT NOT NULL,
            volume_kg    REAL,
            FOREIGN KEY (commodity_id) REFERENCES commodities(id),
            UNIQUE(commodity_id, year_bs, source)
        );
    """)

    conn.commit()
    conn.close()
    print(f"Database initialised at: {DB_PATH}")
