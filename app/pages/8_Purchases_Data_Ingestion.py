from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = next(
    (p for p in [Path(__file__).resolve().parent, *Path(__file__).resolve().parents] if (p / "src").exists()),
    Path(__file__).resolve().parent,
)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import PURCHASES_CSV_PATH, PURCHASES_EXCEL_PATH
from src.metrics import refresh_warehouse

st.title("Purchases / Achats - Data Ingestion")
st.caption("Load purchases from Excel or CSV, validate, quarantine invalid rows, and rebuild warehouse.")

source_label = st.radio("Input source", options=["Excel", "CSV"], horizontal=True)
drop_invalid_rows = st.checkbox("Drop invalid purchases rows and continue", value=False)

if source_label == "Excel":
    source = "excel"
    default_path = str(PURCHASES_EXCEL_PATH)
    source_key = "purchases_excel_path"
else:
    source = "csv"
    default_path = str(PURCHASES_CSV_PATH)
    source_key = "purchases_csv_path"

input_path_str = st.text_input("Input file path", value=default_path)

if st.button("Load Purchases Data", type="primary"):
    build_kwargs: dict[str, object] = {
        "purchases_source": source,
        "drop_invalid_purchase_rows": drop_invalid_rows,
    }
    build_kwargs[source_key] = Path(input_path_str)

    try:
        with st.spinner("Running validation + rebuilding warehouse..."):
            counts = refresh_warehouse(**build_kwargs)
        st.success("Warehouse rebuilt successfully.")
        st.json(counts)
    except Exception as exc:
        st.error("Purchases ingestion/build failed.")
        st.exception(exc)

st.subheader("Validation outputs")
st.markdown(
    """
- `reports/purchases_qa_report.csv`
- `reports/purchases_qa_report.md`
- `reports/purchases_qa_details.csv`
- `reports/purchases_quarantine.csv` (created when invalid rows exist)
- `reports/purchases_profile.md`
"""
)
