# Linux Installation and Run Guide

## 1) Install Python

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip
```

## 2) Open project and activate venv

```bash
cd /path/to/BI
python3 -m venv .venv
source .venv/bin/activate
```

## 3) Install dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 4) Configure `.env`

```bash
cp .env.example .env
```

Defaults:
- `EXCEL_PATH=data/Sales_TD.xlsx`
- `PURCHASES_EXCEL_PATH=data/Purchases_TD.xlsx`
- `PURCHASES_CSV_PATH=data/PurchasesRaw.csv`
- `DUCKDB_PATH=data/warehouse.duckdb`
- `QA_TOLERANCE=0.01`
- `MARGIN_MISSING_COST_AS_ZERO=false`

## 5) Build warehouse

Default:
```bash
python -m src.warehouse --build
```

Force purchases Excel:
```bash
python -m src.warehouse --build --purchases-source excel --purchases-excel data/Purchases_TD.xlsx
```

Force purchases CSV:
```bash
python -m src.warehouse --build --purchases-source csv --purchases-csv data/PurchasesRaw.csv
```

Continue even if purchases validation has invalid rows:
```bash
python -m src.warehouse --build --drop-invalid-purchases-rows
```

## 6) Run Streamlit

```bash
streamlit run app/streamlit_app.py
```

Open `http://localhost:8501`.

## 7) Run tests

```bash
python -m pytest -q
```

## 8) Generated reports

- `reports/qa_report.csv`
- `reports/purchases_qa_report.csv`
- `reports/inventory_qa_report.csv`
- `reports/profile.md`
- `reports/purchases_profile.md`

## 9) Exports from dashboard

- `reports/export_fact_margin_monthly.csv`
- `reports/inventory_ledger_export.csv`

## 10) Deploy with Docker (Linux server)

Build image:
```bash
docker build -t bi-dashboard .
```

Run container:
```bash
docker run --rm -p 8501:8501 bi-dashboard
```

Open `http://localhost:8501`.

Optional env overrides:
```bash
docker run --rm -p 8501:8501 \
  -e AUTO_BUILD_WAREHOUSE=true \
  -e EXCEL_PATH=data/Sales_TD.xlsx \
  -e PURCHASES_EXCEL_PATH=data/Purchases_TD.xlsx \
  -e PURCHASES_CSV_PATH=data/PurchasesRaw.csv \
  -e DUCKDB_PATH=data/warehouse.duckdb \
  bi-dashboard
```

## 11) Deploy on Render (from GitHub)

1. Push repo to GitHub.
2. In Render, create a new `Web Service` from this repo.
3. Select `Docker` environment.
4. Add env vars (same as above), keep `AUTO_BUILD_WAREHOUSE=true`.
5. Deploy and open the service URL.
