# Power BI + Excel BI Build Guide

This guide builds a full BI model/report from `Sales_TD_v2.xlsx` and answers 5 business questions.

## 1) Business questions to answer

1. How do `CA HT`, `Taxe`, and `CA TTC` evolve over time?
2. Which product categories/products drive revenue and quantities?
3. Which customers contribute the most revenue?
4. Which wilayas generate the most sales?
5. What are the Top-N rankings (products/customers/wilayas) under filters?

## 2) Load Excel tables

In Power BI Desktop:

1. `Get Data` -> `Excel` -> select `Sales_TD_v2.xlsx`.
2. Select:
   - `tblSalesRaw`
   - `tblProductCategoryMap`
   - `tblTypeVenteMap`
   - `tblWilayaMap`
3. Click `Transform Data` (not `Load` yet).

## 3) Build Power Query transformations

Use files from `/powerquery`:

1. Create query `fact_SalesLine` from `tblSalesRaw`:
   - Open Advanced Editor.
   - Paste `powerquery/stg_sales.m`.
2. Create query `dim_product` from blank query:
   - Paste `powerquery/dim_product.m`.
3. Create query `dim_customer`:
   - Paste `powerquery/dim_customer.m`.
4. Create query `dim_typevente`:
   - Paste `powerquery/dim_typevente.m`.
5. Create query `dim_wilaya`:
   - Paste `powerquery/dim_wilaya.m`.
6. Disable load for raw/map staging queries if desired (`tblSalesRaw`, map tables).
7. `Close & Apply`.

## 4) Create date table and measures

1. In Model view, create New Table with `/dax/dim_date.dax`.
2. Mark `dim_date` as Date table using `dim_date[Date]`.
3. Create New Measures in fact table using `/dax/measures.dax`.
4. Sort `dim_date[Month]` by `dim_date[MonthNo]`.

## 5) Create relationships (star schema)

Create these active relationships:

1. `fact_SalesLine[Date.CMD]` -> `dim_date[Date]`
2. `fact_SalesLine[Code Produit]` -> `dim_product[Code Produit]`
3. `fact_SalesLine[CustomerKey]` -> `dim_customer[CustomerKey]`
4. `fact_SalesLine[TypeVenteCode]` -> `dim_typevente[TypeVenteCode]`
5. `fact_SalesLine[Wilaya]` -> `dim_wilaya[Wilaya]`

All should be single-direction from dimension to fact, one-to-many.

## 6) Build report pages for the 5 questions

Use `/docs/visuals_spec.md` exactly:

1. Page 1 `Executive Trend` -> Q1
2. Page 2 `Product Mix` -> Q2
3. Page 3 `Customer Performance` -> Q3
4. Page 4 `Geo Sales` -> Q4
5. Page 5 `Rankings` -> Q5

## 7) Validate data quality before/after refresh

Run:

```powershell
python qa/validate_data.py --excel Sales_TD_v2.xlsx --out qa/qa_report.csv
```

Checks:
- `Montant TTC ≈ Montant HT + Taxe` (tolerance)
- no null dates
- positive quantities
- product category mapping coverage by product prefix

## 8) Final sanity checklist

- No orphan keys in relationships.
- All report pages respond to slicers.
- Ranking visuals are sorted by rank/CA as expected.
- QA report returns PASS for all critical checks.
