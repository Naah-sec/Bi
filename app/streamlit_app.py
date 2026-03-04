from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

# Ensure `src` is importable when Streamlit runs from the app directory.
#PROJECT_ROOT = next(
#    (p for p in [Path(__file__).resolve().parent, *Path(__file__).resolve().parents] if (p / "src").exists()),
 #   Path(__file__).resolve().parent,
#)
PROJECT_ROOT =Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.metrics import load_semantic_sales, refresh_warehouse

st.set_page_config(page_title="Sales BI Platform", layout="wide")

st.title("Sales BI Dashboard Platform")
st.caption("Excel -> Transform -> DuckDB Star Schema -> Interactive Analytics")

if st.sidebar.button("Refresh data", key="refresh_main"):
    with st.spinner("Rebuilding warehouse from Excel..."):
        refresh_warehouse()
    st.sidebar.success("Warehouse refreshed")

try:
    df = load_semantic_sales()
except Exception as exc:
    st.error("Warehouse not available. Run `python -m src.warehouse --build` first.")
    st.exception(exc)
    st.stop()

st.subheader("Available pages")
st.markdown(
    """
1. **Sales / Home-KPIs**  
2. **Sales / Q1-Q5 + Explore**  
3. **Purchases / Data Ingestion** (Excel or CSV with validation + quarantine)  
4. **Purchases / KPIs, Q1-Q4, Explore**  
5. **Margins / KPIs, Analysis, Explore** (Revenue, COGS, Gross Margin)  
6. **Inventory Debug / Ledger** (chronological stock + PMP audit)  
"""
)

st.write(f"Loaded rows from warehouse semantic view: **{len(df):,}**")
st.info("Use the left sidebar page selector to navigate.")
