"""Generate a realistic *dirty* retail transaction dataset for the lecture demo.

The dataset intentionally contains the problems the cleaning agent must fix:
duplicates, missing values, bad date formats, currency symbols, refunds,
and extreme outliers.

Usage:  python data/generate_dataset.py
Output: data/retail_transactions.csv
"""

import random
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

random.seed(42)
np.random.seed(42)

N_CUSTOMERS = 800
SNAPSHOT = datetime(2026, 6, 1)

# Four latent behaviour profiles so that real segments exist in the data:
#   (weight, recency window in days, orders range, basket mean)
PROFILES = [
    (0.12, (1, 45), (8, 25), 220),    # champions: recent, frequent, big spend
    (0.15, (1, 60), (1, 3), 350),     # new big spenders: recent, rare, big
    (0.15, (90, 300), (8, 20), 200),  # lapsing loyalists: old, frequent, big
    (0.58, (30, 365), (1, 6), 60),    # everyone else
]


def make_rows():
    rows = []
    order_no = 10000
    for cid in range(1, N_CUSTOMERS + 1):
        r = random.random()
        cum = 0.0
        for weight, rec_window, freq_range, basket_mean in PROFILES:
            cum += weight
            if r <= cum:
                break
        n_orders = random.randint(*freq_range)
        last_purchase = SNAPSHOT - timedelta(days=random.randint(*rec_window))
        for i in range(n_orders):
            order_no += 1
            # Spread earlier orders back in time from the last purchase
            date = last_purchase - timedelta(days=int(np.random.exponential(40)) * i)
            amount = max(5, np.random.normal(basket_mean, basket_mean * 0.4))
            rows.append({
                "customer_id": f"C{cid:05d}",
                "order_id": f"ORD{order_no}",
                "order_date": date.strftime("%Y-%m-%d"),
                "amount": round(amount, 2),
                "channel": random.choice(["online", "store", "app"]),
                "city": random.choice(
                    ["Singapore", "Johor Bahru", "Kuala Lumpur", "Jakarta", "Bangkok"]),
            })
    return rows


def dirty_up(df: pd.DataFrame) -> pd.DataFrame:
    """Inject realistic data-quality problems."""
    # Mixed-type columns ahead (strings + numbers), so relax the dtypes first
    df = df.astype({"amount": object, "order_date": object})

    # 1. Exact duplicates (double submission)
    df = pd.concat([df, df.sample(60, random_state=1)], ignore_index=True)

    # 2. Missing customer ids / dates
    df.loc[df.sample(25, random_state=2).index, "customer_id"] = None
    df.loc[df.sample(20, random_state=3).index, "order_date"] = None

    # 3. Currency symbols and thousands separators in amount
    idx = df.sample(80, random_state=4).index
    df.loc[idx, "amount"] = df.loc[idx, "amount"].map(lambda v: f"${v:,.2f}")

    # 4. Refunds (negative amounts) and zero rows
    idx = df.sample(35, random_state=5).index
    df.loc[idx, "amount"] = -np.abs(pd.to_numeric(
        df.loc[idx, "amount"].astype(str).str.replace(r"[$,]", "", regex=True)))

    # 5. A few absurd outliers (fat-finger errors)
    idx = df.sample(6, random_state=6).index
    df.loc[idx, "amount"] = np.random.uniform(50_000, 99_000, size=len(idx)).round(2)

    # 6. Mixed date formats (unambiguous, e.g. "05 Mar 2026")
    idx = df.sample(50, random_state=7).index
    df.loc[idx, "order_date"] = pd.to_datetime(
        df.loc[idx, "order_date"]).dt.strftime("%d %b %Y")

    # ...and a few truly unparseable dates the cleaner must drop
    idx = df.sample(8, random_state=10).index
    df.loc[idx, "order_date"] = "not-a-date"

    # 7. Messy customer-id casing/spacing
    idx = df.sample(40, random_state=8).index
    df.loc[idx, "customer_id"] = " " + df.loc[idx, "customer_id"].str.lower() + " "

    return df.sample(frac=1, random_state=9).reset_index(drop=True)  # shuffle


if __name__ == "__main__":
    df = pd.DataFrame(make_rows())
    df = dirty_up(df)
    out = Path(__file__).parent / "retail_transactions.csv"
    df.to_csv(out, index=False)
    print(f"Wrote {len(df):,} rows ({df['customer_id'].nunique()} customers) -> {out}")
