from __future__ import annotations

import sys
from pathlib import Path

import plotly.express as px
import streamlit as st

PROJECT_ROOT = next(
    (p for p in [Path(__file__).resolve().parent, *Path(__file__).resolve().parents] if (p / "src").exists()),
    Path(__file__).resolve().parent,
)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.metrics import apply_filters_margins, load_margin_monthly, refresh_warehouse, render_sidebar_filters_margins

st.title("Margins Explore - Dynamic")
st.caption("Choose dimensions and measures freely for accounting gross margin analysis")

if st.sidebar.button("Refresh data", key="refresh_margins_explore"):
    with st.spinner("Rebuilding warehouse..."):
        refresh_warehouse()
    st.sidebar.success("Warehouse refreshed")

try:
    df = load_margin_monthly()
except Exception as exc:
    st.error("Margin dataset is not available. Run warehouse build first.")
    st.exception(exc)
    st.stop()

if df.empty:
    st.warning("No margin data available.")
    st.stop()

filters = render_sidebar_filters_margins(df, key_prefix="margins_explore")
filtered = apply_filters_margins(df, filters)

if filtered.empty:
    st.warning("No margin data for selected filters.")
    st.stop()

dim_options = ["Product", "Category", "Wilaya", "Year", "Month", "YearMonth"]
dim_map = {
    "Product": "product_name",
    "Category": "category",
    "Wilaya": "wilaya_name",
    "Year": "year",
    "Month": "month_name",
    "YearMonth": "year_month",
}
measure_options = ["Revenue", "COGS", "Gross Margin Value", "Gross Margin %", "Sold Qty", "PMP Unit Cost"]

c1, c2, c3 = st.columns(3)
primary_dim_label = c1.selectbox("Primary dimension", options=dim_options, index=0)
use_secondary = c2.checkbox("Use secondary dimension", value=False)
secondary_dim_label = c3.selectbox(
    "Secondary dimension",
    options=dim_options,
    index=1,
    disabled=not use_secondary,
)

c4, c5, c6 = st.columns(3)
measure_label = c4.selectbox("Measure", options=measure_options, index=2)
chart_type = c5.selectbox("Chart type", options=["Auto", "Bar", "Line", "Area"], index=0)
sort_desc = c6.toggle("Sort descending", value=True)

top_n = st.slider("Top N", min_value=3, max_value=150, value=30, step=1)
min_revenue_for_pct = st.number_input(
    "Min revenue for Gross Margin %",
    min_value=0.0,
    value=0.0,
    step=100.0,
    help="Applied only when measure is Gross Margin %.",
)

primary_dim = dim_map[primary_dim_label]
group_cols = [primary_dim]
if use_secondary and secondary_dim_label != primary_dim_label:
    group_cols.append(dim_map[secondary_dim_label])

agg_df = (
    filtered.groupby(group_cols, as_index=False)
    .agg(
        revenue=("revenue", "sum"),
        cogs=("cogs", "sum"),
        gross_margin_value=("gross_margin_value", "sum"),
        sold_qty=("sold_qty", "sum"),
    )
)
agg_df["gross_margin_pct"] = (agg_df["gross_margin_value"] / agg_df["revenue"]).where(agg_df["revenue"] > 0)
agg_df["pmp_unit_cost"] = (agg_df["cogs"] / agg_df["sold_qty"]).where(agg_df["sold_qty"] > 0)

measure_col = {
    "Revenue": "revenue",
    "COGS": "cogs",
    "Gross Margin Value": "gross_margin_value",
    "Gross Margin %": "gross_margin_pct",
    "Sold Qty": "sold_qty",
    "PMP Unit Cost": "pmp_unit_cost",
}[measure_label]

if measure_col == "gross_margin_pct":
    agg_df = agg_df[agg_df["revenue"] >= min_revenue_for_pct].copy()

agg_df = agg_df.sort_values(measure_col, ascending=not sort_desc).head(top_n)
if agg_df.empty:
    st.warning("No rows remain after current constraints.")
    st.stop()

if chart_type == "Auto":
    resolved_chart = "Line" if group_cols[0] == "year_month" else "Bar"
else:
    resolved_chart = chart_type

if len(group_cols) == 1:
    x_col = group_cols[0]
    if resolved_chart == "Line":
        agg_df = agg_df.sort_values(x_col)
        fig = px.line(agg_df, x=x_col, y=measure_col, markers=True, title="Margins dynamic view")
    elif resolved_chart == "Area":
        agg_df = agg_df.sort_values(x_col)
        fig = px.area(agg_df, x=x_col, y=measure_col, title="Margins dynamic view")
    else:
        fig = px.bar(agg_df, x=x_col, y=measure_col, title="Margins dynamic view")
else:
    x_col = group_cols[0]
    color_col = group_cols[1]
    if resolved_chart == "Line":
        agg_df = agg_df.sort_values(x_col)
        fig = px.line(agg_df, x=x_col, y=measure_col, color=color_col, markers=True, title="Margins dynamic view")
    elif resolved_chart == "Area":
        agg_df = agg_df.sort_values(x_col)
        fig = px.area(agg_df, x=x_col, y=measure_col, color=color_col, title="Margins dynamic view")
    else:
        fig = px.bar(agg_df, x=x_col, y=measure_col, color=color_col, title="Margins dynamic view")

fig.update_layout(xaxis_title=primary_dim_label, yaxis_title=measure_label)
st.plotly_chart(fig, use_container_width=True)

st.subheader("Result table")
st.dataframe(agg_df, use_container_width=True)

if len(group_cols) == 1 and group_cols[0] != "year_month":
    share_df = agg_df[[group_cols[0], measure_col]].copy()
    total = float(share_df[measure_col].sum())
    if total != 0:
        share_df["share_pct"] = (share_df[measure_col] / total) * 100
        st.subheader("Share analysis")
        st.dataframe(share_df.sort_values("share_pct", ascending=False), use_container_width=True)
