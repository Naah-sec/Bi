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

st.title("Q2. Product Ranking by Revenue, Type Vente, and Year")

if st.sidebar.button("Refresh data", key="refresh_q2"):
    with st.spinner("Refreshing warehouse..."):
        refresh_warehouse()
    st.sidebar.success("Warehouse refreshed")

df = load_semantic_sales()
filters = render_sidebar_filters(df, key_prefix="q2")
filtered = apply_filters(df, filters)

if filtered.empty:
    st.warning("No data for selected filters.")
    st.stop()

years = sorted(filtered["year"].dropna().astype(int).unique().tolist())
selected_year = st.selectbox("Select year", options=years, index=len(years) - 1 if years else 0)
measure_label = st.selectbox("Measure", options=["CA_TTC", "CA_HT", "Quantites", "Taxe"], index=0)
top_n = st.slider("Top N products", min_value=3, max_value=50, value=10, step=1)

measure_col = MEASURE_COLUMNS[measure_label]
year_df = filtered[filtered["year"] == selected_year].copy()

if year_df.empty:
    st.warning(f"No data for year {selected_year}.")
    st.stop()

ranking = (
    year_df.groupby("product_name", as_index=False)[measure_col]
    .sum()
    .sort_values(measure_col, ascending=False)
    .reset_index(drop=True)
)
ranking["rank"] = ranking.index + 1
top_products = ranking.head(top_n)["product_name"].tolist()

bar_df = (
    year_df[year_df["product_name"].isin(top_products)]
    .groupby(["product_name", "typevente_code"], as_index=False)[measure_col]
    .sum()
)

fig = px.bar(
    bar_df,
    x="product_name",
    y=measure_col,
    color="typevente_code",
    title=f"Top {top_n} products by {measure_label} in {selected_year}",
)
fig.update_layout(xaxis_title="Product", yaxis_title=measure_label)
st.plotly_chart(fig, use_container_width=True)

st.subheader("Ranking table")
st.dataframe(ranking.head(top_n), use_container_width=True)
