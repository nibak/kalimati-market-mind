"""
Extractor: reads raw Excel sheets from each yearly Kalimati report.

Returns raw (untransformed) DataFrames so that the transformer can apply
year-specific logic without mixing concerns.

Key quirks handled here:
- 2060: Price header row=1 (0-indexed), data from row 2
          Volume/Month has extra Code + Percentage columns
- 2061+: Price header row=2 (0-indexed), data from row 3
- 2065+: "Volume by source " sheet name has a trailing space
"""

import pandas as pd
from pathlib import Path


# Sheet name variants
_PRICE_SHEET = "Price"
_VOL_MONTH_SHEET = "Volume by month"
_VOL_SOURCE_SHEET_VARIANTS = ["Volume by source", "Volume by source "]


def _find_sheet(xl: pd.ExcelFile, candidates: list[str]) -> str:
    """Return the first sheet name from *candidates* that exists in *xl*."""
    available = set(xl.sheet_names)
    for name in candidates:
        if name in available:
            return name
    # Fallback: try case-insensitive strip match
    for sheet in xl.sheet_names:
        if sheet.strip().lower() == "volume by source":
            return sheet
    raise KeyError(
        f"None of {candidates} found in workbook. Available: {xl.sheet_names}"
    )


def extract_year(filepath: str, year: int) -> dict[str, pd.DataFrame]:
    """
    Read all three data sheets from *filepath* and return them as a dict.

    Parameters
    ----------
    filepath : str
        Absolute path to the Excel file.
    year : int
        Bikram Sambat year (e.g. 2060).

    Returns
    -------
    dict with keys "price", "volume_month", "volume_source"
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {filepath}")

    xl = pd.ExcelFile(filepath, engine="openpyxl")

    # ------------------------------------------------------------------
    # Price sheet
    # ------------------------------------------------------------------
    if year == 2060:
        # header at row index 1, so header=1 means row 2 (0-indexed) is header
        price_df = pd.read_excel(
            xl, sheet_name=_PRICE_SHEET, header=1, engine="openpyxl"
        )
    else:
        price_df = pd.read_excel(
            xl, sheet_name=_PRICE_SHEET, header=2, engine="openpyxl"
        )

    # ------------------------------------------------------------------
    # Volume by month sheet
    # ------------------------------------------------------------------
    if year == 2060:
        vol_month_df = pd.read_excel(
            xl, sheet_name=_VOL_MONTH_SHEET, header=0, engine="openpyxl"
        )
    else:
        vol_month_df = pd.read_excel(
            xl, sheet_name=_VOL_MONTH_SHEET, header=0, engine="openpyxl"
        )

    # ------------------------------------------------------------------
    # Volume by source sheet
    # ------------------------------------------------------------------
    source_sheet = _find_sheet(xl, _VOL_SOURCE_SHEET_VARIANTS)
    vol_source_df = pd.read_excel(
        xl, sheet_name=source_sheet, header=0, engine="openpyxl"
    )

    # Drop last 2 rows (totals / percentages)
    if len(vol_source_df) > 2:
        vol_source_df = vol_source_df.iloc[:-2].copy()

    return {
        "price": price_df,
        "volume_month": vol_month_df,
        "volume_source": vol_source_df,
    }
