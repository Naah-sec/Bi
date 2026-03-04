from __future__ import annotations

import argparse
import unicodedata
from pathlib import Path

import duckdb
import pandas as pd

from src.config import (
    DEFAULT_TYPEACHAT_LABELS,
    DEFAULT_TYPEVENTE_LABELS,
    DUCKDB_PATH,
    EXCEL_PATH,
    MARGIN_MISSING_COST_AS_ZERO,
    PURCHASES_CSV_PATH,
    PURCHASES_EXCEL_PATH,
    QA_TOLERANCE,
    REPORTS_DIR,
)
from src.io_excel import read_purchases_inputs, read_sales_excel_inputs
from src.qa import (
    generate_profile_markdown,
    run_inventory_event_validation,
    run_purchases_validation,
    run_qa,
)
from src.transform import PurchasesTransformResult, TransformResult, transform_purchases, transform_sales


def _normalize_name(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value))
    text = text.encode("ascii", "ignore").decode("ascii")
    return "".join(ch for ch in text.lower() if ch.isalnum())


def _missing_required_columns(raw_df: pd.DataFrame) -> list[str]:
    normalized_columns = {_normalize_name(col) for col in raw_df.columns}
    required_groups: list[list[str]] = [
        ["Num.CMD"],
        ["Date.CMD"],
        ["Fournisseur", "Supplier", "Vendor"],
        ["Code Produit"],
        ["Produit"],
        ["Qte", "Qt", "Qty", "QTY", "Quantite"],
        ["Montant HT"],
        ["Taxe"],
        ["Montant TTC"],
    ]

    missing: list[str] = []
    for group in required_groups:
        if not any(_normalize_name(name) in normalized_columns for name in group):
            missing.append(group[0])
    return missing


def _empty_purchases_df() -> pd.DataFrame:
    columns = [
        "raw_num_cmd",
        "date_cmd",
        "supplier_raw",
        "supplier_legal_form",
        "supplier_name",
        "product_code",
        "product_name",
        "qty",
        "amount_ht",
        "tax_amount",
        "amount_ttc",
        "typeachat_code",
        "order_number_optional",
        "product_prefix",
        "category",
        "year",
        "month_no",
        "month_name",
        "year_month",
        "date_key",
    ]
    return pd.DataFrame(columns=columns)


def _first_non_empty(series: pd.Series, fallback: str = "UNKNOWN") -> str:
    cleaned = series.dropna().astype(str).str.strip()
    cleaned = cleaned[cleaned != ""]
    if cleaned.empty:
        return fallback
    return cleaned.iloc[0]


def _first_non_unknown(series: pd.Series, fallback: str = "Unknown") -> str:
    cleaned = series.dropna().astype(str).str.strip()
    cleaned = cleaned[cleaned != ""]
    preferred = cleaned[~cleaned.str.lower().eq("unknown")]
    if not preferred.empty:
        return preferred.iloc[0]
    if not cleaned.empty:
        return cleaned.iloc[0]
    return fallback


