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

st.title("Purchases / Achats - KPIs")

if st.sidebar.button("Refresh data", key="refresh_purchases_kpis"):
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

filters = render_sidebar_filters_purchases(df, key_prefix="purchases_kpis")
filtered = apply_filters_purchases(df, filters)

if filtered.empty:
    st.warning("No purchases data for the selected filters.")
    st.stop()

total_cost_ttc = filtered["amount_ttc"].sum()
total_cost_ht = filtered["amount_ht"].sum()
total_qty = filtered["qty"].sum()
total_tax = filtered["tax_amount"].sum()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Cost TTC", f"{total_cost_ttc:,.2f}")
c2.metric("Total Cost HT", f"{total_cost_ht:,.2f}")
c3.metric("Total Qty", f"{total_qty:,.0f}")
c4.metric("Total Tax", f"{total_tax:,.2f}")

trend_df = (
    filtered.groupby("year_month", as_index=False)[["amount_ttc", "amount_ht", "qty"]]
    .sum()
    .sort_values("year_month")
)

fig = px.line(
    trend_df,
    x="year_month",
    y=["amount_ttc", "amount_ht"],
    markers=True,
    title="Purchases Cost Trend",
)
st.plotly_chart(fig, use_container_width=True)

st.subheader("Filtered Purchases")
st.dataframe(
    filtered[
        [
            "order_date",
            "typeachat_code",
            "category",
            "product_name",
            "supplier_name",
            "supplier_legal_form",
            "qty",
            "amount_ht",
            "tax_amount",
            "amount_ttc",
        ]
    ].sort_values("order_date", ascending=False),
    use_container_width=True,
)
