# Finding Watch — Stage 1 source handoff (pending review)

## Scope

Baseline `800619d0a3a9171513afa92b4f5e542206bfc381` is preserved. This stage makes Streamlit's entry, question, and calculated answer concise without modifying `engine.py`, `specs.py`, `comparisons.py`, or `agent.py`. No persistent memory, Revisit, forecasting, new planning engine or JavaScript frontend is added.

### User journey

1. Open the app. Neither dataset nor computation is selected automatically; choose **Try an example** or **Upload CSV**.
2. Dataset name, SHA-256 prefix and record count appear, with inspection behind an expander and explicit **Profile all columns** action.
3. The first schema-derived example is suggested but never run automatically. Choose a local example or edit the question; select **Analyse**. Suggested questions map only to bounded, prevalidated deterministic specifications based on the *actual* dataset columns. Custom free text is passed to Gemini only after consent.
4. A completed result leads with an evidence-derived statement, followed by metric/scope, compact table, a safe chart where useful and material warnings. The complete evidence, execution spec and original JSON download live in **How this was calculated**.
5. For AI traces, inspection is supporting context when exactly one analytical calculation exists. If two or more analytical results exist, the user must select which to inspect. The choice does not certify model intent. Every trace result stays in a collapsed supporting section with an independently keyed download.
6. The original clarification and confirmation-gated Challenge paths remain accessible. Five manual tools are available through **Advanced** in the sidebar.

### Verified offline fixture

For `data/demo_sales.csv`, the grouping `category`, metric `revenue`, sum, and no filters yields Coffee 3000, Snacks 1400, difference 1600, and 4 selected/input rows. `revenue` is the column label, *not* a currency. Count is labelled as records unless independently defined otherwise. Exact integer/null evidence is rendered as text before a pandas display DataFrame is created; charts are omitted for unsafe numeric magnitudes or missing values.

### Runtime review requirements (Windows)

Run in `byte-ml/agentic`:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Take real screenshots at desktop 1365×900 and a phone viewport about 390×844 of **entry**, **loaded example**, and **submitted revenue result**. Verify exact totals/difference, collapsed evidence, keyboard tab order, no horizontal overflow, consent, actual CSV upload and change to an unrelated schema. Test the five manual operations and their Challenge confirmation/stale edit state, inspection+aggregation trace, repeated identical responses/downloads, precision fixture, nulls, ties, provider failure, and JSON download byte/value equivalence. Do not treat this design brief as browser proof. No API key should appear in screenshots, logs or packages.

### Remaining limits

Custom free-text questions require the configured provider and explicit consent; local suggested questions are narrow templates, not a natural-language planner. A calculated tool result does **not** confirm that Gemini selected the relevant tool. The UI cannot infer business units, currencies, causality or meaning beyond explicit fields. Only a user-selected result among multiple candidate calculations is elevated to the visible finding.
