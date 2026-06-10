"""RFM Customer Segmentation & Automated Reporting Agent — demo UI.

Run with:
    streamlit run app.py
"""

import os
import time
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from agent import DataCleaner, RFMEngine, StrategyAgent, ReportGenerator
from agent.rfm_engine import SEGMENT_ORDER

st.set_page_config(
    page_title="RFM Segmentation Agent",
    page_icon="🛍️",
    layout="wide",
)

SEGMENT_COLORS = {
    "High Value Customer": "#2E86AB",
    "Important Customer": "#06A77D",
    "Important Maintaining Customer": "#F18F01",
    "Normal Customer": "#A9A9A9",
}

SAMPLE_PATH = Path(__file__).parent / "data" / "retail_transactions.csv"


# ---------------------------------------------------------------------------
# Sidebar — input & agent settings
# ---------------------------------------------------------------------------

st.sidebar.title("🛍️ RFM Agent")
st.sidebar.caption("Data cleaning → RFM segmentation → strategy report, "
                   "fully automated.")

source = st.sidebar.radio(
    "Dataset",
    ["Use sample retail dataset", "Upload my own CSV"],
)

uploaded = None
if source == "Upload my own CSV":
    uploaded = st.sidebar.file_uploader(
        "Transaction CSV", type="csv",
        help="Needs columns: customer_id, order_id, order_date, amount",
    )

has_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
use_llm = st.sidebar.toggle(
    "Use Claude as AI strategist",
    value=False,
    disabled=not has_key,
    help=("Adds an LLM-written strategy narrative per segment. "
          "Requires the ANTHROPIC_API_KEY environment variable."
          if has_key else
          "Set the ANTHROPIC_API_KEY environment variable to enable."),
)

run = st.sidebar.button("▶ Run agent", type="primary", use_container_width=True)

st.sidebar.divider()
st.sidebar.markdown(
    "**Pipeline**\n\n"
    "1. 🧹 Clean the raw transactions\n"
    "2. 📊 Score Recency / Frequency / Monetary\n"
    "3. 🧩 Segment customers (4 groups)\n"
    "4. 🤖 Generate strategy per segment\n"
    "5. 📄 Assemble the report"
)

# ---------------------------------------------------------------------------
# Main page
# ---------------------------------------------------------------------------

st.title("RFM Customer Segmentation & Automated Reporting Agent")
st.caption("NUS guest lecture demo — Data Analytics in Business")

if run:
    if source == "Upload my own CSV" and uploaded is None:
        st.error("Please upload a CSV file first.")
        st.stop()

    raw = pd.read_csv(uploaded if uploaded is not None else SAMPLE_PATH)

    # --- run the pipeline with visible agent steps ------------------------
    with st.status("Agent is working…", expanded=True) as status:
        st.write("**Step 1/5 — Inspecting & cleaning the data**")
        cleaner = DataCleaner()
        try:
            clean_df, creport = cleaner.clean(raw)
        except ValueError as exc:
            status.update(label="Agent stopped", state="error")
            st.error(str(exc))
            st.stop()
        for action in creport.actions:
            st.write(f"・ {action}")
            time.sleep(0.15)  # small pause so students can follow along

        st.write("**Step 2/5 — Computing RFM metrics & scores**")
        engine = RFMEngine()
        result = engine.run(clean_df)
        st.write(f"・ {len(result.rfm):,} customers scored "
                 f"(snapshot date {result.snapshot_date:%Y-%m-%d}).")

        st.write("**Step 3/5 — Segmenting customers**")
        summary = engine.segment_summary(result.rfm)
        for _, r in summary.iterrows():
            st.write(f"・ {r['segment']}: {int(r['customers']):,} customers "
                     f"({r['customer_share_pct']:.1f}%)")

        st.write("**Step 4/5 — Generating marketing strategies**"
                 + (" (asking Claude…)" if use_llm else " (rule playbook)"))
        strategist = StrategyAgent(use_llm=use_llm)
        strategies = strategist.recommend(summary)
        llm_used = any(s.get("llm_narrative") for s in strategies.values())
        if use_llm and not llm_used:
            err = next((s.get("llm_error") for s in strategies.values()
                        if s.get("llm_error")), "unknown")
            st.write(f"・ ⚠️ LLM unavailable ({err}); used the rule playbook.")
        else:
            st.write("・ Strategy recommendations ready for "
                     f"{len(strategies)} segments.")

        st.write("**Step 5/5 — Assembling the report**")
        report_md = ReportGenerator().build(creport, result, summary, strategies)
        status.update(label="✅ Agent finished — report ready", state="complete")

    # cache results so tab interactions don't rerun the pipeline
    st.session_state["results"] = dict(
        raw=raw, clean_df=clean_df, creport=creport, result=result,
        summary=summary, strategies=strategies, report_md=report_md,
    )

