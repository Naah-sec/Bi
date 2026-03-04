from __future__ import annotations

import pandas as pd

from src.transform import (
    extract_order_number,
    extract_product_prefix,
    extract_typevente_code,
    extract_wilaya,
    parse_french_number,
    split_legal_form_and_customer,
    transform_sales,
)


def test_parse_french_number():
    assert parse_french_number("500 000,00") == 500000.0
    assert parse_french_number("1 234,5") == 1234.5
    assert parse_french_number(None) is None


def test_field_extractors():
    assert extract_typevente_code("SLSD/0001") == "SLSD"
    assert extract_order_number("SLSD/0001") == "0001"
    assert extract_product_prefix("LAP.0120") == "LAP"
    assert extract_wilaya("Cite 20 Aout, Alger") == "Alger"

    legal, customer = split_legal_form_and_customer("SARL ABC Trading")
    assert legal == "SARL"
    assert customer == "ABC Trading"

    legal2, customer2 = split_legal_form_and_customer("ACME Corp")
    assert legal2 == "UNKNOWN"
    assert customer2 == "ACME Corp"


def test_transform_sales_core_derivations():
    raw = pd.DataFrame(
        {
            "Num.CMD": ["SLSD/0001", "SLSR/0002"],
            "Date.CMD": ["2025-02-22", "2025-03-01"],
            "Client": ["SARL ABC", "XYZ Inc"],
            "Adresse": ["Cite 20 Aout, Alger", "Zone Indus, Blida"],
            "Code Produit": ["LAP.0120", "UNK.0001"],
            "Produit": ["Laptop A", "Unknown Item"],
            "Qté": ["2", "3"],
            "Montant HT": ["100 000,00", "50 000,00"],
            "Taxe": ["19 000,00", "9 500,00"],
            "Montant TTC": ["119 000,00", "59 500,00"],
        }
    )

    result = transform_sales(raw)
    df = result.salesline

    assert "typevente_code" in df.columns
    assert "legal_form" in df.columns
    assert "wilaya" in df.columns
    assert "product_prefix" in df.columns
    assert "category" in df.columns

    assert df.loc[0, "typevente_code"] == "SLSD"
    assert df.loc[0, "legal_form"] == "SARL"
    assert df.loc[0, "wilaya"] == "Alger"
    assert df.loc[1, "category"] == "Unknown"
    assert "UNK" in result.missing_prefixes

