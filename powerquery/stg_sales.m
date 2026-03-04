let
    // Source queries loaded from the Excel workbook in Power BI
    tblSalesRaw_Source = tblSalesRaw,
    tblProductCategoryMap_Source = tblProductCategoryMap,

    // Clean text columns
    #"Trimmed Text" = Table.TransformColumns(
        tblSalesRaw_Source,
        {
            {"Num.CMD", each if _ is null then null else Text.Trim(Text.From(_)), type text},
            {"Client", each if _ is null then null else Text.Trim(Text.From(_)), type text},
            {"Adresse", each if _ is null then null else Text.Trim(Text.From(_)), type text},
            {"Code Produit", each if _ is null then null else Text.Trim(Text.From(_)), type text},
            {"Produit", each if _ is null then null else Text.Trim(Text.From(_)), type text}
        }
    ),

    // Base types (fr-FR culture for numeric/date compatibility)
    #"Typed Base" = Table.TransformColumnTypes(
        #"Trimmed Text",
        {
            {"Date.CMD", type date},
            {"Qté", Int64.Type},
            {"Montant HT", type number},
            {"Taxe", type number},
            {"Montant TTC", type number}
        },
        "fr-FR"
    ),

    // Derivations
    #"Added TypeVenteCode" = Table.AddColumn(
        #"Typed Base",
        "TypeVenteCode",
        each if [Num.CMD] = null then null else Text.BeforeDelimiter([Num.CMD], "/"),
        type text
    ),

    #"Added LegalForm" = Table.AddColumn(
        #"Added TypeVenteCode",
        "LegalForm",
        each if [Client] = null then null else Text.BeforeDelimiter(Text.Trim([Client]), " "),
        type text
    ),

    #"Added CustomerName" = Table.AddColumn(
        #"Added LegalForm",
        "CustomerName",
        each
            if [Client] = null then
                null
            else
                let
                    parts = List.Select(Text.Split(Text.Trim([Client]), " "), each _ <> "")
                in
                    if List.Count(parts) <= 1 then Text.Trim([Client]) else Text.Combine(List.Skip(parts, 1), " "),
        type text
    ),

    #"Added CustomerKey" = Table.AddColumn(
        #"Added CustomerName",
        "CustomerKey",
        each
            if [LegalForm] = null and [CustomerName] = null then
                null
            else
                Text.Combine({if [LegalForm] = null then "" else [LegalForm], if [CustomerName] = null then "" else [CustomerName]}, "|"),
        type text
    ),

    #"Added Wilaya" = Table.AddColumn(
        #"Added CustomerKey",
        "Wilaya",
        each
            if [Adresse] = null then
                null
            else
                let
                    tokens = List.Select(List.Transform(Text.Split([Adresse], ","), Text.Trim), each _ <> "")
                in
                    if List.Count(tokens) = 0 then null else List.Last(tokens),
        type text
    ),

    #"Added ProductPrefix" = Table.AddColumn(
        #"Added Wilaya",
        "ProductPrefix",
        each if [Code Produit] = null then null else Text.BeforeDelimiter([Code Produit], "."),
        type text
    ),

    // Prepare map table and merge Category
    #"Typed Product Map" = Table.TransformColumnTypes(
        tblProductCategoryMap_Source,
        {
            {"ProductPrefix", type text},
            {"Category", type text}
        }
    ),

    #"Trimmed Product Map" = Table.TransformColumns(
        #"Typed Product Map",
        {
            {"ProductPrefix", each if _ is null then null else Text.Trim(Text.From(_)), type text},
            {"Category", each if _ is null then null else Text.Trim(Text.From(_)), type text}
        }
    ),

    #"Merged Product Category" = Table.NestedJoin(
        #"Added ProductPrefix",
        {"ProductPrefix"},
        #"Trimmed Product Map",
        {"ProductPrefix"},
        "MapProduct",
        JoinKind.LeftOuter
    ),

    #"Expanded Product Category" = Table.ExpandTableColumn(
        #"Merged Product Category",
        "MapProduct",
        {"Category"},
        {"Category"}
    ),

    // Date helper columns (optional if you choose DAX-only date attributes)
    #"Added Year" = Table.AddColumn(
        #"Expanded Product Category",
        "Year",
        each if [Date.CMD] = null then null else Date.Year([Date.CMD]),
        Int64.Type
    ),

    #"Added MonthNo" = Table.AddColumn(
        #"Added Year",
        "MonthNo",
        each if [Date.CMD] = null then null else Date.Month([Date.CMD]),
        Int64.Type
    ),

    #"Added YearMonth" = Table.AddColumn(
        #"Added MonthNo",
        "YearMonth",
        each if [Date.CMD] = null then null else Date.ToText([Date.CMD], "yyyy-MM"),
        type text
    ),

    #"Reordered Columns" = Table.ReorderColumns(
        #"Added YearMonth",
        {
            "Num.CMD", "Date.CMD", "TypeVenteCode",
            "Client", "LegalForm", "CustomerName", "CustomerKey",
            "Adresse", "Wilaya",
            "Code Produit", "ProductPrefix", "Produit", "Category",
            "Qté", "Montant HT", "Taxe", "Montant TTC",
            "Year", "MonthNo", "YearMonth"
        }
    )
in
    #"Reordered Columns"
