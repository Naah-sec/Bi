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
    apply_filters_margins,
    export_fact_margin_monthly,
    export_inventory_ledger,
    load_inventory_ledger,
    load_margin_monthly,
    refresh_warehouse,
    render_sidebar_filters_margins,
)

st.title("Margins / Marges - Accounting KPIs")
st.caption("Gross Margin = Revenue - Cost of Goods Sold (COGS)")

if st.sidebar.button("Refresh data", key="refresh_margins_kpis"):
    with st.spinner("Rebuilding warehouse..."):
        refresh_warehouse()
    st.sidebar.success("Warehouse refreshed")

try:
    margin_df = load_margin_monthly()
    ledger_df = load_inventory_ledger()
except Exception as exc:
    st.error("Margin/ledger datasets are not available. Run warehouse build first.")
    st.exception(exc)
    st.stop()

if margin_df.empty:
    st.warning("No margin data available.")
    st.stop()

filters = render_sidebar_filters_margins(margin_df, key_prefix="margins_kpis")
filtered_margin = apply_filters_margins(margin_df, filters)
filtered_ledger = apply_filters_margins(ledger_df, filters)

if filtered_margin.empty:
    st.warning("No margin data for selected filters.")
    st.stop()

total_revenue = float(filtered_margin["revenue"].sum())
total_cogs = float(filtered_margin["cogs"].sum())
total_gm = float(filtered_margin["gross_margin_value"].sum())
gm_pct = (total_gm / total_revenue) if total_revenue else 0.0

sale_rows = filtered_ledger[filtered_ledger["event_type"].eq("SALE")].copy()
excluded_sales = sale_rows[~sale_rows["valid_for_margin"].fillna(False)].copy()
valid_sales = sale_rows[sale_rows["valid_for_margin"].fillna(False)].copy()
avg_pmp_used = float(valid_sales["ppm_unit_cost_before"].dropna().mean()) if not valid_sales.empty else 0.0

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Revenue", f"{total_revenue:,.2f}")
c2.metric("COGS", f"{total_cogs:,.2f}")
c3.metric("Gross Margin", f"{total_gm:,.2f}")
c4.metric("Gross Margin %", f"{gm_pct * 100:.2f}%")
c5.metric("Avg PMP used", f"{avg_pmp_used:,.2f}")

if not excluded_sales.empty:
    st.warning(
        f"{len(excluded_sales)} sale events are excluded from gross margin due to ledger errors (e.g. insufficient stock)."
    )

with st.expander("Visual controls", expanded=False):
    top_n = st.slider("Top N products", min_value=3, max_value=100, value=15, step=1)
    min_revenue_for_pct = st.number_input(
        "Min revenue threshold for % charts",
        min_value=0.0,
        value=0.0,
        step=100.0,
        help="Products below this revenue are excluded from margin % ranking.",
    )

main_tab, product_tab, pmp_tab, export_tab = st.tabs(["Executive", "Product Lens", "PMP Diagnostics", "Exports"])

with main_tab:
    trend_df = (
        filtered_margin.groupby("year_month", as_index=False)[["revenue", "cogs", "gross_margin_value"]]
        .sum()
        .sort_values("year_month")
    )
    fig_trend = px.line(
        trend_df,
        x="year_month",
        y=["revenue", "cogs", "gross_margin_value"],
        markers=True,
        title="Revenue vs COGS vs Gross Margin",
    )
    st.plotly_chart(fig_trend, use_container_width=True)

    left, right = st.columns(2)
    with left:
        by_category = (
            filtered_margin.groupby("category", as_index=False)[["revenue", "cogs", "gross_margin_value"]]
            .sum()
            .sort_values("gross_margin_value", ascending=False)
        )
        fig_cat = px.bar(
            by_category,
            x="category",
            y=["revenue", "cogs", "gross_margin_value"],
            barmode="group",
            title="Category mix: Revenue, COGS, Gross Margin",
        )
        st.plotly_chart(fig_cat, use_container_width=True)

    with right:
        by_wilaya = (
            filtered_margin.groupby("wilaya_name", as_index=False)[["revenue", "gross_margin_value"]]
            .sum()
            .sort_values("gross_margin_value", ascending=False)
        )
        fig_wilaya = px.bar(
            by_wilaya,
            x="wilaya_name",
            y=["revenue", "gross_margin_value"],
            barmode="group",
            title="Wilaya performance",
        )
        st.plotly_chart(fig_wilaya, use_container_width=True)

