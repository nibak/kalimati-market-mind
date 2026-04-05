"""
Price Analysis page — Kalimati Market Dashboard.

Charts:
  1. Dual-axis: avg price + monthly volume over time
  2. Seasonality heatmap (months vs years, colour = avg price)
  3. Commodity comparison: overlay two commodities' price trends
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
from app.utils.bs_calendar import BS_MONTHS, BS_MONTH_NAMES, bs_period_label

st.set_page_config(page_title="Price Analysis", page_icon="💰", layout="wide")


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
    row = conn.execute("SELECT MIN(year_bs), MAX(year_bs) FROM prices").fetchone()
    conn.close()
    return (row[0] or 2060, row[1] or 2081)


@st.cache_data(ttl=600)
def load_price_and_volume(commodity_id: int, y_min: int, y_max: int) -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql_query(
        """
        SELECT p.year_bs, p.month, p.avg_price,
               COALESCE(vm.volume_kg, 0) AS volume_kg
        FROM prices p
        LEFT JOIN volume_by_month vm
               ON vm.commodity_id = p.commodity_id
              AND vm.year_bs = p.year_bs
              AND vm.month   = p.month
        WHERE p.commodity_id = ?
          AND p.month IS NOT NULL
          AND p.year_bs BETWEEN ? AND ?
        ORDER BY p.year_bs, p.month
        """,
        conn,
        params=(commodity_id, y_min, y_max),
    )
    conn.close()
    if not df.empty:
        df["period"] = df.apply(
            lambda r: bs_period_label(r["year_bs"], r["month"]), axis=1
        )
    return df


@st.cache_data(ttl=600)
def load_price_heatmap(commodity_id: int, y_min: int, y_max: int) -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql_query(
        """
        SELECT year_bs, month, avg_price
        FROM prices
        WHERE commodity_id = ?
          AND month IS NOT NULL
          AND avg_price IS NOT NULL
          AND year_bs BETWEEN ? AND ?
        ORDER BY year_bs, month
        """,
        conn,
        params=(commodity_id, y_min, y_max),
    )
    conn.close()
    return df


@st.cache_data(ttl=600)
def load_price_series(commodity_id: int, y_min: int, y_max: int) -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql_query(
        """
        SELECT year_bs, month, avg_price
        FROM prices
        WHERE commodity_id = ?
          AND month IS NOT NULL
          AND avg_price IS NOT NULL
          AND year_bs BETWEEN ? AND ?
        ORDER BY year_bs, month
        """,
        conn,
        params=(commodity_id, y_min, y_max),
    )
    conn.close()
    if not df.empty:
        df["period"] = df.apply(
            lambda r: bs_period_label(r["year_bs"], r["month"]), axis=1
        )
    return df


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

commodities = load_commodities()
min_year, max_year = load_year_range()

with st.sidebar:
    st.title("Price Analysis")
    if commodities.empty:
        st.warning("Run ETL first: `python run_etl.py`")
        st.stop()

    commodity_map = commodities.set_index("id")["name_en"].to_dict()

    # Respect session_state selection from Home page
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


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

st.title("Price Analysis")
st.markdown(f"Analysing: **{selected_name}** | {year_range[0]}–{year_range[1]} BS")

# ---- 1. Dual-axis chart: avg price + volume ------------------------------------
st.subheader("Average Price & Monthly Volume Over Time")

pv_df = load_price_and_volume(selected_id, year_range[0], year_range[1])

if pv_df.empty:
    st.info("No data available for the selected commodity and year range.")
else:
    fig_dual = go.Figure()

    fig_dual.add_trace(
        go.Scatter(
            x=pv_df["period"],
            y=pv_df["avg_price"],
            name="Avg Price (Rs/kg)",
            mode="lines+markers",
            line=dict(color="#e74c3c", width=2),
            marker=dict(size=4),
            yaxis="y1",
        )
    )
    fig_dual.add_trace(
        go.Bar(
            x=pv_df["period"],
            y=pv_df["volume_kg"],
            name="Volume (kg)",
            marker_color="rgba(52, 152, 219, 0.5)",
            yaxis="y2",
        )
    )
    fig_dual.update_layout(
        title=f"{selected_name} — Price & Volume",
        xaxis=dict(title="Year-Month (BS)", tickangle=-45),
        yaxis=dict(title=dict(text="Avg Price (Rs/kg)", font=dict(color="#e74c3c"))),
        yaxis2=dict(
            title=dict(text="Volume (kg)", font=dict(color="#3498db")),
            overlaying="y",
            side="right",
        ),
        legend=dict(x=0, y=1.1, orientation="h"),
        height=450,
    )
    st.plotly_chart(fig_dual, use_container_width=True)

# ---- 2. Seasonality heatmap ---------------------------------------------------
st.subheader("Seasonality Heatmap (Avg Price by Month × Year)")

heat_df = load_price_heatmap(selected_id, year_range[0], year_range[1])

if heat_df.empty:
    st.info("No price data for heatmap.")
else:
    pivot = heat_df.pivot(index="year_bs", columns="month", values="avg_price")
    pivot.columns = [BS_MONTHS.get(m, str(m)) for m in pivot.columns]
    pivot = pivot.sort_index(ascending=False)

    fig_heat = px.imshow(
        pivot,
        title=f"{selected_name} — Avg Price Heatmap (Rs/kg)",
        labels=dict(x="Month", y="Year (BS)", color="Avg Price"),
        color_continuous_scale="YlOrRd",
        aspect="auto",
    )
    fig_heat.update_layout(height=500)
    st.plotly_chart(fig_heat, use_container_width=True)

# ---- 3. Commodity comparison --------------------------------------------------
st.subheader("Commodity Price Comparison")

compare_col1, compare_col2 = st.columns(2)
with compare_col1:
    cmp_id_1 = st.selectbox(
        "Commodity A",
        options=list(commodity_map.keys()),
        format_func=lambda x: commodity_map[x],
        index=list(commodity_map.keys()).index(selected_id),
        key="cmp_commodity_1",
    )
with compare_col2:
    # Default second commodity to the next one in the list
    keys = list(commodity_map.keys())
    idx2 = (keys.index(selected_id) + 1) % len(keys)
    cmp_id_2 = st.selectbox(
        "Commodity B",
        options=keys,
        format_func=lambda x: commodity_map[x],
        index=idx2,
        key="cmp_commodity_2",
    )

s1 = load_price_series(cmp_id_1, year_range[0], year_range[1])
s2 = load_price_series(cmp_id_2, year_range[0], year_range[1])

fig_cmp = go.Figure()
if not s1.empty:
    fig_cmp.add_trace(
        go.Scatter(
            x=s1["period"],
            y=s1["avg_price"],
            name=commodity_map[cmp_id_1],
            mode="lines+markers",
            line=dict(color="#2ecc71"),
        )
    )
if not s2.empty:
    fig_cmp.add_trace(
        go.Scatter(
            x=s2["period"],
            y=s2["avg_price"],
            name=commodity_map[cmp_id_2],
            mode="lines+markers",
            line=dict(color="#e67e22"),
        )
    )
fig_cmp.update_layout(
    title="Price Comparison",
    xaxis=dict(title="Year-Month (BS)", tickangle=-45),
    yaxis=dict(title="Avg Price (Rs/kg)"),
    height=400,
    legend=dict(x=0, y=1.1, orientation="h"),
)
st.plotly_chart(fig_cmp, use_container_width=True)
