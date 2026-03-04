from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


@dataclass
class PurchasesValidationResult:
    report: pd.DataFrame
    details: pd.DataFrame
    invalid_row_mask: pd.Series
    has_errors: bool
    has_warnings: bool
    quarantine_path: Path | None


@dataclass
class InventoryValidationResult:
    report: pd.DataFrame
    details: pd.DataFrame
    has_errors: bool


def _write_report_markdown(report_df: pd.DataFrame, output_path: Path, title: str) -> Path:
    lines = [f"# {title}", "", f"- Checks: {len(report_df)}", "", "| check | severity | status | failed_rows | details |", "|---|---|---|---:|---|"]
    for _, row in report_df.iterrows():
        lines.append(
            f"| {row['check']} | {row['severity']} | {row['status']} | {row['failed_rows']} | {row['details']} |"
        )
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def run_qa(
    salesline_df: pd.DataFrame,
    missing_prefixes: list[str],
    output_dir: Path,
    tolerance: float = 0.01,
    output_filename: str = "qa_report.csv",
    markdown_filename: str = "qa_report.md",
) -> pd.DataFrame:
    output_dir.mkdir(parents=True, exist_ok=True)

    amount_nulls = int(
        salesline_df[["amount_ht", "tax_amount", "amount_ttc"]].isna().any(axis=1).sum()
    )
    qty_invalid = int((salesline_df["qty"].isna() | (salesline_df["qty"] <= 0)).sum())
    date_nulls = int(salesline_df["date_cmd"].isna().sum())

    gap = (salesline_df["amount_ttc"] - (salesline_df["amount_ht"] + salesline_df["tax_amount"])).abs()
    ttc_mismatch = int((gap > tolerance).sum())

    missing_count = int((salesline_df["category"] == "Unknown").sum())

    report = pd.DataFrame(
        [
            {
                "check": "Numeric parsing for amounts",
                "severity": "ERROR",
                "status": "PASS" if amount_nulls == 0 else "FAIL",
                "failed_rows": amount_nulls,
                "details": "amount_ht, tax_amount, amount_ttc should not be null",
            },
            {
                "check": "qty > 0",
                "severity": "ERROR",
                "status": "PASS" if qty_invalid == 0 else "FAIL",
                "failed_rows": qty_invalid,
                "details": "qty must be strictly positive",
            },
            {
                "check": "date_cmd non-null",
                "severity": "ERROR",
                "status": "PASS" if date_nulls == 0 else "FAIL",
                "failed_rows": date_nulls,
                "details": "Date.CMD must be parseable as date",
            },
            {
                "check": "amount_ttc ~= amount_ht + tax_amount",
                "severity": "ERROR",
                "status": "PASS" if ttc_mismatch == 0 else "FAIL",
                "failed_rows": ttc_mismatch,
                "details": f"tolerance={tolerance}",
            },
            {
                "check": "Missing category mappings",
                "severity": "WARN",
                "status": "PASS" if missing_count == 0 else "WARN",
                "failed_rows": missing_count,
                "details": "Missing prefixes: " + (", ".join(missing_prefixes) if missing_prefixes else "None"),
            },
        ]
    )

    report_path = output_dir / output_filename
    report.to_csv(report_path, index=False, encoding="utf-8")
    _write_report_markdown(report, output_dir / markdown_filename, "Sales QA Report")

    print("QA SUMMARY")
    print(report.to_string(index=False))
    print(f"\nQA report: {report_path}")
    return report


