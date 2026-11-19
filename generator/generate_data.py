#!/usr/bin/env python3
"""
Seeded synthetic e-commerce data generator
(Databricks Medallion Assignment: orders.csv + transactions.csv)

- Exactly 1,000,000 DATA rows per file (+ header), fixed random seed -> reproducible.
- Dirty data is injected into DISJOINT row sets, so every inventory count is exact.
- Duplicate source rows are taken only from rows that were not otherwise dirtied.
- Writes a dirty-data inventory (CSV + Markdown) and an independent verification
  pass that re-reads the written files and checks counts.

Usage:  python generate_data.py --out ../data --seed 42
No real customer data is used. Never commit the generated CSVs to Git.
"""
import argparse
import hashlib
import json
import os

import numpy as np
import pandas as pd

N_ROWS = 1_000_000
START = np.datetime64("2025-01-01")
END = np.datetime64("2026-11-15")          # last valid order date
TODAY = "2026-11-18"                        # "future" = after this date

CATEGORIES = ["Electronics", "Clothing", "Home & Kitchen", "Books",
              "Beauty", "Sports & Outdoors", "Toys", "Grocery"]
CAT_P = [0.18, 0.20, 0.15, 0.08, 0.10, 0.10, 0.07, 0.12]
CAT_BASE_PRICE = np.array([220, 45, 60, 18, 30, 55, 28, 14], dtype=float)
COUNTRIES = ["US", "GB", "DE", "FR", "CA", "AU", "IN", "BD", "SG", "JP"]
COUNTRY_P = [0.30, 0.10, 0.09, 0.07, 0.08, 0.06, 0.12, 0.08, 0.05, 0.05]
ORDER_STATUS = ["PLACED", "PAID", "SHIPPED", "DELIVERED", "CANCELLED", "RETURNED"]
ORDER_STATUS_P = [0.05, 0.10, 0.15, 0.55, 0.10, 0.05]
PAY_METHODS = ["CARD", "PAYPAL", "BANK_TRANSFER", "WALLET", "COD"]
PAY_P = [0.55, 0.18, 0.10, 0.12, 0.05]
CURRENCIES = ["USD", "EUR", "GBP", "BDT"]
CUR_P = [0.90, 0.05, 0.03, 0.02]
FX = {"USD": 1.0, "EUR": 0.92, "GBP": 0.79, "BDT": 110.0}
TXN_STATUS = ["SUCCESS", "FAILED", "PENDING", "REFUNDED"]
TXN_STATUS_P = [0.82, 0.08, 0.05, 0.05]
N_CUSTOMERS = 200_000

BLANKS = ["", "NULL", "null", "None"]
BAD_DATES = ["2025-13-45", "31/02/2025", "not_a_date", "0000-00-00", "2025/02/30"]
BAD_TS = ["2025-02-30 10:00:00", "not_a_timestamp", "31/13/2025 25:61:00", "0000-00-00 00:00:00"]
TEXT_QTY = ["two", "N/A", "abc", "1O", "many"]
TEXT_PRICE = ["free", "N/A", "abc", "$19.99", "TBD"]
TEXT_AMOUNT = ["N/A", "abc", "free", "USD 12.50", "TBD"]


class Carver:
    """Hands out disjoint row-index slices from one random permutation."""
    def __init__(self, rng, n):
        self.perm = rng.permutation(n)
        self.pos = 0

    def take(self, count):
        s = self.perm[self.pos:self.pos + count]
        self.pos += count
        return s

    def rest(self):
        return self.perm[self.pos:]


def messy_case(vals, rng):
    """Inconsistent case / whitespace variants of the given strings."""
    out = np.empty(len(vals), dtype=object)
    kinds = rng.integers(0, 4, len(vals))
    for i, (s, k) in enumerate(zip(vals, kinds)):
        s = str(s)
        out[i] = (s.lower() if k == 0 else
                  s.title() if k == 1 else
                  "  " + s if k == 2 else
                  s.lower() + "   ")
    return out


def ids(prefix, nums, width):
    return np.array([f"{prefix}{n:0{width}d}" for n in nums], dtype=object)


