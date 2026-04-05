"""
Anomaly detection for Kalimati commodity prices.

Strategy: for every (commodity, month) cell compute the historical mean and
standard deviation across all available years.  A data point is flagged as
anomalous when |z_score| >= threshold_std.
"""

import pandas as pd
import numpy as np

from app.db.database import get_connection


def detect_anomalies(
    commodity_id: int,
    threshold_std: float = 2.0,
) -> pd.DataFrame:
    """
    Detect price anomalies for the given commodity.

    For each monthly price record the function computes:
      - historical_avg : mean avg_price for that calendar month across all years
      - historical_std : std of avg_price for that calendar month
      - z_score        : (avg_price - historical_avg) / historical_std
      - is_anomaly     : True when |z_score| >= threshold_std

    Parameters
    ----------
    commodity_id : int
    threshold_std : float
        Number of standard deviations that defines an anomaly boundary.

    Returns
    -------
    pd.DataFrame with columns:
        year_bs, month, avg_price, historical_avg, historical_std,
        z_score, is_anomaly
    """
    conn = get_connection()
    query = """
        SELECT year_bs, month, avg_price
        FROM prices
        WHERE commodity_id = ?
          AND month IS NOT NULL
          AND avg_price IS NOT NULL
        ORDER BY year_bs, month
    """
    df = pd.read_sql_query(query, conn, params=(commodity_id,))
    conn.close()

    if df.empty:
        return pd.DataFrame(
            columns=[
                "year_bs", "month", "avg_price",
                "historical_avg", "historical_std", "z_score", "is_anomaly",
            ]
        )

    # Compute per-month historical statistics
    month_stats = (
        df.groupby("month")["avg_price"]
        .agg(historical_avg="mean", historical_std="std")
        .reset_index()
    )
    month_stats["historical_std"] = month_stats["historical_std"].fillna(0)

    # Merge back
    result = df.merge(month_stats, on="month", how="left")

    # Z-score (guard against zero std)
    result["z_score"] = np.where(
        result["historical_std"] > 0,
        (result["avg_price"] - result["historical_avg"]) / result["historical_std"],
        0.0,
    )

    result["is_anomaly"] = result["z_score"].abs() >= threshold_std

    return result[
        [
            "year_bs", "month", "avg_price",
            "historical_avg", "historical_std", "z_score", "is_anomaly",
        ]
    ].reset_index(drop=True)
