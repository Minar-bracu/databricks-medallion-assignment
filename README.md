# Databricks Medallion Assignment: Trustworthy E-commerce Lakehouse

**Student:** Minar · **Instructor:** Lipton Ahammed · **Submission date:** 19 November 2026

> **Draft status.** Every number below was taken from runs in my own trial workspace. Items marked **[FILL IN]** or **[CONFIRM]** still need a value or a check before submission. Delete this note when none are left.

---

## 1. Business context

An e-commerce company receives daily CSV extracts of orders and payment transactions. Nulls, text in numeric fields, inconsistent labels, bad timestamps, orphan references and duplicates make sales reports unreliable. This project builds a Bronze → Silver → Gold lakehouse on Databricks that preserves the raw evidence, cleans data with explicit rules, and produces reproducible metrics, reported through Databricks AI/BI and Power BI.

**Flow**

```
orders.csv / transactions.csv (synthetic, 1,000,000 rows each)
  → Unity Catalog volume (raw, unchanged)
  → Bronze Delta tables (all STRING + audit columns)
  → Silver: accepted | quarantine | duplicate losers
  → Gold marts (4 tables + shared revenue view)
  → AI/BI dashboard, Genie, Power BI
  Orchestrated by a Lakeflow Job; governed by Unity Catalog grants.
```

## 2. Trial workspace and environment

| Item | Value |
|---|---|
| Edition | Databricks free trial (not Community Edition, not Free Edition) |
| Signup | Own email address, verified |
| Workspace URL | `https://dbc-1c1095dc-a434.cloud.databricks.com` |
| Cloud / region | AWS / us-east-2 |
| Pricing tier | Premium |
| Compute type | Serverless only (no classic clusters can be created) |
| Trial start | Workspace created Monday 16 November 2026 at 9:57 (derived from "last Monday at 9:57 AM" in the account console; exact signup date not otherwise recorded) |
| Approx. expiry | About 30 November 2026 (start + 14-day credit window) |
| Credits at start / latest check | $400 / $370 remaining (the credits panel showed "updated 3 days ago", so recent usage may not be reflected) |

**Account-limit note.** The workspace is serverless-only, so ETL runs on serverless notebook compute and reporting runs on a SQL warehouse. No payment method was added and the trial was not upgraded. No schedules were enabled.

