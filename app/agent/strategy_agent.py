"""Step 3 of the agent pipeline: per-segment analysis + marketing strategy.

Two modes:

1. Rule-based playbook (always available, runs offline) — encodes classic
   retail CRM strategy for each RFM segment.
2. LLM mode (optional) — if an ANTHROPIC_API_KEY is configured, the agent
   sends the segment statistics to Claude and asks it to write a tailored
   strategy narrative. Falls back to the playbook on any error, so the
   classroom demo never breaks.
"""

import os

import pandas as pd

from agent.rfm_engine import (
    SEGMENT_HIGH_VALUE,
    SEGMENT_IMPORTANT,
    SEGMENT_MAINTAINING,
    SEGMENT_NORMAL,
)

# ---------------------------------------------------------------------------
# Rule-based strategy playbook
# ---------------------------------------------------------------------------

PLAYBOOK = {
    SEGMENT_HIGH_VALUE: {
        "diagnosis": (
            "Bought recently, buy often, and spend the most. They are the "
            "engine of the business and the most likely to respond to "
            "premium offers."
        ),
        "goal": "Retain and grow lifetime value; turn them into advocates.",
        "actions": [
            "Enrol them in a VIP / top-tier loyalty programme with exclusive perks",
            "Give early access to new products and members-only sales",
            "Assign personalised service (dedicated support, birthday gifts)",
            "Invite referrals — reward them for bringing in similar customers",
            "Avoid discounting heavily: they buy on value, not price",
        ],
        "kpi": "Repeat purchase rate, share of wallet, NPS / referral count",
    },
    SEGMENT_IMPORTANT: {
        "diagnosis": (
            "Recent, high-spending customers who do not yet purchase often. "
            "Big baskets but low habit — the highest-upside growth segment."
        ),
        "goal": "Increase purchase frequency and build a buying habit.",
        "actions": [
            "Cross-sell complementary products based on their first purchases",
            "Offer time-limited 'come back within 30 days' incentives",
            "Enrol them in a points programme where frequency earns rewards",
            "Send replenishment / new-arrival reminders matched to what they bought",
            "Use post-purchase email flows to shorten the gap between orders",
        ],
        "kpi": "Purchase frequency, days between orders, repeat rate within 60 days",
    },
    SEGMENT_MAINTAINING: {
        "diagnosis": (
            "Historically loyal, high-spending customers who have not bought "
            "recently. They are drifting away — every week of silence makes "
            "win-back harder and more expensive."
        ),
        "goal": "Reactivate before they churn; find out why they left.",
        "actions": [
            "Launch a win-back campaign: 'We miss you' + meaningful incentive",
            "Survey them for churn reasons (price, product, competitor, service)",
            "Retarget with the categories they previously bought most",
            "Offer free shipping or a loyalty-points boost on the next order",
            "Escalate high-value lapsed accounts to direct outreach (call / DM)",
        ],
        "kpi": "Reactivation rate, win-back campaign ROI, churn-survey completion",
    },
    SEGMENT_NORMAL: {
        "diagnosis": (
            "Low recency, frequency, or spend — a broad base of occasional "
            "shoppers. Serve them efficiently; do not over-invest."
        ),
        "goal": "Nurture cheaply at scale; identify the few with upgrade potential.",
        "actions": [
            "Keep them on low-cost automated channels (email / app push)",
            "Use broad seasonal promotions rather than personalised offers",
            "Watch for spend or frequency spikes and promote risers to "
            "higher-touch journeys",
            "Test entry-level bundles to lift average order value",
            "Cap acquisition-style spend: ROI on this segment is the lowest",
        ],
        "kpi": "Email engagement, conversion on promotions, upgrade rate to higher segments",
    },
}


class StrategyAgent:
    """Generates per-segment marketing strategy recommendations."""

    def __init__(self, use_llm: bool | None = None, model: str = "claude-opus-4-8"):
        if use_llm is None:
            use_llm = bool(os.environ.get("ANTHROPIC_API_KEY"))
        self.use_llm = use_llm
        self.model = model

    # -- public API ---------------------------------------------------------

    def recommend(self, summary: pd.DataFrame) -> dict:
        """Return {segment: strategy_dict} for every segment present."""
        strategies = {}
        for _, row in summary.iterrows():
            seg = row["segment"]
            base = dict(PLAYBOOK[seg])  # copy the playbook entry
            base["stats"] = {
                "customers": int(row["customers"]),
                "customer_share_pct": float(row["customer_share_pct"]),
                "revenue_share_pct": float(row["revenue_share_pct"]),
                "avg_recency_days": float(row["avg_recency_days"]),
                "avg_frequency": float(row["avg_frequency"]),
                "avg_monetary": float(row["avg_monetary"]),
            }
            base["source"] = "playbook"
            strategies[seg] = base

        if self.use_llm:
            try:
                narratives = self._llm_narratives(summary)
                for seg, text in narratives.items():
                    if seg in strategies:
                        strategies[seg]["llm_narrative"] = text
                        strategies[seg]["source"] = "playbook + LLM"
            except Exception as exc:  # network/auth issues: degrade gracefully
                for seg in strategies:
                    strategies[seg]["llm_error"] = str(exc)
        return strategies

    # -- LLM mode -----------------------------------------------------------

    def _llm_narratives(self, summary: pd.DataFrame) -> dict:
        """Ask Claude to write a tailored strategy paragraph per segment."""
        import json

        import anthropic

        client = anthropic.Anthropic()
        stats_table = summary.to_string(index=False)
        prompt = (
            "You are a retail CRM strategist. Below is an RFM segment summary "
            "for a retail business (currency: SGD).\n\n"
            f"{stats_table}\n\n"
            "For EACH segment, write a concise marketing strategy "
            "recommendation (3-5 sentences) that references the actual "
            "numbers (customer share, revenue share, recency, frequency, "
            "spend). Return ONLY a JSON object mapping the exact segment "
            "name to its recommendation string."
        )

        with client.messages.stream(
            model=self.model,
            max_tokens=16000,
            thinking={"type": "adaptive"},
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            message = stream.get_final_message()

        text = next(b.text for b in message.content if b.type == "text")
        # The model may wrap JSON in a code fence; strip it before parsing.
        text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```")
        return json.loads(text)