def run_purchases_validation(
    purchaseline_df: pd.DataFrame,
    missing_prefixes: list[str],
    output_dir: Path,
    tolerance: float = 0.01,
    missing_required_columns: list[str] | None = None,
) -> PurchasesValidationResult:
    output_dir.mkdir(parents=True, exist_ok=True)

    missing_required_columns = missing_required_columns or []
    required_columns_failed_rows = len(purchaseline_df) if missing_required_columns else 0

    amount_invalid = purchaseline_df[["amount_ht", "tax_amount", "amount_ttc"]].isna().any(axis=1)
    qty_invalid = purchaseline_df["qty"].isna() | (purchaseline_df["qty"] <= 0)
    date_invalid = purchaseline_df["date_cmd"].isna()
    gap = (purchaseline_df["amount_ttc"] - (purchaseline_df["amount_ht"] + purchaseline_df["tax_amount"]))
    ttc_mismatch = gap.abs() > tolerance

    typeachat_missing = purchaseline_df["typeachat_code"].isna() | (
        purchaseline_df["typeachat_code"].astype(str).str.strip() == ""
    )
    prefix_missing = purchaseline_df["product_prefix"].isna() | (
        purchaseline_df["product_prefix"].astype(str).str.strip() == ""
    )
    missing_category = purchaseline_df["category"].fillna("Unknown").eq("Unknown")

    invalid_row_mask = amount_invalid | qty_invalid | date_invalid | ttc_mismatch

    report = pd.DataFrame(
        [
            {
                "check": "Required columns",
                "severity": "ERROR",
                "status": "PASS" if not missing_required_columns else "FAIL",
                "failed_rows": required_columns_failed_rows,
                "details": "Missing: " + (", ".join(missing_required_columns) if missing_required_columns else "None"),
            },
            {
                "check": "Date.CMD parseable",
                "severity": "ERROR",
                "status": "PASS" if int(date_invalid.sum()) == 0 else "FAIL",
                "failed_rows": int(date_invalid.sum()),
                "details": "Date.CMD must be parseable as date",
            },
            {
                "check": "QTY > 0",
                "severity": "ERROR",
                "status": "PASS" if int(qty_invalid.sum()) == 0 else "FAIL",
                "failed_rows": int(qty_invalid.sum()),
                "details": "QTY must be positive",
            },
            {
                "check": "Numeric amounts",
                "severity": "ERROR",
                "status": "PASS" if int(amount_invalid.sum()) == 0 else "FAIL",
                "failed_rows": int(amount_invalid.sum()),
                "details": "Montant HT/Taxe/Montant TTC must be numeric",
            },
            {
                "check": "Montant TTC ~= Montant HT + Taxe",
                "severity": "ERROR",
                "status": "PASS" if int(ttc_mismatch.sum()) == 0 else "FAIL",
                "failed_rows": int(ttc_mismatch.sum()),
                "details": f"tolerance={tolerance}",
            },
            {
                "check": "TypeAchatCode parse",
                "severity": "WARN",
                "status": "PASS" if int(typeachat_missing.sum()) == 0 else "WARN",
                "failed_rows": int(typeachat_missing.sum()),
                "details": "TypeAchatCode parsed from Num.CMD",
            },
            {
                "check": "ProductPrefix parse",
                "severity": "WARN",
                "status": "PASS" if int(prefix_missing.sum()) == 0 else "WARN",
                "failed_rows": int(prefix_missing.sum()),
                "details": "ProductPrefix parsed from Code Produit",
            },
            {
                "check": "Category mapping coverage",
                "severity": "WARN",
                "status": "PASS" if int(missing_category.sum()) == 0 else "WARN",
                "failed_rows": int(missing_category.sum()),
                "details": "Missing prefixes: " + (", ".join(missing_prefixes) if missing_prefixes else "None"),
            },
        ]
    )

    details = purchaseline_df.copy()
    details["invalid_date"] = date_invalid
    details["invalid_qty"] = qty_invalid
    details["invalid_amount"] = amount_invalid
    details["invalid_ttc_equation"] = ttc_mismatch
    details["warn_typeachat_missing"] = typeachat_missing
    details["warn_prefix_missing"] = prefix_missing
    details["warn_category_unknown"] = missing_category
    details = details[
        details[
            [
                "invalid_date",
                "invalid_qty",
                "invalid_amount",
                "invalid_ttc_equation",
                "warn_typeachat_missing",
                "warn_prefix_missing",
                "warn_category_unknown",
            ]
        ].any(axis=1)
    ].copy()

    report_path = output_dir / "purchases_qa_report.csv"
    details_path = output_dir / "purchases_qa_details.csv"
    markdown_path = output_dir / "purchases_qa_report.md"

    report.to_csv(report_path, index=False, encoding="utf-8")
    details.to_csv(details_path, index=False, encoding="utf-8")
    _write_report_markdown(report, markdown_path, "Purchases QA Report")

    quarantine_path: Path | None = None
    if int(invalid_row_mask.sum()) > 0:
        quarantine_path = output_dir / "purchases_quarantine.csv"
        purchaseline_df[invalid_row_mask].to_csv(quarantine_path, index=False, encoding="utf-8")

    has_errors = bool((report["severity"].eq("ERROR") & report["status"].eq("FAIL")).any())
    has_warnings = bool((report["severity"].eq("WARN") & report["status"].eq("WARN")).any())

    print("PURCHASES QA SUMMARY")
    print(report.to_string(index=False))
    print(f"\nPurchases QA report: {report_path}")

    return PurchasesValidationResult(
        report=report,
        details=details,
        invalid_row_mask=invalid_row_mask,
        has_errors=has_errors,
        has_warnings=has_warnings,
        quarantine_path=quarantine_path,
    )


