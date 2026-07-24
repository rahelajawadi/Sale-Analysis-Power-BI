"""Sale Dashboard - Full Insight (Streamlit recreation of the Power BI report)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import data as data_module

st.set_page_config(
    page_title="Sale Dashboard - Full Insight",
    page_icon="📊",
    layout="wide",
)

# Color palette echoing the original Power BI theme (blue-forward).
BLUE = "#1F9BFF"
DARK_BLUE = "#0B2A6B"
CATEGORY_COLORS = px.colors.qualitative.Set2

st.markdown(
    """
    <style>
    .kpi-card {
        background: #ffffff;
        border-radius: 10px;
        padding: 18px 20px;
        box-shadow: 0 1px 4px rgba(0,0,0,0.08);
        text-align: center;
    }
    .kpi-value { font-size: 2.1rem; font-weight: 700; color: #0B6BCB; }
    .kpi-label { font-size: 0.95rem; color: #555; margin-top: 2px; }
    .title-card {
        background: #ffffff; border-radius: 10px; padding: 14px 20px;
        box-shadow: 0 1px 4px rgba(0,0,0,0.08);
    }
    .title-main { font-size: 1.7rem; font-weight: 800; color: #1a1a1a; }
    .title-sub { font-size: 1.0rem; color: #666; }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(show_spinner=False)
def _load_default():
    return data_module.load_default()


@st.cache_data(show_spinner=False)
def _load_uploaded(file_bytes: bytes):
    return data_module.load_from_csv_bytes(file_bytes)


def human_format(num: float) -> str:
    num = float(num)
    for unit, div in (("B", 1e9), ("M", 1e6), ("K", 1e3)):
        if abs(num) >= div:
            return f"{num / div:.2f}{unit}"
    return f"{num:.0f}"


# ---------------------------------------------------------------- Sidebar
st.sidebar.header("Data source")
uploaded = st.sidebar.file_uploader(
    "Upload a sales CSV (optional)", type=["csv"],
    help="Columns: Order Date, Region, Country, Category, Ship Mode, Sales, "
         "Profit, Quantity (Sub-Category optional).",
)

if uploaded is not None:
    try:
        df = _load_uploaded(uploaded.getvalue())
        source_label = f"Uploaded: {uploaded.name}"
    except Exception as exc:  # noqa: BLE001
        st.sidebar.error(f"Could not read file: {exc}")
        df, source_label = _load_default()
else:
    df, source_label = _load_default()

st.sidebar.caption(source_label)

st.sidebar.header("Filters")

# Year slicer.
years = sorted(df["Year"].unique())
sel_years = st.sidebar.multiselect("Year", years, default=years)

# Country slicer.
countries = sorted(df["Country"].unique())
sel_countries = st.sidebar.multiselect(
    "Country", countries, default=[],
    help="Leave empty to include all countries.",
)

# Region / category / ship mode.
regions = sorted(df["Region"].unique())
sel_regions = st.sidebar.multiselect("Region", regions, default=[])

categories = sorted(df["Category"].unique())
sel_categories = st.sidebar.multiselect("Category", categories, default=[])

ship_modes = sorted(df["Ship Mode"].unique())
sel_ship = st.sidebar.multiselect("Ship Mode", ship_modes, default=[])

# Date range.
min_d, max_d = df["Order Date"].min(), df["Order Date"].max()
date_range = st.sidebar.date_input(
    "Order date range", value=(min_d, max_d), min_value=min_d, max_value=max_d,
)

# ---------------------------------------------------------------- Filtering
mask = pd.Series(True, index=df.index)
if sel_years:
    mask &= df["Year"].isin(sel_years)
if sel_countries:
    mask &= df["Country"].isin(sel_countries)
if sel_regions:
    mask &= df["Region"].isin(sel_regions)
if sel_categories:
    mask &= df["Category"].isin(sel_categories)
if sel_ship:
    mask &= df["Ship Mode"].isin(sel_ship)
if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
    start, end = pd.Timestamp(date_range[0]), pd.Timestamp(date_range[1])
    mask &= df["Order Date"].between(start, end)

fdf = df[mask]

# ---------------------------------------------------------------- Header + KPIs
top = st.columns([2.2, 1, 1, 1])
with top[0]:
    st.markdown(
        '<div class="title-card">'
        '<div class="title-main">📊 Sale Dashboard</div>'
        '<div class="title-sub">Full Insight</div></div>',
        unsafe_allow_html=True,
    )


def kpi(col, value, label):
    col.markdown(
        f'<div class="kpi-card"><div class="kpi-value">{value}</div>'
        f'<div class="kpi-label">{label}</div></div>',
        unsafe_allow_html=True,
    )


kpi(top[1], human_format(fdf["Sales"].sum()), "Sum of Sales")
kpi(top[2], human_format(fdf["Profit"].sum()), "Sum of Profit")
kpi(top[3], human_format(fdf["Quantity"].sum()), "Sum of Quantity")

st.markdown("")

if fdf.empty:
    st.warning("No data matches the current filters.")
    st.stop()

# ---------------------------------------------------------------- Row 1
row1 = st.columns([1, 1.4, 1.2])

# Treemap: Sum of Quantity by Region.
with row1[0]:
    st.subheader("Quantity by Region")
    region_q = (
        fdf.groupby("Region", as_index=False)["Quantity"].sum()
        .sort_values("Quantity", ascending=False)
    )
    fig = px.treemap(
        region_q, path=["Region"], values="Quantity",
        color="Quantity", color_continuous_scale="Blues",
    )
    fig.update_layout(margin=dict(t=10, l=0, r=0, b=0), height=360,
                      coloraxis_showscale=False)
    st.plotly_chart(fig, use_container_width=True)

# Sales & Profit by Order Date.
with row1[1]:
    st.subheader("Sales & Profit by Order Date")
    daily = (
        fdf.groupby("Order Date", as_index=False)[["Sales", "Profit"]].sum()
    )
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=daily["Order Date"], y=daily["Sales"],
                             name="Sum of Sales", line=dict(color=BLUE)))
    fig.add_trace(go.Scatter(x=daily["Order Date"], y=daily["Profit"],
                             name="Sum of Profit", line=dict(color=DARK_BLUE)))
    fig.update_layout(margin=dict(t=10, l=0, r=0, b=0), height=360,
                      legend=dict(orientation="h", y=1.1),
                      xaxis_title="Order Date", yaxis_title="Amount")
    st.plotly_chart(fig, use_container_width=True)

# Sales by Category.
with row1[2]:
    st.subheader("Sales by Category")
    cat = (
        fdf.groupby("Category", as_index=False)["Sales"].sum()
        .sort_values("Sales", ascending=True)
    )
    fig = px.bar(cat, x="Sales", y="Category", orientation="h",
                 color="Category", color_discrete_sequence=CATEGORY_COLORS)
    fig.update_layout(margin=dict(t=10, l=0, r=0, b=0), height=360,
                      showlegend=False, xaxis_title="Sum of Sales")
    st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------- Row 2
row2 = st.columns([1.2, 1.4])

# Sales by Ship Mode (pie).
with row2[0]:
    st.subheader("Sales by Ship Mode")
    ship = fdf.groupby("Ship Mode", as_index=False)["Sales"].sum()
    fig = px.pie(ship, names="Ship Mode", values="Sales", hole=0.0,
                 color_discrete_sequence=px.colors.sequential.Blues_r)
    fig.update_traces(textposition="outside",
                      texttemplate="%{value:.2s} (%{percent})")
    fig.update_layout(margin=dict(t=10, l=0, r=0, b=0), height=380,
                      legend=dict(orientation="h", y=-0.1))
    st.plotly_chart(fig, use_container_width=True)

# Sales by Year and Month.
with row2[1]:
    st.subheader("Sales by Year and Month")
    monthly = (
        fdf.groupby("Year-Month", as_index=False)["Sales"].sum()
        .sort_values("Year-Month")
    )
    fig = px.line(monthly, x="Year-Month", y="Sales", markers=True)
    fig.update_traces(line=dict(color=BLUE))
    fig.update_layout(margin=dict(t=10, l=0, r=0, b=0), height=380,
                      xaxis_title="Year / Month", yaxis_title="Sum of Sales")
    st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------- Detail + download
with st.expander("View & download filtered data"):
    st.dataframe(fdf.drop(columns=["Year-Month"]), use_container_width=True)
    st.download_button(
        "Download filtered data as CSV",
        data=fdf.drop(columns=["Year-Month"]).to_csv(index=False).encode("utf-8"),
        file_name="filtered_sales.csv",
        mime="text/csv",
    )
