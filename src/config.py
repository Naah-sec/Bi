from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
REPORTS_DIR = PROJECT_ROOT / "reports"

EXCEL_PATH = Path(os.getenv("EXCEL_PATH", DATA_DIR / "Sales_TD.xlsx"))
PURCHASES_EXCEL_PATH = Path(os.getenv("PURCHASES_EXCEL_PATH", DATA_DIR / "Purchases_TD.xlsx"))
PURCHASES_CSV_PATH = Path(os.getenv("PURCHASES_CSV_PATH", DATA_DIR / "PurchasesRaw.csv"))
DUCKDB_PATH = Path(os.getenv("DUCKDB_PATH", DATA_DIR / "warehouse.duckdb"))

QA_TOLERANCE = float(os.getenv("QA_TOLERANCE", "0.01"))
MARGIN_MISSING_COST_AS_ZERO = os.getenv("MARGIN_MISSING_COST_AS_ZERO", "false").strip().lower() in {
    "1",
    "true",
    "yes",
}

DEFAULT_PRODUCT_CATEGORY_MAP = {
    "LAP": "Laptop",
    "PRI": "Printer",
    "INK": "Ink/Toner",
    "SCA": "Scanner",
}

DEFAULT_TYPEVENTE_LABELS = {
    "SLSD": "Vente directe",
    "SLSR": "Vente revendeur",
    "SLSG": "Vente gros",
}

DEFAULT_TYPEACHAT_LABELS = {
    "POL": "Type POL",
    "POI": "Type POI",
}

LEGAL_FORMS = {"SARL", "EURL", "SNC"}
