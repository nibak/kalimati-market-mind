"""
Kalimati Agricultural Market Data Platform — Home page.

Run with:
    streamlit run app/dashboard/Home.py
"""

import sys
from pathlib import Path

# Ensure project root is on sys.path so `app.*` imports work regardless of
# where streamlit is launched from.
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import plotly.express as px
import streamlit as st

from app.db.database import get_connection

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Kalimati Market Platform",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------------------------------------------------------------------------
# Cached data loaders
# ---------------------------------------------------------------------------

@st.cache_data(ttl=600)
def load_commodities() -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT id, name_en, category FROM commodities ORDER BY name_en",
        conn,
    )
    conn.close()
    return df


@st.cache_data(ttl=600)
def load_year_range() -> tuple[int, int]:
    conn = get_connection()
    row = conn.execute(
        "SELECT MIN(year_bs), MAX(year_bs) FROM prices"
    ).fetchone()
    conn.close()
    return (row[0] or 2060, row[1] or 2081)


@st.cache_data(ttl=600)
def load_price_trend(commodity_id: int) -> pd.DataFrame:
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
    if df.empty:
        return df
    df["period"] = df["year_bs"].astype(str) + "-" + df["month"].astype(str).str.zfill(2)
    return df


@st.cache_data(ttl=600)
def load_latest_year_stats(year_bs: int) -> dict:
    conn = get_connection()
    n_commodities = conn.execute(
        "SELECT COUNT(DISTINCT commodity_id) FROM prices WHERE year_bs = ?",
        (year_bs,),
    ).fetchone()[0]
    total_volume = conn.execute(
        "SELECT SUM(volume_kg) FROM volume_by_month WHERE year_bs = ?",
        (year_bs,),
    ).fetchone()[0]
    conn.close()
    return {
        "n_commodities": n_commodities or 0,
        "total_volume_kg": total_volume or 0,
    }


# ---------------------------------------------------------------------------
# Sidebar — shared commodity selector
# ---------------------------------------------------------------------------

commodities = load_commodities()
min_year, max_year = load_year_range()

with st.sidebar:
    st.title("Kalimati Market")
    st.markdown("---")

    if commodities.empty:
        st.warning("No commodities found. Run the ETL pipeline first: `python run_etl.py`")
        st.stop()

    commodity_options = commodities.set_index("id")["name_en"].to_dict()
    selected_id = st.selectbox(
        "Select Commodity",
        options=list(commodity_options.keys()),
        format_func=lambda x: commodity_options[x],
        key="selected_commodity_id",
    )
    selected_name = commodity_options[selected_id]

    year_range = st.slider(
        "Year Range (BS)",
        min_value=min_year,
        max_value=max_year,
        value=(min_year, max_year),
        key="selected_year_range",
    )

    st.markdown("---")
    st.caption(f"Data: {min_year}–{max_year} BS | Kalimati Fruit & Vegetable Market")


# ---------------------------------------------------------------------------
# Main content
# ---------------------------------------------------------------------------

st.title("Kalimati Agricultural Market Data Platform")
st.markdown(
    "Explore **21 years** of price, volume, and supply-chain data "
    "from Nepal's largest wholesale fruit & vegetable market."
)

# KPI cards
latest_year = max_year
latest_stats = load_latest_year_stats(latest_year)
total_years = max_year - min_year + 1  # note: 2066 is missing

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Commodities (DB)", len(commodities))
col2.metric("Years of Data", total_years)
col3.metric(
    f"Commodities in {latest_year} BS",
    latest_stats["n_commodities"],
)
col4.metric(
    f"Total Volume {latest_year} BS",
    f"{latest_stats['total_volume_kg'] / 1_000_000:.1f} M kg"
    if latest_stats["total_volume_kg"]
    else "N/A",
)

st.markdown("---")

# Overview: price trend for selected commodity
st.subheader(f"Price Trend — {selected_name}")
trend_df = load_price_trend(selected_id)

if trend_df.empty:
    st.info("No price data available for this commodity.")
else:
    # Filter by selected year range
    trend_df = trend_df[
        trend_df["year_bs"].between(year_range[0], year_range[1])
    ]
    if trend_df.empty:
        st.info("No data for the selected year range.")
    else:
        fig = px.line(
            trend_df,
            x="period",
            y="avg_price",
            title=f"{selected_name} — Monthly Average Price (Rs/kg)",
            labels={"period": "Year-Month (BS)", "avg_price": "Avg Price (Rs/kg)"},
            markers=True,
        )
        fig.update_layout(xaxis_tickangle=-45, height=400)
        fig.update_traces(line_color="#2ecc71", marker_color="#27ae60")
        st.plotly_chart(fig, use_container_width=True)

# Category breakdown
st.markdown("---")
st.subheader("Commodity Categories")
cat_counts = commodities["category"].value_counts().reset_index()
cat_counts.columns = ["Category", "Count"]
fig_cat = px.pie(
    cat_counts,
    names="Category",
    values="Count",
    title="Commodities by Category",
    color_discrete_sequence=px.colors.qualitative.Set3,
)
fig_cat.update_traces(textposition="inside", textinfo="percent+label")

col_a, col_b = st.columns([1, 2])
with col_a:
    st.dataframe(cat_counts, use_container_width=True, hide_index=True)
with col_b:
    st.plotly_chart(fig_cat, use_container_width=True)

st.markdown("---")
st.caption(
    "Data source: Kalimati Fruits and Vegetable Market Development Board, "
    "Kathmandu, Nepal | Years 2060–2081 BS"
)
