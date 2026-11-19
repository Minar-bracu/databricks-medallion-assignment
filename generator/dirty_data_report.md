# Dirty-data inventory (seed=42)

Percentages are of 1,000,000 data rows per file. Injected rows are disjoint, so each row has at most one injected defect. Duplicate rows are extra rows (copies) counted within the 1,000,000.

## orders.csv

| Type | Field | Rows | % of rows |
|---|---|---:|---:|
| Null/blank value | customer_id | 5,000 | 0.5% |
| Null/blank value | category | 4,000 | 0.4% |
| Null/blank value | country | 3,000 | 0.3% |
| Text inside numeric field | quantity | 4,000 | 0.4% |
| Text inside numeric field | unit_price | 3,000 | 0.3% |
| Negative / out-of-range number | quantity | 4,000 | 0.4% |
| Negative / out-of-range number | unit_price | 3,000 | 0.3% |
| Invalid timestamp/date | order_date | 3,000 | 0.3% |
| Future timestamp/date | order_date | 3,000 | 0.3% |
| Inconsistent case/whitespace | order_status | 20,000 | 2.0% |
| Inconsistent case/whitespace | category | 15,000 | 1.5% |
| Inconsistent case/whitespace | country | 15,000 | 1.5% |
| Invalid label (not an allowed status) | order_status | 2,000 | 0.2% |
| Exact duplicate row | (entire row) | 10,000 | 1.0% |
| Duplicate business key, conflicting content | order_id | 5,000 | 0.5% |
| **Total affected rows** | | **99,000** | **9.9%** |

## transactions.csv

| Type | Field | Rows | % of rows |
|---|---|---:|---:|
| Null/blank value | order_id | 3,000 | 0.3% |
| Null/blank value | payment_method | 4,000 | 0.4% |
| Null/blank value | amount | 3,000 | 0.3% |
| Null/blank value | currency | 2,000 | 0.2% |
| Null/blank value | txn_status | 2,000 | 0.2% |
| Text inside numeric field | amount | 4,000 | 0.4% |
| Negative / out-of-range number | amount | 4,000 | 0.4% |
| Invalid timestamp/date | txn_ts | 3,000 | 0.3% |
| Future timestamp/date | txn_ts | 3,000 | 0.3% |
| Inconsistent case/whitespace | payment_method | 20,000 | 2.0% |
| Inconsistent case/whitespace | txn_status | 20,000 | 2.0% |
| Inconsistent case/whitespace | currency | 15,000 | 1.5% |
| Unsupported currency code | currency | 2,000 | 0.2% |
| Orphan order_id (no matching order) | order_id | 5,000 | 0.5% |
| Exact duplicate row | (entire row) | 10,000 | 1.0% |
| Duplicate business key, conflicting content | txn_id | 5,000 | 0.5% |
| **Total affected rows** | | **105,000** | **10.5%** |

## File facts

| File | Data rows | Bytes | SHA-256 |
|---|---:|---:|---|
| orders.csv | 1,000,000 | 65,678,252 | `22bd861a8f63468592c31aa23829254f53dcd9766de8c91b57151c35bcbf256b` |
| transactions.csv | 1,000,000 | 68,836,646 | `254fd45f4c739ba52acce81b7509610b1f97ed8409722dcdbe94c61d99cc327b` |

## Independent verification (re-read from disk)

| Check | Actual | Expected | OK |
|---|---:|---:|---|
| orders data rows | 1,000,000 | 1,000,000 | PASS |
| transactions data rows | 1,000,000 | 1,000,000 | PASS |
| orders exact duplicate rows | 10,000 | 10,000 | PASS |
| orders surplus rows per duplicated order_id | 15,000 | 15,000 | PASS |
| transactions exact duplicate rows | 10,000 | 10,000 | PASS |
| transactions surplus rows per duplicated txn_id | 15,000 | 15,000 | PASS |
| orders quantity not numeric | 4,000 | 4,000 | PASS |
| orders unit_price not numeric | 3,000 | 3,000 | PASS |
| transactions amount not numeric (text + blank) | 7,000 | 7,000 | PASS |
| orders customer_id blank/null | 5,000 | 5,000 | PASS |
| transactions order_id blank/null | 3,000 | 3,000 | PASS |
| transactions orphan order_id | 5,000 | 5,000 | PASS |
| orders future order_date | 3,000 | 3,000 | PASS |
| orders unparseable order_date | 3,000 | 3,000 | PASS |
| transactions future txn_ts | 3,000 | 3,000 | PASS |
| transactions unparseable txn_ts | 3,000 | 3,000 | PASS |
