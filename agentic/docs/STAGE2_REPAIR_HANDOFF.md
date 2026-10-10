# Finding Watch — Stage 2 targeted repair handoff

**Scope:** Repair only the grouped-result UI column collision, filtered-record preview accounting, and the stale provider-error Streamlit AppTest assertion. No Stage 3, memory, persistence, or Revisit. The accepted Stage 1 UI and existing Stage 2 flows are retained.

## Git and protected modules

Starting commit: `21bee55a1655d89aeb449f36fa18696add471c0b`

The supplied source ZIP's Git bundle was cloned explicitly on branch `main`; its starting HEAD was exactly the required SHA, with 14 historical commits and zero tracked-file differences between the archive and checkout. `agentic/engine.py`, `agentic/specs.py`, `agentic/comparisons.py`, and `agentic/agent.py` are unchanged.

## Changes

- `presentation.py`: The presentation-only `unique_presentation_columns` contract keeps every field distinct when dataset group names collide with metric or accounting labels. `simple_group_table`, detailed group accounting, and time-period display labels use this contract. Source evidence, JSON and numeric types are unchanged. Adds `preview_counts`, which separates matches, engine-returned rows and actually displayed rows.
- `ui_components.py`: The grouped detailed accounting table uses the collision-safe formatted adapter instead of potentially colliding `DataFrame.rename` labels. Filtered-record captions show **Matching**, **Returned** and **Shown in table** as separate counts. The main table still respects the 12-row UI cap; the engine's original result and download are untouched.
- `tests/test_stage2_repairs.py`: Eight offline regressions for the reviewer CSV, accounting-label collisions, exact integer/null retention, engine truncation versus UI cap, and unchanged example labels.
- `tests/test_app.py`: Fixes the old phrase `did not complete` to assert the actual provider recovery message (`could not complete`) **and** retry, settings, local-suggestion paths, preserved question and absence of an unrelated finding. Adds actual Streamlit AppTests for both collision and preview counts; these require Streamlit and Gemini SDK dependencies.

## Reviewer fixtures and expected values

### Colliding grouped column names

```csv
Total revenue,revenue
Coffee,10
Snacks,5
```

Run grouped summary with group `Total revenue`, metric `revenue`, operation `sum`. The user-facing table must show **Total revenue (group)** = Coffee/Snacks and **Total revenue** = 10/5. The technical group-accounting table retains those identities and separate counts. The engine evidence and JSON remain the unmodified original objects.

### Filtered preview

Use 13 records matching one condition, with `display_limit=100`. The summary must report **13 matching**, **13 returned**, **12 shown in table**. With engine `display_limit=5`, the corresponding counts are **13**, **5**, **5**, and the engine truncation warning remains. Both cases display original row values, including leading-zero identifiers.

### Provider error

After a mocked status `error` or local provider exception, show one concise recovery message with **retry Analyse**, **connection settings**, and **local suggested questions**. Preserve the question and do not show an earlier successful finding as its answer. Provider-specific details remain behind an expander; no credentials are included.

## Test results (authoring environment, actual)

Baseline before repair: the full discovery runner reported `Ran 136 tests ... FAILED (errors=2)`; exactly **134 individual tests passed**, with two failed imports (`test_agent` because `google.genai` was unavailable, and `test_app` because `streamlit` was unavailable). It did **not** pass 136 tests.

After repair:

- `python -m unittest discover -s tests -p 'test_stage2_repairs.py' -v`: **8 passed**.
- `python -m unittest discover -s tests -v`: **142 individual tests passed**, **two import errors**, `Ran 144 tests ... FAILED (errors=2)`.
- Explicit discovery of every `test_*.py` module except `test_agent.py` and `test_app.py`: **142 passed, 0 failures/errors**.
- `python -m compileall -q .`: **passed**.
- Pinned SDK-mock tests in `test_agent.py`: **NOT executed**.
- Actual Streamlit AppTests in `test_app.py`: **NOT executed**, including new regression tests.
- Running browser checks and desktop/mobile screenshots: **NOT executed/captured**.
- Live Gemini: **NOT executed**; previous reports are not fresh verification.

Attempt to install `streamlit==1.64.0` and `google-genai==2.25.0` through the configured package index returned **No matching distribution found**. Neither dependency is installed in this environment. This is a dependency-access blocker, not a passed runtime test.

## Windows verification (PowerShell)

From an unzipped release directory:

```powershell
cd "$HOME\Documents\BYTE-Stage2-Repair\byte-ml\agentic"
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Run targeted tests separately if needed:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_stage2_repairs.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_app.py -v
```

Inspect the *running* app: test a manual grouped result from the collision fixture, then an AI result displaying the same returned evidence; confirm both table columns show Coffee/Snacks and 10/5 and the technical accounting is intact. Test a returned 13-row filtered result with UI showing 12, plus engine limit 5 showing 5. Confirm no duplicate download widget errors, original JSON exactness, repeat-call trace identity, stale-result guards, previous question retention and retry guidance. Take desktop and ~390px phone screenshots if desired for runtime evidence. Existing Gemini credentials should stay solely in the user's local private configuration; never include `.env` in review archives.

**Review disposition:** source candidate only; Stage 2 acceptance not claimed. No Stage 3 work started.
