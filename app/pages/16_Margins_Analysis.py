from __future__ import annotations

import sys
from pathlib import Path

import plotly.express as px
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.metrics import apply_filters_margins, load_margin_monthly, refresh_warehouse, render_sidebar_filters_margins

st.title("Margins Analysis")
st.caption("Analyze gross margin by product, category, wilaya, month, and year")

if st.sidebar.button("Refresh data", key="refresh_margins_analysis"):
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

filters = render_sidebar_filters_margins(df, key_prefix="margins_analysis")
filtered = apply_filters_margins(df, filters)

if filtered.empty:
    st.warning("No margin data for selected filters.")
    st.stop()

metric_label = st.selectbox(
    "Time-series metric",
    options=["Gross Margin Value", "Gross Margin %", "Revenue", "COGS", "Sold Qty"],
    index=0,
)
chart_style = st.selectbox("Chart style", options=["Line", "Area", "Bar"], index=0)
breakdown = st.selectbox("Time-series breakdown", options=["None", "Category", "Wilaya", "Product"], index=0)
top_n = st.slider("Top N products", min_value=3, max_value=100, value=20, step=1)
min_revenue_for_pct = st.number_input(
    "Min revenue for % rankings",
    min_value=0.0,
    value=0.0,
    step=100.0,
    help="Avoids ranking products with unstable % on very small revenue.",
)

metric_col = {
    "Gross Margin Value": "gross_margin_value",
    "Gross Margin %": "gross_margin_pct",
    "Revenue": "revenue",
    "COGS": "cogs",
    "Sold Qty": "sold_qty",
}[metric_label]

group_key = None
if breakdown == "Category":
    group_key = "category"
elif breakdown == "Wilaya":
    group_key = "wilaya_name"
elif breakdown == "Product":
    group_key = "product_name"

group_cols = ["year_month"] + ([group_key] if group_key else [])
time_df = filtered.groupby(group_cols, as_index=False)[["revenue", "cogs", "gross_margin_value", "sold_qty"]].sum()
time_df["gross_margin_pct"] = (time_df["gross_margin_value"] / time_df["revenue"]).where(time_df["revenue"] > 0)
time_df = time_df.sort_values("year_month")

if chart_style == "Bar":
    fig_time = px.bar(
        time_df,
        x="year_month",
        y=metric_col,
        color=group_key if group_key else None,
        barmode="group",
        title=f"{metric_label} over time",
    )
elif chart_style == "Area":
    fig_time = px.area(
        time_df,
        x="year_month",
        y=metric_col,
        color=group_key if group_key else None,
        title=f"{metric_label} over time",
    )
else:
    fig_time = px.line(
        time_df,
        x="year_month",
        y=metric_col,
        color=group_key if group_key else None,
        markers=True,
        title=f"{metric_label} over time",
    )

fig_time.update_layout(xaxis_title="YearMonth", yaxis_title=metric_label)
st.plotly_chart(fig_time, use_container_width=True)

product_totals = (
    filtered.groupby("product_name", as_index=False)
    .agg(revenue=("revenue", "sum"), cogs=("cogs", "sum"), gross_margin_value=("gross_margin_value", "sum"))
)
product_totals["gross_margin_pct"] = (product_totals["gross_margin_value"] / product_totals["revenue"]).where(
    product_totals["revenue"] > 0
)
pct_base = product_totals[product_totals["revenue"] >= min_revenue_for_pct].copy()

left, right = st.columns(2)
with left:
    fig_margin = px.bar(
        product_totals.sort_values("gross_margin_value", ascending=False).head(top_n),
        x="product_name",
        y="gross_margin_value",
        title=f"Top {top_n} products by gross margin value",
    )
    st.plotly_chart(fig_margin, use_container_width=True)

with right:
    fig_pct = px.bar(
        pct_base.sort_values("gross_margin_pct", ascending=False).head(top_n),
        x="product_name",
        y="gross_margin_pct",
        hover_data=["revenue"],
        title=f"Top {top_n} products by gross margin % (check revenue context)",
    )
    st.plotly_chart(fig_pct, use_container_width=True)

heatmap_base = (
    filtered.groupby(["category", "wilaya_name"], as_index=False)["gross_margin_value"]
    .sum()
    .pivot(index="category", columns="wilaya_name", values="gross_margin_value")
    .fillna(0.0)
)
if not heatmap_base.empty:
    fig_heatmap = px.imshow(
        heatmap_base,
        aspect="auto",
        color_continuous_scale="RdYlGn",
        title="Gross margin heatmap: Category x Wilaya",
    )
    st.plotly_chart(fig_heatmap, use_container_width=True)

matrix_measure = st.selectbox(
    "Matrix measure",
    options=["Gross Margin Value", "Gross Margin %", "Revenue", "COGS", "Sold Qty"],
    index=0,
)
matrix_col = {
    "Gross Margin Value": "gross_margin_value",
    "Gross Margin %": "gross_margin_pct",
    "Revenue": "revenue",
    "COGS": "cogs",
    "Sold Qty": "sold_qty",
}[matrix_measure]
matrix_agg = "mean" if matrix_col == "gross_margin_pct" else "sum"
matrix_df = filtered.pivot_table(index="product_name", columns="year_month", values=matrix_col, aggfunc=matrix_agg)
matrix_df = matrix_df.sort_index()

st.subheader(f"Matrix - {matrix_measure}")
st.dataframe(matrix_df, use_container_width=True)

st.subheader("Drilldown table")
drill_cols = [
    "year_month",
    "product_name",
    "category",
    "wilaya_name",
    "sold_qty",
    "revenue",
    "cogs",
    "gross_margin_value",
    "gross_margin_pct",
]
st.dataframe(filtered[drill_cols].sort_values(["year_month", "product_name"]), use_container_width=True)