with product_tab:
    product_perf = (
        filtered_margin.groupby(["product_name", "category"], as_index=False)
        .agg(
            revenue=("revenue", "sum"),
            cogs=("cogs", "sum"),
            gross_margin_value=("gross_margin_value", "sum"),
            sold_qty=("sold_qty", "sum"),
        )
    )
    product_perf["gross_margin_pct"] = (product_perf["gross_margin_value"] / product_perf["revenue"]).where(
        product_perf["revenue"] > 0
    )
    product_perf["pmp_unit_cost"] = (product_perf["cogs"] / product_perf["sold_qty"]).where(product_perf["sold_qty"] > 0)

    left, right = st.columns(2)
    with left:
        fig_prod_margin = px.bar(
            product_perf.sort_values("gross_margin_value", ascending=False).head(top_n),
            x="product_name",
            y="gross_margin_value",
            color="category",
            title=f"Top {top_n} products by gross margin value",
        )
        st.plotly_chart(fig_prod_margin, use_container_width=True)

    with right:
        pct_base = product_perf[product_perf["revenue"] >= min_revenue_for_pct].copy()
        fig_prod_pct = px.bar(
            pct_base.sort_values("gross_margin_pct", ascending=False).head(top_n),
            x="product_name",
            y="gross_margin_pct",
            color="category",
            hover_data=["revenue", "sold_qty", "pmp_unit_cost"],
            title=f"Top {top_n} products by gross margin %",
        )
        st.plotly_chart(fig_prod_pct, use_container_width=True)

    scatter_df = pct_base if not pct_base.empty else product_perf
    fig_scatter = px.scatter(
        scatter_df,
        x="revenue",
        y="gross_margin_pct",
        size="sold_qty",
        hover_name="product_name",
        color="category",
        title="Product positioning: Revenue vs Gross Margin %",
    )
    st.plotly_chart(fig_scatter, use_container_width=True)

    st.subheader("Filtered Margin Data")
    st.dataframe(filtered_margin.sort_values(["year", "month_no", "product_name"]), use_container_width=True)

with pmp_tab:
    valid_sales = valid_sales.sort_values(["date", "event_sequence"])
    pmp_trend = (
        valid_sales.groupby("year_month", as_index=False)["ppm_unit_cost_before"]
        .mean()
        .rename(columns={"ppm_unit_cost_before": "avg_pmp_before_sale"})
        .sort_values("year_month")
    )
    if not pmp_trend.empty:
        fig_pmp = px.line(
            pmp_trend,
            x="year_month",
            y="avg_pmp_before_sale",
            markers=True,
            title="Average PMP used in sale COGS by month",
        )
        st.plotly_chart(fig_pmp, use_container_width=True)

    latest_state = (
        filtered_ledger.sort_values(["product_name", "date", "event_sequence"])
        .groupby("product_name", as_index=False)
        .tail(1)[["product_name", "category", "stock_qty_after", "stock_value_after", "ppm_unit_cost_after", "error_code"]]
        .sort_values("stock_value_after", ascending=False)
    )
    st.subheader("Latest inventory state by product")
    st.dataframe(latest_state, use_container_width=True)

    if not excluded_sales.empty:
        st.subheader("Excluded sale events")
        st.dataframe(
            excluded_sales[
                [
                    "date",
                    "product_name",
                    "wilaya_name",
                    "sale_qty",
                    "sale_revenue",
                    "ppm_unit_cost_before",
                    "error_code",
                ]
            ].sort_values(["date", "product_name"]),
            use_container_width=True,
        )

with export_tab:
    st.write("Export current filtered datasets")

    margin_csv = filtered_margin.to_csv(index=False).encode("utf-8")
    ledger_csv = filtered_ledger.to_csv(index=False).encode("utf-8")

    c1, c2 = st.columns(2)
    if c1.button("Export fact_margin_monthly"):
        out_path = export_fact_margin_monthly(filtered_margin)
        st.success(f"Exported: {out_path}")
    c1.download_button(
        "Download filtered margin CSV",
        data=margin_csv,
        file_name="export_fact_margin_monthly.csv",
        mime="text/csv",
    )

    if c2.button("Export inventory_ledger"):
        out_path = export_inventory_ledger(filtered_ledger)
        st.success(f"Exported: {out_path}")
    c2.download_button(
        "Download filtered ledger CSV",
        data=ledger_csv,
        file_name="inventory_ledger_export.csv",
        mime="text/csv",
    )

    st.caption(f"Rows in current scope: margin={len(filtered_margin):,}, ledger={len(filtered_ledger):,}")
