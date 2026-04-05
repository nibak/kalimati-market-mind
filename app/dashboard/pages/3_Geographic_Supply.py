"""
Geographic Supply page — Kalimati Market Dashboard.

Charts:
  1. Treemap: % supply by source for selected commodity + year
  2. Pie chart: domestic vs imports
  3. Table: top 5 sources by volume
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import plotly.express as px
import streamlit as st

from app.db.database import get_connection

st.set_page_config(page_title="Geographic Supply", page_icon="🗺️", layout="wide")

# Import countries / regions treated as imports
IMPORT_SOURCES = {"india", "china", "bhutan", "pakistan", "bangladesh"}


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
        "SELECT MIN(year_bs), MAX(year_bs) FROM volume_by_source"
    ).fetchone()
    conn.close()
    return (row[0] or 2060, row[1] or 2081)


@st.cache_data(ttl=600)
def load_source_data(commodity_id: int, year_bs: int) -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql_query(
        """
        SELECT source, volume_kg
        FROM volume_by_source
        WHERE commodity_id = ?
          AND year_bs = ?
          AND volume_kg > 0
        ORDER BY volume_kg DESC
        """,
        conn,
        params=(commodity_id, year_bs),
    )
    conn.close()
    return df


@st.cache_data(ttl=600)
def load_source_trend(commodity_id: int) -> pd.DataFrame:
    """Volume per source per year across all years — for trend chart."""
    conn = get_connection()
    df = pd.read_sql_query(
        """
        SELECT year_bs, source, SUM(volume_kg) AS volume_kg
        FROM volume_by_source
        WHERE commodity_id = ?
          AND volume_kg > 0
        GROUP BY year_bs, source
        ORDER BY year_bs, source
        """,
        conn,
        params=(commodity_id,),
    )
    conn.close()
    return df


@st.cache_data(ttl=600)
def load_available_years(commodity_id: int) -> list[int]:
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT DISTINCT year_bs
        FROM volume_by_source
        WHERE commodity_id = ?
        ORDER BY year_bs
        """,
        (commodity_id,),
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def classify_source(source: str) -> str:
    """Return 'Import' or 'Domestic' based on source name."""
    return "Import" if source.strip().lower() in IMPORT_SOURCES else "Domestic"


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

commodities = load_commodities()
min_year, max_year = load_year_range()

