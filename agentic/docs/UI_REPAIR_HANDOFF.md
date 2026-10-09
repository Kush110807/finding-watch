# Finding Watch — P1–P3 UI repair (independent-review candidate)

## Version and scope

- Source baseline required: `98b5e066a46f9cbd7d7d48193ca7abf2ff3bfb51`.
- M2 remains frozen and accepted at `4bf170a16fafe420b1c633e4b13fe96b7f76c1fe`.
- Scope is repair-only. No memory, persistence, Revisit, M3, forecasting, redesign,
  simulation content or new analytical operation.
- The numeric execution contract in `engine.py`, `specs.py` and `comparisons.py`
  was **not changed**. The exact original calculation evidence and downloads
  remain intact.

## Repaired UI defects

1. `ui_components.py` now converts scalars from immutable tool `rows` through
   `presentation.display_rows()` **before** constructing pandas tables. All
   displayed cells are text for this purpose. Large exact Python integers are
   formatted losslessly and null metric values are explicitly `No numeric
   value`. Original evidence remains Python int/null and JSON downloads use
   the original result object. Comparison tables were already built as text;
   their exact-value behavior is covered by a regression.
2. Manual and Gemini comparison approval labels reflect the actual executed
   plan. A matching confirmed calculation gets a success statement, not a
   pending warning, and a changed definition hides old comparison output and
   download. `confirmed_comparison_matches` also checks the submitted baseline
   binding and completed calculation status.
3. Clarified grouped results now display their **own** Challenge controls,
   tied to the exact clarified output, dataset, original question and chosen
   metric/group. No unrelated manual result is substituted. For a Gemini
   follow-up, the user must explicitly pick a named submitted baseline;
   the prior automatic fallback from old AI/manual calculations was removed.
   The selection is reset when the list or definitions change.
4. Clarification now has two *unselected* routes: explicit grouping+measure
   (validated `run_tool`) or free-text contextual explanation. The latter
   sends the **unchanged original question** and a separate, bounded
   `clarification_context` field into the Gemini request. It never parses
   model prose as an executable calculation. This small agent adapter change
   was necessary to preserve original-question identity for dates and other
   non-grouped questions.
5. `test_app.py` real Streamlit assertions now inspect the correct warning
   components, comparison/download visibility and confirmed vs pending text;
   new cases cover the clarified-result Challenge, exact large integers,
   contextual clarification and explicit Gemini baseline selection.
   `test_ui_repairs.py` covers the exact review CSV, missing values, precision,
   source immutability and baseline binding in offline tests. The adapter shim
   suite includes contextual payload validation.

## Actual verification and limitations

Local offline tests pass (legacy calculation tests, prior M1/M2/UI tests,
new pure-UI regressions and isolated mock-SDK adapter tests). Full discovery
cannot load the **real** `test_agent` or `test_app` modules here because
`google.genai` and `streamlit` are not installed. Internet/DNS-based package
installation is unavailable. Accordingly real SDK mocked tests, Streamlit
AppTest, actual running desktop/mobile screenshots and any new live-provider
check **are not verified here**. Earlier Windows reports are not being
reclassified as verification of the repaired UI.

The golden review CSV in `docs/fixtures/overflow_ui.csv` contains eleven
`A,999999999999999` records and a twelfth `B,` record. Exact Python evidence:
`A=10999999999999989`, `B=null`. Exact table display:
`A=10,999,999,999,999,989`, `B=No numeric value`.

See `docs/UI_REPAIR_WINDOWS.md` for full Windows and screenshot checklist.

## Source policy

`engine.py`, `specs.py`, `comparisons.py` unchanged. No `.env` or credentials
included in the source archive. No acceptance or M3 work is claimed.
