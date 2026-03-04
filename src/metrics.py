from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st

from src.config import DUCKDB_PATH, REPORTS_DIR
from src.warehouse import build_warehouse

MEASURE_COLUMNS = {
    "CA_TTC": "amount_ttc",
    "CA_HT": "amount_ht",
    "Quantites": "qty",
    "Taxe": "tax_amount",
}

DIMENSION_COLUMNS = {
    "Product": "product_name",
    "Category": "category",
    "Customer": "customer_name",
    "Wilaya": "wilaya_name",
    "TypeVente": "typevente_code",
    "LegalForm": "legal_form",
    "YearMonth": "year_month",
}

PURCHASE_MEASURE_COLUMNS = {
    "Cost_TTC": "amount_ttc",
    "Cost_HT": "amount_ht",
    "Qty": "qty",
    "Tax": "tax_amount",
}

PURCHASE_DIMENSION_COLUMNS = {
    "Product": "product_name",
    "Category": "category",
    "Supplier": "supplier_name",
    "SupplierLegalForm": "supplier_legal_form",
    "TypeAchat": "typeachat_code",
    "YearMonth": "year_month",
    "Year": "year",
    "Month": "month_name",
}


def get_connection(db_path: Path = DUCKDB_PATH, read_only: bool = True) -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(db_path), read_only=read_only)


def ensure_warehouse_ready(db_path: Path = DUCKDB_PATH) -> None:
    required_tables = {"fact_salesline", "fact_purchaseline", "fact_inventory_events", "fact_margin_monthly", "dim_date", "dim_product"}

    if not db_path.exists():
        build_warehouse(duckdb_path=db_path, drop_invalid_purchase_rows=True)
        return

    try:
        conn = duckdb.connect(str(db_path), read_only=True)
        try:
            tables_df = conn.execute("SHOW TABLES").fetchdf()
        finally:
            conn.close()
    except Exception:
        build_warehouse(duckdb_path=db_path, drop_invalid_purchase_rows=True)
        return

    tables = set(tables_df["name"].astype(str).str.lower().tolist()) if not tables_df.empty else set()
    if not required_tables.issubset(tables):
        build_warehouse(duckdb_path=db_path, drop_invalid_purchase_rows=True)


@st.cache_data(show_spinner=False)
def load_semantic_sales(db_path_str: str = str(DUCKDB_PATH)) -> pd.DataFrame:
    ensure_warehouse_ready(Path(db_path_str))
    conn = duckdb.connect(db_path_str, read_only=True)
    try:
        query = """
        SELECT
            f.salesline_id,
            d.date AS order_date,
            d.year,
            d.month_no,
            d.month_name,
            d.year_month,
            d.quarter,
            p.product_code,
            p.product_name,
            p.product_prefix,
            p.category,
            c.customer_name,
            c.legal_form,
            c.wilaya AS customer_wilaya,
            t.typevente_code,
            t.typevente_label_optional,
            w.wilaya_name,
            f.qty,
            f.amount_ht,
            f.tax_amount,
            f.amount_ttc,
            f.order_number_optional,
            f.raw_num_cmd_optional
        FROM fact_salesline f
        JOIN dim_date d ON f.date_id = d.date_id
        JOIN dim_product p ON f.product_id = p.product_id
        JOIN dim_customer c ON f.customer_id = c.customer_id
        JOIN dim_typevente t ON f.typevente_id = t.typevente_id
        JOIN dim_wilaya w ON f.wilaya_id = w.wilaya_id
        """
        df = conn.execute(query).df()
    finally:
        conn.close()

    df["order_date"] = pd.to_datetime(df["order_date"], errors="coerce").dt.date
    return df