def run_inventory_event_validation(
    inventory_df: pd.DataFrame,
    output_dir: Path,
    tolerance: float = 0.01,
) -> InventoryValidationResult:
    output_dir.mkdir(parents=True, exist_ok=True)

    if inventory_df is None or inventory_df.empty:
        report = pd.DataFrame(
            [
                {
                    "check": "Inventory events present",
                    "severity": "WARN",
                    "status": "WARN",
                    "failed_rows": 0,
                    "details": "No inventory events available",
                }
            ]
        )
        details = pd.DataFrame()
        report.to_csv(output_dir / "inventory_qa_report.csv", index=False, encoding="utf-8")
        details.to_csv(output_dir / "inventory_qa_details.csv", index=False, encoding="utf-8")
        _write_report_markdown(report, output_dir / "inventory_qa_report.md", "Inventory QA Report")
        return InventoryValidationResult(report=report, details=details, has_errors=False)

    purchase_mask = inventory_df["event_type"].eq("PURCHASE")
    sale_mask = inventory_df["event_type"].eq("SALE")

    purchase_qty_invalid = purchase_mask & (
        inventory_df["purchase_qty"].isna() | (inventory_df["purchase_qty"] <= 0)
    )
    sale_qty_invalid = sale_mask & (inventory_df["sale_qty"].isna() | (inventory_df["sale_qty"] <= 0))

    sale_exceeds_stock = sale_mask & (
        inventory_df["sale_qty"].fillna(0.0) > (inventory_df["stock_qty_before"].fillna(0.0) + tolerance)
    )

    purchase_value_mismatch = purchase_mask & (
        (
            inventory_df["purchase_value"]
            - (inventory_df["purchase_qty"] * inventory_df["purchase_unit_price"])
        )
        .abs()
        .fillna(0.0)
        > tolerance
    )

    revenue_mismatch = sale_mask & (
        (
            inventory_df["sale_revenue"]
            - (inventory_df["sale_qty"] * inventory_df["sale_unit_price"])
        )
        .abs()
        .fillna(0.0)
        > tolerance
    )

    excluded_from_margin = sale_mask & (~inventory_df["valid_for_margin"].fillna(False))

    report = pd.DataFrame(
        [
            {
                "check": "sale_qty <= stock_qty_before",
                "severity": "ERROR",
                "status": "PASS" if int(sale_exceeds_stock.sum()) == 0 else "FAIL",
                "failed_rows": int(sale_exceeds_stock.sum()),
                "details": "Sale quantity cannot exceed available stock",
            },
            {
                "check": "purchase_qty > 0",
                "severity": "ERROR",
                "status": "PASS" if int(purchase_qty_invalid.sum()) == 0 else "FAIL",
                "failed_rows": int(purchase_qty_invalid.sum()),
                "details": "Purchase quantity must be > 0",
            },
            {
                "check": "sale_qty > 0",
                "severity": "ERROR",
                "status": "PASS" if int(sale_qty_invalid.sum()) == 0 else "FAIL",
                "failed_rows": int(sale_qty_invalid.sum()),
                "details": "Sale quantity must be > 0",
            },
            {
                "check": "revenue = sale_unit_price * sale_qty",
                "severity": "ERROR",
                "status": "PASS" if int(revenue_mismatch.sum()) == 0 else "FAIL",
                "failed_rows": int(revenue_mismatch.sum()),
                "details": f"tolerance={tolerance}",
            },
            {
                "check": "purchase_value = purchase_unit_price * purchase_qty",
                "severity": "ERROR",
                "status": "PASS" if int(purchase_value_mismatch.sum()) == 0 else "FAIL",
                "failed_rows": int(purchase_value_mismatch.sum()),
                "details": f"tolerance={tolerance}",
            },
            {
                "check": "Rows excluded from margin calculation",
                "severity": "WARN",
                "status": "PASS" if int(excluded_from_margin.sum()) == 0 else "WARN",
                "failed_rows": int(excluded_from_margin.sum()),
                "details": "Invalid rows are flagged and excluded from gross margin aggregation",
            },
        ]
    )

    details = inventory_df[
        purchase_qty_invalid
        | sale_qty_invalid
        | sale_exceeds_stock
        | purchase_value_mismatch
        | revenue_mismatch
        | excluded_from_margin
        | inventory_df["error_code"].notna()
    ].copy()

    report.to_csv(output_dir / "inventory_qa_report.csv", index=False, encoding="utf-8")
    details.to_csv(output_dir / "inventory_qa_details.csv", index=False, encoding="utf-8")
    _write_report_markdown(report, output_dir / "inventory_qa_report.md", "Inventory QA Report")

    has_errors = bool((report["severity"].eq("ERROR") & report["status"].eq("FAIL")).any())

    print("INVENTORY QA SUMMARY")
    print(report.to_string(index=False))
    print(f"\nInventory QA report: {output_dir / 'inventory_qa_report.csv'}")

    return InventoryValidationResult(report=report, details=details, has_errors=has_errors)


