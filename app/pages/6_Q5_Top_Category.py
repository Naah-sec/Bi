from __future__ import annotations

import sys
from pathlib import Path

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

st.title("Q5. Category Generating the Most Revenue")

if st.sidebar.button("Refresh data", key="refresh_q5"):
    with st.spinner("Refreshing warehouse..."):
        refresh_warehouse()
    st.sidebar.success("Warehouse refreshed")

df = load_semantic_sales()
filters = render_sidebar_filters(df, key_prefix="q5")
filtered = apply_filters(df, filters)

if filtered.empty:
    st.warning("No data for selected filters.")
    st.stop()

cat_df = (
    filtered.groupby("category", as_index=False)["amount_ttc"]
    .sum()
    .sort_values("amount_ttc", ascending=False)
)

top = cat_df.iloc[0]
total = cat_df["amount_ttc"].sum()
share = (float(top["amount_ttc"]) / float(total) * 100.0) if total else 0.0

c1, c2 = st.columns(2)
c1.metric("Top Category", str(top["category"]))
c2.metric("Top Category Share", f"{share:.2f}%")

fig = px.bar(cat_df, x="category", y="amount_ttc", title="CA_TTC by Category (descending)")
fig.update_layout(xaxis_title="Category", yaxis_title="CA_TTC")
st.plotly_chart(fig, use_container_width=True)

st.dataframe(cat_df, use_container_width=True)
