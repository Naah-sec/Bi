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
    apply_filters_purchases,
    load_semantic_purchases,
    refresh_warehouse,
    render_sidebar_filters_purchases,
)

st.title("Purchases Q1 - Liste des produits achetes en 2024")

if st.sidebar.button("Refresh data", key="refresh_purchases_q1"):
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

filters = render_sidebar_filters_purchases(df, key_prefix="purchases_q1")
filtered = apply_filters_purchases(df, filters)
filtered = filtered[filtered["year"] == 2024].copy()

if filtered.empty:
    st.warning("No products purchased in 2024 under the current filters.")
    st.stop()

top_n = st.slider("Top N products", min_value=3, max_value=100, value=15, step=1)

summary = (
    filtered.groupby(["product_name", "category"], as_index=False)[["amount_ttc", "qty"]]
    .sum()
    .sort_values("amount_ttc", ascending=False)
)
summary = summary.rename(columns={"amount_ttc": "TotalCost", "qty": "Qty"})

st.dataframe(summary, use_container_width=True)

fig = px.bar(
    summary.head(top_n),
    x="product_name",
    y="TotalCost",
    color="category",
    title=f"Top {top_n} products purchased in 2024 by total cost",
)
fig.update_layout(xaxis_title="Product", yaxis_title="Total Cost")
st.plotly_chart(fig, use_container_width=True)
