# Stage 2 — Windows AppTest assertion repair (candidate, not accepted)

## Provenance and scope

- Required parent commit: `9804090d547b1841c84b2352d9823f63d42fbbc6`.
- User-supplied Windows review: 201 tests, 10 failures and 4 errors; detailed Windows trace is not present in this package. The independent review attributed them to eight download assertions, four formatted-selectbox choices, and two stale state/recovery assertions.
- This repair edits **only `agentic/tests/test_app.py`** plus this handoff. No application or agent behavior was changed.
- `engine.py`, `specs.py`, `comparisons.py`, `agent.py` remain unchanged.

## Exact corrections

1. **Download widgets.** Assertions use `at.download_button`, not `at.button`. The helper `_assert_download()` also checks a download's label and retrieves it using its explicit key from the existing `download_keys.evidence_key()` contract. The tests now require simultaneous unique locations/occurrences for manual, profile, local suggestion, confirmed Challenge, primary AI, support AI, and original AI-response evidence. Repeated identical AI calls are inspected at trace positions 1 and 2; inspection followed by grouped aggregation checks both support downloads. The pre-existing monkeypatch test still asserts the complete exact JSON payload (`10999999999999989` and `None`), MIME type, and download key.
2. **Result choice.** Four AppTest interactions now use `select_index(0)` / `select_index(1)` for the Streamlit selectbox that presents formatted text but stores integer trace positions. The app's integer selection contract is unchanged. Tests continue to check occurrence selection, edit hiding and re-submission reset.
3. **Question edits and error recovery.** The stale warning check now targets the current `st.info` and also verifies that the prior finding and result download are not visible. The provider-failure check now requires the actual recovery message, preserved original question, retry Analyse button, connection-settings guidance, local-question guidance, and no obsolete finding/download.

No assertion was skipped or removed. Other `at.button` usage for *regular action buttons* was intentionally retained.

## Verification actually executed in this environment

- Baseline ZIP source matched the full-history Git checkout byte for byte (no source mismatch).
- `python -m compileall -q agentic/tests/test_app.py` — passed.
- `git diff --check` — passed.
- All eleven non-SDK/non-Streamlit offline test modules — **142 passed, 0 failures, 0 errors**.
- Full discovery — **144 tests discovered/run; 142 passed; two import errors** because `streamlit` and `google.genai` are not installed here.
- Attempted `pip install streamlit==1.64.0 google-genai==2.25.0`; configured index returned no available release. No successful real AppTest run or browser launch occurred here.
- Git history/ZIP recovery checks performed after release packaging; see release response.

The reported earlier Windows results are *not* post-repair results.

## Windows re-verification

Run in PowerShell in the unpacked `byte-ml\agentic` directory:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_app.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m streamlit run app.py
```

The first test command should exercise real Streamlit's `AppTest.download_button` and `Selectbox.select_index` without live Gemini access; SDK code is imported but `agent.ask` is patched in the relevant AppTests. If anything fails, preserve the full failure traceback and test name for focused review. Do not treat mock calls as live model verification.

Manually inspect: (1) profile + suggested local result, (2) manual result + identical AI result, (3) two identical AI trace calls selected individually, (4) inspection then grouped primary result, (5) confirmed Challenge then changed condition, (6) edit after prior answer, and (7) provider error with question intact and retry/local guidance. Confirm downloads are available and their JSON is unchanged. Do not upload `.env` or credentials.

## Remaining limitations

The real Streamlit AppTest suite and desktop/phone browser screenshots were **not executed/captured** in this environment. Candidate acceptance requires Windows post-repair tests and review. No Stage 3, persistence, memory, Revisit or Challenge redesign is included.
