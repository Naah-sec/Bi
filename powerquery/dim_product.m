let
    Source = fact_SalesLine,
    #"Selected Columns" = Table.SelectColumns(Source, {"Code Produit", "Produit", "ProductPrefix", "Category"}),
    #"Removed Null Codes" = Table.SelectRows(#"Selected Columns", each [Code Produit] <> null and Text.Trim([Code Produit]) <> ""),
    #"Distinct Products" = Table.Distinct(#"Removed Null Codes"),
    #"Sorted Rows" = Table.Sort(#"Distinct Products", {{"Code Produit", Order.Ascending}})
in
    #"Sorted Rows"
