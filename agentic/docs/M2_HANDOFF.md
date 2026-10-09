# Finding Watch M2 — Challenge a Finding (candidate, review required)

## Baseline and scope

- Starting accepted M1 commit: `4eb7ec4fffa4de1709bd34fc099e1b613c7403e1`.
- M2 implements ONLY a reproducible comparison between two `grouped_summary` specifications.
- Exactly **one** filter condition may be added, removed, or replaced. Reordering without changing the filters is not a valid challenge. Multiple changed conditions are rejected.
- Aggregation arguments (`group`, `metric`, `operation`) must match. `display_limit` is a presentation cap, not an analytical assumption.
- No memory, Revisit, forecasting, joins, external DB, or UI redesign was implemented.

## Data integrity and evidence

`comparisons.prepare_comparison(df, baseline, challenged)` validates and previews the changed condition without executing a comparison. `comparisons.execute_comparison(df, baseline, challenged, expected_fingerprint=...)` validates again, evaluates both scenarios on the **same DataFrame**, then matches groups by typed `group_value` (not row position). This uses M1's private full-result path **before display truncation**. Public `engine.execute_spec` retains its M1 display-limit contract.

The comparison contains: same dataset fingerprint; both exact normalized specs; operation and filter accounting for both calculations; independently calculated complete group rows; per-group baseline/challenged presence, values, row counts and exact integer deltas; complete lists of all tied leaders; a visible preview cap; and a warning that a changed inclusion rule answers a different question. Missing groups and zero/all-missing numeric results are distinct. Grouping nulls are represented by JSON `null`, and a present group with all-missing metrics has `value: null`, not zero. Deltas with absent or all-missing values are `null`, not inferred zeros. For floating values, ties use exact numerical equality.

**Important:** M1's guard against floating accumulation overflow and exact Python integer summation remain intact. Very large integer JSON values are exact when parsed by integer-safe readers, but JS viewers and spreadsheets may round numbers beyond 2^53. SQL/Excel export is not provided. Only aggregation `sum`, `count_rows`, `mean`, `min`, `max` for grouped data; no significance or causality claims.

## Manual and Gemini workflows

1. In Streamlit, submit an M1 **Summarise groups** calculation; expand *Challenge this submitted grouped finding*.
2. Choose one condition to add/remove/replace, inspect the **baseline submitted spec**, **challenged pending spec**, and changed condition. Click **Run confirmed manual comparison**. The submission is bound to the same dataset fingerprint and baseline; editing settings hides the old comparison until reconfirmation.
3. Or ask Gemini for a challenge to the last submitted grouped analysis. Gemini may call `propose_grouped_comparison` (workflow adapter, NOT a sixth analytical tool). The adapter validates definitions and returns `comparison_pending` without computing. The UI previews both specifications and demands **Confirm and run proposed comparison**. It binds the confirmation to the submitted question, proposal, and dataset hash. User must inspect the model-proposed definitions; model explanation is explicitly unverified.
4. The existing five real tools (`inspect_dataset`, `filter_rows`, `grouped_summary`, `time_trend`, `correlation`) remain in place and are not replaced by comparison wrappers.

## Golden synthetic example (independently calculated)

`category,status,revenue` rows: Coffee completed 120, Coffee completed 90, Coffee cancelled 300, Snacks completed 180, Snacks completed 100.

- Baseline, no filters: 5 selected; Coffee 510, Snacks 280; Coffee leads.
- Challenge, add `status eq completed`: 4 selected, 1 excluded; Coffee 210, Snacks 280; Snacks leads.
- Difference (challenged minus baseline): Coffee -300, Snacks 0.
- Changed leader **does not invalidate** the baseline; different inclusion assumptions answer different questions.

`M2_example_comparison_evidence.json` is produced by the real deterministic executor on this synthetic CSV.

## Tests and environments

Run from `agentic`:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Offline M2 tests (`tests/test_m2.py`) cover: golden, unaffected leader, ties, missing group labels, all-missing values, disappearances vs zero, empty selection, malformed input, unsupported operations, adding/removing/replacing conditions, invalid multi-change, argument preservation, sequential exclusion accounting, exact huge sums and integer differences, label-based matching, truncation, unfamiliar schema, input immutability and fingerprint mismatch. `tests/test_m2_agent_adapter.py` uses an **isolated SDK shim** to check the no-execution proposal gate; this is NOT real SDK verification. Actual SDK contract tests in `tests/test_agent.py` and Streamlit AppTest tests in `tests/test_app.py` must run on Windows with pinned dependencies. Do not claim they passed from this environment when missing dependencies prevent execution.

### Optional actual Gemini M2 smoke (synthetic only)

Requires an existing private `agentic/.env` or environment config. Do not share, print, commit, or package secrets.

```powershell
.\.venv\Scripts\python.exe verify_live_comparison.py --output live_comparison_local.json
.\.venv\Scripts\python.exe verify_live_comparison.py --confirm --output live_comparison_confirmed_local.json
```

Without `--confirm`, a proposed comparison is shown and logged but **not executed**. With `--confirm`, inspect both specs and type `CONFIRM` to execute and independently check golden values. Real Gemini tool selection and its schema validation are unverified until the Windows live run succeeds. Inspect local JSON before sharing; the project archive excludes `.env` and any `live_*_local.json` logs.

## Deliberate limitations

- Only one changed filter; no compound sensitivity experiments or causal claims.
- If either scenario filters to zero records, M1 rejects it with `AnalysisError`; no invented empty result.
- No memory, saved findings, dataset version reconciliation, or multi-turn conversation history. The last submitted grouped finding in the current Streamlit session is the optional baseline for a follow-up question.
- Agent-proposed definitions are **not** trusted business definitions; user must confirm or edit manually.
- UI/SDK tests must be completed in Windows with actual dependencies. A successful M0 run from prior review does **not** count as M2 live verification.
- Dataset hash is based on the uploaded immutable raw CSV. Mutating a DataFrame manually after loading may invalidate that provenance; do not mutate analysis input frames.

## Local implementation verification on this candidate

- **Baseline Git HEAD:** verified exact `4eb7ec4fffa4de1709bd34fc099e1b613c7403e1`, unchanged ZIP checkout before edits.
- **Offline deterministic:** `python -m unittest discover -s tests -p test_engine.py -q` → 23 passed; `-p 'test_m1*.py'` → 31 passed; `-p 'test_m2*.py'` → 25 passed (19 comparison + 6 isolated SDK-shim adapter). Total **79 tests passed**.
- **Full discovery:** `python -m unittest discover -s tests -v` → 79 tests passed and **2 module import errors** (`google.genai`, `streamlit` absent). No claim of full-suite pass.
- **Pinned SDK and Streamlit AppTests:** added/updated; **not executed** in this container. `pip download --no-deps streamlit==1.64.0 google-genai==2.25.0 python-dotenv==1.2.3` failed at DNS resolution. This does not demonstrate a package/version incompatibility.
- **Windows:** no access to the user's local laptop during this implementation. The user's previous successful M1 Windows and M0 tests do not validate M2.
- **Real M2 Gemini:** not run; `verify_live_comparison.py` explicitly requires local existing configuration and manual approval.