def fmt2(a):
    return np.array([f"{x:.2f}" for x in a], dtype=object)


def count(rate):
    return int(round(rate * N_ROWS))


def build_orders(rng, inv):
    n_exact, n_key = count(0.010), count(0.005)
    n = N_ROWS - n_exact - n_key

    cat_idx = rng.choice(len(CATEGORIES), n, p=CAT_P)
    qty = rng.choice([1, 2, 3, 4, 5], n, p=[0.55, 0.22, 0.12, 0.07, 0.04])
    price = np.clip(np.round(CAT_BASE_PRICE[cat_idx] * rng.lognormal(0, 0.45, n), 2), 1.0, 5000.0)
    days = rng.integers(0, int((END - START).astype(int)) + 1, n)
    dates = START + days.astype("timedelta64[D]")

    clean = pd.DataFrame({
        "order_id": ids("ORD-", np.arange(1, n + 1), 7),
        "customer_id": ids("CUST-", (N_CUSTOMERS * rng.random(n) ** 1.8).astype(int) + 1, 6),
        "order_date": np.datetime_as_string(dates, unit="D").astype(object),
        "category": np.array(CATEGORIES, dtype=object)[cat_idx],
        "quantity": qty.astype(str).astype(object),
        "unit_price": fmt2(price),
        "order_status": rng.choice(ORDER_STATUS, n, p=ORDER_STATUS_P).astype(object),
        "country": rng.choice(COUNTRIES, n, p=COUNTRY_P).astype(object),
    })
    df = clean.copy()
    carve = Carver(rng, n)

    def inject(cat, field, rate, fn):
        idx = carve.take(count(rate))
        df.loc[idx, field] = fn(idx)
        inv.append(dict(file="orders.csv", category=cat, field=field,
                        rows=len(idx), pct=round(100 * len(idx) / N_ROWS, 3)))

    inject("Null/blank value", "customer_id", 0.005, lambda i: rng.choice(BLANKS, len(i)))
    inject("Null/blank value", "category", 0.004, lambda i: rng.choice(BLANKS, len(i)))
    inject("Null/blank value", "country", 0.003, lambda i: rng.choice(BLANKS, len(i)))
    inject("Text inside numeric field", "quantity", 0.004, lambda i: rng.choice(TEXT_QTY, len(i)))
    inject("Text inside numeric field", "unit_price", 0.003, lambda i: rng.choice(TEXT_PRICE, len(i)))
    inject("Negative / out-of-range number", "quantity", 0.004,
           lambda i: rng.choice(["0", "-1", "-3", "5000", "99999"], len(i)))
    inject("Negative / out-of-range number", "unit_price", 0.003,
           lambda i: rng.choice(["-9.99", "0.00", "-100.00", "999999.99"], len(i)))
    inject("Invalid timestamp/date", "order_date", 0.003, lambda i: rng.choice(BAD_DATES, len(i)))
    inject("Future timestamp/date", "order_date", 0.003,
           lambda i: np.datetime_as_string(np.datetime64("2027-01-01") +
                                           rng.integers(0, 1000, len(i)).astype("timedelta64[D]"),
                                           unit="D").astype(object))
    inject("Inconsistent case/whitespace", "order_status", 0.020,
           lambda i: messy_case(df.loc[i, "order_status"].values, rng))
    inject("Inconsistent case/whitespace", "category", 0.015,
           lambda i: messy_case(df.loc[i, "category"].values, rng))
    inject("Inconsistent case/whitespace", "country", 0.015,
           lambda i: messy_case(df.loc[i, "country"].values, rng))
    inject("Invalid label (not an allowed status)", "order_status", 0.002,
           lambda i: rng.choice(["UNKNOWN", "DELIVERD", "SHIPED", "???"], len(i)))

    # duplicates: sources come from untouched rows only
    src = rng.choice(carve.rest(), n_exact + n_key, replace=False)
    exact = df.loc[src[:n_exact]].copy()
    keyd = df.loc[src[n_exact:]].copy()
    # guarantee conflicting content: quantity and status always differ from the original row
    keyd["quantity"] = [str(int(q) % 5 + 1) for q in keyd["quantity"]]
    keyd["order_status"] = [ORDER_STATUS[(ORDER_STATUS.index(x) + 1 + int(rng.integers(0, 5))) % 6]
                            for x in keyd["order_status"]]
    inv.append(dict(file="orders.csv", category="Exact duplicate row", field="(entire row)",
                    rows=n_exact, pct=round(100 * n_exact / N_ROWS, 3)))
    inv.append(dict(file="orders.csv", category="Duplicate business key, conflicting content",
                    field="order_id", rows=n_key, pct=round(100 * n_key / N_ROWS, 3)))

    out = pd.concat([df, exact, keyd], ignore_index=True)
    out = out.iloc[rng.permutation(len(out))].reset_index(drop=True)
    assert len(out) == N_ROWS
    return out, clean, price, qty


