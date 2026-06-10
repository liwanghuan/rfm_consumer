# CLAUDE.md

Teaching materials for a 2-hour NUS guest lecture (*Data Analytics in Business*,
Year-2 elective): an AI agent demo that takes raw retail transactions and
automates **data cleaning → RFM segmentation → marketing strategy → report**.
This is classroom code — clarity and a reliable live demo matter more than
performance or production hardening.

## Layout

All code lives in `app/`:

- `app.py` — Streamlit demo UI, run live in class. Drives the pipeline and
  narrates each step (cleaning log, scoring, segmentation, strategy).
- `agent/` — the four pipeline steps, in order:
  - `data_cleaner.py` (step 1) — fixes duplicates, missing keys, mixed date
    formats, currency symbols, refunds, outliers; logs every action to a
    `CleaningReport` so students can see what the agent decided and why.
  - `rfm_engine.py` (step 2) — R/F/M scored 1–5 by quintile; customers mapped
    to four segments by comparing scores against the population mean. Segment
    name constants (`SEGMENT_*`) and `SEGMENT_ORDER` are defined here and
    imported elsewhere — don't duplicate the strings.
  - `strategy_agent.py` (step 3) — rule-based `PLAYBOOK` always available;
    optional Claude mode when `ANTHROPIC_API_KEY` is set.
  - `report_generator.py` (step 4) — assembles the Markdown strategy report.
- `data/retail_transactions.csv` — sample *dirty* dataset (5.5k rows, 800
  customers); regenerate with `data/generate_dataset.py`.
- `build_ppt.py` — regenerates the lecture deck `nus_lecture_rfm_agent.pptx`.

## Running

```bash
cd app
pip install -r requirements.txt
streamlit run app.py
```

Optional LLM strategist: `export ANTHROPIC_API_KEY=sk-ant-...` before
launching, then toggle "Use Claude as AI strategist" in the sidebar.

There are no tests; verify changes by running the Streamlit app end-to-end
(press **▶ Run agent** in the sidebar).

## Conventions and constraints

- **The demo must always work offline.** The LLM strategist is strictly
  optional and must fall back to the rule-based playbook on any error
  (missing key, network failure, API error). Never make `anthropic` a hard
  dependency.
- Uploaded CSVs are only required to have `customer_id`, `order_id`,
  `order_date`, `amount`; the cleaner must keep handling everything else
  gracefully.
- The four segments (High Value / Important / Important Maintaining / Normal)
  and the quintile + above-mean segmentation rule are lecture content — they
  appear in the slides and README. If you change the logic, update
  `build_ppt.py`, both READMEs, and regenerate the deck.
- Module docstrings explain each step in plain language for students; keep
  that style when editing.
