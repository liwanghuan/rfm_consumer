"""Step 2 of the agent pipeline: RFM scoring and customer segmentation.

RFM:
    Recency   - days since the customer's most recent purchase (lower = better)
    Frequency - number of distinct orders (higher = better)
    Monetary  - total spend (higher = better)

Each dimension is scored 1-5 by quintile, then customers are mapped into four
business segments by comparing their R / F / M scores with the population mean:

    High Value Customer            R high, F high, M high  - the best customers
    Important Customer             R high, F low,  M high  - recent big spenders,
                                                             room to grow frequency
    Important Maintaining Customer R low,  F high, M high  - loyal big spenders
                                                             who are drifting away
    Normal Customer                everyone else
"""

from dataclasses import dataclass

import pandas as pd

SEGMENT_HIGH_VALUE = "High Value Customer"
SEGMENT_IMPORTANT = "Important Customer"
SEGMENT_MAINTAINING = "Important Maintaining Customer"
SEGMENT_NORMAL = "Normal Customer"

SEGMENT_ORDER = [
    SEGMENT_HIGH_VALUE,
    SEGMENT_IMPORTANT,
    SEGMENT_MAINTAINING,
    SEGMENT_NORMAL,
]


@dataclass
class RFMResult:
    rfm: pd.DataFrame          # one row per customer with scores + segment
    snapshot_date: pd.Timestamp
    thresholds: dict           # the mean R/F/M scores used as split points


def _quintile_score(series: pd.Series, higher_is_better: bool) -> pd.Series:
    """Score 1-5 by quintile. Falls back gracefully when values tie heavily."""
    labels = [1, 2, 3, 4, 5] if higher_is_better else [5, 4, 3, 2, 1]
    try:
        return pd.qcut(series, q=5, labels=labels, duplicates="drop").astype(int)
    except ValueError:
        # Too many ties to form 5 bins — rank first, then cut.
        ranked = series.rank(method="first")
        return pd.qcut(ranked, q=5, labels=labels).astype(int)


class RFMEngine:
    """Computes RFM metrics, quintile scores, and the four business segments."""

    def run(self, df: pd.DataFrame) -> RFMResult:
        # Snapshot = day after the latest transaction in the dataset
        snapshot = df["order_date"].max() + pd.Timedelta(days=1)

        rfm = df.groupby("customer_id").agg(
            recency_days=("order_date", lambda s: (snapshot - s.max()).days),
            frequency=("order_id", "nunique"),
            monetary=("amount", "sum"),
        ).reset_index()

        rfm["R"] = _quintile_score(rfm["recency_days"], higher_is_better=False)
        rfm["F"] = _quintile_score(rfm["frequency"], higher_is_better=True)
        rfm["M"] = _quintile_score(rfm["monetary"], higher_is_better=True)

        thresholds = {
            "R": rfm["R"].mean(),
            "F": rfm["F"].mean(),
            "M": rfm["M"].mean(),
        }

        # "High" means strictly above the population mean score
        r_high = rfm["R"] > thresholds["R"]
        f_high = rfm["F"] > thresholds["F"]
        m_high = rfm["M"] > thresholds["M"]

        rfm["segment"] = SEGMENT_NORMAL
        rfm.loc[r_high & f_high & m_high, "segment"] = SEGMENT_HIGH_VALUE
        rfm.loc[r_high & ~f_high & m_high, "segment"] = SEGMENT_IMPORTANT
        rfm.loc[~r_high & f_high & m_high, "segment"] = SEGMENT_MAINTAINING

        rfm["rfm_score"] = rfm["R"].astype(str) + rfm["F"].astype(str) + rfm["M"].astype(str)
        return RFMResult(rfm=rfm, snapshot_date=snapshot, thresholds=thresholds)

    @staticmethod
    def segment_summary(rfm: pd.DataFrame) -> pd.DataFrame:
        """Per-segment aggregates used by the strategy step and the UI."""
        total_revenue = rfm["monetary"].sum()
        summary = rfm.groupby("segment").agg(
            customers=("customer_id", "count"),
            avg_recency_days=("recency_days", "mean"),
            avg_frequency=("frequency", "mean"),
            avg_monetary=("monetary", "mean"),
            total_revenue=("monetary", "sum"),
        ).reindex(SEGMENT_ORDER).dropna(how="all").reset_index()
        summary["customer_share_pct"] = (
            summary["customers"] / summary["customers"].sum() * 100
        )
        summary["revenue_share_pct"] = summary["total_revenue"] / total_revenue * 100
        return summary.round(2)
