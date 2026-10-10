# Finding Watch — Stage 1 review repair (candidate, NOT accepted)

## Scope and history

**Input Git HEAD**: `308da2760e279323acb9f100211a8e7d464953ed`.
The Stage 1 ZIP's 50 project files were compared byte-for-byte with a fresh Git-bundle checkout; exact match and clean original tree. The original Git bundle and historical commits are preserved in the release ZIP. Repairs apply only to the widget-download key contract and schema-driven date suggestions. No Stage 2, persistence, or Revisit.

`engine.py`, `specs.py`, `comparisons.py`, `agent.py` remain byte-for-byte unchanged.

## Changes

- `download_keys.py`: preserve existing surfaces and add `stage1_profile`, `stage1_local_result`, `ai_primary_result`, `ai_support_result`, `suggested_comparison`. AI primary/supporting and legacy AI trace keys **require** one-based trace position, with different keys for primary/supporting surfaces even at the same trace index. Nontrace locations require occurrence 0. Evidence content/hash is not used to create identity; the original JSON serialization is unchanged.
- `stage1_logic.py`: make month suggestion conditional on verifying *every* nonmissing date in the chosen column against a supported **exact** format. ISO `YYYY-MM-DD` needs literal shape, valid calendar dates, and pandas-supported timestamp range. Day-first `DD/MM/YYYY` or month-first `MM/DD/YYYY` is offered only when at least one observed date disambiguates the order; otherwise omit the suggestion. No trimming of nonmissing strings: the suggestion must be executable against the **unchanged** input values. This affects suggestions only, not the existing manual date-format picker.
- `tests/test_download_keys.py`: add surface/key stability, separate AI primary/supporting trace positions, invalid occurrence/type tests.
- `tests/test_stage1_logic.py`: add executed ISO/month-first/day-first examples, ambiguity, invalid/mixed formats, missing dates, whitespace, out-of-range dates, date-like IDs.
- `tests/test_app.py`: add five real Streamlit AppTest cases: profile + suggested result, confirmed suggested Challenge and pending edit, AI primary with identical supporting download, repeated identical AI outputs, inspection followed by grouped aggregation. These tests do not use a Streamlit shim and do not call the live provider.

## Verified local results

Run from `byte-ml/agentic` in the audit environment:

```bash
PYTHONPATH=".:tests" python -m unittest \
  test_download_keys test_engine test_m1 test_m1_repairs test_m2 \
  test_m2_agent_adapter test_stage1_logic test_ui_contract test_ui_repairs -v
python -m unittest discover -s tests -v
python -m compileall -q app.py stage1_logic.py download_keys.py ui_components.py tests
python -m streamlit run app.py
```

- **Offline deterministic and isolated adapter suite**: 118 / 118 pass (includes prior 109 and 9 new regression methods). Isolated adapter tests are **not** real-SDK mocked verification.
- **Unrestricted discovery**: 120 entries, 118 pass + **two import errors** from absent `google.genai` and `streamlit`; NOT a successful full-suite run.
- **Syntax compilation**: pass.
- **Actual Streamlit AppTest (including five added tests)**: **not executed here**; real `streamlit` package unavailable. The app launch failed with `No module named streamlit`. Package installation could not resolve the pinned packages from this execution environment's package index. No browser screenshots are claimed.
- **Real SDK mocked tests**: not executed; Google SDK unavailable.
- **Live Gemini**: not run; not requested for this repair. Historical live results do not validate this candidate.

## Windows verification (required before acceptance)

Use your already-private configuration; do **not** upload `.env` or share API keys.

```powershell
Expand-Archive -LiteralPath "$HOME\Downloads\BYTE_Finding_Watch_Stage1_REPAIRED.zip" -DestinationPath "$HOME\Documents\BYTE-Stage1-Repair" -Force
cd "$HOME\Documents\BYTE-Stage1-Repair\byte-ml\agentic"
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Expected **test result**: no import errors or failures; compare to real Windows output, **do not assume an expected count is a measured count**. Run targeted UI cases with:

```powershell
$env:PYTHONPATH = "$PWD;$PWD\tests"
.\.venv\Scripts\python.exe -m unittest test_app.Stage1DownloadLocationAppTests -v
```

Browser review (real Streamlit, not mockups):

1. Desktop 1365x900 and phone ~390x844: capture **entry**, **loaded example**, **submitted Coffee 3000 / Snacks 1400 revenue finding**. Examine clipping and keyboard focus.
2. Click **Profile all columns**, then **Analyse** the schema-generated revenue question. Both profile and local result remain accessible; evidence downloads must not throw `StreamlitDuplicateElementId`.
3. Confirm a **suggested** Challenge (`category eq Coffee`). It must show a completed comparison and a working downloaded JSON. Edit the filter and ensure the old result is hidden pending reconfirmation.
4. With Gemini responses mocked by the AppTests, verify AI primary/supporting output at the same trace index, two identical tool outputs at indices 1 and 2, and inspection followed by aggregation. Both calculations and their original downloads must remain accessible. Do not substitute a live-model text response for the fixed AppTest evidence.
5. Upload other real CSVs via UI: ISO `2026-01-10`, unambiguous `13/02/2026`, ambiguous `01/02/2026`, invalid `2026-02-30`, mixed formats, date with surrounding spaces, and unsupported old dates. Only valid, unambiguous, engine-executable date columns may generate a direct monthly question. For ambiguous dates use advanced time analysis only after explicitly choosing a date format. Check that malformed date data are never silently removed by a suggested calculation.
6. Inspect JSON downloads and confirm exact equality to source evidence, including large integer `10999999999999989`, null values and unmodified specs. Run all five manual tools and existing confirmation/stale protections.

## Limitations / review questions

- Suggestions are heuristic, bounded UI templates rather than model understanding. Date columns without safe full-column interpretation receive no auto monthly suggestion; manual analysis permits explicit format choice.
- This is a **source candidate**, not accepted. Windows full Streamlit AppTests and real desktop/phone browser review must pass before approval.
