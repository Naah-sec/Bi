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

from src.metrics import (
    PURCHASE_DIMENSION_COLUMNS,
    PURCHASE_MEASURE_COLUMNS,
    apply_filters_purchases,
    load_semantic_purchases,
    refresh_warehouse,
    render_sidebar_filters_purchases,
)

st.title("Purchases Explore - Dynamic Analysis")

if st.sidebar.button("Refresh data", key="refresh_purchases_explore"):
    with st.spinner("Rebuilding warehouse..."):
        refresh_warehouse()
    st.sidebar.success("Warehouse refreshed")

try:
    df = load_semantic_purchases()
except Exception as exc:
    st.error("Purchases warehouse tables are not available. Run a warehouse build first.")
    st.exception(exc)
    st.stop()

if df.empty:
    st.warning("No purchases data available.")
    st.stop()

filters = render_sidebar_filters_purchases(df, key_prefix="purchases_explore")
filtered = apply_filters_purchases(df, filters)

if filtered.empty:
    st.warning("No purchases data for selected filters.")
    st.stop()

dimension_label = st.selectbox(
    "Dimension",
    options=["Product", "Category", "Supplier", "SupplierLegalForm", "TypeAchat", "YearMonth", "Year", "Month"],
)
measure_label = st.selectbox("Measure", options=["Cost_TTC", "Cost_HT", "Qty", "Tax"], index=0)
top_n = st.slider("Top N", min_value=3, max_value=100, value=25, step=1)

dimension_col = PURCHASE_DIMENSION_COLUMNS[dimension_label]
measure_col = PURCHASE_MEASURE_COLUMNS[measure_label]

agg_df = (
    filtered.groupby(dimension_col, as_index=False)[measure_col]
    .sum()
    .sort_values(measure_col, ascending=False)
    .head(top_n)
)

if dimension_label == "YearMonth":
    agg_df = agg_df.sort_values(dimension_col)
    fig = px.line(agg_df, x=dimension_col, y=measure_col, markers=True, title="Dynamic purchases analysis")
else:
    fig = px.bar(agg_df, x=dimension_col, y=measure_col, title="Dynamic purchases analysis")

fig.update_layout(xaxis_title=dimension_label, yaxis_title=measure_label)
st.plotly_chart(fig, use_container_width=True)

st.subheader("Table")
st.dataframe(agg_df, use_container_width=True)
