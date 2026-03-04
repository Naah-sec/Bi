from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any

import pandas as pd

from src.config import DEFAULT_PRODUCT_CATEGORY_MAP, LEGAL_FORMS


def _normalize_key(text: str) -> str:
    value = unicodedata.normalize("NFKD", str(text))
    value = value.encode("ascii", "ignore").decode("ascii")
    return "".join(ch for ch in value.lower() if ch.isalnum())


def _resolve_column(df: pd.DataFrame, logical_name: str) -> str:
    target = _normalize_key(logical_name)
    for col in df.columns:
        if _normalize_key(col) == target:
            return col
    raise KeyError(f"Missing required column: {logical_name}. Available columns: {list(df.columns)}")


def _resolve_column_any(df: pd.DataFrame, logical_names: list[str]) -> str:
    errors: list[str] = []
    for name in logical_names:
        try:
            return _resolve_column(df, name)
        except KeyError as exc:
            errors.append(str(exc))
    raise KeyError("; ".join(errors))


def parse_french_number(value: Any) -> float | None:
    if pd.isna(value):
        return None
    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip()
    if not text:
        return None

    text = text.replace("\u00a0", "").replace(" ", "").replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def parse_french_number_series(series: pd.Series) -> pd.Series:
    return series.map(parse_french_number).astype("float64")


def parse_date_series(series: pd.Series) -> pd.Series:
    parsed = pd.to_datetime(series, format="%Y-%m-%d", errors="coerce")
    if parsed.notna().all():
        return parsed.dt.date

    mask = parsed.isna()
    parsed.loc[mask] = pd.to_datetime(series[mask], format="%Y-%m-%d %H:%M:%S", errors="coerce")
    mask = parsed.isna()
    parsed.loc[mask] = pd.to_datetime(series[mask], errors="coerce", dayfirst=True)
    return parsed.dt.date


def extract_typevente_code(num_cmd: Any) -> str | None:
    if pd.isna(num_cmd):
        return None
    text = str(num_cmd).strip()
    if not text:
        return None
    return text.split("/", 1)[0].strip().upper()


def extract_typeachat_code(num_cmd: Any) -> str | None:
    return extract_typevente_code(num_cmd)


def extract_order_number(num_cmd: Any) -> str | None:
    if pd.isna(num_cmd):
        return None
    text = str(num_cmd).strip()
    if "/" not in text:
        return None
    right = text.split("/", 1)[1].strip()
    return right or None


def _split_legal_form_and_name(value: Any) -> tuple[str, str]:
    if pd.isna(value):
        return "UNKNOWN", ""

    text = re.sub(r"\s+", " ", str(value).strip())
    if not text:
        return "UNKNOWN", ""

    first_token = text.split(" ", 1)[0].upper()
    if first_token in LEGAL_FORMS:
        remainder = text[len(first_token) :].strip()
        return first_token, remainder
    return "UNKNOWN", text


def split_legal_form_and_customer(client_value: Any) -> tuple[str, str]:
    return _split_legal_form_and_name(client_value)


def split_legal_form_and_supplier(supplier_value: Any) -> tuple[str, str]:
    return _split_legal_form_and_name(supplier_value)


def extract_product_prefix(product_code: Any) -> str | None:
    if pd.isna(product_code):
        return None
    text = str(product_code).strip()
    if not text:
        return None
    return text.split(".", 1)[0].strip().upper()


