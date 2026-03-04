# End-to-End BI Analytics Project (Sales + Purchases + Inventory Ledger + Margins)

This project builds a reproducible BI pipeline from Excel/CSV into DuckDB and serves interactive dashboards in Streamlit.

## Scope

1. Sales ingestion and analytics.
2. Purchases ingestion and analytics.
3. Date-ordered inventory ledger for manual auditing.
4. Accounting-correct gross margin calculation:
- `Revenue`
- `Cost_of_goods_sold (COGS)`
- `Gross_margin_value = Revenue - COGS`
- `Gross_margin_pct = Gross_margin_value / Revenue` (only when `Revenue > 0`)

## Inputs

Sales:
- `data/Sales_TD.xlsx`

Purchases:
- `data/Purchases_TD.xlsx` (preferred)
- `data/PurchasesRaw.csv` (alternative)

## Key build command

```bash
python -m src.warehouse --build
```

Force purchases source:

```bash
python -m src.warehouse --build --purchases-source excel --purchases-excel data/Purchases_TD.xlsx
python -m src.warehouse --build --purchases-source csv --purchases-csv data/PurchasesRaw.csv
```

If purchases validation contains errors and you want to continue by dropping invalid rows:

```bash
python -m src.warehouse --build --drop-invalid-purchases-rows
```

## Validation reports

Sales:
- `reports/qa_report.csv`
- `reports/qa_report.md`
- `reports/profile.md`

Purchases:
- `reports/purchases_qa_report.csv`
- `reports/purchases_qa_report.md`
- `reports/purchases_qa_details.csv`
- `reports/purchases_quarantine.csv` (if invalid rows exist)
- `reports/purchases_profile.md`

Inventory ledger/accounting checks:
- `reports/inventory_qa_report.csv`
- `reports/inventory_qa_report.md`
- `reports/inventory_qa_details.csv`

## DuckDB objects

Dimensions:
- `dim_date`
- `dim_product`
- `dim_customer`
- `dim_typevente`
- `dim_wilaya`
- `dim_supplier`
- `dim_typeachat`

Facts / helpers:
- `fact_salesline`
- `fact_purchaseline`
- `purchase_unit_cost_events`
- `ppm_product_month`
- `fact_inventory_events`
- `fact_margin_monthly`

Views:
- `view_inventory_ledger`
- `view_margin_salesline`

## Inventory ledger logic (chronological)

Per product, events are processed in date order (purchase before sale on same day).

State variables:
- `stock_qty`
- `stock_value`
- `ppm_unit_cost` (PMP)

Purchase event:
- `purchase_value = purchase_qty * purchase_unit_price`
- `stock_qty += purchase_qty`
- `stock_value += purchase_value`
- `ppm_unit_cost = stock_value / stock_qty`

Sale event:
- `COGS = sale_qty * ppm_unit_cost_before`
- `Revenue = sale_qty * sale_unit_price`
- `stock_qty -= sale_qty`
- `stock_value -= COGS`
- `ppm_unit_cost` remains unchanged after sale

Invalid events are flagged with `error_code` and excluded from margin aggregation.

## Margin dataset

`fact_margin_monthly` aggregates by:
- `year`
- `month_no`
- `year_month`
- `product_id`
- `category`
- `wilaya_id`

Measures:
- `revenue`
- `cogs`
- `gross_margin_value`
- `gross_margin_pct`
- `sold_qty`

## Streamlit pages

Sales:
- Home/KPIs, Q1-Q5, Explore

Purchases:
- Data Ingestion
- KPIs
- Q1-Q4
- Explore

Margins:
- KPIs
- Analysis
- Explore

Inventory:
- Inventory Debug / Ledger

## Exports from app

- `reports/export_fact_margin_monthly.csv`
- `reports/inventory_ledger_export.csv`

## Run app

```bash
streamlit run app/streamlit_app.py
```

## Tests

```bash
python -m pytest -q
```

## Deploy

### Option A: Streamlit Community Cloud (fastest)

1. Push this repo to GitHub.
2. Go to [share.streamlit.io](https://share.streamlit.io/) and create a new app.
3. Set:
   - Repository: `Naah-sec/Bi` (or your fork)
   - Branch: `main`
   - Main file path: `app/streamlit_app.py`
4. Deploy.

Notes:
- On first boot, the app auto-builds `warehouse.duckdb` if missing.
- Keep `data/Sales_TD.xlsx` and purchases files in the repo (or adjust env vars).

### Option B: Docker deploy (Render/Railway/Fly/VM)

This repository now includes:
- `Dockerfile`
- `.dockerignore`
- `scripts/start_streamlit.sh`

The startup script:
- builds warehouse automatically (`AUTO_BUILD_WAREHOUSE=true` by default)
- starts Streamlit on `0.0.0.0:$PORT`

Local container test:

```bash
docker build -t bi-dashboard .
docker run --rm -p 8501:8501 bi-dashboard
```

Open `http://localhost:8501`.

### Render quick steps (Docker Web Service)

1. Create `Web Service` on Render from your GitHub repo.
2. Environment: `Docker`.
3. No custom start command needed (Docker `CMD` is used).
4. Add env vars if needed:
   - `EXCEL_PATH=data/Sales_TD.xlsx`
   - `PURCHASES_EXCEL_PATH=data/Purchases_TD.xlsx`
   - `PURCHASES_CSV_PATH=data/PurchasesRaw.csv`
   - `DUCKDB_PATH=data/warehouse.duckdb`
   - `AUTO_BUILD_WAREHOUSE=true`
5. Deploy.
