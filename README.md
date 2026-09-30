# BYTE ML — Phase 1
Two selected tasks: Agentic Task and Paper Craft. This is a foundation checkpoint, not a completed submission.

## Windows setup (PowerShell)
Install Python 3.11 if needed. Extract the ZIP, open PowerShell inside `byte-ml`, then run:

```powershell
cd agentic
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```
Open the Local URL printed by Streamlit (normally http://localhost:8501). Keep the terminal running; Ctrl+C stops it. Virtual-environment activation is not required.
Expected: foundation banner, synthetic four-row table, five planned tools, disabled question box and no-key status. No model access is needed.

## API key (needed later)
Initial provider: Gemini. Visit https://aistudio.google.com/apikey and follow your account's key/project creation flow. Availability, quota and charges depend on your account; do not assume unlimited free access.
Inside `agentic`, copy `.env.example` to `.env` and set `GEMINI_API_KEY` locally. Do not paste it into chat, Git or screenshots. Model choice and actual connection testing happen in Phase 3. Phase 1 only checks whether a key is present; it does not validate it.

## What exists
`agentic/app.py`: runnable setup screen and example-data preview.
`agentic/data/`: synthetic CSV.
`agentic/docs/`: scope, requirements, contribution record and verification results.
`paper-craft/`: next steps, not a completed paper response.
`phase1-history.bundle`: portable Git history included in delivery; see below.

## Continue the Git history
Git is optional for launching but required for our development history. The ZIP excludes the internal Git directory. To restore the existing checkpoint rather than inventing new history, run from a parent folder:

```powershell
git clone path\to\byte-ml\phase1-history.bundle byte-ml-working
cd byte-ml-working
```
Then follow the setup above. The source in the bundle matches the checkpoint in the ZIP. No GitHub repository has been created or published.

## Verification
See `agentic/docs/VERIFICATION.md`. Linux checks do not replace your Windows launch check. No live LLM, complete agent or analysis-tool accuracy is claimed at this phase.
