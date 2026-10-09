# Finding Watch — P1–P3 Streamlit UI pass (review candidate)

## Baseline and scope

- Source baseline: accepted and frozen M2 `4bf170a16fafe420b1c633e4b13fe96b7f76c1fe`.
- Independent review reports 105 Windows tests passed and a confirmed real Gemini golden comparison. **M2 manual browser Challenge verification also passed** (per review decision). These are prior M2 review results, not new UI-pass testing.
- P1–P3 source scope only: `app.py`, `ui_components.py`, `presentation.py`, clarification instruction in `agent.py`, UI and pure-presentation tests, documentation and theme configuration. `engine.py`, `specs.py`, `comparisons.py` remain unmodified.
- No persistence, Saved Findings records, M3, Revisit, forecasting, arbitrary code execution or API-key changes.

## Design corrections implemented

1. Dataset schema is read as uploaded. When a question mentions a product but the schema has no product column, the clarification UI warns that a product result cannot be established as asked. Explicit grouping alternatives are offered **without preselection**. All labels come from actual CSV columns.
2. The returned model clarification is **display only** and never parsed as a calculation. An explicit form choice of group plus metric is required before deterministic execution. The original submitted question is preserved for evidence and pending-edit checks. Changing the question disables confirmation of an old proposal or clarification until re-submission.
3. Options are **Record count (rows)**, total and average of actual validated numeric columns, without inventing currencies or claiming each record is an order or product. Exact CSV filter value strings are not reformatted.
4. Python result rows and returned evidence determine numeric headlines, ties, comparison differences, group present vs absent vs missing metric, exclusions, and truncation warnings. A truncated grouped result **never establishes the global leader**. Bar charts are illustrative of displayed data only and omitted for unsafe >2^53 integers. Full evidence remains downloadable byte-equivalent to the runtime JSON serialization contract; display transformations do not change the result object.
5. Gemini commentary stays in a separate collapsed section with unverified labeling. Trace details and exact specs live under **How this was calculated**. Failed tools or provider failures are visibly errors, not successful findings.
6. Model-proposed Challenge and manual Challenge remain pending until explicit confirmation; the one-filter-only comparison validator is unchanged. Pending edits hide stale calculations. Results are tied to dataset fingerprint, submitted question and exact spec/plan.
7. Saved Findings is shown as planned text only. No simulated entries, prototype navigation or persistence controls.
8. No application state or global cache stores uploads. The existing Gemini opt-in consent remains intact.

## Source changes and rationale

- `agentic/app.py`: compact Analyse / Challenge presentation; consent, submitted-state handling, original-question clarification and clear pending-vs-completed states.
- `agentic/ui_components.py` **new**: Streamlit-only display surfaces, collapsed evidence and untouched JSON downloads; renders comparison present/absent values differently.
- `agentic/presentation.py` **new**: dependency-free evidence-to-text transforms and schema choice helpers, unit-free labeling, tie and truncation handling; independently testable without Streamlit.
- `agentic/agent.py`: clarification guidance only (no new tool or model payload contract).
- `agentic/tests/test_ui_contract.py` **new**: deterministic golden, missing, tie, truncation, absent/zero, large-integer and unfamiliar-schema checks.
- `agentic/tests/test_app.py`: simulated provider clarification / explicit opt-in test fixtures plus planned-state / provider-error assertions; requires real Streamlit AppTest and Google SDK packages on Windows.
- `agentic/.streamlit/config.toml`: native Streamlit theme and typography.
- Documentation: this handoff, README status and M2 manual browser verification correction.

## Windows verification (required before accepting UI pass)

From extracted `byte-ml/agentic` folder in PowerShell:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Capture **real running Streamlit** screenshots for:

1. Default Analyse dashboard and demo CSV, at desktop 1440×900 and a mobile viewport ~390×844.
2. Manual `Summarise groups` → `Group by category` → sum `revenue`: 3000 Coffee, 1400 Snacks (source `data/demo_sales.csv`, no currency assumed).
3. Gemini clarification: submit `Which is the best-selling product?` against demo CSV with opt-in. The response must be a clarification to use guided choices; if the live provider chooses a different path, record actual outcome. Product column warning, zero preselected choices, original question shown. Choose group `category` + `Total of “units”` then click **Analyse with my choices**; results Coffee 100, Snacks 70. Note: calculations are manual after explicit definition, not model-verified interpretation.
4. Unknown-schema CSV: `City,QuantitySold,SalesTotal` with rows `Delhi,2,25` and `Mumbai,4,50`; verify exact metric choices and original question retained.
5. Challenge: a submitted grouped result, filter `region equals North` on demo CSV. Before confirmation only pending definitions appear; after confirmation complete comparison and evidence. Then edit filter to `South`: old confirmed result must hide. Revert to `North`: source results reappear only if the exact confirmed plan is restored; any changed plan requires confirmation.
6. All five manual tools; missing values; tied group leaders; zero vs absent group; invalid filter; long groups exceeding display limit; network/provider error and no-key case.
7. Keyboard Tab/Shift+Tab flow across radio, selectbox, Gemini consent, clarification choices and confirmation; verify focus, no accidental triggering; downloads open as valid JSON with original numbers.

### Additional optional screenshot automation

With the Streamlit server running on `http://localhost:8501`, open the site in Chromium, inspect responsive widths, and use browser `Capture screenshot` or Windows Snipping Tool. Capture and upload those screenshots for a **separate actual-browser audit**. Screenshots of a static HTML mockup do not count as running Streamlit evidence.

## Verification categories

- **Offline deterministic:** pure presentation and inherited engine/M1/M2 test modules can run without Streamlit/SDK; log exact results.
- **Mocked agent adapter:** requires either real SDK mock tests or the inherited isolated shims; do not equate with live provider.
- **Streamlit AppTest/UI:** requires Streamlit and `google-genai` installed. Not verifiable in the coding container if DNS blocks installation.
- **Actual desktop/mobile browser, accessibility and downloads:** must be tested on a running Streamlit app; no simulated screenshot may be claimed as this.
- **Live Gemini:** not re-run by this UI pass; previous confirmed M2 smoke is reviewer-provided evidence only. New clarification flow is not live-verified without fresh check.

## Intentional constraints

- Product identity cannot be established if no product-level column exists. Choosing category is a *new explicit question*, not proof of the original product claim.
- Records ≠ orders ≠ units; user specifies intended metric. No currency symbols are inferred.
- Charts show up to 30 returned rows (not a hidden complete dataset). Exact large integers are displayed as text and maintained in JSON.
- The original AI response trace and calculation JSON are not edited to match display wording.
- The model may answer incorrectly or call an unrelated tool; evidence is visible but relevance/explanation remains unverified.
- True responsive and keyboard outcomes cannot be asserted from offline tests alone.

## Actual coding-container verification record

- `python -m unittest discover -s tests -p test_engine.py -q`: 23 passed.
- `python -m unittest discover -s tests -p 'test_m1*.py' -q`: 31 passed.
- `python -m unittest discover -s tests -p 'test_m2*.py' -q`: 25 passed, including isolated SDK shim tests (not pinned-SDK).
- `python -m unittest discover -s tests -p test_ui_contract.py -q`: 10 passed.
- Total deterministic + shim tests = **89 passing**.
- `python -m unittest discover -s tests -v`: **89 passing test methods and 2 module-import errors** (`google.genai` and `streamlit` not installed). Full discovery printed `Ran 91 tests ... FAILED (errors=2)` because it counts failed module load placeholders.
- `python -m pip install streamlit==1.64.0 google-genai==2.25.0 python-dotenv==1.2.3`: failed after repeated DNS resolution failures, not a verified package compatibility failure.
- **No new Windows or real Streamlit browser screenshots captured here**, no actual keyboard/responsive/download exercise, and no new live Gemini call. The prior confirmed M2 Windows and live results are reviewer-reported, and are not a substitute for P1–P3 verification.

### Review acceptance recommendation

Keep this candidate **pending** until a Windows reviewer can run the full suite and capture screenshots of the *running* Streamlit UI covering clarification, manual result, pending/confirmed Challenge, mobile width, keyboard traversal and download integrity. Do not begin M3 based solely on these offline passes.
