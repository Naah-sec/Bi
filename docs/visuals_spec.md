# Visuals Specification

Use these pages/visuals exactly. Measures come from `dax/measures.dax`.

## Global slicers (add on every page)

- `dim_date[Year]`
- `dim_date[YearMonth]`
- `dim_typevente[TypeVenteLabel]`
- `dim_wilaya[Wilaya]`

## Page 1: Executive Trend (Q1)

Visuals:

1. Cards (3)
- `CA HT`
- `Taxe`
- `CA TTC`

2. Line and clustered column chart
- Axis: `dim_date[YearMonth]`
- Column values: `CA HT`
- Line values: `CA TTC`

3. Stacked column chart
- Axis: `dim_date[YearMonth]`
- Legend: `dim_typevente[TypeVenteLabel]`
- Values: `CA HT`

4. Matrix
- Rows: `dim_date[Year]`, `dim_date[Month]`
- Values: `CA HT`, `Taxe`, `CA TTC`, `Quantités`

## Page 2: Product Mix (Q2)

Visuals:

1. Clustered bar chart
- Axis: `dim_product[Category]`
- Values: `CA HT`

2. Treemap
- Group: `dim_product[Category]`
- Details: `dim_product[Produit]`
- Values: `CA HT`

3. Table
- Columns: `dim_product[Code Produit]`, `dim_product[Produit]`, `dim_product[Category]`, `Quantités`, `CA HT`, `CA TTC`
- Sort by: `CA HT` descending

4. Ribbon chart
- Axis: `dim_date[YearMonth]`
- Legend: `dim_product[Category]`
- Values: `CA HT`

Page slicer (extra):
- `dim_product[Category]`

## Page 3: Customer Performance (Q3)

Visuals:

1. Clustered bar chart
- Axis: `dim_customer[CustomerName]`
- Values: `CA HT`
- Visual filter: Top N = 10 by `CA HT`

2. Donut chart
- Legend: `dim_customer[LegalForm]`
- Values: `CA HT`

3. Table
- Columns: `dim_customer[LegalForm]`, `dim_customer[CustomerName]`, `Quantités`, `CA HT`, `Taxe`, `CA TTC`, `Rank Customer by CA HT`
- Sort: `Rank Customer by CA HT` ascending

Page slicer (extra):
- `dim_customer[LegalForm]`

## Page 4: Geo Sales (Q4)

Visuals:

1. Filled map (or map)
- Location: `dim_wilaya[Wilaya]`
- Color saturation / Bubble size: `CA HT`

2. Clustered bar chart
- Axis: `dim_wilaya[Wilaya]`
- Values: `CA HT`

3. Matrix
- Rows: `dim_wilaya[Wilaya]`
- Columns: `dim_product[Category]`
- Values: `CA HT`

4. Line chart
- Axis: `dim_date[YearMonth]`
- Legend: `dim_wilaya[Wilaya]`
- Values: `CA HT`

## Page 5: Rankings (Q5)

Visuals:

1. Table (Products ranking)
- Columns: `dim_product[Produit]`, `CA HT`, `Rank Product by CA HT`
- Filter: `Rank Product by CA HT <= 10`
- Sort: `Rank Product by CA HT` ascending

2. Table (Customers ranking)
- Columns: `dim_customer[CustomerName]`, `CA HT`, `Rank Customer by CA HT`
- Filter: `Rank Customer by CA HT <= 10`
- Sort: `Rank Customer by CA HT` ascending

3. Table (Wilaya ranking)
- Columns: `dim_wilaya[Wilaya]`, `CA HT`, `Rank Wilaya by CA HT`
- Filter: `Rank Wilaya by CA HT <= 10`
- Sort: `Rank Wilaya by CA HT` ascending

4. KPI/scorecard tiles
- `CA HT`
- `CA TTC`
- `Quantités`
