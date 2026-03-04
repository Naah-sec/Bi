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

st.title("Purchases Q3 - Fournisseur avec le plus d'achat par categorie")

if st.sidebar.button("Refresh data", key="refresh_purchases_q3"):
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

filters = render_sidebar_filters_purchases(df, key_prefix="purchases_q3")
filtered = apply_filters_purchases(df, filters)

if filtered.empty:
    st.warning("No purchases data for selected filters.")
    st.stop()

categories = sorted(filtered["category"].dropna().unique().tolist())
selected_category = st.selectbox("Category", options=["All"] + categories, index=0)
top_n = st.slider("Top N suppliers", min_value=3, max_value=50, value=10, step=1)
facet_by_category = st.checkbox("Facet by category", value=False)

plot_df = filtered.copy()
if selected_category != "All":
    plot_df = plot_df[plot_df["category"] == selected_category]

if plot_df.empty:
    st.warning("No data after category filter.")
    st.stop()

rank_df = (
    plot_df.groupby(["supplier_name", "category"], as_index=False)["amount_ttc"]
    .sum()
    .sort_values("amount_ttc", ascending=False)
)

if selected_category == "All":
    supplier_totals = rank_df.groupby("supplier_name", as_index=False)["amount_ttc"].sum().sort_values("amount_ttc", ascending=False)
else:
    supplier_totals = rank_df[["supplier_name", "amount_ttc"]].copy().sort_values("amount_ttc", ascending=False)

supplier_totals = supplier_totals.reset_index(drop=True)
supplier_totals["rank"] = supplier_totals.index + 1

top_suppliers = supplier_totals.head(top_n)["supplier_name"].tolist()
chart_df = rank_df[rank_df["supplier_name"].isin(top_suppliers)].copy()

if facet_by_category and selected_category == "All":
    fig = px.bar(
        chart_df,
        x="supplier_name",
        y="amount_ttc",
        color="supplier_name",
        facet_col="category",
        title=f"Top {top_n} suppliers by total cost (faceted by category)",
    )
else:
    fig = px.bar(
        chart_df.groupby("supplier_name", as_index=False)["amount_ttc"].sum().sort_values("amount_ttc", ascending=False),
        x="supplier_name",
        y="amount_ttc",
        title=f"Top {top_n} suppliers by total cost",
    )

fig.update_layout(xaxis_title="Supplier", yaxis_title="Total Cost")
st.plotly_chart(fig, use_container_width=True)

st.subheader("Supplier Ranking")
st.dataframe(supplier_totals.head(top_n), use_container_width=True)
