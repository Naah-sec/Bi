# Inventory QA Report

- Checks: 6

| check | severity | status | failed_rows | details |
|---|---|---|---:|---|
| sale_qty <= stock_qty_before | ERROR | FAIL | 1 | Sale quantity cannot exceed available stock |
| purchase_qty > 0 | ERROR | PASS | 0 | Purchase quantity must be > 0 |
| sale_qty > 0 | ERROR | PASS | 0 | Sale quantity must be > 0 |
| revenue = sale_unit_price * sale_qty | ERROR | PASS | 0 | tolerance=0.01 |
| purchase_value = purchase_unit_price * purchase_qty | ERROR | PASS | 0 | tolerance=0.01 |
| Rows excluded from margin calculation | WARN | WARN | 1 | Invalid rows are flagged and excluded from gross margin aggregation |