def _build_dim_date(sales_df: pd.DataFrame, purchases_df: pd.DataFrame) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []

    if not sales_df.empty:
        frames.append(sales_df[["date_cmd", "year", "month_no", "month_name", "year_month"]].copy())
    if not purchases_df.empty:
        frames.append(purchases_df[["date_cmd", "year", "month_no", "month_name", "year_month"]].copy())

    if not frames:
        return pd.DataFrame(columns=["date_id", "date", "year", "month_no", "month_name", "year_month", "quarter"])

    dim_date = pd.concat(frames, ignore_index=True)
    dim_date = dim_date.dropna(subset=["date_cmd"]).drop_duplicates().sort_values("date_cmd").reset_index(drop=True)
    if dim_date.empty:
        return pd.DataFrame(columns=["date_id", "date", "year", "month_no", "month_name", "year_month", "quarter"])

    dim_date["month_no"] = pd.to_numeric(dim_date["month_no"], errors="coerce").astype("Int64")
    dim_date["year"] = pd.to_numeric(dim_date["year"], errors="coerce").astype("Int64")
    dim_date["quarter"] = "Q" + (((dim_date["month_no"] - 1) // 3 + 1).astype("Int64").astype(str))

    dim_date.insert(0, "date_id", range(1, len(dim_date) + 1))
    dim_date = dim_date.rename(columns={"date_cmd": "date"})
    return dim_date[["date_id", "date", "year", "month_no", "month_name", "year_month", "quarter"]].copy()


def _build_dim_product(sales_df: pd.DataFrame, purchases_df: pd.DataFrame) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []

    if not sales_df.empty:
        frames.append(sales_df[["product_code", "product_name", "product_prefix", "category"]].copy())
    if not purchases_df.empty:
        frames.append(purchases_df[["product_code", "product_name", "product_prefix", "category"]].copy())

    if not frames:
        return pd.DataFrame(columns=["product_id", "product_code", "product_name", "product_prefix", "category"])

    all_products = pd.concat(frames, ignore_index=True)
    all_products["product_code"] = all_products["product_code"].fillna("").astype(str).str.strip()
    all_products = all_products[all_products["product_code"] != ""].copy()

    if all_products.empty:
        return pd.DataFrame(columns=["product_id", "product_code", "product_name", "product_prefix", "category"])

    grouped = (
        all_products.groupby("product_code", as_index=False)
        .agg(
            product_name=("product_name", lambda s: _first_non_empty(s, "UNKNOWN")),
            product_prefix=("product_prefix", lambda s: _first_non_empty(s, "UNKNOWN")),
            category=("category", lambda s: _first_non_unknown(s, "Unknown")),
        )
        .sort_values("product_code")
        .reset_index(drop=True)
    )

    grouped.insert(0, "product_id", range(1, len(grouped) + 1))
    return grouped[["product_id", "product_code", "product_name", "product_prefix", "category"]].copy()


def _build_dim_customer(sales_df: pd.DataFrame) -> pd.DataFrame:
    if sales_df.empty:
        return pd.DataFrame(columns=["customer_id", "customer_name", "legal_form", "wilaya", "address_optional"])

    dim_customer = (
        sales_df[["customer_name", "legal_form", "wilaya", "address"]]
        .drop_duplicates()
        .sort_values(["customer_name", "legal_form", "wilaya"])
        .reset_index(drop=True)
    )
    dim_customer.insert(0, "customer_id", range(1, len(dim_customer) + 1))
    dim_customer = dim_customer.rename(columns={"address": "address_optional"})
    return dim_customer[["customer_id", "customer_name", "legal_form", "wilaya", "address_optional"]].copy()


def _build_dim_typevente(sales_df: pd.DataFrame, typevente_label_map: dict[str, str]) -> pd.DataFrame:
    if sales_df.empty:
        return pd.DataFrame(columns=["typevente_id", "typevente_code", "typevente_label_optional"])

    codes = sales_df[["typevente_code"]].dropna().copy()
    codes["typevente_code"] = codes["typevente_code"].astype(str).str.strip().str.upper()
    codes = codes[codes["typevente_code"] != ""].drop_duplicates().sort_values("typevente_code").reset_index(drop=True)
    codes["typevente_label_optional"] = codes["typevente_code"].map(
        lambda c: typevente_label_map.get(c, DEFAULT_TYPEVENTE_LABELS.get(c, c))
    )
    codes.insert(0, "typevente_id", range(1, len(codes) + 1))
    return codes[["typevente_id", "typevente_code", "typevente_label_optional"]].copy()


def _build_dim_wilaya(sales_df: pd.DataFrame) -> pd.DataFrame:
    if sales_df.empty:
        return pd.DataFrame(columns=["wilaya_id", "wilaya_name"])

    dim_wilaya = sales_df[["wilaya"]].dropna().copy()
    dim_wilaya["wilaya"] = dim_wilaya["wilaya"].astype(str).str.strip()
    dim_wilaya = dim_wilaya[dim_wilaya["wilaya"] != ""].drop_duplicates().sort_values("wilaya").reset_index(drop=True)
    dim_wilaya = dim_wilaya.rename(columns={"wilaya": "wilaya_name"})
    dim_wilaya.insert(0, "wilaya_id", range(1, len(dim_wilaya) + 1))
    return dim_wilaya[["wilaya_id", "wilaya_name"]].copy()


def _build_dim_supplier(purchases_df: pd.DataFrame) -> pd.DataFrame:
    if purchases_df.empty:
        return pd.DataFrame(columns=["supplier_id", "supplier_name", "supplier_legal_form"])

    dim_supplier = (
        purchases_df[["supplier_name", "supplier_legal_form"]]
        .drop_duplicates()
        .sort_values(["supplier_name", "supplier_legal_form"])
        .reset_index(drop=True)
    )
    dim_supplier.insert(0, "supplier_id", range(1, len(dim_supplier) + 1))
    return dim_supplier[["supplier_id", "supplier_name", "supplier_legal_form"]].copy()


def _build_dim_typeachat(purchases_df: pd.DataFrame, typeachat_label_map: dict[str, str]) -> pd.DataFrame:
    if purchases_df.empty:
        return pd.DataFrame(columns=["typeachat_id", "typeachat_code", "typeachat_label"])

    codes = purchases_df[["typeachat_code"]].dropna().copy()
    codes["typeachat_code"] = codes["typeachat_code"].astype(str).str.strip().str.upper()
    codes = codes[codes["typeachat_code"] != ""].drop_duplicates().sort_values("typeachat_code").reset_index(drop=True)
    codes["typeachat_label"] = codes["typeachat_code"].map(
        lambda c: typeachat_label_map.get(c, DEFAULT_TYPEACHAT_LABELS.get(c, c))
    )
    codes.insert(0, "typeachat_id", range(1, len(codes) + 1))
    return codes[["typeachat_id", "typeachat_code", "typeachat_label"]].copy()


def _cast_int_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    for col in columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
    return df


def _build_fact_salesline(
    sales_df: pd.DataFrame,
    dim_date: pd.DataFrame,
    dim_product: pd.DataFrame,
    dim_customer: pd.DataFrame,
    dim_typevente: pd.DataFrame,
    dim_wilaya: pd.DataFrame,
) -> pd.DataFrame:
    output_columns = [
        "salesline_id",
        "date_id",
        "product_id",
        "customer_id",
        "typevente_id",
        "wilaya_id",
        "qty",
        "amount_ht",
        "tax_amount",
        "amount_ttc",
        "order_number_optional",
        "raw_num_cmd_optional",
    ]

    if sales_df.empty:
        return pd.DataFrame(columns=output_columns)

    fact = sales_df.copy().reset_index(drop=True)
    fact.insert(0, "salesline_id", range(1, len(fact) + 1))

    fact = fact.merge(dim_date[["date_id", "date"]], left_on="date_cmd", right_on="date", how="left")
    fact = fact.merge(dim_product[["product_id", "product_code"]], on="product_code", how="left")
    fact = fact.merge(
        dim_customer[["customer_id", "customer_name", "legal_form", "wilaya", "address_optional"]],
        left_on=["customer_name", "legal_form", "wilaya", "address"],
        right_on=["customer_name", "legal_form", "wilaya", "address_optional"],
        how="left",
    )
    fact = fact.merge(dim_typevente[["typevente_id", "typevente_code"]], on="typevente_code", how="left")
    fact = fact.merge(dim_wilaya, left_on="wilaya", right_on="wilaya_name", how="left")

    out = fact[
        [
            "salesline_id",
            "date_id",
            "product_id",
            "customer_id",
            "typevente_id",
            "wilaya_id",
            "qty",
            "amount_ht",
            "tax_amount",
            "amount_ttc",
            "order_number_optional",
            "raw_num_cmd",
        ]
    ].rename(columns={"raw_num_cmd": "raw_num_cmd_optional"})

    out = _cast_int_columns(out, ["salesline_id", "date_id", "product_id", "customer_id", "typevente_id", "wilaya_id"])
    return out


def _build_fact_purchaseline(
    purchases_df: pd.DataFrame,
    dim_date: pd.DataFrame,
    dim_product: pd.DataFrame,
    dim_supplier: pd.DataFrame,
    dim_typeachat: pd.DataFrame,
) -> pd.DataFrame:
    output_columns = [
        "purchaseline_id",
        "date_id",
        "product_id",
        "supplier_id",
        "typeachat_id",
        "qty",
        "amount_ht",
        "tax_amount",
        "amount_ttc",
        "order_number_optional",
        "raw_num_cmd_optional",
    ]

    if purchases_df.empty:
        return pd.DataFrame(columns=output_columns)

    fact = purchases_df.copy().reset_index(drop=True)
    fact.insert(0, "purchaseline_id", range(1, len(fact) + 1))

    fact = fact.merge(dim_date[["date_id", "date"]], left_on="date_cmd", right_on="date", how="left")
    fact = fact.merge(dim_product[["product_id", "product_code"]], on="product_code", how="left")
    fact = fact.merge(dim_supplier, on=["supplier_name", "supplier_legal_form"], how="left")
    fact = fact.merge(dim_typeachat[["typeachat_id", "typeachat_code"]], on="typeachat_code", how="left")

    out = fact[
        [
            "purchaseline_id",
            "date_id",
            "product_id",
            "supplier_id",
            "typeachat_id",
            "qty",
            "amount_ht",
            "tax_amount",
            "amount_ttc",
            "order_number_optional",
            "raw_num_cmd",
        ]
    ].rename(columns={"raw_num_cmd": "raw_num_cmd_optional"})

    out = _cast_int_columns(out, ["purchaseline_id", "date_id", "product_id", "supplier_id", "typeachat_id"])
    return out


def build_purchase_unit_cost_events(purchases_df: pd.DataFrame, dim_product: pd.DataFrame) -> pd.DataFrame:
    output_columns = [
        "purchase_event_id",
        "product_id",
        "purchase_date",
        "year",
        "month_no",
        "year_month",
        "qty",
        "amount_ttc",
        "unit_cost_event_ttc",
    ]

    if purchases_df.empty:
        return pd.DataFrame(columns=output_columns)

    events = purchases_df.copy()
    events = events[(events["qty"] > 0) & events["amount_ttc"].notna()]
    if events.empty:
        return pd.DataFrame(columns=output_columns)

    events = events.merge(dim_product[["product_id", "product_code"]], on="product_code", how="left")
    events["purchase_date"] = pd.to_datetime(events["date_cmd"], errors="coerce")
    events = events[events["purchase_date"].notna()].copy()
    if events.empty:
        return pd.DataFrame(columns=output_columns)

    events["unit_cost_event_ttc"] = events["amount_ttc"] / events["qty"]
    events["year"] = pd.to_numeric(events["year"], errors="coerce").astype("Int64")
    events["month_no"] = pd.to_numeric(events["month_no"], errors="coerce").astype("Int64")

    events = events[
        ["product_id", "purchase_date", "year", "month_no", "year_month", "qty", "amount_ttc", "unit_cost_event_ttc"]
    ].copy()
    events = events.sort_values(["product_id", "purchase_date"]).reset_index(drop=True)
    events.insert(0, "purchase_event_id", range(1, len(events) + 1))
    events = _cast_int_columns(events, ["purchase_event_id", "product_id", "year", "month_no"])
    return events


def compute_ppm_product_month(
    purchase_events_df: pd.DataFrame,
    dim_date: pd.DataFrame,
    product_ids: list[int] | pd.Series,
) -> pd.DataFrame:
    output_columns = [
        "product_id",
        "year",
        "month_no",
        "year_month",
        "purchased_qty",
        "purchased_cost_ttc",
        "cum_purchase_qty",
        "cum_purchase_cost_ttc",
        "ppm_simple_to_month",
        "ppm_weighted_to_month",
    ]

    month_dim = dim_date[["year", "month_no", "year_month"]].dropna().drop_duplicates().copy()
    if month_dim.empty or len(product_ids) == 0:
        return pd.DataFrame(columns=output_columns)

    month_dim["year"] = pd.to_numeric(month_dim["year"], errors="coerce").astype("Int64")
    month_dim["month_no"] = pd.to_numeric(month_dim["month_no"], errors="coerce").astype("Int64")
    month_dim = month_dim.sort_values(["year", "month_no"]).reset_index(drop=True)

    product_df = pd.DataFrame({"product_id": pd.Series(list(product_ids), dtype="Int64")})
    product_df = product_df.dropna().drop_duplicates().reset_index(drop=True)
    if product_df.empty:
        return pd.DataFrame(columns=output_columns)

    product_df["_k"] = 1
    month_dim["_k"] = 1
    grid = product_df.merge(month_dim, on="_k", how="inner").drop(columns="_k")

    if purchase_events_df.empty:
        grid["purchased_qty"] = 0.0
        grid["purchased_cost_ttc"] = 0.0
        grid["cum_purchase_qty"] = 0.0
        grid["cum_purchase_cost_ttc"] = 0.0
        grid["ppm_simple_to_month"] = pd.NA
        grid["ppm_weighted_to_month"] = pd.NA
        return grid[output_columns]

    events = purchase_events_df.copy()
    monthly = (
        events.groupby(["product_id", "year", "month_no", "year_month"], dropna=False)
        .agg(
            event_count=("unit_cost_event_ttc", "count"),
            sum_unit_cost=("unit_cost_event_ttc", "sum"),
            purchased_qty=("qty", "sum"),
            purchased_cost_ttc=("amount_ttc", "sum"),
        )
        .reset_index()
    )

    out = grid.merge(monthly, on=["product_id", "year", "month_no", "year_month"], how="left")
    out = out.sort_values(["product_id", "year", "month_no"]).reset_index(drop=True)

    out[["event_count", "sum_unit_cost", "purchased_qty", "purchased_cost_ttc"]] = out[
        ["event_count", "sum_unit_cost", "purchased_qty", "purchased_cost_ttc"]
    ].fillna(0.0)

    out["cum_event_count"] = out.groupby("product_id")["event_count"].cumsum()
    out["cum_sum_unit_cost"] = out.groupby("product_id")["sum_unit_cost"].cumsum()
    out["cum_purchase_qty"] = out.groupby("product_id")["purchased_qty"].cumsum()
    out["cum_purchase_cost_ttc"] = out.groupby("product_id")["purchased_cost_ttc"].cumsum()

    out["ppm_simple_to_month"] = (out["cum_sum_unit_cost"] / out["cum_event_count"]).where(out["cum_event_count"] > 0)
    out["ppm_weighted_to_month"] = (out["cum_purchase_cost_ttc"] / out["cum_purchase_qty"]).where(
        out["cum_purchase_qty"] > 0
    )

    out = out[output_columns].copy()
    out = _cast_int_columns(out, ["product_id", "year", "month_no"])
    return out


def build_fact_inventory_events(
    sales_df: pd.DataFrame,
    purchases_df: pd.DataFrame,
    dim_product: pd.DataFrame,
    dim_wilaya: pd.DataFrame,
    tolerance: float = 0.01,
) -> pd.DataFrame:
    output_columns = [
        "inventory_event_id",
        "date",
        "year",
        "month_no",
        "year_month",
        "product_id",
        "product_code",
        "product_name",
        "category",
        "wilaya_id",
        "wilaya_name",
        "event_type",
        "event_sequence",
        "purchase_qty",
        "sale_qty",
        "purchase_unit_price",
        "sale_unit_price",
        "ppm_unit_cost_before",
        "ppm_unit_cost_after",
        "stock_qty_before",
        "stock_qty_after",
        "stock_value_before",
        "stock_value_after",
        "purchase_value",
        "sale_revenue",
        "cost_of_goods_sold",
        "gross_margin_value",
        "gross_margin_pct",
        "margin_value",
        "margin_pct",
        "error_code",
        "valid_for_margin",
        "salesline_id_optional",
        "purchaseline_id_optional",
    ]

    event_frames: list[pd.DataFrame] = []

    if not purchases_df.empty:
        p = purchases_df.copy().reset_index(drop=True)
        p["event_type"] = "PURCHASE"
        p["event_priority"] = 1
        p["source_sequence"] = p.index + 1
        p["date"] = pd.to_datetime(p["date_cmd"], errors="coerce").dt.date
        p["purchase_qty"] = p["qty"]
        p["sale_qty"] = 0.0
        p["purchase_unit_price"] = (p["amount_ttc"] / p["qty"]).where(p["qty"] > 0)
        p["sale_unit_price"] = pd.NA
        p["purchase_value_input"] = p["amount_ttc"]
        p["sale_revenue_input"] = pd.NA
        p["wilaya_name"] = pd.NA
        p["salesline_id_optional"] = pd.NA
        p["purchaseline_id_optional"] = p["source_sequence"]
        event_frames.append(
            p[
                [
                    "date",
                    "product_code",
                    "product_name",
                    "category",
                    "event_type",
                    "event_priority",
                    "source_sequence",
                    "purchase_qty",
                    "sale_qty",
                    "purchase_unit_price",
                    "sale_unit_price",
                    "purchase_value_input",
                    "sale_revenue_input",
                    "wilaya_name",
                    "salesline_id_optional",
                    "purchaseline_id_optional",
                ]
            ].copy()
        )

    if not sales_df.empty:
        s = sales_df.copy().reset_index(drop=True)
        s["event_type"] = "SALE"
        s["event_priority"] = 2
        s["source_sequence"] = s.index + 1
        s["date"] = pd.to_datetime(s["date_cmd"], errors="coerce").dt.date
        s["purchase_qty"] = 0.0
        s["sale_qty"] = s["qty"]
        s["purchase_unit_price"] = pd.NA
        s["sale_unit_price"] = (s["amount_ttc"] / s["qty"]).where(s["qty"] > 0)
        s["purchase_value_input"] = pd.NA
        s["sale_revenue_input"] = s["amount_ttc"]
        s["wilaya_name"] = s["wilaya"]
        s["salesline_id_optional"] = s["source_sequence"]
        s["purchaseline_id_optional"] = pd.NA
        event_frames.append(
            s[
                [
                    "date",
                    "product_code",
                    "product_name",
                    "category",
                    "event_type",
                    "event_priority",
                    "source_sequence",
                    "purchase_qty",
                    "sale_qty",
                    "purchase_unit_price",
                    "sale_unit_price",
                    "purchase_value_input",
                    "sale_revenue_input",
                    "wilaya_name",
                    "salesline_id_optional",
                    "purchaseline_id_optional",
                ]
            ].copy()
        )

    if not event_frames:
        return pd.DataFrame(columns=output_columns)

    events = pd.concat(event_frames, ignore_index=True)
    events["event_datetime"] = pd.to_datetime(events["date"], errors="coerce")
    events = events.sort_values(
        ["product_code", "event_datetime", "event_priority", "source_sequence"],
        kind="stable",
        na_position="last",
    ).reset_index(drop=True)
    events["event_sequence"] = events.groupby("product_code").cumcount() + 1

    events = events.merge(dim_product[["product_id", "product_code", "product_name", "category"]], on="product_code", how="left", suffixes=("", "_dim"))
    events["product_name"] = events["product_name"].fillna(events["product_name_dim"])
    events["category"] = events["category"].fillna(events["category_dim"])
    events = events.drop(columns=[col for col in ["product_name_dim", "category_dim"] if col in events.columns])

    events = events.merge(dim_wilaya, on="wilaya_name", how="left")

    state_map: dict[str, tuple[float, float, float | None]] = {}
    records: list[dict[str, object]] = []

    for row in events.itertuples(index=False):
        product_code = str(row.product_code) if row.product_code is not None else ""
        stock_qty_before, stock_value_before, ppm_before = state_map.get(product_code, (0.0, 0.0, None))

        stock_qty_after = stock_qty_before
        stock_value_after = stock_value_before
        ppm_after = ppm_before

        error_codes: list[str] = []
        purchase_value = pd.NA
        sale_revenue = pd.NA
        cogs = pd.NA
        gross_margin_value = pd.NA
        gross_margin_pct = pd.NA

        purchase_qty = float(row.purchase_qty) if pd.notna(row.purchase_qty) else 0.0
        sale_qty = float(row.sale_qty) if pd.notna(row.sale_qty) else 0.0
        purchase_unit_price = float(row.purchase_unit_price) if pd.notna(row.purchase_unit_price) else pd.NA
        sale_unit_price = float(row.sale_unit_price) if pd.notna(row.sale_unit_price) else pd.NA

        event_date = pd.to_datetime(row.event_datetime, errors="coerce")
        if pd.isna(event_date):
            error_codes.append("INVALID_DATE")

        update_state = False
        valid_for_margin = False

        if row.event_type == "PURCHASE":
            if purchase_qty <= 0:
                error_codes.append("INVALID_PURCHASE_QTY")
            if pd.isna(purchase_unit_price):
                error_codes.append("INVALID_PURCHASE_UNIT_PRICE")

            if not error_codes:
                purchase_value = float(purchase_qty * purchase_unit_price)
                purchase_input = float(row.purchase_value_input) if pd.notna(row.purchase_value_input) else pd.NA
                if pd.notna(purchase_input) and abs(float(purchase_value) - float(purchase_input)) > tolerance:
                    error_codes.append("PURCHASE_VALUE_MISMATCH")

            if not error_codes:
                stock_qty_after = stock_qty_before + purchase_qty
                stock_value_after = stock_value_before + float(purchase_value)
                ppm_after = (stock_value_after / stock_qty_after) if stock_qty_after > 0 else pd.NA
                update_state = True

        elif row.event_type == "SALE":
            if sale_qty <= 0:
                error_codes.append("INVALID_SALE_QTY")
            if pd.isna(sale_unit_price):
                error_codes.append("INVALID_SALE_UNIT_PRICE")

            if not error_codes:
                sale_revenue = float(sale_qty * sale_unit_price)
                revenue_input = float(row.sale_revenue_input) if pd.notna(row.sale_revenue_input) else pd.NA
                if pd.notna(revenue_input) and abs(float(sale_revenue) - float(revenue_input)) > tolerance:
                    error_codes.append("REVENUE_MISMATCH")

            if not error_codes and sale_qty > (stock_qty_before + tolerance):
                error_codes.append("INSUFFICIENT_STOCK")

            if not error_codes and ppm_before is None:
                error_codes.append("MISSING_PMP")

            if not error_codes:
                cogs = float(sale_qty * float(ppm_before))
                stock_qty_after = stock_qty_before - sale_qty
                stock_value_after = stock_value_before - float(cogs)
                ppm_after = ppm_before
                gross_margin_value = float(sale_revenue - cogs)
                gross_margin_pct = (gross_margin_value / float(sale_revenue)) if float(sale_revenue) > 0 else pd.NA
                update_state = True
                valid_for_margin = True

        if update_state:
            state_map[product_code] = (stock_qty_after, stock_value_after, ppm_after if pd.notna(ppm_after) else None)
        else:
            state_map[product_code] = (stock_qty_before, stock_value_before, ppm_before)

        error_code = ";".join(error_codes) if error_codes else None

        records.append(
            {
                "date": event_date.date() if pd.notna(event_date) else pd.NA,
                "year": int(event_date.year) if pd.notna(event_date) else pd.NA,
                "month_no": int(event_date.month) if pd.notna(event_date) else pd.NA,
                "year_month": event_date.strftime("%Y-%m") if pd.notna(event_date) else pd.NA,
                "product_id": row.product_id,
                "product_code": row.product_code,
                "product_name": row.product_name,
                "category": row.category,
                "wilaya_id": row.wilaya_id,
                "wilaya_name": row.wilaya_name,
                "event_type": row.event_type,
                "event_sequence": row.event_sequence,
                "purchase_qty": purchase_qty,
                "sale_qty": sale_qty,
                "purchase_unit_price": purchase_unit_price,
                "sale_unit_price": sale_unit_price,
                "ppm_unit_cost_before": ppm_before,
                "ppm_unit_cost_after": ppm_after,
                "stock_qty_before": stock_qty_before,
                "stock_qty_after": stock_qty_after,
                "stock_value_before": stock_value_before,
                "stock_value_after": stock_value_after,
                "purchase_value": purchase_value,
                "sale_revenue": sale_revenue,
                "cost_of_goods_sold": cogs,
                "gross_margin_value": gross_margin_value,
                "gross_margin_pct": gross_margin_pct,
                "margin_value": gross_margin_value,
                "margin_pct": gross_margin_pct,
                "error_code": error_code,
                "valid_for_margin": valid_for_margin,
                "salesline_id_optional": row.salesline_id_optional,
                "purchaseline_id_optional": row.purchaseline_id_optional,
            }
        )

    out = pd.DataFrame(records)
    out = out.sort_values(["product_id", "date", "event_sequence"], kind="stable").reset_index(drop=True)
    out.insert(0, "inventory_event_id", range(1, len(out) + 1))
    out = _cast_int_columns(
        out,
        [
            "inventory_event_id",
            "year",
            "month_no",
            "product_id",
            "wilaya_id",
            "event_sequence",
            "salesline_id_optional",
            "purchaseline_id_optional",
        ],
    )
    return out[output_columns].copy()


def build_fact_margin_monthly(inventory_events_df: pd.DataFrame) -> pd.DataFrame:
    output_columns = [
        "margin_monthly_id",
        "year",
        "month_no",
        "year_month",
        "product_id",
        "category",
        "wilaya_id",
        "sold_qty",
        "revenue",
        "cogs",
        "gross_margin_value",
        "gross_margin_pct",
        "avg_sale_unit_price",
        "avg_pmp_unit_cost",
        "sold_revenue_ttc",
    ]

    if inventory_events_df.empty:
        return pd.DataFrame(columns=output_columns)

    sales_valid = inventory_events_df[
        inventory_events_df["event_type"].eq("SALE") & inventory_events_df["valid_for_margin"].fillna(False)
    ].copy()
    if sales_valid.empty:
        return pd.DataFrame(columns=output_columns)

    grouped = (
        sales_valid.groupby(["year", "month_no", "year_month", "product_id", "category", "wilaya_id"], dropna=False)
        .agg(
            sold_qty=("sale_qty", "sum"),
            revenue=("sale_revenue", "sum"),
            cogs=("cost_of_goods_sold", "sum"),
        )
        .reset_index()
    )

    grouped["gross_margin_value"] = grouped["revenue"] - grouped["cogs"]
    grouped["gross_margin_pct"] = (grouped["gross_margin_value"] / grouped["revenue"]).where(grouped["revenue"] > 0)
    grouped["avg_sale_unit_price"] = (grouped["revenue"] / grouped["sold_qty"]).where(grouped["sold_qty"] > 0)
    grouped["avg_pmp_unit_cost"] = (grouped["cogs"] / grouped["sold_qty"]).where(grouped["sold_qty"] > 0)
    grouped["sold_revenue_ttc"] = grouped["revenue"]

    grouped = grouped.sort_values(["year", "month_no", "product_id", "wilaya_id"]).reset_index(drop=True)
    grouped.insert(0, "margin_monthly_id", range(1, len(grouped) + 1))
    grouped = _cast_int_columns(grouped, ["margin_monthly_id", "year", "month_no", "product_id", "wilaya_id"])

    return grouped[output_columns].copy()


def _build_tables(
    sales_result: TransformResult,
    purchases_result: PurchasesTransformResult,
    margin_missing_cost_as_zero: bool,
    tolerance: float,
) -> dict[str, pd.DataFrame]:
    sales_df = sales_result.salesline.copy()
    purchases_df = purchases_result.purchaseline.copy()

    dim_date = _build_dim_date(sales_df, purchases_df)
    dim_product = _build_dim_product(sales_df, purchases_df)
    dim_customer = _build_dim_customer(sales_df)
    dim_typevente = _build_dim_typevente(sales_df, sales_result.typevente_label_map)
    dim_wilaya = _build_dim_wilaya(sales_df)
    dim_supplier = _build_dim_supplier(purchases_df)
    dim_typeachat = _build_dim_typeachat(purchases_df, purchases_result.typeachat_label_map)

    fact_salesline = _build_fact_salesline(sales_df, dim_date, dim_product, dim_customer, dim_typevente, dim_wilaya)
    fact_purchaseline = _build_fact_purchaseline(purchases_df, dim_date, dim_product, dim_supplier, dim_typeachat)

    purchase_unit_cost_events = build_purchase_unit_cost_events(purchases_df, dim_product)

    sales_product_ids = (
        dim_product[dim_product["product_code"].isin(sales_df["product_code"].unique().tolist())]["product_id"].tolist()
        if not sales_df.empty
        else []
    )
    ppm_product_month = compute_ppm_product_month(
        purchase_events_df=purchase_unit_cost_events,
        dim_date=dim_date,
        product_ids=sales_product_ids,
    )

    # Accounting-correct inventory ledger and margin dataset.
    fact_inventory_events = build_fact_inventory_events(
        sales_df=sales_df,
        purchases_df=purchases_df,
        dim_product=dim_product,
        dim_wilaya=dim_wilaya,
        tolerance=tolerance,
    )
    fact_margin_monthly = build_fact_margin_monthly(fact_inventory_events)

    return {
        "dim_date": dim_date,
        "dim_product": dim_product,
        "dim_customer": dim_customer,
        "dim_typevente": dim_typevente,
        "dim_wilaya": dim_wilaya,
        "dim_supplier": dim_supplier,
        "dim_typeachat": dim_typeachat,
        "fact_salesline": fact_salesline,
        "fact_purchaseline": fact_purchaseline,
        "purchase_unit_cost_events": purchase_unit_cost_events,
        "ppm_product_month": ppm_product_month,
        "fact_inventory_events": fact_inventory_events,
        "fact_margin_monthly": fact_margin_monthly,
    }


def _create_margin_view(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(
        """
        CREATE OR REPLACE VIEW view_margin_salesline AS
        SELECT
            inventory_event_id,
            salesline_id_optional AS salesline_id,
            date,
            year,
            month_no,
            year_month,
            product_id,
            wilaya_id,
            sale_qty AS sold_qty,
            sale_revenue AS revenue,
            cost_of_goods_sold AS cogs,
            gross_margin_value,
            gross_margin_pct,
            ppm_unit_cost_before AS pmp_unit_cost,
            error_code,
            valid_for_margin
        FROM fact_inventory_events
        WHERE event_type = 'SALE'
        """
    )


def _create_inventory_ledger_view(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(
        """
        CREATE OR REPLACE VIEW view_inventory_ledger AS
        SELECT
            inventory_event_id,
            date,
            year,
            month_no,
            year_month,
            product_id,
            product_name,
            category,
            wilaya_id,
            wilaya_name,
            event_type,
            event_sequence,
            purchase_qty,
            sale_qty,
            purchase_unit_price,
            sale_unit_price,
            ppm_unit_cost_before,
            ppm_unit_cost_after,
            stock_qty_before,
            stock_qty_after,
            stock_value_before,
            stock_value_after,
            purchase_value,
            sale_revenue,
            cost_of_goods_sold,
            gross_margin_value,
            gross_margin_pct,
            margin_value,
            margin_pct,
            error_code,
            valid_for_margin,
            salesline_id_optional,
            purchaseline_id_optional
        FROM fact_inventory_events
        ORDER BY product_id, date, event_sequence
        """
    )


def _write_to_duckdb(tables: dict[str, pd.DataFrame], duckdb_path: Path) -> None:
    duckdb_path.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(duckdb_path))
    try:
        for table_name, frame in tables.items():
            conn.register("tmp_df", frame)
            conn.execute(f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM tmp_df")
            conn.unregister("tmp_df")
        _create_margin_view(conn)
        _create_inventory_ledger_view(conn)
    finally:
        conn.close()


def _build_purchases_transform(
    purchases_source: str,
    purchases_excel_path: Path,
    purchases_csv_path: Path,
    reports_dir: Path,
    tolerance: float,
    drop_invalid_purchase_rows: bool,
) -> tuple[PurchasesTransformResult, str]:
    purchases_input = read_purchases_inputs(
        purchases_excel_path=purchases_excel_path,
        purchases_csv_path=purchases_csv_path,
        source=purchases_source,
    )

    source_used = str(purchases_input.get("source", "none"))
    raw_df = purchases_input["purchases_raw"]

    if raw_df is None or raw_df.empty:
        empty_result = PurchasesTransformResult(
            purchaseline=_empty_purchases_df(),
            missing_prefixes=[],
            typeachat_label_map={},
        )
        generate_profile_markdown(
            empty_result.purchaseline,
            output_dir=reports_dir,
            filename="purchases_profile.md",
            title="Purchases Data Profile",
        )
        return empty_result, source_used

    missing_required = _missing_required_columns(raw_df)
    if missing_required:
        run_purchases_validation(
            purchaseline_df=_empty_purchases_df(),
            missing_prefixes=[],
            output_dir=reports_dir,
            tolerance=tolerance,
            missing_required_columns=missing_required,
        )
        raise ValueError(
            "Purchases required columns are missing: "
            + ", ".join(missing_required)
            + ". Validation report generated at reports/purchases_qa_report.csv"
        )

    transformed = transform_purchases(
        purchases_raw=raw_df,
        map_product_category=purchases_input.get("map_product_category"),
        map_typeachat=purchases_input.get("map_typeachat"),
    )

    validation = run_purchases_validation(
        purchaseline_df=transformed.purchaseline,
        missing_prefixes=transformed.missing_prefixes,
        output_dir=reports_dir,
        tolerance=tolerance,
        missing_required_columns=[],
    )

    if validation.has_errors:
        invalid_rows = int(validation.invalid_row_mask.sum())
        if not drop_invalid_purchase_rows:
            raise ValueError(
                "Purchases validation contains ERROR checks. "
                "Set drop_invalid_purchase_rows=True (or --drop-invalid-purchases-rows) "
                "to quarantine/drop invalid rows and continue build. "
                f"Invalid rows: {invalid_rows}."
            )

        transformed.purchaseline = transformed.purchaseline.loc[~validation.invalid_row_mask].reset_index(drop=True)
        print(f"Dropped {invalid_rows} invalid purchases rows and continued warehouse build.")

    generate_profile_markdown(
        transformed.purchaseline,
        output_dir=reports_dir,
        filename="purchases_profile.md",
        title="Purchases Data Profile",
    )
    return transformed, source_used


def build_warehouse(
    excel_path: Path = EXCEL_PATH,
    duckdb_path: Path = DUCKDB_PATH,
    reports_dir: Path = REPORTS_DIR,
    tolerance: float = QA_TOLERANCE,
    purchases_source: str = "auto",
    purchases_excel_path: Path = PURCHASES_EXCEL_PATH,
    purchases_csv_path: Path = PURCHASES_CSV_PATH,
    drop_invalid_purchase_rows: bool = False,
    margin_missing_cost_as_zero: bool = MARGIN_MISSING_COST_AS_ZERO,
) -> dict[str, int]:
    if not excel_path.exists():
        raise FileNotFoundError(f"Excel file not found: {excel_path}")

    sales_data = read_sales_excel_inputs(excel_path)
    sales_transformed = transform_sales(
        sales_raw=sales_data["sales_raw"],
        map_product_category=sales_data["map_product_category"],
        map_typevente=sales_data["map_typevente"],
        map_wilaya=sales_data["map_wilaya"],
    )

    run_qa(
        salesline_df=sales_transformed.salesline,
        missing_prefixes=sales_transformed.missing_prefixes,
        output_dir=reports_dir,
        tolerance=tolerance,
    )
    generate_profile_markdown(sales_transformed.salesline, output_dir=reports_dir)

    purchases_transformed, source_used = _build_purchases_transform(
        purchases_source=purchases_source,
        purchases_excel_path=purchases_excel_path,
        purchases_csv_path=purchases_csv_path,
        reports_dir=reports_dir,
        tolerance=tolerance,
        drop_invalid_purchase_rows=drop_invalid_purchase_rows,
    )

    tables = _build_tables(
        sales_result=sales_transformed,
        purchases_result=purchases_transformed,
        margin_missing_cost_as_zero=margin_missing_cost_as_zero,
        tolerance=tolerance,
    )

    run_inventory_event_validation(
        inventory_df=tables["fact_inventory_events"],
        output_dir=reports_dir,
        tolerance=tolerance,
    )

    _write_to_duckdb(tables, duckdb_path)

    counts = {name: len(df) for name, df in tables.items()}
    print(f"Warehouse file: {duckdb_path}")
    print(f"Purchases source used: {source_used}")
    for name, count in counts.items():
        print(f"{name}: {count} rows")
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Build/rebuild DuckDB warehouse from Sales + Purchases inputs.")
    parser.add_argument("--build", action="store_true", help="Build warehouse and reports.")
    parser.add_argument("--excel", type=Path, default=EXCEL_PATH, help="Sales Excel path.")
    parser.add_argument("--db", type=Path, default=DUCKDB_PATH, help="DuckDB output path.")
    parser.add_argument("--reports", type=Path, default=REPORTS_DIR, help="Reports output folder.")
    parser.add_argument("--tolerance", type=float, default=QA_TOLERANCE, help="QA tolerance for TTC checks.")
    parser.add_argument(
        "--purchases-source",
        choices=["auto", "excel", "csv", "none"],
        default="auto",
        help="Purchases input source selection.",
    )
    parser.add_argument(
        "--purchases-excel",
        type=Path,
        default=PURCHASES_EXCEL_PATH,
        help="Purchases Excel path (used in auto/excel mode).",
    )
    parser.add_argument(
        "--purchases-csv",
        type=Path,
        default=PURCHASES_CSV_PATH,
        help="Purchases CSV path (used in auto/csv mode).",
    )
    parser.add_argument(
        "--drop-invalid-purchases-rows",
        action="store_true",
        help="If set, quarantine/drop invalid purchases rows and continue build.",
    )
    parser.add_argument(
        "--margin-missing-cost-as-zero",
        action="store_true",
        help="If set, missing purchase history uses cost=0 instead of NULL margins.",
    )
    args = parser.parse_args()

    if not args.build:
        parser.print_help()
        return

    build_warehouse(
        excel_path=args.excel,
        duckdb_path=args.db,
        reports_dir=args.reports,
        tolerance=args.tolerance,
        purchases_source=args.purchases_source,
        purchases_excel_path=args.purchases_excel,
        purchases_csv_path=args.purchases_csv,
        drop_invalid_purchase_rows=args.drop_invalid_purchases_rows,
        margin_missing_cost_as_zero=args.margin_missing_cost_as_zero or MARGIN_MISSING_COST_AS_ZERO,
    )


if __name__ == "__main__":
    main()
