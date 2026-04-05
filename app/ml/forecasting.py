"""
Price forecasting for Kalimati commodities.

Two approaches:
  - SARIMA(1,1,1)(1,1,1,12) when >= 24 monthly observations exist
  - Simple 12-month moving average as fallback

The Bikram Sambat calendar is used throughout (year_bs, month 1-12).
Forecast output uses the same calendar: after month 12 the year increments.
"""

import warnings
from typing import Optional

import numpy as np
import pandas as pd

from app.db.database import get_connection


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _fetch_monthly_prices(commodity_id: int) -> pd.DataFrame:
    """
    Return a DataFrame of monthly average prices sorted chronologically.
    Columns: year_bs, month, avg_price
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
    return df


def _next_year_month(year_bs: int, month: int) -> tuple[int, int]:
    """Increment a BS calendar month by one."""
    if month == 12:
        return year_bs + 1, 1
    return year_bs, month + 1


def _build_future_index(last_year: int, last_month: int, steps: int) -> list[tuple[int, int]]:
    """Return a list of (year_bs, month) tuples for the next *steps* periods."""
    result = []
    y, m = last_year, last_month
    for _ in range(steps):
        y, m = _next_year_month(y, m)
        result.append((y, m))
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def forecast_price(
    commodity_id: int,
    months_ahead: int = 12,
) -> pd.DataFrame:
    """
    Forecast monthly average prices for a commodity.

    Uses SARIMA(1,1,1)(1,1,1,12) when there are >= 24 observations,
    otherwise falls back to a 12-month rolling average.

    Parameters
    ----------
    commodity_id : int
    months_ahead : int
        Number of months to forecast into the future.

    Returns
    -------
    pd.DataFrame with columns:
        year_bs, month, forecast_price, lower_ci, upper_ci
    """
    df = _fetch_monthly_prices(commodity_id)

    if df.empty:
        return pd.DataFrame(
            columns=["year_bs", "month", "forecast_price", "lower_ci", "upper_ci"]
        )

    series = df["avg_price"].values.astype(float)
    last_year = int(df["year_bs"].iloc[-1])
    last_month = int(df["month"].iloc[-1])
    future_index = _build_future_index(last_year, last_month, months_ahead)

    if len(series) >= 24:
        forecast_vals, lower_ci, upper_ci = _sarima_forecast(series, months_ahead)
    else:
        forecast_vals, lower_ci, upper_ci = _moving_average_forecast(series, months_ahead)

    records = []
    for i, (y, m) in enumerate(future_index):
        records.append(
            {
                "year_bs": y,
                "month": m,
                "forecast_price": round(float(forecast_vals[i]), 2),
                "lower_ci": round(float(lower_ci[i]), 2),
                "upper_ci": round(float(upper_ci[i]), 2),
            }
        )

    return pd.DataFrame(records)


def get_seasonal_pattern(commodity_id: int) -> pd.DataFrame:
    """
    Return average price by month (1-12) aggregated across all available years.

    Columns: month, avg_price, std_price, count
    """
    df = _fetch_monthly_prices(commodity_id)
    if df.empty:
        return pd.DataFrame(columns=["month", "avg_price", "std_price", "count"])

    pattern = (
        df.groupby("month")["avg_price"]
        .agg(avg_price="mean", std_price="std", count="count")
        .reset_index()
    )
    pattern["std_price"] = pattern["std_price"].fillna(0)
    return pattern


# ---------------------------------------------------------------------------
# Forecasting implementations
# ---------------------------------------------------------------------------

def _sarima_forecast(
    series: np.ndarray,
    steps: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Fit SARIMA(1,1,1)(1,1,1,12) and return forecast + 95 % CI arrays."""
    try:
        from statsmodels.tsa.statespace.sarimax import SARIMAX

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            model = SARIMAX(
                series,
                order=(1, 1, 1),
                seasonal_order=(1, 1, 1, 12),
                enforce_stationarity=False,
                enforce_invertibility=False,
            )
            result = model.fit(disp=False, maxiter=200)
            forecast = result.get_forecast(steps=steps)
            mean = forecast.predicted_mean
            ci = forecast.conf_int(alpha=0.05)

            # Clip to non-negative prices
            lower = np.maximum(ci[:, 0], 0)
            upper = np.maximum(ci[:, 1], 0)
            mean = np.maximum(mean, 0)

        return mean, lower, upper

    except Exception:
        # If SARIMA fails for any reason, fall back
        return _moving_average_forecast(series, steps)


def _moving_average_forecast(
    series: np.ndarray,
    steps: int,
    window: int = 12,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Simple rolling-mean forecast.
    CI is ±1.96 * std of the last *window* observations.
    """
    window = min(window, len(series))
    tail = series[-window:]
    mean_val = float(np.mean(tail))
    std_val = float(np.std(tail)) if len(tail) > 1 else 0.0
    margin = 1.96 * std_val

    forecast = np.full(steps, max(mean_val, 0))
    lower = np.maximum(forecast - margin, 0)
    upper = forecast + margin

    return forecast, lower, upper
