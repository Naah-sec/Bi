from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.metrics import (
    apply_filters_inventory_ledger,
    export_inventory_ledger,
    load_inventory_ledger,
    refresh_warehouse,
)

st.title("Inventory Debug / Ledger")
st.caption("Manual inspection of stock movements, PMP evolution, and accounting gross margin line by line")

if st.sidebar.button("Refresh data", key="refresh_inventory_debug"):
    with st.spinner("Rebuilding warehouse..."):
        refresh_warehouse()
    st.sidebar.success("Warehouse refreshed")

try:
    df = load_inventory_ledger()
except Exception as exc:
    st.error("Inventory ledger is not available. Run warehouse build first.")
    st.exception(exc)
    st.stop()

if df.empty:
    st.warning("No inventory ledger data available.")
    st.stop()

products = sorted(df["product_name"].dropna().unique().tolist())
selected_product = st.selectbox("Product", options=["All"] + products, index=0)
event_type_filter = st.multiselect("Event type", options=["PURCHASE", "SALE"], default=["PURCHASE", "SALE"])
show_only_errors = st.toggle("Show only rows with error_code", value=False)

date_min = min([d for d in df["date"].dropna().tolist()])
date_max = max([d for d in df["date"].dropna().tolist()])
date_range = st.date_input("Date range", value=(date_min, date_max))

filtered = apply_filters_inventory_ledger(df, product=selected_product, date_range=date_range if isinstance(date_range, tuple) else None)
filtered = filtered[filtered["event_type"].isin(event_type_filter)].copy()
if show_only_errors:
    filtered = filtered[filtered["error_code"].notna()].copy()

if filtered.empty:
    st.warning("No ledger rows for selected filters.")
    st.stop()

if st.button("Export inventory_ledger_export.csv"):
    out_path = export_inventory_ledger(filtered)
    st.success(f"Exported: {out_path}")

error_rows = int(filtered["error_code"].notna().sum())
if error_rows > 0:
    st.warning(f"{error_rows} rows contain validation error_code values.")

ordered = filtered.sort_values(["product_id", "date", "event_sequence"]).copy()
opening_stock = float(ordered.iloc[0]["stock_qty_before"])
closing_stock = float(ordered.iloc[-1]["stock_qty_after"])
total_purchase_qty = float(ordered["purchase_qty"].fillna(0.0).sum())
total_sale_qty = float(ordered["sale_qty"].fillna(0.0).sum())
ending_pmp_raw = ordered.iloc[-1]["ppm_unit_cost_after"]
ending_pmp = float(ending_pmp_raw) if pd.notna(ending_pmp_raw) else 0.0
sale_scope = ordered[ordered["event_type"].eq("SALE")]
scope_revenue = float(sale_scope["sale_revenue"].fillna(0.0).sum())
scope_cogs = float(sale_scope["cost_of_goods_sold"].fillna(0.0).sum())
scope_margin = float(sale_scope["gross_margin_value"].fillna(0.0).sum())
scope_margin_pct = (scope_margin / scope_revenue) if scope_revenue > 0 else 0.0

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Opening stock", f"{opening_stock:,.2f}")
k2.metric("Closing stock", f"{closing_stock:,.2f}")
k3.metric("Purchased qty", f"{total_purchase_qty:,.2f}")
k4.metric("Sold qty", f"{total_sale_qty:,.2f}")
k5.metric("Ending PMP", f"{ending_pmp:,.2f}")

k6, k7, k8 = st.columns(3)
k6.metric("Revenue", f"{scope_revenue:,.2f}")
k7.metric("COGS", f"{scope_cogs:,.2f}")
k8.metric("Gross Margin %", f"{scope_margin_pct * 100:.2f}%")

st.subheader("Ledger table")
st.dataframe(
    ordered,
    use_container_width=True,
)

chart_df = ordered.sort_values(["date", "event_sequence"])

c1, c2, c3 = st.columns(3)
with c1:
    fig_qty = px.line(
        chart_df,
        x="date",
        y="stock_qty_after",
        color="event_type",
        markers=True,
        title="Stock quantity over time",
    )
    st.plotly_chart(fig_qty, use_container_width=True)

with c2:
    fig_value = px.line(
        chart_df,
        x="date",
        y="stock_value_after",
        color="event_type",
        markers=True,
        title="Stock value over time",
    )
    st.plotly_chart(fig_value, use_container_width=True)

with c3:
    fig_ppm = px.line(
        chart_df,
        x="date",
        y="ppm_unit_cost_after",
        color="event_type",
        markers=True,
        title="PMP unit cost over time",
    )
    st.plotly_chart(fig_ppm, use_container_width=True)

sale_rows = chart_df[chart_df["event_type"] == "SALE"].copy()
if not sale_rows.empty:
    sale_long = sale_rows[["date", "sale_revenue", "cost_of_goods_sold", "gross_margin_value"]].rename(
        columns={
            "sale_revenue": "Revenue",
            "cost_of_goods_sold": "COGS",
            "gross_margin_value": "Gross Margin",
        }
    )
    sale_long = sale_long.melt(id_vars=["date"], var_name="Metric", value_name="Value")

    fig_fin = px.bar(
        sale_long,
        x="date",
        y="Value",
        color="Metric",
        barmode="group",
        title="Revenue vs COGS vs Gross Margin",
    )
    st.plotly_chart(fig_fin, use_container_width=True)

if error_rows > 0:
    st.subheader("Error summary")
    error_summary = (
        chart_df[chart_df["error_code"].notna()]
        .groupby("error_code", as_index=False)
        .size()
        .rename(columns={"size": "rows"})
        .sort_values("rows", ascending=False)
    )
    st.dataframe(error_summary, use_container_width=True)
