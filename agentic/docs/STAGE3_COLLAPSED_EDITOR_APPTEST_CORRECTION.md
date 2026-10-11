# Finding Watch — Stage 3 collapsed-editor AppTest correction

## Scope and provenance
- Required starting commit: `fc15de7f75cbafd1388efe453060c43b315b139b`.
- This change is **test-only**, apart from this handoff document. No application behaviour, calculation engines, Gemini agent, or Challenge state contract has been modified.
- Root cause: after `Confirm and compare`, the accepted Stage 3 UI intentionally hides the condition editor. The golden AppTest incorrectly tried to access the hidden `Value` selectbox immediately after confirmation.

## Regression changes

### `Stage3ChallengeAppTests.test_review_then_confirm_exact_golden_and_download`
1. Review North explicitly; ensure the proposal has not been executed.
2. Confirm; assert exact Coffee/Snacks golden totals, leader, and the original evidence download.
3. Assert the `Column`, `Condition`, `Value`, and change-action editor controls are **absent** after confirmation.
4. Click **Edit condition**; ensure completed comparison, reviewed plan, conclusion, download, and confirmation control are removed.
5. Explicitly select **Add condition → region → equals → South** in the visible editor; selecting must not create a review or execute a comparison.
6. Review; assert the executed definition is `region eq South` and that no result or comparison download exists yet.
7. Confirm again; assert Coffee 3000 → 1800, Snacks 1400 → 600; baseline 4 rows, alternative 2; original comparison download remains available.

### `Stage3ContainsTextAppTests.test_contains_uses_explicit_substring_and_requires_review_confirmation`
- Repaired the same obsolete post-confirmation assumption: the `Text to find` input is hidden while completed.
- Click **Edit condition**, assert cleared approval/review/download, explicitly set `contains Sou`, review, and confirm again; selected rows are 2.
- All prior checks of whitespace rejection, typed substring `Nor`, and exact filter identity remain.

## Test and runtime evidence
- `python -m unittest discover -s tests -v` from `agentic/`: **171 test entries: 169 passed, two import errors** for `google.genai` and `streamlit` (not 171 passes). This is the complete available offline suite.
- `python -m py_compile agentic/tests/test_app.py`: passed.
- `git diff --check`: passed.
- Streamlit 1.64.0 AppTests, actual browser interaction, Windows full suite and new live Gemini checks: **not executed** here. `streamlit` and `google.genai` are missing in this environment; configured package index could not supply Streamlit.
- Previous Windows/live results relate to the parent build; they do not verify this test correction.

## Windows rerun (same combined session, no separate extra manual round)
From the extracted archive's `byte-ml\agentic` directory:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_app.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Within the agreed consolidated Windows/browser review, verify the completed North Challenge and its unmodified JSON download, hidden editor, **Edit condition** clearing, South re-selection, fresh review, and fresh confirmation. Also verify the contains-text `Nor → Sou` edit journey. Do not provide credentials or local `.env` in any review package.

## Status
Candidate for independent review only. Stage 3 acceptance not claimed; no new milestone, memory, persistence, or Revisit work.
