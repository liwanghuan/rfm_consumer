"""Step 1 of the agent pipeline: automated data cleaning.

The cleaner inspects the raw transaction table, fixes every problem it can fix
autonomously, and keeps a human-readable log of each action so students can see
exactly what an "agent" decided to do and why.
"""

from dataclasses import dataclass, field

import pandas as pd

REQUIRED_COLUMNS = ["customer_id", "order_id", "order_date", "amount"]


@dataclass
class CleaningReport:
    """What the cleaning step did, in plain language."""

    rows_in: int = 0
    rows_out: int = 0
    actions: list = field(default_factory=list)

    def log(self, message: str) -> None:
        self.actions.append(message)


class DataCleaner:
    """Rule-driven cleaning agent for retail transaction data."""

    def clean(self, df: pd.DataFrame) -> tuple[pd.DataFrame, CleaningReport]:
        report = CleaningReport(rows_in=len(df))
        df = df.copy()

        # 1. Normalise column names (strip spaces, lower-case)
        df.columns = [c.strip().lower() for c in df.columns]
        missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
        if missing:
            raise ValueError(
                f"Dataset is missing required columns: {missing}. "
                f"Expected at least {REQUIRED_COLUMNS}."
            )
        report.log("Validated schema: found all required columns "
                   f"{REQUIRED_COLUMNS}.")

        # 2. Drop exact duplicate rows (double-submitted orders)
        dupes = int(df.duplicated().sum())
        if dupes:
            df = df.drop_duplicates()
            report.log(f"Removed {dupes} exact duplicate rows.")

        # 3. Drop rows missing the keys we cannot recover
        before = len(df)
        df = df.dropna(subset=["customer_id", "order_date"])
        dropped = before - len(df)
        if dropped:
            report.log(f"Dropped {dropped} rows with missing customer_id or "
                       "order_date (cannot be attributed to a customer).")

        # 4. Parse dates; coerce bad formats to NaT then drop them
        df["order_date"] = pd.to_datetime(df["order_date"], errors="coerce",
                                          format="mixed")
        bad_dates = int(df["order_date"].isna().sum())
        if bad_dates:
            df = df.dropna(subset=["order_date"])
            report.log(f"Dropped {bad_dates} rows with unparseable order dates.")

        # 5. Clean amount: strip currency symbols, coerce to numeric
        df["amount"] = (
            df["amount"].astype(str)
            .str.replace(r"[$,SGD\s]", "", regex=True)
        )
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
        bad_amounts = int(df["amount"].isna().sum())
        if bad_amounts:
            df = df.dropna(subset=["amount"])
            report.log(f"Dropped {bad_amounts} rows with non-numeric amounts "
                       "(after stripping currency symbols).")

        # 6. Remove refunds / zero-value rows for RFM purposes
        negatives = int((df["amount"] <= 0).sum())
        if negatives:
            df = df[df["amount"] > 0]
            report.log(f"Removed {negatives} refund/zero-amount rows "
                       "(amount <= 0) — they distort Monetary value.")

        # 7. Cap extreme outliers at the 99.5th percentile (likely data errors)
        cap = df["amount"].quantile(0.995)
        outliers = int((df["amount"] > cap).sum())
        if outliers:
            df.loc[df["amount"] > cap, "amount"] = cap
            report.log(f"Winsorised {outliers} extreme amounts above the "
                       f"99.5th percentile (capped at ${cap:,.2f}).")

        # 8. Standardise customer ids
        df["customer_id"] = df["customer_id"].astype(str).str.strip().str.upper()
        report.log("Standardised customer_id format (trimmed, upper-cased).")

        report.rows_out = len(df)
        report.log(f"Cleaning complete: {report.rows_in} rows in -> "
                   f"{report.rows_out} rows out.")
        return df.reset_index(drop=True), report
