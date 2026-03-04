from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

from src.qa import run_inventory_event_validation, run_purchases_validation
from src.transform import extract_typeachat_code, split_legal_form_and_supplier, transform_purchases
from src.warehouse import (
    build_fact_inventory_events,
    build_fact_margin_monthly,
    build_warehouse,
    compute_ppm_product_month,
)


def test_purchase_extractors_and_transform():
    assert extract_typeachat_code("POL/0001") == "POL"

    legal, supplier = split_legal_form_and_supplier("SARL IMPORT COMPUTER")
    assert legal == "SARL"
    assert supplier == "IMPORT COMPUTER"

    raw = pd.DataFrame(
        {
            "Num.CMD": ["POL/0001", "POI/0002"],
            "Date.CMD": ["2024-11-05", "2024-12-16"],
            "Fournisseur": ["SARL IMPORT COMPUTER", "Vendor X"],
            "Code Produit": ["LAP.0120", "UNK.0001"],
            "Produit": ["Laptop A", "Unknown item"],
            "QTY": ["10", "5"],
            "Montant HT": ["1000", "500"],
            "Taxe": ["190", "95"],
            "Montant TTC": ["1190", "595"],
        }
    )

    transformed = transform_purchases(raw)
    df = transformed.purchaseline

    assert df.loc[0, "typeachat_code"] == "POL"
    assert df.loc[0, "supplier_legal_form"] == "SARL"
    assert df.loc[0, "supplier_name"] == "IMPORT COMPUTER"
    assert df.loc[1, "supplier_legal_form"] == "UNKNOWN"
    assert df.loc[1, "category"] == "Unknown"
    assert "UNK" in transformed.missing_prefixes


def test_purchases_validation_ttc_fail(tmp_path: Path):
    raw = pd.DataFrame(
        {
            "Num.CMD": ["POL/0001"],
            "Date.CMD": ["2024-11-05"],
            "Fournisseur": ["SARL SUPPLIER"],
            "Code Produit": ["LAP.0120"],
            "Produit": ["Laptop"],
            "QTY": ["10"],
            "Montant HT": ["1000"],
            "Taxe": ["190"],
            "Montant TTC": ["1500"],
        }
    )

    transformed = transform_purchases(raw)
    result = run_purchases_validation(
        purchaseline_df=transformed.purchaseline,
        missing_prefixes=transformed.missing_prefixes,
        output_dir=tmp_path,
        tolerance=0.01,
    )

    assert result.has_errors is True
    ttc_row = result.report[result.report["check"] == "Montant TTC ~= Montant HT + Taxe"].iloc[0]
    assert ttc_row["status"] == "FAIL"
    assert int(ttc_row["failed_rows"]) == 1


def test_ppm_simple_weighted_and_time_awareness():
    purchase_events = pd.DataFrame(
        {
            "product_id": [1, 1],
            "year": [2024, 2024],
            "month_no": [1, 2],
            "year_month": ["2024-01", "2024-02"],
            "qty": [1.0, 3.0],
            "amount_ttc": [100.0, 600.0],
            "unit_cost_event_ttc": [100.0, 200.0],
        }
    )

    dim_date = pd.DataFrame(
        {
            "year": [2024, 2024, 2024],
            "month_no": [1, 2, 3],
            "year_month": ["2024-01", "2024-02", "2024-03"],
        }
    )

    ppm = compute_ppm_product_month(purchase_events_df=purchase_events, dim_date=dim_date, product_ids=[1])

    jan = ppm[ppm["year_month"] == "2024-01"].iloc[0]
    feb = ppm[ppm["year_month"] == "2024-02"].iloc[0]
    mar = ppm[ppm["year_month"] == "2024-03"].iloc[0]

    assert jan["ppm_simple_to_month"] == 100.0
    assert feb["ppm_simple_to_month"] == 150.0

    assert jan["ppm_weighted_to_month"] == 100.0
    assert feb["ppm_weighted_to_month"] == 175.0

    assert mar["ppm_simple_to_month"] == 150.0
    assert mar["ppm_weighted_to_month"] == 175.0


def test_inventory_ledger_pmp_sequence():
    sales_df = pd.DataFrame(
        {
            "date_cmd": [pd.to_datetime("2024-02-01").date()],
            "product_code": ["P1"],
            "product_name": ["Prod 1"],
            "category": ["Cat A"],
            "wilaya": ["Alger"],
            "qty": [20.0],
            "amount_ttc": [300.0],
        }
    )

    purchases_df = pd.DataFrame(
        {
            "date_cmd": [pd.to_datetime("2024-01-01").date(), pd.to_datetime("2024-03-01").date()],
            "product_code": ["P1", "P1"],
            "product_name": ["Prod 1", "Prod 1"],
            "category": ["Cat A", "Cat A"],
            "qty": [100.0, 50.0],
            "amount_ttc": [1000.0, 1000.0],
        }
    )

    dim_product = pd.DataFrame(
        {
            "product_id": [1],
            "product_code": ["P1"],
            "product_name": ["Prod 1"],
            "product_prefix": ["P"],
            "category": ["Cat A"],
        }
    )
    dim_wilaya = pd.DataFrame({"wilaya_id": [1], "wilaya_name": ["Alger"]})

    ledger = build_fact_inventory_events(
        sales_df=sales_df,
        purchases_df=purchases_df,
        dim_product=dim_product,
        dim_wilaya=dim_wilaya,
        tolerance=0.01,
    )

    assert len(ledger) == 3

    r1 = ledger.iloc[0]  # purchase 2024-01-01
    r2 = ledger.iloc[1]  # sale 2024-02-01
    r3 = ledger.iloc[2]  # purchase 2024-03-01

    assert r1["event_type"] == "PURCHASE"
    assert r1["stock_qty_before"] == 0.0
    assert r1["stock_qty_after"] == 100.0
    assert r1["ppm_unit_cost_after"] == 10.0

    assert r2["event_type"] == "SALE"
    assert r2["stock_qty_before"] == 100.0
    assert r2["stock_qty_after"] == 80.0
    assert r2["ppm_unit_cost_before"] == 10.0
    assert r2["ppm_unit_cost_after"] == 10.0

    assert r3["event_type"] == "PURCHASE"
    assert r3["stock_qty_before"] == 80.0
    assert r3["stock_qty_after"] == 130.0
    assert round(float(r3["ppm_unit_cost_after"]), 2) == 13.85


