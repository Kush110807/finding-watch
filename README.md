# Finding Watch — BYTE Applied ML (Basic Agentic Task)

**Understand your data. Test your findings.** Finding Watch is a Python/Streamlit assistant for asking supported questions about an uploaded CSV, checking the calculation evidence, and testing how a **grouped** finding changes under **one explicitly approved filter change**. This repository addresses **one** BYTE Basic Agentic Task; it is not a submission for a second task.

## What works

**Answer → Challenge**

1. Open the app, **Upload CSV** or **Try an example**, and choose a locally suggested question or type your own.
2. Suggested questions run deterministic Python analysis without an API. For custom language, the optional Gemini agent chooses from declared tools (after explicit user consent); Python—not Gemini—calculates the numbers. A selected model must actually support function calling.
3. Read the evidence-derived answer. Open **How this was calculated** to inspect the executed definition, filters, row accounting, results and original downloadable JSON. Model commentary is **not** an independently verified interpretation.
4. Under a submitted grouped finding, select **Test another condition**, explicitly add/replace/remove **one** filter, **Review comparison**, then **Confirm and compare**. The two scenarios run independently on the same dataset; changing an inclusion assumption answers a different question, not necessarily disproving the original.

Clarification requires a user's definition; no suggested grouping, metric, date format, or Challenge is silently approved. Editing or switching the relevant submitted result invalidates previously approved comparisons. There is **no stored memory**, cross-session Saved Findings, or Revisit feature.

## Five distinct analytical tools

| Tool exposed to Gemini | Calculation responsibility |
| --- | --- |
| `inspect_dataset` | Schema, row/column counts, missing values and duplicates (not a guarantee of accuracy) |
| `filter_rows` | Select matching records and show a bounded record preview; not an aggregation source |
| `grouped_summary` | Grouped sums, means, minima, maxima and row counts |
| `time_trend` | Explicit-date daily/weekly/monthly grouped statistics |
| `correlation` | Pearson correlation on complete numeric pairs (not causation) |

Gemini can call these via a bounded function-calling loop. Validated arguments pass through `engine.py`/`specs.py`; there is **no arbitrary model-generated code execution**. `propose_grouped_comparison` only proposes a definition: it is **not** counted among the five analytical tools, and user confirmation is required for execution. `request_clarification` is likewise not an analytical tool. The advanced sidebar keeps all five deterministic manual tools available without an API key.

## Windows quick start

Install Python **3.13** and Git. From a checkout containing the `agentic` folder:

