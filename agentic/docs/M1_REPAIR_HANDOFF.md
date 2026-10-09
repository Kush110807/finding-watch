# M1 repair handoff — two independent-review defects

**Scope:** repairs to M1 only. No Challenge, Revisit, SQLite memory, UI redesign, new analysis tools or model configuration changes. **M1 remains a candidate awaiting review; M0 live Gemini verification remains open.**

## Version / provenance

- Required starting HEAD: `f6bf5755c444945ea64e552c008e530d705a174c`.
- Starting checkout was clean; the 24 source/document entries in `BYTE_Finding_Watch_M1.zip` were byte-compared with that commit and all matched.
- Development took place in a separate Git clone, preserving the previous source and all Phase 1–M1 history. See packaged history bundle (`phaseM1-repair-history.bundle`).
- The resulting repair commit and archive SHA-256 are recorded in the accompanying external handoff; run `git rev-parse HEAD` / `Get-FileHash` independently after unpacking.

## Defect 1 — fixed-width integer overflow

### Root cause

`grouped_summary()` and `time_trend()` used pandas grouped `sum()`. On 64-bit integer series this can wrap without yielding a non-finite value, so the existing `result()` finite check cannot catch it. Additionally, pandas `to_json` and inferred nullable float result columns can silently lose or coerce large integers.

### Repair

- All grouped and time **integer sums** now use Python's unbounded integer addition over the full selected rows, maintaining exact integer values through `result()` and JSON encoding. No multiplication by a float, no fixed-width accumulation.
- Floating sums and means use `math.fsum` and reject overflow / non-finite accumulation with a controlled `AnalysisError` (rather than label a result completed). This intentionally rejects some finite means whose intermediate sum is outside the supported range.
- Means of integer inputs above `2**53` are explicitly rejected to avoid silent float precision loss. Numeric min/max and row counts remain exact; correlation rejects integer inputs beyond `2**53` rather than round them.
- Rows with missing metrics retain `null` results when entirely missing. Result creation explicitly preserves Python `int` even when some groups have missing metric values.
- Evidence warns when an exact integer exceeds `2**53`: browser and spreadsheet renderers may not display all digits. Python JSON and downloaded JSON contain the exact decimal integer.

### Independent regression truth

Synthetic CSV `g,amount` + **10,000** times `A,999999999999999`:

```json
{"tool":"grouped_summary","arguments":{"group":"g","metric":"amount","operation":"sum"}}
```

Exact integer answer: `9999999999999990000` (also for `time_trend` using date `2026-01-01`). The previous wrapped value `-8446744073709561616` must not appear. JSON must roundtrip the correct integer, and `calculation_status` may be `completed` **only on a successful exact result**.

Also covered: all-missing groups, positive/negative sums, min/max, count, float cancellation, infinite float totals, unsafe integer means, precision-risk correlations.

## Defect 2 — malformed specifications

### Root cause

Some validation paths used set membership before checking input type, producing `TypeError` on unhashable arrays/dicts. The `run_tool('filter_rows', ...)` adapter unpacked `filters` with a star expression before validating that it was a list.

### Repair

- `specs.py` validates filter operators and date formats as strings **before** set membership; rejects non-text mapping keys.
- `engine.py` validates direct entry point operators / formats / tool names as strings. The `filter_rows` adapter validates its filter list **before** unpacking.
- `agent.py` treats non-object model tool arguments as controlled tool errors and only catches `AnalysisError` from application validation; unexpected internal coding exceptions are not swallowed. Controlled errors carry their safe concrete explanation into the tool trace.
- Tests cover the reported `operator=[]`, `date_format=[]`, `filters=None` repros and related malformed field names, arguments, unknown operations, date format objects, invalid field keys and legacy entry points.

## Existing workflows and new boundaries

The same five tools remain: `inspect_dataset`, `filter_rows`, `grouped_summary`, `time_trend`, `correlation`. Original manual UI is unchanged. A test fixture was updated to the current `evidence_available` response shape, including actual deterministic tool evidence, submitted-question binding and pending input changes. No credentials or private local configuration are bundled.

### Limitations

- Very large integer totals are exact in Python/JSON, but client-side browser/Spreadsheet IEEE-754 number rendering may round digits; consult JSON as ground truth.
- Floating-point inputs remain floating point; `math.fsum` improves accumulation but cannot recover precision already lost in source numbers or during CSV parsing. Very large float sums/means are rejected rather than silently overflowed.
- Means for integer values greater than `2**53` are not supported; sums/min/max work for valid integer columns.
- CSV columns with 16+ digit integral tokens remain **text** under the conservative M1 parser unless explicitly converted in a separate controlled workflow. Identifier-like and leading-zero fields remain text.
- SDK and Streamlit test modules cannot be executed in the audit environment without `google-genai` and `streamlit`; rerun on Windows after installing pinned requirements.
- M0 live tool-use checks require a locally configured provider account and are not implied by any unit test or model listing.

## Windows verification (PowerShell, no secrets printed)

```powershell
Expand-Archive -LiteralPath "$HOME\Downloads\BYTE_Finding_Watch_M1_REPAIRED.zip" -DestinationPath "$HOME\Documents\BYTE-M1-Repair" -Force
cd "$HOME\Documents\BYTE-M1-Repair\byte-ml\agentic"
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# All tests, including mocked SDK and Streamlit AppTest
.\.venv\Scripts\python.exe -m unittest discover -s tests -v

# Reviewer regressions in isolation
.\.venv\Scripts\python.exe -m unittest discover -s tests -p 'test_m1_repairs.py' -v

# Manual UI verification, not a model integration check
.\.venv\Scripts\python.exe -m streamlit run app.py
```

With an already-private, locally present `.env` / environment `GEMINI_API_KEY`, M0 is **separate**:

```powershell
.\.venv\Scripts\python.exe verify_live.py --output live_verification_local.json
```

Inspect redacted error messages, used model, actual tool calls and correct synthetic results. Do not upload `.env`, raw SDK network logs or unreviewed files. See `docs/M0_WINDOWS.md` for the three required M0 checks.

## Verification categories

- **Offline**: the `test_engine.py`, `test_m1.py`, and `test_m1_repairs.py` suites exercise real deterministic calculations.
- **Mocked model**: `test_agent.py` requires Google GenAI package and uses synthetic SDK objects rather than network calls.
- **UI**: `test_app.py` requires Streamlit AppTest and mocks `agent.ask` for chat interactions.
- **Live model**: `verify_live.py` calls the actual configured provider on Windows; not executed during this repair.

All test counts and environmental blockers must be stated separately in the external handoff. No acceptance is implied.