@st.cache_data(show_spinner=False)
def load_semantic_purchases(db_path_str: str = str(DUCKDB_PATH)) -> pd.DataFrame:
    ensure_warehouse_ready(Path(db_path_str))
    conn = duckdb.connect(db_path_str, read_only=True)
    try:
        query = """
        SELECT
            f.purchaseline_id,
            d.date AS order_date,
            d.year,
            d.month_no,
            d.month_name,
            d.year_month,
            d.quarter,
            p.product_code,
            p.product_name,
            p.product_prefix,
            p.category,
            s.supplier_name,
            s.supplier_legal_form,
            t.typeachat_code,
            t.typeachat_label,
            f.qty,
            f.amount_ht,
            f.tax_amount,
            f.amount_ttc,
            f.order_number_optional,
            f.raw_num_cmd_optional
        FROM fact_purchaseline f
        JOIN dim_date d ON f.date_id = d.date_id
        JOIN dim_product p ON f.product_id = p.product_id
        JOIN dim_supplier s ON f.supplier_id = s.supplier_id
        JOIN dim_typeachat t ON f.typeachat_id = t.typeachat_id
        """
        df = conn.execute(query).df()
    finally:
        conn.close()

    df["order_date"] = pd.to_datetime(df["order_date"], errors="coerce").dt.date
    return df


@st.cache_data(show_spinner=False)
def load_margin_monthly(db_path_str: str = str(DUCKDB_PATH)) -> pd.DataFrame:
    ensure_warehouse_ready(Path(db_path_str))
    conn = duckdb.connect(db_path_str, read_only=True)
    try:
        query = """
        SELECT
            m.margin_monthly_id,
            m.year,
            m.month_no,
            d.month_name,
            m.year_month,
            m.product_id,
            p.product_code,
            p.product_name,
            m.category,
            m.wilaya_id,
            w.wilaya_name,
            m.sold_qty,
            m.revenue,
            m.cogs,
            m.gross_margin_value,
            m.gross_margin_pct,
            m.avg_sale_unit_price,
            m.avg_pmp_unit_cost,
            m.sold_revenue_ttc
        FROM fact_margin_monthly m
        JOIN dim_product p ON m.product_id = p.product_id
        LEFT JOIN dim_wilaya w ON m.wilaya_id = w.wilaya_id
        LEFT JOIN (
            SELECT DISTINCT year, month_no, month_name
            FROM dim_date
        ) d
            ON d.year = m.year
           AND d.month_no = m.month_no
        """
        df = conn.execute(query).df()
    finally:
        conn.close()

    return df


@st.cache_data(show_spinner=False)
def load_inventory_ledger(db_path_str: str = str(DUCKDB_PATH)) -> pd.DataFrame:
    ensure_warehouse_ready(Path(db_path_str))
    conn = duckdb.connect(db_path_str, read_only=True)
    try:
        query = """
        SELECT
            l.inventory_event_id,
            l.date,
            l.year,
            l.month_no,
            d.month_name,
            l.year_month,
            l.product_id,
            l.product_name,
            l.category,
            l.wilaya_id,
            l.wilaya_name,
            l.event_type,
            l.event_sequence,
            l.purchase_qty,
            l.sale_qty,
            l.purchase_unit_price,
            l.sale_unit_price,
            l.ppm_unit_cost_before,
            l.ppm_unit_cost_after,
            l.stock_qty_before,
            l.stock_qty_after,
            l.stock_value_before,
            l.stock_value_after,
            l.purchase_value,
            l.sale_revenue,
            l.cost_of_goods_sold,
            l.gross_margin_value,
            l.gross_margin_pct,
            l.margin_value,
            l.margin_pct,
            l.error_code,
            l.valid_for_margin,
            l.salesline_id_optional,
            l.purchaseline_id_optional
        FROM view_inventory_ledger l
        LEFT JOIN (
            SELECT DISTINCT year, month_no, month_name
            FROM dim_date
        ) d
            ON d.year = l.year
           AND d.month_no = l.month_no
        ORDER BY l.product_id, l.date, l.event_sequence
        """
        df = conn.execute(query).df()
    finally:
        conn.close()

    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date
    return df


