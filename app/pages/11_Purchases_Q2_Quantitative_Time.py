from __future__ import annotations

import sys
from pathlib import Path

import plotly.express as px
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.metrics import (
    apply_filters_purchases,
    load_semantic_purchases,
    refresh_warehouse,
    render_sidebar_filters_purchases,
)

st.title("Purchases Q2 - Achats quantitatifs par produit/type achat/mois/annee")

if st.sidebar.button("Refresh data", key="refresh_purchases_q2"):
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

filters = render_sidebar_filters_purchases(df, key_prefix="purchases_q2")
filtered = apply_filters_purchases(df, filters)

if filtered.empty:
    st.warning("No purchases data for selected filters.")
    st.stop()

grouping_label = st.selectbox("Grouping for quantity trend", options=["Product", "TypeAchat", "Category"], index=0)
group_col = {
    "Product": "product_name",
    "TypeAchat": "typeachat_code",
    "Category": "category",
}[grouping_label]

series_df = (
    filtered.groupby(["year_month", group_col], as_index=False)["qty"]
    .sum()
    .sort_values("year_month")
)

fig_line = px.line(
    series_df,
    x="year_month",
    y="qty",
    color=group_col,
    markers=True,
    title=f"Quantities over time grouped by {grouping_label}",
)
fig_line.update_layout(xaxis_title="YearMonth", yaxis_title="Qty")
st.plotly_chart(fig_line, use_container_width=True)

stacked_df = (
    filtered.groupby(["year_month", "typeachat_code"], as_index=False)["qty"]
    .sum()
    .sort_values("year_month")
)
fig_stacked = px.bar(
    stacked_df,
    x="year_month",
    y="qty",
    color="typeachat_code",
    title="Stacked quantities by TypeAchat per month",
)
fig_stacked.update_layout(xaxis_title="YearMonth", yaxis_title="Qty")
st.plotly_chart(fig_stacked, use_container_width=True)

st.subheader("Aggregated Table")
st.dataframe(series_df, use_container_width=True)
