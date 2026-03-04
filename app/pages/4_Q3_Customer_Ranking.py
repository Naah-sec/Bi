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

from src.metrics import (
    MEASURE_COLUMNS,
    apply_filters,
    load_semantic_sales,
    render_sidebar_filters,
    refresh_warehouse,
)

st.title("Q3. Customer Ranking by Purchases (Wilaya + Legal Form)")

if st.sidebar.button("Refresh data", key="refresh_q3"):
    with st.spinner("Refreshing warehouse..."):
        refresh_warehouse()
    st.sidebar.success("Warehouse refreshed")

df = load_semantic_sales()
filters = render_sidebar_filters(df, key_prefix="q3")
filtered = apply_filters(df, filters)

if filtered.empty:
    st.warning("No data for selected filters.")
    st.stop()

measure_label = st.selectbox("Measure", options=["CA_TTC", "CA_HT", "Quantites", "Taxe"], index=0)
top_n = st.slider("Top N customers", min_value=3, max_value=50, value=10, step=1)
breakdown = st.selectbox("Breakdown", options=["None", "Wilaya", "LegalForm", "Wilaya + LegalForm"], index=3)

measure_col = MEASURE_COLUMNS[measure_label]

rank_df = (
    filtered.groupby("customer_name", as_index=False)[measure_col]
    .sum()
    .sort_values(measure_col, ascending=False)
    .reset_index(drop=True)
)
rank_df["rank"] = rank_df.index + 1
top_customers = rank_df.head(top_n)["customer_name"].tolist()

plot_df = filtered[filtered["customer_name"].isin(top_customers)].copy()

if breakdown == "Wilaya":
    grouped = plot_df.groupby(["customer_name", "wilaya_name"], as_index=False)[measure_col].sum()
    fig = px.bar(grouped, x="customer_name", y=measure_col, color="wilaya_name", title="Top customers by wilaya")
elif breakdown == "LegalForm":
    grouped = plot_df.groupby(["customer_name", "legal_form"], as_index=False)[measure_col].sum()
    fig = px.bar(grouped, x="customer_name", y=measure_col, color="legal_form", title="Top customers by legal form")
elif breakdown == "Wilaya + LegalForm":
    grouped = plot_df.groupby(["customer_name", "wilaya_name", "legal_form"], as_index=False)[measure_col].sum()
    fig = px.bar(
        grouped,
        x="customer_name",
        y=measure_col,
        color="wilaya_name",
        facet_col="legal_form",
        title="Top customers by wilaya and legal form",
    )
else:
    grouped = plot_df.groupby(["customer_name"], as_index=False)[measure_col].sum()
    fig = px.bar(grouped, x="customer_name", y=measure_col, title="Top customers")

fig.update_layout(xaxis_title="Customer", yaxis_title=measure_label)
st.plotly_chart(fig, use_container_width=True)

st.subheader("Ranking table")
st.dataframe(rank_df.head(top_n), use_container_width=True)
