# M1 handoff — composable analysis & evidence

M1 code candidate, not accepted. **No Challenge, SQLite memory, Revisit, or UI redesign**. This document accompanies the full preserved Git history in `phaseM1-history.bundle`.

## Scope

- `AnalysisSpec.parse` in `specs.py` strictly whitelists five tools and their fields; at most 8 conjunctive (AND) filters; operations limited to numeric group statistics, explicit-date time buckets, Pearson correlation, dataset inspection and bounded record preview. `display_limit` is 1–1000, default 100.
- `engine.execute_spec(df, spec)` filters the **full dataset** in order, then calculates. Preview records cannot feed any aggregation. Legacy `run_tool` routes through the same executor. Direct legacy deterministic tool functions remain for existing tests and callers.
- `load_csv` reads all fields initially as text. It infers numeric values **only when unambiguous and finite**, preserving leading-zero values and identifier-like column names as text. This intentionally differs from Phase 3, where pandas silently converted `0012` to `12`. If a metric is a textual mixed/ambiguous column, analysis refuses: no implicit coercion or cleaning. Explicit `%Y-%m-%d`, `%d/%m/%Y` or `%m/%d/%Y` date interpretation is required. More formats/overrides are deferred.
- Evidence includes full SHA-256 of original CSV bytes (`dataset_fingerprint_sha256`); normalized `executed_spec`; `input_rows`, `selected_rows`, `excluded_by_filters`; per-filter sequential counts; operation-specific exclusion partitions; result payload; display truncation metadata; warnings. `dataset_id` remains a 16-character compatibility alias. Caller-generated DataFrames use a derived canonical fingerprint instead of original bytes.
- Manual Streamlit controls include optional AND filters for grouped/time/correlation analyses. Results are stored with their exact submitted arguments and dataset fingerprint; pending edits hide old manual results. AI output displays its exact submitted question/fingerprint and warns if there are unsent question edits. Trace evidence is shown separate from **unverified** model explanation.
- Agent now declares optional AND filters on grouped/time/correlation tool calls. At least one successful tool call can yield status **`evidence_available`**, not `answered`; this verifies a deterministic *calculation*, **not** the semantic relevance of the selected tool or model's narrative. An unrelated successful tool never counts as independently proven answer correctness. Clarification calls are logged in trace.
- M0 synthetic-only `verify_live.py` tests two genuine tool types and explicit clarification using local Gemini; see `M0_WINDOWS.md`.

## Missing-value and overlap accounting

- `excluded_by_filters = input_rows - selected_rows`. Each filter sees only the preceding selected population. `newly_excluded` partitions are sequential and disjoint even if conditions overlap. Missing values do not match ordinary equality, inequality, ordered comparisons, or contains; `is_missing` / `not_missing` are explicit.
- **Grouped:** Rows with a missing group label remain in a `null` group; they are **not** group exclusions. Row counts include selected rows even if the metric is missing. `missing_metric_excluded_from_values` counts rows omitted from numeric values (including null group labels with missing metrics). All-missing group sums produce `null`, not zero. Therefore do not add `missing_group_labels_included` to exclusion counts.
- **Time:** All `missing_date_excluded` are omitted from period row counts. For numeric operations, `missing_metric_with_valid_date_excluded_from_values` counts distinct omissions in date-valid rows. `missing_metric_and_date_overlap` is disclosed but **not** added again; `excluded_from_numeric_values_union = missing_date_excluded + missing_metric_with_valid_date_excluded_from_values`. Nonempty invalid dates cause explicit rejection, not silent omission.
- **Correlation:** `missing_x_only`, `missing_y_only`, `missing_both` partition exclusions. Their sum equals `excluded_incomplete_pairs_union`; complete pairs plus that union equals `selected_rows`.
- Filter exclusions happen **before** these operation omissions; never add overlapping totals from different populations.

## Operational limitations and blockers

- No schema-mapping UI or explicit casts for ambiguous numeric values; clean a **copy** of data if an ID-looking text field genuinely represents a numeric metric. Dates supported at day precision only. No model-generated arithmetic/formulas, forecasting, joins, memory, causal inference or auto-detection of business meaning.
- Agent function schemas and full Streamlit flow **not runnable in the delivery environment** because pinned SDK and Streamlit are missing and package network resolution failed. Local Windows test is mandatory. The mock tests exist in source but have not been re-run with the pinned SDK in this environment.
- M0 live Gemini **not run**: user's private credentials are intentionally unavailable. The provider may reject a tool declaration or fail on quota/access/service. Capture redacted log using `verify_live.py`.
- At most 1,000 result rows are displayed; default 100. The agent additionally caps returned tool-result JSON to 40,000 characters. A wide/large response can trigger a bounded failure; there is no automatic replanning. Tool relevance and narrative accuracy are not mechanically proven.
- Identifiers with misleading names may still need manual review; inference is conservative, not a universal semantic classifier.
- Only offline engine tests were run here; no claim of accepted milestone or finished recruitment task.

## Offline verification

From `agentic` directory:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_engine.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_m1.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Expected fixtures include 1,500 selected records aggregated to 1,500, missing-date/metric intersection and union, composite AND filtering, null group labels, ties, valid/invalid specifications, CSV identifier preservation, immutability and unseen schemas. The final command also runs SDK-mocked agent tests and Streamlit AppTest on Windows with required dependencies.

**Baseline:** `6bf87e8386cb6b8360c95d1aa4aff56d9d9ea774`; target final commit hash recorded in the accompanying handoff message.
