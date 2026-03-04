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
    DIMENSION_COLUMNS,
    MEASURE_COLUMNS,
    apply_filters,
    load_semantic_sales,
    render_sidebar_filters,
    refresh_warehouse,
)

st.title("Explore (Dynamic Analysis)")

if st.sidebar.button("Refresh data", key="refresh_explore"):
    with st.spinner("Refreshing warehouse..."):
        refresh_warehouse()
    st.sidebar.success("Warehouse refreshed")

df = load_semantic_sales()
filters = render_sidebar_filters(df, key_prefix="explore")
filtered = apply_filters(df, filters)

if filtered.empty:
    st.warning("No data for selected filters.")
    st.stop()

dimension_label = st.selectbox(
    "Dimension selector",
    options=["Product", "Category", "Customer", "Wilaya", "TypeVente", "LegalForm", "YearMonth"],
)
measure_label = st.selectbox(
    "Measure selector",
    options=["CA_TTC", "CA_HT", "Quantites", "Taxe"],
    index=0,
)
top_n = st.slider("Top N", min_value=3, max_value=100, value=20, step=1)

dimension_col = DIMENSION_COLUMNS[dimension_label]
measure_col = MEASURE_COLUMNS[measure_label]

agg_df = (
    filtered.groupby(dimension_col, as_index=False)[measure_col]
    .sum()
    .sort_values(measure_col, ascending=False)
)
agg_df = agg_df.head(top_n)

chart_type = "line" if dimension_label == "YearMonth" else "bar"
if chart_type == "line":
    agg_df = agg_df.sort_values(dimension_col)
    fig = px.line(agg_df, x=dimension_col, y=measure_col, markers=True, title="Dynamic analysis")
else:
    fig = px.bar(agg_df, x=dimension_col, y=measure_col, title="Dynamic analysis")

fig.update_layout(xaxis_title=dimension_label, yaxis_title=measure_label)
st.plotly_chart(fig, use_container_width=True)

st.subheader("Table")
st.dataframe(agg_df, use_container_width=True)