def build_transactions(rng, inv, clean_orders, price, qty):
    n_exact, n_key = count(0.010), count(0.005)
    n = N_ROWS - n_exact - n_key
    n_orders = len(clean_orders)

    first = int(0.96 * n)   # 96% one payment per order; 4% repeat/retry payments
    ord_idx = np.concatenate([rng.permutation(n_orders)[:first],
                              rng.integers(0, n_orders, n - first)])
    cur = rng.choice(CURRENCIES, n, p=CUR_P)
    fx = np.array([FX[c] for c in cur])
    amount = np.round(qty[ord_idx] * price[ord_idx] * fx, 2)

    odates = np.array(clean_orders["order_date"].values[ord_idx], dtype="datetime64[s]")
    ts = odates + rng.integers(0, 172_800, n).astype("timedelta64[s]")
    ts_str = np.char.replace(np.datetime_as_string(ts, unit="s"), "T", " ").astype(object)

    clean = pd.DataFrame({
        "txn_id": ids("TXN-", np.arange(1, n + 1), 7),
        "order_id": clean_orders["order_id"].values[ord_idx],
        "payment_method": rng.choice(PAY_METHODS, n, p=PAY_P).astype(object),
        "amount": fmt2(amount),
        "currency": cur.astype(object),
        "txn_status": rng.choice(TXN_STATUS, n, p=TXN_STATUS_P).astype(object),
        "txn_ts": ts_str,
    })
    df = clean.copy()
    carve = Carver(rng, n)

    def inject(cat, field, rate, fn):
        idx = carve.take(count(rate))
        df.loc[idx, field] = fn(idx)
        inv.append(dict(file="transactions.csv", category=cat, field=field,
                        rows=len(idx), pct=round(100 * len(idx) / N_ROWS, 3)))

    inject("Null/blank value", "order_id", 0.003, lambda i: rng.choice(["", "NULL"], len(i)))
    inject("Null/blank value", "payment_method", 0.004, lambda i: rng.choice(BLANKS, len(i)))
    inject("Null/blank value", "amount", 0.003, lambda i: rng.choice(BLANKS, len(i)))
    inject("Null/blank value", "currency", 0.002, lambda i: rng.choice(BLANKS, len(i)))
    inject("Null/blank value", "txn_status", 0.002, lambda i: rng.choice(BLANKS, len(i)))
    inject("Text inside numeric field", "amount", 0.004, lambda i: rng.choice(TEXT_AMOUNT, len(i)))

    def bad_amount(i):
        a = amount[i]
        k = rng.integers(0, 3, len(i))
        return np.where(k == 0, [f"{-x:.2f}" for x in a],
                        np.where(k == 1, "0.00", "99999999.99")).astype(object)
    inject("Negative / out-of-range number", "amount", 0.004, bad_amount)
    inject("Invalid timestamp/date", "txn_ts", 0.003, lambda i: rng.choice(BAD_TS, len(i)))
    inject("Future timestamp/date", "txn_ts", 0.003,
           lambda i: np.char.replace(np.datetime_as_string(
               np.datetime64("2027-01-01T00:00:00") + rng.integers(0, 86_400 * 900, len(i)).astype("timedelta64[s]"),
               unit="s"), "T", " ").astype(object))
    inject("Inconsistent case/whitespace", "payment_method", 0.020,
           lambda i: messy_case(df.loc[i, "payment_method"].values, rng))
    inject("Inconsistent case/whitespace", "txn_status", 0.020,
           lambda i: messy_case(df.loc[i, "txn_status"].values, rng))
    inject("Inconsistent case/whitespace", "currency", 0.015,
           lambda i: messy_case(df.loc[i, "currency"].values, rng))
    inject("Unsupported currency code", "currency", 0.002, lambda i: rng.choice(["XXX", "ZZZ", "BTC"], len(i)))
    inject("Orphan order_id (no matching order)", "order_id", 0.005,
           lambda i: ids("ORD-", rng.integers(9_000_000, 9_999_999, len(i)), 7))

    src = rng.choice(carve.rest(), n_exact + n_key, replace=False)
    exact = df.loc[src[:n_exact]].copy()
    keyd = df.loc[src[n_exact:]].copy()
    keyd["amount"] = fmt2(np.round(amount[src[n_exact:]] * 1.10, 2))
    keyd["txn_status"] = rng.choice(TXN_STATUS, len(keyd))
    inv.append(dict(file="transactions.csv", category="Exact duplicate row", field="(entire row)",
                    rows=n_exact, pct=round(100 * n_exact / N_ROWS, 3)))
    inv.append(dict(file="transactions.csv", category="Duplicate business key, conflicting content",
                    field="txn_id", rows=n_key, pct=round(100 * n_key / N_ROWS, 3)))

    out = pd.concat([df, exact, keyd], ignore_index=True)
    out = out.iloc[rng.permutation(len(out))].reset_index(drop=True)
    assert len(out) == N_ROWS
    return out


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify(out_dir, inv):
    """Independent re-read of the written files; returns list of check dicts."""
    o = pd.read_csv(os.path.join(out_dir, "orders.csv"), dtype=str, keep_default_na=False)
    t = pd.read_csv(os.path.join(out_dir, "transactions.csv"), dtype=str, keep_default_na=False)
    exp = {(r["file"], r["category"], r["field"]): r["rows"] for r in inv}
    blank = {"", "NULL", "null", "None"}
    checks = []

    def chk(name, actual, expected):
        checks.append(dict(check=name, actual=int(actual), expected=int(expected),
                           ok=bool(actual == expected)))

    chk("orders data rows", len(o), N_ROWS)
    chk("transactions data rows", len(t), N_ROWS)
    chk("orders exact duplicate rows", o.duplicated().sum(),
        exp[("orders.csv", "Exact duplicate row", "(entire row)")])
    chk("orders surplus rows per duplicated order_id", len(o) - o["order_id"].nunique(),
        exp[("orders.csv", "Exact duplicate row", "(entire row)")] +
        exp[("orders.csv", "Duplicate business key, conflicting content", "order_id")])
    chk("transactions exact duplicate rows", t.duplicated().sum(),
        exp[("transactions.csv", "Exact duplicate row", "(entire row)")])
    chk("transactions surplus rows per duplicated txn_id", len(t) - t["txn_id"].nunique(),
        exp[("transactions.csv", "Exact duplicate row", "(entire row)")] +
        exp[("transactions.csv", "Duplicate business key, conflicting content", "txn_id")])
    chk("orders quantity not numeric", pd.to_numeric(o["quantity"], errors="coerce").isna().sum(),
        exp[("orders.csv", "Text inside numeric field", "quantity")])
    chk("orders unit_price not numeric", pd.to_numeric(o["unit_price"], errors="coerce").isna().sum(),
        exp[("orders.csv", "Text inside numeric field", "unit_price")])
    amt = pd.to_numeric(t["amount"], errors="coerce")
    chk("transactions amount not numeric (text + blank)", amt.isna().sum(),
        exp[("transactions.csv", "Text inside numeric field", "amount")] +
        exp[("transactions.csv", "Null/blank value", "amount")])
    chk("orders customer_id blank/null", o["customer_id"].isin(blank).sum(),
        exp[("orders.csv", "Null/blank value", "customer_id")])
    chk("transactions order_id blank/null", t["order_id"].isin({"", "NULL"}).sum(),
        exp[("transactions.csv", "Null/blank value", "order_id")])
    orphans = (~t["order_id"].isin(set(o["order_id"]))) & (~t["order_id"].isin({"", "NULL"}))
    chk("transactions orphan order_id", orphans.sum(),
        exp[("transactions.csv", "Orphan order_id (no matching order)", "order_id")])
    d = pd.to_datetime(o["order_date"], format="%Y-%m-%d", errors="coerce")
    chk("orders future order_date", (d > pd.Timestamp(TODAY)).sum(),
        exp[("orders.csv", "Future timestamp/date", "order_date")])
    chk("orders unparseable order_date", d.isna().sum(),
        exp[("orders.csv", "Invalid timestamp/date", "order_date")])
    ts = pd.to_datetime(t["txn_ts"], format="%Y-%m-%d %H:%M:%S", errors="coerce")
    chk("transactions future txn_ts", (ts > pd.Timestamp(TODAY)).sum(),
        exp[("transactions.csv", "Future timestamp/date", "txn_ts")])
    chk("transactions unparseable txn_ts", ts.isna().sum(),
        exp[("transactions.csv", "Invalid timestamp/date", "txn_ts")])
    return checks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="../data")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    rng = np.random.default_rng(args.seed)
    inv = []

    print("Generating orders ...")
    orders, clean_orders, price, qty = build_orders(rng, inv)
    print("Generating transactions ...")
    txns = build_transactions(rng, inv, clean_orders, price, qty)

    op, tp = os.path.join(args.out, "orders.csv"), os.path.join(args.out, "transactions.csv")
    orders.to_csv(op, index=False, lineterminator="\n")
    txns.to_csv(tp, index=False, lineterminator="\n")

    files = {}
    for p in (op, tp):
        files[os.path.basename(p)] = dict(data_rows=N_ROWS, bytes=os.path.getsize(p), sha256=sha256(p))

    print("Verifying written files ...")
    checks = verify(args.out, inv)

    inv_df = pd.DataFrame(inv)
    inv_df.to_csv(os.path.join(args.out, "dirty_data_inventory.csv"), index=False)
    with open(os.path.join(args.out, "source_inventory.json"), "w") as f:
        json.dump(dict(seed=args.seed, files=files, verification=checks), f, indent=2)

    with open(os.path.join(args.out, "dirty_data_report.md"), "w") as f:
        f.write(f"# Dirty-data inventory (seed={args.seed})\n\n")
        f.write("Percentages are of 1,000,000 data rows per file. Injected rows are disjoint, "
                "so each row has at most one injected defect. Duplicate rows are extra rows "
                "(copies) counted within the 1,000,000.\n\n")
        for fn in ("orders.csv", "transactions.csv"):
            sub = inv_df[inv_df["file"] == fn]
            f.write(f"## {fn}\n\n| Type | Field | Rows | % of rows |\n|---|---|---:|---:|\n")
            for _, r in sub.iterrows():
                f.write(f"| {r['category']} | {r['field']} | {r['rows']:,} | {r['pct']}% |\n")
            f.write(f"| **Total affected rows** | | **{sub['rows'].sum():,}** | "
                    f"**{round(100 * sub['rows'].sum() / N_ROWS, 2)}%** |\n\n")
        f.write("## File facts\n\n| File | Data rows | Bytes | SHA-256 |\n|---|---:|---:|---|\n")
        for k, v in files.items():
            f.write(f"| {k} | {v['data_rows']:,} | {v['bytes']:,} | `{v['sha256']}` |\n")
        f.write("\n## Independent verification (re-read from disk)\n\n| Check | Actual | Expected | OK |\n|---|---:|---:|---|\n")
        for c in checks:
            f.write(f"| {c['check']} | {c['actual']:,} | {c['expected']:,} | {'PASS' if c['ok'] else 'FAIL'} |\n")

    bad = [c for c in checks if not c["ok"]]
    print("ALL CHECKS PASSED" if not bad else f"FAILED CHECKS: {bad}")


if __name__ == "__main__":
    main()