**Trial vs Free Edition.** The trial is a time-limited, credit-based evaluation of a full Premium workspace. Free Edition is a separate, ongoing free tier with tighter quotas and a reduced feature set. (High-level description only; see Databricks' free trial versus Free Edition documentation for current limits.)

## 3. Governance, naming and paths

| Object | Name |
|---|---|
| Catalog | `workspace` (the only writable non-system catalog; `samples` and `system` are built in) |
| Schema | `workspace.ecom_poc` |
| Managed volume | `workspace.ecom_poc.raw_files` |
| Raw files | `/Volumes/workspace/ecom_poc/raw_files/orders.csv` and `.../transactions.csv` |

**Naming standard.** Lowercase with underscores; project schema `ecom_poc`; layer prefixes `bronze_`, `silver_`, `gold_`; side outputs named `quarantine_*` and `duplicate_*`; audit columns start with an underscore.

Setup SQL: `sql/setup.sql`.

## 4. Compute choices and credit control

- **ETL:** serverless notebook compute. No cluster to configure, billed only while running.
- **BI:** one small SQL warehouse ("Serverless Starter Warehouse": serverless, Small, auto-stop after 10 minutes of inactivity), used by the dashboard, Genie, Power BI loads and ad-hoc SQL.
- **Minimising credits:** one warehouse only, short auto-stop, no parallel experiments, Power BI in Import mode so the warehouse is not needed while building the report, warehouse stopped when finished.

## 5. Git

Repository: https://github.com/Minar-bracu/databricks-medallion-assignment

A Databricks Git folder was linked to this GitHub repository and notebooks were pushed from it. Limitation to disclose: I developed in the workspace first and committed afterwards, so the commit history shows the work grouped by stage on the day of submission rather than as it was developed.

## 6. Synthetic source files

The generator is `generator/generate_data.py` (seed **42**, so the output is reproducible). It writes exactly 1,000,000 data rows per file, plus a dirty-data inventory and an independent verification pass that re-reads the files and checks every count (all 16 checks passed).

| File | Data rows (excl. header) | Bytes | Path |
|---|---:|---:|---|
| orders.csv | 1,000,000 | 65,678,252 | `/Volumes/workspace/ecom_poc/raw_files/orders.csv` |
| transactions.csv | 1,000,000 | 68,836,646 | `/Volumes/workspace/ecom_poc/raw_files/transactions.csv` |

Row counts were measured in Databricks with `read_files(...)` (`sql/source_row_counts.sql`), and the byte sizes with `LIST` on the volume.

### Dirty-data inventory

Each injected defect is placed on a disjoint set of rows, so every count is exact. Percentages are of 1,000,000 rows.

**orders.csv**

| Type | Field | Rows | % |
|---|---|---:|---:|
| Null/blank | customer_id | 5,000 | 0.5 |
| Null/blank | category | 4,000 | 0.4 |
| Null/blank | country | 3,000 | 0.3 |
| Text in numeric | quantity | 4,000 | 0.4 |
| Text in numeric | unit_price | 3,000 | 0.3 |
| Negative/out-of-range | quantity | 4,000 | 0.4 |
| Negative/out-of-range | unit_price | 3,000 | 0.3 |
| Invalid date | order_date | 3,000 | 0.3 |
| Future date | order_date | 3,000 | 0.3 |
| Case/whitespace | order_status | 20,000 | 2.0 |
| Case/whitespace | category | 15,000 | 1.5 |
| Case/whitespace | country | 15,000 | 1.5 |
| Invalid label | order_status | 2,000 | 0.2 |
| Exact duplicate rows | all columns | 10,000 | 1.0 |
| Duplicate key, conflicting content | order_id | 5,000 | 0.5 |

**transactions.csv**

| Type | Field | Rows | % |
|---|---|---:|---:|
| Null/blank | order_id | 3,000 | 0.3 |
| Null/blank | payment_method | 4,000 | 0.4 |
| Null/blank | amount | 3,000 | 0.3 |
| Null/blank | currency | 2,000 | 0.2 |
| Null/blank | txn_status | 2,000 | 0.2 |
| Text in numeric | amount | 4,000 | 0.4 |
| Negative/out-of-range | amount | 4,000 | 0.4 |
| Invalid timestamp | txn_ts | 3,000 | 0.3 |
| Future timestamp | txn_ts | 3,000 | 0.3 |
| Case/whitespace | payment_method | 20,000 | 2.0 |
| Case/whitespace | txn_status | 20,000 | 2.0 |
| Case/whitespace | currency | 15,000 | 1.5 |
| Unsupported currency | currency | 2,000 | 0.2 |
| Orphan order_id | order_id | 5,000 | 0.5 |
| Exact duplicate rows | all columns | 10,000 | 1.0 |
| Duplicate key, conflicting content | txn_id | 5,000 | 0.5 |

Full machine-readable version: `generator/dirty_data_inventory.csv` and `generator/dirty_data_report.md`.

**Why must anomalies stay a small, measured fraction?** Real data is mostly valid. If most rows were dirty, the data would be unrealistic, the cleaning rules could not be tested meaningfully, analytics would be dominated by rejects, and the share of rejected rows (a data-quality KPI) would carry no information. Measuring the injected fraction also gives exact expected counts to test each rule against.

**Why real data, credentials and raw extracts must not be committed to Git.** Git history is permanent and widely copied, so anything committed (personal data, tokens, raw extracts) can be recovered even after deletion and may leak through forks, clones and public hosting. Raw extracts are also very large. Here the data is synthetic, the two CSVs are excluded by `.gitignore`, and only the seeded generator is versioned so the data can be recreated.

**Minimum production controls.** Secrets in a secret manager (never in code or notebooks); least-privilege access with Unity Catalog grants; `.gitignore` plus pre-commit secret scanning; short-lived, narrowly scoped tokens; raw data kept in governed storage with access logging; masking or tokenising personal data; retention rules; branch protection and code review.

## 7. Bronze: lossless ingestion

Notebook: `notebooks/01_bronze_ingestion`. Each CSV is read with `read_files` using an explicit schema in which **every column is STRING** (no schema inference), then saved as its own Delta table: `bronze_orders` and `bronze_transactions`. The option `nullValue => '__NO_NULL__'` keeps blank cells as empty strings so Bronze matches the file exactly.

**Why malformed data belongs in Bronze.** Bronze is the system of record for what actually arrived. Rejecting at the door would lose evidence, make rejected rows impossible to count or explain, and make it impossible to fix a rule later and reprocess. Bad rows are handled explicitly in Silver instead.

**Audit fields**

| Column | Meaning |
|---|---|
| `_ingested_at` | Timestamp of the load |
| `_source_file` | Path of the source file for the row (reported with a `dbfs:/Volumes/...` prefix) |
| `_batch_id` | Label of the load run (`orders_batch_20261118_001`, `transactions_batch_20261118_001`) |
| `_row_hash` | SHA-256 of all source values in the row; identifies identical content and is the deterministic tie-breaker in Silver |

**Lossless proof**

| Dataset | Source rows | Bronze rows |
|---|---:|---:|
| orders | 1,000,000 | 1,000,000 |
| transactions | 1,000,000 | 1,000,000 |

**Idempotent loading.** Each Bronze table is created with `CREATE OR REPLACE TABLE ... AS SELECT`, so re-running the notebook replaces the table instead of appending. I re-ran the load and the counts stayed at 1,000,000.

## 8. Silver: cleaning, validation and reconciliation

Notebooks: `notebooks/02_silver_orders` and `notebooks/03_silver_transactions`.

**Processing precedence.** (1) Clean and safely convert types, (2) validate every rule, sending failures to quarantine, (3) deduplicate among valid rows only. Each Bronze row therefore lands in exactly one bucket.

**Safe parsing.** `try_cast` and `try_to_date` / `try_to_timestamp` return NULL for strings that cannot be converted instead of failing the job. A NULL in a required field then fails a rule and the row goes to quarantine with a reason (for example `QUANTITY_NOT_NUMERIC`). Case and whitespace issues are cleaned (trimmed, standardised) rather than rejected.

### Rules matrix: orders

| Field | Rule | Rejection reason |
|---|---|---|
| order_id | not blank | MISSING_ORDER_ID |
| customer_id | not blank | MISSING_CUSTOMER_ID |
| category | not blank; one of 8 known categories | MISSING_CATEGORY / INVALID_CATEGORY |
| country | not blank; one of 10 known codes | MISSING_COUNTRY / INVALID_COUNTRY |
| order_status | PLACED, PAID, SHIPPED, DELIVERED, CANCELLED, RETURNED | INVALID_ORDER_STATUS |
| quantity | integer | QUANTITY_NOT_NUMERIC |
| quantity | 1 to 1000 | QUANTITY_OUT_OF_RANGE |
| unit_price | decimal | UNIT_PRICE_NOT_NUMERIC |
| unit_price | 0.01 to 100,000 | UNIT_PRICE_OUT_OF_RANGE |
| order_date | valid `yyyy-MM-dd` | ORDER_DATE_INVALID |
| order_date | not in the future | ORDER_DATE_FUTURE |

### Rules matrix: transactions

| Field | Rule | Rejection reason |
|---|---|---|
| txn_id | not blank | MISSING_TXN_ID |
| order_id | not blank; exists in orders | MISSING_ORDER_ID / ORPHAN_ORDER_ID |
| payment_method | CARD, PAYPAL, BANK_TRANSFER, WALLET, COD | MISSING_PAYMENT_METHOD / INVALID_PAYMENT_METHOD |
| amount | decimal | AMOUNT_NOT_NUMERIC |
| amount | 0.01 to 10,000,000 | AMOUNT_OUT_OF_RANGE |
| currency | USD, EUR, GBP, BDT | MISSING_CURRENCY / UNSUPPORTED_CURRENCY |
| txn_status | SUCCESS, FAILED, PENDING, REFUNDED | INVALID_TXN_STATUS |
| txn_ts | valid `yyyy-MM-dd HH:mm:ss` | TXN_TS_INVALID |
| txn_ts | not in the future | TXN_TS_FUTURE |

A row can break several rules; `rejection_reason` lists all of them separated by `;`.

**Orphan rule design decision.** A transaction is an orphan if its `order_id` matches **no order in the orders data** (Bronze). A payment for an order that exists but was itself quarantined is not an orphan; it is excluded from revenue later because Gold joins to `silver_orders`.

**Keep-one rule.** Among valid rows sharing a business key (`order_id` or `txn_id`), `ROW_NUMBER() OVER (PARTITION BY key ORDER BY _row_hash ASC)`; row number 1 is kept and the rest are duplicate losers. This is deterministic. **Exact duplicate rows** have identical content (same `_row_hash`), so the choice among them is immaterial. **Duplicate keys** have the same key but different content, so the hash rule decides the winner.

### Reconciliation (Bronze = accepted + quarantined + duplicate losers)

| Dataset | Bronze | Accepted (Silver) | Quarantined | Duplicate losers | Total | Reconciles |
|---|---:|---:|---:|---:|---:|---|
| orders | 1,000,000 | 951,000 | 34,000 | 15,000 | 1,000,000 | true |
| transactions | 1,000,000 | 950,000 | 35,000 | 15,000 | 1,000,000 | true |

No row is in two buckets because quarantine takes `rejection_reason <> ''`, the rest are ranked, and rank 1 versus rank > 1 splits them.

Tables: `silver_orders`, `silver_transactions`, `quarantine_orders`, `quarantine_transactions`, `duplicate_orders`, `duplicate_transactions`. Audit columns (`_ingested_at`, `_source_file`, `_batch_id`, `_row_hash`) are preserved in every outcome table.

## 9. Gold: business-ready models

Notebook: `notebooks/04_gold`.

### Revenue definition

| Question | Decision |
|---|---|
| Source of truth | `silver_transactions` joined to `silver_orders` on `order_id` |
| Eligible payments | `txn_status = 'SUCCESS'` only; FAILED, PENDING and REFUNDED add nothing |
| Eligible orders | order status not `CANCELLED` or `RETURNED` |
| Refunds / cancellations | Excluded by status; revenue is not netted further |
| Currency | Converted to USD at fixed assumed rates: 1 USD = 0.92 EUR = 0.79 GBP = 110 BDT |
| Partial / repeat payments | Each successful payment (`txn_id`) counts once at the amount received; amounts are not compared to quantity × price |
| Dating | Revenue belongs to the order's `order_date` |
| Rounding | Each payment rounded to 2 decimals in USD; every report sums that stored column |

**Example.** A SUCCESS payment of 92.00 EUR on a SHIPPED order counts as 100.00 USD. A FAILED payment counts 0. A SUCCESS payment on a CANCELLED order counts 0.

The definition lives in one place, the view `gold_revenue_base`, and all Gold revenue numbers read from it.

### Gold outputs

| Table | Grain (one row per) | Unique key | Rows |
|---|---|---|---:|
| `gold_daily_sales` | order date | `order_date` | 684 |
| `gold_revenue_breakdown` | order date × category × country | those 3 columns | 54,522 |
| `gold_payment_success` | transaction date × payment method | those 2 columns | 3,425 |
| `gold_top_customers` | customer (top 100 by revenue) | `customer_id` | 100 |

Other metric assumptions: `cancellation_rate` = cancelled orders / all accepted orders; `success_rate` = SUCCESS transactions / all transactions in the group; `gold_payment_success` uses transaction date while the revenue tables use order date.

**No multiplication.** Orders and revenue are aggregated separately and joined by date. Silver guarantees one row per `order_id` and per `txn_id`, so the many-to-one join cannot multiply payments. Total revenue is identical in the base view, daily sales and the breakdown: **92,181,483.93 USD**.

**How documentation prevents misinterpretation.** Table and column comments state grain, key and metric definitions in Catalog Explorer, so a reader cannot, for example, average daily rates by mistake, sum a table at the wrong grain, or mix order-dated and transaction-dated figures.

## 10. Databricks AI/BI and Genie

**Dashboard** (`dashboards/`): four counters (Total Revenue USD, Total Orders, Cancellation Rate, Payment Success Rate), a daily revenue trend, revenue by category, payment success rate by method, and a shared date filter. Link: https://dbc-1c1095dc-a434.cloud.databricks.com/dashboardsv3/01f1e351514312588afdf5c3a8ad08c5/published?o=7474648792875588 (published dashboard; viewing requires access to the workspace; an export is included in `dashboards/`). How it was built: created in Databricks with Genie assistance, then checked against SQL (reference values: 92,181,483.93 USD revenue, 951,000 orders, 10% cancellation rate, 81.82% payment success rate).

Note: payment success is about 82% for every payment method because the generator assigned payment status independently of the method. This is a property of the synthetic data, not a dashboard error.

**Genie Agent.** A Genie Agent over the four Gold tables was asked three business questions. Each answer was cross-checked with my own SQL (`sql/genie_verification.sql`).

| # | Question asked | Genie's answer | Verification SQL | Result |
|---|---|---|---|---|
| 1 | Which product category generated the highest total revenue? | Electronics, $51.43M (next: Home & Kitchen $11.62M, Clothing $11.58M) | `SELECT category, SUM(revenue_usd) AS revenue FROM workspace.ecom_poc.gold_revenue_breakdown GROUP BY category ORDER BY revenue DESC LIMIT 3;` | **[CONFIRM: matches]** |
| 2 | Who is our number one customer by total spend? | CUST-000001: $109,623.92 across 705 paid orders (729 successful payments) | `SELECT customer_id, revenue_usd, paid_orders, successful_payments FROM workspace.ecom_poc.gold_top_customers WHERE spend_rank = 1;` | **[CONFIRM: matches]** |
| 3 | How many total successful transactions were processed? | 777,333 | `SELECT SUM(success_txns) FROM workspace.ecom_poc.gold_payment_success;` and `SELECT COUNT(*) FROM workspace.ecom_poc.silver_transactions WHERE txn_status = 'SUCCESS';` | **[CONFIRM: matches]** |

Note on question 3: this counts all accepted SUCCESS transactions. It is larger than the number of payments counted in revenue (`gold_revenue_base`), which additionally excludes payments on cancelled or returned orders. The two figures answer different questions and are not expected to be equal.

## 11. Power BI

- **Connection:** Power BI Desktop native Databricks connector to the SQL warehouse, **Import** mode, Gold tables only (`gold_daily_sales`, `gold_revenue_breakdown`, `gold_payment_success`, `gold_top_customers`).
- **Measures:** Total Revenue USD, Total Orders, Cancellation Rate, Payment Success Rate, Category Revenue USD (same definitions as the dashboard: totals divided by totals).
- **Build:** the Power BI report and its measures were built by hand in Power BI Desktop.
- **Report:** one page with four KPI cards, a daily revenue trend, a revenue-by-category chart, and date and category slicers. Files: `powerbi/`.

**Import vs DirectQuery**

| | Import | DirectQuery |
|---|---|---|
| Data | copied into the `.pbix` | queried live from the warehouse |
| Speed | fast, offline | depends on the warehouse, a query per interaction |
| Credits | warehouse needed only at load/refresh | warehouse used on every interaction |
| Freshness | stale until refresh | always current |

**Chosen: Import.** The Gold tables are small and only change when the pipeline runs, and Import avoids spending trial credits on every click.

Limitation: no relationships were created between the Gold tables (different grains), so each slicer filters only visuals built from its own table.

### Three-way revenue check

| Source | Date range | Currency | Total revenue |
|---|---|---|---:|
| SQL query | 1 Jan to 31 Mar 2026 | USD | 12,029,477.02 |
| AI/BI dashboard | 1 Jan to 31 Mar 2026 | USD | 12,029,477.02 |
| Power BI | 1 Jan to 31 Mar 2026 | USD | 12,029,477.02 |
| SQL query | all dates | USD | 92,181,483.93 |
| AI/BI dashboard | all dates | USD | 92,181,483.93 |
| Power BI | all dates | USD | 92,181,483.93 |

All sources apply the same revenue definition, so no mismatch needed diagnosing. **[Add any discrepancy found and its explanation, if applicable.]**

## 12. Lakeflow Job

Job `ecom_medallion_pipeline` (serverless compute, no schedule):

| Task | Notebook | Depends on |
|---|---|---|
| `bronze_ingest` | 01_bronze_ingestion | none |
| `silver_orders` | 02_silver_orders | bronze_ingest |
| `silver_transactions` | 03_silver_transactions | silver_orders |
| `gold_marts` | 04_gold | silver_transactions |

Retries: 1 per task, 60 s apart (confirmed in the exported YAML: `max_retries: 1`, `min_retry_interval_millis: 60000`). Failure notification to the owner's email. Run result: the job was run manually once and all four tasks succeeded. Config: `operations/JobPipeline.yaml`.

**Why Gold does not run after a failed dependency.** By default a task starts only after all upstream tasks succeed. A failure upstream skips Gold, so reports are never rebuilt from stale or incomplete data.

**Safe to re-run.** Every notebook uses `CREATE OR REPLACE`, so repeated runs rebuild rather than append.

## 13. Security: least-privilege reporting access

A group `reporting_users` was created (**[CONFIRM entitlements: Databricks SQL access on, admin access off]**) and granted only what reporting needs (`sql/grants.sql`):

```sql
GRANT USE CATALOG ON CATALOG workspace TO `reporting_users`;
GRANT USE SCHEMA  ON SCHEMA  workspace.ecom_poc TO `reporting_users`;
GRANT SELECT ON TABLE workspace.ecom_poc.gold_daily_sales       TO `reporting_users`;
GRANT SELECT ON TABLE workspace.ecom_poc.gold_revenue_breakdown TO `reporting_users`;
GRANT SELECT ON TABLE workspace.ecom_poc.gold_payment_success   TO `reporting_users`;
GRANT SELECT ON TABLE workspace.ecom_poc.gold_top_customers     TO `reporting_users`;
```

`SHOW GRANTS` confirmed `USE SCHEMA` on the schema and `SELECT` on the Gold tables. Bronze, Silver, quarantine, duplicate tables and the raw volume are not granted.

**Test plan (not executed, since the group has no member):** signed in as a member, `SELECT` from a Gold table should succeed; `SELECT` from `silver_orders` or `quarantine_orders`, `DROP TABLE` on a Gold table, and browsing the raw volume should all fail with permission errors. Members also need *Can use* on a SQL warehouse.

## 14. Cleanup checklist (`operations/cleanup_checklist.md`)

- [x] SQL warehouse stopped (status "Stopped" confirmed)
- [ ] No schedules enabled (job has none; dashboard has no scheduled refresh)
- [x] Remaining trial credits recorded: $370 of $400 (panel updated 3 days earlier)
- [ ] Notebooks, job YAML, dashboard export and `.pbix` saved in Git
- [ ] All commits pushed
- [ ] Repository checked: no tokens, account IDs, secrets or personal email addresses

## 15. Disclosures and limitations

- Serverless-only workspace; no classic compute.
- Fixed assumed FX rates are used for USD conversion.
- The synthetic data makes payment success the same for every method.
- Orphan checks are against all Bronze orders; payments for quarantined orders are excluded from revenue through the Gold join.
- Power BI slicers filter only their own table (no relationships between Gold tables).
- Git history was created at the end of development.
- The reporting-access test plan was not executed with a signed-in member.

## 16. Repository layout

```
README.md
.gitignore
generator/    generate_data.py, dirty_data_report.md, dirty_data_inventory.csv
notebooks/    01_bronze_ingestion, 02_silver_orders, 03_silver_transactions, 04_gold
sql/          setup, source_row_counts, rules, grants, silver evidence, cross-tool validation
dashboards/   dashboard export, Genie checks
powerbi/      `.pbix`
evidence/     topic-labelled output snippets and query results
operations/   JobPipeline.yaml, cleanup_checklist.md
```

The two source CSVs are intentionally not in Git.
