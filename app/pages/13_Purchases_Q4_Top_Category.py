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

st.title("Purchases Q4 - Categorie de produit la plus couteuse")

if st.sidebar.button("Refresh data", key="refresh_purchases_q4"):
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

filters = render_sidebar_filters_purchases(df, key_prefix="purchases_q4")
filtered = apply_filters_purchases(df, filters)

if filtered.empty:
    st.warning("No purchases data for selected filters.")
    st.stop()

cat_df = (
    filtered.groupby("category", as_index=False)["amount_ttc"]
    .sum()
    .sort_values("amount_ttc", ascending=False)
)

top = cat_df.iloc[0]
total = float(cat_df["amount_ttc"].sum())
share = (float(top["amount_ttc"]) / total * 100.0) if total else 0.0

c1, c2 = st.columns(2)
c1.metric("Top Category", str(top["category"]))
c2.metric("Top Category Share", f"{share:.2f}%")

fig = px.bar(cat_df, x="category", y="amount_ttc", title="Total purchase cost by category")
fig.update_layout(xaxis_title="Category", yaxis_title="Total Cost TTC")
st.plotly_chart(fig, use_container_width=True)

st.dataframe(cat_df, use_container_width=True)
