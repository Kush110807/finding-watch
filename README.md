# BYTE Applied ML — Finding Watch (Stage 1 review candidate)

**Stage 1 is pending independent review and is not accepted.** Starting commit `800619d0a3a9171513afa92b4f5e542206bfc381` preserves M1's deterministic evidence and the accepted, confirmation-gated M2 Challenge. M3, Saved Findings persistence and Revisit are not implemented. BYTE Basic Agentic Task only.

## Start locally (Windows)

```powershell
cd agentic
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Open the app and choose **Try an example** or **Upload CSV**. The main path uses a dataset-specific suggestion or an explicit custom question and the **Analyse** action. Suggestions execute a bounded Python tool locally, without Gemini. Custom natural-language questions require explicit Gemini consent in the optional settings and a configured private API key. Python performs calculations; model explanations are not independently verified.

The first result shows the evidence-derived finding, scope and definition, small exact-valued table, safe chart where possible, and material exclusions. The original calculation JSON and complete operation details are under **How this was calculated**. Inspection, full previews and other trace results remain behind explicit controls. Five manual analytical tools remain available in **Advanced** in the sidebar. Existing one-filter Challenge comparisons require confirmation.

**Evidence fixture:** `agentic/data/demo_sales.csv` has Coffee revenue 3000 and Snacks revenue 1400 (difference 1600; four records, no filter). No currency or order meaning is inferred. Comparisons that might round unsafe integers do not render numeric charts.

## Review and limitations

See [Stage 1 handoff](agentic/docs/STAGE1_HANDOFF.md), which separates deterministic, SDK-mocked, Streamlit AppTest, browser and live-provider evidence. In the candidate build's authoring environment, Streamlit and the Gemini SDK could not be installed because the package host was unreachable; no actual app screenshots are claimed. Perform the Windows suite, upload/clarification/provider checks and real desktop/mobile screenshot review before acceptance.

The full Git history is preserved in the accompanying `stage1-history.bundle`. Restore with `git clone -b main stage1-history.bundle byte-ml-stage1`. No credentials, virtual environments or live verification logs are included in the archive.


## Stage 1 presentation cleanup

The app starts with a CSV upload/example, optional suggested questions, and an evidence-first answer. The optional five-tool workbench remains available in the initially collapsed sidebar. The exact JSON evidence and user-confirmed Challenge remain supported. See `agentic/docs/STAGE1_PRESENTATION_CLEANUP.md` for the current independent-review handoff and required Streamlit/browser checks.