if "results" not in st.session_state:
    st.info("👈 Choose a dataset and press **Run agent** to start.")
    with st.expander("What does the input data look like?"):
        st.dataframe(pd.read_csv(SAMPLE_PATH).head(15), use_container_width=True)
    st.stop()

R = st.session_state["results"]
rfm, summary = R["result"].rfm, R["summary"]

# ---------------------------------------------------------------------------
# KPI row
# ---------------------------------------------------------------------------

k1, k2, k3, k4 = st.columns(4)
k1.metric("Customers", f"{len(rfm):,}")
k2.metric("Total revenue", f"${rfm['monetary'].sum():,.0f}")
k3.metric("Avg orders / customer", f"{rfm['frequency'].mean():.1f}")
hv = summary.loc[summary['segment'] == 'High Value Customer']
if not hv.empty:
    k4.metric("High-value revenue share", f"{hv.iloc[0]['revenue_share_pct']:.1f}%")

tab_clean, tab_rfm, tab_seg, tab_report = st.tabs(
    ["🧹 Data Cleaning", "📊 RFM Analysis", "🧩 Segments & Strategy", "📄 Report"])

# ---------------------------------------------------------------------------
# Tab 1 — cleaning
# ---------------------------------------------------------------------------

with tab_clean:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Raw data (first 12 rows)")
        st.dataframe(R["raw"].head(12), use_container_width=True)
    with c2:
        st.subheader("Cleaned data (first 12 rows)")
        st.dataframe(R["clean_df"].head(12), use_container_width=True)
    st.subheader("Agent cleaning log")
    for action in R["creport"].actions:
        st.markdown(f"- {action}")

# ---------------------------------------------------------------------------
# Tab 2 — RFM analysis
# ---------------------------------------------------------------------------

with tab_rfm:
    c1, c2 = st.columns(2)
    with c1:
        fig = px.pie(summary, names="segment", values="customers",
                     title="Customer share by segment",
                     color="segment", color_discrete_map=SEGMENT_COLORS, hole=0.45)
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        fig = px.bar(summary, x="segment", y="revenue_share_pct",
                     title="Revenue share by segment (%)",
                     color="segment", color_discrete_map=SEGMENT_COLORS,
                     text_auto=".1f")
        fig.update_layout(showlegend=False, xaxis_title=None)
        st.plotly_chart(fig, use_container_width=True)

    fig = px.scatter(
        rfm, x="recency_days", y="monetary", size="frequency",
        color="segment", color_discrete_map=SEGMENT_COLORS,
        category_orders={"segment": SEGMENT_ORDER},
        hover_data=["customer_id", "frequency"],
        title="Customer map — Recency vs Monetary (bubble = Frequency)",
        labels={"recency_days": "Days since last purchase",
                "monetary": "Total spend ($)"},
    )
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Segment summary table")
    st.dataframe(summary, use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# Tab 3 — segments & strategy
# ---------------------------------------------------------------------------

with tab_seg:
    seg_choice = st.selectbox("Pick a segment", [s for s in SEGMENT_ORDER
                                                 if s in R["strategies"]])
    s = R["strategies"][seg_choice]
    stats = s["stats"]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Customers", f"{stats['customers']:,}",
              f"{stats['customer_share_pct']:.1f}% of base")
    c2.metric("Revenue share", f"{stats['revenue_share_pct']:.1f}%")
    c3.metric("Avg recency", f"{stats['avg_recency_days']:.0f} days")
    c4.metric("Avg spend", f"${stats['avg_monetary']:,.0f}")

    st.markdown(f"**Diagnosis** — {s['diagnosis']}")
    if s.get("llm_narrative"):
        st.info(f"🤖 **Claude's view** — {s['llm_narrative']}")
    st.markdown(f"**Goal** — {s['goal']}")
    st.markdown("**Recommended actions**")
    for a in s["actions"]:
        st.markdown(f"- {a}")
    st.markdown(f"**KPIs to track** — {s['kpi']}")

    st.divider()
    st.subheader(f"Customers in “{seg_choice}”")
    seg_df = rfm[rfm["segment"] == seg_choice].sort_values(
        "monetary", ascending=False)
    st.dataframe(seg_df.head(50), use_container_width=True, hide_index=True)
    st.download_button(
        "⬇ Download this segment as CSV",
        seg_df.to_csv(index=False).encode(),
        file_name=f"{seg_choice.lower().replace(' ', '_')}.csv",
        mime="text/csv",
    )

# ---------------------------------------------------------------------------
# Tab 4 — report
# ---------------------------------------------------------------------------

with tab_report:
    st.download_button(
        "⬇ Download full report (Markdown)",
        R["report_md"].encode(),
        file_name="rfm_strategy_report.md",
        mime="text/markdown",
        type="primary",
    )
    st.markdown(R["report_md"])
