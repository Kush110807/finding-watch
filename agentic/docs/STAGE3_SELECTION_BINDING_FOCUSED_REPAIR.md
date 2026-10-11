# Stage 3: result-option import and selected Challenge invalidation

Status: **candidate for independent Windows review** (not accepted).

## Source / repair scope

Required parent: `3e8e7b48d225c9c11da9db269fed3057c33d2e97`.

The parent checkout was inspected before editing: clean `main` branch with the full 19-commit lineage. No uncommitted work needed recovery. Only Stage 2 UI-state glue, the app import/binding, and their regressions are modified. The analytical modules `engine.py`, `specs.py`, `comparisons.py`, and `agent.py` remain unchanged.

### Defects addressed

1. `app.py` called `result_option_map(choices)` without importing it. The module now imports it directly from `stage2_logic` so the actual multiple-calculation UI route no longer raises `NameError`.
2. A confirmed selected-Gemini Challenge could survive `grouped_summary -> time_trend -> same grouped_summary`, because `show_challenge()` was not rendered for the intervening time result. A response-scoped, trace-position-aware selection binding now runs before any conditional Challenge rendering. On a **different response scope or occurrence** (including `None`/neutral) it clears the completed selected-Gemini comparison, review, editor, and context. On the **same** occurrence it preserves state. This applies to identical output occurrences because positions are stable and distinct.

No modification to the result picker’s existing string-option/neutral-choice contract, baseline calculations, evidence bytes, confirmation gate, or download-key contract was needed.

### Added verification

- Three offline state tests: grouped → non-grouped → grouped, ordinary same-selection rerender, new response/neutral choice, and invalid trace positions.
- One genuine `streamlit.testing.v1.AppTest` regression (requires Streamlit and `google.genai`) drives the UI's multiple-result picker with inspection + grouped + time results, confirms a Challenge, rerenders to check that confirmation persists, switches to time and back, confirms the earlier Challenge is **gone**, then requires a fresh review and confirmation.
- Existing AppTests for identical occurrences, response resets, unique downloads, and direct grouped Challenge remain intact.

### Actual local checks

- Offline modules excluding SDK-dependent `test_agent.py` and Streamlit `test_app.py`: **163 passed**.
- Full discovery: **165 entries: 163 passed, 2 module import errors**, for `google.genai` and `streamlit`; therefore not a full pass.
- `pip install --no-deps streamlit==1.64.0 google-genai==2.25.0` failed: configured index reported no matching `streamlit==1.64.0` distribution.
- Real Windows Streamlit AppTests, browser interaction and live Gemini: **not executed here**. No live-model success is claimed.

### Windows: rerun from the extracted ZIP

Open PowerShell in the extracted `byte-ml\agentic` folder:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_app.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Check the actual app: select two calculations with different tools, approve a grouped Challenge, switch to the non-grouped result, switch back, and verify that old approval/downloads do **not** reappear. Staying on the same selected occurrence through a harmless rerender must retain a confirmed result. Separately, verify repeated identical result occurrences and the neutral picker option. The existing Stage 2/Stage 3 combined desktop, ~390px phone, and live-provider checklist remains unchanged. No key or `.env` file is included in this package.
