# BYTE ML — Phase 2
Local analysis workbench with CSV upload and five deterministic tools. AI chat and memory are not implemented yet. No API key needed.

## Upgrade from Phase 1 on Windows
Stop Streamlit with Ctrl+C. Copy the contents of this ZIP's `byte-ml/agentic` folder into your existing `byte-ml/agentic` folder, replacing matching source files. Keep your existing `.venv` and any private `.env`; neither is included in this ZIP. Dependencies are unchanged.
From that existing agentic folder:
```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m streamlit run app.py
```
Refresh the browser. The heading should say Phase 2.

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
Results are read-only; no uploads saved to disk. No LLM or network calls in the application. Model integration will later require a documented data-sharing boundary. Phase 2 results use all input rows; preview and filtered returned rows are explicitly limited. Correlation does not establish causation. Date formats are explicitly selected. See PLAN.md for later scope.

## Git history
The ZIP contains `phase2-history.bundle`, preserving both implementation checkpoints. To restore history, from a parent folder run:
```powershell
git clone path\to\byte-ml\phase2-history.bundle byte-ml-working
```
No remote repository was created or published. Do not commit `.env`, uploads, or API keys. See docs/CONTRIBUTIONS.md for the actual AI-assistance record.
