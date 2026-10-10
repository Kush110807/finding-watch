# Finding Watch — Stage 2 Candidate (for independent review)

## Scope / baseline

Start: `f1f3d62dc342aae1ddefa84370401a322862bc62` (accepted Stage 1).
Stage 2 exclusively extends Streamlit presentation and UI state. `engine.py`, `specs.py`, `comparisons.py`, and `agent.py` are byte-identical to the baseline. No memory, Revisit, forecasting, arbitrary code, or Challenge redesign.

## Source changes

- `presentation.py`: evidence-derived, truthful descriptive headlines for all five tools; readable preview columns and dates; material exclusions; exact integers formatted before DataFrame creation. Missing periods are never filled or considered zero. No invented currency, unit, confidence, or causal meaning.
- `ui_components.py`: compact supporting tables and safe charts; evidence and original downloads remain under *How this was calculated*; inspection quality, filtered match/preview accounting, time format/scope, correlation pair count/caveats; existing comparison UI untouched.
- `stage2_logic.py` (new): pure multi-result choice descriptors, question/dataset/response/submission-scoped selection keys, bounded explicit clarification context composition, controlled UI recovery categorization.
- `app.py`: unverified multi-tool results require explicit choice, with 1-based trace occurrence identity; input changes hide old results; contextual follow-up carries previous explicit context and resets the edit field for each new provider response; distinguished failed calculation vs provider failure; phone-friendly full suggestion label; existing consent and Challenge paths intact.
- `tests/test_stage2_logic.py` (new): offline engine-driven presentation and state tests.
- `tests/test_app.py`: real Streamlit AppTest contracts for five tools, multi-result selection, clarification follow-ups, stale responses, provider failure. No provider network access; `agent.ask` is patched in tests.

## Important behaviour

1. **Inspect:** number of data rows, column count, empty-value and duplicate information. This does not claim accuracy validation.
2. **Filter:** selected/matching count separately from returned preview count, criteria, exact identifiers and missing cells; truncation visible.
3. **Group:** totals/averages/min/max/count, tied leaders, missing numeric groups, safe chart limits, no misleading global leader when display truncated.
4. **Time:** specified metric, date column, explicit date format and bucket size, only observed periods, material missing-date/metric exclusions; chart only for safe complete values.
5. **Correlation:** Pearson coefficient, actual complete-pair count and non-causation warning; rejected calculations shown as recovery states.
6. **Multiple operations:** inspection is supporting when a substantive calculation exists. For several substantive operations, the user chooses by full metric/group/filters/period definition; identical occurrences remain separate and keys reset across question/dataset/response/repeated submission.
7. **Clarification:** original submitted question retained. Group/metric selections cannot trigger calculation before explicit submit. Context can be added across up to 2,000 characters without parsing prose into specs; new response uses a fresh context text input. Edited definitions hide earlier results and Challenge.
8. **Failures:** a provider error, a rejected calculation, and insufficient user detail display different paths; old successful findings are not substituted for failed new answers.

## Verification categories

### Local offline

Run in `byte-ml/agentic`:

```powershell
py -3.13 -m unittest discover -s tests -p test_stage2_logic.py -v
py -3.13 -m unittest discover -s tests -v
```

A full discovery import error from an absent SDK or Streamlit does **not** count as a test pass. See accompanying review handoff for actual run results.

### Windows real Streamlit AppTest / browser (required before acceptance)

```powershell
cd byte-ml\agentic
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Confirm the whole AppTest suite passes. Capture **actual running Streamlit** entry/loaded/Analyse screens at desktop 1280px+ and phone ~390px. Inspect the suggested question full-text caption, one visible editable question, disclosure and consent, all five optional manual tool presentations, valid/missing time format, complete pair count, large integer+null, tied/missing groups, filtered > limit, multiple identical AI events, previous answer hidden after question edits, confirmation and stale Challenge guards, provider-error recovery, original JSON downloads. Check keyboard-only tab navigation and label focus. Do not substitute design mockups for screenshots.

### Live Gemini on user's Windows machine (separate from AppTest and offline)

Use only the existing private `.env`; do not upload, print or commit it. After confirming the model setting, enable the explicit provider consent, load the bundled example, and ask a **custom** question not identical to the suggested questions, e.g. "Check the data structure, then calculate total revenue by region and tell me which region is highest." Verify that the *actual provider trace* contains inspection and grouped-summary function calls with exact Python results and that the grouped result is primary. Next ask "Which product was best-selling?" and verify that the provider requests clarification because the CSV only has `category`, not `product`. Choose explicit grouping/metric or supply a contextual response and explicitly submit. Keep returned model commentary visibly unverified; a model list or mocked call is not a live pass. Capture success/failure and redacted details only. Do not print or transmit API keys.

## Remaining limitations

- General free-text semantic correctness and model interpretation cannot be proven by successful Python tool execution.
- AppTest and browser verification requires Streamlit and Gemini SDK imports; when packages cannot be installed, these remain blocked, not passed.
- Saved Findings, cross-file persistence and Revisit are not implemented (intentionally Stage 3+).
