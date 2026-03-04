let
    FromFact = Table.Distinct(Table.SelectColumns(fact_SalesLine, {"Wilaya"})),
    #"Fact Non Null" = Table.SelectRows(FromFact, each [Wilaya] <> null and Text.Trim([Wilaya]) <> ""),

    MapSource = tblWilayaMap,
    #"Typed Map" = Table.TransformColumnTypes(MapSource, {{"Wilaya", type text}}),
    #"Trimmed Map" = Table.TransformColumns(#"Typed Map", {{"Wilaya", each if _ is null then null else Text.Trim(Text.From(_)), type text}}),
    #"Map Non Null" = Table.SelectRows(#"Trimmed Map", each [Wilaya] <> null and Text.Trim([Wilaya]) <> ""),

    #"Combined" = Table.Combine({#"Map Non Null", #"Fact Non Null"}),
    #"Distinct Wilaya" = Table.Distinct(#"Combined"),
    #"Sorted Rows" = Table.Sort(#"Distinct Wilaya", {{"Wilaya", Order.Ascending}})
in
    #"Sorted Rows"
