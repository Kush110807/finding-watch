# M0 — Local LIVE Gemini Verification (Windows only)

**State at packaging:** NOT verified. We did not access your `.env`, call Gemini with a real key, or inspect a local Windows run. A model listing, unit test, and mocked call are **not** live verification. This check is deliberately independent from the offline M1 engine.

## Preparation

Use PowerShell. Extract `BYTE_Finding_Watch_M1.zip` somewhere you control (for example `Documents\BYTE-Finding-Watch-M1`). Do not upload a key or `.env` to anyone. In PowerShell, navigate to the extracted `byte-ml\agentic` directory:

```powershell
cd "$HOME\Documents\BYTE-Finding-Watch-M1\byte-ml\agentic"
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

If you already have a working local Gemini configuration, keep it in your private existing `.env`; place your **existing** `.env` alongside `agentic\agent.py` only on your laptop. Never copy it into Git or ZIP submissions. Alternatively, use a local `GEMINI_API_KEY` environment variable; `agent.py` reads it. The script does not print the key.

If installation fails, record the package name and **redacted** error; do not count M0 as done. Pinned versions are in `requirements.txt`. Python 3.13 was used in the prior Windows prototype; compatibility with the current dependency versions still needs confirmation on your machine.

## Execute the three real requests

```powershell
.\.venv\Scripts\python.exe verify_live.py --output live_verification_local.json
```

The script calls the actual configured provider (no mocks) with the following **synthetic** table, which contains no personal data:

| date | category | revenue |
|---|---|---:|
| 2026-01-01 | Coffee | 10 |
| 2026-01-02 | Coffee | 20 |
| 2026-02-01 | Snacks | 5 |

Expected tool and independent numerical truth:

1. **Grouped sum / ranking:** `grouped_summary` with `group=category`, `metric=revenue`, `operation=sum` — Coffee **30**, Snacks **5**.
2. **Time trend:** `time_trend` with date format `%Y-%m-%d`, monthly sum — January **30**, February **5**.
3. **Ambiguous question:** "Which column is best?" should explicitly call `request_clarification`. A direct prose answer, a model listing, or a fabricated metric **does not pass**.

The JSON log records the configured **model name**, synthetic **questions**, actual returned **tool names/arguments/results**, model response status, each check's verdict and an error message sanitized by the application. The tool calculation and the unverified model explanation are distinguished. The script writes no credentials. Inspect JSON before sharing anything. **Do not share `.env`, debug network dumps, or raw SDK tracebacks.**

If provider access, quota, network, tool schema, or model support fails, report the specific redacted blocker and leave M0 open. No automatic model fallback is performed. A passing M0 requires all three checks plus human inspection that model narrative matches the evidence. The script's `live_verified: true` means the three mechanical checks passed, **not** that all natural-language outputs are reliably correct.

## UI regression / manual checks

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

- Example sales → Grouped sum of `revenue` by `category`: Coffee **3000**, Snacks **1400**.
- Example sales → month totals: Jan **1800**, Feb **2600**.
- Add optional AND filters under a grouped/time/correlation analysis; inspect `Executed specification and calculation evidence`. Confirm `selected_rows` reflects filters and matches the saved results, not the 100-row preview.
- Upload `data/student_practice.csv`, inspect (5 rows), correlate `study_hours` and `score` (r = **1**, four complete pairs).
- Enter different manual controls without running again: earlier results must be hidden and prompt for submission.
- Submit an AI question with consent and then edit text without submitting: old result remains labelled with the old **submitted question** and warns that newer edits are pending.
- Switch dataset: saved AI/manual results must not silently describe the new data.
- Check the M0 questions in Streamlit only after the CLI confirms real provider access. The CLI is the preferred machine-readable tool trace.

**Report UI and live verification separately.** Streamlit AppTest with a patched `ask()` is mocked, not live.
