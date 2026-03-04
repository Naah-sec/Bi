let
    Source = fact_SalesLine,
    #"Selected Columns" = Table.SelectColumns(Source, {"CustomerKey", "LegalForm", "CustomerName"}),
    #"Removed Null Keys" = Table.SelectRows(#"Selected Columns", each [CustomerKey] <> null and Text.Trim([CustomerKey]) <> ""),
    #"Distinct Customers" = Table.Distinct(#"Removed Null Keys"),
    #"Sorted Rows" = Table.Sort(#"Distinct Customers", {{"CustomerName", Order.Ascending}})
in
    #"Sorted Rows"