def clear_all_caches() -> None:
    load_semantic_sales.clear()
    load_semantic_purchases.clear()
    load_margin_monthly.clear()
    load_inventory_ledger.clear()


def refresh_warehouse(**build_kwargs: object) -> dict[str, int]:
    counts = build_warehouse(**build_kwargs)
    clear_all_caches()
    return counts


def render_sidebar_filters(df: pd.DataFrame, key_prefix: str = "global") -> dict[str, object]:
    st.sidebar.subheader("Filters")

    date_min = pd.to_datetime(df["order_date"], errors="coerce").min()
    date_max = pd.to_datetime(df["order_date"], errors="coerce").max()
    default_range = (date_min.date(), date_max.date()) if pd.notna(date_min) and pd.notna(date_max) else None
    date_range = st.sidebar.date_input(
        "Date range",
        value=default_range,
        key=f"{key_prefix}_date_range",
    )

    years = sorted([int(x) for x in df["year"].dropna().unique().tolist()])
    selected_years = st.sidebar.multiselect("Year", options=years, default=years, key=f"{key_prefix}_year")

    month_order = (
        df[["month_no", "month_name"]].dropna().drop_duplicates().sort_values("month_no")["month_name"].tolist()
    )
    selected_months = st.sidebar.multiselect(
        "Month",
        options=month_order,
        default=month_order,
        key=f"{key_prefix}_month",
    )

    typeventes = sorted(df["typevente_code"].dropna().unique().tolist())
    selected_typeventes = st.sidebar.multiselect(
        "Type vente",
        options=typeventes,
        default=typeventes,
        key=f"{key_prefix}_typevente",
    )

    categories = sorted(df["category"].dropna().unique().tolist())
    selected_categories = st.sidebar.multiselect(
        "Category",
        options=categories,
        default=categories,
        key=f"{key_prefix}_category",
    )

    wilayas = sorted(df["wilaya_name"].dropna().unique().tolist())
    selected_wilayas = st.sidebar.multiselect(
        "Wilaya",
        options=wilayas,
        default=wilayas,
        key=f"{key_prefix}_wilaya",
    )

    legal_forms = sorted(df["legal_form"].dropna().unique().tolist())
    selected_legal_forms = st.sidebar.multiselect(
        "Legal form",
        options=legal_forms,
        default=legal_forms,
        key=f"{key_prefix}_legalform",
    )

    return {
        "date_range": date_range,
        "years": selected_years,
        "months": selected_months,
        "typevente": selected_typeventes,
        "category": selected_categories,
        "wilaya": selected_wilayas,
        "legal_form": selected_legal_forms,
    }


def apply_filters(df: pd.DataFrame, filters: dict[str, object]) -> pd.DataFrame:
    out = df.copy()
    out["order_date"] = pd.to_datetime(out["order_date"], errors="coerce")

    date_range = filters.get("date_range")
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start, end = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])
        out = out[(out["order_date"] >= start) & (out["order_date"] <= end)]

    if filters.get("years"):
        out = out[out["year"].isin(filters["years"])]
    if filters.get("months"):
        out = out[out["month_name"].isin(filters["months"])]
    if filters.get("typevente"):
        out = out[out["typevente_code"].isin(filters["typevente"])]
    if filters.get("category"):
        out = out[out["category"].isin(filters["category"])]
    if filters.get("wilaya"):
        out = out[out["wilaya_name"].isin(filters["wilaya"])]
    if filters.get("legal_form"):
        out = out[out["legal_form"].isin(filters["legal_form"])]

    return out


