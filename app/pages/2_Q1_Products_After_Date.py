from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

# Ensure `src` is importable when Streamlit runs page scripts.
PROJECT_ROOT = next(
    (p for p in [Path(__file__).resolve().parent, *Path(__file__).resolve().parents] if (p / "src").exists()),
    Path(__file__).resolve().parent,
)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.metrics import apply_filters, load_semantic_sales, render_sidebar_filters, refresh_warehouse

st.title("Q1. Products Sold After 2025-02-01")

if st.sidebar.button("Refresh data", key="refresh_q1"):
    with st.spinner("Refreshing warehouse..."):
        refresh_warehouse()
    st.sidebar.success("Warehouse refreshed")

df = load_semantic_sales()
filters = render_sidebar_filters(df, key_prefix="q1")
filtered = apply_filters(df, filters)

fixed_date = pd.Timestamp("2025-02-01")
filtered["order_date"] = pd.to_datetime(filtered["order_date"], errors="coerce")
filtered = filtered[filtered["order_date"] >= fixed_date]

if filtered.empty:
    st.warning("No products sold after 2025-02-01 under current filters.")
    st.stop()

top_n = st.slider("Top N products", min_value=3, max_value=50, value=10, step=1)

summary = (
    filtered.groupby(["product_name", "category"], as_index=False)[["amount_ttc", "qty"]]
    .sum()
    .sort_values("amount_ttc", ascending=False)
)
summary = summary.rename(columns={"amount_ttc": "CA_TTC", "qty": "Quantites"})

st.subheader("Products sold after 2025-02-01")
st.dataframe(summary, use_container_width=True)

top_products = summary.head(top_n)
fig = px.bar(
    top_products,
    x="product_name",
    y="CA_TTC",
    color="category",
    title=f"Top {top_n} products by CA_TTC (>= 2025-02-01)",
)
fig.update_layout(xaxis_title="Product", yaxis_title="CA_TTC")
st.plotly_chart(fig, use_container_width=True)