def _strip_and_collapse(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def extract_wilaya(address_value: Any) -> str:
    if pd.isna(address_value):
        return "UNKNOWN"
    text = str(address_value)
    if not text.strip():
        return "UNKNOWN"
    token = text.rsplit(",", 1)[-1]
    token = _strip_and_collapse(token)
    return token if token else "UNKNOWN"


def _normalize_match_key(text: str) -> str:
    value = unicodedata.normalize("NFKD", text)
    value = value.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", value.lower()).strip()


def build_product_category_map(map_df: pd.DataFrame | None) -> dict[str, str]:
    mapping = {k.upper(): v for k, v in DEFAULT_PRODUCT_CATEGORY_MAP.items()}
    if map_df is None or map_df.empty:
        return mapping

    col_prefix = _resolve_column(map_df, "ProductPrefix")
    col_category = _resolve_column(map_df, "Category")
    for _, row in map_df.iterrows():
        prefix = str(row[col_prefix]).strip().upper() if not pd.isna(row[col_prefix]) else ""
        category = str(row[col_category]).strip() if not pd.isna(row[col_category]) else ""
        if prefix:
            mapping[prefix] = category or "Unknown"
    return mapping


def build_typevente_label_map(map_df: pd.DataFrame | None) -> dict[str, str]:
    if map_df is None or map_df.empty:
        return {}

    col_code = _resolve_column(map_df, "TypeVenteCode")
    col_label = _resolve_column(map_df, "TypeVenteLabel")
    out: dict[str, str] = {}
    for _, row in map_df.iterrows():
        code = str(row[col_code]).strip().upper() if not pd.isna(row[col_code]) else ""
        label = str(row[col_label]).strip() if not pd.isna(row[col_label]) else ""
        if code:
            out[code] = label
    return out


def build_typeachat_label_map(map_df: pd.DataFrame | None) -> dict[str, str]:
    if map_df is None or map_df.empty:
        return {}

    col_code = _resolve_column(map_df, "TypeAchatCode")
    col_label = _resolve_column(map_df, "TypeAchatLabel")
    out: dict[str, str] = {}
    for _, row in map_df.iterrows():
        code = str(row[col_code]).strip().upper() if not pd.isna(row[col_code]) else ""
        label = str(row[col_label]).strip() if not pd.isna(row[col_label]) else ""
        if code:
            out[code] = label
    return out


def build_wilaya_canonical_map(map_df: pd.DataFrame | None) -> dict[str, str]:
    if map_df is None or map_df.empty:
        return {}

    col_wilaya = _resolve_column(map_df, "Wilaya")
    mapping: dict[str, str] = {}
    for val in map_df[col_wilaya].dropna():
        cleaned = _strip_and_collapse(str(val))
        if cleaned:
            mapping[_normalize_match_key(cleaned)] = cleaned
    return mapping


def standardize_wilaya(value: str, canonical_map: dict[str, str]) -> str:
    if not value or value == "UNKNOWN":
        return "UNKNOWN"
    key = _normalize_match_key(value)
    if key in canonical_map:
        return canonical_map[key]
    return value


@dataclass
class TransformResult:
    salesline: pd.DataFrame
    missing_prefixes: list[str]
    typevente_label_map: dict[str, str]


@dataclass
class PurchasesTransformResult:
    purchaseline: pd.DataFrame
    missing_prefixes: list[str]
    typeachat_label_map: dict[str, str]


def _drop_empty_sales_rows(df: pd.DataFrame) -> pd.DataFrame:
    empty_mask = (
        df["raw_num_cmd"].eq("")
        & df["client_raw"].eq("")
        & df["address"].eq("")
        & df["product_code"].eq("")
        & df["product_name"].eq("")
        & df["date_cmd"].isna()
        & df["qty"].isna()
        & df["amount_ht"].isna()
        & df["tax_amount"].isna()
        & df["amount_ttc"].isna()
    )
    return df.loc[~empty_mask].copy().reset_index(drop=True)


def _drop_empty_purchases_rows(df: pd.DataFrame) -> pd.DataFrame:
    empty_mask = (
        df["raw_num_cmd"].eq("")
        & df["supplier_raw"].eq("")
        & df["product_code"].eq("")
        & df["product_name"].eq("")
        & df["date_cmd"].isna()
        & df["qty"].isna()
        & df["amount_ht"].isna()
        & df["tax_amount"].isna()
        & df["amount_ttc"].isna()
    )
    return df.loc[~empty_mask].copy().reset_index(drop=True)


def transform_sales(
    sales_raw: pd.DataFrame,
    map_product_category: pd.DataFrame | None = None,
    map_typevente: pd.DataFrame | None = None,
    map_wilaya: pd.DataFrame | None = None,
) -> TransformResult:
    if sales_raw is None or sales_raw.empty:
        raise ValueError("sales_raw is empty")

    col_num_cmd = _resolve_column(sales_raw, "Num.CMD")
    col_date = _resolve_column(sales_raw, "Date.CMD")
    col_client = _resolve_column(sales_raw, "Client")
    col_address = _resolve_column(sales_raw, "Adresse")
    col_product_code = _resolve_column(sales_raw, "Code Produit")
    col_product_name = _resolve_column(sales_raw, "Produit")
    col_qty = _resolve_column_any(sales_raw, ["Qte", "Qt", "Qty", "QTY", "Quantite"])
    col_ht = _resolve_column(sales_raw, "Montant HT")
    col_tax = _resolve_column(sales_raw, "Taxe")
    col_ttc = _resolve_column(sales_raw, "Montant TTC")

    df = pd.DataFrame(
        {
            "raw_num_cmd": sales_raw[col_num_cmd].fillna("").astype(str).str.strip(),
            "date_cmd": parse_date_series(sales_raw[col_date]),
            "client_raw": sales_raw[col_client].fillna("").astype(str).str.strip(),
            "address": sales_raw[col_address].fillna("").astype(str).str.strip(),
            "product_code": sales_raw[col_product_code].fillna("").astype(str).str.strip(),
            "product_name": sales_raw[col_product_name].fillna("").astype(str).str.strip(),
            "qty": parse_french_number_series(sales_raw[col_qty]),
            "amount_ht": parse_french_number_series(sales_raw[col_ht]),
            "tax_amount": parse_french_number_series(sales_raw[col_tax]),
            "amount_ttc": parse_french_number_series(sales_raw[col_ttc]),
        }
    )
    df = _drop_empty_sales_rows(df)

    df["typevente_code"] = df["raw_num_cmd"].map(extract_typevente_code)
    df["order_number_optional"] = df["raw_num_cmd"].map(extract_order_number)

    legal_customer = df["client_raw"].map(split_legal_form_and_customer)
    df["legal_form"] = legal_customer.map(lambda x: x[0])
    df["customer_name"] = legal_customer.map(lambda x: x[1] if x[1] else "UNKNOWN")

    canonical_wilaya_map = build_wilaya_canonical_map(map_wilaya)
    df["wilaya"] = df["address"].map(extract_wilaya).map(lambda x: standardize_wilaya(x, canonical_wilaya_map))

    df["product_prefix"] = df["product_code"].map(extract_product_prefix)
    category_map = build_product_category_map(map_product_category)
    df["category"] = df["product_prefix"].map(lambda x: category_map.get(x or "", "Unknown"))

    missing_prefixes = sorted(df.loc[df["category"] == "Unknown", "product_prefix"].dropna().unique().tolist())

    df["year"] = pd.to_datetime(df["date_cmd"], errors="coerce").dt.year.astype("Int64")
    df["month_no"] = pd.to_datetime(df["date_cmd"], errors="coerce").dt.month.astype("Int64")
    df["month_name"] = pd.to_datetime(df["date_cmd"], errors="coerce").dt.strftime("%B")
    df["year_month"] = pd.to_datetime(df["date_cmd"], errors="coerce").dt.strftime("%Y-%m")
    df["date_key"] = pd.to_datetime(df["date_cmd"], errors="coerce").dt.strftime("%Y%m%d")
    df["date_key"] = pd.to_numeric(df["date_key"], errors="coerce").astype("Int64")

    df["qty"] = df["qty"].astype("float64")
    df["amount_ht"] = df["amount_ht"].astype("float64")
    df["tax_amount"] = df["tax_amount"].astype("float64")
    df["amount_ttc"] = df["amount_ttc"].astype("float64")

    typevente_label_map = build_typevente_label_map(map_typevente)
    return TransformResult(salesline=df, missing_prefixes=missing_prefixes, typevente_label_map=typevente_label_map)


def transform_purchases(
    purchases_raw: pd.DataFrame,
    map_product_category: pd.DataFrame | None = None,
    map_typeachat: pd.DataFrame | None = None,
) -> PurchasesTransformResult:
    if purchases_raw is None or purchases_raw.empty:
        raise ValueError("purchases_raw is empty")

    col_num_cmd = _resolve_column(purchases_raw, "Num.CMD")
    col_date = _resolve_column(purchases_raw, "Date.CMD")
    col_supplier = _resolve_column_any(purchases_raw, ["Fournisseur", "Supplier", "Vendor"])
    col_product_code = _resolve_column(purchases_raw, "Code Produit")
    col_product_name = _resolve_column(purchases_raw, "Produit")
    col_qty = _resolve_column_any(purchases_raw, ["Qte", "Qt", "Qty", "QTY", "Quantite"])
    col_ht = _resolve_column(purchases_raw, "Montant HT")
    col_tax = _resolve_column(purchases_raw, "Taxe")
    col_ttc = _resolve_column(purchases_raw, "Montant TTC")

    df = pd.DataFrame(
        {
            "raw_num_cmd": purchases_raw[col_num_cmd].fillna("").astype(str).str.strip(),
            "date_cmd": parse_date_series(purchases_raw[col_date]),
            "supplier_raw": purchases_raw[col_supplier].fillna("").astype(str).str.strip(),
            "product_code": purchases_raw[col_product_code].fillna("").astype(str).str.strip(),
            "product_name": purchases_raw[col_product_name].fillna("").astype(str).str.strip(),
            "qty": parse_french_number_series(purchases_raw[col_qty]),
            "amount_ht": parse_french_number_series(purchases_raw[col_ht]),
            "tax_amount": parse_french_number_series(purchases_raw[col_tax]),
            "amount_ttc": parse_french_number_series(purchases_raw[col_ttc]),
        }
    )
    df = _drop_empty_purchases_rows(df)

    df["typeachat_code"] = df["raw_num_cmd"].map(extract_typeachat_code)
    df["order_number_optional"] = df["raw_num_cmd"].map(extract_order_number)

    legal_supplier = df["supplier_raw"].map(split_legal_form_and_supplier)
    df["supplier_legal_form"] = legal_supplier.map(lambda x: x[0])
    df["supplier_name"] = legal_supplier.map(lambda x: x[1] if x[1] else "UNKNOWN")

    df["product_prefix"] = df["product_code"].map(extract_product_prefix)
    category_map = build_product_category_map(map_product_category)
    df["category"] = df["product_prefix"].map(lambda x: category_map.get(x or "", "Unknown"))

    missing_prefixes = sorted(df.loc[df["category"] == "Unknown", "product_prefix"].dropna().unique().tolist())

    df["year"] = pd.to_datetime(df["date_cmd"], errors="coerce").dt.year.astype("Int64")
    df["month_no"] = pd.to_datetime(df["date_cmd"], errors="coerce").dt.month.astype("Int64")
    df["month_name"] = pd.to_datetime(df["date_cmd"], errors="coerce").dt.strftime("%B")
    df["year_month"] = pd.to_datetime(df["date_cmd"], errors="coerce").dt.strftime("%Y-%m")
    df["date_key"] = pd.to_datetime(df["date_cmd"], errors="coerce").dt.strftime("%Y%m%d")
    df["date_key"] = pd.to_numeric(df["date_key"], errors="coerce").astype("Int64")

    df["qty"] = df["qty"].astype("float64")
    df["amount_ht"] = df["amount_ht"].astype("float64")
    df["tax_amount"] = df["tax_amount"].astype("float64")
    df["amount_ttc"] = df["amount_ttc"].astype("float64")

    typeachat_label_map = build_typeachat_label_map(map_typeachat)
    return PurchasesTransformResult(
        purchaseline=df,
        missing_prefixes=missing_prefixes,
        typeachat_label_map=typeachat_label_map,
    )