```powershell
cd agentic
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Use the URL Streamlit prints locally. Without any Gemini key, **Try an example**, local suggested questions, and the advanced manual tools still work. This project pins `streamlit==1.64.0`, `pandas==2.2.3`, `python-dotenv==1.2.3`, and `google-genai==2.25.0` in `agentic/requirements.txt`. No GPU is required: computation runs in Python; the optional LLM is hosted.

### Optional private Gemini configuration

Copy `agentic/.env.example` to `agentic/.env` **on your own machine**, then set `GEMINI_API_KEY` and `GEMINI_MODEL` to a model **actually available to your account with function calling**. The code has a configurable SDK default; do **not** assume the default is available. The local `.env` is ignored by Git. Never paste a key in an issue, README, screenshot, test log or public repository. In the app, open **Gemini connection and consent** and explicitly agree before sending your question, schema and relevant bounded dataset/tool outputs to Google. A model listing alone is not live-tool verification.

For optional local synthetic-only verification, `python verify_live.py --output live_verification_local.json` checks two distinct tool calls plus clarification, and `python verify_live_comparison.py --confirm` tests proposal/confirmation. These files contain outputs and must remain private. Neither script substitutes for a real browser test.

## Reproducible examples

Bundled `agentic/data/demo_sales.csv` has columns `date, category, region, revenue, units`:

- **Total revenue by category:** Coffee **3,000**, Snacks **1,400**; Coffee is **1,600** higher. Four records, no filters; no currency is assumed.
- **Challenge: Region is North:** Coffee **1,200**, Snacks **800** (two selected records); Coffee remains the leader. The comparison is only run after review and confirmation.
- **Monthly total revenue:** January 2026 **1,800**, February 2026 **2,600**, with explicit `%Y-%m-%d` parsing. This is descriptive, not a growth forecast.

These are calculations from the CSV, not hard-coded answers. The smaller `agentic/docs/fixtures/golden_orders.csv` shows a different outcome when cancelled records are excluded. The app also accepts suitable unfamiliar CSVs with different column names; use a matching grouping, numeric metric and explicit date interpretation rather than assuming standard business column names.

## Inputs and limitations

- CSV only: UTF-8 (including UTF-8 BOM), header, **up to 10 MiB / 100,000 data rows / 100 columns**. The application deliberately retains identifier-like text and leading-zero values; ambiguous numeric/date fields may require preparing a cleaned copy.
- Only validated filters and supported descriptive analysis. Five manual tools are available through **Advanced**. One-condition Challenge is for a submitted **grouped** finding, not a general what-if engine.
- Date formats must be explicit. Missing values, exclusions, all-missing groups, ties, truncation and unsupported numeric ranges are surfaced in evidence. Some unsafe charts are intentionally omitted. Correlation never establishes causality.
- No joins, forecasting, model training, arbitrary formulas, statistics significance tests, universal verification, persistent memory or cross-dataset Revisit. A completed calculation is not proof Gemini correctly understood every nuance of a user's intent.
- If Gemini is unconfigured, rate-limited or unavailable, use local suggested questions/manual analysis. Public deployments with a shared Gemini key can consume the owner's quota; do not deploy a public key-backed app casually.

## Implementation and verification transparency

**Stack:** Python, pandas/NumPy (through pandas), Streamlit, `python-dotenv`, Google Gen AI Python SDK / Gemini function calling. The interface and deterministic computation run locally or on the Streamlit host; the LLM is a Google-hosted API, not a trained local model. There are no custom learned weights.

**Contributions:** The user defined scope, feature gates, expected outputs, acceptance criteria, and conducted independent Windows/live-provider/browser review. ChatGPT/Codex assisted with architecture, implementation, tests and documentation. Review the detailed, dated record in [`agentic/docs/CONTRIBUTIONS.md`](agentic/docs/CONTRIBUTIONS.md) and adapt it honestly to reflect any hands-on edits or experiments before publishing. This README and release documentation were AI-assisted drafts, not claimed to be unaided work.

**Previously reported acceptance:** On the frozen Stage 3 commit `754ec1cda8f917fbe62f242d503c654dca4138d6`, the user reported **239 Windows tests passed** and manual UI checks. Earlier real Gemini checks successfully exercised monthly analysis, clarification and a user-confirmed grouped result. **These were user-reported prior verification; the release documentation pass has not re-run live Gemini or the Windows suite.** See [`RELEASE_CHECKLIST.md`](agentic/docs/RELEASE_CHECKLIST.md) for up-to-date release review status.

## Deployment, demo and submission

- [Deployment instructions, hosting secrets and quota safety](agentic/docs/DEPLOYMENT.md)
- [Short demonstration script](agentic/docs/DEMO_SCRIPT.md)
- [BYTE requirements and release checklist](agentic/docs/RELEASE_CHECKLIST.md)

Official BYTE task: <https://bytesoc.dev/tasks/applied-ml/>. The published deadline is **13 October 2026, 11:59 PM IST**. Submit a **public GitHub repository and README**; a short video and/or hosted demo are strongly preferred. Finding Watch is **one task**; any other required task must be submitted separately. **No public repository, hosted URL or submission is claimed in this release.**

### Provider pacing and recovery

Gemini requests are spaced across Streamlit sessions within one Python process,
with capped, status-aware retries and safe diagnostics. See
[`agentic/docs/GEMINI_RELIABILITY_REPAIR.md`](agentic/docs/GEMINI_RELIABILITY_REPAIR.md).
This does not increase project quota or guarantee Google service availability.
