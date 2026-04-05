"""
Transformer: converts raw wide-format DataFrames into clean long-format records
ready for database insertion.

Price sheet layout (41 columns, 0-indexed):
  Col 0  : Commodity name
  Col 1  : Unit
  Cols 2-4  : Month 1  Min/Max/Avg
  Cols 5-7  : Month 2  Min/Max/Avg
  ...
  Cols 35-37: Month 12 Min/Max/Avg
  Cols 38-40: Annual   Min/Max/Avg

Volume by month (2060):
  Code no. | Commodity | Month 1 … 12 | Total kg | Percentage
Volume by month (2061+):
  Commodity | Month 1 … 12 | Total

Volume by source:
  Commodity | Source1 | Source2 | … (variable columns)
"""

import pandas as pd
import numpy as np
from typing import Optional


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_float(val) -> Optional[float]:
    """Convert to float, returning None for non-numeric / NaN values."""
    try:
        f = float(val)
        if np.isnan(f):
            return None
        return f
    except (TypeError, ValueError):
        return None


def _is_empty(val) -> bool:
    """Return True if the value is NaN, None, or an empty string."""
    if val is None:
        return True
    if isinstance(val, float) and np.isnan(val):
        return True
    if isinstance(val, str) and val.strip() == "":
        return True
    return False


# ---------------------------------------------------------------------------
# Price transformer
# ---------------------------------------------------------------------------

def transform_price(df: pd.DataFrame, year: int) -> pd.DataFrame:
    """
    Convert the wide-format price sheet into a long-format DataFrame.

    Returns columns:
        commodity_name, year_bs, month (int 1-12 or None), min_price,
        max_price, avg_price
    """
    records = []

    # Column layout: position 0=name, 1=unit, then triplets of (min,max,avg)
    # Months 1-12 occupy cols 2..37 (36 cols = 12*3)
    # Annual summary occupies cols 38-40

    for _, row in df.iterrows():
        raw_name = row.iloc[0]
        if _is_empty(raw_name):
            continue

        commodity_name = str(raw_name).strip()
        if not commodity_name:
            continue

        # Extract monthly prices
        for month_idx in range(12):  # 0-based month index
            col_base = 2 + month_idx * 3
            if col_base + 2 >= len(row):
                break

            min_p = _safe_float(row.iloc[col_base])
            max_p = _safe_float(row.iloc[col_base + 1])
            avg_p = _safe_float(row.iloc[col_base + 2])

            # Skip entirely missing month records
            if min_p is None and max_p is None and avg_p is None:
                continue

            records.append(
                {
                    "commodity_name": commodity_name,
                    "year_bs": year,
                    "month": month_idx + 1,
                    "min_price": min_p,
                    "max_price": max_p,
                    "avg_price": avg_p,
                }
            )

        # Annual summary (cols 38-40)
        if len(row) >= 41:
            min_p = _safe_float(row.iloc[38])
            max_p = _safe_float(row.iloc[39])
            avg_p = _safe_float(row.iloc[40])

            if not (min_p is None and max_p is None and avg_p is None):
                records.append(
                    {
                        "commodity_name": commodity_name,
                        "year_bs": year,
                        "month": None,   # annual
                        "min_price": min_p,
                        "max_price": max_p,
                        "avg_price": avg_p,
                    }
                )

    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# Volume by month transformer
# ---------------------------------------------------------------------------

def transform_volume_month(df: pd.DataFrame, year: int) -> pd.DataFrame:
    """
    Convert volume-by-month sheet to long format.

    Returns columns: commodity_name, year_bs, month (1-12), volume_kg
    """
    records = []

    if year == 2060:
        # Columns: Commodity | M1..M12 | Total kg | Percentage
        commodity_col_idx = 0
        month_start_idx = 1
        month_end_idx = 13   # exclusive
    else:
        # Columns: Commodity | M1..M12 | Total
        commodity_col_idx = 0
        month_start_idx = 1
        month_end_idx = 13   # exclusive

    for _, row in df.iterrows():
        raw_name = row.iloc[commodity_col_idx]
        if _is_empty(raw_name):
            continue

        commodity_name = str(raw_name).strip()
        if not commodity_name:
            continue

        for month_offset, col_idx in enumerate(range(month_start_idx, month_end_idx)):
            if col_idx >= len(row):
                break
            vol = _safe_float(row.iloc[col_idx])
            if vol is None:
                continue
            records.append(
                {
                    "commodity_name": commodity_name,
                    "year_bs": year,
                    "month": month_offset + 1,
                    "volume_kg": vol,
                }
            )

    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# Volume by source transformer
# ---------------------------------------------------------------------------

def transform_volume_source(df: pd.DataFrame, year: int) -> pd.DataFrame:
    """
    Convert volume-by-source sheet to long format.

    Returns columns: commodity_name, year_bs, source, volume_kg
    Rows where volume_kg is NaN or 0 are excluded.
    Source names have whitespace stripped.
    """
    if df.empty:
        return pd.DataFrame(columns=["commodity_name", "year_bs", "source", "volume_kg"])

    # The 2060 source sheet has an extra code column as col 0 (Unnamed: 0 with
    # values like 101.0, 102.0). Detect this and skip to the real name column.
    first_col_vals = pd.to_numeric(df.iloc[:, 0], errors="coerce")
    if first_col_vals.notna().mean() > 0.5:
        # Col 0 is mostly numeric codes — commodity name is in col 1
        commodity_col = df.columns[1]
        source_cols = df.columns[2:]
    else:
        commodity_col = df.columns[0]
        source_cols = df.columns[1:]

    # Melt to long format
    melted = df.melt(
        id_vars=[commodity_col],
        value_vars=source_cols,
        var_name="source",
        value_name="volume_kg",
    )

    # Rename commodity column
    melted = melted.rename(columns={commodity_col: "commodity_name"})

    # Clean up
    melted["commodity_name"] = melted["commodity_name"].astype(str).str.strip()
    melted["source"] = melted["source"].astype(str).str.strip()
    melted["volume_kg"] = pd.to_numeric(melted["volume_kg"], errors="coerce")

    # Add year
    melted["year_bs"] = year

    # Drop rows with empty commodity, NaN volume, or zero volume
    melted = melted[melted["commodity_name"].str.len() > 0]
    melted = melted[melted["commodity_name"].str.lower() != "nan"]
    melted = melted.dropna(subset=["volume_kg"])
    melted = melted[melted["volume_kg"] != 0]

    return melted[["commodity_name", "year_bs", "source", "volume_kg"]].reset_index(drop=True)
