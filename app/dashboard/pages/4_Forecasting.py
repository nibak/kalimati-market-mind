"""
Forecasting page — Kalimati Market Dashboard.

Features:
  1. Commodity + months-ahead selector
  2. Historical prices + forecast with confidence interval
  3. Anomaly flags (red dots) on historical chart
  4. Seasonal pattern bar chart (avg price by BS month)
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

from app.db.database import get_connection
from app.ml.forecasting import forecast_price, get_seasonal_pattern
from app.ml.anomaly import detect_anomalies
from app.utils.bs_calendar import BS_MONTHS, bs_period_label

st.set_page_config(page_title="Forecasting", page_icon="📈", layout="wide")


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------

@st.cache_data(ttl=600)
def load_commodities() -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT id, name_en FROM commodities ORDER BY name_en", conn
    )
    conn.close()
    return df


@st.cache_data(ttl=600)
def load_historical_prices(commodity_id: int) -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql_query(
        """
        SELECT year_bs, month, avg_price
        FROM prices
        WHERE commodity_id = ?
          AND month IS NOT NULL
          AND avg_price IS NOT NULL
        ORDER BY year_bs, month
        """,
        conn,
        params=(commodity_id,),
    )
    conn.close()
    if not df.empty:
        df["period"] = df.apply(
            lambda r: bs_period_label(r["year_bs"], r["month"]), axis=1
        )
    return df


@st.cache_data(ttl=600, show_spinner="Running forecast (SARIMA)...")
def run_forecast(commodity_id: int, months_ahead: int) -> pd.DataFrame:
    return forecast_price(commodity_id, months_ahead)


@st.cache_data(ttl=600)
def run_anomaly_detection(commodity_id: int, threshold: float) -> pd.DataFrame:
    return detect_anomalies(commodity_id, threshold)


@st.cache_data(ttl=600)
def run_seasonal_pattern(commodity_id: int) -> pd.DataFrame:
    return get_seasonal_pattern(commodity_id)


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

commodities = load_commodities()

with st.sidebar:
    st.title("Forecasting")
    if commodities.empty:
        st.warning("Run ETL first: `python run_etl.py`")
        st.stop()

    commodity_map = commodities.set_index("id")["name_en"].to_dict()
    default_id = st.session_state.get("selected_commodity_id", list(commodity_map.keys())[0])
    if default_id not in commodity_map:
        default_id = list(commodity_map.keys())[0]

    selected_id = st.selectbox(
        "Select Commodity",
        options=list(commodity_map.keys()),
        format_func=lambda x: commodity_map[x],
        index=list(commodity_map.keys()).index(default_id),
        key="selected_commodity_id",
    )
    selected_name = commodity_map[selected_id]

    st.markdown("---")
    months_ahead = st.slider(
        "Months to Forecast",
        min_value=1,
        max_value=36,
        value=12,
        step=1,
    )
    anomaly_threshold = st.slider(
        "Anomaly Threshold (std devs)",
        min_value=1.0,
        max_value=4.0,
        value=2.0,
        step=0.5,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

st.title("Price Forecasting & Anomaly Detection")
st.markdown(
    f"Commodity: **{selected_name}** | "
    f"Forecast: **{months_ahead} months** | "
    f"Anomaly threshold: **{anomaly_threshold:.1f} σ**"
)

historical_df = load_historical_prices(selected_id)

if historical_df.empty:
    st.warning("No historical price data available for this commodity.")
    st.stop()

# Run models
forecast_df = run_forecast(selected_id, months_ahead)
anomaly_df = run_anomaly_detection(selected_id, anomaly_threshold)
seasonal_df = run_seasonal_pattern(selected_id)

# ---- 1. Historical + Forecast chart with anomalies -------------------------
st.subheader("Historical Prices, Forecast & Anomalies")

fig = go.Figure()

# Historical line
fig.add_trace(
    go.Scatter(
        x=historical_df["period"],
        y=historical_df["avg_price"],
        name="Historical Avg Price",
        mode="lines",
        line=dict(color="#3498db", width=2),
    )
)

# Anomaly dots
if not anomaly_df.empty:
    anoms = anomaly_df[anomaly_df["is_anomaly"]].copy()
    if not anoms.empty:
        anoms["period"] = (
            anoms["year_bs"].astype(str) + "-" + anoms["month"].astype(str).str.zfill(2)
        )
        # Merge period to match historical_df index
        anoms_merged = anoms.merge(
            historical_df[["period", "avg_price"]],
            on="period",
            how="inner",
            suffixes=("_det", ""),
        )
        if not anoms_merged.empty:
            fig.add_trace(
                go.Scatter(
                    x=anoms_merged["period"],
                    y=anoms_merged["avg_price"],
                    name="Anomaly",
                    mode="markers",
                    marker=dict(color="#e74c3c", size=10, symbol="circle-open", line=dict(width=2)),
                )
            )

# Forecast confidence interval shading
if not forecast_df.empty:
    forecast_df["period"] = (
        forecast_df["year_bs"].astype(str) + "-" + forecast_df["month"].astype(str).str.zfill(2)
    )

    # Shade CI
    fig.add_trace(
        go.Scatter(
            x=list(forecast_df["period"]) + list(forecast_df["period"])[::-1],
            y=list(forecast_df["upper_ci"]) + list(forecast_df["lower_ci"])[::-1],
            fill="toself",
            fillcolor="rgba(231, 76, 60, 0.15)",
            line=dict(color="rgba(255,255,255,0)"),
            name="95% CI",
            showlegend=True,
        )
    )

    # Forecast line
    fig.add_trace(
        go.Scatter(
            x=forecast_df["period"],
            y=forecast_df["forecast_price"],
            name="Forecast",
            mode="lines+markers",
            line=dict(color="#e74c3c", width=2, dash="dash"),
            marker=dict(size=5),
        )
    )

fig.update_layout(
    title=f"{selected_name} — Price Forecast",
    xaxis=dict(title="Year-Month (BS)", tickangle=-45),
    yaxis=dict(title="Price (Rs/kg)"),
    height=500,
    legend=dict(orientation="h", y=1.05),
)
st.plotly_chart(fig, use_container_width=True)

# Forecast table
if not forecast_df.empty:
    with st.expander("View forecast values"):
        display_fc = forecast_df[["year_bs", "month", "forecast_price", "lower_ci", "upper_ci"]].copy()
        display_fc.columns = ["Year BS", "Month", "Forecast (Rs/kg)", "Lower CI", "Upper CI"]
        st.dataframe(display_fc, use_container_width=True, hide_index=True)

# ---- 2. Anomaly summary ---------------------------------------------------
st.subheader("Anomaly Detection Summary")

if anomaly_df.empty:
    st.info("No anomaly data available.")
else:
    n_anomalies = anomaly_df["is_anomaly"].sum()
    total_obs = len(anomaly_df)
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Observations", total_obs)
    col2.metric("Anomalies Detected", int(n_anomalies))
    col3.metric("Anomaly Rate", f"{n_anomalies / total_obs * 100:.1f}%" if total_obs > 0 else "N/A")

    if n_anomalies > 0:
        anom_table = anomaly_df[anomaly_df["is_anomaly"]].copy()
        anom_table = anom_table.sort_values("z_score", key=abs, ascending=False)
        anom_table["z_score"] = anom_table["z_score"].round(2)
        anom_table["avg_price"] = anom_table["avg_price"].round(2)
        anom_table["historical_avg"] = anom_table["historical_avg"].round(2)
        anom_display = anom_table[
            ["year_bs", "month", "avg_price", "historical_avg", "z_score"]
        ].head(20)
        anom_display.columns = ["Year BS", "Month", "Price (Rs/kg)", "Historical Avg", "Z-Score"]
        st.dataframe(anom_display, use_container_width=True, hide_index=True)

# ---- 3. Seasonal pattern bar chart ----------------------------------------
st.subheader("Seasonal Price Pattern (Average by Month)")

if seasonal_df.empty:
    st.info("No seasonal pattern data available.")
else:
    seasonal_df["month_name"] = seasonal_df["month"].map(BS_MONTHS)
    seasonal_df["error_upper"] = seasonal_df["avg_price"] + seasonal_df["std_price"]
    seasonal_df["error_lower"] = (seasonal_df["avg_price"] - seasonal_df["std_price"]).clip(lower=0)

    fig_season = go.Figure()
    fig_season.add_trace(
        go.Bar(
            x=seasonal_df["month_name"],
            y=seasonal_df["avg_price"],
            name="Avg Price",
            marker_color="#2ecc71",
            error_y=dict(
                type="data",
                symmetric=False,
                array=(seasonal_df["error_upper"] - seasonal_df["avg_price"]).tolist(),
                arrayminus=(seasonal_df["avg_price"] - seasonal_df["error_lower"]).tolist(),
                color="#27ae60",
            ),
        )
    )
    fig_season.update_layout(
        title=f"{selected_name} — Average Price by Month (All Years, ±1σ)",
        xaxis_title="Month (BS)",
        yaxis_title="Avg Price (Rs/kg)",
        height=380,
    )
    st.plotly_chart(fig_season, use_container_width=True)

    # Peak / trough months
    peak_row = seasonal_df.loc[seasonal_df["avg_price"].idxmax()]
    trough_row = seasonal_df.loc[seasonal_df["avg_price"].idxmin()]
    c1, c2 = st.columns(2)
    c1.success(
        f"Peak month: **{peak_row['month_name']}** "
        f"(avg Rs {peak_row['avg_price']:.0f}/kg)"
    )
    c2.info(
        f"Lowest month: **{trough_row['month_name']}** "
        f"(avg Rs {trough_row['avg_price']:.0f}/kg)"
    )
