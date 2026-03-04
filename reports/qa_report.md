# Sales QA Report

- Checks: 5

| check | severity | status | failed_rows | details |
|---|---|---|---:|---|
| Numeric parsing for amounts | ERROR | PASS | 0 | amount_ht, tax_amount, amount_ttc should not be null |
| qty > 0 | ERROR | PASS | 0 | qty must be strictly positive |
| date_cmd non-null | ERROR | PASS | 0 | Date.CMD must be parseable as date |
| amount_ttc ~= amount_ht + tax_amount | ERROR | PASS | 0 | tolerance=0.01 |
| Missing category mappings | WARN | PASS | 0 | Missing prefixes: None |