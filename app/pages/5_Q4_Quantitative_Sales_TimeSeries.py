from __future__ import annotations

import sys
from pathlib import Path

import plotly.express as px
import streamlit as st

# Ensure `src` is importable when Streamlit runs page scripts.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.metrics import (
    MEASURE_COLUMNS,
    apply_filters,
    load_semantic_sales,
    render_sidebar_filters,
    refresh_warehouse,
)

st.title("Q4. Quantitative Sales by Product/Category/Type Over Time")

if st.sidebar.button("Refresh data", key="refresh_q4"):
    with st.spinner("Refreshing warehouse..."):
        refresh_warehouse()
    st.sidebar.success("Warehouse refreshed")

df = load_semantic_sales()
filters = render_sidebar_filters(df, key_prefix="q4")
filtered = apply_filters(df, filters)

if filtered.empty:
    st.warning("No data for selected filters.")
    st.stop()

measure_label = st.selectbox("Measure", options=["Quantites", "CA_TTC", "CA_HT", "Taxe"], index=0)
grouping_label = st.selectbox("Grouping", options=["Category", "Product", "TypeVente"], index=0)

measure_col = MEASURE_COLUMNS[measure_label]
group_col = {
    "Category": "category",
    "Product": "product_name",
    "TypeVente": "typevente_code",
}[grouping_label]

series_df = (
    filtered.groupby(["year_month", group_col], as_index=False)[measure_col]
    .sum()
    .sort_values("year_month")
)

fig = px.line(
    series_df,
    x="year_month",
    y=measure_col,
    color=group_col,
    markers=True,
    title=f"{measure_label} over time grouped by {grouping_label}",
)
fig.update_layout(xaxis_title="YearMonth", yaxis_title=measure_label)
st.plotly_chart(fig, use_container_width=True)

st.subheader("Aggregated table")
st.dataframe(series_df, use_container_width=True)
