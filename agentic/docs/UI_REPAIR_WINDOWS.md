# UI repair candidate — required Windows / real Streamlit verification

This file does not assert these steps have already passed. Windows AppTest,
actual browser observation/screenshots and live Gemini must be recorded independently.
Do not upload `.env`, API keys, or personal datasets.

## Install and tests

In PowerShell from the extracted `byte-ml\agentic` directory:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v 2>&1 | Tee-Object ui_repair_windows_tests.log
.\.venv\Scripts\python.exe -m streamlit run app.py
```

The `unittest` exit status must be checked. PowerShell piped output may report
`Tee-Object` success even if Python exits non-zero; for an authoritative run,
execute ` .\.venv\Scripts\python.exe -m unittest discover -s tests -v `
without a pipe and verify no errors/failures.

## Real running Streamlit browser captures

Use a browser opened to the Streamlit application's local URL. Capture these
**from running Streamlit**, not the old static HTML design prototype.
Screen-capture filenames are suggestions; keep them outside any public archive
unless the images contain no personal information.

1. `01_analyse_desktop.png`: 1440x900 browser size. Demo CSV → `Summarise groups`
   → group `category`, metric `revenue`, operation `sum`, click `Run analysis`.
   Confirm Coffee=3000, Snacks=1400 as dataset-specific example and visible
   `How this was calculated` disclosure plus JSON download.
2. `02_clarify_product.png`: opt in to Gemini; ask `Which is the best-selling
   product?`. **Only if the actual model requests clarification**, inspect
   missing product warning and an unselected clarification approach. Select
   `Choose a grouping and calculation`, group `category`, `Total of “units”`,
   submit. Expected Coffee=100 and Snacks=70. If Gemini behaves differently,
   capture the actual result; the mocked AppTest isolates the deterministic
   clarification UI regardless of provider wording.
3. `03_clarified_challenge_pending.png`: from the clarified grouped result,
   expand `Challenge this clarified grouped finding`, add region equals North.
   Capture pending notice and exact baseline definitions.
4. `04_clarified_challenge_confirmed.png`: click `Run confirmed clarified comparison`.
   The result and JSON download should show; there must be **no simultaneous
   'not calculated or approved'** warning for the matching definition.
5. `05_challenge_changed_filter.png`: change North to South without reconfirming.
   Confirm previous comparison/result/download disappear; warning indicates
   pending edits. Reconfirm and capture updated comparison if desired.
6. `06_date_clarification.png`: use a live or mocked `request_clarification`
   for an ambiguous date such as 01/02/2026. Select `Explain the missing context`;
   type `Dates are DD/MM/YYYY`. Before clicking Continue, no new Gemini call
   is expected. Then submit and verify **original question** is retained and
   context travels in a separate field. Do not assume a particular live response.
7. `07_exact_integer.png`: with `docs/fixtures/overflow_ui.csv` uploaded,
   `Summarise groups`, group `g`, total `amount`, click `Run analysis`.
   Table MUST show `10,999,999,999,999,989` for A, and `No numeric value`
   for B. Download JSON and confirm the raw number is `10999999999999989`,
   B is `null` (not 0, not rounded).
8. `08_unknown_csv.png`: upload `docs/fixtures/unfamiliar_ui.csv`, use a
   natural-language question that requires clarification and inspect actual
   `City`, `QuantitySold`, `SalesTotal` choices. No product group invented.
9. `09_mobile.png`: Chrome DevTools > Toggle device toolbar, width 390 height
   844. Inspect title, selectors, buttons, table scrolling and Challenge
   confirmation. Capture genuine running Streamlit UI.
10. Review all five manual tools, tied group leaders, missing and absent groups,
    invalid filter errors, truncated previews, exact filter strings, consent
    checkbox, keyboard tab order and evidence downloads. Check that changing
    the source dataset cannot reuse a previously approved comparison.

## Optional synthetic provider check

Only use an existing local `.env` you maintain privately. To inspect live
model behavior, opt into Gemini and ask one normal question, one ambiguous
question and one valid comparison. Provider results are not guaranteed and
should not be reported as passed without observing tool calls and evidence.

## Runtime report format

For each result record: OS, Python version, Streamlit version, Git HEAD,
test counts, browser/version, viewport dimensions, redacted errors and
screenshot filename. Never print, commit or share `.env` or raw credentials.
