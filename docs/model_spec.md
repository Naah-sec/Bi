# Model Specification (Star Schema)

## 1) Target schema

Fact table:
- `fact_salesline` (Power BI query name: `fact_SalesLine`)

Dimensions:
- `dim_date`
- `dim_product`
- `dim_customer`
- `dim_typevente`
- `dim_wilaya`

## 2) Fact table (`fact_SalesLine`)

Grain:
- One row = one sales line from `tblSalesRaw`.

Business columns (minimum):
- `Num.CMD` (order number)
- `Date.CMD`
- `Code Produit`
- `Produit`
- `Qté`
- `Montant HT`
- `Taxe`
- `Montant TTC`
- `TypeVenteCode` (derived from `Num.CMD`, before `/`)
- `LegalForm` (derived from `Client`, first token)
- `CustomerName` (derived from `Client`, remaining tokens)
- `CustomerKey` (`LegalForm|CustomerName`)
- `Wilaya` (derived from last token of `Adresse` after comma)
- `ProductPrefix` (derived from `Code Produit`, before `.`)
- `Category` (merged from `tblProductCategoryMap`)
- `Year`, `MonthNo`, `YearMonth` (derived from `Date.CMD`)

## 3) Dimension tables

### `dim_product`
Source:
- Distinct rows from `fact_SalesLine` on product attributes.

Columns:
- `Code Produit` (PK)
- `Produit`
- `ProductPrefix`
- `Category`

### `dim_customer`
Source:
- Distinct rows from `fact_SalesLine` on customer attributes.

Columns:
- `CustomerKey` (PK)
- `LegalForm`
- `CustomerName`

### `dim_typevente`
Source:
- Distinct `TypeVenteCode` from `fact_SalesLine`
- Left join with `tblTypeVenteMap` for labels.

Columns:
- `TypeVenteCode` (PK)
- `TypeVenteLabel`

### `dim_wilaya`
Source:
- Union of `tblWilayaMap` and distinct Wilaya values from `fact_SalesLine`.

Columns:
- `Wilaya` (PK)

### `dim_date`
Source:
- DAX `CALENDAR` table bounded by min/max `fact_SalesLine[Date.CMD]`.

Columns:
- `Date` (PK)
- `Year`
- `MonthNo`
- `Month`
- `YearMonth`

## 4) Relationships

Set all as Single direction (dimension filters fact), Many-to-One (*:1), Active:

1. `fact_SalesLine[Date.CMD]` -> `dim_date[Date]`
2. `fact_SalesLine[Code Produit]` -> `dim_product[Code Produit]`
3. `fact_SalesLine[CustomerKey]` -> `dim_customer[CustomerKey]`
4. `fact_SalesLine[TypeVenteCode]` -> `dim_typevente[TypeVenteCode]`
5. `fact_SalesLine[Wilaya]` -> `dim_wilaya[Wilaya]`

## 5) Modeling notes

- Disable Auto Date/Time in Power BI options.
- Keep keys trimmed and case-consistent in Power Query.
- Validate unmatched product prefixes (via QA script + model checks).
- Sort `dim_date[Month]` by `dim_date[MonthNo]`.
