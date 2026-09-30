# BYTE ML — Phase 3 candidate
Local analysis tools plus a bounded Gemini tool-calling agent. Live API validation is pending. Persistent memory is not implemented. Manual tools still work without an API key.

## Upgrade from Phase 2 on Windows
Stop Streamlit with Ctrl+C. Copy the contents of this ZIP's `byte-ml/agentic` folder into your existing `byte-ml/agentic` folder, replacing matching source files. Keep your existing `.venv` and any private `.env`; neither is included in this ZIP. Install the updated requirements: google-genai is new.
From that existing agentic folder:
```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m streamlit run app.py
```
Refresh the browser. The heading should say Phase 3.

## Fresh setup
Python 3.13 is installed on the user's Windows machine and launched Phase 1 successfully. In the extracted `byte-ml/agentic` folder:
```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m streamlit run app.py
```
Use the Local URL printed by Streamlit. Keep the terminal open. Ctrl+C stops the server.

## Windows acceptance checks
1. Example sales → Summarise groups → category / sum / revenue: Coffee 3000, Snacks 1400.
2. Analyse time trends → date / %Y-%m-%d / month / sum / revenue: January 1800, February 2600.
3. Filter rows → category / Equals / Coffee: two rows.
4. Upload `data/student_practice.csv`: Inspect shows 5 rows; study_hours has 1 missing value.
5. Correlate study_hours and score: Pearson r = 1 with 4 complete pairs and 1 excluded row.
6. Change a filter or dataset: old results must disappear until you run again. Upload a malformed CSV: readable error, no traceback.
7. Download result JSON and inspect the tool, dataset identifier, rows and metadata.

## Structure
`app.py`: user interface. `engine.py`: CSV validation and five read-only tools. `tests/`: independent expected-value tests and Streamlit interface checks. `docs/`: decisions, scope, contribution log and verification.

## Supported input and behaviour
UTF-8 comma-separated CSV with a unique non-empty header; 10 MiB / 100,000 rows / 100 columns. Only empty fields are missing; labels such as NA are retained. Pandas infers numeric types; numeric-looking IDs may lose leading zeros. Do not use this version when exact preservation of such IDs is required; configurable schema/ID handling remains future work. Mixed numeric/text columns are not silently cleaned.
Results are read-only; no uploads saved to disk. Manual analysis makes no model requests. AI questions send schema, question and bounded tool results to Gemini after the data-sharing checkbox is selected. Phase 2 results use all input rows; preview and filtered returned rows are explicitly limited. Correlation does not establish causation. Date formats are explicitly selected. See PLAN.md for later scope.

## Git history
The ZIP contains `phase3-history.bundle`, preserving all implementation checkpoints. To restore history, from a parent folder run:
```powershell
git clone path\to\byte-ml\phase3-history.bundle byte-ml-working
```
No remote repository was created or published. Do not commit `.env`, uploads, or API keys. See docs/CONTRIBUTIONS.md for the actual AI-assistance record.

## Phase 3 local connection check
Keep your existing secret `.env` in the current Phase 2 `agentic` directory when upgrading. Do not upload it. A blank GEMINI_MODEL now uses gemini-3.8-flash, as listed in Google's documentation checked 30 September 2026. Account access, compatibility and quota must be verified with a real request.
1. Run tests: expected 42 tests, OK.
2. Launch app, expand Connection setup and click Check available models. This does not itself test model inference or tool calling.
3. If needed set GEMINI_MODEL to an available text/function-calling model, then rerun the app. No silent fallback or billing changes occur.
4. Use synthetic Example sales; select the Gemini data-sharing checkbox.
5. Ask: Which category has the highest total revenue?
Expected: grouped_summary tool evidence showing Coffee 3000 and Snacks 1400, then a consistent explanation.
6. Ask: Show total revenue by month using date format YYYY-MM-DD.
Expected: time_trend with January 1800 and February 2600.
7. Ask: Which column is best? Expect clarification, not an invented metric.
8. Download evidence JSON for review; it contains your question's analysis results, but never the API key. Share errors without credentials.

Each question is independent; no conversational or persistent memory yet. Tools do not chain filtered datasets. Unsupported calculations should trigger clarification. A tool-backed explanation can still contain model mistakes: inspect evidence. No automatic retry; 30-second per-request timeout, at most six model rounds and eight tool executions. No browser, shell or generated-code execution is exposed to the model.

## API implementation references
https://googleapis.github.io/python-genai/
https://ai.google.dev/gemini-api/docs/function-calling
https://ai.google.dev/gemini-api/docs/models
