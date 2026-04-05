"""
Supply Analysis page — Kalimati Market Dashboard.

Charts:
  1. Total supply volume by year (bar chart)
  2. Monthly supply pattern (line chart)
  3. Year-over-year supply comparison (multi-line)
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from app.db.database import get_connection
from app.utils.bs_calendar import BS_MONTHS, BS_MONTH_NAMES

st.set_page_config(page_title="Supply Analysis", page_icon="📦", layout="wide")


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
def load_year_range() -> tuple[int, int]:
    conn = get_connection()
    row = conn.execute(
        "SELECT MIN(year_bs), MAX(year_bs) FROM volume_by_month"
    ).fetchone()
    conn.close()
    return (row[0] or 2060, row[1] or 2081)


@st.cache_data(ttl=600)
def load_yearly_volume(commodity_id: int, y_min: int, y_max: int) -> pd.DataFrame:
    """Total volume per year."""
    conn = get_connection()
    df = pd.read_sql_query(
        """
        SELECT year_bs, SUM(volume_kg) AS total_volume_kg
        FROM volume_by_month
        WHERE commodity_id = ?
          AND year_bs BETWEEN ? AND ?
        GROUP BY year_bs
        ORDER BY year_bs
        """,
        conn,
        params=(commodity_id, y_min, y_max),
    )
    conn.close()
    return df


@st.cache_data(ttl=600)
def load_monthly_pattern(commodity_id: int, y_min: int, y_max: int) -> pd.DataFrame:
    """Average volume by calendar month, aggregated across years."""
    conn = get_connection()
    df = pd.read_sql_query(
        """
        SELECT month,
               AVG(volume_kg)  AS avg_volume_kg,
               SUM(volume_kg)  AS total_volume_kg,
               COUNT(*)        AS n_years
        FROM volume_by_month
        WHERE commodity_id = ?
          AND year_bs BETWEEN ? AND ?
        GROUP BY month
        ORDER BY month
        """,
        conn,
        params=(commodity_id, y_min, y_max),
    )
    conn.close()
    return df


@st.cache_data(ttl=600)
def load_monthly_by_year(commodity_id: int, y_min: int, y_max: int) -> pd.DataFrame:
    """Monthly volumes per year — used for YoY comparison."""
    conn = get_connection()
    df = pd.read_sql_query(
        """
        SELECT year_bs, month, volume_kg
        FROM volume_by_month
        WHERE commodity_id = ?
          AND year_bs BETWEEN ? AND ?
        ORDER BY year_bs, month
        """,
        conn,
        params=(commodity_id, y_min, y_max),
    )
    conn.close()
    return df


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

commodities = load_commodities()
min_year, max_year = load_year_range()

with st.sidebar:
    st.title("Supply Analysis")
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

    year_range = st.slider(
        "Year Range (BS)",
        min_value=min_year,
        max_value=max_year,
        value=st.session_state.get("selected_year_range", (min_year, max_year)),
        key="selected_year_range",
    )

    st.markdown("---")
    # Year-over-year comparison selector
    available_years = list(range(year_range[0], year_range[1] + 1))
    yoy_years = st.multiselect(
        "Years for YoY Comparison",
        options=available_years,
        default=available_years[-min(5, len(available_years)):],
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

st.title("Supply Analysis")
st.markdown(f"Analysing: **{selected_name}** | {year_range[0]}–{year_range[1]} BS")

# ---- 1. Total supply by year -----------------------------------------------
st.subheader("Total Annual Supply Volume")

yearly_df = load_yearly_volume(selected_id, year_range[0], year_range[1])

if yearly_df.empty:
    st.info("No volume data available for this commodity and year range.")
else:
    fig_year = px.bar(
        yearly_df,
        x="year_bs",
        y="total_volume_kg",
        title=f"{selected_name} — Annual Supply (kg)",
        labels={"year_bs": "Year (BS)", "total_volume_kg": "Total Volume (kg)"},
        color="total_volume_kg",
        color_continuous_scale="Blues",
    )
    fig_year.update_layout(height=400, coloraxis_showscale=False)
    st.plotly_chart(fig_year, use_container_width=True)

    # Summary stats
    c1, c2, c3 = st.columns(3)
    c1.metric("Peak Year", int(yearly_df.loc[yearly_df["total_volume_kg"].idxmax(), "year_bs"]))
    c2.metric(
        "Peak Volume",
        f"{yearly_df['total_volume_kg'].max() / 1_000:.0f} tonnes",
    )
    c3.metric(
        "Avg Annual Volume",
        f"{yearly_df['total_volume_kg'].mean() / 1_000:.0f} tonnes",
    )

# ---- 2. Monthly supply pattern (average across years) ----------------------
st.subheader("Average Monthly Supply Pattern")

monthly_df = load_monthly_pattern(selected_id, year_range[0], year_range[1])

if monthly_df.empty:
    st.info("No monthly data available.")
else:
    monthly_df["month_name"] = monthly_df["month"].map(BS_MONTHS)

    fig_month = px.line(
        monthly_df,
        x="month",
        y="avg_volume_kg",
        title=f"{selected_name} — Average Monthly Supply (kg)",
        labels={"month": "Month (BS)", "avg_volume_kg": "Avg Volume (kg)"},
        markers=True,
    )
    fig_month.update_xaxes(
        tickvals=list(range(1, 13)),
        ticktext=BS_MONTH_NAMES,
    )
    fig_month.update_traces(line_color="#27ae60", marker_color="#2ecc71")
    fig_month.update_layout(height=380)
    st.plotly_chart(fig_month, use_container_width=True)

# ---- 3. Year-over-year comparison ------------------------------------------
st.subheader("Year-over-Year Supply Comparison")

yoy_df = load_monthly_by_year(selected_id, year_range[0], year_range[1])

if yoy_df.empty or not yoy_years:
    st.info("Select years in the sidebar to display comparison.")
else:
    yoy_filtered = yoy_df[yoy_df["year_bs"].isin(yoy_years)]
    if yoy_filtered.empty:
        st.info("No data for the selected years.")
    else:
        fig_yoy = go.Figure()
        for yr in sorted(yoy_years):
            yr_data = yoy_filtered[yoy_filtered["year_bs"] == yr].copy()
            if yr_data.empty:
                continue
            fig_yoy.add_trace(
                go.Scatter(
                    x=yr_data["month"],
                    y=yr_data["volume_kg"],
                    name=str(yr),
                    mode="lines+markers",
                )
            )
        fig_yoy.update_xaxes(
            tickvals=list(range(1, 13)),
            ticktext=[
                "Baisakh", "Jestha", "Ashadh", "Shrawan",
                "Bhadra", "Ashwin", "Kartik", "Mangsir",
                "Poush", "Magh", "Falgun", "Chaitra",
            ],
        )
        fig_yoy.update_layout(
            title=f"{selected_name} — Monthly Volume by Year",
            xaxis_title="Month (BS)",
            yaxis_title="Volume (kg)",
            height=430,
            legend=dict(orientation="h", y=1.05),
        )
        st.plotly_chart(fig_yoy, use_container_width=True)
