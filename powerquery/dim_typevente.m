let
    FromFact = Table.Distinct(Table.SelectColumns(fact_SalesLine, {"TypeVenteCode"})),

    MapSource = tblTypeVenteMap,
    #"Typed Map" = Table.TransformColumnTypes(MapSource, {{"TypeVenteCode", type text}, {"TypeVenteLabel", type text}}),
    #"Trimmed Map" = Table.TransformColumns(
        #"Typed Map",
        {
            {"TypeVenteCode", each if _ is null then null else Text.Trim(Text.From(_)), type text},
            {"TypeVenteLabel", each if _ is null then null else Text.Trim(Text.From(_)), type text}
        }
    ),

    #"Merged Map" = Table.NestedJoin(
        FromFact,
        {"TypeVenteCode"},
        #"Trimmed Map",
        {"TypeVenteCode"},
        "TypeMap",
        JoinKind.LeftOuter
    ),

    #"Expanded TypeLabel" = Table.ExpandTableColumn(#"Merged Map", "TypeMap", {"TypeVenteLabel"}, {"TypeVenteLabel"}),
    #"Filled Unknown" = Table.ReplaceValue(#"Expanded TypeLabel", null, "Unknown", Replacer.ReplaceValue, {"TypeVenteLabel"}),
    #"Sorted Rows" = Table.Sort(#"Filled Unknown", {{"TypeVenteCode", Order.Ascending}})
in
    #"Sorted Rows"
