# Purchases QA Report

- Checks: 8

| check | severity | status | failed_rows | details |
|---|---|---|---:|---|
| Required columns | ERROR | PASS | 0 | Missing: None |
| Date.CMD parseable | ERROR | PASS | 0 | Date.CMD must be parseable as date |
| QTY > 0 | ERROR | PASS | 0 | QTY must be positive |
| Numeric amounts | ERROR | PASS | 0 | Montant HT/Taxe/Montant TTC must be numeric |
| Montant TTC ~= Montant HT + Taxe | ERROR | PASS | 0 | tolerance=0.01 |
| TypeAchatCode parse | WARN | PASS | 0 | TypeAchatCode parsed from Num.CMD |
| ProductPrefix parse | WARN | PASS | 0 | ProductPrefix parsed from Code Produit |
| Category mapping coverage | WARN | PASS | 0 | Missing prefixes: None |