def render_sidebar_filters_purchases(df: pd.DataFrame, key_prefix: str = "purchases") -> dict[str, object]:
    st.sidebar.subheader("Purchases Filters")

    date_min = pd.to_datetime(df["order_date"], errors="coerce").min()
    date_max = pd.to_datetime(df["order_date"], errors="coerce").max()
    default_range = (date_min.date(), date_max.date()) if pd.notna(date_min) and pd.notna(date_max) else None
    date_range = st.sidebar.date_input("Date range", value=default_range, key=f"{key_prefix}_date_range")

    years = sorted([int(x) for x in df["year"].dropna().unique().tolist()])
    selected_years = st.sidebar.multiselect("Year", options=years, default=years, key=f"{key_prefix}_year")

    month_order = (
        df[["month_no", "month_name"]].dropna().drop_duplicates().sort_values("month_no")["month_name"].tolist()
    )
    selected_months = st.sidebar.multiselect("Month", options=month_order, default=month_order, key=f"{key_prefix}_month")

    typeachats = sorted(df["typeachat_code"].dropna().unique().tolist())
    selected_typeachats = st.sidebar.multiselect(
        "Type achat",
        options=typeachats,
        default=typeachats,
        key=f"{key_prefix}_typeachat",
    )

    categories = sorted(df["category"].dropna().unique().tolist())
    selected_categories = st.sidebar.multiselect(
        "Category",
        options=categories,
        default=categories,
        key=f"{key_prefix}_category",
    )

    supplier_legal_forms = sorted(df["supplier_legal_form"].dropna().unique().tolist())
    selected_supplier_legal_forms = st.sidebar.multiselect(
        "Supplier legal form",
        options=supplier_legal_forms,
        default=supplier_legal_forms,
        key=f"{key_prefix}_supplier_legal_form",
    )

    suppliers = sorted(df["supplier_name"].dropna().unique().tolist())
    selected_suppliers = st.sidebar.multiselect(
        "Supplier",
        options=suppliers,
        default=suppliers,
        key=f"{key_prefix}_supplier",
    )

    products = sorted(df["product_name"].dropna().unique().tolist())
    selected_products = st.sidebar.multiselect(
        "Product",
        options=products,
        default=products,
        key=f"{key_prefix}_product",
    )

    return {
        "date_range": date_range,
        "years": selected_years,
        "months": selected_months,
        "typeachat": selected_typeachats,
        "category": selected_categories,
        "supplier_legal_form": selected_supplier_legal_forms,
        "supplier_name": selected_suppliers,
        "product": selected_products,
    }


def apply_filters_purchases(df: pd.DataFrame, filters: dict[str, object]) -> pd.DataFrame:
    out = df.copy()
    out["order_date"] = pd.to_datetime(out["order_date"], errors="coerce")

    date_range = filters.get("date_range")
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start, end = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])
        out = out[(out["order_date"] >= start) & (out["order_date"] <= end)]

    if filters.get("years"):
        out = out[out["year"].isin(filters["years"])]
    if filters.get("months"):
        out = out[out["month_name"].isin(filters["months"])]
    if filters.get("typeachat"):
        out = out[out["typeachat_code"].isin(filters["typeachat"])]
    if filters.get("category"):
        out = out[out["category"].isin(filters["category"])]
    if filters.get("supplier_legal_form"):
        out = out[out["supplier_legal_form"].isin(filters["supplier_legal_form"])]
    if filters.get("supplier_name"):
        out = out[out["supplier_name"].isin(filters["supplier_name"])]
    if filters.get("product"):
        out = out[out["product_name"].isin(filters["product"])]

    return out


