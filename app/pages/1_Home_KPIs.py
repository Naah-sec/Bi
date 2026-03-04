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

st.title("Home / KPIs")

if st.sidebar.button("Refresh data", key="refresh_home"):
    with st.spinner("Refreshing warehouse..."):
        refresh_warehouse()
    st.sidebar.success("Warehouse refreshed")

df = load_semantic_sales()
filters = render_sidebar_filters(df, key_prefix="home")
filtered = apply_filters(df, filters)

if filtered.empty:
    st.warning("No data for the current filters.")
    st.stop()

total_ttc = filtered["amount_ttc"].sum()
total_ht = filtered["amount_ht"].sum()
total_qty = filtered["qty"].sum()
total_tax = filtered["tax_amount"].sum()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total CA_TTC", f"{total_ttc:,.2f}")
c2.metric("Total CA_HT", f"{total_ht:,.2f}")
c3.metric("Total Quantites", f"{total_qty:,.0f}")
c4.metric("Total Taxe", f"{total_tax:,.2f}")

chart_df = (
    filtered.groupby("year_month", as_index=False)[["amount_ttc", "amount_ht"]]
    .sum()
    .sort_values("year_month")
)

fig = px.line(
    chart_df,
    x="year_month",
    y=["amount_ttc", "amount_ht"],
    markers=True,
    title="Revenue trend (CA_TTC vs CA_HT)",
)
st.plotly_chart(fig, use_container_width=True)

st.subheader("Filtered data preview")
st.dataframe(
    filtered[
        [
            "order_date",
            "typevente_code",
            "category",
            "product_name",
            "customer_name",
            "wilaya_name",
            "qty",
            "amount_ht",
            "tax_amount",
            "amount_ttc",
        ]
    ].sort_values("order_date", ascending=False),
    use_container_width=True,
)