with st.sidebar:
    st.title("Geographic Supply")
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

    available_years = load_available_years(selected_id)
    if not available_years:
        st.warning("No source data for this commodity.")
        st.stop()

    selected_year = st.selectbox(
        "Select Year (BS)",
        options=available_years,
        index=len(available_years) - 1,
        key="geo_selected_year",
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

st.title("Geographic Supply Analysis")
st.markdown(f"Analysing: **{selected_name}** | Year: **{selected_year} BS**")

source_df = load_source_data(selected_id, selected_year)

if source_df.empty:
    st.info("No source data available for this commodity and year.")
    st.stop()

# Add domestic / import classification
source_df["type"] = source_df["source"].apply(classify_source)
total_vol = source_df["volume_kg"].sum()
source_df["pct"] = (source_df["volume_kg"] / total_vol * 100).round(2)

# ---- 1. Treemap -----------------------------------------------------------
st.subheader("Supply Source Treemap")

fig_tree = px.treemap(
    source_df,
    path=["type", "source"],
    values="volume_kg",
    color="volume_kg",
    color_continuous_scale="Greens",
    title=f"{selected_name} ({selected_year} BS) — Supply by Source",
    hover_data={"pct": ":.2f"},
)
fig_tree.update_traces(
    textinfo="label+percent parent",
    hovertemplate="<b>%{label}</b><br>Volume: %{value:,.0f} kg<br>%{customdata[0]:.2f}% of total",
)
fig_tree.update_layout(height=500)
st.plotly_chart(fig_tree, use_container_width=True)

# ---- 2. Domestic vs Import pie ---------------------------------------------
st.subheader("Domestic vs Import Split")

type_agg = source_df.groupby("type")["volume_kg"].sum().reset_index()
fig_pie = px.pie(
    type_agg,
    names="type",
    values="volume_kg",
    title=f"{selected_name} ({selected_year} BS) — Domestic vs Import",
    color="type",
    color_discrete_map={"Domestic": "#2ecc71", "Import": "#e74c3c"},
)
fig_pie.update_traces(
    textposition="inside",
    textinfo="percent+label",
    pull=[0.05, 0],
)
fig_pie.update_layout(height=400)

col_pie, col_stats = st.columns([1, 1])
with col_pie:
    st.plotly_chart(fig_pie, use_container_width=True)
with col_stats:
    st.markdown("**Supply Summary**")
    for _, row in type_agg.iterrows():
        pct = row["volume_kg"] / total_vol * 100
        st.metric(
            row["type"],
            f"{row['volume_kg'] / 1_000:.1f} tonnes",
            f"{pct:.1f}% of total",
        )

# ---- 3. Top 5 sources table ------------------------------------------------
st.subheader("Top 5 Supply Sources")

top5 = source_df.nlargest(5, "volume_kg")[["source", "type", "volume_kg", "pct"]].copy()
top5["volume_kg"] = top5["volume_kg"].apply(lambda x: f"{x:,.0f} kg")
top5["pct"] = top5["pct"].apply(lambda x: f"{x:.2f}%")
top5.columns = ["Source", "Type", "Volume", "% of Total"]
st.dataframe(top5, use_container_width=True, hide_index=True)

# ---- 4. Source volume trend over years ------------------------------------
st.subheader("Supply Volume by Source — Year-over-Year Trend")

trend_df = load_source_trend(selected_id)

if trend_df.empty:
    st.info("No multi-year source data available.")
else:
    trend_df["type"] = trend_df["source"].apply(classify_source)

    view = st.radio(
        "Group by",
        ["Individual Sources", "Domestic vs Import"],
        horizontal=True,
        key="geo_trend_view",
    )

    if view == "Domestic vs Import":
        plot_df = (
            trend_df.groupby(["year_bs", "type"])["volume_kg"]
            .sum()
            .reset_index()
            .rename(columns={"type": "source"})
        )
        color_map = {"Domestic": "#2ecc71", "Import": "#e74c3c"}
    else:
        # Keep only top N sources by total volume to avoid clutter
        top_sources = (
            trend_df.groupby("source")["volume_kg"]
            .sum()
            .nlargest(10)
            .index.tolist()
        )
        plot_df = trend_df[trend_df["source"].isin(top_sources)]
        color_map = None

    fig_trend = px.area(
        plot_df,
        x="year_bs",
        y="volume_kg",
        color="source",
        title=f"{selected_name} — Supply Volume by Source Over Years",
        labels={"year_bs": "Year (BS)", "volume_kg": "Volume (kg)", "source": "Source"},
        color_discrete_map=color_map,
    )
    fig_trend.update_layout(
        height=480,
        xaxis=dict(dtick=2),
        legend=dict(orientation="h", y=-0.25),
        hovermode="x unified",
    )
    st.plotly_chart(fig_trend, use_container_width=True)

# Full source table (expandable)
with st.expander("View all sources"):
    all_sources = source_df[["source", "type", "volume_kg", "pct"]].copy()
    all_sources = all_sources.sort_values("volume_kg", ascending=False)
    all_sources["volume_kg"] = all_sources["volume_kg"].apply(lambda x: f"{x:,.0f} kg")
    all_sources["pct"] = all_sources["pct"].apply(lambda x: f"{x:.2f}%")
    all_sources.columns = ["Source", "Type", "Volume", "% of Total"]
    st.dataframe(all_sources, use_container_width=True, hide_index=True)
