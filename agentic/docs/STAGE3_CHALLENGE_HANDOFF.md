# Finding Watch — Stage 3 Challenge UI/state candidate (not accepted)

## Provenance and boundaries

- **Required parent**: `fd6c01da1433d8cacf0a74f592ac306e3effbb26` (16 previous commits).
- No edits to `engine.py`, `specs.py`, `comparisons.py`, or `agent.py`.
- Uses the existing `prepare_comparison()` (validation only) and `execute_comparison()` (deterministic calculation) contracts. At most one filter may be added, removed, or replaced; grouping, metric, operation, display limit and all unchanged filters are inherited verbatim.
- No Stage 4, M3, persistence, memory, Revisit, arbitrary execution or framework migration.
- This candidate is not accepted; independent review and the combined Windows checks are required.

## Visible interaction and state contract

1. An eligible **submitted grouped finding** offers **Test another condition**, plus a short purpose statement. Nothing is proposed or calculated by opening the editor.
2. Choose add/replace/remove explicitly. Existing conditions are shown as readable choices for replace/remove. Choose a column, then a compatible operator, then a typed value (or explicitly check missing/not missing). Fields start unselected, not at `date = ''`. The user's real dataset supplies categorical options where bounded. Leading-zero text values remain text. Dates are compared as literal data, without parsing or guessed date order. Numeric input is validated and rejects unsupported large filter boundaries.
3. Only **Review comparison** calls `prepare_comparison`, which never executes the calculation. The preview shows the original and alternative inclusion rules and the unchanged grouped measure. **Confirm and compare** alone calls `execute_comparison` for the exact reviewed plan/dataset fingerprint. **Edit condition** discards the preview and approval.
4. The result begins with the leader outcome derived from complete grouped evidence. The compact table is formatted from exact original values before pandas sees it. Absent groups, zero, all-missing metrics, and ties are different. Scope, row selection, material exclusions and truncation are visible; technical evidence and unchanged JSON are collapsed under **How this was compared**.
5. Review/confirmation records are scoped by submitted-finding binding (source fingerprint, question/definition and submission occurrence, plus trace index for Gemini). A changed control invalidates both preview and old result; a new submission or dataset resets the editor. A no-matches calculation error leaves the editor available for correction.
6. The original, separately validated Gemini comparison-proposal confirmation gate remains functional. It does not gain automatic approval. The existing five analytical tools, advanced manual controls, consent, clarification and analysis remain in place.

## Change list

- `agentic/app.py`: replace the old auto-proposed Challenge controls with the new explicit editor; connect selected Gemini grouped findings; give each manual/local/clarified submission an occurrence token.
- `agentic/challenge_ui.py` **new**: Streamlit-only entry, editor, reviewed preview and confirmation-state renderer.
- `agentic/challenge_logic.py` **new**: deterministic operator eligibility, numeric validation, condition creation, submission-binding identity and exact-value comparison presentation.
- `agentic/ui_components.py`: concise evidence-based comparison presentation; full unmodified JSON download moved under `How this was compared`.
- `agentic/download_keys.py`: declare `ai_selected_comparison` as another non-trace download surface.
- `agentic/tests/test_stage3_logic.py` **new**: deterministic golden cases, type/precision/absence/tie/truncation/state-identity regressions.
- `agentic/tests/test_app.py`: migrate existing Challenge AppTests to the explicit gate and add new real Streamlit AppTests (not counted as passing until run).
- `agentic/docs/STAGE3_CHALLENGE_HANDOFF.md` **new**: this verification guide.

## Combined Stage 2 + Stage 3 Windows verification — one final session

All commands below run in PowerShell, from the extracted `byte-ml\agentic` folder. Use existing **private** Gemini configuration; do not copy `.env` into test packages or logs.

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_app.py -v *> app_test_windows.log
.\.venv\Scripts\python.exe -m unittest discover -s tests -v *> full_suite_windows.log
.\.venv\Scripts\python.exe -m streamlit run app.py
```

For **screenshots of the actual running Streamlit app** use the browser at approximately 1365px desktop width and 390px phone width, in the same final verification session. Capture desktop and phone (a) entry state, (b) loaded example and answer, (c) unopened Challenge, (d) incomplete editor, (e) review awaiting confirmation, (f) confirmed comparison, and (g) edited/stale and no-match recovery. Never substitute HTML mockups.

### Functional browser checklist

- Test Try example and upload pathways. The bundled demo's `category`/`revenue` summary is Coffee 3000, Snacks 1400. Test **Region is North**: Coffee 1200, Snacks 800; leader unchanged. Baseline 4 records; alternative 2 records.
- Test existing M2 fixture in `docs/fixtures/golden_orders.csv`: Coffee 510 vs Snacks 280; after `status is completed`, Coffee 210 vs Snacks 280; changed leader and differences -300/0. Confirm that this uses the dataset rows, not hardcoded examples.
- Confirm opening/choosing filters does not compute or auto-review; incomplete definitions cannot reach confirmation. Add, remove and replace exactly one condition. `is missing`, `is not missing`, and empty text are distinct where supported. Check text identities, numeric validation, and changed existing filters.
- After Review, inspect original/alternative/unchanged definitions. Edit condition, change submitted question/dataset, rerun same question, and switch selected Gemini occurrence; in each case old approvals/downloads must disappear. Confirm only the matching reviewed plan. No-match retains editor and shows a recoverable message.
- Verify original/alternative table, exact integers, zeros, missing/all-missing values, absent groups, ties, visible material exclusions and truncation. Check `How this was compared` is collapsed and JSON downloads byte-for-byte match the original calculation dictionary (no reordered/rounded evidence from UI).
- Recheck **all five manual tools**, contextual and grouped clarification, clarified-result Challenge, provider error after a prior answer, result choice across repeated identical Gemini outputs, and the Stage 2 duplicate-download regression scenarios. Check keyboard/focus and phone wrapping; no essential text clipped.
- Keep provider errors separate from rejected calculations. Do not display secrets.

### Fresh live Gemini — separate from mocked tests

- Use the existing local `.env` or environment configuration without displaying its contents; provide user consent in the application.
- Ask a **new** dataset-appropriate question that genuinely requires model tool choice, e.g. “How does the total of revenue compare between categories?” Verify the returned real Gemini tool call, executed Python evidence and explanatory status. A model-listing or mocked call does **not** count.
- Ask an ambiguous custom question (“Which product sold best?” when only category exists), provide explicit grouped/metric or date context, and verify no calculation runs merely from choosing an option. Observe the actual provider follow-up and the preserved original question.
- If provider unavailable, record sanitized status/error and complete deterministic manual tests independently. Do not upload credentials.

### Evidence categories to report independently

1. Offline deterministic counts (this container).
2. Mocked real-SDK tests (requires SDK; **not** a live provider check).
3. Real Streamlit AppTests plus running-browser screenshots (requires Streamlit).
4. Fresh live Gemini (requires user's private configuration/consent).

No statement of success is justified for an unexecuted category.