def test_inventory_validation_flags_insufficient_stock(tmp_path: Path):
    sales_df = pd.DataFrame(
        {
            "date_cmd": [pd.to_datetime("2024-01-01").date()],
            "product_code": ["P1"],
            "product_name": ["Prod 1"],
            "category": ["Cat A"],
            "wilaya": ["Alger"],
            "qty": [5.0],
            "amount_ttc": [100.0],
        }
    )
    purchases_df = pd.DataFrame(columns=["date_cmd", "product_code", "product_name", "category", "qty", "amount_ttc"])

    dim_product = pd.DataFrame(
        {
            "product_id": [1],
            "product_code": ["P1"],
            "product_name": ["Prod 1"],
            "product_prefix": ["P"],
            "category": ["Cat A"],
        }
    )
    dim_wilaya = pd.DataFrame({"wilaya_id": [1], "wilaya_name": ["Alger"]})

    ledger = build_fact_inventory_events(
        sales_df=sales_df,
        purchases_df=purchases_df,
        dim_product=dim_product,
        dim_wilaya=dim_wilaya,
        tolerance=0.01,
    )

    assert bool(ledger.iloc[0]["valid_for_margin"]) is False
    assert "INSUFFICIENT_STOCK" in str(ledger.iloc[0]["error_code"])

    result = run_inventory_event_validation(ledger, output_dir=tmp_path, tolerance=0.01)
    assert result.has_errors is True
    check_row = result.report[result.report["check"] == "sale_qty <= stock_qty_before"].iloc[0]
    assert check_row["status"] == "FAIL"


def test_margin_aggregation_from_inventory_events():
    ledger = pd.DataFrame(
        {
            "event_type": ["SALE", "SALE", "PURCHASE"],
            "valid_for_margin": [True, True, False],
            "year": [2024, 2024, 2024],
            "month_no": [1, 1, 1],
            "year_month": ["2024-01", "2024-01", "2024-01"],
            "product_id": [1, 1, 1],
            "category": ["Cat A", "Cat A", "Cat A"],
            "wilaya_id": [1, 1, pd.NA],
            "sale_qty": [2.0, 3.0, 0.0],
            "sale_revenue": [200.0, 300.0, pd.NA],
            "cost_of_goods_sold": [120.0, 180.0, pd.NA],
        }
    )

    margin = build_fact_margin_monthly(ledger)
    assert len(margin) == 1
    row = margin.iloc[0]

    assert row["revenue"] == 500.0
    assert row["cogs"] == 300.0
    assert row["gross_margin_value"] == 200.0
    assert row["gross_margin_pct"] == 0.4


def test_build_warehouse_creates_required_objects(tmp_path: Path):
    project_root = Path(__file__).resolve().parents[1]
    sales_excel = project_root / "data" / "Sales_TD.xlsx"
    purchases_excel = project_root / "data" / "Purchases_TD.xlsx"
    purchases_csv = project_root / "data" / "PurchasesRaw.csv"

    out_db = tmp_path / "warehouse.duckdb"
    out_reports = tmp_path / "reports"

    counts = build_warehouse(
        excel_path=sales_excel,
        duckdb_path=out_db,
        reports_dir=out_reports,
        purchases_source="auto",
        purchases_excel_path=purchases_excel,
        purchases_csv_path=purchases_csv,
        drop_invalid_purchase_rows=False,
    )

    assert counts["fact_salesline"] > 0
    assert counts["fact_purchaseline"] > 0
    assert counts["fact_inventory_events"] > 0
    assert counts["fact_margin_monthly"] > 0

    conn = duckdb.connect(str(out_db), read_only=True)
    try:
        tables = conn.execute("SHOW TABLES").fetchdf()["name"].str.lower().tolist()
        assert "fact_salesline" in tables
        assert "fact_purchaseline" in tables
        assert "fact_inventory_events" in tables
        assert "fact_margin_monthly" in tables

        views = conn.execute(
            "SELECT table_name FROM information_schema.views WHERE table_schema = 'main'"
        ).fetchdf()["table_name"].str.lower().tolist()
        assert "view_margin_salesline" in views
        assert "view_inventory_ledger" in views

        margin_cols = (
            conn.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_name='fact_margin_monthly'"
            )
            .fetchdf()["column_name"]
            .str.lower()
            .tolist()
        )
        for col in ["revenue", "cogs", "gross_margin_value", "gross_margin_pct", "sold_qty"]:
            assert col in margin_cols
    finally:
        conn.close()
