# Finding Watch — Stage 3 focused UI cleanup (review candidate)

## Scope / baseline
- Starting commit: `dc3dd3d625dea94d92e33ea4aecd86de7078f1c7`.
- Four protected files **unchanged**: `agentic/engine.py`, `specs.py`, `comparisons.py`, `agent.py`.
- No memory, persistence, Revisit, new analytical tools, provider routing, or Challenge capability changes.
- The previously reported 231 Windows passes, live Gemini monthly totals, and clarification success apply to the **previous build**; they are **not** counted as verification of this release.

## Changes
1. `presentation.time_chart_points` sorts **observed engine period_start dates**, not strings like `Feb 2026` / `Jan 2026`; Streamlit plots compact teal bars using a **temporal** axis called Month / Week starting / Date. Only observed buckets appear. A bar chart avoids falsely connecting missing periods with a line. Original result JSON unchanged; unsafe-number chart guard still applies.
2. Clarification uses two independent, initially unselected controls: **What should the results be grouped by?** and **What should be measured?** A dynamic sentence previews the exact selected definition (e.g. “Compare categories by total revenue.”), updating *before* submission. The old form was changed to ordinary Streamlit widgets and an explicit button precisely because a form would defer widget updates and not display the preview before submission. Same numeric grouping/metric values are permitted but explained; changing either choice hides an older clarified calculation. No question, grouping, or metric is automatically inferred.
3. Completed Challenge now renders its conclusion, comparison and original/alternative definitions once, while hiding the entire condition editor. An explicit **Edit condition** control revokes the reviewed plan and completed approval/result and reopens the editor. Fresh Review and Confirm are mandatory. The comparison and evidence JSON are unchanged.
4. Multiple-calculation selection copy is short and direct, while the existing neutral unselected option and occurrence bindings remain authoritative. Selecting is still an explicit user action; identical calls remain distinct.

## Verification (performed in this environment)
- Offline tests: **169 passed, 0 failed**, including six new focused tests for chronology, sparse periods, evidence-derived time totals, clarification definitions, numeric same-column guidance, and confirmation revocation/preservation.
- Full unittest discovery: **171 entries: 169 passed and 2 module import errors** (`streamlit`, `google.genai`). Neither real Streamlit AppTests nor SDK-dependent tests ran.
- Syntax compilation and Git diff whitespace check passed.
- Runtime launch/screenshots/live Gemini: **not executed**. Streamlit installation was attempted via the configured package index; package-network DNS resolution failed. Prior Windows and live-provider checks are not proofs of this changed source.
- AppTest cases updated for reactive clarification and the collapsed editor. Added real AppTest cases verify the definition and warning without submission, confirmed comparison-first view, one pair of visible definitions, no visible condition editor, evidence downloads, and edit revocation. These AppTests must run in Windows.

## One combined Windows verification pass
From the extracted ZIP's `byte-ml\\agentic` directory in PowerShell:

```powershell
py -3.13 -m venv .venv
.\\.venv\\Scripts\\python.exe -m pip install -r requirements.txt
.\\.venv\\Scripts\\python.exe -m unittest discover -s tests -p test_app.py -v
.\\.venv\\Scripts\\python.exe -m unittest discover -s tests -v
.\\.venv\\Scripts\\python.exe -m streamlit run app.py
```

In the **same final browser session**, at desktop and approximately 390px width, verify: example and uploaded data; all five tools; result selection, repeated identical occurrences and stale results; Gemini optional consent and private configuration; provider recovery; date table **and chart** ordered January then February (monthly synthetic data); clarification with category vs region, total revenue vs record count, same-column warning and explicit submission; completed Challenge conclusion/table above one original/alternative definition; editor hidden until **Edit condition**; changing condition removes completed comparison and JSON download; fresh Review and Confirm; precise integer/null/absent-group tables; original JSON downloads and unique keys. Use local synthetic data for deterministic checks. For one separate custom live Gemini question and clarification follow-up, confirm real provider tool calls and log redacted errors without sharing `.env`.

## Acceptance status
This candidate is for independent source review and one combined runtime verification. Acceptance is not claimed. Stop before further milestones.
