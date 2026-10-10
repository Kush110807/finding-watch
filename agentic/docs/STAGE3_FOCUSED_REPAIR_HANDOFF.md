# Finding Watch — Stage 3 focused repair (candidate, not accepted)

## Provenance and scope

- Starting HEAD: `26052bcffad26febaea5bf22c2b3a57d524d3009` (17 commits).
- Changes are restricted to `challenge_logic.py`, `challenge_ui.py`, relevant tests, and this note.
- `engine.py`, `specs.py`, `comparisons.py`, `agent.py` remain untouched.
- Open → Choose → Review → Compare, one-change restriction, explicit confirmation, stale-state invalidation, existing evidence downloads and download keys are preserved.
- No persistence, memory, Revisit, or follow-on stage was implemented.

## Repair 1 — collision-safe comparison headings

`comparison_display_rows` now uses the pre-existing `presentation.unique_presentation_columns()` helper for the four roles: group, original value, alternative value, difference. The calculated-value columns retain their normal names; a grouping field named `original`, `alternative`, or `difference` receives a distinctive `(group)` suffix. This changes UI labels only and never mutates the result or downloadable JSON.

Regression: all three colliding field names; four groups, including an exact 10,999,999,999,999,989 integer, a zero, an absent group, and a group with only missing numeric values. Assert all four headings unique, full group identity retention, unchanged source JSON and exact differences.

## Repair 2 — contains-text value entry

The `contains` operator now always displays a separate **Text to find** input. It accepts an explicitly typed literal substring, including when the column has <=60 unique values; neither opening the editor nor entering blank/whitespace-only input creates an actionable proposal. It preserves exact entered nonblank text rather than converting to an existing whole-cell value. The engine already matches a literal substring (`regex=False`); no engine change was needed. Length is limited to the existing specification maximum of 256 characters. Equality/inequality keep their distinct existing-value selection, as do missing-value conditions.

Regression: explicit substring `North` selects `North East` and `North West` and leaves `South` out, whereas equality to `North` has no matches. Invalid/empty/overlong inputs are refused. A real Streamlit AppTest covers opening, entering blank text, review, confirmation, JSON download, stale-result invalidation and equality-mode input. These AppTests were **not executed here** without Streamlit.

## Actual local verification

- All 157 available offline tests passed (`157 tests; 0 failures; 0 errors`).
- Full discovery: 159 entries: 157 passes, **2 module import errors**, specifically `test_app` missing `streamlit` and `test_agent` missing `google.genai`.
- Python compilation and source diff checks passed.
- `pip install streamlit==1.64.0 google-genai==2.25.0` failed against the current package index (no Streamlit distribution returned). No running Streamlit screens or fresh live provider calls were verified.
- Source ZIP and Git bundle integrity are checked independently at release.

## One consolidated Windows / browser / live-provider session

Use the **existing** checklist in `docs/STAGE3_CHALLENGE_HANDOFF.md` for combined Stage 2 and Stage 3 acceptance. Do not initiate a separate manual screenshot session just for this narrow repair. During the already planned final session, add only these assertions to the Challenge section:

- Group by `original`, `alternative`, and `difference` on small CSVs: every group name survives, numerical columns are distinct, exact integers/null/absent groups remain correct, original JSON downloads remain unchanged.
- With `region` values `North East`, `North West`, `South`: select **contains text**, enter `North` (not a whole value), confirm both North records match. Blank input cannot be reviewed. Verify `is`/`is not` still offer existing values and explicit missing filters remain separate.
- Verify the responsive text input and comparison heading at desktop and ~390 px along with the existing suite of Stage 2/3 cases.

From extracted `byte-ml\agentic` in PowerShell:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_app.py -v *> app_test_windows.log
.\.venv\Scripts\python.exe -m unittest discover -s tests -v *> full_suite_windows.log
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Report Windows AppTest, full suite, actual browser screenshots, and live-Gemini outcomes separately. Use the user's existing private provider configuration and opt-in consent; never send API keys or `.env` in a handoff.
