from __future__ import annotations

import argparse
from pathlib import Path
import sys
import unicodedata

import pandas as pd


def normalize_name(name: str) -> str:
    text = unicodedata.normalize("NFKD", str(name))
    text = text.encode("ascii", "ignore").decode("ascii")
    return "".join(ch for ch in text.lower() if ch.isalnum())


def find_column(df: pd.DataFrame, logical_name: str) -> str:
    target = normalize_name(logical_name)
    for col in df.columns:
        if normalize_name(col) == target:
            return col
    raise KeyError(f"Column not found: {logical_name}. Available: {list(df.columns)}")


def to_number(series: pd.Series) -> pd.Series:
    cleaned = (
        series.astype(str)
        .str.replace("\u00a0", "", regex=False)
        .str.replace(" ", "", regex=False)
        .str.replace(",", ".", regex=False)
    )
    return pd.to_numeric(cleaned, errors="coerce")


def parse_dates(series: pd.Series) -> pd.Series:
    parsed = pd.to_datetime(series, format="%Y-%m-%d", errors="coerce")
    if parsed.notna().all():
        return parsed

    mask = parsed.isna()
    parsed.loc[mask] = pd.to_datetime(series[mask], format="%Y-%m-%d %H:%M:%S", errors="coerce")
    if parsed.notna().all():
        return parsed

    mask = parsed.isna()
    parsed.loc[mask] = pd.to_datetime(series[mask], errors="coerce")
    return parsed


def run_checks(excel_path: Path, tolerance: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    sales = pd.read_excel(excel_path, sheet_name="SalesRaw", dtype=str)
    map_product = pd.read_excel(excel_path, sheet_name="Map_ProductCategory", dtype=str)

    col_date = find_column(sales, "Date.CMD")
    col_qty = find_column(sales, "Qte")
    col_ht = find_column(sales, "Montant HT")
    col_taxe = find_column(sales, "Taxe")
    col_ttc = find_column(sales, "Montant TTC")
    col_code = find_column(sales, "Code Produit")

    map_prefix_col = find_column(map_product, "ProductPrefix")

    sales["date_parsed"] = parse_dates(sales[col_date])
    sales["qty_num"] = to_number(sales[col_qty])
    sales["ht_num"] = to_number(sales[col_ht])
    sales["taxe_num"] = to_number(sales[col_taxe])
    sales["ttc_num"] = to_number(sales[col_ttc])

    sales["calc_gap"] = (sales["ttc_num"] - (sales["ht_num"] + sales["taxe_num"])).abs()
    invalid_ttc = sales["calc_gap"] > tolerance
    null_dates = sales["date_parsed"].isna()
    invalid_qty = sales["qty_num"].isna() | (sales["qty_num"] <= 0)

    sales["ProductPrefix"] = sales[col_code].astype(str).str.split(".").str[0].str.strip()
    mapped_prefixes = set(map_product[map_prefix_col].astype(str).str.strip().dropna().unique())
    missing_prefix = ~sales["ProductPrefix"].isin(mapped_prefixes)
    missing_prefix_values = sorted(sales.loc[missing_prefix, "ProductPrefix"].dropna().unique().tolist())

    rows = [
        {
            "check": "MontantTTC ~= MontantHT + Taxe",
            "status": "PASS" if int(invalid_ttc.sum()) == 0 else "FAIL",
            "failed_rows": int(invalid_ttc.sum()),
            "details": f"tolerance={tolerance}",
        },
        {
            "check": "No null dates",
            "status": "PASS" if int(null_dates.sum()) == 0 else "FAIL",
            "failed_rows": int(null_dates.sum()),
            "details": "Date.CMD parsed with ISO + fallback",
        },
        {
            "check": "Positive quantities",
            "status": "PASS" if int(invalid_qty.sum()) == 0 else "FAIL",
            "failed_rows": int(invalid_qty.sum()),
            "details": "Qty > 0",
        },
        {
            "check": "Category mapping coverage by ProductPrefix",
            "status": "PASS" if int(missing_prefix.sum()) == 0 else "FAIL",
            "failed_rows": int(missing_prefix.sum()),
            "details": "Missing prefixes: " + (", ".join(missing_prefix_values) if missing_prefix_values else "None"),
        },
    ]

    report = pd.DataFrame(rows)
    detail = sales.loc[invalid_ttc | null_dates | invalid_qty | missing_prefix, [
        find_column(sales, "Num.CMD"),
        col_date,
        col_code,
        col_qty,
        col_ht,
        col_taxe,
        col_ttc,
        "ProductPrefix",
        "calc_gap",
    ]].copy()

    return report, detail


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate BI source data quality checks.")
    parser.add_argument("--excel", type=Path, default=Path("Sales_TD_v2.xlsx"), help="Path to source Excel file.")
    parser.add_argument("--out", type=Path, default=Path("qa/qa_report.csv"), help="Path for summary CSV report.")
    parser.add_argument(
        "--detail-out",
        type=Path,
        default=Path("qa/qa_report_details.csv"),
        help="Path for detailed failing rows CSV.",
    )
    parser.add_argument("--tolerance", type=float, default=0.01, help="Tolerance for TTC = HT + Taxe check.")
    args = parser.parse_args()

    if not args.excel.exists():
        print(f"[ERROR] Excel file not found: {args.excel}")
        return 2

    report, detail = run_checks(args.excel, args.tolerance)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    report.to_csv(args.out, index=False, encoding="utf-8")

    args.detail_out.parent.mkdir(parents=True, exist_ok=True)
    detail.to_csv(args.detail_out, index=False, encoding="utf-8")

    print("QA SUMMARY")
    print(report.to_string(index=False))
    print(f"\nSummary CSV: {args.out}")
    print(f"Details CSV: {args.detail_out}")

    has_fail = (report["status"] == "FAIL").any()
    return 1 if has_fail else 0


if __name__ == "__main__":
    sys.exit(main())
