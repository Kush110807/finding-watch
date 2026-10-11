# Finding Watch — Stage 3 Combined Windows Repair Handoff

**Scope:** Four Windows review causes only. No memory, persistence, Revisit, new analytical tools, or redesigned Challenge flow.

## Source and log provenance

- Starting commit: `5f3cda6bca300286875684dee73a38d12a47a11f`
- Starting ZIP: `BYTE_Finding_Watch_Stage3_FOCUSED_REPAIR.zip`
- The supplied ZIP's Git bundle was cloned with `git clone -b main`, showing 18 starting commits and an exact tracked-file match.
- **Important:** `full_suite_windows.log` was not present among the available conversation attachments or inside the source ZIP. The four Windows failure descriptions in the user's instruction were used; the stated `223 tests, 3 failures, 4 errors` is user-provided historical evidence and has **not** been independently parsed from that log.

## Actual repairs

1. **Result selection:** `app.py` now passes *unique readable strings* directly to `st.selectbox` without `format_func` or an unselected `None` option. A real, first option, `Choose a calculation`, maps to no calculation. `stage2_logic.result_option_map()` maps each distinct labeled choice back to its exact one-based trace occurrence and original event. This avoids Streamlit AppTest's formatted-integer/placeholder mismatch while preserving explicit user choice, duplicate occurrence identity, and question/dataset/response scoping. The widget key is versioned `stage2_result_choice_v2_...` so old integer-valued widget state cannot leak into the new option contract after a hot reload. Choosing the neutral option clears any previously approved selected-Gemini Challenge.
2. **Profile evidence download:** The AppTest now expects the approved actual default label `Download complete, unmodified calculation evidence` and retains the location key and separate original-JSON payload assertions.
3. **Gemini-proposed comparison confirmation:** The AppTest checks the real confirmed heading, state (`status=completed`), `CONFIRMED` success, distinct comparison JSON download, absence of pending warnings, and disappearance of the result/download after question edits. No automatic confirmation is introduced.
4. **Gemini Challenge fixtures:** `inspect_dataset + grouped_summary` now has a direct Challenge AppTest without a picker. A different fixture containing *inspection and two legitimate grouped summaries* exercises explicit selection, confirmation and switching, asserting that prior Challenge approval/download disappear and that supporting inspection/download identities survive.

## Verification performed in this environment

- `python -m compileall -q agentic`: passed.
- `git diff --check`: passed.
- Standalone suite excluding SDK- and Streamlit-importing modules: **160 tests passed**.
- Full `python -m unittest discover -s tests -v`: **160 passed; 2 module import errors** (missing `streamlit` and `google.genai`). No application/SDK AppTest is counted as executed. A package-install attempt failed: local package index reported no matching `streamlit==1.64.0` release.
- No real Streamlit browser screenshots or fresh live Gemini calls were captured in this container.

## Windows command and acceptance checks

Run from the extracted ZIP's `byte-ml\agentic` folder with your existing private local configuration. Do **not** upload `.env` or publish API keys.

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_app.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m streamlit run app.py
```

In one combined final browser session (not an extra intermediate round), check:

- Both the `inspect + grouped` direct Challenge and the `inspect + two grouped calculations` result-choice Challenge.
- Result picker starts on **Choose a calculation** and displays no unsolicited answer, and identical grouped calls remain distinct.
- Selection changes and returning to the neutral option remove prior selected-Gemini approval and comparison download.
- New responses/question edits cannot restore an older selection.
- Profile download carries the exact approved wording; its original JSON, all selected result JSON, and repeated download widget IDs are unchanged.
- Proposed comparison requires confirmation, then shows confirmed UI and JSON; question edits hide the confirmed result.
- Existing five manual analytical tools, ordinary Analyse, consent, clarification, stale-state handling and Challenge confirmation remain usable.
- Desktop and approximately 390px phone browser layouts, and a fresh custom Gemini tool-selection + clarification interaction should be reported separately as browser/live verification, not inferred from mocked tests.

## Protected modules

`engine.py`, `specs.py`, `comparisons.py`, and `agent.py` are byte-for-byte unchanged from the specified starting commit.

**Status:** candidate for independent review, not accepted. Do not begin another milestone.