def generate_profile_markdown(
    dataset_df: pd.DataFrame,
    output_dir: Path,
    filename: str = "profile.md",
    title: str = "Data Profile",
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)

    row_count = len(dataset_df)
    col_count = len(dataset_df.columns)

    profile_rows: list[dict[str, str | int | float]] = []
    for col in dataset_df.columns:
        null_count = int(dataset_df[col].isna().sum())
        null_rate = (null_count / row_count * 100) if row_count else 0.0
        unique_count = int(dataset_df[col].nunique(dropna=True))
        profile_rows.append(
            {
                "column": col,
                "dtype": str(dataset_df[col].dtype),
                "null_count": null_count,
                "null_rate_pct": round(null_rate, 2),
                "unique_count": unique_count,
            }
        )

    profile_df = pd.DataFrame(profile_rows).sort_values("column")

    lines = [
        f"# {title}",
        "",
        f"- Row count: {row_count}",
        f"- Column count: {col_count}",
        "",
        "## Column Statistics",
        "",
        "| column | dtype | null_count | null_rate_pct | unique_count |",
        "|---|---|---:|---:|---:|",
    ]

    for _, row in profile_df.iterrows():
        lines.append(
            f"| {row['column']} | {row['dtype']} | {row['null_count']} | {row['null_rate_pct']} | {row['unique_count']} |"
        )

    profile_path = output_dir / filename
    profile_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Profile report: {profile_path}")
    return profile_path