def render_sidebar_filters_margins(df: pd.DataFrame, key_prefix: str = "margins") -> dict[str, object]:
    st.sidebar.subheader("Margins Filters")

    year_months = sorted(df["year_month"].dropna().unique().tolist())
    default_year_month_range = (year_months[0], year_months[-1]) if year_months else None
    selected_year_month_range = (
        st.sidebar.select_slider(
            "YearMonth range",
            options=year_months,
            value=default_year_month_range,
            key=f"{key_prefix}_year_month_range",
        )
        if len(year_months) >= 2
        else default_year_month_range
    )

    selected_year_months = st.sidebar.multiselect(
        "YearMonth (exact filter)",
        options=year_months,
        default=year_months,
        key=f"{key_prefix}_year_month",
    )

    years = sorted([int(x) for x in df["year"].dropna().unique().tolist()])
    selected_years = st.sidebar.multiselect("Year", options=years, default=years, key=f"{key_prefix}_year")

    month_order = (
        df[["month_no", "month_name"]].dropna().drop_duplicates().sort_values("month_no")["month_name"].tolist()
    )
    selected_months = st.sidebar.multiselect("Month", options=month_order, default=month_order, key=f"{key_prefix}_month")

    categories = sorted(df["category"].dropna().unique().tolist())
    selected_categories = st.sidebar.multiselect(
        "Category",
        options=categories,
        default=categories,
        key=f"{key_prefix}_category",
    )

    products = sorted(df["product_name"].dropna().unique().tolist())
    selected_products = st.sidebar.multiselect(
        "Product",
        options=products,
        default=products,
        key=f"{key_prefix}_product",
    )

    wilayas = sorted(df["wilaya_name"].dropna().unique().tolist())
    selected_wilayas = st.sidebar.multiselect(
        "Wilaya",
        options=wilayas,
        default=wilayas,
        key=f"{key_prefix}_wilaya",
    )

    return {
        "year_month": selected_year_months,
        "year_month_range": selected_year_month_range,
        "years": selected_years,
        "months": selected_months,
        "category": selected_categories,
        "product": selected_products,
        "wilaya": selected_wilayas,
    }


def apply_filters_margins(df: pd.DataFrame, filters: dict[str, object]) -> pd.DataFrame:
    out = df.copy()
    year_month_range = filters.get("year_month_range")
    if isinstance(year_month_range, tuple) and len(year_month_range) == 2:
        start_ym, end_ym = year_month_range
        if start_ym and end_ym:
            out = out[(out["year_month"] >= start_ym) & (out["year_month"] <= end_ym)]

    if filters.get("year_month"):
        out = out[out["year_month"].isin(filters["year_month"])]
    if filters.get("years"):
        out = out[out["year"].isin(filters["years"])]
    if filters.get("months"):
        out = out[out["month_name"].isin(filters["months"])]
    if filters.get("category"):
        out = out[out["category"].isin(filters["category"])]
    if filters.get("product"):
        out = out[out["product_name"].isin(filters["product"])]
    if filters.get("wilaya"):
        out = out[out["wilaya_name"].isin(filters["wilaya"])]
    return out


def apply_filters_inventory_ledger(
    df: pd.DataFrame,
    product: str | None = None,
    date_range: tuple[object, object] | None = None,
) -> pd.DataFrame:
    out = df.copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce")

    if product and product != "All":
        out = out[out["product_name"] == product]

    if isinstance(date_range, tuple) and len(date_range) == 2:
        start, end = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])
        out = out[(out["date"] >= start) & (out["date"] <= end)]

    return out


def get_margin_columns(_: str | None = None) -> dict[str, str]:
    return {
        "revenue": "revenue",
        "cogs": "cogs",
        "margin_value": "gross_margin_value",
        "margin_pct": "gross_margin_pct",
        "sold_qty": "sold_qty",
        "pmp_unit_cost": "avg_pmp_unit_cost",
    }


def export_fact_margin_monthly(
    df: pd.DataFrame,
    output_dir: Path = REPORTS_DIR,
    filename: str = "export_fact_margin_monthly.csv",
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / filename
    df.to_csv(out_path, index=False, encoding="utf-8")
    return out_path


def export_inventory_ledger(
    df: pd.DataFrame,
    output_dir: Path = REPORTS_DIR,
    filename: str = "inventory_ledger_export.csv",
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / filename
    df.to_csv(out_path, index=False, encoding="utf-8")
    return out_path


def aggregate_measure(df: pd.DataFrame, dimension_col: str, measure_label: str) -> pd.DataFrame:
    measure_col = MEASURE_COLUMNS[measure_label]
    agg = (
        df.groupby(dimension_col, dropna=False)[measure_col]
        .sum()
        .reset_index()
        .sort_values(measure_col, ascending=False)
    )
    return agg
